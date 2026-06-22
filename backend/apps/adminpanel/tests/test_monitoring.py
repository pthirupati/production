"""Tests for the admin fleet/server-monitoring + container-list endpoints.

Locks in the behaviour that regressed when the platform moved to the 4-droplet
cluster:

  * ``/api/admin/monitoring/fleet/`` enumerates ALL configured nodes (the four
    droplets: edge / app / data / labs), attaches LIVE host metrics to the node
    serving the request — even when the host can only be identified by its
    cluster role (``MONITORING_NODE_NAME``) because it runs in a container whose
    hostname/IP do not appear in cluster.json.
  * ``/api/admin/monitoring/containers/`` lists BOTH system containers (read from
    the local Docker daemon) AND lab containers (labs engine), and synthesises
    ``remote`` entries for expected system services that live on other nodes —
    instead of showing only the labs engine's containers.
  * Both endpoints are admin-only.

Docker and the cluster topology are mocked so the tests are hermetic (CI has no
Docker daemon and no real cluster.json).
"""

from __future__ import annotations

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.adminpanel import cluster_topology
from apps.adminpanel.views import AdminMonitoringContainersView

User = get_user_model()


# ─── Fakes ──────────────────────────────────────────────────────────────────--

class _FakeImage:
    def __init__(self, tags):
        self.tags = tags
        self.id = "sha256:deadbeef"


class _FakeContainer:
    def __init__(self, cid, name, status="running", labels=None, image_tags=None):
        self.id = cid
        self.short_id = cid[:12]
        self.name = name
        self.status = status
        self.labels = labels or {}
        self.image = _FakeImage(image_tags or ["fixitlab/img:latest"])
        self.attrs = {
            "Created": "2026-06-22T00:00:00Z",
            "RestartCount": 0,
            "State": {"Status": status, "StartedAt": "2026-06-22T00:00:00Z", "ExitCode": 0},
        }

    def stats(self, stream=False):
        return {
            "cpu_stats": {"cpu_usage": {"total_usage": 1_000_000}},
            "memory_stats": {"usage": 50 * 1024 * 1024, "limit": 512 * 1024 * 1024,
                             "stats": {"cache": 0}},
        }

    def logs(self, **kwargs):
        return b"2026-06-22T00:00:00Z line one\n2026-06-22T00:00:01Z line two\n"


class _FakeContainers:
    def __init__(self, containers):
        self._containers = containers

    def list(self, all=False, filters=None):  # noqa: A002 - mirror docker API
        if filters and "label" in filters:
            label = filters["label"]
            return [c for c in self._containers if label in (c.labels or {})]
        return list(self._containers)

    def get(self, cid):
        for c in self._containers:
            if c.id == cid or c.short_id == cid or c.name == cid:
                return c
        raise KeyError(cid)


class _FakeClient:
    def __init__(self, containers):
        self.containers = _FakeContainers(containers)

    def ping(self):
        return True


# Local daemon (D2 app node): its own system containers.
_LOCAL_CONTAINERS = [
    _FakeContainer("aaaa1111", "fixitlab-backend-1"),
    _FakeContainer("bbbb2222", "fixitlab_redis"),
]
# Labs engine (D4): ephemeral lab containers.
_LAB_CONTAINERS = [
    _FakeContainer("cccc3333", "fixitlab_lab_abc",
                   labels={"fixitlab.session_id": "abc", "fixitlab.scenario": "linux-1"}),
]

_FOUR_NODE_TOPOLOGY = {
    "topology": "four-droplet",
    "is_cluster": True,
    "source": "test",
    "nodes": [
        {"key": "edge", "name": "fixitlab-edge", "role": "edge", "public": True,
         "public_ipv4": "139.59.38.209", "private_ipv4": "10.122.16.2",
         "ip": "10.122.16.2", "services": ["gateway", "redis", "vault"], "droplet_id": "1"},
        {"key": "app", "name": "fixitlab-app", "role": "app", "public": False,
         "public_ipv4": None, "private_ipv4": "10.122.16.3",
         "ip": "10.122.16.3", "services": ["backend", "celery_worker"], "droplet_id": "2"},
        {"key": "data", "name": "fixitlab-db", "role": "data", "public": False,
         "public_ipv4": None, "private_ipv4": "10.122.16.4",
         "ip": "10.122.16.4", "services": ["database", "pgbouncer"], "droplet_id": "3"},
        {"key": "labs", "name": "fixitlab-labs", "role": "labs", "public": False,
         "public_ipv4": None, "private_ipv4": "10.122.16.5",
         "ip": "10.122.16.5", "services": ["docker-engine"], "droplet_id": "4"},
    ],
    "meta": {"region": "blr1", "domain": "fixitlab.in"},
}


def _patch_topology():
    """Force the 4-droplet topology regardless of the host's cluster.json."""
    return mock.patch.object(cluster_topology, "load_topology", return_value=_FOUR_NODE_TOPOLOGY)


