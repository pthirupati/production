"""Integration test: a real azure-* LabSession, validated cold (no warm
engine cache — the realistic "different worker" case), must dispatch through
`SimulationProvisioner.run_validation` -> `validate_azure_lab`, and the
terminal seeded for that session must be the SAME Azure VM (hostname/vCPU/RAM
match the portal), proving the unified-server model holds end-to-end and not
just inside azure_engine's own unit tests.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.labs.models import LabSession
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
from apps.question_bank.models import Scenario, Technology
from apps.vmware_sim import azure_engine as ae
from apps.labs.provisioner.simulation.shell import get_sim_session

User = get_user_model()


class AzureDispatchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.user = User.objects.create_user(
            username="azuredispatch", email="azuredispatch@test.com", password="pass12345!"
        )
        self.tech = Technology.objects.create(name="Azure", slug="azure-dispatch-test", is_active=True)

    def _make_session(self, slug: str, sim_type: str = "azure") -> LabSession:
        scenario = Scenario.objects.create(
            title=f"Dispatch test {slug}", slug=slug, technology=self.tech,
            is_active=True, simulation_type=sim_type, validation_script="exit 0",
        )
        resource_id = f"sim-{slug}"
        session = LabSession.objects.create(
            user=self.user, scenario=scenario, status="RUNNING",
            provider="simulation", container_id=resource_id,
        )
        self.addCleanup(ae.drop_session, str(session.id))
        return session, resource_id

    def test_cold_session_dispatches_to_azure_validator_and_seeds_terminal(self):
        session, resource_id = self._make_session("azure-vm-undersized-resize")
        prov = SimulationProvisioner()

        # No cache warm-up: exercise the ensure_sim_session() fallback path.
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)

        entry = get_sim_session(str(session.id))
        self.assertIsNotNone(entry)
        shell_state = entry["state"]["engine"].shell.state
        self.assertEqual(shell_state.hostname, "vm-web01")
        self.assertEqual(shell_state.cpu_count, 1)  # Standard_B1s preset
        self.assertEqual(shell_state.mem_mb, 1024)

        ae.apply_action(str(session.id), "login", {"user": "admin"})
        ae.apply_action(str(session.id), "resize_vm", {"vm_name": "vm-web01", "size": "Standard_D2s_v5"})

        passed2, msg2 = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertTrue(passed2, msg2)

    def test_generic_sim_type_with_azure_slug_still_dispatches(self):
        """Slug prefix alone must be enough even when simulation_type wasn't
        normalized to "azure" on the scenario row (mirrors how SOC/NetApp/
        DellEmc/Datacenter dispatch tolerate a generic simulation_type)."""
        session, resource_id = self._make_session("azure-nsg-blocks-ssh", sim_type="generic")
        prov = SimulationProvisioner()
        passed, msg = prov.run_validation(resource_id, "exit 0", session.scenario.slug)
        self.assertFalse(passed, msg)
        self.assertNotIn("session not found", msg.lower())
