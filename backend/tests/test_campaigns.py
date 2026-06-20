"""Tests for the Admin Ads/Campaigns manager and public campaign banner API."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.adminpanel.models import Campaign

User = get_user_model()


class CampaignAdminCRUDTests(TestCase):
    """Admin can create, edit, enable, cancel and delete campaigns."""

    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="admin", email="admin@test.com", password="Admin123!", is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="reg", email="reg@test.com", password="Pass123!", is_staff=False,
        )

    def test_non_admin_forbidden_from_management(self):
        self.client.force_authenticate(user=self.regular)
        self.assertIn(
            self.client.get("/api/admin/campaigns/").status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED],
        )
        self.assertIn(
            self.client.post("/api/admin/campaigns/", {"title": "x"}, format="json").status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED],
        )

    def test_anonymous_forbidden_from_management(self):
        res = self.client.post("/api/admin/campaigns/", {"title": "x"}, format="json")
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_admin_full_crud_and_enable(self):
        self.client.force_authenticate(user=self.staff)

        # Create — starts as draft.
        res = self.client.post(
            "/api/admin/campaigns/",
            {
                "title": "K8s labs live",
                "body": "Try them now",
                "placement": "banner_top",
                "audience": "all",
                "bg_color": "#1e3a5f",
                "text_color": "#ffffff",
                "cta_label": "Open",
                "cta_url": "/technologies",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        cid = res.json()["id"]
        self.assertEqual(res.json()["status"], "draft")
        self.assertEqual(res.json()["created_by"], "admin")

        # List shows it.
        res = self.client.get("/api/admin/campaigns/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()), 1)

        # Update body.
        res = self.client.patch(f"/api/admin/campaigns/{cid}/", {"body": "Updated"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["body"], "Updated")

        # Enable.
        res = self.client.patch(f"/api/admin/campaigns/{cid}/", {"action": "enable"}, format="json")
        self.assertEqual(res.json()["status"], "enabled")
        self.assertTrue(res.json()["is_live"])

        # Cancel.
        res = self.client.patch(f"/api/admin/campaigns/{cid}/", {"action": "cancel"}, format="json")
        self.assertEqual(res.json()["status"], "cancelled")

        # Delete.
        res = self.client.delete(f"/api/admin/campaigns/{cid}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(Campaign.objects.filter(pk=cid).exists())

    def test_create_requires_title(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.post("/api/admin/campaigns/", {"title": "  "}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_social_posts_generation(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.post(
            "/api/admin/campaigns/social/",
            {
                "current_features": ["VMware simulator", "K8s labs"],
                "upcoming_features": ["GPU labs"],
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        for net in ("twitter", "linkedin", "reddit"):
            self.assertIn(net, body)
            self.assertIn("share_url", body[net])
        self.assertIn("twitter.com/intent/tweet", body["twitter"]["share_url"])
        self.assertIn("linkedin.com/sharing", body["linkedin"]["share_url"])
        self.assertIn("reddit.com/submit", body["reddit"]["share_url"])
        self.assertIn("VMware simulator", body["linkedin"]["text"])


class PublicActiveCampaignsTests(TestCase):
    """Public /api/campaigns/active/ returns only enabled in-window campaigns."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # avoid the anon-slice cache leaking between tests
        self.client = APIClient()
        now = timezone.now()

        self.enabled = Campaign.objects.create(
            title="Live banner", status="enabled", placement="banner_top", audience="all",
        )
        self.draft = Campaign.objects.create(
            title="Draft banner", status="draft", placement="banner_top",
        )
        self.cancelled = Campaign.objects.create(
            title="Cancelled banner", status="cancelled", placement="banner_top",
        )
        self.future = Campaign.objects.create(
            title="Future banner", status="enabled", placement="banner_top",
            starts_at=now + timedelta(days=1),
        )
        self.expired = Campaign.objects.create(
            title="Expired banner", status="enabled", placement="banner_top",
            ends_at=now - timedelta(days=1),
        )
        self.paid_only = Campaign.objects.create(
            title="Paid banner", status="enabled", placement="banner_top", audience="paid",
        )

    def test_anonymous_sees_only_live_audience_all(self):
        res = self.client.get("/api/campaigns/active/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        titles = {c["title"] for c in res.json()}
        # Only the always-on enabled "all" banner is visible.
        self.assertIn("Live banner", titles)
        self.assertNotIn("Draft banner", titles)
        self.assertNotIn("Cancelled banner", titles)
        self.assertNotIn("Future banner", titles)
        self.assertNotIn("Expired banner", titles)
        # Anonymous user is treated as "free" — paid-only campaign hidden.
        self.assertNotIn("Paid banner", titles)

    def test_serializer_excludes_internal_status_field(self):
        res = self.client.get("/api/campaigns/active/")
        item = res.json()[0]
        # Public payload should not leak admin-only fields.
        self.assertNotIn("status", item)
        self.assertNotIn("created_by", item)
        self.assertIn("title", item)
        self.assertIn("placement", item)

    def test_placement_filter(self):
        Campaign.objects.create(
            title="Dashboard card", status="enabled", placement="dashboard", audience="all",
        )
        res = self.client.get("/api/campaigns/active/?placement=dashboard")
        titles = {c["title"] for c in res.json()}
        self.assertEqual(titles, {"Dashboard card"})

    def test_paid_user_sees_paid_campaign(self):
        from apps.billing.models import TechnologySubscription
        from apps.question_bank.models import Technology

        paid_user = User.objects.create_user(
            username="paid", email="paid@test.com", password="Pass123!",
        )
        tech = Technology.objects.create(name="Linux", slug="linux", is_active=True)
        # An active technology subscription makes the user "paid" for targeting.
        TechnologySubscription.objects.create(
            user=paid_user, technology=tech,
            subscription_id="LINUX-PAID-2026-FIXITLAB",
            is_active=True, payment_verified=True,
        )
        self.client.force_authenticate(user=paid_user)
        res = self.client.get("/api/campaigns/active/")
        titles = {c["title"] for c in res.json()}
        self.assertIn("Paid banner", titles)
        self.assertIn("Live banner", titles)

    def test_free_user_excluded_from_paid_campaign(self):
        free_user = User.objects.create_user(
            username="free", email="free@test.com", password="Pass123!",
        )
        self.client.force_authenticate(user=free_user)
        res = self.client.get("/api/campaigns/active/")
        titles = {c["title"] for c in res.json()}
        self.assertNotIn("Paid banner", titles)
        self.assertIn("Live banner", titles)

    def test_never_500s_on_internal_error(self):
        # Even if the resolver blows up, the endpoint degrades to [].
        from unittest.mock import patch

        with patch(
            "apps.public_api.views.active_campaigns_for" if False else "apps.adminpanel.campaigns.active_campaigns_for",
            side_effect=Exception("boom"),
        ):
            res = self.client.get("/api/campaigns/active/?placement=banner_top")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json(), [])
