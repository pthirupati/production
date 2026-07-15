"""End-to-end tests for the two NEW cross-technology bridge chains.

These exercise the shared, session-keyed world-state bridge
(apps.labs.provisioner.simulation.vmware_bridge) exactly the way the existing
VMware<->Linux disk/NIC chains do: an action on engine A records to the bridge,
and engine B reads it back so its state reflects the cross-tool event. Both
chains are FAIL-CLOSED — engine B shows nothing until engine A has actually
acted for that session.

Chain 1  ANSIBLE (AWX) -> LINUX
  A service-configuring AWX job template that launches to success records the
  intended end state (record_ansible_result). The Linux terminal for the same
  session reveals it (RHELOSState.reveal_ansible_services), so
  `systemctl is-active <svc>` reports `active` and the config file is present —
  but only AFTER the playbook ran.

Chain 2  WORKLOAD -> MONITORING
  A running Linux service is published as a scrape target
  (RHELOSState.publish_workload_to_monitoring -> record_workload). The
  monitoring engine reads it so PromQL `up{...}` and the Prometheus target list
  reflect the real workload — up==1 while running, up==0 once stopped, and no
  series at all until it is published.
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import awx_engine as ae
from apps.vmware_sim import monitoring_engine as me
from apps.labs.provisioner.simulation import vmware_bridge as vb
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell


class AnsibleToLinuxChainTests(TestCase):
    """Chain 1: AWX job-template success -> Linux service revealed."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _linux(self, session_id, hostname="web-prod-01"):
        st = RHELOSState(hostname=hostname)
        st.session_id = session_id
        return st, RHELShell(state=st)

    def _launch_service_template(self, session_id, name="Configure Nginx", slug="awx-launch-nginx"):
        ae.get_state(session_id, slug)
        ae.apply_action(session_id, "login", {})
        ae.apply_action(session_id, "create_template", {"name": name})
        tid = next(t["id"] for t in ae.get_state(session_id)["inventory"]["job_templates"]
                   if t["name"] == name)
        return ae.apply_action(session_id, "launch_template", {"template_id": tid})

    def test_failclosed_before_playbook_runs(self):
        # No AWX job has run -> the bridge is empty and the guest sees nothing.
        sid = "chain1-failclosed"
        st, sh = self._linux(sid)
        self.assertFalse(vb.has_pending_ansible(sid))
        self.assertEqual(sh.run("systemctl is-active nginx"), "inactive")
        self.assertEqual(st.last_exit_code, 3)
        self.assertFalse(st.is_package_installed("nginx"))
        self.assertFalse(st.file_exists("/etc/nginx/nginx.conf"))
        # A reveal with nothing pending is a no-op that changes nothing.
        self.assertEqual(st.reveal_ansible_services(), [])
        self.assertEqual(sh.run("systemctl is-active nginx"), "inactive")

    def test_launch_records_ansible_result_on_bridge(self):
        sid = "chain1-records"
        res = self._launch_service_template(sid)
        self.assertTrue(res["ok"])
        pending = vb.pending_ansible(sid)
        self.assertEqual(len(pending), 1)
        entry = pending[0]
        self.assertEqual(entry["service"], "nginx")
        self.assertTrue(entry["installed"])
        self.assertTrue(entry["started"])
        self.assertEqual(entry["config_path"], "/etc/nginx/nginx.conf")

    def test_terminal_reveals_service_after_playbook(self):
        # Full chain: AWX launch -> Linux reveal -> systemctl shows active.
        sid = "chain1-e2e"
        st, sh = self._linux(sid)
        self._launch_service_template(sid)

        revealed = st.reveal_ansible_services()
        self.assertEqual(revealed, ["nginx"])

        self.assertEqual(sh.run("systemctl is-active nginx"), "active")
        self.assertEqual(st.last_exit_code, 0)
        self.assertEqual(sh.run("systemctl is-enabled nginx"), "enabled")
        self.assertTrue(st.is_package_installed("nginx"))
        self.assertTrue(st.file_exists("/etc/nginx/nginx.conf"))
        # Draining is one-shot: a second reveal returns nothing new.
        self.assertEqual(st.reveal_ansible_services(), [])
        # ...but the service stays active (state persisted on the guest).
        self.assertEqual(sh.run("systemctl is-active nginx"), "active")

    def test_explicit_service_payload(self):
        # A scenario can name the service explicitly in the launch payload even
        # when the template name carries no known token.
        sid = "chain1-explicit"
        st, sh = self._linux(sid)
        ae.get_state(sid, "awx-config-service")
        ae.apply_action(sid, "login", {})
        ae.apply_action(sid, "launch_template",
                        {"template_id": 12, "service": "httpd"})
        self.assertEqual(st.reveal_ansible_services(), ["httpd"])
        self.assertEqual(sh.run("systemctl is-active httpd"), "active")

    def test_non_service_template_records_nothing(self):
        # The seeded "Patch Linux"/"Deploy App" templates do not configure a
        # service, so launching them must NOT arm the chain (stays fail-closed).
        sid = "chain1-noservice"
        st, sh = self._linux(sid)
        ae.get_state(sid, "awx-patch")
        ae.apply_action(sid, "login", {})
        ae.apply_action(sid, "launch_template", {"template_id": 10})  # Patch Linux
        self.assertFalse(vb.has_pending_ansible(sid))
        self.assertEqual(st.reveal_ansible_services(), [])

    def test_awx_grading_unchanged_by_chain(self):
        # The bridge write is additive: validate_awx_lab still fails before the
        # launch and passes after, exactly as before.
        sid = "chain1-grading"
        ae.get_state(sid, "awx-launch-job")
        ae.apply_action(sid, "login", {})
        ok, _ = ae.validate_awx_lab(sid, "awx-launch-job")
        self.assertFalse(ok)
        ae.apply_action(sid, "launch_template", {"template_id": 11, "service": "nginx"})
        ok, msg = ae.validate_awx_lab(sid, "awx-launch-job")
        self.assertTrue(ok, msg)


