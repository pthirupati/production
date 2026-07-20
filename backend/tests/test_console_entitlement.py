"""Standalone console APIs require a technology subscription."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.billing.models import TechnologySubscription
from apps.billing.subscription_utils import activate_technology_subscription
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

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
        self.linux, _ = Technology.objects.get_or_create(
            slug="linux",
            defaults={"name": "Linux", "price": 499, "is_free": False},
        )
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

    def test_linux_session_cannot_open_vmware_console_without_cross_tech(self):
        """Revenue loophole: Linux-only sub must not drive VMware via a plain Linux session."""
        scen, _ = Scenario.objects.get_or_create(
            slug="linux-plain-for-entitlement",
            defaults={
                "title": "Linux plain",
                "technology": self.linux,
                "lab_mode": "simulation",
                "simulation_type": "generic",
                "is_active": True,
                "is_free": True,
                "cross_technology": False,
                "vmware_link": False,
                "description": "CONTEXT: t\n\nENVIRONMENT: t\n\nOBJECTIVE: t",
                "objectives": ["x"],
                "time_limit": 600,
                "max_score": 100,
            },
        )
        if scen.cross_technology or scen.vmware_link:
            scen.cross_technology = False
            scen.vmware_link = False
            scen.save(update_fields=["cross_technology", "vmware_link"])
        session = LabSession.objects.create(
            user=self.user,
            scenario=scen,
            status="RUNNING",
            provider="simulation",
            container_id="sim-entitlement-linux",
            duration_limit=600,
        )
        res = self.client.get(f"/api/vmware/sessions/{session.id}/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data.get("code"), "SUBSCRIPTION_REQUIRED")

    def test_cross_tech_linux_session_can_open_vmware_console(self):
        scen, _ = Scenario.objects.get_or_create(
            slug="linux-cross-vmware-entitlement",
            defaults={
                "title": "Linux cross VMware",
                "technology": self.linux,
                "lab_mode": "simulation",
                "simulation_type": "generic",
                "is_active": True,
                "is_free": True,
                "cross_technology": True,
                "vmware_link": True,
                "description": "CONTEXT: t\n\nENVIRONMENT: t\n\nOBJECTIVE: t",
                "objectives": ["x"],
                "time_limit": 600,
                "max_score": 100,
            },
        )
        if not scen.cross_technology:
            scen.cross_technology = True
            scen.vmware_link = True
            scen.save(update_fields=["cross_technology", "vmware_link"])
        session = LabSession.objects.create(
            user=self.user,
            scenario=scen,
            status="RUNNING",
            provider="simulation",
            container_id="sim-entitlement-cross",
            duration_limit=600,
        )
        res = self.client.get(f"/api/vmware/sessions/{session.id}/")
        self.assertEqual(res.status_code, 200)

    def test_linux_session_cannot_open_datacenter_or_azure_console(self):
        """Same loophole pattern for other session consoles."""
        scen, _ = Scenario.objects.get_or_create(
            slug="linux-plain-for-dc-entitlement",
            defaults={
                "title": "Linux plain DC",
                "technology": self.linux,
                "lab_mode": "simulation",
                "simulation_type": "generic",
                "is_active": True,
                "is_free": True,
                "cross_technology": False,
                "vmware_link": False,
                "description": "CONTEXT: t\n\nENVIRONMENT: t\n\nOBJECTIVE: t",
                "objectives": ["x"],
                "time_limit": 600,
                "max_score": 100,
            },
        )
        session = LabSession.objects.create(
            user=self.user,
            scenario=scen,
            status="RUNNING",
            provider="simulation",
            container_id="sim-entitlement-linux-dc",
            duration_limit=600,
        )
        for path in (
            f"/api/vmware/datacenter/sessions/{session.id}/",
            f"/api/vmware/azure/sessions/{session.id}/",
            f"/api/vmware/gcp/sessions/{session.id}/",
            f"/api/vmware/openstack/sessions/{session.id}/",
        ):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 403, path)
            self.assertEqual(res.data.get("code"), "SUBSCRIPTION_REQUIRED", path)
