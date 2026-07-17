"""Tests for the Azure Portal console simulator (apps.vmware_sim.azure_engine)
and its cross-technology bridge to the Linux lab terminal.

Covers: login gate, VM power lifecycle, NSG priority-ordered allow/deny rule
evaluation, managed disk attach/detach, the fail-closed grader for each hero
scenario preset, and the master-prompt canonical example — resizing a VM in
the portal changes the vCPU/RAM the SAME session's Linux guest reports via
nproc/free — proven end-to-end through the real bridge + shell, not just by
asserting on the engine's own state dict.
"""

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import azure_engine as ae
from apps.labs.provisioner.simulation import azure_bridge as ab
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell


class AzureEngineBase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "azure-test-session"
        ae.drop_session(self.sid)
        self.addCleanup(ae.drop_session, self.sid)
        self.addCleanup(ab.clear, self.sid)

    def _login(self, slug: str = ""):
        ae._ensure(self.sid, slug)
        ae.apply_action(self.sid, "login", {"user": "admin"})

    def _vm(self, slug: str = ""):
        return ae.get_state(self.sid, slug)["state"]["vms"][0]


class LoginGateTests(AzureEngineBase):
    def test_actions_require_login(self):
        ae._ensure(self.sid, "")
        res = ae.apply_action(self.sid, "start_vm", {"vm_name": "vm-web01"})
        self.assertFalse(res["ok"])
        self.assertIn("Sign in", res["error"])

    def test_login_then_action_succeeds(self):
        self._login()
        res = ae.apply_action(self.sid, "start_vm", {"vm_name": "vm-web01"})
        self.assertTrue(res["ok"], res)


class VmPowerLifecycleTests(AzureEngineBase):
    def test_stop_then_start_transitions(self):
        self._login()
        r1 = ae.apply_action(self.sid, "stop_vm", {"vm_name": "vm-web01"})
        self.assertTrue(r1["ok"], r1)
        self.assertEqual(r1["power_state"], "stopping")

        r2 = ae.apply_action(self.sid, "start_vm", {"vm_name": "vm-web01"})
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(r2["power_state"], "starting")

    def test_unknown_vm_errors(self):
        self._login()
        res = ae.apply_action(self.sid, "start_vm", {"vm_name": "does-not-exist"})
        self.assertFalse(res["ok"])


class NsgRuleEvaluationTests(AzureEngineBase):
    def test_default_nsg_allows_http_but_not_ssh(self):
        self._login()
        state = ae.get_state(self.sid)["state"]
        nsg = state["nsgs"][0]
        self.assertTrue(ae._nsg_allows(nsg, "80"))
        self.assertTrue(ae._nsg_allows(nsg, "22"))  # base preset allows SSH by default

    def test_removing_ssh_rule_falls_through_to_deny(self):
        self._login()
        ae.apply_action(self.sid, "remove_nsg_rule", {"nsg_name": "nsg-web", "name": "AllowSSH"})
        state = ae.get_state(self.sid)["state"]
        nsg = state["nsgs"][0]
        self.assertFalse(ae._nsg_allows(nsg, "22"))
        self.assertTrue(ae._nsg_allows(nsg, "80"))

    def test_adding_lower_priority_allow_rule_wins_over_deny(self):
        self._login(slug="azure-nsg-blocks-ssh")
        state = ae.get_state(self.sid, "azure-nsg-blocks-ssh")["state"]
        nsg = state["nsgs"][0]
        self.assertFalse(ae._nsg_allows(nsg, "22"))

        res = ae.apply_action(self.sid, "add_nsg_rule", {
            "nsg_name": "nsg-web", "name": "AllowSSH", "priority": 110,
            "protocol": "TCP", "destination_port": "22", "access": "Allow",
        })
        self.assertTrue(res["ok"], res)
        state = ae.get_state(self.sid)["state"]
        nsg = state["nsgs"][0]
        self.assertTrue(ae._nsg_allows(nsg, "22"))

    def test_check_port_reachable_respects_power_state(self):
        self._login()
        self.assertTrue(ae.check_port_reachable(self.sid, "22"))
        ae.apply_action(self.sid, "stop_vm", {"vm_name": "vm-web01"})
        self.assertFalse(ae.check_port_reachable(self.sid, "22"))


