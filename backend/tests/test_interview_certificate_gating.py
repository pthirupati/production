"""Interview certificates are a paid-tier feature and must be enforced server-side.

InterviewPlanTier.certificate_enabled is seeded False on Free and True on
Pro/Premium, exposed in the entitlement payload, and shown in the pricing UI — but
nothing checked it. _finalize_campaign called issue_certificate() unconditionally,
so a Free-tier user received the artefact that Premium is partly sold on. Grepping
certificate_enabled found only serializers, admin, seeds and the payload; there was
no enforcement site.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.interviews.models import InterviewCampaign, InterviewCertificate
from apps.interviews.services.certificate import issue_certificate

User = get_user_model()


class CertificateGatingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="candidate", email="cand@example.com", password="Str0ng-Pass-1"
        )
        self.campaign = InterviewCampaign.objects.create(
            user=self.user,
            experience_level="mid",
            round_count=3,
            overall_score=78,
            status="completed",
        )

    def _payload(self, enabled, code="free"):
        return {"plan": {"code": code, "certificate_enabled": enabled}}

    def test_free_tier_gets_no_certificate(self):
        with patch(
            "apps.interviews.services.entitlements.get_entitlement_payload",
            return_value=self._payload(False, "free"),
        ):
            self.assertIsNone(issue_certificate(self.campaign))
        self.assertFalse(
            InterviewCertificate.objects.filter(campaign=self.campaign).exists(),
            "free tier received the paid certificate",
        )

    def test_paid_tier_gets_a_certificate(self):
        with patch(
            "apps.interviews.services.entitlements.get_entitlement_payload",
            return_value=self._payload(True, "premium"),
        ):
            cert = issue_certificate(self.campaign)
        self.assertIsNotNone(cert, "paid tier was denied its certificate")
        self.assertTrue(cert.certificate_id)

    def test_entitlement_lookup_failure_withholds(self):
        """Fails closed: withholding is recoverable, over-issuing is not."""
        with patch(
            "apps.interviews.services.entitlements.get_entitlement_payload",
            side_effect=RuntimeError("db down"),
        ):
            self.assertIsNone(issue_certificate(self.campaign))

    def test_missing_plan_key_withholds(self):
        with patch(
            "apps.interviews.services.entitlements.get_entitlement_payload",
            return_value={},
        ):
            self.assertIsNone(issue_certificate(self.campaign))

    def test_existing_certificate_is_returned_without_re_gating(self):
        """Idempotency must survive the new gate — a already-issued cert stands."""
        with patch(
            "apps.interviews.services.entitlements.get_entitlement_payload",
            return_value=self._payload(True, "premium"),
        ):
            first = issue_certificate(self.campaign)
        self.campaign.refresh_from_db()
        # Even on the free tier, an already-earned certificate is not withdrawn here.
        with patch(
            "apps.interviews.services.entitlements.get_entitlement_payload",
            return_value=self._payload(False, "free"),
        ):
            second = issue_certificate(self.campaign)
        self.assertEqual(first.pk, second.pk)
