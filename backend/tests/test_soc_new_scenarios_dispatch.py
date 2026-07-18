"""Integration test: the 4 new SOC hero scenarios (escalate, playbook,
threat-hunt, red-vs-blue) dispatch correctly through
`SimulationProvisioner.run_validation` -> `validate_soc_lab`, cold (no warm
engine cache — the realistic "different worker" case), proving the unified
dispatch + grading path holds for freshly-authored content and not just the
2 pre-existing SOC hero labs.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.labs.models import LabSession
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
from apps.question_bank.models import Scenario, Technology
from apps.vmware_sim import soc_engine as se

User = get_user_model()


class SocNewScenariosDispatchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username="socdispatch", email="socdispatch@test.com", password="pass12345!"
        )
        self.tech = Technology.objects.create(name="SOC", slug="soc-dispatch-test", is_active=True)

    def _make_session(self, slug: str) -> tuple[LabSession, str]:
        scenario = Scenario.objects.create(
            title=f"Dispatch test {slug}", slug=slug, technology=self.tech,
            is_active=True, simulation_type="soc", validation_script="exit 0",
        )
        resource_id = f"sim-{slug}"
        session = LabSession.objects.create(
            user=self.user, scenario=scenario, status="RUNNING",
            provider="simulation", container_id=resource_id,
        )
        self.addCleanup(se.drop_session, str(session.id))
        return session, resource_id

    def _login(self, session_id: str):
        se.apply_action(session_id, "login", {"user": "analyst"})

    def test_escalate_scenario_dispatches_and_grades(self):
        session, resource_id = self._make_session("soc-escalate-critical-alert")
        prov = SimulationProvisioner()
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)

        self._login(str(session.id))
        se.apply_action(str(session.id), "escalate_incident", {"alert_id": "AL-1003"})
        passed2, msg2 = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertTrue(passed2, msg2)

    def test_playbook_scenario_dispatches_and_grades(self):
        session, resource_id = self._make_session("soc-execute-containment-playbook")
        prov = SimulationProvisioner()
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)

        self._login(str(session.id))
        se.apply_action(str(session.id), "run_playbook", {"playbook_id": "pb-malware-contain"})
        passed2, msg2 = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertTrue(passed2, msg2)

    def test_threat_hunt_scenario_dispatches_and_grades(self):
        session, resource_id = self._make_session("soc-threat-hunt-attacker-ip")
        prov = SimulationProvisioner()
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)

        self._login(str(session.id))
        se.apply_action(str(session.id), "search_logs", {"query": "203.0.113.55"})
        passed2, msg2 = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertTrue(passed2, msg2)

    def test_red_vs_blue_scenario_requires_both_containment_actions(self):
        session, resource_id = self._make_session("soc-red-vs-blue-dual-containment")
        prov = SimulationProvisioner()
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)

        self._login(str(session.id))
        se.apply_action(str(session.id), "quarantine_host", {"asset": "ws-finance-07"})
        passed_partial, _ = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed_partial)

        se.apply_action(str(session.id), "block_ip", {"ip": "198.51.100.23"})
        passed2, msg2 = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertTrue(passed2, msg2)
