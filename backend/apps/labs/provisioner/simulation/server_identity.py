"""Canonical ServerIdentity — one server record shared across consoles.

Every technology console (VMware, AWS, lab terminal, Commvault, Datacenter, …)
should read/write through this module rather than inventing a parallel host
identity. Hardware and power changes publish events on a Redis-backed bus so
subscribers can refresh.

This is the Phase 1 foundation. Engines adopt it incrementally; bridges already
feed the lab terminal and are mirrored here.
"""

from __future__ import annotations

import copy
import json
import time
import uuid
from typing import Any

from django.core.cache import cache

IDENTITY_TTL = 7200
EVENTS_TTL = 7200
EVENTS_MAX = 200


def _identity_key(session_id: str, server_id: str) -> str:
    return f"server_identity:{session_id}:{server_id}"


def _index_key(session_id: str) -> str:
    return f"server_identity_index:{session_id}"


def _events_key(session_id: str) -> str:
    return f"server_identity_events:{session_id}"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _blank(
    *,
    server_id: str | None = None,
    hostname: str = "lab-server",
    primary_ip: str = "10.20.30.41",
    source: str = "unknown",
) -> dict[str, Any]:
    sid = server_id or f"srv-{uuid.uuid4().hex[:10]}"
    return {
        "id": sid,
        "hostname": hostname,
        "fqdn": f"{hostname}.corp.local",
        "primary_ip": primary_ip,
        "ips": [primary_ip] if primary_ip else [],
        "cpu": 4,
        "mem_mb": 8192,
        "disks": [{"name": "sda", "size_gb": 40, "role": "root"}],
        "nics": [{"name": "eth0", "mac": "00:50:56:a1:b2:c3", "connected": True, "ip": primary_ip}],
        "power": "on",  # on | off | reboot_pending
        "os": "rhel-9",
        "install_state": "deployed",
        "tags": {},
        "sources": [source] if source else [],
        "physical_location": None,  # {room, rack, u_position}
        "bmc": None,  # {endpoint, protocol, power, sensors}
        "network_port": None,  # {switch, port, vlan}
        # Virtualized GPU/accelerator facet — never backed by real silicon.
        "gpu": None,  # {present, model, driver_loaded, health, driver_version, mig_enabled}
        "updated_at": _now_iso(),
    }


def list_servers(session_id: str) -> list[dict]:
    ids = cache.get(_index_key(str(session_id))) or []
    out = []
    for sid in ids:
        data = cache.get(_identity_key(str(session_id), sid))
        if data:
            out.append(json.loads(data) if isinstance(data, str) else data)
    return out


def get_server(session_id: str, server_id: str) -> dict | None:
    data = cache.get(_identity_key(str(session_id), server_id))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def get_primary(session_id: str) -> dict | None:
    servers = list_servers(session_id)
    if not servers:
        return None
    for s in servers:
        if s.get("tags", {}).get("role") == "primary":
            return s
    return servers[0]


def _save(session_id: str, server: dict) -> dict:
    sid = str(session_id)
    server = copy.deepcopy(server)
    server["updated_at"] = _now_iso()
    server_id = server["id"]
    cache.set(_identity_key(sid, server_id), json.dumps(server, default=str), IDENTITY_TTL)
    index = list(cache.get(_index_key(sid)) or [])
    if server_id not in index:
        index.append(server_id)
        cache.set(_index_key(sid), index, IDENTITY_TTL)
    return server


