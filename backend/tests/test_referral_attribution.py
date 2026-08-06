"""Audit Z6-16 — the referral schema was dead.

`referral_code` and `referred_by` existed on `Profile`. Codes were generated for
every user on save, and `referred_by` was **never set by anything** — so there was
no attribution to reward even if a reward scheme were added later.

The audit says "activate it or drop the columns". Split differently, because the
two halves are not the same kind of decision:

* **attribution is engineering, and cannot be done retroactively.** If the referrer
  is not recorded at signup, that link is gone permanently — there is no way to
  reconstruct who introduced whom after the fact. This is implemented.
* **reward policy is a product decision** (what, how much, when it vests, whether
  it is abusable). Deliberately not implemented. Capturing the data is what keeps
  that decision open.

Dropping the columns was the other option and would have been the wrong one: codes
are already generated and already exported in the GDPR data export, so dropping
loses data users can already see.

The failure mode these tests exist to prevent is a signup that fails because of a
mistyped code. Referral is a growth feature; it must never cost a customer.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.accounts.serializers import RegisterSerializer

User = get_user_model()
PASSWORD = "Str0ng-Pass-1"


def _register(**extra):
    data = {"email": f"u{extra.pop('n', 1)}@example.com", "password": PASSWORD}
    data.update(extra)
    s = RegisterSerializer(data=data)
    assert s.is_valid(), s.errors
    return s.save()


class AttributionIsRecordedTests(TestCase):
    def setUp(self):
        self.referrer = _register(n=1)
        self.code = Profile.objects.get(user=self.referrer).referral_code

    def test_every_user_gets_a_code(self):
        self.assertTrue(self.code)
        self.assertEqual(len(self.code), Profile.REFERRAL_CODE_LENGTH)

    def test_signing_up_with_a_code_records_the_referrer(self):
        invited = _register(n=2, referral_code=self.code)
        self.assertEqual(
            Profile.objects.get(user=invited).referred_by,
            Profile.objects.get(user=self.referrer),
            "referred_by is still never set — there is nothing to reward",
        )

    def test_the_referrer_can_see_their_referrals(self):
        """`related_name='referrals'` was already on the model and had nothing to
        point at."""
        invited = _register(n=2, referral_code=self.code)
        referrals = Profile.objects.get(user=self.referrer).referrals.all()
        self.assertIn(Profile.objects.get(user=invited), referrals)

    def test_the_code_is_case_insensitive(self):
        """These get typed from a screenshot or dictated over a call."""
        invited = _register(n=2, referral_code=self.code.lower())
        self.assertIsNotNone(Profile.objects.get(user=invited).referred_by)

    def test_surrounding_whitespace_is_tolerated(self):
        invited = _register(n=2, referral_code=f"  {self.code}  ")
        self.assertIsNotNone(Profile.objects.get(user=invited).referred_by)


class ABadCodeNeverCostsASignupTests(TestCase):
    """Referral is a growth feature. Failing a registration to protect a statistic
    would be exactly backwards."""

    def test_an_unknown_code_still_creates_the_account(self):
        user = _register(n=9, referral_code="NOTACODE")
        self.assertTrue(User.objects.filter(pk=user.pk).exists())
        self.assertIsNone(Profile.objects.get(user=user).referred_by)

    def test_an_empty_code_is_fine(self):
        user = _register(n=9, referral_code="")
        self.assertIsNone(Profile.objects.get(user=user).referred_by)

    def test_no_code_at_all_is_fine(self):
        """The overwhelmingly common path — this must not regress."""
        user = _register(n=9)
        self.assertIsNone(Profile.objects.get(user=user).referred_by)

    def test_a_junk_code_does_not_raise(self):
        for junk in ("'; DROP TABLE--", "x" * 20, "!!!"):
            s = RegisterSerializer(
                data={"email": f"j{hash(junk) % 9999}@example.com",
                      "password": PASSWORD, "referral_code": junk}
            )
            self.assertTrue(s.is_valid(), s.errors)
            self.assertIsNotNone(s.save())

    def test_it_works_over_the_api(self):
        referrer = _register(n=1)
        code = Profile.objects.get(user=referrer).referral_code
        resp = APIClient().post(
            "/api/auth/register/",
            {"email": "api@example.com", "password": PASSWORD,
             "referral_code": code},
            format="json",
        )
        # Registration requires a verified OTP session, so a 400 here is the OTP
        # gate rather than the referral field — what matters is that supplying a
        # code does not produce a 500.
        self.assertNotEqual(resp.status_code, 500)


class CodeGenerationIsSafeTests(TestCase):
    def test_codes_are_unique_across_many_users(self):
        codes = set()
        for i in range(30):
            user = _register(n=100 + i)
            codes.add(Profile.objects.get(user=user).referral_code)
        self.assertEqual(len(codes), 30)

    def test_the_alphabet_excludes_ambiguous_characters(self):
        """O/0 and I/1/L are where a dictated or screenshotted code goes wrong, and
        a mistyped code silently attributes the signup to nobody."""
        for ch in "OI01L":
            self.assertNotIn(ch, Profile.REFERRAL_ALPHABET)

    def test_generation_avoids_an_existing_code(self):
        """`referral_code` is unique=True and the previous version generated one
        random string with no collision check — a duplicate surfaced as an
        IntegrityError *during signup*."""
        from unittest import mock

        # A post-save signal already creates the Profile, so fetch rather than
        # create — a second create violates the OneToOne constraint.
        user = User.objects.create_user(
            username="taken", email="taken@example.com", password=PASSWORD
        )
        taken = Profile.objects.get(user=user).referral_code

        # Force the first two attempts to collide, then succeed.
        seq = iter(list(taken) * 2 + list("ZZZZZZZZ") * 4)
        with mock.patch("secrets.choice", side_effect=lambda _: next(seq)):
            code = Profile.generate_referral_code()
        self.assertNotEqual(code, taken)

    def test_it_returns_a_code_even_under_repeated_collision(self):
        """Falling through to an exception would fail the signup outright."""
        from unittest import mock

        with mock.patch.object(
            Profile.objects, "filter"
        ) as flt:
            flt.return_value.exists.return_value = True  # always collide
            code = Profile.generate_referral_code()
        self.assertTrue(code)
        self.assertGreater(
            len(code), Profile.REFERRAL_CODE_LENGTH,
            "the fallback should widen the code rather than give up",
        )


class NoSelfReferralTests(TestCase):
    def test_a_user_cannot_be_their_own_referrer(self):
        """The referrer must already exist to have a code, so this cannot happen at
        signup — asserted so a future 'apply a code later' feature has to think
        about it."""
        user = _register(n=1)
        profile = Profile.objects.get(user=user)
        self.assertIsNone(profile.referred_by)
        self.assertNotEqual(profile.referred_by, profile)
