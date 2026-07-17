"""API-level test for the cross-console ActiveFaultsView (Phase 3.2/3.4).

Any open console for a lab session should be able to ask "what's currently
broken here" without knowing which engine caused it.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.labs.provisioner.simulation import chaos_engine as ce
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


class ActiveFaultsApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username="faultuser", email="fault@test.com", password="pass12345!"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@test.com", password="pass12345!"
        )
        self.tech = Technology.objects.create(name="VMware", slug="vmware-faults-test", is_active=True)
        self.scenario = Scenario.objects.create(
            title="Fault ledger scenario",
            slug="fault-ledger-test",
            technology=self.tech,
            is_active=True,
            validation_script="exit 0",
        )
        self.session = LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="RUNNING",
            provider="simulation", container_id="sim-fault-test",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_lists_active_faults_for_the_session(self):
        ce.inject(str(self.session.id), "drop_nic", "web01")
        res = self.client.get(f"/api/vmware/sessions/{self.session.id}/faults/")
        self.assertEqual(res.status_code, 200)
        faults = res.json()["faults"]
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0]["fault_type"], "drop_nic")

    def test_active_false_includes_cleared_faults(self):
        ce.inject(str(self.session.id), "drop_nic", "web01")
        ce.clear_faults(str(self.session.id))
        active = self.client.get(f"/api/vmware/sessions/{self.session.id}/faults/").json()["faults"]
        self.assertEqual(active, [])
        all_faults = self.client.get(f"/api/vmware/sessions/{self.session.id}/faults/?active=false").json()["faults"]
        self.assertEqual(len(all_faults), 1)

    def test_other_users_session_is_not_accessible(self):
        other_client = APIClient()
        other_client.force_authenticate(user=self.other_user)
        res = other_client.get(f"/api/vmware/sessions/{self.session.id}/faults/")
        self.assertEqual(res.status_code, 404)

    def test_unauthenticated_request_is_rejected(self):
        anon = APIClient()
        res = anon.get(f"/api/vmware/sessions/{self.session.id}/faults/")
        self.assertIn(res.status_code, (401, 403))