def upsert_server(session_id: str, patch: dict, *, source: str = "api") -> dict:
    """Create or merge a server identity. Returns the saved record."""
    sid = str(session_id)
    server_id = patch.get("id") or patch.get("server_id")
    existing = get_server(sid, server_id) if server_id else None
    if existing is None and patch.get("hostname"):
        # Match by hostname within the session when id omitted.
        for s in list_servers(sid):
            if s.get("hostname") == patch["hostname"]:
                existing = s
                server_id = s["id"]
                break
    if existing is None:
        server = _blank(
            server_id=server_id,
            hostname=patch.get("hostname") or "lab-server",
            primary_ip=patch.get("primary_ip") or patch.get("ip") or "10.20.30.41",
            source=source,
        )
    else:
        server = copy.deepcopy(existing)
        if source and source not in server.get("sources", []):
            server.setdefault("sources", []).append(source)

    for key in (
        "hostname", "fqdn", "primary_ip", "cpu", "mem_mb", "power", "os",
        "install_state", "physical_location", "bmc", "network_port", "gpu",
    ):
        if key in patch and patch[key] is not None:
            server[key] = patch[key]
    if "ip" in patch and patch["ip"]:
        server["primary_ip"] = patch["ip"]
        if patch["ip"] not in server.get("ips", []):
            server.setdefault("ips", []).append(patch["ip"])
    if "ips" in patch and isinstance(patch["ips"], list):
        server["ips"] = list(patch["ips"])
    if "disks" in patch and isinstance(patch["disks"], list):
        server["disks"] = copy.deepcopy(patch["disks"])
    if "nics" in patch and isinstance(patch["nics"], list):
        server["nics"] = copy.deepcopy(patch["nics"])
    if "tags" in patch and isinstance(patch["tags"], dict):
        server.setdefault("tags", {}).update(patch["tags"])

    saved = _save(sid, server)
    publish_event(sid, "server.upserted", {"server_id": saved["id"], "source": source, "server": saved})
    return saved


def set_power(session_id: str, server_id: str, power: str, *, source: str = "api") -> dict | None:
    server = get_server(session_id, server_id)
    if not server:
        return None
    server["power"] = power
    if source and source not in server.get("sources", []):
        server.setdefault("sources", []).append(source)
    saved = _save(session_id, server)
    publish_event(session_id, "server.power", {"server_id": server_id, "power": power, "source": source})
    return saved


def attach_disk(
    session_id: str,
    server_id: str,
    *,
    name: str,
    size_gb: int,
    source: str = "api",
) -> dict | None:
    server = get_server(session_id, server_id)
    if not server:
        return None
    disks = list(server.get("disks") or [])
    if not any(d.get("name") == name for d in disks):
        disks.append({"name": name, "size_gb": int(size_gb), "role": "data", "pending_rescan": True})
    server["disks"] = disks
    saved = _save(session_id, server)
    publish_event(
        session_id,
        "server.disk_attached",
        {"server_id": server_id, "name": name, "size_gb": size_gb, "source": source},
    )
    return saved


def attach_nic(
    session_id: str,
    server_id: str,
    *,
    name: str,
    mac: str | None = None,
    source: str = "api",
) -> dict | None:
    server = get_server(session_id, server_id)
    if not server:
        return None
    nics = list(server.get("nics") or [])
    if not any(n.get("name") == name for n in nics):
        nics.append({
            "name": name,
            "mac": mac or f"00:50:56:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[:2]}",
            "connected": True,
            "pending_rescan": True,
        })
    server["nics"] = nics
    saved = _save(session_id, server)
    publish_event(session_id, "server.nic_attached", {"server_id": server_id, "name": name, "source": source})
    return saved


def publish_event(session_id: str, event_type: str, payload: dict | None = None) -> dict:
    sid = str(session_id)
    event = {
        "id": uuid.uuid4().hex,
        "type": event_type,
        "payload": payload or {},
        "ts": _now_iso(),
        "trace_id": (payload or {}).get("trace_id") or uuid.uuid4().hex[:16],
    }
    raw = cache.get(_events_key(sid))
    events = json.loads(raw) if isinstance(raw, str) else (raw or [])
    events.insert(0, event)
    events = events[:EVENTS_MAX]
    cache.set(_events_key(sid), json.dumps(events, default=str), EVENTS_TTL)
    return event


def consume_events(session_id: str, after_id: str | None = None) -> list[dict]:
    raw = cache.get(_events_key(str(session_id)))
    events = json.loads(raw) if isinstance(raw, str) else (raw or [])
    if not after_id:
        return list(events)
    out = []
    for ev in events:
        if ev.get("id") == after_id:
            break
        out.append(ev)
    return out


