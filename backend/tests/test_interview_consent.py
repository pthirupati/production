"""Camera/mic/transcript consent must be provable, not just enforced in the UI.

Audit Z4-5: `InterviewRoom.jsx` has always required an explicit consent checkbox
before the start button enables — but there were **zero** `consent` references in
`backend/apps/interviews/`. Nothing recorded that consent was given, so the platform
processed biometric-adjacent data (camera, microphone, transcribed speech) with no
evidence of a lawful basis. Under DPDP/GDPR the burden of proof is the controller's,
and "the button was disabled without it" is not evidence — it is a client-side
control the server never saw.

Storing the *version* matters as much as the timestamp: consent is given to a
specific text, so a later rewrite of the consent wording must not silently
re-interpret what an earlier candidate agreed to.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.interviews.models import (
    InterviewCampaign,
    InterviewEntitlement,
    InterviewRound,
)
from apps.interviews.views import CONSENT_POLICY_VERSION

User = get_user_model()


class InterviewConsentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="consent1", email="consent1@example.com", password="Str0ng-Pass-1"
        )
        ent, _ = InterviewEntitlement.objects.get_or_create(user=self.user)
        ent.free_rounds_remaining = 5
        ent.save()
        self.campaign = InterviewCampaign.objects.create(
            user=self.user, title="t", status="in_progress", experience_level="mid"
        )
        self.round = InterviewRound.objects.create(
            campaign=self.campaign, round_number=1, round_type="technical",
            title="r", status="scheduled", duration_minutes=30,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = f"/api/interviews/rounds/{self.round.id}/start/"

    # ── the gap ──────────────────────────────────────────────────────────────
    def test_a_fresh_round_has_no_consent_recorded(self):
        self.assertIsNone(self.round.consent_granted_at)
        self.assertEqual(self.round.consent_policy_version, "")

    def test_starting_a_round_records_consent(self):
        self.client.post(self.url, {}, format="json")
        self.round.refresh_from_db()
        self.assertIsNotNone(
            self.round.consent_granted_at,
            "the interview started without recording that consent was given",
        )

    def test_recorded_consent_carries_a_policy_version(self):
        self.client.post(self.url, {}, format="json")
        self.round.refresh_from_db()
        self.assertEqual(self.round.consent_policy_version, CONSENT_POLICY_VERSION)

    def test_client_supplied_version_is_stored(self):
        """The client knows which wording it actually rendered."""
        self.client.post(
            self.url, {"consent_policy_version": "2026-09-01"}, format="json"
        )
        self.round.refresh_from_db()
        self.assertEqual(self.round.consent_policy_version, "2026-09-01")

    def test_absurd_client_version_cannot_overflow_the_column(self):
        self.client.post(
            self.url, {"consent_policy_version": "x" * 500}, format="json"
        )
        self.round.refresh_from_db()
        self.assertLessEqual(len(self.round.consent_policy_version), 32)

    # ── the timestamp must stay defensible ───────────────────────────────────
    def test_reconnecting_does_not_overwrite_the_original_timestamp(self):
        """A dropped connection mid-interview re-hits start. The consent record must
        keep pointing at when consent was actually given."""
        self.client.post(self.url, {}, format="json")
        self.round.refresh_from_db()
        first = self.round.consent_granted_at
        self.assertIsNotNone(first)

        self.client.post(self.url, {}, format="json")
        self.round.refresh_from_db()
        self.assertEqual(
            self.round.consent_granted_at, first,
            "a reconnect rewrote the consent timestamp — the record is no longer "
            "evidence of when consent was given",
        )

    def test_prior_consent_survives_a_later_version_bump(self):
        """A policy rewrite must not retroactively change what someone agreed to."""
        self.round.consent_granted_at = timezone.now()
        self.round.consent_policy_version = "2020-01-01"
        self.round.save(update_fields=["consent_granted_at", "consent_policy_version"])

        self.client.post(
            self.url, {"consent_policy_version": "2099-01-01"}, format="json"
        )
        self.round.refresh_from_db()
        self.assertEqual(self.round.consent_policy_version, "2020-01-01")

    def test_consent_is_scoped_to_the_round_that_recorded_it(self):
        other = InterviewRound.objects.create(
            campaign=self.campaign, round_number=2, round_type="technical",
            title="r2", status="scheduled", duration_minutes=30,
        )
        self.client.post(self.url, {}, format="json")
        other.refresh_from_db()
        self.assertIsNone(
            other.consent_granted_at,
            "starting one round recorded consent against another",
        )
