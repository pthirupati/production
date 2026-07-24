"""Tests for the Google Cloud Console simulator (apps.vmware_sim.gcp_engine)
and its cross-technology bridge to the Linux lab terminal.

Covers: login gate, instance power lifecycle, VPC firewall priority-ordered
allow/deny rule evaluation, persistent disk attach/detach, the fail-closed
grader for each hero scenario preset, and the master-prompt canonical
example — changing an instance's machine type in the console changes the
vCPU/RAM the SAME session's Linux guest reports via nproc/free — proven
end-to-end through the real bridge + shell, not just by asserting on the
engine's own state dict.
"""

from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import gcp_engine as ge
from apps.labs.provisioner.simulation import gcp_bridge as gb
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell


class GcpEngineBase(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "gcp-test-session"
        ge.drop_session(self.sid)
        self.addCleanup(ge.drop_session, self.sid)
        self.addCleanup(gb.clear, self.sid)

    def _login(self, slug: str = ""):
        ge._ensure(self.sid, slug)
        ge.apply_action(self.sid, "login", {"user": "admin"})

    def _instance(self, slug: str = ""):
        return ge.get_state(self.sid, slug)["state"]["instances"][0]


class LoginGateTests(GcpEngineBase):
    def test_actions_require_login(self):
        ge._ensure(self.sid, "")
        res = ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        self.assertFalse(res["ok"])
        self.assertIn("Sign in", res["error"])

    def test_login_then_action_succeeds(self):
        self._login()
        res = ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        self.assertTrue(res["ok"], res)


class InstancePowerLifecycleTests(GcpEngineBase):
    def test_stop_then_start_transitions(self):
        self._login()
        r1 = ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        self.assertTrue(r1["ok"], r1)
        self.assertEqual(r1["status"], "STOPPING")

        r2 = ge.apply_action(self.sid, "start_instance", {"instance_name": "web01"})
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(r2["status"], "PROVISIONING")

    def test_unknown_instance_errors(self):
        self._login()
        res = ge.apply_action(self.sid, "stop_instance", {"instance_name": "does-not-exist"})
        self.assertFalse(res["ok"])


class FirewallRuleEvaluationTests(GcpEngineBase):
    def test_default_vpc_allows_http_and_ssh(self):
        self._login()
        state = ge.get_state(self.sid)["state"]
        self.assertTrue(ge._fw_allows(state, "80"))
        self.assertTrue(ge._fw_allows(state, "22"))  # base preset allows SSH by default

    def test_removing_ssh_rule_falls_through_to_deny(self):
        self._login()
        ge.apply_action(self.sid, "delete_firewall_rule", {"name": "allow-ssh"})
        state = ge.get_state(self.sid)["state"]
        self.assertFalse(ge._fw_allows(state, "22"))
        self.assertTrue(ge._fw_allows(state, "80"))

    def test_adding_lower_priority_allow_rule_wins_over_deny(self):
        self._login(slug="gcp-firewall-blocks-ssh")
        state = ge.get_state(self.sid, "gcp-firewall-blocks-ssh")["state"]
        self.assertFalse(ge._fw_allows(state, "22"))

        res = ge.apply_action(self.sid, "create_firewall_rule", {
            "name": "allow-ssh", "priority": 1000, "protocols": "tcp:22", "action": "ALLOW",
        })
        self.assertTrue(res["ok"], res)
        state = ge.get_state(self.sid)["state"]
        self.assertTrue(ge._fw_allows(state, "22"))

    def test_cannot_delete_system_rule(self):
        self._login()
        res = ge.apply_action(self.sid, "delete_firewall_rule", {"name": "default-deny-ingress"})
        self.assertFalse(res["ok"])

    def test_check_port_reachable_respects_power_state(self):
        self._login()
        self.assertTrue(ge.check_port_reachable(self.sid, "22"))
        ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        self.assertFalse(ge.check_port_reachable(self.sid, "22"))


class PersistentDiskTests(GcpEngineBase):
    def test_attach_and_detach_disk(self):
        self._login()
        res = ge.apply_action(self.sid, "attach_disk", {
            "instance_name": "web01", "disk_name": "disk-data-unattached",
        })
        self.assertTrue(res["ok"], res)
        state = ge.get_state(self.sid)["state"]
        disk = next(d for d in state["disks"] if d["name"] == "disk-data-unattached")
        self.assertEqual(disk["attached_to"], "web01")
        self.assertIn("disk-data-unattached", state["instances"][0]["extra_disks"])

        res2 = ge.apply_action(self.sid, "detach_disk", {"disk_name": "disk-data-unattached"})
        self.assertTrue(res2["ok"], res2)
        state2 = ge.get_state(self.sid)["state"]
        disk2 = next(d for d in state2["disks"] if d["name"] == "disk-data-unattached")
        self.assertIsNone(disk2["attached_to"])

    def test_cannot_double_attach(self):
        self._login()
        ge.apply_action(self.sid, "attach_disk", {"instance_name": "web01", "disk_name": "disk-data-unattached"})
        res = ge.apply_action(self.sid, "attach_disk", {"instance_name": "web01", "disk_name": "disk-data-unattached"})
        self.assertFalse(res["ok"])

    def test_cannot_detach_boot_disk(self):
        self._login()
        res = ge.apply_action(self.sid, "detach_disk", {"disk_name": "web01"})
        self.assertFalse(res["ok"])


class HeroScenarioGradingTests(GcpEngineBase):
    def test_resize_scenario_fails_before_and_passes_after(self):
        slug = "gcp-instance-undersized-resize"
        self._login(slug)
        ok, _ = ge.validate_gcp_lab(self.sid, slug)
        self.assertFalse(ok)

        ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        with mock.patch.object(ge, "_now", return_value=ge.time.time() + ge.PENDING_SECONDS + 1):
            ge.get_state(self.sid, slug)  # fold the stop transition in
        ge.apply_action(self.sid, "set_machine_type", {"instance_name": "web01", "machine_type": "e2-standard-2"})
        ge.apply_action(self.sid, "start_instance", {"instance_name": "web01"})
        with mock.patch.object(ge, "_now", return_value=ge.time.time() + ge.PENDING_SECONDS + 1):
            ge.get_state(self.sid, slug)  # fold the start transition in
            ok2, msg = ge.validate_gcp_lab(self.sid, slug)
        self.assertTrue(ok2, msg)

    def test_firewall_scenario_fails_before_and_passes_after(self):
        slug = "gcp-firewall-blocks-ssh"
        self._login(slug)
        ok, _ = ge.validate_gcp_lab(self.sid, slug)
        self.assertFalse(ok)

        ge.apply_action(self.sid, "create_firewall_rule", {
            "name": "allow-ssh", "priority": 1000, "protocols": "tcp:22", "action": "ALLOW",
        })
        ok2, msg = ge.validate_gcp_lab(self.sid, slug)
        self.assertTrue(ok2, msg)

    def test_disk_scenario_fails_before_and_passes_after(self):
        slug = "gcp-attach-persistent-disk"
        self._login(slug)
        ok, _ = ge.validate_gcp_lab(self.sid, slug)
        self.assertFalse(ok)

        ge.apply_action(self.sid, "attach_disk", {"instance_name": "web01", "disk_name": "disk-data-unattached"})
        ok2, msg = ge.validate_gcp_lab(self.sid, slug)
        self.assertTrue(ok2, msg)

    def test_resize_scenario_blocked_while_instance_still_transitioning(self):
        slug = "gcp-instance-undersized-resize"
        self._login(slug)
        ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        ge.apply_action(self.sid, "set_machine_type", {"instance_name": "web01", "machine_type": "e2-standard-2"})
        ge.apply_action(self.sid, "start_instance", {"instance_name": "web01"})
        # Still transitioning (PROVISIONING -> RUNNING) immediately after start.
        ok, msg = ge.validate_gcp_lab(self.sid, slug)
        self.assertFalse(ok, msg)
        self.assertIn("transitioning", msg)

    def test_resize_requires_instance_stopped_first(self):
        self._login()
        res = ge.apply_action(self.sid, "set_machine_type", {"instance_name": "web01", "machine_type": "e2-standard-2"})
        self.assertFalse(res["ok"])
        self.assertIn("Stop", res["error"])


class GcpLinuxResizeBridgeTests(GcpEngineBase):
    """The master-prompt canonical example: changing an instance's machine
    type in the console changes the vCPU/RAM the SAME session's Linux
    terminal reports."""

    def _shell_for_session(self) -> RHELShell:
        state = RHELOSState(hostname="web01")
        state.session_id = self.sid
        return RHELShell(state=state)

    def test_machine_type_change_changes_nproc_and_free_output(self):
        self._login()
        shell = self._shell_for_session()
        # RHELOSState's own default (unrelated to GCP) — confirms the "before"
        # value is NOT already coincidentally equal to the target machine type,
        # so the assertion below actually proves the bridge fired.
        self.assertEqual(shell.state.cpu_count, 4)
        self.assertEqual(shell.state.mem_mb, 16384)

        ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        ge.apply_action(self.sid, "set_machine_type", {"instance_name": "web01", "machine_type": "e2-standard-2"})
        # Lab Server must refuse while the instance is stopped (real SSH would too).
        blocked = shell.run("nproc")
        self.assertIn("powered off", blocked.lower())

        ge.apply_action(self.sid, "start_instance", {"instance_name": "web01"})
        out = shell.run("nproc").strip()
        self.assertEqual(out, "2")
        self.assertEqual(shell.state.mem_mb, 8192)

    def test_no_pending_resize_leaves_hardware_untouched(self):
        self._login()
        shell = self._shell_for_session()
        before_cpu = shell.state.cpu_count
        shell.run("nproc")
        self.assertEqual(shell.state.cpu_count, before_cpu)


class GcpBridgePowerTests(GcpEngineBase):
    def test_stop_instance_records_power_event_for_bridge_consumers(self):
        self._login()
        ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        self.assertEqual(gb.consume_power(self.sid), "stop")
        self.assertIsNone(gb.consume_power(self.sid))

    def test_create_instance_from_terraform_without_prior_login(self):
        res = ge.apply_action(self.sid, "create_instance", {"name": "tf-web", "machine_type": "e2-standard-2"})
        self.assertTrue(res["ok"], res)
        names = [i["name"] for i in ge.get_state(self.sid)["state"]["instances"]]
        self.assertIn("tf-web", names)
        self.assertIn("web01", names)
        res2 = ge.apply_action(self.sid, "create_instance", {"name": "tf-web"})
        self.assertTrue(res2["ok"])
        self.assertEqual(len([i for i in ge.get_state(self.sid)["state"]["instances"] if i["name"] == "tf-web"]), 1)


class GcpV2FacadeTests(GcpEngineBase):
    def test_seeded_v2_collections(self):
        self._login()
        st = ge.get_state(self.sid)["state"]
        self.assertTrue(st.get("cloud_run_services"))
        self.assertTrue(st.get("pubsub_topics"))
        self.assertTrue(st.get("gke_clusters"))
        self.assertTrue(st.get("cloud_functions"))
        self.assertTrue(st.get("cloud_sql_instances"))
        self.assertTrue(st.get("secrets"))
        self.assertTrue(st.get("armor_policies"))
        self.assertTrue(st.get("spanner_instances"))

    def test_cloud_run_and_pubsub(self):
        self._login()
        self.assertTrue(ge.apply_action(self.sid, "create_cloud_run_service", {"name": "svc-lab"})["ok"])
        self.assertTrue(ge.apply_action(
            self.sid, "update_cloud_run_traffic", {"name": "svc-lab", "traffic_pct": 25},
        )["ok"])
        self.assertTrue(ge.apply_action(self.sid, "create_pubsub_topic", {"name": "lab-topic"})["ok"])
        self.assertTrue(ge.apply_action(
            self.sid, "create_pubsub_subscription", {"topic": "lab-topic", "name": "lab-sub"},
        )["ok"])
        self.assertTrue(ge.apply_action(self.sid, "publish_pubsub", {"topic": "lab-topic"})["ok"])

    def test_gke_sql_secrets(self):
        self._login()
        self.assertTrue(ge.apply_action(self.sid, "create_gke_cluster", {"name": "gke-lab"})["ok"])
        self.assertTrue(ge.apply_action(
            self.sid, "resize_gke_node_pool",
            {"cluster": "gke-lab", "pool": "default-pool", "node_count": 5},
        )["ok"])
        self.assertTrue(ge.apply_action(self.sid, "create_sql_instance", {"name": "sql-lab"})["ok"])
        self.assertTrue(ge.apply_action(
            self.sid, "create_sql_database", {"instance": "sql-lab", "name": "orders"},
        )["ok"])
        self.assertTrue(ge.apply_action(self.sid, "create_secret", {"name": "lab-secret"})["ok"])
        self.assertTrue(ge.apply_action(self.sid, "add_secret_version", {"name": "lab-secret"})["ok"])

