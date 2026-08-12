"""Jira REST API v3 teaching surface over simulated tickets."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.jira_integration.jira_rest import jira_rest_api
from apps.jira_integration.models import UserScenarioJiraTicket
from apps.question_bank.models import Scenario, Technology


User = get_user_model()


@override_settings(JIRA_SIMULATION_MODE=True)
class JiraRestApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jira-rest", password="x")
        tech = Technology.objects.create(slug="linux-test", name="Linux Test")
        self.scenario = Scenario.objects.create(
            slug="jira-rest-lab",
            title="Jira REST lab",
            technology=tech,
            difficulty="easy",
        )
        self.ticket = UserScenarioJiraTicket.objects.create(
            user=self.user,
            scenario=self.scenario,
            issue_key="KAN-42",
            issue_url="/jira/KAN-42",
            summary="Broken nginx",
            description="nginx won't start",
            jira_status="In Progress",
            simulated=True,
        )

    def test_get_issue(self):
        status, body = jira_rest_api(
            "/rest/api/3/issue/KAN-42",
            method="GET",
            user=self.user,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["key"], "KAN-42")
        self.assertEqual(body["fields"]["summary"], "Broken nginx")

    def test_get_transitions(self):
        status, body = jira_rest_api(
            "http://jira:8089/rest/api/3/issue/KAN-42/transitions",
            method="GET",
            user=self.user,
        )
        self.assertEqual(status, 200)
        names = {t["name"] for t in body["transitions"]}
        self.assertIn("Done", names)

    def test_post_comment(self):
        status, body = jira_rest_api(
            "/rest/api/3/issue/KAN-42/comment",
            method="POST",
            body={"body": "Looking into it"},
            user=self.user,
        )
        self.assertEqual(status, 201)

    def test_missing_issue_404(self):
        status, body = jira_rest_api(
            "/rest/api/3/issue/KAN-999",
            method="GET",
            user=self.user,
        )
        self.assertEqual(status, 404)
