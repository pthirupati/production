"""Certification platform tests — seed, API, per-objective progress, exam flow.

Seeds one real RHCSA-mapped scenario per objective (9 total); the remaining
slugs in rhcsa.yaml resolve to nothing and are skipped (the seed's documented
behavior), so the asserted counts reflect exactly what we created.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.certifications import openbadge
from apps.certifications.models import (
    CertEarnedCertificate,
    CertificationTrack,
    OpenBadgeCredential,
    TrackScenario,
)
from apps.progress.models import UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()

# One real slug per RHCSA objective so a fully-completed exam scores 100%.
SEEDED_SLUGS = {
    "linux-ssh-key-auth-fail": "rhcsa.tools",
    "systemd-unit-wont-start": "rhcsa.operate",
    "linux-lvm-create-mount": "rhcsa.storage",
    "linux-fstab-recovery": "rhcsa.filesystems",
    "linux-cron-not-running": "rhcsa.deploy",
    "linux-default-gateway-missing": "rhcsa.networking",
    "broken-useradd": "rhcsa.users",
    "rhel-selinux-booleans": "rhcsa.selinux",
    "sim-docker-container-exited": "rhcsa.containers",
}


class CertificationsTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="Linux Administration", slug="linux")
        cls.scenarios = {}
        for slug in SEEDED_SLUGS:
            cls.scenarios[slug] = Scenario.objects.create(
                technology=cls.tech,
                slug=slug,
                title=slug.replace("-", " ").title(),
                category="rhcsa",
                difficulty="medium",
                description="Test scenario.",
            )
        call_command("seed_certifications")

    def setUp(self):
        self.user = User.objects.create_user(
            username="learner", email="learner@example.com", password="pw-Str0ng!23"
        )
        self.client = APIClient()

    def _complete_all_exam_scenarios(self, exam, when=None):
        when = when or timezone.now()
        for s in exam["scenarios"]:
            UserScenarioProgress.objects.update_or_create(
                user=self.user,
                scenario_id=s["scenario_id"],
                defaults={"completed": True, "best_score": 100, "completed_at": when},
            )

    # ---- seed ----
    def test_seed_creates_track_and_links(self):
        track = CertificationTrack.objects.get(slug="rhcsa")
        self.assertEqual(track.code, "RHCSA")
        self.assertEqual(track.objectives.count(), 9)
        self.assertEqual(
            TrackScenario.objects.filter(objective__track=track).count(),
            len(SEEDED_SLUGS),
        )

    def test_seed_is_idempotent(self):
        before = TrackScenario.objects.count()
        call_command("seed_certifications")
        self.assertEqual(TrackScenario.objects.count(), before)

    # ---- public API ----
    def test_track_list(self):
        resp = self.client.get("/api/certifications/")
        self.assertEqual(resp.status_code, 200)
        codes = {t["code"] for t in resp.data["tracks"]}
        # All seven seeded tracks should be active and listed.
        self.assertEqual(
            codes,
            {"RHCSA", "RHCE", "CKA", "CKAD", "CKS", "LFCS", "TF-ASSOCIATE"},
        )

    def test_track_detail_anonymous_zero_progress(self):
        resp = self.client.get("/api/certifications/rhcsa/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["overall_percent"], 0)
        self.assertEqual(len(resp.data["objectives"]), 9)

    def test_track_detail_reflects_completion(self):
        UserScenarioProgress.objects.create(
            user=self.user, scenario=self.scenarios["broken-useradd"],
            completed=True, best_score=100,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/certifications/rhcsa/")
        users_obj = next(o for o in resp.data["objectives"] if o["code"] == "rhcsa.users")
        self.assertEqual(users_obj["completed_scenarios"], 1)
        self.assertGreater(resp.data["overall_percent"], 0)

    def test_track_detail_404(self):
        self.assertEqual(self.client.get("/api/certifications/nope/").status_code, 404)

    # ---- exam flow ----
    def test_exam_start_requires_auth(self):
        resp = self.client.post("/api/certifications/rhcsa/exam/start/")
        self.assertIn(resp.status_code, (401, 403))

    def test_full_exam_pass_issues_certificate(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        self.assertEqual(start.status_code, 201)
        self.assertTrue(start.data["scenarios"])
        self._complete_all_exam_scenarios(start.data)

        submit = self.client.post(f"/api/certifications/exam/{start.data['id']}/submit/")
        self.assertEqual(submit.status_code, 200)
        self.assertTrue(submit.data["passed"])
        self.assertEqual(submit.data["score"], 100)
        cert = submit.data["certificate"]
        self.assertIsNotNone(cert)
        # certificate_id must carry a random token, not be date/userid-derived.
        self.assertTrue(cert["certificate_id"].startswith("FIXIT-RHCSA-"))
        self.assertEqual(len(cert["certificate_id"].split("-")[-1]), 12)

        verify = self.client.get(
            "/api/certifications/certificate/verify/", {"id": cert["certificate_id"]}
        )
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.data["valid"])

    def test_exam_fail_no_certificate(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        submit = self.client.post(f"/api/certifications/exam/{start.data['id']}/submit/")
        self.assertEqual(submit.status_code, 200)
        self.assertFalse(submit.data["passed"])
        self.assertEqual(submit.data["status"], "failed")
        self.assertIsNone(submit.data["certificate"])

    def test_exam_proctoring_signals_are_report_only(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        self.assertEqual(start.status_code, 201)
        aid = start.data["id"]
        self.assertEqual(start.data["proctoring"]["tab_switches"], 0)

        r1 = self.client.post(
            f"/api/certifications/exam/{aid}/proctoring/",
            {"event": "tab_switch"},
            format="json",
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data["proctoring"]["tab_switches"], 1)

        r2 = self.client.post(
            f"/api/certifications/exam/{aid}/proctoring/",
            {"event": "paste", "source": "page"},
            format="json",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.data["proctoring"]["paste_events"], 1)

        submit = self.client.post(f"/api/certifications/exam/{aid}/submit/")
        self.assertEqual(submit.status_code, 200)
        self.assertEqual(submit.data["proctoring"]["tab_switches"], 1)
        self.assertEqual(submit.data["proctoring"]["paste_events"], 1)
        # Signals never block grading.
        self.assertIn(submit.data["status"], ("failed", "passed", "expired"))

    def test_exam_ignores_pre_exam_completions(self):
        """Integrity: labs completed BEFORE the exam window must not count."""
        # Complete every mapped scenario a day before the exam starts.
        yesterday = timezone.now() - timezone.timedelta(days=1)
        for sc in self.scenarios.values():
            UserScenarioProgress.objects.create(
                user=self.user, scenario=sc, completed=True, best_score=100,
                completed_at=yesterday,
            )
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        submit = self.client.post(f"/api/certifications/exam/{start.data['id']}/submit/")
        self.assertEqual(submit.data["score"], 0)
        self.assertFalse(submit.data["passed"])

    def test_certificate_unique_per_user_track(self):
        """Re-passing updates the single cert row rather than duplicating it."""
        self.client.force_authenticate(user=self.user)
        for _ in range(2):
            start = self.client.post("/api/certifications/rhcsa/exam/start/")
            self._complete_all_exam_scenarios(start.data)
            self.client.post(f"/api/certifications/exam/{start.data['id']}/submit/")
        self.assertEqual(
            CertEarnedCertificate.objects.filter(user=self.user, track__slug="rhcsa").count(),
            1,
        )

    def test_certificate_holder_is_not_email(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        self._complete_all_exam_scenarios(start.data)
        submit = self.client.post(f"/api/certifications/exam/{start.data['id']}/submit/")
        holder = submit.data["certificate"]["holder_name"]
        self.assertNotIn("@", holder)  # never leak the user's email

    # ---- Open Badge 3.0 verifiable credential ----
    def _earn_cert(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        self._complete_all_exam_scenarios(start.data)
        self.client.post(f"/api/certifications/exam/{start.data['id']}/submit/")
        return CertEarnedCertificate.objects.get(user=self.user, track__slug="rhcsa")

    def test_earning_cert_mints_open_badge(self):
        cert = self._earn_cert()
        ob = OpenBadgeCredential.objects.get(certificate=cert)
        # Spec-shaped OB 3.0 / VC credential.
        self.assertEqual(
            ob.credential["type"], ["VerifiableCredential", "OpenBadgeCredential"]
        )
        self.assertIn("https://www.w3.org/ns/credentials/v2", ob.credential["@context"])
        ach = ob.credential["credentialSubject"]["achievement"]
        self.assertIn("RHCSA", ach["name"])
        self.assertTrue(ach.get("skills"))          # skills from the cert track objectives
        self.assertTrue(ach["criteria"]["narrative"])
        self.assertTrue(ob.credential["evidence"])  # references the exam/score
        # Recipient email is only ever stored hashed, never in the clear.
        blob = str(ob.credential)
        self.assertNotIn(self.user.email, blob)
        self.assertTrue(ob.recipient_hash.startswith("sha256$"))
        self.assertNotIn("privateKey", blob)

    def test_verify_endpoint_reports_verified_true(self):
        cert = self._earn_cert()
        ob = OpenBadgeCredential.objects.get(certificate=cert)
        self.client.logout()  # public endpoint — no auth
        resp = self.client.get(f"/api/certifications/verify/{ob.credential_uuid}/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["verified"])
        self.assertEqual(resp.data["achievement"]["track_code"], "RHCSA")
        self.assertEqual(resp.data["achievement"]["score"], 100)

    def test_tampered_credential_verifies_false(self):
        cert = self._earn_cert()
        ob = OpenBadgeCredential.objects.get(certificate=cert)
        # Tamper with the signed body after issuance.
        ob.credential["credentialSubject"]["achievement"]["name"] = "Forged Master Cert"
        ob.save(update_fields=["credential"])
        self.client.logout()
        resp = self.client.get(f"/api/certifications/verify/{ob.credential_uuid}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["verified"])
        # Direct verifier check too.
        self.assertFalse(openbadge.verify(ob.credential, ob.public_key_b64))

    def test_verify_unknown_credential_404(self):
        resp = self.client.get(
            "/api/certifications/verify/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(resp.data["verified"])

    def test_raw_credential_json_endpoint(self):
        cert = self._earn_cert()
        ob = OpenBadgeCredential.objects.get(certificate=cert)
        self.client.logout()
        resp = self.client.get(
            f"/api/certifications/verify/{ob.credential_uuid}/credential.json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], ob.credential["id"])
        self.assertIn("proof", resp.data)
        # The signed JSON is independently verifiable offline.
        self.assertTrue(openbadge.verify(resp.data, ob.public_key_b64))

    def test_issuer_is_deterministic_with_fixed_key(self):
        """Same persisted/fixed key => credential re-verifies; offline (no network)."""
        cert = self._earn_cert()
        ob = OpenBadgeCredential.objects.get(certificate=cert)
        # Re-verify against a freshly loaded signing key's public half.
        priv = openbadge._signing_key()
        pub = openbadge.public_key_b64_for(priv)
        self.assertEqual(pub, ob.public_key_b64)
        self.assertTrue(openbadge.verify(ob.credential, ob.public_key_b64))