class WorkloadToMonitoringChainTests(TestCase):
    """Chain 2: running workload -> Prometheus scrape target / `up` series."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _up(self, session_id, expr='up{job="webapp"}'):
        res = me.apply_action(session_id, "query", {"expr": expr})
        return res["result"]["data"]["result"]

    def _linux(self, session_id, hostname="app-01"):
        st = RHELOSState(hostname=hostname)
        st.session_id = session_id
        return st, RHELShell(state=st)

    def test_failclosed_no_workload_no_target(self):
        # Fresh monitoring session -> no workload target, `up{job=webapp}` empty.
        sid = "chain2-failclosed"
        me.get_state(sid, "monitoring-target-down")
        self.assertEqual(self._up(sid), [])
        targets = me.get_state(sid)["prometheus"]["targets"]
        self.assertFalse(any("app-01" in str(t) for t in targets))

    def test_running_service_surfaces_up_and_target(self):
        # Full chain: start service -> publish -> monitoring shows up==1 + target.
        sid = "chain2-e2e"
        me.get_state(sid, "monitoring-target-down")
        st, sh = self._linux(sid)
        sh.run("dnf install -y nginx")
        sh.run("systemctl start nginx")
        self.assertTrue(st.publish_workload_to_monitoring("nginx", port=8080, job="webapp"))

        rows = self._up(sid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["metric"]["job"], "webapp")
        self.assertEqual(rows[0]["metric"]["instance"], "app-01:8080")
        self.assertEqual(rows[0]["value"][1], "1")

        targets = me.get_state(sid)["prometheus"]["targets"]
        tgt = next(t for t in targets
                   if (t.get("instance") or "").startswith("app-01"))
        self.assertEqual(tgt["health"], "up")
        self.assertEqual(tgt["source"], "workload-bridge")

    def test_stopped_service_scrapes_down(self):
        # A stopped service must scrape DOWN (up==0), never a fabricated 1.
        sid = "chain2-down"
        me.get_state(sid, "monitoring-target-down")
        st, sh = self._linux(sid)
        sh.run("dnf install -y nginx")
        sh.run("systemctl start nginx")
        st.publish_workload_to_monitoring("nginx", port=8080, job="webapp")
        self.assertEqual(self._up(sid)[0]["value"][1], "1")

        sh.run("systemctl stop nginx")
        st.publish_workload_to_monitoring("nginx", port=8080, job="webapp")
        rows = self._up(sid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"][1], "0")
        targets = me.get_state(sid)["prometheus"]["targets"]
        tgt = next(t for t in targets
                   if (t.get("instance") or "").startswith("app-01"))
        self.assertEqual(tgt["health"], "down")

    def test_unknown_unit_not_published(self):
        # Publishing a service that does not exist on the box is a no-op (no
        # target invented) — the fail-closed guard.
        sid = "chain2-unknown"
        me.get_state(sid, "monitoring-target-down")
        st, _ = self._linux(sid)
        self.assertFalse(st.publish_workload_to_monitoring("does-not-exist"))
        self.assertEqual(vb.workloads(sid), [])
        self.assertEqual(self._up(sid), [])

    def test_removed_workload_disappears_from_up(self):
        sid = "chain2-remove"
        me.get_state(sid, "monitoring-target-down")
        st, sh = self._linux(sid)
        sh.run("dnf install -y nginx")
        sh.run("systemctl start nginx")
        st.publish_workload_to_monitoring("nginx", port=8080, job="webapp")
        self.assertEqual(len(self._up(sid)), 1)
        vb.remove_workload(sid, "nginx")
        self.assertEqual(self._up(sid), [])

    def test_monitoring_grading_unchanged_by_chain(self):
        # The workload bridge is additive and must not affect validation of an
        # unrelated monitoring scenario (still fail-closed on the seeded fault).
        sid = "chain2-grading"
        me.get_state(sid, "monitoring-target-down")
        st, sh = self._linux(sid)
        sh.run("dnf install -y nginx")
        sh.run("systemctl start nginx")
        st.publish_workload_to_monitoring("nginx", port=8080, job="webapp")
        ok, _ = me.validate_monitoring_lab(sid, "monitoring-target-down")
        self.assertFalse(ok)  # seeded node-2 target still DOWN


class BridgeSessionIsolationTests(TestCase):
    """Both chains are session-keyed and multi-worker safe (Django cache)."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_ansible_result_isolated_per_session(self):
        vb.record_ansible_result("sess-A", {"service": "nginx"})
        self.assertTrue(vb.has_pending_ansible("sess-A"))
        self.assertFalse(vb.has_pending_ansible("sess-B"))
        # Consuming A does not touch B.
        self.assertEqual([e["service"] for e in vb.consume_ansible_results("sess-A")], ["nginx"])
        self.assertEqual(vb.consume_ansible_results("sess-B"), [])

    def test_workload_isolated_per_session(self):
        vb.record_workload("sess-A", {"name": "api", "up": True})
        self.assertEqual([w["name"] for w in vb.workloads("sess-A")], ["api"])
        self.assertEqual(vb.workloads("sess-B"), [])
