"""Phase 2+ feature tests: blog, interview hints, learning path, billing unified."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.adminpanel.models import BlogPost
from apps.billing.models import TechnologySubscription
from apps.hints.models import Hint
from apps.labs.models import LabSession
from apps.progress.models import LearningPathProgress, UserScenarioProgress
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class Phase2BlogTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        BlogPost.objects.create(
            slug="test-post",
            title="Test Post",
            excerpt="Excerpt",
            content="Body content",
            is_published=True,
            published_at=timezone.now(),
        )

    def test_public_blog_list(self):
        res = self.client.get("/api/blog/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(p["slug"] == "test-post" for p in res.data))

    def test_public_blog_detail(self):
        res = self.client.get("/api/blog/test-post/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["title"], "Test Post")


class Phase2InterviewHintsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="labuser", email="lab@test.com", password="pass12345!")
        self.tech = Technology.objects.create(name="Linux", slug="linux", is_active=True)
        self.scenario = Scenario.objects.create(
            title="Interview scenario",
            slug="interview-nginx",
            technology=self.tech,
            is_active=True,
            interview_mode=True,
            validation_script="exit 0",
        )
        Hint.objects.create(scenario=self.scenario, order=1, content="Real hint spoiler", penalty=10)
        self.session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="RUNNING",
            provider="simulation",
            container_id="sim-test",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_standard_hints_blocked_in_interview_mode(self):
        res = self.client.post(f"/api/labs/{self.session.id}/hints/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], "INTERVIEW_MODE")

    def test_ai_hint_available_in_interview_mode(self):
        res = self.client.post(f"/api/labs/{self.session.id}/ai-hint/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["hint"]["ai_generated"])
        self.session.refresh_from_db()
        self.assertEqual(self.session.hints_used, 1)


class Phase2LearningPathTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", email="learn@test.com", password="pass12345!")
        self.tech = Technology.objects.create(
            name="Docker",
            slug="docker",
            is_active=True,
            learning_path=[
                {"title": "Step 1", "scenario_slug": "docker-basics"},
                {"title": "Step 2", "scenario_slug": "docker-network"},
            ],
        )
        self.scenario = Scenario.objects.create(
            title="Docker basics",
            slug="docker-basics",
            technology=self.tech,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_learning_path_progress_on_technology_detail(self):
        UserScenarioProgress.objects.create(
            user=self.user, scenario=self.scenario, completed=True, attempts=1,
        )
        res = self.client.get("/api/technologies/docker/")
        self.assertEqual(res.status_code, 200)
        progress = res.data["technology"]["learning_path_progress"]
        self.assertEqual(progress["steps_completed"], 1)
        self.assertIn("docker-basics", progress["completed_slugs"])


class Phase2UnifiedBillingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer", email="buyer@test.com", password="pass12345!")
        self.tech = Technology.objects.create(name="K8s", slug="k8s", is_active=True, price=999)
        TechnologySubscription.objects.create(
            user=self.user,
            technology=self.tech,
            subscription_id="TECH-K8S-TEST",
            amount=999,
            is_active=True,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_unified_billing_payload(self):
        res = self.client.get("/api/billing/unified/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("technology_subscriptions", res.data)
        self.assertIn("gateways", res.data)
        self.assertEqual(len(res.data["technology_subscriptions"]), 1)
