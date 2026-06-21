"""
Cluster topology loader for the admin fleet-monitoring dashboard.

FixitLab can run as a single host (dev / one droplet) or as the production
4-droplet cluster (edge / app / data / labs). This module is the single source
of truth for *which nodes exist* so the monitoring views can enumerate the whole
fleet instead of only the node serving the request.

Discovery order:

  1. ``settings.CLUSTER_TOPOLOGY_FILE`` (defaults to
     ``<repo>/infra/digitalocean/cluster.json``) when its ``topology`` field is
     ``"four-droplet"`` — returns all four nodes with role / IP / services.
  2. Otherwise fall back to a single "local" node so the dashboard always renders.

Everything here is best-effort and NEVER raises: a malformed or missing file
degrades gracefully to the single-node fallback. The metrics themselves are
filled in by ``server_metrics`` / the fleet aggregator; this module only answers
"what nodes should we be showing, and how do we reach them?".
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# A normalised cluster node looks like:
#   {
#     "key": "edge",            # stable key from cluster.json
#     "name": "fixitlab-edge",  # friendly display name
#     "role": "edge",
#     "public": True,
#     "public_ipv4": "139.59.38.209" | None,
#     "private_ipv4": "10.122.16.2" | None,
#     "ip": "10.122.16.2",      # preferred address (private first, public fallback)
#     "services": [...],
#     "droplet_id": "579110328" | None,
#   }


def _default_topology_file() -> Path:
    """Repo-root ``infra/digitalocean/cluster.json``.

    ``settings.BASE_DIR`` is the ``backend/`` directory, so the repo root is its
    parent.
    """
    configured = getattr(settings, "CLUSTER_TOPOLOGY_FILE", "") or ""
    if configured:
        return Path(configured)
    base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    return base.parent / "infra" / "digitalocean" / "cluster.json"


def _normalise_node(key: str, raw: dict) -> dict:
    raw = raw or {}
    private_ip = raw.get("private_ipv4") or None
    public_ip = raw.get("public_ipv4") or None
    # Prefer the private VPC address for in-cluster reachability; fall back to
    # the public address (edge node) so there is always *something* to show.
    preferred = private_ip or public_ip
    return {
        "key": key,
        "name": raw.get("name") or key,
        "role": raw.get("role") or key,
        "public": bool(raw.get("public")),
        "public_ipv4": public_ip,
        "private_ipv4": private_ip,
        "ip": preferred,
        "services": list(raw.get("services") or []),
        "droplet_id": raw.get("droplet_id"),
    }


def _read_cluster_file(path: Path) -> dict | None:
    try:
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not read cluster topology %s: %s", path, exc)
    return None


@lru_cache(maxsize=1)
def _load_cached() -> dict:
    """Parse the cluster file once per process (cheap; topology rarely changes)."""
    path = _default_topology_file()
    data = _read_cluster_file(path)

    if not data or str(data.get("topology", "")).lower() != "four-droplet":
        return {
            "topology": str((data or {}).get("topology", "") or "single-host"),
            "source": str(path) if data else "fallback",
            "is_cluster": False,
            "nodes": [],
            "meta": {},
        }

    droplets = data.get("droplets") or {}
    nodes = []
    # Stable, human-friendly ordering by role.
    role_order = {"edge": 0, "app": 1, "data": 2, "db": 2, "labs": 3}
    for key, raw in droplets.items():
        nodes.append(_normalise_node(key, raw))
    nodes.sort(key=lambda n: (role_order.get(n["role"], 99), n["name"]))

    return {
        "topology": "four-droplet",
        "source": str(path),
        "is_cluster": True,
        "nodes": nodes,
        "meta": {
            "region": data.get("region"),
            "domain": data.get("domain"),
            "vpc_name": data.get("vpc_name"),
            "ssh_user": data.get("ssh_user"),
            "updated_at": data.get("updated_at"),
        },
    }


def reset_cache() -> None:
    """Clear the parsed-topology cache (useful in tests / after a re-deploy)."""
    _load_cached.cache_clear()


def load_topology() -> dict:
    """Return the parsed cluster topology.

    Honours the ``CLUSTER_TOPOLOGY_DISABLE`` env flag (force single-host) so the
    single-host fallback can be exercised without editing the file.
    """
    if os.environ.get("CLUSTER_TOPOLOGY_DISABLE", "").lower() in ("1", "true", "yes"):
        return {
            "topology": "single-host",
            "source": "disabled",
            "is_cluster": False,
            "nodes": [],
            "meta": {},
        }
    return _load_cached()


def is_cluster() -> bool:
    return bool(load_topology().get("is_cluster"))


def cluster_nodes() -> list[dict]:
    """List of normalised cluster nodes (empty when not a cluster)."""
    return list(load_topology().get("nodes") or [])


def node_count() -> int:
    return len(cluster_nodes())


def local_node_identity() -> dict:
    """Best-effort: which cluster node *is* the host serving this request.

    Matches by ``MONITORING_NODE_NAME``/hostname or the local IPs against
    cluster.json so the fleet view can attribute live local metrics (and the
    local Docker container list) to the right node card. Returns ``{}`` when no
    confident match is found.
    """
    nodes = cluster_nodes()
    if not nodes:
        return {}

    import socket

    candidates = set()
    node_name = (getattr(settings, "MONITORING_NODE_NAME", "") or "").lower()
    if node_name:
        candidates.add(node_name)
    try:
        candidates.add(socket.gethostname().lower())
    except Exception:
        pass

    # Local IP addresses (private + outbound) for IP-based matching.
    local_ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ips.add(s.getsockname()[0])
        finally:
            s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            local_ips.add(info[4][0])
    except Exception:
        pass

    for node in nodes:
        name = (node.get("name") or "").lower()
        key = (node.get("key") or "").lower()
        role = (node.get("role") or "").lower()
        if name in candidates or key in candidates or role in candidates:
            return node
        if any(c and (c in name or name in c) for c in candidates if c):
            return node
        node_ips = {node.get("private_ipv4"), node.get("public_ipv4"), node.get("ip")}
        if local_ips & {ip for ip in node_ips if ip}:
            return node
    return {}
