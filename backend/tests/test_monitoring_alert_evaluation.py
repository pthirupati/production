"""Alert-rule authoring → evaluation → firing loop in the monitoring simulator.

The audit (docs/AUDIT_2026_08_TODO.md:1021) found the loop was open: `add_alert_rule`
stored whatever `state` the payload asked for and `toggle_alert_rule` flipped it by
hand, so a rule's expression was never evaluated. These tests pin the closed loop —
state is derived from `expr` via eval_promql — and pin that closing it did NOT hand
the learner a free pass on grading.
"""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim.monitoring_engine import (
    _duration_seconds,
    apply_action,
    drop_session,
    evaluate_alert_rule,
    get_state,
    refresh_alert_rules,
    validate_monitoring_lab,
)

DOWN = {"targets_down": ["node-2:9100"], "no_data_metrics": [],
        "high_cardinality_metric": None, "panels_no_data": [], "alert_misrouted": False}
HEALTHY = {"targets_down": [], "no_data_metrics": [],
           "high_cardinality_metric": None, "panels_no_data": [], "alert_misrouted": False}


class AlertRuleEvaluationTests(TestCase):
    """evaluate_alert_rule derives state from the rule's own PromQL expression."""

    def test_expr_with_no_samples_is_inactive(self):
        rule = evaluate_alert_rule({"name": "TargetDown", "expr": "up == 0", "for": "0s"}, HEALTHY)
        self.assertEqual(rule["state"], "inactive")
        self.assertEqual(rule["firing_samples"], 0)

    def test_expr_with_samples_and_no_hold_fires(self):
        rule = evaluate_alert_rule({"name": "TargetDown", "expr": "up == 0", "for": "0s"}, DOWN)
        self.assertEqual(rule["state"], "firing")
        self.assertEqual(rule["firing_samples"], 1)

    def test_unmet_for_duration_is_pending_not_firing(self):
        rule = evaluate_alert_rule({"name": "TargetDown", "expr": "up == 0", "for": "5m"}, DOWN)
        self.assertEqual(rule["state"], "pending")

    def test_elapsed_for_duration_promotes_pending_to_firing(self):
        rule = {"name": "TargetDown", "expr": "up == 0", "for": "5m"}
        evaluate_alert_rule(rule, DOWN, t=1_000_000.0)
        self.assertEqual(rule["state"], "pending")
        # Same active_since, clock advanced past the 5m hold.
        evaluate_alert_rule(rule, DOWN, t=1_000_000.0 + 301)
        self.assertEqual(rule["state"], "firing")

    def test_recovery_clears_active_since(self):
        rule = {"name": "TargetDown", "expr": "up == 0", "for": "0s"}
        evaluate_alert_rule(rule, DOWN, t=1_000_000.0)
        self.assertEqual(rule["state"], "firing")
        evaluate_alert_rule(rule, HEALTHY, t=1_000_000.0 + 10)
        self.assertEqual(rule["state"], "inactive")
        self.assertIsNone(rule["active_since"])

    def test_unparseable_expr_is_marked_unhealthy(self):
        rule = evaluate_alert_rule({"name": "Junk", "expr": "!!! not promql", "for": "0s"}, DOWN)
        self.assertEqual(rule["health"], "err")
        self.assertEqual(rule["state"], "inactive")
        self.assertTrue(rule.get("last_error"))

    def test_disabled_rule_never_fires(self):
        rule = evaluate_alert_rule(
            {"name": "TargetDown", "expr": "up == 0", "for": "0s", "enabled": False}, DOWN)
        self.assertEqual(rule["state"], "inactive")

    def test_active_silence_suppresses_but_rule_still_fires(self):
        silences = [{"id": "s1", "state": "active",
                     "matchers": [{"name": "alertname", "value": "TargetDown"}]}]
        rule = evaluate_alert_rule({"name": "TargetDown", "expr": "up == 0", "for": "0s"},
                                   DOWN, silences)
        # Real Alertmanager silences suppress notification, not evaluation.
        self.assertEqual(rule["state"], "firing")
        self.assertTrue(rule["suppressed"])

    def test_expired_silence_does_not_suppress(self):
        silences = [{"id": "s1", "state": "expired",
                     "matchers": [{"name": "alertname", "value": "TargetDown"}]}]
        rule = evaluate_alert_rule({"name": "TargetDown", "expr": "up == 0", "for": "0s"},
                                   DOWN, silences)
        self.assertFalse(rule["suppressed"])

    def test_silence_for_a_different_alert_does_not_suppress(self):
        silences = [{"id": "s1", "state": "active",
                     "matchers": [{"name": "alertname", "value": "SomethingElse"}]}]
        rule = evaluate_alert_rule({"name": "TargetDown", "expr": "up == 0", "for": "0s"},
                                   DOWN, silences)
        self.assertFalse(rule["suppressed"])

    def test_duration_parser(self):
        self.assertEqual(_duration_seconds("5m"), 300.0)
        self.assertEqual(_duration_seconds("0s"), 0.0)
        self.assertEqual(_duration_seconds("2h"), 7200.0)
        self.assertEqual(_duration_seconds("1h30m"), 5400.0)
        self.assertEqual(_duration_seconds("", default=42.0), 42.0)

    def test_refresh_walks_every_rule(self):
        state = {"broken": DOWN, "prometheus": {"alertmanager": {"silences": []}, "alerting_rules": [
            {"name": "A", "expr": "up == 0", "for": "0s"},
            {"name": "B", "expr": "up == 1", "for": "0s"},
        ]}}
        rules = refresh_alert_rules(state)
        self.assertEqual(rules[0]["state"], "firing")
        self.assertEqual(rules[1]["state"], "firing")  # many targets are up
        state["broken"] = HEALTHY
        refresh_alert_rules(state)
        self.assertEqual(state["prometheus"]["alerting_rules"][0]["state"], "inactive")


