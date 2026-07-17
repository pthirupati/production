"""Integration test: a real gcp-* LabSession, validated cold (no warm engine
cache — the realistic "different worker" case), must dispatch through
`SimulationProvisioner.run_validation` -> `validate_gcp_lab`, and the
terminal seeded for that session must be the SAME Compute Engine instance
(hostname/vCPU/RAM match the console), proving the unified-server model
holds end-to-end and not just inside gcp_engine's own unit tests.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.labs.models import LabSession
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
from apps.question_bank.models import Scenario, Technology
from apps.vmware_sim import gcp_engine as ge
from apps.labs.provisioner.simulation.shell import get_sim_session

User = get_user_model()


class GcpDispatchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username="gcpdispatch", email="gcpdispatch@test.com", password="pass12345!"
        )
        self.tech = Technology.objects.create(name="GCP", slug="gcp-dispatch-test", is_active=True)

    def _make_session(self, slug: str, sim_type: str = "gcp") -> tuple[LabSession, str]:
        scenario = Scenario.objects.create(
            title=f"Dispatch test {slug}", slug=slug, technology=self.tech,
            is_active=True, simulation_type=sim_type, validation_script="exit 0",
        )
        resource_id = f"sim-{slug}"
        session = LabSession.objects.create(
            user=self.user, scenario=scenario, status="RUNNING",
            provider="simulation", container_id=resource_id,
        )
        self.addCleanup(ge.drop_session, str(session.id))
        return session, resource_id

    def test_cold_session_dispatches_to_gcp_validator_and_seeds_terminal(self):
        session, resource_id = self._make_session("gcp-instance-undersized-resize")
        prov = SimulationProvisioner()

        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)

        entry = get_sim_session(str(session.id))
        self.assertIsNotNone(entry)
        shell_state = entry["state"]["engine"].shell.state
        self.assertEqual(shell_state.hostname, "web01")
        self.assertEqual(shell_state.cpu_count, 2)  # e2-micro preset
        self.assertEqual(shell_state.mem_mb, 1024)

        ge.apply_action(str(session.id), "login", {"user": "admin"})
        ge.apply_action(str(session.id), "stop_instance", {"instance_name": "web01"})
        import time
        from unittest import mock
        with mock.patch.object(ge, "_now", return_value=time.time() + ge.PENDING_SECONDS + 1):
            ge.get_state(str(session.id))
        ge.apply_action(str(session.id), "set_machine_type", {"instance_name": "web01", "machine_type": "e2-standard-2"})
        ge.apply_action(str(session.id), "start_instance", {"instance_name": "web01"})
        with mock.patch.object(ge, "_now", return_value=time.time() + ge.PENDING_SECONDS + 1):
            ge.get_state(str(session.id))

        passed2, msg2 = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertTrue(passed2, msg2)

    def test_generic_sim_type_with_gcp_slug_still_dispatches(self):
        session, resource_id = self._make_session("gcp-firewall-blocks-ssh", sim_type="generic")
        prov = SimulationProvisioner()
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)
        self.assertNotIn("session not found", msg.lower())
