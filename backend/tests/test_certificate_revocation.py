"""Certificates must be revocable, and revocation must be publicly visible.

Expiry used to be the ONLY way a certificate could become invalid, so there was no
way to withdraw one that should not have been issued. That matters concretely: a
number of certificates were earned against fail-open graders (audit section G), and
the only remedy was a raw DB delete — which would orphan the OneToOne
OpenBadgeCredential while any already-distributed, Ed25519-signed credential JSON
stayed independently verifiable forever.

The signed-badge case is the important one. A signature stays cryptographically
valid permanently — that is the point of signing it — so `verified` must keep
answering "did we really issue this" while a separate `valid` answers "does it
still stand". A consumer reading only `verified` would accept a withdrawn badge.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.certifications.models import (
    CertEarnedCertificate,
    CertificationTrack,
    ExamAttempt,
)
from apps.certifications.views import ExamSubmitView
from apps.question_bank.models import Technology

User = get_user_model()


class CertificateRevocationTests(TestCase):
    def setUp(self):
        self.tech = Technology.objects.create(name="RevokeTech", slug="revoketech")
        self.track = CertificationTrack.objects.create(
            code="RVK", name="Revocable Track", technology=self.tech
        )
        self.user = User.objects.create_user(
            username="holder", email="holder@example.com", password="Str0ng-Pass-1"
        )
        self.cert = CertEarnedCertificate.objects.create(
            user=self.user,
            track=self.track,
            certificate_id="FIXIT-RVK-ABC123",
            holder_name="Holder Name",
            score=82,
            expires_at=timezone.now() + timedelta(days=365),
        )

    # ── model ────────────────────────────────────────────────────────────────
    def test_new_certificate_is_valid(self):
        self.assertTrue(self.cert.is_valid)
        self.assertFalse(self.cert.revoked)

    def test_revoke_sets_state_and_reason(self):
        self.cert.revoke("grader defect")
        self.cert.refresh_from_db()
        self.assertTrue(self.cert.revoked)
        self.assertFalse(self.cert.is_valid)
        self.assertIsNotNone(self.cert.revoked_at)
        self.assertEqual(self.cert.revoked_reason, "grader defect")

    def test_revoke_is_idempotent(self):
        self.cert.revoke("first")
        first_at = CertEarnedCertificate.objects.get(pk=self.cert.pk).revoked_at
        self.cert.revoke("second")
        self.assertEqual(
            CertEarnedCertificate.objects.get(pk=self.cert.pk).revoked_at, first_at,
            "a second revoke overwrote the original timestamp",
        )

    def test_revocation_beats_expiry(self):
        """An unexpired but revoked certificate is invalid."""
        self.cert.revoke("withdrawn")
        self.assertFalse(self.cert.is_expired)
        self.assertFalse(self.cert.is_valid)

    def test_expiry_still_invalidates_without_revocation(self):
        self.cert.expires_at = timezone.now() - timedelta(days=1)
        self.cert.save(update_fields=["expires_at"])
        self.assertTrue(self.cert.is_expired)
        self.assertFalse(self.cert.is_valid)

    def test_long_reason_is_truncated_not_rejected(self):
        self.cert.revoke("x" * 500)
        self.cert.refresh_from_db()
        self.assertEqual(len(self.cert.revoked_reason), 300)


class PublicVerificationTests(TestCase):
    """Verification must say "revoked", not "not found"."""

    def setUp(self):
        self.tech = Technology.objects.create(name="VerifyTech", slug="verifytech")
        self.track = CertificationTrack.objects.create(
            code="VFY", name="Verify Track", technology=self.tech
        )
        self.user = User.objects.create_user(
            username="vholder", email="vholder@example.com", password="Str0ng-Pass-1"
        )
        self.cert = CertEarnedCertificate.objects.create(
            user=self.user, track=self.track,
            certificate_id="FIXIT-VFY-XYZ789",
            holder_name="Verify Holder", score=75,
            expires_at=timezone.now() + timedelta(days=365),
        )
        self.url = "/api/certifications/certificate/verify/"

    def test_valid_certificate_verifies(self):
        r = self.client.get(self.url, {"id": self.cert.certificate_id})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["valid"])

    def test_revoked_certificate_reports_revoked_not_missing(self):
        """"Not found" is indistinguishable from a typo and reads as a bug."""
        self.cert.revoke("issued against a defective grader")
        r = self.client.get(self.url, {"id": self.cert.certificate_id})
        self.assertEqual(r.status_code, 200, "revoked cert should not 404")
        self.assertFalse(r.data["valid"])
        self.assertTrue(r.data.get("revoked"))
        self.assertIn("revoked", r.data.get("error", "").lower())

    def test_revocation_reason_is_public(self):
        """An employer checking the credential deserves to know why."""
        self.cert.revoke("grader defect; re-take the exam")
        r = self.client.get(self.url, {"id": self.cert.certificate_id})
        self.assertIn("grader defect", r.data["certificate"]["revoked_reason"])

    def test_unknown_id_still_404s(self):
        r = self.client.get(self.url, {"id": "FIXIT-NOPE-000000"})
        self.assertEqual(r.status_code, 404)


class SharedVerifyPageTests(TestCase):
    """The endpoint the user-facing verify page actually calls must honour revocation.

    /api/achievements/certificate/verify/ (apps.public_api) is what
    frontend/src/pages/CertificateVerify.jsx fetches — it is the page an employer
    lands on from a shared link. The apps.certifications verify endpoint covered by
    PublicVerificationTests is wired to a different surface, so honouring revocation
    there is not enough: this one resolved track certificates by expiry alone and
    kept vouching for withdrawn credentials.
    """

    def setUp(self):
        self.tech = Technology.objects.create(name="ShareTech", slug="sharetech")
        self.track = CertificationTrack.objects.create(
            code="SHR", name="Share Track", technology=self.tech
        )
        self.user = User.objects.create_user(
            username="sholder", email="sholder@example.com", password="Str0ng-Pass-1"
        )
        self.cert = CertEarnedCertificate.objects.create(
            user=self.user,
            track=self.track,
            certificate_id="FIXIT-SHR-QRS456",
            holder_name="Share Holder",
            score=88,
            expires_at=timezone.now() + timedelta(days=365),
        )
        self.url = "/api/achievements/certificate/verify/"

    def _verify(self):
        return self.client.get(self.url, {"certificate_id": self.cert.certificate_id})

    def test_valid_track_certificate_verifies(self):
        r = self._verify()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["valid"])
        self.assertEqual(r.data["holder_name"], "Share Holder")

    def test_revoked_track_certificate_is_not_valid(self):
        self.cert.revoke("issued against a defective grader")
        r = self._verify()
        self.assertEqual(r.status_code, 200, "revoked cert should not 404")
        self.assertFalse(
            r.data["valid"],
            "the shared verify page still vouches for a revoked certificate",
        )

    def test_revoked_track_certificate_says_why(self):
        """Reported as revoked, not as missing — "not found" reads as a typo."""
        self.cert.revoke("grader defect; re-take the exam")
        r = self._verify()
        self.assertTrue(r.data.get("revoked"))
        self.assertIn("revoked", r.data.get("error", "").lower())
        self.assertIn("grader defect", r.data.get("revoked_reason", ""))

    def test_expired_track_certificate_is_still_invalid(self):
        """Folding revocation in must not drop the pre-existing expiry check."""
        self.cert.expires_at = timezone.now() - timedelta(days=1)
        self.cert.save(update_fields=["expires_at"])
        r = self._verify()
        self.assertFalse(r.data["valid"])
        self.assertFalse(r.data.get("revoked", False))


class ReissueAfterRevocationTests(TestCase):
    """Re-passing the exam must actually clear a revocation.

    The grader-defect revocation reason literally tells the holder to "re-take the
    exam to earn it again", and there is exactly one certificate row per
    (user, track) — so a re-pass updates that same row in place. If the update
    refreshes issued_at/expires_at but leaves ``revoked`` set, the holder follows
    the instructions, passes, sees a freshly-dated certificate, and it still
    verifies as invalid forever with no self-serve way out.
    """

    def setUp(self):
        self.tech = Technology.objects.create(name="ReissueTech", slug="reissuetech")
        self.track = CertificationTrack.objects.create(
            code="RIS", name="Reissue Track", technology=self.tech
        )
        self.user = User.objects.create_user(
            username="reholder", email="reholder@example.com", password="Str0ng-Pass-1"
        )
        self.cert = CertEarnedCertificate.objects.create(
            user=self.user,
            track=self.track,
            certificate_id="FIXIT-RIS-ABC123",
            holder_name="Re Holder",
            score=80,
            expires_at=timezone.now() + timedelta(days=365),
        )

    def _attempt(self, score):
        return ExamAttempt.objects.create(
            user=self.user,
            track=self.track,
            status="passed",
            score=score,
            expires_at=timezone.now() + timedelta(hours=2),
        )

    def test_repassing_clears_revocation(self):
        self.cert.revoke("Issued against a defective grader; re-take the exam.")
        attempt = self._attempt(91)

        ExamSubmitView._issue_certificate(self.user, attempt, 91)

        self.cert.refresh_from_db()
        self.assertFalse(
            self.cert.revoked,
            "re-passing left the certificate revoked — the holder followed the "
            "revocation instructions and still has an invalid certificate",
        )
        self.assertIsNone(self.cert.revoked_at)
        self.assertEqual(self.cert.revoked_reason, "")
        self.assertTrue(self.cert.is_valid)

    def test_lower_repass_score_does_not_clear_revocation(self):
        """The in-place update only applies at >= the stored score.

        A revoked cert must not be silently reinstated by a weaker attempt that
        does not even refresh the certificate's other fields.
        """
        self.cert.revoke("grader defect")
        attempt = self._attempt(50)

        ExamSubmitView._issue_certificate(self.user, attempt, 50)

        self.cert.refresh_from_db()
        self.assertTrue(self.cert.revoked)
        self.assertEqual(self.cert.score, 80, "a worse attempt overwrote the score")

    def test_unrevoked_repass_is_unaffected(self):
        attempt = self._attempt(95)

        ExamSubmitView._issue_certificate(self.user, attempt, 95)

        self.cert.refresh_from_db()
        self.assertFalse(self.cert.revoked)
        self.assertEqual(self.cert.score, 95)
