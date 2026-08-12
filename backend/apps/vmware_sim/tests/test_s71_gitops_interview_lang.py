"""Session 71: GitOps digest drift, InterviewRound.language."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.interviews.models import InterviewCampaign, InterviewRound
from apps.question_bank.models import Technology
from apps.vmware_sim.cicd_v2_facades import apply_v2_action, seed_v2

User = get_user_model()


class GitopsDigestTests(TestCase):
    def test_write_digest_drift_and_sync(self):
        st = seed_v2()
        # Force synced baseline
        app = next(a for a in st["argo_apps"] if a["name"] == "api-server")
        self.assertEqual(app["sync_status"], "Synced")

        wrote = apply_v2_action(st, "gitops_write_digest", {
            "name": "api-server",
            "digest": "sha256:new-build-99",
        })
        self.assertTrue(wrote.get("ok"), wrote)
        self.assertTrue(wrote.get("out_of_sync"))
        app = next(a for a in st["argo_apps"] if a["name"] == "api-server")
        self.assertEqual(app["desired_digest"], "sha256:new-build-99")
        self.assertEqual(app["sync_status"], "OutOfSync")

        drift = apply_v2_action(st, "detect_drift", {"name": "api-server"})
        self.assertTrue(drift.get("drift"))
        self.assertEqual(len(drift["drifted"]), 1)

        synced = apply_v2_action(st, "argo_sync", {"name": "api-server"})
        self.assertTrue(synced.get("ok"))
        app = next(a for a in st["argo_apps"] if a["name"] == "api-server")
        self.assertEqual(app["live_digest"], "sha256:new-build-99")
        self.assertEqual(app["sync_status"], "Synced")

        clean = apply_v2_action(st, "detect_drift", {"name": "api-server"})
        self.assertFalse(clean.get("drift"))


class InterviewLanguageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="ilang", email="ilang@test.com", password="Pass123!",
        )
        self.client.force_authenticate(user=self.user)
        tech = Technology.objects.create(
            name="Linux", slug="linux-ilang", description="x", price=0, is_active=True,
        )
        self.campaign = InterviewCampaign.objects.create(
            user=self.user, title="Lang camp", primary_technology=tech, status="ready",
        )
        self.round = InterviewRound.objects.create(
            campaign=self.campaign,
            round_number=1,
            round_type="technical",
            title="R1",
            status="ready",
            duration_minutes=30,
        )

    def test_default_en_and_patch(self):
        self.assertEqual(self.round.language, "en")
        bad = self.client.patch(
            f"/api/interviews/rounds/{self.round.id}/",
            {"language": "fr"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

        ok = self.client.patch(
            f"/api/interviews/rounds/{self.round.id}/",
            {"language": "hi"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()["language"], "hi")
        self.round.refresh_from_db()
        self.assertEqual(self.round.language, "hi")

        get = self.client.get(f"/api/interviews/rounds/{self.round.id}/")
        self.assertEqual(get.json().get("language"), "hi")
