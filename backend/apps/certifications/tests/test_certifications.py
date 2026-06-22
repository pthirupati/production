"""Certification platform tests — seed, API, per-objective progress, exam flow.

Seeds one real RHCSA-mapped scenario per objective (9 total); the remaining
slugs in rhcsa.yaml resolve to nothing and are skipped (the seed's documented
behavior), so the asserted counts reflect exactly what we created.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.certifications.models import (
    CertEarnedCertificate,
    CertificationTrack,
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
        self.assertIn("RHCSA", [t["code"] for t in resp.data["tracks"]])

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
