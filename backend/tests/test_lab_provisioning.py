"""
Tests for the admin Lab Provisioning endpoint.

Covers:
  - GET lists scenario-folder technologies (the checkbox source) with the
    workflow input name for the copy-paste command.
  - POST re-seeds ONLY the selected technologies via
    `seed_scenarios --merge-only --technologies <slugs>` and returns a summary
    plus the exact `gh workflow run` command.
  - unknown slugs are rejected / reported; empty selection → 400.
  - admin-only: anonymous and non-staff users are forbidden.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.question_bank.models import Scenario, Technology

User = get_user_model()

LIST_URL = "/api/admin/lab-provisioning/"


class AdminLabProvisioningTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin", email="admin@test.com", password="Admin123!", is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="bob", email="bob@test.com", password="Pass123!", is_staff=False,
        )

    # ── permission gating ──

    def test_anonymous_forbidden(self):
        res = self.client.get(LIST_URL)
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(user=self.regular)
        res = self.client.get(LIST_URL)
        self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        res2 = self.client.post(LIST_URL, {"technologies": "vmware"}, format="json")
        self.assertIn(res2.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    # ── GET catalog ──

    def test_list_returns_scenario_technologies(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.get(LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("technologies", data)
        self.assertGreater(data["count"], 0)
        slugs = {t["slug"] for t in data["technologies"]}
        # Real scenario folders that ship in the repo.
        self.assertIn("vmware", slugs)
        # Helper folders are hidden from the checklist.
        self.assertNotIn("shared", slugs)
        # The UI uses this to render the copy-paste workflow command.
        self.assertEqual(data["workflow_input"], "technologies")
        self.assertFalse(data["github_dispatch_available"])

    # ── POST re-seed selected ──

    def test_provision_runs_for_selected_only(self):
        self.client.force_authenticate(user=self.staff)
        self.assertEqual(Scenario.objects.count(), 0)

        res = self.client.post(LIST_URL, {"technologies": "vmware"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        body = res.json()
        self.assertTrue(body["provisioned"])
        self.assertEqual(body["technologies"], ["vmware"])
        self.assertEqual(body["slug_csv"], "vmware")

        # Selected tech got seeded into the DB.
        self.assertTrue(Technology.objects.filter(slug="vmware").exists())
        self.assertGreater(Scenario.objects.count(), 0)
        # Every seeded scenario belongs to the selected technology only.
        other = Scenario.objects.exclude(technology__slug="vmware").count()
        self.assertEqual(other, 0)

        # The exact copy-paste command for the same selection is returned.
        self.assertIn("gh workflow run production.yml", body["gh_command"])
        self.assertIn("-f technologies=vmware", body["gh_command"])

    def test_provision_accepts_list_payload(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.post(LIST_URL, {"technologies": ["vmware"]}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertEqual(res.json()["slug_csv"], "vmware")

    def test_empty_selection_is_400(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.post(LIST_URL, {"technologies": ""}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_slug_rejected(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.post(LIST_URL, {"technologies": "not-a-real-tech"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not-a-real-tech", res.json().get("unknown", []))

    def test_seed_failure_returns_500_not_crash(self):
        self.client.force_authenticate(user=self.staff)
        with patch("django.core.management.call_command", side_effect=RuntimeError("boom")):
            res = self.client.post(LIST_URL, {"technologies": "vmware"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("boom", res.json().get("error", ""))
