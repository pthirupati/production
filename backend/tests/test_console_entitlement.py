"""Standalone console APIs require a technology subscription."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.billing.models import TechnologySubscription
from apps.billing.subscription_utils import activate_technology_subscription
from apps.question_bank.models import Technology

User = get_user_model()


class StandaloneConsoleEntitlementTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="linux-only",
            email="linux-only@example.com",
            password="testpass123",
        )
        self.vmware, _ = Technology.objects.get_or_create(
            slug="vmware",
            defaults={"name": "VMware", "price": 499, "is_free": False},
        )
        if self.vmware.is_free or self.vmware.price == 0:
            self.vmware.is_free = False
            self.vmware.price = 499
            self.vmware.save(update_fields=["is_free", "price"])
        self.client.force_authenticate(user=self.user)

    def test_vmware_demo_denied_without_subscription(self):
        res = self.client.get("/api/vmware/demo/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data.get("code"), "SUBSCRIPTION_REQUIRED")

    def test_vmware_demo_allowed_with_subscription(self):
        sub, _ = TechnologySubscription.objects.get_or_create(
            user=self.user, technology=self.vmware,
        )
        activate_technology_subscription(sub)
        res = self.client.get("/api/vmware/demo/")
        self.assertEqual(res.status_code, 200)

    def test_vmware_demo_allowed_for_staff(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        res = self.client.get("/api/vmware/demo/")
        self.assertEqual(res.status_code, 200)