class AlertRuleActionTests(TestCase):
    """The UI actions feed the same evaluator instead of writing state by hand."""

    SESSION = "alert-eval-sess"

    def setUp(self):
        cache.clear()
        drop_session(self.SESSION)
        self.addCleanup(drop_session, self.SESSION)

    def test_add_alert_rule_ignores_declared_state_and_evaluates(self):
        get_state(self.SESSION, "grafana-target-down-lab")
        res = apply_action(self.SESSION, "add_alert_rule", {
            "name": "MyTargetDown", "expr": "up == 0", "for": "0s", "state": "firing",
        })
        self.assertTrue(res["ok"])
        # Expression matches (node-2 is down in this preset) so it genuinely fires.
        self.assertEqual(res["rule"]["state"], "firing")
        self.assertEqual(res["rule"]["firing_samples"], 1)

    def test_add_alert_rule_cannot_declare_itself_firing(self):
        get_state(self.SESSION, "grafana-datasource-misconfig")
        res = apply_action(self.SESSION, "add_alert_rule", {
            # No target is down in this preset, so the payload's "firing" is a lie.
            "name": "WishfulAlert", "expr": "up == 0", "for": "0s", "state": "firing",
        })
        self.assertTrue(res["ok"])
        self.assertEqual(res["rule"]["state"], "inactive")

    def test_toggle_disables_a_firing_rule_and_re_enable_re_evaluates(self):
        get_state(self.SESSION, "grafana-target-down-lab")
        apply_action(self.SESSION, "add_alert_rule",
                     {"name": "ToggleMe", "expr": "up == 0", "for": "0s"})
        off = apply_action(self.SESSION, "toggle_alert_rule", {"name": "ToggleMe"})
        self.assertFalse(off["rule"]["enabled"])
        self.assertEqual(off["rule"]["state"], "inactive")
        on = apply_action(self.SESSION, "toggle_alert_rule", {"name": "ToggleMe"})
        self.assertTrue(on["rule"]["enabled"])
        self.assertEqual(on["rule"]["state"], "firing")

    def test_toggle_cannot_fire_a_rule_whose_expr_does_not_match(self):
        get_state(self.SESSION, "grafana-datasource-misconfig")
        apply_action(self.SESSION, "add_alert_rule",
                     {"name": "Quiet", "expr": "up == 0", "for": "0s"})
        # Toggling twice returns to enabled; state must still come from the expr.
        apply_action(self.SESSION, "toggle_alert_rule", {"name": "Quiet"})
        on = apply_action(self.SESSION, "toggle_alert_rule", {"name": "Quiet"})
        self.assertEqual(on["rule"]["state"], "inactive")

    def test_get_state_reports_derived_firing_counts(self):
        st = get_state(self.SESSION, "grafana-target-down-lab")
        apply_action(self.SESSION, "add_alert_rule",
                     {"name": "DerivedCount", "expr": "up == 0", "for": "0s"})
        st = get_state(self.SESSION, "grafana-target-down-lab")
        names = {r["name"]: r for r in st["prometheus"]["alerting_rules"]}
        self.assertEqual(names["DerivedCount"]["state"], "firing")
        self.assertGreaterEqual(st["summary"]["alerting_rules_firing"], 1)

    def test_silence_marks_the_matching_rule_suppressed(self):
        get_state(self.SESSION, "grafana-target-down-lab")
        apply_action(self.SESSION, "add_alert_rule",
                     {"name": "Noisy", "expr": "up == 0", "for": "0s"})
        apply_action(self.SESSION, "silence_alert", {
            "matchers": [{"name": "alertname", "value": "Noisy", "isRegex": False}],
        })
        st = get_state(self.SESSION, "grafana-target-down-lab")
        rule = next(r for r in st["prometheus"]["alerting_rules"] if r["name"] == "Noisy")
        self.assertTrue(rule["suppressed"])
        self.assertEqual(rule["state"], "firing")


class AlertEvaluationDoesNotWeakenGradingTests(TestCase):
    """Guard the HIGH silent-grading risk called out in the audit: switching
    evaluation on must not let an untouched session auto-pass validation."""

    SESSION = "alert-eval-grading"

    def setUp(self):
        cache.clear()
        drop_session(self.SESSION)
        self.addCleanup(drop_session, self.SESSION)

    def test_fresh_alert_flap_scenario_still_fails_validation(self):
        slug = "prometheus-alert-flap-lab"
        get_state(self.SESSION, slug)
        # Force every rule to be evaluated first — this is the path that could
        # have silently cleared the fault if grading keyed off rule state.
        get_state(self.SESSION, slug)
        ok, reason = validate_monitoring_lab(self.SESSION, slug)
        self.assertFalse(ok, reason)

    def test_silencing_every_alert_does_not_pass_the_lab(self):
        slug = "prometheus-alert-silence-lab"
        get_state(self.SESSION, slug)
        for name in ("TargetDown", "HighErrorRate"):
            apply_action(self.SESSION, "silence_alert", {
                "matchers": [{"name": "alertname", "value": name, "isRegex": False}],
            })
        ok, reason = validate_monitoring_lab(self.SESSION, slug)
        self.assertFalse(ok, reason)

    def test_fresh_target_down_scenario_still_fails_validation(self):
        slug = "prometheus-target-down-lab"
        get_state(self.SESSION, slug)
        ok, reason = validate_monitoring_lab(self.SESSION, slug)
        self.assertFalse(ok, reason)
