"""Tests for Jira inbound webhooks."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.jira_integration.models import UserScenarioJiraTicket
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


@override_settings(JIRA_WEBHOOK_SECRET="test-secret", DEBUG=False)
class JiraWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="whuser", email="w@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Linux", icon="terminal")
        self.scenario = Scenario.objects.create(
            title="Webhook Test", slug="webhook-test", technology=self.tech,
            description="Test", is_active=True,
        )
        self.session = LabSession.objects.create(user=self.user, scenario=self.scenario, status="RUNNING")
        UserScenarioJiraTicket.objects.create(
            user=self.user, scenario=self.scenario,
            issue_key="FIXIT-99", issue_url="https://example.atlassian.net/browse/FIXIT-99",
            last_session=self.session, jira_status="In Progress",
        )

    def test_webhook_rejects_bad_secret(self):
        client = Client()
        resp = client.post(
            "/api/jira/webhooks/",
            data='{"webhookEvent":"jira:issue_updated","issue":{"key":"FIXIT-99","fields":{"status":{"name":"Done"}}}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_webhook_updates_status(self):
        client = Client()
        resp = client.post(
            "/api/jira/webhooks/?secret=test-secret",
            data='{"webhookEvent":"jira:issue_updated","issue":{"key":"FIXIT-99","fields":{"status":{"name":"Done"}}}}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        ticket = UserScenarioJiraTicket.objects.get(issue_key="FIXIT-99")
        self.assertEqual(ticket.jira_status, "Done")
