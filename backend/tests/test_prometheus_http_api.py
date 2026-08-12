"""Prometheus HTTP API surface — wraps eval_promql for curl teaching labs."""

from django.test import SimpleTestCase

from apps.vmware_sim.monitoring_engine import eval_promql, prometheus_http_api


class PrometheusHttpApiTests(SimpleTestCase):
    BROKEN = {
        "targets_down": ["node-2:9100"],
        "no_data_metrics": [],
        "high_cardinality_metric": "http_requests_total",
    }

    def test_query_up_matches_eval_promql(self):
        status, body = prometheus_http_api(
            "http://localhost:9090/api/v1/query?query=up",
            self.BROKEN,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "success")
        direct = eval_promql("up", self.BROKEN)
        self.assertEqual(len(body["data"]["result"]), len(direct["data"]["result"]))

    def test_query_range_returns_matrix(self):
        status, body = prometheus_http_api(
            "/api/v1/query_range?query=up",
            self.BROKEN,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["resultType"], "matrix")
        self.assertTrue(body["data"]["result"])
        self.assertIn("values", body["data"]["result"][0])

    def test_unknown_path_is_404(self):
        status, body = prometheus_http_api("/api/v1/label/job/values", self.BROKEN)
        self.assertEqual(status, 404)
        self.assertEqual(body["status"], "error")
