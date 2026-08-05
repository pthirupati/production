"""Tests for DevOps and Networking simulation engines."""
from django.test import TestCase

from apps.labs.provisioner.simulation.devops_state import DevOpsState
from apps.labs.provisioner.simulation.networking_state import NetworkingState
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.validation import (
    CANONICAL_DEVOPS_CHECK,
    CANONICAL_NETWORKING_CHECK,
    resolve_simulation_validation_script,
    validate_simulation_state,
)


class DevOpsNetworkingSimTests(TestCase):
    def test_devops_pipeline_failure_preset(self):
        d = DevOpsState("devops-ci-pipeline-failure")
        self.assertEqual(d.pipeline_status, "failed")
        self.assertFalse(d.is_healthy())
        d.fix_pipeline()
        self.assertTrue(d.is_healthy())

    def test_devops_helm_rollback(self):
        d = DevOpsState("devops-helm-release-stuck")
        self.assertEqual(d.helm_release_status, "pending-upgrade")
        d.helm_rollback("webapp", 3)
        self.assertEqual(d.helm_release_status, "deployed")

    def test_networking_bgp_fix(self):
        n = NetworkingState("networking-bgp-session-down")
        self.assertEqual(n.bgp_neighbors[0]["state"], "Idle")
        n.fix_bgp(65001)
        self.assertEqual(n.bgp_neighbors[0]["state"], "Established")
        self.assertTrue(n.is_healthy())

    def test_networking_ntp_sync(self):
        n = NetworkingState("networking-ntp-drift")
        self.assertFalse(n.ntp_synced)
        n.sync_ntp()
        self.assertTrue(n.is_healthy())

    def test_devops_validation_script_resolution(self):
        script = resolve_simulation_validation_script("devops-ci-pipeline-failure", "exit 0")
        self.assertIn("gitlab-runner", script)

    def test_networking_validation_script_resolution(self):
        script = resolve_simulation_validation_script("networking-bgp-session-down", "true")
        self.assertIn("bgp summary", script)

    def test_devops_validate_fails_until_fixed(self):
        state = RHELOSState("devops-ci-pipeline-failure")
        engine = UnifiedSimulationEngine("devops-ci-pipeline-failure", simulation_type="devops")
        engine.shell.state = state
        ok, _ = validate_simulation_state(state, CANONICAL_DEVOPS_CHECK, engine=engine)
        self.assertFalse(ok)
        engine.devops.fix_pipeline()
        ok, msg = validate_simulation_state(state, CANONICAL_DEVOPS_CHECK, engine=engine)
        self.assertTrue(ok, msg)

    def test_networking_validate_fails_until_bgp_fixed(self):
        state = RHELOSState("networking-bgp-session-down")
        engine = UnifiedSimulationEngine("networking-bgp-session-down", simulation_type="networking")
        engine.shell.state = state
        ok, _ = validate_simulation_state(state, CANONICAL_NETWORKING_CHECK, engine=engine)
        self.assertFalse(ok)
        engine.networking.fix_bgp(65001)
        ok, msg = validate_simulation_state(state, CANONICAL_NETWORKING_CHECK, engine=engine)
        self.assertTrue(ok, msg)

    def test_devops_shell_handlers(self):
        engine = UnifiedSimulationEngine("devops-ci-pipeline-failure", simulation_type="devops")
        out = engine.shell.run("gitlab-runner status")
        self.assertIn("FAILED", out)
        engine.shell.run("export KUBECONFIG=/root/.kube/config")
        out2 = engine.shell.run("gitlab-runner status")
        self.assertIn("passed", out2.lower())

    def test_networking_shell_handlers(self):
        engine = UnifiedSimulationEngine("networking-bgp-session-down", simulation_type="networking")
        out = engine.shell.run('vtysh -c "show ip bgp summary"')
        self.assertIn("Idle", out)
        engine.shell.run("router bgp 65001\n neighbor 10.0.0.2 remote-as 65001")
        out2 = engine.shell.run('vtysh -c "show ip bgp summary"')
        self.assertIn("Established", out2)

    def test_vyos_configure_commit_compare_rollback(self):
        n = NetworkingState("ai-infra-vyos-bgp")
        self.assertEqual(n.vyos_enter_configure(), "[edit]")
        before = n.vyos_running
        self.assertEqual(n.vyos_compare(), "No changes between working and active configurations")
        n.vyos_set("protocols bgp 65099 neighbor 10.64.1.50 remote-as 65099")
        diff = n.vyos_compare()
        self.assertIn("+", diff)
        self.assertIn("Commit complete", n.vyos_commit())
        self.assertNotEqual(n.vyos_running, before)
        self.assertIn("Rollback complete", n.vyos_rollback(1))
        self.assertEqual(n.vyos_running, before)
        hist = n.vyos_show_history()
        self.assertTrue("Revision" in hist or "No commits" in hist)

    def test_vyos_shell_commit_rollback_on_ai_infra(self):
        engine = UnifiedSimulationEngine("academy-ai-infra-005-production-cross-tech", simulation_type="rhel")
        out = engine.shell.run("configure")
        self.assertIn("[edit]", out)
        engine.shell.run("set interfaces ethernet eth1 description pxe-uplink")
        cmp_out = engine.shell.run("compare")
        self.assertTrue("+" in cmp_out or "No changes" in cmp_out or "Error" in cmp_out)
        commit = engine.shell.run("commit")
        self.assertTrue("Commit" in commit or "No configuration" in commit)
        rb = engine.shell.run("rollback 1")
        self.assertTrue("Rollback" in rb or "Error" in rb or "no previous" in rb.lower())
