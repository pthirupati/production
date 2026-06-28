"""
Tests for Jira integration sync layer.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient

from apps.jira_integration.models import JiraTicketLog, UserScenarioJiraTicket
from apps.jira_integration.sync import (
    ensure_scenario_ticket,
    sync_lab_completed,
    sync_lab_started,
    sync_lab_stopped,
)
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


@override_settings(
    JIRA_ENABLED=False,
    JIRA_BASE_URL="",
    JIRA_EMAIL="",
    JIRA_API_TOKEN="",
    JIRA_SIMULATION_MODE=False,
)
class JiraSyncDisabledTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sim_patcher = patch(
            "apps.jira_integration.simulated.use_simulated_jira", return_value=False
        )
        cls._sim_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._sim_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username="jirauser", email="j@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Linux", icon="terminal")
        self.scenario = Scenario.objects.create(
            title="Test Scenario",
            slug="test-scenario",
            technology=self.tech,
            description="Test",
            is_active=True,
        )
        self.session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="RUNNING",
        )

    def test_sync_disabled_returns_empty(self):
        result = sync_lab_started(self.session)
        self.assertEqual(result["jira_enabled"], False)
        self.assertEqual(result["jira_issue_key"], "")


@override_settings(
    JIRA_ENABLED=True,
    JIRA_BASE_URL="https://example.atlassian.net",
    JIRA_EMAIL="bot@example.com",
    JIRA_API_TOKEN="token",
    JIRA_PROJECT_KEY="FIXIT",
    JIRA_ISSUE_TYPE="Task",
    JIRA_TRANSITION_IN_PROGRESS="In Progress",
    JIRA_TRANSITION_TODO="To Do",
    JIRA_TRANSITION_DONE="Done",
    JIRA_SIMULATION_MODE=False,
    SITE_URL="https://fixitlab.example.com",
)
class JiraSyncEnabledTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._sim_patcher = patch(
            "apps.jira_integration.simulated.use_simulated_jira", return_value=False
        )
        cls._sim_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._sim_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        self.user = User.objects.create_user(username="jirauser2", email="j2@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Linux", icon="terminal")
        self.scenario = Scenario.objects.create(
            title="Broken Nginx",
            slug="broken-nginx",
            technology=self.tech,
            description="Nginx is down",
            objectives=["Fix nginx"],
            is_active=True,
            jira_priority="High",
        )
        self.session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="RUNNING",
        )

    @patch("apps.jira_integration.sync.JiraClient")
    def test_sync_lab_started_creates_ticket(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.create_issue.return_value = {"key": "FIXIT-101"}
        mock_client.issue_url.return_value = "https://example.atlassian.net/browse/FIXIT-101"
        mock_client.get_issue_status.return_value = "In Progress"
        mock_client_cls.return_value = mock_client

        result = sync_lab_started(self.session)

        self.assertTrue(result["jira_enabled"])
        self.assertEqual(result["jira_issue_key"], "FIXIT-101")
        self.session.refresh_from_db()
        self.assertEqual(self.session.jira_issue_key, "FIXIT-101")
        self.assertTrue(JiraTicketLog.objects.filter(session=self.session, action="created").exists())
        self.assertTrue(UserScenarioJiraTicket.objects.filter(user=self.user, scenario=self.scenario).exists())

    @patch("apps.jira_integration.sync.JiraClient")
    def test_sync_lab_started_resets_existing_ticket(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.issue_url.return_value = "https://example.atlassian.net/browse/FIXIT-101"
        mock_client.get_issue_status.return_value = "In Progress"
        mock_client_cls.return_value = mock_client

        UserScenarioJiraTicket.objects.create(
            user=self.user,
            scenario=self.scenario,
            issue_key="FIXIT-101",
            issue_url="https://example.atlassian.net/browse/FIXIT-101",
            run_count=1,
        )

        result = sync_lab_started(self.session)

        self.assertTrue(result["jira_reset"])
        self.assertEqual(result["jira_run_count"], 2)
        mock_client.add_comment.assert_called()
        mock_client.transition_issue.assert_any_call("FIXIT-101", "To Do")
        mock_client.transition_issue.assert_any_call("FIXIT-101", "In Progress")

    @patch("apps.jira_integration.sync.JiraClient")
    def test_sync_lab_completed_adds_comment_only(self, mock_client_cls):
        self.session.jira_issue_key = "FIXIT-101"
        self.session.jira_issue_url = "https://example.atlassian.net/browse/FIXIT-101"
        self.session.save()

        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.get_issue_status.return_value = "In Progress"
        mock_client_cls.return_value = mock_client

        result = sync_lab_completed(self.session, score=95, time_taken=600)
        self.assertTrue(result["jira_enabled"])
        mock_client.add_comment.assert_called()
        mock_client.transition_issue.assert_not_called()

    @patch("apps.jira_integration.sync.JiraClient")
    def test_sync_lab_stopped_resets_to_todo(self, mock_client_cls):
        self.session.jira_issue_key = "FIXIT-101"
        self.session.jira_issue_url = "https://example.atlassian.net/browse/FIXIT-101"
        self.session.save()

        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.get_issue_status.return_value = "To Do"
        mock_client_cls.return_value = mock_client

        sync_lab_stopped(self.session, reason="User stopped")
        mock_client.add_comment.assert_called()
        mock_client.transition_issue.assert_not_called()

    @patch("apps.jira_integration.sync.JiraClient")
    def test_ensure_scenario_ticket_creates_without_session(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.create_issue.return_value = {"key": "FIXIT-200"}
        mock_client.issue_url.return_value = "https://example.atlassian.net/browse/FIXIT-200"
        mock_client.get_issue_status.return_value = "To Do"
        mock_client_cls.return_value = mock_client

        result = ensure_scenario_ticket(self.user, self.scenario)

        self.assertTrue(result["jira_enabled"])
        self.assertEqual(result["jira_issue_key"], "FIXIT-200")
        self.assertTrue(result["jira_created"])
        self.assertTrue(
            UserScenarioJiraTicket.objects.filter(
                user=self.user, scenario=self.scenario, issue_key="FIXIT-200"
            ).exists()
        )


@override_settings(JIRA_ENABLED=True, JIRA_SIMULATION_MODE=True)
class JiraSubscriptionGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="nosub", email="n@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Gated Tech", icon="terminal")
        self.scenario = Scenario.objects.create(
            title="Gated Scenario",
            slug="gated-scenario",
            technology=self.tech,
            description="Test",
            is_active=True,
            is_free=False,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _exhaust_free_labs(self):
        """Use up the Free plan's daily lab quota so labs_remaining == 0."""
        from apps.billing.services import get_user_plan_info
        max_labs = get_user_plan_info(self.user)["plan"]["max_labs_per_day"]
        for _ in range(max_labs):
            LabSession.objects.create(user=self.user, scenario=self.scenario, status="RUNNING")

    def test_open_blocked_after_free_labs_exhausted(self):
        """Not subscribed + no free labs left → ticket must NOT open."""
        self._exhaust_free_labs()
        resp = self.client.post(f"/api/jira/tickets/scenario/{self.scenario.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json().get("code"), "SUBSCRIPTION_REQUIRED")

    def test_get_blocked_after_free_labs_exhausted(self):
        self._exhaust_free_labs()
        resp = self.client.get(f"/api/jira/tickets/scenario/{self.scenario.id}/")
        self.assertEqual(resp.status_code, 403)

    def test_open_allowed_with_free_labs_remaining(self):
        """Free-plan user with daily free labs left → ticket may open."""
        resp = self.client.post(f"/api/jira/tickets/scenario/{self.scenario.id}/")
        self.assertNotEqual(resp.status_code, 403)
