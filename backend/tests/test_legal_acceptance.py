"""Audit Z4-8 — you could not say which text a user agreed to.

Nothing recorded terms or privacy acceptance, so "they agreed to the policy" was
unprovable. Under DPDP/GDPR the burden of proof is ours, and consent is to a
*specific text* — a later rewrite must not silently re-interpret what someone
agreed to years earlier. This copies the `consent_policy_version` pattern already
used for interview consent (Z4-5).

The load-bearing decision is that the version is **server-side**. The interview
flow takes `consent_policy_version` from the request body; that is fine there
because the value is corroborated by a live session, but for account-level
acceptance it would let a client claim agreement to a document that was never
displayed. The client is shown whatever the server currently serves, so the server
is the only honest authority on which version that was — and neither the register
serializer nor the accept endpoint reads a version from the caller.

The re-acceptance endpoint is not optional: without it, bumping
`LEGAL_TERMS_VERSION` sets `needs_legal_reacceptance` for every existing account
with no way to clear it, and the field becomes a permanent nag rather than a
record.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Profile

User = get_user_model()

PASSWORD = "Str0ng-Pass-1"


class SignupRecordsAcceptanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _register(self):
        from apps.accounts.serializers import RegisterSerializer

        s = RegisterSerializer(data={
            "email": "new@example.com",
            "password": PASSWORD,
            "accepted_legal": True,
        })
        self.assertTrue(s.is_valid(), s.errors)
        return s.save()

    @override_settings(LEGAL_TERMS_VERSION="2026-06-05", LEGAL_PRIVACY_VERSION="2026-08-08")
    def test_the_versions_are_stamped_at_signup(self):
        user = self._register()
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.terms_version, "2026-06-05")
        self.assertEqual(profile.privacy_version, "2026-08-08")

    @override_settings(LEGAL_TERMS_VERSION="2026-06-05")
    def test_the_moment_is_recorded_too(self):
        """A version without a timestamp cannot answer 'when'."""
        user = self._register()
        self.assertIsNotNone(Profile.objects.get(user=user).terms_accepted_at)

    def test_the_phone_number_is_still_stored(self):
        """The acceptance fields were added to an existing update_or_create; the
        defaults it already carried must survive."""
        from apps.accounts.serializers import RegisterSerializer

        s = RegisterSerializer(
            data={
                "email": "p@example.com",
                "password": PASSWORD,
                "phone_number": "+911234567890",
                "accepted_legal": True,
            }
        )
        self.assertTrue(s.is_valid(), s.errors)
        user = s.save()
        self.assertEqual(Profile.objects.get(user=user).phone_number, "+911234567890")

    def test_signup_requires_explicit_legal_acceptance(self):
        """Stamp without a tick would invent consent the user never gave."""
        from apps.accounts.serializers import RegisterSerializer

        s = RegisterSerializer(data={
            "email": "no-tick@example.com",
            "password": PASSWORD,
            "accepted_legal": False,
        })
        self.assertFalse(s.is_valid())
        self.assertIn("accepted_legal", s.errors)

    def test_signup_rejects_missing_legal_flag(self):
        from apps.accounts.serializers import RegisterSerializer

        s = RegisterSerializer(data={"email": "missing@example.com", "password": PASSWORD})
        self.assertFalse(s.is_valid())
        self.assertIn("accepted_legal", s.errors)


class _AuthedBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="legal", email="legal@example.com", password=PASSWORD
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _profile(self):
        resp = self.client.get("/api/auth/profile/")
        self.assertNotEqual(
            resp.status_code, 404,
            "/api/auth/profile/ is not routed — this test must fail on a wrong URL "
            "rather than pass silently",
        )
        return resp.data

    def _accept(self):
        resp = self.client.post("/api/auth/accept-terms/", {}, format="json")
        self.assertNotEqual(
            resp.status_code, 404,
            "/api/auth/accept-terms/ is not routed — bumping a version would strand "
            "every existing account with no way to clear the prompt",
        )
        return resp


@override_settings(LEGAL_TERMS_VERSION="v2", LEGAL_PRIVACY_VERSION="v2")
class TheProfileReportsTheStateTests(_AuthedBase):
    def test_an_account_predating_the_field_needs_reacceptance(self):
        """Blank is a truthful "we do not know", and a different answer from
        "agreed to an unknown version"."""
        data = self._profile()
        self.assertEqual(data["terms_version"], "")
        self.assertTrue(data["needs_legal_reacceptance"])

    def test_a_current_account_does_not(self):
        Profile.objects.filter(pk=self.profile.pk).update(
            terms_version="v2", privacy_version="v2"
        )
        self.assertFalse(self._profile()["needs_legal_reacceptance"])

    def test_a_stale_privacy_version_alone_triggers_it(self):
        """Either document moving is enough; requiring both would let a privacy
        rewrite ship unacknowledged."""
        Profile.objects.filter(pk=self.profile.pk).update(
            terms_version="v2", privacy_version="v1"
        )
        self.assertTrue(self._profile()["needs_legal_reacceptance"])

    def test_the_current_versions_are_exposed(self):
        data = self._profile()
        self.assertEqual(data["current_terms_version"], "v2")
        self.assertEqual(data["current_privacy_version"], "v2")


@override_settings(LEGAL_TERMS_VERSION="v2", LEGAL_PRIVACY_VERSION="v2")
class ReacceptanceTests(_AuthedBase):
    def test_accepting_records_the_current_versions(self):
        resp = self._accept()
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.terms_version, "v2")
        self.assertEqual(self.profile.privacy_version, "v2")

    def test_accepting_clears_the_prompt(self):
        self._accept()
        self.assertFalse(self._profile()["needs_legal_reacceptance"])

    def test_a_client_supplied_version_is_ignored(self):
        """Otherwise an account could claim agreement to a document it was never
        shown — including a future or fabricated version."""
        self.client.post(
            "/api/auth/accept-terms/",
            {"terms_version": "v99", "privacy_version": "v99"},
            format="json",
        )
        self.profile.refresh_from_db()
        self.assertEqual(
            self.profile.terms_version, "v2",
            "the endpoint trusted a version string supplied by the caller",
        )

    def test_it_requires_authentication(self):
        anon = APIClient()
        resp = anon.post("/api/auth/accept-terms/", {}, format="json")
        self.assertIn(resp.status_code, (401, 403))

    def test_a_second_bump_prompts_again(self):
        """Guard the guard: if acceptance were recorded once and never re-checked,
        every later policy change would ship unacknowledged."""
        self._accept()
        with override_settings(LEGAL_TERMS_VERSION="v3"):
            self.assertTrue(self._profile()["needs_legal_reacceptance"])
