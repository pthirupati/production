"""Tests for the Grafana + Prometheus monitoring simulator engine."""
from django.test import TestCase

from apps.vmware_sim.monitoring_engine import (
    apply_action,
    drop_session,
    eval_promql,
    get_state,
)


class PromQLEvaluatorTests(TestCase):
    """The teaching PromQL evaluator handles selectors, aggregations, functions,
    and scalar/comparison binary ops without erroring on common dashboard exprs."""

    BROKEN = {"targets_down": ["node-2:9100"], "no_data_metrics": [],
              "high_cardinality_metric": "http_requests_total"}

    def _rows(self, q, broken=None):
        res = eval_promql(q, broken if broken is not None else self.BROKEN)
        self.assertEqual(res["status"], "success", f"{q} -> {res}")
        return res["data"]["result"]

    def test_up_returns_series_with_down_target(self):
        rows = self._rows("up")
        self.assertTrue(len(rows) >= 6)
        downs = [r for r in rows if r["value"][1] == "0"]
        self.assertEqual([r["metric"]["instance"] for r in downs], ["node-2:9100"])

    def test_comparison_filter_keeps_only_matching(self):
        rows = self._rows("up == 0")
        self.assertTrue(all(r["value"][1] == "0" for r in rows))
        self.assertEqual(len(rows), 1)

    def test_aggregation_by_job(self):
        rows = self._rows("sum by(job)(up)")
        self.assertTrue(len(rows) >= 3)
        self.assertTrue(all("job" in r["metric"] for r in rows))

    def test_scalar_arithmetic_does_not_error(self):
        # 100 - (avg by(instance)(rate(...)) * 100) — previously errored.
        rows = self._rows('100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
        self.assertTrue(len(rows) >= 1)

    def test_division_ratio(self):
        rows = self._rows('sum(rate(http_requests_total{code="500"}[5m])) / sum(rate(http_requests_total[5m]))')
        self.assertEqual(len(rows), 1)
        self.assertTrue(0.0 <= float(rows[0]["value"][1]) <= 1.0)

    def test_vector_vector_division_ignores_name(self):
        rows = self._rows('node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100')
        self.assertTrue(len(rows) >= 1)

    def test_no_data_metric_returns_empty(self):
        rows = self._rows("node_memory_MemAvailable_bytes",
                          {"no_data_metrics": ["node_memory_MemAvailable_bytes"]})
        self.assertEqual(rows, [])

    def test_high_cardinality_explodes_series(self):
        rows = self._rows("http_requests_total")
        # The unbounded user_id label adds many extra series.
        self.assertTrue(len(rows) > 10)

    def test_empty_query_is_error(self):
        res = eval_promql("", self.BROKEN)
        self.assertEqual(res["status"], "error")


class MonitoringStateTests(TestCase):
    """get_state seeds a broken state per scenario; actions are non-grading."""

    def tearDown(self):
        drop_session("mon-test-1")
        drop_session("mon-test-2")

    def test_datasource_scenario_marks_failure(self):
        st = get_state("mon-test-1", "grafana-datasource-misconfigured-no-data")
        self.assertEqual(st["summary"]["datasources_failing"], 1)
        self.assertTrue(st["broken"]["panels_no_data"])
        self.assertIn("No data", st["broken"]["summary"])

    def test_target_down_scenario(self):
        st = get_state("mon-test-2", "prometheus-target-down-scrape-refused")
        self.assertTrue(st["summary"]["targets_down"] >= 1)

    def test_query_action_returns_result(self):
        get_state("mon-test-1", "prometheus-target-down-scrape-refused")
        res = apply_action("mon-test-1", "query", {"expr": "sum(up)"})
        self.assertTrue(res["ok"])
        self.assertEqual(res["result"]["status"], "success")

    def test_unknown_action_fails(self):
        get_state("mon-test-1", "grafana-datasource-misconfigured-no-data")
        res = apply_action("mon-test-1", "frobnicate", {})
        self.assertFalse(res["ok"])

    def test_action_on_missing_session(self):
        res = apply_action("no-such-session", "query", {"expr": "up"})
        self.assertFalse(res["ok"])
