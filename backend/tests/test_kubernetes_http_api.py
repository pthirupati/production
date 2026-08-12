"""Kubernetes HTTP API surface — pods/deployments for curl teaching labs."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import k8s_engine as ke


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "k8s-http-api-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class KubernetesHttpApiTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_list_pods_returns_pod_list(self):
        sid = "k8s-http-pods"
        ke.drop_session(sid)
        cluster = ke.get_state(sid).get("cluster") or {}
        status, body = ke.kubernetes_http_api(
            "https://127.0.0.1:6443/api/v1/pods",
            cluster,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["kind"], "PodList")
        self.assertGreater(len(body["items"]), 0)
        self.assertEqual(body["items"][0]["apiVersion"], "v1")
        self.assertEqual(body["items"][0]["kind"], "Pod")

    def test_namespaced_deployment_list(self):
        sid = "k8s-http-deps"
        ke.drop_session(sid)
        cluster = ke.get_state(sid).get("cluster") or {}
        # Pick a namespace that exists on the seeded cluster.
        ns = (cluster.get("deployments") or [{}])[0].get("namespace") or "default"
        status, body = ke.kubernetes_http_api(
            f"/apis/apps/v1/namespaces/{ns}/deployments",
            cluster,
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["kind"], "DeploymentList")
        self.assertTrue(body["items"])

    def test_missing_pod_is_404(self):
        status, body = ke.kubernetes_http_api(
            "/api/v1/namespaces/default/pods/does-not-exist-xyz",
            {"pods": [], "deployments": []},
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["status"], "Failure")

    def test_apply_action_http_api(self):
        sid = "k8s-http-action"
        ke.drop_session(sid)
        ke.get_state(sid)
        res = ke.apply_action(sid, "k8s_http", {"url": "/api/v1/pods"})
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("status"), 200)
        self.assertEqual(res["body"]["kind"], "PodList")