def _patch_engines():
    """Mock the two Docker engines the container view reads."""
    return (
        mock.patch.object(AdminMonitoringContainersView, "_local_client",
                          staticmethod(lambda: _FakeClient(_LOCAL_CONTAINERS))),
        mock.patch.object(AdminMonitoringContainersView, "_labs_client",
                          staticmethod(lambda: _FakeClient(_LAB_CONTAINERS))),
    )


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user(
            username="admin", email="admin@fixitlab.in", password="x", is_staff=True
        )
        self.user = User.objects.create_user(
            username="joe", email="joe@fixitlab.in", password="x"
        )
        self.client = APIClient()

    def tearDown(self):
        cache.clear()


# ─── Auth ──────────────────────────────────────────────────────────────────--

class MonitoringAuthTests(_Base):
    URLS = [
        "/api/admin/monitoring/fleet/",
        "/api/admin/monitoring/metrics/",
        "/api/admin/monitoring/containers/",
    ]

    def test_anonymous_denied(self):
        for url in self.URLS:
            resp = self.client.get(url)
            self.assertIn(resp.status_code, (401, 403), f"{url} should reject anon")

    def test_non_staff_denied(self):
        self.client.force_authenticate(self.user)
        for url in self.URLS:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 403, f"{url} should reject non-staff")


# ─── Fleet (4 droplets + live local metrics) ──────────────────────────────────