def drop_session(session_id: str) -> None:
    sid = str(session_id)
    for server_id in list(cache.get(_index_key(sid)) or []):
        cache.delete(_identity_key(sid, server_id))
    cache.delete(_index_key(sid))
    cache.delete(_events_key(sid))


def set_gpu(
    session_id: str,
    server_id: str,
    *,
    present: bool = True,
    model: str = "NVIDIA H100 80GB HBM3",
    driver_loaded: bool = False,
    health: str = "failed",
    driver_version: str = "550.90.07",
    mig_enabled: bool = False,
    source: str = "gpu",
) -> dict | None:
    """Update the virtualized GPU facet on a server (never real accelerator hardware)."""
    server = get_server(session_id, server_id)
    if not server:
        return None
    server["gpu"] = {
        "present": present,
        "model": model,
        "driver_loaded": driver_loaded,
        "health": health,  # healthy | failed | missing
        "driver_version": driver_version,
        "mig_enabled": mig_enabled,
    }
    if source and source not in server.get("sources", []):
        server.setdefault("sources", []).append(source)
    tags = dict(server.get("tags") or {})
    tags["has_gpu"] = True
    server["tags"] = tags
    saved = _save(session_id, server)
    publish_event(
        session_id,
        "server.gpu_updated",
        {"server_id": server_id, "gpu": saved["gpu"], "source": source},
    )
    return saved


def seed_gpu_node(
    session_id: str,
    *,
    hostname: str = "gpu-node-01",
    primary_ip: str = "10.20.40.10",
    healthy: bool = False,
    role: str = "primary",
) -> dict:
    """Seed a GPU training node into ServerIdentity for gpu-track labs."""
    server = upsert_server(
        session_id,
        {
            "id": f"gpu-{hostname}",
            "hostname": hostname,
            "primary_ip": primary_ip,
            "cpu": 64,
            "mem_mb": 524288,
            "power": "on",
            "os": "rhel-9",
            "tags": {"role": role, "track": "gpu"},
            "gpu": {
                "present": True,
                "model": "NVIDIA H100 80GB HBM3",
                "driver_loaded": bool(healthy),
                "health": "healthy" if healthy else "failed",
                "driver_version": "550.90.07",
                "mig_enabled": False,
            },
        },
        source="gpu",
    )
    return server


def seed_from_vmware_vm(session_id: str, vm: dict, *, role: str = "primary") -> dict:
    """Upsert identity from a VMware inventory VM dict."""
    return upsert_server(
        session_id,
        {
            "id": f"vmware-{vm.get('id') or vm.get('name') or 'guest'}",
            "hostname": vm.get("hostname") or vm.get("name") or "vm-guest",
            "primary_ip": vm.get("ip") or "",
            "cpu": vm.get("cpu") or 2,
            "mem_mb": vm.get("memory_mb") or vm.get("mem_mb") or 4096,
            "power": "on" if (vm.get("power") or "").lower() in ("poweredon", "on", "running") else "off",
            "os": vm.get("guest_os") or vm.get("guest_os_version") or "linux",
            "tags": {"role": role, "vmware_name": vm.get("name")},
            "physical_location": vm.get("physical_location"),
        },
        source="vmware",
    )


def seed_from_aws_instance(session_id: str, inst: dict, *, role: str = "primary") -> dict:
    """Upsert identity from an AWS EC2-like instance dict."""
    private_ip = inst.get("privateIp") or ""
    hostname = f"ip-{private_ip.replace('.', '-')}" if private_ip else (inst.get("name") or inst.get("id") or "ec2")
    return upsert_server(
        session_id,
        {
            "id": f"aws-{inst.get('id') or hostname}",
            "hostname": hostname,
            "primary_ip": private_ip,
            "cpu": 1,
            "mem_mb": 1024,
            "power": "on" if inst.get("state") == "running" else "off",
            "os": inst.get("os") or "amazon-linux-2023",
            "tags": {"role": role, "instance_id": inst.get("id"), "name": inst.get("name")},
        },
        source="aws",
    )