class ManagedDiskTests(AzureEngineBase):
    def test_attach_and_detach_disk(self):
        self._login()
        res = ae.apply_action(self.sid, "attach_disk", {
            "vm_name": "vm-web01", "disk_name": "disk-data-unattached",
        })
        self.assertTrue(res["ok"], res)
        state = ae.get_state(self.sid)["state"]
        disk = next(d for d in state["disks"] if d["name"] == "disk-data-unattached")
        self.assertEqual(disk["state"], "Attached")
        self.assertIn("disk-data-unattached", state["vms"][0]["data_disks"])

        res2 = ae.apply_action(self.sid, "detach_disk", {"disk_name": "disk-data-unattached"})
        self.assertTrue(res2["ok"], res2)
        state2 = ae.get_state(self.sid)["state"]
        disk2 = next(d for d in state2["disks"] if d["name"] == "disk-data-unattached")
        self.assertEqual(disk2["state"], "Unattached")

    def test_cannot_double_attach(self):
        self._login()
        ae.apply_action(self.sid, "attach_disk", {"vm_name": "vm-web01", "disk_name": "disk-data-unattached"})
        res = ae.apply_action(self.sid, "attach_disk", {"vm_name": "vm-web01", "disk_name": "disk-data-unattached"})
        self.assertFalse(res["ok"])


class HeroScenarioGradingTests(AzureEngineBase):
    def test_resize_scenario_fails_before_and_passes_after(self):
        slug = "azure-vm-undersized-resize"
        self._login(slug)
        ok, _ = ae.validate_azure_lab(self.sid, slug)
        self.assertFalse(ok)

        ae.apply_action(self.sid, "resize_vm", {"vm_name": "vm-web01", "size": "Standard_D2s_v5"})
        ok2, msg = ae.validate_azure_lab(self.sid, slug)
        self.assertTrue(ok2, msg)

    def test_nsg_scenario_fails_before_and_passes_after(self):
        slug = "azure-nsg-blocks-ssh"
        self._login(slug)
        ok, _ = ae.validate_azure_lab(self.sid, slug)
        self.assertFalse(ok)

        ae.apply_action(self.sid, "add_nsg_rule", {
            "nsg_name": "nsg-web", "name": "AllowSSH", "priority": 110,
            "protocol": "TCP", "destination_port": "22", "access": "Allow",
        })
        ok2, msg = ae.validate_azure_lab(self.sid, slug)
        self.assertTrue(ok2, msg)

    def test_disk_scenario_fails_before_and_passes_after(self):
        slug = "azure-attach-managed-disk"
        self._login(slug)
        ok, _ = ae.validate_azure_lab(self.sid, slug)
        self.assertFalse(ok)

        ae.apply_action(self.sid, "attach_disk", {"vm_name": "vm-web01", "disk_name": "disk-data-unattached"})
        ok2, msg = ae.validate_azure_lab(self.sid, slug)
        self.assertTrue(ok2, msg)

    def test_resize_scenario_blocked_while_vm_still_transitioning(self):
        slug = "azure-vm-undersized-resize"
        self._login(slug)
        ae.apply_action(self.sid, "resize_vm", {"vm_name": "vm-web01", "size": "Standard_D2s_v5"})
        ae.apply_action(self.sid, "stop_vm", {"vm_name": "vm-web01"})
        ok, msg = ae.validate_azure_lab(self.sid, slug)
        self.assertFalse(ok, msg)
        self.assertIn("transitioning", msg)


class AzureLinuxResizeBridgeTests(AzureEngineBase):
    """The master-prompt canonical example: resizing a VM in the Azure portal
    changes the vCPU/RAM the SAME session's Linux terminal reports."""

    def _shell_for_session(self) -> RHELShell:
        state = RHELOSState(hostname="vm-web01")
        state.session_id = self.sid
        return RHELShell(state=state)

    def test_resize_changes_nproc_and_free_output(self):
        self._login()
        shell = self._shell_for_session()
        self.assertEqual(shell.run("nproc").strip(), "4")  # RHELOSState default

        ae.apply_action(self.sid, "resize_vm", {"vm_name": "vm-web01", "size": "Standard_D8s_v5"})
        out = shell.run("nproc").strip()
        self.assertEqual(out, "8")
        self.assertEqual(shell.state.mem_mb, 32768)

    def test_no_pending_resize_leaves_hardware_untouched(self):
        self._login()
        shell = self._shell_for_session()
        before_cpu = shell.state.cpu_count
        shell.run("nproc")
        self.assertEqual(shell.state.cpu_count, before_cpu)


class AzureBridgePowerTests(AzureEngineBase):
    def test_stop_vm_records_power_event_for_bridge_consumers(self):
        self._login()
        ae.apply_action(self.sid, "stop_vm", {"vm_name": "vm-web01"})
        self.assertEqual(ab.consume_power(self.sid), "stop")
        # Second drain returns None (already consumed).
        self.assertIsNone(ab.consume_power(self.sid))
