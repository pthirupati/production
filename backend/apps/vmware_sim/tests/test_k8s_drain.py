"""Tests for the K8s engine's wall-clock node-drain + graceful-pod-termination
lifecycle.

A `kubectl drain` cordons the node and evicts its pods, which enter Terminating
and disappear after their grace period; the node then reports drained. The
transitions advance on wall-clock (patched via the engine's ``_now``) so they run
instantly and deterministically. Grading must be unaffected.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import k8s_engine as k8s


class NodeDrainLifecycleTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug="node-maintenance"):
        sid = f"test-k8s-{slug}"
        k8s.drop_session(sid)
        k8s.get_state(sid, slug)
        return sid

    def _node(self, sid, name):
        cluster = k8s.get_state(sid)["cluster"]
        return next(n for n in cluster["nodes"] if n["name"] == name)

    def _pods_on(self, sid, name):
        cluster = k8s.get_state(sid)["cluster"]
        return [p for p in cluster["pods"] if p.get("node") == name]

    def test_drain_marks_pods_terminating_then_removes_them(self):
        sid = self._session()
        base = 1_000_000.0
        with mock.patch.object(k8s, "_now", return_value=base):
            before = self._pods_on(sid, "node2")
            self.assertTrue(before, "node2 should host pods to evict")
            res = k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
            self.assertTrue(res["ok"], res)
            # Immediately after: pods are Terminating, node draining.
            term = [p for p in self._pods_on(sid, "node2") if p["phase"] == "Terminating"]
            self.assertTrue(term)
            self.assertEqual(self._node(sid, "node2")["drain_state"], "draining")

        # After the grace period the evicted pods are gone.
        with mock.patch.object(k8s, "_now", return_value=base + k8s.POD_GRACE_SECONDS + 1):
            remaining = [p for p in self._pods_on(sid, "node2")
                         if p.get("labels", {}).get("k8s-app") != "kube-proxy"]
            self.assertEqual(remaining, [])

        # After the drain window the node reports drained.
        with mock.patch.object(k8s, "_now", return_value=base + k8s.NODE_DRAIN_SECONDS + 1):
            self.assertEqual(self._node(sid, "node2")["drain_state"], "drained")

    def test_drain_cordons_node(self):
        sid = self._session()
        k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
        self.assertTrue(self._node(sid, "node2")["unschedulable"])

    def test_daemonset_pod_not_evicted(self):
        sid = self._session()
        base = 2_000_000.0
        with mock.patch.object(k8s, "_now", return_value=base):
            k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
        with mock.patch.object(k8s, "_now", return_value=base + k8s.NODE_DRAIN_SECONDS + 5):
            kube_proxy = [p for p in self._pods_on(sid, "node2")
                          if p.get("labels", {}).get("k8s-app") == "kube-proxy"]
            self.assertTrue(kube_proxy, "kube-proxy daemonset pod must survive drain")

    def test_repeated_reads_idempotent(self):
        sid = self._session()
        base = 3_000_000.0
        with mock.patch.object(k8s, "_now", return_value=base):
            k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
        with mock.patch.object(k8s, "_now", return_value=base + 2):
            first = len(self._pods_on(sid, "node2"))
            second = len(self._pods_on(sid, "node2"))
            self.assertEqual(first, second)

    def test_uncordon_clears_drain_state(self):
        sid = self._session()
        k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
        k8s.apply_action(sid, "uncordon_node", {"node_name": "node2"})
        node = self._node(sid, "node2")
        self.assertFalse(node["unschedulable"])
        self.assertIsNone(node.get("drain_state"))

    def test_summary_reports_draining_and_terminating(self):
        sid = self._session()
        base = 4_000_000.0
        with mock.patch.object(k8s, "_now", return_value=base):
            k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
            summary = k8s.get_state(sid)["summary"]
        self.assertGreaterEqual(summary["pods_terminating"], 1)
        self.assertEqual(summary["nodes_draining"], 1)


class DrainGradingUnaffectedTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_node_ready_scenario_still_grades(self):
        sid = "k8s-grade-node"
        k8s.drop_session(sid)
        k8s.get_state(sid, "node-notready")
        ok, _ = k8s.validate_k8s_lab(sid, "node-notready")
        self.assertFalse(ok)
        # Fixing node3 (not draining node2) still flips validation to pass.
        k8s.apply_action(sid, "uncordon_node", {"node_name": "node3"})
        ok, msg = k8s.validate_k8s_lab(sid, "node-notready")
        self.assertTrue(ok, msg)

    def test_default_deployment_grading_unaffected_by_drain(self):
        sid = "k8s-grade-dep"
        k8s.drop_session(sid)
        k8s.get_state(sid, "worker-crashloop")
        base = 5_000_000.0
        with mock.patch.object(k8s, "_now", return_value=base):
            # Draining a node does not change deployment.availableReplicas.
            k8s.apply_action(sid, "drain_node", {"node_name": "node2"})
        with mock.patch.object(k8s, "_now", return_value=base + k8s.NODE_DRAIN_SECONDS + 5):
            k8s.apply_action(sid, "scale_deployment",
                             {"deployment": "worker", "replicas": 4})
            ok, msg = k8s.validate_k8s_lab(sid, "worker-crashloop")
            self.assertTrue(ok, msg)
