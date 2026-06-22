"""Certification platform tests — seed, API, per-objective progress, exam flow.

Seeds only a handful of the RHCSA-mapped scenarios; the rest of the slugs in
rhcsa.yaml resolve to nothing and are skipped (which is the seed's documented
behavior), so the asserted counts reflect exactly what we created.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient, APITestCase

from apps.certifications.models import (
    CertEarnedCertificate,
    CertificationTrack,
    TrackScenario,
)
from apps.progress.models import UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()

# Slugs that appear in rhcsa.yaml, spanning several objectives.
SEEDED_SLUGS = {
    "linux-ssh-key-auth-fail": "rhcsa.tools",
    "linux-lvm-create-mount": "rhcsa.storage",
    "broken-useradd": "rhcsa.users",
    "rhel-selinux-booleans": "rhcsa.selinux",
    "sim-docker-container-exited": "rhcsa.containers",
    "build-docker-image-do": "rhcsa.containers",
}


class CertificationsTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="Linux Administration", slug="linux")
        cls.scenarios = {}
        for i, slug in enumerate(SEEDED_SLUGS):
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

    # ---- seed ----
    def test_seed_creates_track_and_links(self):
        track = CertificationTrack.objects.get(slug="rhcsa")
        self.assertEqual(track.code, "RHCSA")
        self.assertEqual(track.objectives.count(), 9)
        # Every scenario we created should be linked exactly once.
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
        codes = [t["code"] for t in resp.data["tracks"]]
        self.assertIn("RHCSA", codes)

    def test_track_detail_anonymous_zero_progress(self):
        resp = self.client.get("/api/certifications/rhcsa/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["overall_percent"], 0)
        self.assertEqual(len(resp.data["objectives"]), 9)

    def test_track_detail_reflects_completion(self):
        UserScenarioProgress.objects.create(
            user=self.user,
            scenario=self.scenarios["broken-useradd"],
            completed=True,
            best_score=100,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.get("/api/certifications/rhcsa/")
        self.assertEqual(resp.status_code, 200)
        users_obj = next(o for o in resp.data["objectives"] if o["code"] == "rhcsa.users")
        self.assertEqual(users_obj["completed_scenarios"], 1)
        self.assertGreater(users_obj["percent"], 0)
        self.assertGreater(resp.data["overall_percent"], 0)

    def test_track_detail_404(self):
        resp = self.client.get("/api/certifications/nope/")
        self.assertEqual(resp.status_code, 404)

    # ---- exam flow ----
    def test_exam_start_requires_auth(self):
        resp = self.client.post("/api/certifications/rhcsa/exam/start/")
        self.assertIn(resp.status_code, (401, 403))

    def test_full_exam_pass_issues_certificate(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        self.assertEqual(start.status_code, 201)
        attempt_id = start.data["id"]
        exam_scenarios = start.data["scenarios"]
        self.assertTrue(exam_scenarios)

        # Complete every scenario in the attempt → 100% on represented objectives.
        for s in exam_scenarios:
            UserScenarioProgress.objects.update_or_create(
                user=self.user,
                scenario_id=s["scenario_id"],
                defaults={"completed": True, "best_score": 100},
            )

        submit = self.client.post(f"/api/certifications/exam/{attempt_id}/submit/")
        self.assertEqual(submit.status_code, 200)
        self.assertTrue(submit.data["passed"])
        self.assertEqual(submit.data["status"], "passed")
        cert = submit.data["certificate"]
        self.assertIsNotNone(cert)

        # Public verification of the issued certificate.
        verify = self.client.get(
            "/api/certifications/certificate/verify/", {"id": cert["certificate_id"]}
        )
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(verify.data["valid"])
        self.assertEqual(CertEarnedCertificate.objects.filter(user=self.user).count(), 1)

    def test_exam_fail_no_certificate(self):
        self.client.force_authenticate(user=self.user)
        start = self.client.post("/api/certifications/rhcsa/exam/start/")
        attempt_id = start.data["id"]
        # Solve nothing → score 0 → fail, no cert.
        submit = self.client.post(f"/api/certifications/exam/{attempt_id}/submit/")
        self.assertEqual(submit.status_code, 200)
        self.assertFalse(submit.data["passed"])
        self.assertEqual(submit.data["status"], "failed")
        self.assertIsNone(submit.data["certificate"])
