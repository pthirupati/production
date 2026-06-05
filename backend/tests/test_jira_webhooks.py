"""Tests for Jira inbound webhooks."""

import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from apps.jira_integration.models import UserScenarioJiraTicket
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


@override_settings(JIRA_WEBHOOK_SECRET="test-secret", DEBUG=False, SECURE_SSL_REDIRECT=False)
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

    def test_webhook_accepts_hmac_signature(self):
        client = Client()
        payload = json.dumps({
            "webhookEvent": "jira:issue_updated",
            "issue": {"key": "FIXIT-99", "fields": {"status": {"name": "Done"}}},
        }).encode()
        sig = hmac.new(b"test-secret", payload, hashlib.sha256).hexdigest()
        resp = client.post(
            "/api/jira/webhooks/",
            data=payload,
            content_type="application/json",
            HTTP_X_FIXITLAB_SIGNATURE=f"sha256={sig}",
        )
        self.assertEqual(resp.status_code, 200)
        ticket = UserScenarioJiraTicket.objects.get(issue_key="FIXIT-99")
        self.assertEqual(ticket.jira_status, "Done")

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