class FleetMonitoringTests(_Base):
    def test_fleet_lists_all_four_nodes(self):
        self.client.force_authenticate(self.admin)
        with _patch_topology(), \
                mock.patch.object(cluster_topology, "local_node_identity", return_value={}):
            resp = self.client.get("/api/admin/monitoring/fleet/?refresh=1")

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["is_cluster"])
        self.assertEqual(data["total"], 4)
        roles = {n["role"] for n in data["nodes"]}
        self.assertEqual(roles, {"edge", "app", "data", "labs"})
        # Every node card carries topology metadata so the UI can render it.
        for node in data["nodes"]:
            self.assertIn("role", node)
            self.assertIn("ip", node)
            self.assertIn("status", node)
            self.assertIn("services", node)

    def test_local_node_resolved_by_role_gets_live_metrics(self):
        """The regression: the containerised host can't match cluster.json by
        hostname/IP, so the local node must be resolved via MONITORING_NODE_NAME
        (= the cluster role) and receive live host metrics. Without the fix every
        node showed ``unknown`` with no metrics."""
        self.client.force_authenticate(self.admin)
        fake_metrics = {
            "name": "fixitlab-app", "status": "online", "cpu_percent": 12.5,
            "mem_percent": 40.0, "disk_percent": 22.0, "cpu_count": 2,
            "mem_total": 8 * 1024**3, "uptime_seconds": 3600, "process_count": 120,
        }
        with self.settings(MONITORING_NODE_NAME="app"), \
                _patch_topology(), \
                mock.patch.object(cluster_topology, "local_node_identity", return_value={}), \
                mock.patch("apps.adminpanel.server_metrics.collect_local_metrics",
                           return_value=dict(fake_metrics)):
            resp = self.client.get("/api/admin/monitoring/fleet/?refresh=1")

        data = resp.json()
        app_node = next(n for n in data["nodes"] if n["role"] == "app")
        self.assertEqual(app_node["status"], "online")
        self.assertTrue(app_node["is_local"])
        self.assertEqual(app_node["cpu_percent"], 12.5)
        self.assertEqual(app_node["mem_percent"], 40.0)
        self.assertGreaterEqual(data["online"], 1)
        # Topology metadata stays authoritative even after live metrics merge in.
        self.assertEqual(app_node["ip"], "10.122.16.3")

    def test_node_metrics_endpoint_shape(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get("/api/admin/monitoring/metrics/?refresh=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Never 500s; always returns a renderable card with these keys.
        for key in ("name", "status", "cpu_percent", "mem_percent", "disk_percent"):
            self.assertIn(key, data)


# ─── Container list (system + lab + remote synthesis) ──────────────────────────

class MonitoringContainersTests(_Base):
    def _get(self, qs=""):
        self.client.force_authenticate(self.admin)
        local_p, labs_p = _patch_engines()
        with _patch_topology(), local_p, labs_p, \
                mock.patch.object(cluster_topology, "local_node_identity",
                                  return_value=_FOUR_NODE_TOPOLOGY["nodes"][1]):  # app node
            return self.client.get(f"/api/admin/monitoring/containers/{qs}")

    def test_lists_system_and_lab_containers(self):
        resp = self._get("?refresh=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        names = {c["name"] for c in data["containers"]}
        # System containers from the LOCAL daemon.
        self.assertIn("fixitlab-backend-1", names)
        self.assertIn("fixitlab_redis", names)
        # Lab container from the LABS engine.
        self.assertIn("fixitlab_lab_abc", names)
        self.assertGreaterEqual(data["system_count"], 2)
        self.assertEqual(data["lab_count"], 1)
        self.assertTrue(data["is_cluster"])

    def test_synthesises_remote_system_services(self):
        """Services that live on OTHER nodes (gateway/vault on edge, pgbouncer on
        the data node) are listed as ``remote`` rather than silently omitted."""
        resp = self._get("?refresh=1")
        data = resp.json()
        remote = {c["name"]: c for c in data["containers"] if c.get("location") == "remote"}
        # vault + gateway live on edge; pgbouncer on data — none run on the app node.
        self.assertIn("vault", remote)
        self.assertIn("pgbouncer", remote)
        self.assertEqual(remote["pgbouncer"]["node_name"], "fixitlab-db")
        self.assertEqual(remote["vault"]["status"], "remote")
        self.assertGreaterEqual(data["remote_count"], 1)

    def test_node_scope_metadata(self):
        resp = self._get("?refresh=1")
        data = resp.json()
        self.assertEqual(len(data["nodes"]), 4)
        labs_meta = next(n for n in data["nodes"] if n["role"] == "labs")
        # Lab containers ARE reachable (labs engine), so labs node is available.
        self.assertTrue(labs_meta["containers_available"])

    def test_kind_filter(self):
        resp = self._get("?kind=lab&refresh=1")
        data = resp.json()
        self.assertTrue(all(c["kind"] == "lab" for c in data["containers"]))
        self.assertEqual(data["lab_count"], 1)


# ─── Graceful degradation: local socket unreadable must NOT hard-fail ──────────

class MonitoringDegradationTests(_Base):
    """The container view must return partial data (HTTP 200), never a 500/503,
    when the LOCAL Docker socket is unreadable — e.g. a non-root backend that is
    not in the host docker group raises PermissionError opening the socket, or
    the socket is simply not mounted. The frontend renders "Could not load
    containers" on ANY non-2xx, so degradation here is what keeps the page alive.
    """

    def _get_with_local(self, local_client_factory, labs_containers=None):
        self.client.force_authenticate(self.admin)
        labs = _FakeClient(labs_containers if labs_containers is not None else _LAB_CONTAINERS)
        with _patch_topology(), \
                mock.patch.object(AdminMonitoringContainersView, "_local_client",
                                  classmethod(lambda cls: local_client_factory(cls))), \
                mock.patch.object(AdminMonitoringContainersView, "_labs_client",
                                  staticmethod(lambda: labs)), \
                mock.patch.object(cluster_topology, "local_node_identity",
                                  return_value=_FOUR_NODE_TOPOLOGY["nodes"][1]):  # app node
            return self.client.get("/api/admin/monitoring/containers/?refresh=1")

    def test_permission_error_on_local_socket_returns_partial_200(self):
        """A PermissionError opening the local socket (the classic non-root
        backend / `:ro` mount case) degrades to 200 with the labs containers +
        synthesized system rows — it must never bubble up as a 500."""
        def boom(cls):
            cls._last_local_error = "permission denied on unix:///var/run/docker.sock"
            return None  # _local_client catches PermissionError and returns None

        resp = self._get_with_local(boom)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        # Labs containers still listed (labs engine reachable).
        names = {c["name"] for c in data["containers"]}
        self.assertIn("fixitlab_lab_abc", names)
        # Per-engine status surfaces the local failure for the UI's small note.
        self.assertFalse(data["local_engine"]["available"])
        self.assertIn("permission", data["local_engine"]["error"].lower())
        # Expected system services are synthesized (so the grid is never blank):
        # local-node services as "unknown", other-node services as "remote".
        system = [c for c in data["containers"] if c["kind"] == "system"]
        self.assertTrue(system, "system rows should be synthesized when local is down")
        statuses = {c["status"] for c in system}
        self.assertTrue(statuses & {"unknown", "remote"})

    def test_both_engines_down_still_returns_200_not_503(self):
        """Even with NO reachable Docker engine, the view returns 200 with
        synthesized rows + engine errors — previously this was a hard 503 that the
        UI rendered as "Could not load containers"."""
        resp = self._get_with_local(lambda cls: None, labs_containers=[])
        # Patch labs to None as well for the true "nothing reachable" case.
        self.client.force_authenticate(self.admin)
        with _patch_topology(), \
                mock.patch.object(AdminMonitoringContainersView, "_local_client",
                                  classmethod(lambda cls: None)), \
                mock.patch.object(AdminMonitoringContainersView, "_labs_client",
                                  staticmethod(lambda: None)), \
                mock.patch.object(cluster_topology, "local_node_identity",
                                  return_value=_FOUR_NODE_TOPOLOGY["nodes"][1]):
            resp = self.client.get("/api/admin/monitoring/containers/?refresh=1")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertFalse(data["local_engine"]["available"])
        # The expected platform services are still represented for the operator.
        self.assertGreater(data["system_count"], 0)
        self.assertIn("engine_errors", data)
