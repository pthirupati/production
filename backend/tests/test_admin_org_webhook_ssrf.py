"""§S5 — AdminOrganizationDetailView.patch must reject unsafe webhook_url."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization


User = get_user_model()


class AdminOrgWebhookSsrfTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-ssrf", email="admin-ssrf@example.com",
            password="x", is_staff=True, is_superuser=True,
        )
        self.org = Organization.objects.create(
            name="SSRF Org", slug="ssrf-org", owner=self.admin,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_metadata_url_rejected(self):
        res = self.client.patch(
            f"/api/admin/organizations/{self.org.id}/",
            {"webhook_url": "https://169.254.169.254/latest/meta-data/"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.org.refresh_from_db()
        self.assertEqual(self.org.webhook_url, "")

    @patch(
        "apps.accounts.url_safety.resolve_public_addresses",
        return_value=["93.184.216.34"],
    )
    def test_safe_https_url_accepted(self, _resolve):
        res = self.client.patch(
            f"/api/admin/organizations/{self.org.id}/",
            {"webhook_url": "https://example.com/fixitlab-hook"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.org.refresh_from_db()
        self.assertEqual(self.org.webhook_url, "https://example.com/fixitlab-hook")

    def test_clearing_webhook_allowed(self):
        self.org.webhook_url = "https://example.com/fixitlab-hook"
        self.org.save(update_fields=["webhook_url"])
        res = self.client.patch(
            f"/api/admin/organizations/{self.org.id}/",
            {"webhook_url": ""},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.org.refresh_from_db()
        self.assertEqual(self.org.webhook_url, "")
