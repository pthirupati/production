"""
Tests for the public certificate-verify endpoint (PRODUCTION_AUDIT PRIV-01).

The endpoint must resolve certificates STRICTLY by the stored, unique
``UserCertificate.certificate_id`` — never by a user id parsed out of the
client-supplied string. A non-matching id must return a flat ``valid: false``
that leaks no holder PII, closing the user/PII enumeration vector.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import TechnologySubscription, UserCertificate
from apps.progress.models import UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()

VERIFY_URL = "/api/achievements/certificate/verify/"


class CertificateVerifyEnumerationTests(APITestCase):
    def setUp(self):
        # A real holder with a genuinely issued certificate.
        self.holder = User.objects.create_user(
            username="alice", email="alice@t.com", password="Pass123!x",
            first_name="Alice", last_name="Holder",
        )
        # A separate victim whose PII must never leak via enumeration. They have
        # completed work + an active sub but NO issued certificate.
        self.victim = User.objects.create_user(
            username="victim", email="victim@t.com", password="Pass123!x",
            first_name="Victor", last_name="Secret",
        )

        self.tech = Technology.objects.create(
            name="Python", slug="python", description="x", price=499, is_active=True,
        )
        self.scenario = Scenario.objects.create(
            title="Fix imports", description="x", technology=self.tech,
            slug="fix-imports", category="Python", difficulty="easy",
            is_free=False, is_active=True,
        )

        # Both users "completed" the only scenario.
        for u in (self.holder, self.victim):
            UserScenarioProgress.objects.create(
                user=u, scenario=self.scenario, completed=True,
                completed_at=timezone.now(), best_score=90,
            )
            TechnologySubscription.objects.create(
                user=u, technology=self.tech, is_active=True,
                expires_at=timezone.now() + timedelta(days=365),
            )

        now = timezone.now()
        # Only the holder gets an actual issued certificate row.
        self.cert = UserCertificate.objects.create(
            user=self.holder, technology=self.tech,
            certificate_id=f"FIXIT-PYTHON-{self.holder.id}-{now.strftime('%Y%m%d')}",
            issued_at=now, expires_at=now + timedelta(days=365),
        )

    # ── Valid, genuinely-issued certificate ──

    def test_valid_certificate_returns_holder_and_stats(self):
        res = self.client.get(VERIFY_URL, {"certificate_id": self.cert.certificate_id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertTrue(body["valid"])
        self.assertEqual(body["certificate_id"], self.cert.certificate_id)
        self.assertEqual(body["holder_name"], "Alice Holder")
        self.assertEqual(body["technology"], "Python")
        self.assertEqual(body["scenarios_completed"], 1)
        self.assertEqual(body["total_scenarios"], 1)

    # ── The core enumeration fix ──

    def test_constructed_id_for_victim_does_not_leak_pii(self):
        """
        An attacker constructs a plausible id embedding the victim's user id.
        No UserCertificate row matches → must be valid:false with NO PII.
        """
        forged = f"FIXIT-PYTHON-{self.victim.id}-20260101"
        res = self.client.get(VERIFY_URL, {"certificate_id": forged})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertFalse(body["valid"])
        # The victim's name / username must not appear anywhere in the response.
        blob = str(body).lower()
        self.assertNotIn("victor", blob)
        self.assertNotIn("secret", blob)
        self.assertNotIn("victim", blob)
        self.assertNotIn("holder_name", body)
        self.assertNotIn("scenarios_completed", body)
        self.assertNotIn("total_score", body)

    def test_enumeration_by_incrementing_user_id_reveals_nothing(self):
        """Sweeping user ids (the original attack) never yields a holder name."""
        for uid in range(1, self.victim.id + 5):
            forged = f"FIXIT-PYTHON-{uid}-20260101"
            res = self.client.get(VERIFY_URL, {"certificate_id": forged})
            body = res.json()
            if forged == self.cert.certificate_id:
                continue  # the one genuinely-issued cert is allowed to resolve
            self.assertFalse(body.get("valid"), f"{forged} should not be valid")
            self.assertNotIn("holder_name", body, f"{forged} leaked a name")

    def test_wrong_date_suffix_for_real_holder_is_not_valid(self):
        """
        Same tech + real holder id but a date that doesn't match the issued
        row → no match → valid:false, no PII. (Proves date isn't just cosmetic.)
        """
        wrong = f"FIXIT-PYTHON-{self.holder.id}-19990101"
        res = self.client.get(VERIFY_URL, {"certificate_id": wrong})
        body = res.json()
        self.assertFalse(body["valid"])
        self.assertNotIn("holder_name", body)

    # ── Format / edge handling ──

    def test_missing_param_is_400(self):
        res = self.client.get(VERIFY_URL)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_fixit_id_is_invalid_without_pii(self):
        res = self.client.get(VERIFY_URL, {"certificate_id": "random-garbage"})
        body = res.json()
        self.assertFalse(body["valid"])
        self.assertNotIn("holder_name", body)

    def test_expired_certificate_reports_expired(self):
        now = timezone.now()
        # Move the holder's cert into the past.
        self.cert.issued_at = now - timedelta(days=400)
        self.cert.expires_at = now - timedelta(days=35)
        self.cert.save()
        res = self.client.get(VERIFY_URL, {"certificate_id": self.cert.certificate_id})
        body = res.json()
        self.assertFalse(body["valid"])
        self.assertTrue(body.get("is_expired"))
        # Expired path legitimately identifies the holder's own cert.
        self.assertEqual(body["holder_name"], "Alice Holder")
