from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.oauth_state import issue_oauth_state, validate_oauth_state
from apps.labs.models import LabSession
from apps.hints.models import Hint, Scenario, Technology

User = get_user_model()


class OAuthStateTests(TestCase):
    def test_issue_and_validate_state(self):
        state = issue_oauth_state("login")
        ok, intent = validate_oauth_state(state)
        self.assertTrue(ok)
        self.assertEqual(intent, "login")

    def test_reject_replay(self):
        state = issue_oauth_state("register")
        self.assertTrue(validate_oauth_state(state)[0])
        self.assertFalse(validate_oauth_state(state)[0])


class SessionTrackerTombstoneTests(TestCase):
    def test_invalidate_all_sets_tombstone(self):
        from common.security import SessionTracker

        SessionTracker.record_session(42, "jti-abc", "127.0.0.1", "test")
        self.assertTrue(SessionTracker.is_session_valid(42, "jti-abc"))
        SessionTracker.invalidate_all_sessions(42)
        self.assertFalse(SessionTracker.is_session_valid(42, "jti-abc"))
        self.assertFalse(SessionTracker.is_session_valid(42, "jti-new"))


@override_settings(DEBUG=True)
class SolutionGatingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="learner", email="l@example.com", password="pass12345!!")
        self.tech = Technology.objects.create(name="Linux", slug="linux", is_active=True)
        self.scenario = Scenario.objects.create(
            slug="gate-test",
            title="Gate",
            technology=self.tech,
            solution_explanation="The answer is 42",
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_terminated_stop_does_not_leak_solution(self):
        session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="TERMINATED",
        )
        resp = self.client.get(f"/api/labs/{session.id}/solution/")
        self.assertEqual(resp.status_code, 403)

    def test_completed_session_shows_solution(self):
        session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="COMPLETED",
            validation_passed=True,
        )
        resp = self.client.get(f"/api/labs/{session.id}/solution/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("42", resp.json()["solution_explanation"])

    def test_terminated_with_hints_exhausted_shows_solution(self):
        Hint.objects.create(scenario=self.scenario, order=1, content="hint1", penalty=10)
        session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="TERMINATED",
            hints_used=1,
        )
        resp = self.client.get(f"/api/labs/{session.id}/solution/")
        self.assertEqual(resp.status_code, 200)
