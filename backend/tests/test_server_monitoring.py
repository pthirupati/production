"""Tests for the FREE fleet server-monitoring endpoints.

Guarantees:
  * GET /api/admin/monitoring/metrics/ returns 200 + expected host-metric keys
    for a staff admin, and 403 for a non-admin user.
  * GET /api/admin/monitoring/fleet/ always includes the local node and NEVER
    500s — even when a configured peer node is unreachable (it is reported
    offline instead).
  * The local metrics collector never raises and returns the documented keys.
"""

import os
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.adminpanel import cluster_topology
from apps.adminpanel.server_metrics import collect_local_metrics

User = get_user_model()

METRICS_URL = "/api/admin/monitoring/metrics/"
FLEET_URL = "/api/admin/monitoring/fleet/"

# Keys every node payload must expose so the dashboard can always render a card.
EXPECTED_KEYS = {
    "name", "hostname", "ip", "status",
    "cpu_percent", "cpu_count",
    "mem_percent", "mem_used", "mem_total",
    "disk_percent", "disk_used", "disk_total",
    "load_1", "load_5", "load_15",
    "uptime_seconds", "process_count",
}


class NodeMetricsEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="admin-mon", email="admin-mon@test.com",
            password="Pass123!", is_staff=True,
        )
        self.user = User.objects.create_user(
            username="plain-mon", email="plain-mon@test.com", password="Pass123!",
        )

    def test_metrics_returns_200_with_expected_keys_for_admin(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(METRICS_URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body.get("status"), "online")
        self.assertTrue(body.get("is_local"))
        missing = EXPECTED_KEYS - set(body.keys())
        self.assertFalse(missing, f"missing keys: {missing}")

    def test_metrics_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(METRICS_URL)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_metrics_forbidden_for_anonymous(self):
        resp = self.client.get(METRICS_URL)
        self.assertIn(resp.status_code, (401, 403))

    @override_settings(MONITORING_AGENT_TOKEN="secret-agent-token")
    def test_metrics_allows_peer_with_agent_token(self):
        # No logged-in user, but a valid agent token → allowed (peer aggregation).
        resp = self.client.get(METRICS_URL, HTTP_X_MONITORING_TOKEN="secret-agent-token")
        self.assertEqual(resp.status_code, 200, resp.content)

    @override_settings(MONITORING_AGENT_TOKEN="secret-agent-token")
    def test_metrics_rejects_peer_with_wrong_token(self):
        resp = self.client.get(METRICS_URL, HTTP_X_MONITORING_TOKEN="wrong")
        # Denied either as 401 (no session + failed challenge) or 403.
        self.assertIn(resp.status_code, (401, 403), resp.content)


class FleetEndpointTests(TestCase):
    """Exercises the SINGLE-HOST fleet path (local node + MONITORING_SERVERS peers).

    The repo now ships a real four-droplet ``infra/digitalocean/cluster.json``, so
    without forcing single-host mode the fleet view would enumerate the 4 cluster
    nodes instead of "local + peers". These tests guard the single-host aggregation
    and peer-failure handling, so we pin single-host via the documented
    ``CLUSTER_TOPOLOGY_DISABLE`` flag. The 4-droplet cluster path is covered
    separately by the topology-aware view logic.
    """

    def setUp(self):
        self.client = APIClient()
        # Force the single-host topology this suite targets, bypassing the
        # committed four-droplet cluster.json (and the topology lru_cache).
        self._env = mock.patch.dict(os.environ, {"CLUSTER_TOPOLOGY_DISABLE": "1"})
        self._env.start()
        cluster_topology.reset_cache()
        cache.clear()  # fleet payload is cached process-wide (LocMemCache)
        self.addCleanup(self._env.stop)
        self.addCleanup(cluster_topology.reset_cache)
        self.addCleanup(cache.clear)
        self.admin = User.objects.create_user(
            username="admin-fleet", email="admin-fleet@test.com",
            password="Pass123!", is_staff=True,
        )
        self.user = User.objects.create_user(
            username="plain-fleet", email="plain-fleet@test.com", password="Pass123!",
        )

    def test_fleet_includes_local_node(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(FLEET_URL)
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertGreaterEqual(body["total"], 1)
        self.assertGreaterEqual(body["online"], 1)
        self.assertTrue(any(n.get("is_local") for n in body["nodes"]))

    def test_fleet_forbidden_for_non_admin(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(FLEET_URL)
        self.assertEqual(resp.status_code, 403, resp.content)

    @override_settings(
        MONITORING_SERVERS=["dead-node=http://127.0.0.1:9"],  # port 9 = discard, refuses
    )
    def test_fleet_marks_unreachable_peer_offline_without_500(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(FLEET_URL + "?refresh=1")
        # The whole point: a dead peer must NOT crash the endpoint.
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body["total"], 2)
        offline = [n for n in body["nodes"] if n.get("status") == "offline"]
        self.assertEqual(len(offline), 1)
        self.assertEqual(offline[0]["name"], "dead-node")
        self.assertIn("error", offline[0])
        # Local node still reported online alongside the dead peer.
        self.assertTrue(any(n.get("is_local") and n["status"] == "online" for n in body["nodes"]))

    @override_settings(MONITORING_SERVERS=["http://127.0.0.1:9", "bad spec"])
    def test_fleet_handles_multiple_bad_specs_without_500(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(FLEET_URL + "?refresh=1")
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body["total"], 3)  # local + 2 peers
        self.assertEqual(body["offline"], 2)


class CollectorTests(TestCase):
    def test_collector_never_raises_and_has_keys(self):
        data = collect_local_metrics("unit-node")
        self.assertEqual(data["name"], "unit-node")
        self.assertEqual(data["status"], "online")
        missing = EXPECTED_KEYS - set(data.keys())
        self.assertFalse(missing, f"missing keys: {missing}")
