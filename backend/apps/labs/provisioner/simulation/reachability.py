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
    """True when ICMP/SSH between platforms is allowed without VPN/peering."""
    if not src or not dst:
        return True  # unknown → allow inventory peer on same session
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

    # Known lab peer by hostname
    if host in host_ips:
        return str(host_ips[host]), None
    if host in host_names:
        meta = host_names.get(host) or {}
        ip = meta.get("ip") if isinstance(meta, dict) else None
        if ip:
            return str(ip), None

    # Own interface address
    if host in iface_addrs or any(host == a.split("/")[0] for a in iface_addrs):
        return host.split("/")[0], None

    # Inventory lookup
    inventory: list[dict] = []
    if session_id:
        try:
            from .server_identity import list_servers
            inventory = list_servers(session_id) or []
        except Exception:
            inventory = []

    match = None
    if _IPV4.match(host):
        for s in inventory:
            if (s.get("primary_ip") or "") == host:
                match = s
                break
        if match is None:
            # Same L2/L3 underlay as a local iface + known gateway (.1) only —
            # never open-reply to random dotted-quads.
            if _ip_on_local_subnets(host, iface_addrs):
                # Gateway .1 on lab underlay is reachable for routing labs.
                if host.endswith(".1") or host.endswith(".254"):
                    return host, None
                return None, f"From {host} icmp_seq=1 Destination Host Unreachable"
            return None, f"From {host} icmp_seq=1 Destination Host Unreachable"
    else:
        for s in inventory:
            if host in (s.get("hostname"), s.get("fqdn")):
                match = s
                break
        if match is None:
            return None, f"ping: {host}: Name or service not known"

    if match.get("power") == "off":
        return None, f"From {match.get('primary_ip') or host} icmp_seq=1 Destination Host Unreachable"

    # MAAS New/Ready without Deployed: link-local commission path only — no guest stack.
    inst = (match.get("install_state") or "").lower()
    plat = _platform_of(match)
    if plat in ("maas", "baremetal", "ai-infra") and inst and inst not in (
        "deployed", "allocated", "ready",
    ):
        # Ready is PXE-commissioned but OS may still answer ICMP on BMC path —
        # allow Ready; block New/Failed/Commissioning without IP stack.
        if inst in ("new", "failed", "commissioning", ""):
            if not match.get("primary_ip"):
                return None, f"ping: {host}: Name or service not known"

    src_plat = local_platform or ""
    if not src_plat and inventory:
        # Infer local platform from primary hostname match in inventory
        pass
    if not _same_l3_family(src_plat, plat):
        return None, f"connect: Network is unreachable"

    ip = match.get("primary_ip") or host
    if not ip:
        return None, f"ping: {host}: Name or service not known"
    return str(ip), None


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

    match = None
    for s in servers:
        if host in (s.get("hostname"), s.get("fqdn"), s.get("primary_ip"), s.get("id")):
            match = s
            break
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
