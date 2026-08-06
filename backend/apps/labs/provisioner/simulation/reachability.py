"""ICMP / SSH reachability for lab terminals — inventory-scoped, not open internet.

Hosts are reachable only when they exist in the lab inventory (ServerIdentity /
engine host maps) on a path that matches Fortune-100 network reality:
same platform / underlay, powered on, and (for MAAS) Deployed.
Cross-cloud private paths (AWS↔Azure↔GCP) are refused without an explicit
peering model.
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any


_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

# Cloud / platform tags used for isolation (AWS private cannot reach Azure private).
_CLOUD_PLATFORMS = frozenset({"aws", "azure", "gcp", "openstack"})
_BAREMETAL_PLATFORMS = frozenset({"maas", "baremetal", "ai-infra", "datacenter", "lxd", "vyos"})


def _platform_of(server: dict[str, Any] | None) -> str:
    if not server:
        return ""
    sources = {str(s).lower() for s in (server.get("sources") or [])}
    tags = server.get("tags") or {}
    tag_blob = " ".join(str(v).lower() for v in (tags.values() if isinstance(tags, dict) else []))
    hay = " ".join(sources) + " " + tag_blob + " " + str(server.get("owner") or "").lower()
    for p in ("aws", "azure", "gcp", "openstack", "maas", "baremetal", "ai-infra"):
        if p in hay or p in sources:
            return p
    if "gpu" in hay:
        return "maas"
    return (next(iter(sources), "") or "").lower()


def _same_l3_family(src: str, dst: str) -> bool:
    """True when ICMP/SSH between platforms is allowed without VPN/peering.

    Unknown (empty) platforms do NOT auto-allow into a named public cloud.
    Empty↔empty is allowed for local underlay peers that already passed
    inventory/power checks (caller responsibility).
    """
    if not src and not dst:
        return True
    # One side unknown: allow only baremetal-family destinations (lab underlay),
    # never cross into a named public cloud.
    if not src:
        return dst in _BAREMETAL_PLATFORMS or not dst
    if not dst:
        return src in _BAREMETAL_PLATFORMS or not src
    if src == dst:
        return True
    if src in _BAREMETAL_PLATFORMS and dst in _BAREMETAL_PLATFORMS:
        return True
    # Distinct public clouds: private reachability denied.
    if src in _CLOUD_PLATFORMS and dst in _CLOUD_PLATFORMS and src != dst:
        return False
    if (src in _CLOUD_PLATFORMS and dst in _BAREMETAL_PLATFORMS) or (
        dst in _CLOUD_PLATFORMS and src in _BAREMETAL_PLATFORMS
    ):
        return False
    return True


def _ip_on_local_subnets(target_ip: str, iface_addrs: list[str]) -> bool:
    try:
        tip = ipaddress.ip_address(target_ip)
    except ValueError:
        return False
    for raw in iface_addrs:
        try:
            if "/" in raw:
                net = ipaddress.ip_network(raw, strict=False)
            else:
                net = ipaddress.ip_network(f"{raw}/24", strict=False)
            if tip in net:
                return True
        except ValueError:
            continue
    return False


def _find_inventory_match(host: str, inventory: list[dict]) -> dict | None:
    if not inventory:
        return None
    if _IPV4.match(host):
        for s in inventory:
            if (s.get("primary_ip") or "") == host:
                return s
        return None
    for s in inventory:
        if host in (s.get("hostname"), s.get("fqdn"), s.get("id")):
            return s
    return None


def _gate_inventory_peer(
    match: dict,
    *,
    host: str,
    local_platform: str,
) -> tuple[str | None, str | None]:
    """Apply power / MAAS install / platform gates. Returns (ip, err)."""
    if match.get("power") == "off":
        tip = match.get("primary_ip") or host
        return None, f"From {tip} icmp_seq=1 Destination Host Unreachable"

    inst = (match.get("install_state") or "").lower()
    plat = _platform_of(match)
    if plat in ("maas", "baremetal", "ai-infra") and inst and inst not in (
        "deployed", "allocated", "ready",
    ):
        if inst in ("new", "failed", "commissioning", ""):
            if not match.get("primary_ip"):
                return None, f"ping: {host}: Name or service not known"

    src_plat = (local_platform or "").lower()
    if not _same_l3_family(src_plat, plat):
        return None, "connect: Network is unreachable"

    ip = match.get("primary_ip") or (host if _IPV4.match(host) else "")
    if not ip:
        return None, f"ping: {host}: Name or service not known"
    return str(ip), None


def resolve_icmp_target(
    *,
    host: str,
    host_ips: dict,
    host_names: dict,
    iface_addrs: list[str],
    session_id: str | None,
    local_platform: str = "",
) -> tuple[str | None, str | None]:
    """Return (target_ip, error_message). error_message set on failure."""
    host = (host or "").strip()
    if not host:
        return None, "Usage: ping destination"

    if host in ("localhost", "127.0.0.1", "::1"):
        return "127.0.0.1", None

    # Own interface address
    if host in iface_addrs or any(host == a.split("/")[0] for a in iface_addrs):
        return host.split("/")[0], None

    inventory: list[dict] = []
    if session_id:
        try:
            from .server_identity import list_servers
            inventory = list_servers(session_id) or []
        except Exception:
            inventory = []

    # Resolve hostname → IP via maps, then ALWAYS gate through inventory/power/
    # platform (maps alone must not short-circuit to success).
    resolved_ip: str | None = None
    resolved_name: str | None = None
    if host in host_ips:
        # host_ips is {ip → hostname}
        resolved_ip = str(host)
        resolved_name = str(host_ips[host])
    elif host in host_names:
        meta = host_names.get(host) or {}
        ip = meta.get("ip") if isinstance(meta, dict) else None
        if ip:
            resolved_ip = str(ip)
            resolved_name = str(host)
    elif _IPV4.match(host):
        for ip, hn in (host_ips or {}).items():
            if str(ip) == host:
                resolved_ip = str(ip)
                resolved_name = str(hn)
                break

    if resolved_ip or resolved_name:
        match = _find_inventory_match(resolved_name or "", inventory) if inventory else None
        if match is None and resolved_ip and inventory:
            match = _find_inventory_match(resolved_ip, inventory)
        if match is not None:
            return _gate_inventory_peer(match, host=host, local_platform=local_platform)
        # Mapped peer with no ServerIdentity row — refuse when local is a named
        # public cloud (cannot prove same-cloud). Baremetal underlay maps OK.
        src = (local_platform or "").lower()
        if src in _CLOUD_PLATFORMS:
            return None, "connect: Network is unreachable"
        return str(resolved_ip or host), None

    match = _find_inventory_match(host, inventory)
    if match is not None:
        return _gate_inventory_peer(match, host=host, local_platform=local_platform)

    if _IPV4.match(host):
        # Same L2/L3 underlay as a local iface + known gateway (.1/.254) only.
        if _ip_on_local_subnets(host, iface_addrs):
            if host.endswith(".1") or host.endswith(".254"):
                return host, None
            return None, f"From {host} icmp_seq=1 Destination Host Unreachable"
        return None, f"From {host} icmp_seq=1 Destination Host Unreachable"

    return None, f"ping: {host}: Name or service not known"


def ssh_peer_allowed(
    *,
    host: str,
    session_id: str | None,
    local_platform: str = "",
) -> tuple[dict | None, str | None]:
    """Return (server_row, error). error set when SSH must be refused."""
    if not session_id:
        return None, None
    try:
        from .server_identity import list_servers
        servers = list_servers(session_id) or []
    except Exception:
        return None, None

    match = _find_inventory_match(host, servers)
    if not match:
        return None, None

    if match.get("power") == "off":
        return match, f"ssh: connect to host {host} port 22: Connection refused"

    plat = _platform_of(match)
    inst = (match.get("install_state") or "").lower()
    if plat in ("maas", "baremetal", "ai-infra") and inst and inst != "deployed":
        return match, f"ssh: connect to host {host} port 22: Connection refused"

    if local_platform and not _same_l3_family(local_platform, plat):
        return match, f"ssh: connect to host {host} port 22: No route to host"

    return match, None
