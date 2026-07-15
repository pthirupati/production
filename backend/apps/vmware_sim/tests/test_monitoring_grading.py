"""Fail-CLOSED grading tests for the monitoring (Grafana/Prometheus) engine.

The audit found the monitoring simulator was routed in simulation_provisioner
but had NO validator, so "Check" fell through to the generic path and could
fail-open on a fresh observability world. These tests pin the new
`validate_monitoring_lab`:

  * FAILS on a freshly-seeded scenario (the planted datasource/target/alert/
    cardinality/recording-rule fault is still present).
  * PASSES only after the learner's repair action clears the fault (add a
    datasource, bring a target back up, mark the terminal fix applied, etc.).

Sessions use plain string ids so the engine runs purely on the Django cache
(the LabSession host-merge is a best-effort no-op without a DB row).
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import monitoring_engine as me


class MonitoringGradingTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _fresh(self, slug):
        sid = f"test-mon-{slug}"
        me.drop_session(sid)
        me.get_state(sid, slug)  # seeds the scenario
        return sid

    # ---- datasource misconfig --------------------------------------------
    def test_datasource_scenario_fails_then_passes(self):
        sid = self._fresh("monitoring-datasource-misconfig")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-datasource-misconfig")
        self.assertFalse(ok, f"should fail before fix, got: {reason}")

        # Adding a healthy Prometheus datasource + reloading clears no-data.
        me.apply_action(sid, "add_datasource", {"name": "Prometheus-Fixed", "type": "prometheus",
                                                 "url": "http://prometheus:9090"})
        me.apply_action(sid, "reload_config", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-datasource-misconfig")
        self.assertTrue(ok, f"should pass after adding datasource + reload, got: {reason}")

    # ---- target down ------------------------------------------------------
    def test_target_down_fails_then_passes(self):
        sid = self._fresh("monitoring-target-down")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-target-down")
        self.assertFalse(ok, f"should fail while a target is down, got: {reason}")

        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-target-down")
        self.assertTrue(ok, f"should pass after target restored, got: {reason}")

    def test_target_down_removing_dead_target_passes(self):
        # Deleting the dead scrape target (decommissioned node) also clears it.
        sid = self._fresh("monitoring-node-exporter-down")
        ok, _ = me.validate_monitoring_lab(sid, "monitoring-node-exporter-down")
        self.assertFalse(ok)
        me.apply_action(sid, "delete_scrape_target", {"instance": "node-2:9100"})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-node-exporter-down")
        self.assertTrue(ok, f"should pass after removing dead target, got: {reason}")

    # ---- high cardinality -------------------------------------------------
    def test_high_cardinality_fails_then_passes(self):
        sid = self._fresh("monitoring-high-cardinality")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-high-cardinality")
        self.assertFalse(ok, f"should fail while cardinality is high, got: {reason}")

        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-high-cardinality")
        self.assertTrue(ok, f"should pass after relieving cardinality, got: {reason}")

    # ---- alert misrouting / contact point --------------------------------
    def test_contact_point_fails_then_passes(self):
        sid = self._fresh("monitoring-alert-contact-point")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-alert-contact-point")
        self.assertFalse(ok, f"should fail while contact point broken, got: {reason}")

        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-alert-contact-point")
        self.assertTrue(ok, f"should pass after fixing alert routing, got: {reason}")

    # ---- recording rule ---------------------------------------------------
    def test_recording_rule_fails_then_passes(self):
        sid = self._fresh("monitoring-recording-rule-broken")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-recording-rule-broken")
        self.assertFalse(ok, f"should fail while recording rule broken, got: {reason}")

        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-recording-rule-broken")
        self.assertTrue(ok, f"should pass after fix, got: {reason}")

    # ---- remote write / federation ---------------------------------------
    def test_remote_write_fails_then_passes(self):
        sid = self._fresh("monitoring-remote-write-down")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-remote-write-down")
        self.assertFalse(ok, f"should fail while remote_write down, got: {reason}")
        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-remote-write-down")
        self.assertTrue(ok, reason)

    def test_federation_fails_then_passes(self):
        sid = self._fresh("monitoring-federation-misconfig")
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-federation-misconfig")
        self.assertFalse(ok, f"should fail while federation misconfigured, got: {reason}")
        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-federation-misconfig")
        self.assertTrue(ok, reason)

    # ---- generic / catch-all fault ---------------------------------------
    def test_generic_scenario_fails_until_fix_applied(self):
        # A slug we don't specifically key on still seeds a generic fault summary,
        # so grading must fail closed until the learner marks the fix applied.
        sid = self._fresh("monitoring-investigate-stack")
        ok, _ = me.validate_monitoring_lab(sid, "monitoring-investigate-stack")
        self.assertFalse(ok, "generic monitoring scenario must fail closed on a fresh world")
        me.apply_action(sid, "mark_fix_applied", {})
        ok, reason = me.validate_monitoring_lab(sid, "monitoring-investigate-stack")
        self.assertTrue(ok, reason)

    def test_no_session_fails_closed(self):
        ok, reason = me.validate_monitoring_lab("nonexistent-mon-session", "monitoring-target-down")
        self.assertFalse(ok)
        self.assertIn("session", reason.lower())
