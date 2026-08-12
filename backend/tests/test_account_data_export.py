"""A subject access request must return everything, and only your own data.

Audit Z4-12: the only export was `/api/interviews/export/transcripts/`, so an access
request could be answered with interview transcripts while the profile, lab history,
billing, community posts, certificates and preferences went unmentioned. GDPR Art.15
and DPDP §11 cover all personal data held, not one convenient subset.

The two tests that matter most here are the negative ones. An export endpoint has
exactly two ways to be dangerous — returning another user's rows, and returning
credentials — and both produce a *larger* file, so neither shows up as a failure in
casual use. They are asserted rather than assumed.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.data_export import FORBIDDEN_KEYS, build_account_export

User = get_user_model()

EXPECTED_SECTIONS = {
    "profile", "preferences", "labs", "command_history",
    "interviews", "certificates", "billing", "community",
}


def _walk(node):
    """Yield every (key, value) pair anywhere in a nested structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)


class ExportCompletenessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="exporter", email="exporter@example.com",
            password="Str0ng-Pass-1", first_name="Ex",
        )

    def test_every_section_is_present(self):
        payload = build_account_export(self.user)
        self.assertTrue(
            EXPECTED_SECTIONS <= set(payload),
            f"missing sections: {EXPECTED_SECTIONS - set(payload)}",
        )

    def test_no_section_silently_errored(self):
        """`_safe` degrades a broken section instead of failing the export, which is
        right — but a green test must not hide that every section errored."""
        payload = build_account_export(self.user)
        broken = [
            name for name in EXPECTED_SECTIONS
            if isinstance(payload.get(name), dict) and "error" in payload[name]
        ]
        self.assertEqual(broken, [], f"sections failed to build: {broken}")

    def test_profile_contains_the_identifying_fields(self):
        payload = build_account_export(self.user)
        self.assertEqual(payload["profile"]["email"], "exporter@example.com")
        self.assertEqual(payload["profile"]["username"], "exporter")

    def test_export_is_json_serialisable(self):
        """It is downloaded as a file; a stray UUID or datetime would 500 the view."""
        json.dumps(build_account_export(self.user), default=str)


class ExportLeaksNothingTests(TestCase):
    """The two dangerous failure modes, both of which make the file bigger."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="mine", email="mine@example.com", password="Str0ng-Pass-1"
        )
        self.other = User.objects.create_user(
            username="theirs", email="theirs@example.com", password="Str0ng-Pass-1"
        )

    def test_no_credential_material_is_exported(self):
        payload = build_account_export(self.user)
        offenders = [
            k for k, _ in _walk(payload)
            if isinstance(k, str) and k.lower() in FORBIDDEN_KEYS
        ]
        self.assertEqual(
            offenders, [],
            f"credential fields present in the export: {offenders} — a download "
            "should not be an account-takeover kit",
        )

    def test_password_hash_never_appears_in_the_payload(self):
        blob = json.dumps(build_account_export(self.user), default=str)
        self.assertNotIn(self.user.password, blob)
        self.assertNotIn("pbkdf2_", blob)

    def test_another_users_email_never_appears(self):
        blob = json.dumps(build_account_export(self.user), default=str)
        self.assertNotIn(
            "theirs@example.com", blob,
            "the export contains another user's data",
        )


class ExportEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ep", email="ep@example.com", password="Str0ng-Pass-1"
        )
        self.client = APIClient()
        self.url = "/api/auth/account/export/"

    def test_requires_authentication(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_authenticated_user_gets_their_export(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["profile"]["email"], "ep@example.com")

    def test_download_returns_a_file_attachment(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {"download": "1"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assertIn("attachment", resp["Content-Disposition"])
        self.assertIn("fixitlab-my-data-", resp["Content-Disposition"])
        json.loads(resp.content)  # must be valid JSON, not a repr

    def test_one_user_cannot_export_anothers_data(self):
        """There is no user parameter by design — the export is always request.user."""
        other = User.objects.create_user(
            username="victim", email="victim@example.com", password="Str0ng-Pass-1"
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url, {"user": other.id, "user_id": other.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["profile"]["email"], "ep@example.com")


class ExportActuallyContainsTheDataTests(TestCase):
    """"No section errored" is satisfied by eight empty lists.

    For a fresh account every section is legitimately empty, so the completeness
    tests above would pass against an export that silently returns nothing. This
    creates real rows and asserts they come back — the difference between "the export
    runs" and "the export exports".
    """

    def setUp(self):
        from apps.interviews.models import InterviewCampaign, InterviewMessage, InterviewRound
        from apps.labs.models import CommandHistory, LabSession
        from apps.question_bank.models import Scenario, Technology

        self.user = User.objects.create_user(
            username="rich", email="rich@example.com", password="Str0ng-Pass-1"
        )
        tech = Technology.objects.create(name="ExpTech", slug="exptech")
        scenario = Scenario.objects.create(
            title="Exp", slug="exp-scenario", technology=tech, description="d"
        )
        self.session = LabSession.objects.create(user=self.user, scenario=scenario)
        CommandHistory.objects.create(session=self.session, command="systemctl status nginx")

        campaign = InterviewCampaign.objects.create(
            user=self.user, title="My campaign", status="in_progress",
            experience_level="mid",
        )
        rnd = InterviewRound.objects.create(
            campaign=campaign, round_number=1, round_type="technical",
            title="r", status="in_progress", duration_minutes=30,
        )
        InterviewMessage.objects.create(
            round=rnd, role="candidate", content="I checked the journal first"
        )
        self.payload = build_account_export(self.user)

    def test_lab_session_appears(self):
        slugs = [row["scenario"] for row in self.payload["labs"]]
        self.assertIn("exp-scenario", slugs)

    def test_command_history_is_counted(self):
        self.assertEqual(self.payload["command_history"]["commands_recorded"], 1)

    def test_interview_transcript_appears(self):
        contents = [
            m["content"]
            for c in self.payload["interviews"]
            for r in c["rounds"]
            for m in r["messages"]
        ]
        self.assertIn("I checked the journal first", contents)

    def test_interview_consent_record_is_included(self):
        """Consent is part of the account's data and evidences our lawful basis."""
        rounds = [r for c in self.payload["interviews"] for r in c["rounds"]]
        self.assertTrue(rounds)
        self.assertIn("consent_granted_at", rounds[0])
        self.assertIn("consent_policy_version", rounds[0])

    def test_preferences_reflect_the_optin_default(self):
        self.assertFalse(self.payload["preferences"]["email_marketing"])
