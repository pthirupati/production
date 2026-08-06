"""Scenario-scoped LabServer identity — one server graph per lab session.

IMPORTANT: There is NO platform-global server. Each LabSession owns its own
LabServer records (hostname, IP, CPU, RAM, disks, NICs, power, OS, optional
physical_location / BMC / GPU). Cross-tech consoles in the *same* session
read/write those records; a different scenario gets a different graph.

Hardware and power changes publish events on a Redis-backed bus so subscribers
in this session can refresh.
"""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)

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
        "install_state": "deployed",  # MAAS: New|Ready|Deployed|… or generic deployed
        "tags": {},
        "sources": [source] if source else [],
        "physical_location": None,  # {room, rack, u_position}
        "bmc": None,  # {endpoint, protocol, power, sensors}
        "network_port": None,  # {switch, port, vlan}
        # Virtualized GPU/accelerator facet — never backed by real silicon.
        "gpu": None,  # {present, model, driver_loaded, health, driver_version, mig_enabled}
        # S1 CMDB / twin fields — single asset record shared across consoles.
        "serial": None,
        "asset_tag": None,
        "owner": None,
        "firmware": None,  # {bios, bmc, raid, vbios}
        "raid": None,  # {level, controllers, virtual_disks}
        "gpus": [],  # multi-GPU inventory; `gpu` remains primary/compat facet
        "thermal": None,  # {inlet_c, gpu_max_c, power_w}
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


def upsert_server(session_id: str, patch: dict, *, source: str = "api", trace_id: str | None = None) -> dict:
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
        "serial", "asset_tag", "owner", "firmware", "raid", "thermal",
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
    if "gpus" in patch and isinstance(patch["gpus"], list):
        server["gpus"] = copy.deepcopy(patch["gpus"])
    if "tags" in patch and isinstance(patch["tags"], dict):
        server.setdefault("tags", {}).update(patch["tags"])

    saved = _save(sid, server)
    publish_event(
        sid, "server.upserted", {"server_id": saved["id"], "source": source, "server": saved},
        trace_id=trace_id,
    )
    return saved


def set_power(
    session_id: str, server_id: str, power: str, *, source: str = "api", trace_id: str | None = None,
) -> dict | None:
    server = get_server(session_id, server_id)
    if not server:
        return None
    server["power"] = power
    if source and source not in server.get("sources", []):
        server.setdefault("sources", []).append(source)
    saved = _save(session_id, server)
    # Power-off must drop terminal SSH/ICMP maps so stopped cloud VMs stop
    # answering ping/ssh — matching Fortune-100 guest lifecycle.
    if power == "off":
        try:
            unregister_terminal_ssh_host(
                session_id,
                hostname=server.get("hostname") or "",
                ip=server.get("primary_ip") or "",
            )
        except Exception:
            pass
    elif power == "on" and (server.get("primary_ip") or "") and (server.get("hostname") or ""):
        try:
            register_terminal_ssh_host(
                session_id,
                hostname=server["hostname"],
                ip=server["primary_ip"],
                source=source or "power-on",
            )
        except Exception:
            pass
    publish_event(
        session_id, "server.power", {"server_id": server_id, "power": power, "source": source},
        trace_id=trace_id,
    )
    return saved


def attach_disk(
    session_id: str,
    server_id: str,
    *,
    name: str,
    size_gb: int,
    source: str = "api",
    trace_id: str | None = None,
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
        trace_id=trace_id,
    )
    return saved


def detach_disk(
    session_id: str,
    server_id: str,
    *,
    name: str,
    source: str = "api",
    trace_id: str | None = None,
) -> dict | None:
    """Remove a data disk (e.g. an AWS EBS volume detach) from this server's
    identity so `lsblk`/inventory views stop showing it — mirrors attach_disk."""
    server = get_server(session_id, server_id)
    if not server:
        return None
    disks = [d for d in (server.get("disks") or []) if d.get("name") != name]
    server["disks"] = disks
    saved = _save(session_id, server)
    publish_event(
        session_id,
        "server.disk_detached",
        {"server_id": server_id, "name": name, "source": source},
        trace_id=trace_id,
    )
    return saved


def attach_nic(
    session_id: str,
    server_id: str,
    *,
    name: str,
    mac: str | None = None,
    source: str = "api",
    trace_id: str | None = None,
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
    publish_event(
        session_id, "server.nic_attached", {"server_id": server_id, "name": name, "source": source},
        trace_id=trace_id,
    )
    return saved


def new_trace_id() -> str:
    """A single logical learner action (e.g. one "resize VM" click) that
    fans out across multiple engines/consoles (the console's own event log,
    the cross-tech bridge, ServerIdentity, and eventually the terminal)
    should carry ONE trace_id through every hop, so
    `events_for_trace(session_id, trace_id)` can reconstruct the whole
    cross-engine story for a single support/debug question: "what actually
    happened when the learner clicked this button?" Call this ONCE at the
    top of the action and thread the returned id through every downstream
    `publish_event`/bridge call.
    """
    return uuid.uuid4().hex[:16]


def publish_event(
    session_id: str,
    event_type: str,
    payload: dict | None = None,
    *,
    trace_id: str | None = None,
) -> dict:
    sid = str(session_id)
    payload = payload or {}
    event = {
        "id": uuid.uuid4().hex,
        "type": event_type,
        "payload": payload,
        "ts": _now_iso(),
        # Explicit trace_id kwarg wins; falls back to one embedded in the
        # payload (older call sites), else a fresh id so every event still
        # has SOME trace_id even when the caller has nothing to correlate.
        "trace_id": trace_id or payload.get("trace_id") or uuid.uuid4().hex[:16],
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


def events_for_trace(session_id: str, trace_id: str) -> list[dict]:
    """Every LabServer event recorded under a given trace_id, oldest first —
    reconstructs the full cross-engine story for one logical learner action."""
    raw = cache.get(_events_key(str(session_id)))
    events = json.loads(raw) if isinstance(raw, str) else (raw or [])
    matched = [ev for ev in events if ev.get("trace_id") == trace_id]
    return list(reversed(matched))


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
    gpus = [
        {
            "index": i,
            "model": "NVIDIA H100 80GB HBM3",
            "uuid": f"GPU-{i:08x}-1a2b-3c4d-5e6f-0011223344{i:02d}",
            "pci_bus_id": f"00000000:{(i + 1) * 0x10 + 1:02X}:00.0",
        }
        for i in range(8)
    ]
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
            "serial": f"SN-H100-{hostname[-2:].upper()}",
            "asset_tag": f"AT-GPU-{hostname[-2:].upper()}",
            "owner": "ai-infra",
            "install_state": "Deployed",
            "firmware": {"bios": "2.14.0", "bmc": "5.10.30", "vbios": "96.00.74.00.01"},
            "tags": {"role": role, "track": "gpu"},
            "gpu": {
                "present": True,
                "model": "NVIDIA H100 80GB HBM3",
                "driver_loaded": bool(healthy),
                "health": "healthy" if healthy else "failed",
                "driver_version": "550.90.07",
                "mig_enabled": False,
            },
            "gpus": gpus,
            "physical_location": {"room": "Hall-A", "rack": "R12", "u_position": 20},
        },
        source="gpu",
    )
    return server


def upsert_from_maas_machine(
    session_id: str,
    machine: dict,
    *,
    source: str = "maas",
    owner: str = "ai-infra",
) -> dict | None:
    """Write-once MAAS machine → unified asset registry (S1 #210–211).

    Called when commission reaches Ready or deploy reaches Deployed so the
    same hostname appears in CMDB lists, AWX maas-gpu-nodes, and DC twin.
    """
    if not session_id or not isinstance(machine, dict):
        return None
    name = (machine.get("name") or machine.get("hostname") or "").strip()
    if not name:
        return None
    status = (machine.get("status") or "").strip() or "New"
    ip = machine.get("ip") or machine.get("primary_ip") or ""
    if ip in ("-", None):
        ip = ""
    power = "on" if (machine.get("power") or "on").lower() in ("on", "on.", "poweredon") else "off"
    # Stable synthetic identity so re-commission updates the same record.
    digit = "".join(ch for ch in name if ch.isdigit()) or "00"
    serial = machine.get("serial") or f"CN7{digit.zfill(4)}MAAS{digit.zfill(2)}"
    asset_tag = machine.get("asset_tag") or f"AT-{name.upper()}"
    is_gpu = "gpu" in name.lower() or "h100" in name.lower() or "mi300" in name.lower()
    patch: dict[str, Any] = {
        "id": f"maas-{name}",
        "hostname": name,
        "primary_ip": ip,
        "power": power,
        "os": machine.get("os") or ("ubuntu-22.04" if status == "Deployed" else "commissioning"),
        "install_state": status,
        "serial": serial,
        "asset_tag": asset_tag,
        "owner": machine.get("owner") or owner,
        "cpu": machine.get("cpu") or (64 if is_gpu else 32),
        "mem_mb": machine.get("mem_mb") or (524288 if is_gpu else 131072),
        "firmware": machine.get("firmware") or {
            "bios": "2.14.0",
            "bmc": "5.10.30",
            "raid": "50.5.0-0000",
        },
        "physical_location": machine.get("physical_location") or {
            "room": "Hall-A",
            "rack": machine.get("rack") or "R12",
            "u_position": machine.get("u_position") or (10 + int(digit or 0) % 20),
        },
        "bmc": machine.get("bmc") or {
            "endpoint": f"https://bmc-{name}.dc.local",
            "protocol": "IPMI",
            "power": power,
        },
        "tags": {
            "role": "gpu-node" if is_gpu else "baremetal",
            "maas_status": status,
            "arch": machine.get("arch") or "amd64/generic",
            "zone": machine.get("zone") or "default",
            "pool": machine.get("pool") or "default",
            "appears_in": ["maas", "awx", "datacenter", "cmdb", "terminal"],
        },
    }
    if is_gpu:
        patch["gpu"] = {
            "present": True,
            "model": "NVIDIA H100 80GB HBM3",
            "driver_loaded": status == "Deployed",
            "health": "healthy" if status == "Deployed" else "unknown",
            "driver_version": "550.90.07",
            "mig_enabled": False,
        }
        patch["gpus"] = [
            {
                "index": i,
                "model": "NVIDIA H100 80GB HBM3",
                "uuid": f"GPU-{i:08x}-maas-{digit}-{i:02d}",
                "pci_bus_id": f"00000000:{(i + 1) * 0x10 + 1:02X}:00.0",
            }
            for i in range(8)
        ]
        patch["raid"] = {"level": "RAID10", "controllers": 1, "virtual_disks": 2}
    row = upsert_server(session_id, patch, source=source)
    # Terminal SSH peers: only Deployed + powered-on nodes (real guest OS).
    if row and status == "Deployed" and ip and power == "on":
        try:
            register_terminal_ssh_host(
                session_id, hostname=name, ip=ip, source="maas-deployed",
            )
        except Exception:
            pass
    return row


def upsert_from_lxd_instance(
    session_id: str,
    instance: dict,
    *,
    source: str = "lxd",
    owner: str = "ai-infra",
) -> dict | None:
    """Register an LXD instance host into the unified asset registry."""
    if not session_id or not isinstance(instance, dict):
        return None
    name = (instance.get("name") or "").strip()
    if not name:
        return None
    status = (instance.get("status") or "Stopped").strip()
    ip = instance.get("ipv4") or instance.get("ip") or ""
    power = "on" if status.lower() == "running" else "off"
    has_gpu = bool(instance.get("nvidia_smi_ok")) or any(
        isinstance(d, dict) and d.get("type") == "gpu"
        for d in (instance.get("devices") or {}).values()
    )
    patch: dict[str, Any] = {
        "id": f"lxd-{name}",
        "hostname": name,
        "primary_ip": ip,
        "power": power,
        "os": "ubuntu-22.04",
        "install_state": status,
        "serial": f"LXD-{name.upper()[:12]}",
        "asset_tag": f"LXD-{name.upper()}",
        "owner": owner,
        "cpu": int((instance.get("config") or {}).get("limits.cpu") or 4),
        "mem_mb": 8192,
        "physical_location": {
            "room": "Hall-A",
            "rack": "R14",
            "u_position": 8,
        },
        "tags": {
            "role": "lxd-instance",
            "type": instance.get("type") or "container",
            "project": instance.get("project") or "default",
            "location": instance.get("location") or "none",
            "appears_in": ["lxd", "maas", "datacenter", "terminal"],
        },
    }
    if has_gpu:
        patch["gpu"] = {
            "present": True,
            "model": "NVIDIA H100 80GB HBM3",
            "driver_loaded": bool(instance.get("nvidia_smi_ok")),
            "health": "healthy" if instance.get("nvidia_smi_ok") else "unknown",
        }
    return upsert_server(session_id, patch, source=source)


def list_assets(session_id: str) -> list[dict[str, Any]]:
    """CMDB-shaped projection of the unified asset registry (S1 #210)."""
    rows: list[dict[str, Any]] = []
    for s in list_servers(session_id):
        loc = s.get("physical_location") or {}
        fw = s.get("firmware") or {}
        gpu = s.get("gpu") or {}
        rows.append(
            {
                "id": s.get("id"),
                "hostname": s.get("hostname"),
                "serial": s.get("serial"),
                "asset_tag": s.get("asset_tag"),
                "owner": s.get("owner"),
                "install_state": s.get("install_state"),
                "power": s.get("power"),
                "primary_ip": s.get("primary_ip"),
                "os": s.get("os"),
                "rack": loc.get("rack"),
                "u_position": loc.get("u_position"),
                "room": loc.get("room"),
                "firmware_bios": fw.get("bios") if isinstance(fw, dict) else None,
                "firmware_bmc": fw.get("bmc") if isinstance(fw, dict) else None,
                "gpu_model": gpu.get("model") if isinstance(gpu, dict) else None,
                "gpu_count": len(s.get("gpus") or []) or (1 if gpu.get("present") else 0),
                "sources": list(s.get("sources") or []),
                "updated_at": s.get("updated_at"),
            }
        )
    rows.sort(key=lambda r: (r.get("hostname") or "", r.get("id") or ""))
    return rows


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
    server = upsert_server(
        session_id,
        {
            "id": f"aws-{inst.get('id') or hostname}",
            "hostname": hostname,
            "primary_ip": private_ip,
            "cpu": 1,
            "mem_mb": 1024,
            "power": "on" if inst.get("state") == "running" else "off",
            "os": inst.get("os") or "amazon-linux-2023",
            "tags": {
                "role": role,
                "instance_id": inst.get("id"),
                "name": inst.get("name"),
                "appears_in": ["aws", "terminal"],
            },
        },
        source="aws",
    )
    if private_ip and (inst.get("state") or "running") == "running":
        register_terminal_ssh_host(
            session_id, hostname=hostname, ip=private_ip, ssh_user="ec2-user", source="aws",
        )
    return server


def register_terminal_ssh_host(
    session_id: str,
    *,
    hostname: str,
    ip: str,
    ssh_user: str = "root",
    role: str = "cloud-vm",
    source: str = "cloud",
) -> None:
    """Register a LabServer so ``ssh user@hostname`` / ``ssh user@ip`` works in
    this session's primary shell and jump-box (ssh_client) shell.

    ServerIdentity alone is not enough — the terminal resolves peers via the
    sim session's ``hosts`` / ``host_ips`` maps (and ``/etc/hosts``). Call this
    whenever a cloud console creates or syncs a reachable VM.
    """
    hostname = (hostname or "").strip()
    ip = (ip or "").strip()
    if not hostname or not ip:
        return
    try:
        from .shell import get_sim_session
    except Exception:
        return
    entry = get_sim_session(str(session_id))
    if not entry:
        return
    state = entry.setdefault("state", {})
    hosts = state.setdefault("hosts", {})
    host_ips = state.setdefault("host_ips", {})
    meta = {
        "name": hostname,
        "role": role,
        "ip": ip,
        "ssh_user": ssh_user,
        "source": source,
    }
    hosts[hostname] = {**(hosts.get(hostname) or {}), **meta}
    host_ips[ip] = hostname

    def _wire(shell) -> None:
        if shell is None:
            return
        shell._host_names = dict(hosts)
        shell._host_ips = dict(host_ips)
        try:
            content = shell.state.read_file("/etc/hosts") or ""
            line = f"{ip} {hostname}"
            # Avoid duplicate lines for the same hostname or IP.
            already = False
            for raw in content.splitlines():
                cols = raw.split("#", 1)[0].split()
                if len(cols) >= 2 and (hostname in cols[1:] or cols[0] == ip):
                    already = True
                    break
            if not already:
                shell.state._write_file("/etc/hosts", content.rstrip("\n") + "\n" + line + "\n")
        except Exception:
            pass

    engine = state.get("engine")
    if engine is not None:
        _wire(getattr(engine, "shell", None))
        try:
            engine.shell._engine = engine  # noqa: SLF001
        except Exception:
            pass
    _wire(state.get("ssh_client_shell"))

    client_meta = hosts.get("ssh_client")
    if isinstance(client_meta, dict):
        targets = list(client_meta.get("ssh_targets") or [])
        if not any(t.get("name") == hostname or t.get("ip") == ip for t in targets):
            targets.append({"name": hostname, "ip": ip, "user": ssh_user})
            client_meta["ssh_targets"] = targets
            hosts["ssh_client"] = client_meta


def unregister_terminal_ssh_host(
    session_id: str,
    *,
    hostname: str = "",
    ip: str = "",
) -> None:
    """Remove a peer from terminal host maps after power-off / terminate."""
    hostname = (hostname or "").strip()
    ip = (ip or "").strip()
    if not hostname and not ip:
        return
    try:
        from .shell import get_sim_session
    except Exception:
        return
    entry = get_sim_session(str(session_id))
    if not entry:
        return
    state = entry.setdefault("state", {})
    hosts = state.setdefault("hosts", {})
    host_ips = state.setdefault("host_ips", {})
    # Drop by hostname and/or IP.
    if hostname and hostname in hosts:
        meta = hosts.pop(hostname) or {}
        if not ip and isinstance(meta, dict):
            ip = str(meta.get("ip") or "")
    drop_ips = [k for k, v in list(host_ips.items()) if (ip and k == ip) or (hostname and v == hostname)]
    for k in drop_ips:
        host_ips.pop(k, None)
    if ip:
        host_ips.pop(ip, None)

    def _unwire(shell) -> None:
        if shell is None:
            return
        shell._host_names = dict(hosts)
        shell._host_ips = dict(host_ips)

    engine = state.get("engine")
    if engine is not None:
        _unwire(getattr(engine, "shell", None))
    _unwire(state.get("ssh_client_shell"))


def sync_awx_inventory(session_id: str, hosts: list[dict] | None) -> None:
    """Mirror AWX inventory hosts into this session's LabServer registry."""
    for host in hosts or []:
        if not isinstance(host, dict):
            continue
        name = (host.get("name") or "").strip()
        if not name:
            continue
        hid = host.get("id") or name
        enabled = host.get("enabled", True)
        status = (host.get("status") or "ok").lower()
        power = "on" if enabled and status in ("ok", "ready", "successful") else "off"
        upsert_server(
            session_id,
            {
                "id": f"awx-{hid}",
                "hostname": name.split(".")[0] if "." in name else name,
                "fqdn": name if "." in name else f"{name}.corp.local",
                "primary_ip": host.get("ip") or "",
                "power": power,
                "os": host.get("guest_os") or "rhel-9",
                "tags": {
                    "role": "inventory",
                    "persona": "awx",
                    "inventory": host.get("inventory") or "",
                    "appears_in": ["awx", "terminal"],
                    "source_label": host.get("source") or "AWX",
                },
            },
            source="awx",
        )


def sync_monitoring_targets(session_id: str, targets: list[dict] | None) -> None:
    """Mirror Prometheus scrape targets into this session's LabServer registry."""
    for target in targets or []:
        if not isinstance(target, dict):
            continue
        labels = target.get("labels") or {}
        instance = (target.get("instance") or labels.get("instance") or "").strip()
        host_label = (labels.get("host") or labels.get("hostname") or "").strip()
        if not instance and not host_label:
            continue
        ip = instance.split(":")[0] if instance else ""
        hostname = host_label or (f"ip-{ip.replace('.', '-')}" if ip else instance)
        health = (target.get("health") or "up").lower()
        upsert_server(
            session_id,
            {
                "id": f"mon-{hostname}",
                "hostname": hostname,
                "primary_ip": ip,
                "power": "on" if health == "up" else "off",
                "os": "rhel-9",
                "tags": {
                    "role": "monitored",
                    "persona": "prometheus",
                    "job": target.get("job") or labels.get("job") or "",
                    "appears_in": ["grafana", "prometheus", "terminal"],
                },
            },
            source="monitoring",
        )


def sync_windows_host(session_id: str, world: dict | None) -> dict | None:
    """Mirror the Windows Server console host into LabServer identity."""
    if not isinstance(world, dict):
        return None
    computer = (world.get("computer_name") or "WIN-DC01").strip()
    session = world.get("session") or {}
    locked = bool(session.get("locked"))
    logged_in = bool(session.get("logged_in", True))
    power = "off" if locked and not logged_in else "on"
    nics = []
    for iface in (world.get("network") or {}).get("adapters") or []:
        if isinstance(iface, dict) and iface.get("name"):
            nics.append({
                "name": iface.get("name"),
                "mac": iface.get("mac") or "",
                "connected": bool(iface.get("connected", True)),
                "ip": iface.get("ip") or "",
            })
    primary_ip = ""
    for nic in nics:
        if nic.get("ip"):
            primary_ip = str(nic["ip"]).split("/")[0]
            break
    patch: dict[str, Any] = {
        "id": f"windows-{computer}",
        "hostname": computer,
        "primary_ip": primary_ip or "10.20.60.10",
        "power": power,
        "os": world.get("os") or "windows-server-2022",
        "tags": {
            "role": "primary",
            "persona": "windows",
            "appears_in": ["windows", "terminal"],
            "domain": ((world.get("domain") or {}).get("name") or ""),
        },
    }
    if nics:
        patch["nics"] = nics
    return upsert_server(session_id, patch, source="windows")


def _parse_k8s_cpu(value: str | None) -> int:
    raw = (value or "4").strip().lower()
    try:
        if raw.endswith("m"):
            return max(1, int(raw[:-1]) // 1000)
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        return 4


def _parse_k8s_mem_mb(value: str | None) -> int:
    raw = (value or "8192Mi").strip()
    try:
        if raw.endswith("Gi"):
            return int(float(raw[:-2]) * 1024)
        if raw.endswith("Mi"):
            return int(float(raw[:-2]))
        if raw.endswith("Ki"):
            return max(1, int(float(raw[:-2]) / 1024))
        return int(float(raw))
    except (TypeError, ValueError):
        return 8192


def sync_commvault_clients(session_id: str, clients: list[dict] | None) -> None:
    """Mirror CommCell clients into this session's LabServer registry.

    A client's backup protection status is metadata (tags), not power — the
    client's online/offline status IS its power, since a client that's offline
    to Commvault is the same underlying host being unreachable everywhere else.
    """
    for client in clients or []:
        if not isinstance(client, dict):
            continue
        name = (client.get("name") or "").strip()
        if not name:
            continue
        status = (client.get("status") or "online").lower()
        upsert_server(
            session_id,
            {
                "id": f"cv-{name}",
                "hostname": name,
                "primary_ip": client.get("ip") or "",
                "power": "on" if status == "online" else "off",
                "os": client.get("os") or "rhel-9",
                "tags": {
                    "role": "protected_client",
                    "persona": "commvault",
                    "backup_health": client.get("backup_health") or "",
                    "appears_in": ["commvault", "terminal"],
                },
            },
            source="commvault",
        )


def sync_netapp_storage(session_id: str, state: dict | None) -> None:
    """Mirror the ONTAP cluster's capacity/health facts onto its LabServer.

    NetApp's LabServer represents the storage controller itself (seeded via
    the "netapp" persona); volumes/aggregates are storage facts about that
    one server, not separate LabServers — a volume is not a host.
    """
    if not isinstance(state, dict):
        return
    cluster = (state.get("clusters") or [{}])[0] if state.get("clusters") else {}
    volumes = state.get("volumes") or []
    near_full = [v.get("name") for v in volumes if isinstance(v, dict)
                 and v.get("size_gb") and v.get("used_gb", 0) / max(1, v["size_gb"]) >= 0.9]
    upsert_server(
        session_id,
        {
            "id": "netapp-storage",
            "hostname": (state.get("summary") or {}).get("cluster") or "fixitlab-cluster",
            "power": "on" if (cluster or {}).get("health", "ok") != "down" else "off",
            "os": "ontap",
            "tags": {
                "role": "storage_controller",
                "persona": "netapp",
                "volumes_total": len(volumes),
                "volumes_near_full": ",".join(v for v in near_full if v) or "",
                "appears_in": ["netapp"],
            },
        },
        source="netapp",
    )


def sync_dellemc_storage(session_id: str, state: dict | None) -> None:
    """Mirror the PowerMax/Unisphere array's capacity/masking facts onto its LabServer."""
    if not isinstance(state, dict):
        return
    array = (state.get("arrays") or [{}])[0] if state.get("arrays") else {}
    volumes = state.get("volumes") or []
    unmapped = [v.get("id") for v in volumes if isinstance(v, dict) and not v.get("storage_group")]
    upsert_server(
        session_id,
        {
            "id": "dellemc-storage",
            "hostname": array.get("id") or "powermax-array",
            "power": "on" if (array or {}).get("health", "normal") != "critical" else "off",
            "os": "powermax-os",
            "tags": {
                "role": "storage_array",
                "persona": "dellemc",
                "volumes_total": len(volumes),
                "volumes_unmapped": ",".join(v for v in unmapped if v) or "",
                "masking_views": len(state.get("masking_views") or []),
                "appears_in": ["dellemc"],
            },
        },
        source="dellemc",
    )


def sync_soc_assets(session_id: str, assets: list[dict] | None) -> None:
    """Mirror SOC-monitored assets into this session's LabServer registry.

    Quarantining a host in the SOC console is a real network-isolation event —
    it flips the SAME underlying host's power/reachability, consistent with
    how a real EDR network-isolate action would look from every other console
    (terminal, monitoring) reading that host's state.
    """
    for asset in assets or []:
        if not isinstance(asset, dict):
            continue
        name = (asset.get("name") or "").strip()
        if not name:
            continue
        quarantined = bool(asset.get("quarantined"))
        upsert_server(
            session_id,
            {
                "id": f"soc-{name}",
                "hostname": name,
                "primary_ip": asset.get("ip") or "",
                "power": "off" if quarantined else "on",
                "os": "rhel-9",
                "tags": {
                    "role": "monitored_asset",
                    "persona": "soc",
                    "risk": asset.get("risk") or "",
                    "quarantined": quarantined,
                    "appears_in": ["soc", "terminal"],
                },
            },
            source="soc",
        )


def sync_azure_vm(session_id: str, vm: dict | None, *, vm_sizes: dict | None = None) -> dict | None:
    """Mirror an Azure console VM into this session's LabServer registry and
    make it SSH-reachable from the lab terminal."""
    if not isinstance(vm, dict):
        return None
    size_info = (vm_sizes or {}).get(vm.get("size") or "", {})
    power = vm.get("power_state") or "running"
    hostname = vm.get("name") or "azure-vm"
    private_ip = vm.get("private_ip") or ""
    patch: dict[str, Any] = {
        "id": f"azure-{hostname}",
        "hostname": hostname,
        "primary_ip": private_ip,
        "cpu": size_info.get("vcpus") or 2,
        "mem_mb": int(size_info.get("ram_gb") or 4) * 1024,
        "power": "on" if power in ("running", "starting") else ("reboot_pending" if power == "restarting" else "off"),
        "os": vm.get("os") or "linux",
        "tags": {
            "role": "primary" if not vm.get("lab_managed") else "cloud-vm",
            "persona": "azure",
            "size": vm.get("size") or "",
            "resource_group": vm.get("resource_group") or "",
            "appears_in": ["azure", "terminal"],
        },
    }
    server = upsert_server(session_id, patch, source="azure")
    if private_ip and power in ("running", "starting"):
        register_terminal_ssh_host(
            session_id, hostname=hostname, ip=private_ip, ssh_user="azureuser", source="azure",
        )
    return server


def sync_gcp_instance(session_id: str, instance: dict | None, *, machine_types: dict | None = None) -> dict | None:
    """Mirror a GCP Compute Engine instance into this session's LabServer
    registry and make it SSH-reachable from the lab terminal."""
    if not isinstance(instance, dict):
        return None
    size_info = (machine_types or {}).get(instance.get("machine_type") or "", {})
    status = instance.get("status") or "RUNNING"
    hostname = instance.get("name") or "gcp-vm"
    internal_ip = instance.get("internal_ip") or ""
    patch: dict[str, Any] = {
        "id": f"gcp-{hostname}",
        "hostname": hostname,
        "primary_ip": internal_ip,
        "cpu": size_info.get("vcpus") or 2,
        "mem_mb": int(size_info.get("ram_gb") or 4) * 1024,
        "power": "on" if status in ("RUNNING", "PROVISIONING") else ("reboot_pending" if status == "REPAIRING" else "off"),
        "os": instance.get("os") or "linux",
        "tags": {
            "role": "primary" if not instance.get("lab_managed") else "cloud-vm",
            "persona": "gcp",
            "machine_type": instance.get("machine_type") or "",
            "zone": instance.get("zone") or "",
            "appears_in": ["gcp", "terminal"],
        },
    }
    server = upsert_server(session_id, patch, source="gcp")
    if internal_ip and status in ("RUNNING", "PROVISIONING"):
        register_terminal_ssh_host(
            session_id, hostname=hostname, ip=internal_ip, ssh_user="ubuntu", source="gcp",
        )
    return server


def sync_openstack_instance(session_id: str, instance: dict | None, *, flavors: dict | None = None) -> dict | None:
    """Mirror a Nova instance into this session's LabServer registry and
    make it SSH-reachable from the lab terminal."""
    if not isinstance(instance, dict):
        return None
    size_info = (flavors or {}).get(instance.get("flavor") or "", {})
    status = (instance.get("status") or "ACTIVE").upper()
    hostname = instance.get("name") or "openstack-vm"
    private_ip = instance.get("private_ip") or ""
    power_on = status in ("ACTIVE", "BUILD", "REBOOT") or instance.get("power_state") == "Running"
    patch: dict[str, Any] = {
        "id": f"openstack-{hostname}",
        "hostname": hostname,
        "primary_ip": private_ip,
        "cpu": size_info.get("vcpus") or 2,
        "mem_mb": int(size_info.get("ram_gb") or 4) * 1024,
        "power": "on" if power_on else "off",
        "os": "linux",
        "tags": {
            "role": "primary" if not instance.get("lab_managed") else "cloud-vm",
            "persona": "openstack",
            "flavor": instance.get("flavor") or "",
            "appears_in": ["openstack", "terminal"],
        },
    }
    server = upsert_server(session_id, patch, source="openstack")
    if private_ip and power_on:
        register_terminal_ssh_host(
            session_id, hostname=hostname, ip=private_ip, ssh_user="ubuntu", source="openstack",
        )
    return server


def sync_aws_instance(session_id: str, instance: dict | None, *, instance_types: dict | None = None) -> dict | None:
    """Mirror an AWS EC2 instance into this session's LabServer registry.

    Terminal Hosted as: AWS EC2 Instance. Power/state follows EC2 lifecycle.
    """
    if not isinstance(instance, dict):
        return None
    itype = instance.get("type") or instance.get("instance_type") or "t2.micro"
    size_info = (instance_types or {}).get(itype, {})
    state = (instance.get("state") or "running").lower()
    hostname = instance.get("name") or instance.get("id") or "ec2-instance"
    private_ip = instance.get("privateIp") or instance.get("private_ip") or ""
    public_ip = instance.get("publicIp") or instance.get("public_ip") or ""
    power_on = state in ("running", "pending", "rebooting")
    patch: dict[str, Any] = {
        "id": f"aws-{instance.get('id') or hostname}",
        "hostname": str(hostname).replace(" ", "-")[:48] or "ec2-instance",
        "primary_ip": private_ip or public_ip,
        "cpu": size_info.get("vcpus") or size_info.get("vcpu") or 2,
        "mem_mb": int(size_info.get("ram_gb") or size_info.get("memory_gb") or 1) * 1024,
        "power": "on" if power_on else ("reboot_pending" if state == "rebooting" else "off"),
        "os": instance.get("os") or "linux",
        "tags": {
            "role": "primary",
            "persona": "aws",
            "instance_id": instance.get("id") or "",
            "instance_type": itype,
            "az": instance.get("az") or "",
            "appears_in": ["aws", "terminal"],
        },
    }
    server = upsert_server(session_id, patch, source="aws")
    if (private_ip or public_ip) and power_on:
        register_terminal_ssh_host(
            session_id,
            hostname=patch["hostname"],
            ip=private_ip or public_ip,
            ssh_user="ec2-user",
            source="aws",
        )
    return server


def sync_k8s_nodes(session_id: str, nodes: list[dict] | None) -> None:
    """Mirror Kubernetes cluster nodes into this session's LabServer registry."""
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        name = (node.get("name") or "").strip()
        if not name:
            continue
        status = (node.get("status") or "Unknown").lower()
        roles = node.get("roles") or []
        role = "control-plane" if any("control" in str(r) or r == "master" for r in roles) else "worker"
        power = "on" if status == "ready" else "off"
        upsert_server(
            session_id,
            {
                "id": f"k8s-{name}",
                "hostname": name,
                "primary_ip": node.get("internal_ip") or node.get("ip") or "",
                "cpu": _parse_k8s_cpu(node.get("cpu_capacity")),
                "mem_mb": _parse_k8s_mem_mb(node.get("mem_capacity")),
                "power": power,
                "os": "rhel-9",
                "tags": {
                    "role": role,
                    "persona": "kubernetes",
                    "k8s_status": node.get("status") or "",
                    "drain_state": node.get("drain_state") or "",
                    "appears_in": ["kubernetes", "terminal"],
                },
            },
            source="kubernetes",
        )


# Persona defaults for scenario-scoped LabServer seeding (terminal = this host).
_PERSONA_DEFAULTS: dict[str, dict[str, Any]] = {
    "linux": {"hostname": "lab-server", "primary_ip": "10.20.30.41", "os": "rhel-9", "source": "linux"},
    "ansible": {"hostname": "ansible-control", "primary_ip": "10.20.30.50", "os": "rhel-9", "source": "ansible"},
    "gpu": {"hostname": "gpu-node-01", "primary_ip": "10.20.40.10", "os": "rhel-9", "source": "gpu", "cpu": 64, "mem_mb": 524288},
    "kubernetes": {"hostname": "k8s-master", "primary_ip": "10.20.50.10", "os": "rhel-9", "source": "kubernetes"},
    "windows": {"hostname": "WIN-DC01", "primary_ip": "10.20.60.10", "os": "windows-server-2022", "source": "windows"},
    "grafana": {"hostname": "mon-grafana-01", "primary_ip": "10.20.70.10", "os": "rhel-9", "source": "monitoring"},
    "prometheus": {"hostname": "mon-prom-01", "primary_ip": "10.20.70.11", "os": "rhel-9", "source": "monitoring"},
    "awx": {"hostname": "awx-controller", "primary_ip": "10.20.80.10", "os": "rhel-9", "source": "awx"},
    "terraform": {"hostname": "iac-runner", "primary_ip": "10.20.90.10", "os": "rhel-9", "source": "terraform"},
    "baremetal": {"hostname": "bm-node-01", "primary_ip": "10.20.100.10", "os": "rhel-9", "source": "baremetal"},
    "datacenter": {"hostname": "dc-srv-r12u10", "primary_ip": "10.20.110.10", "os": "rhel-9", "source": "datacenter"},
    "soc": {"hostname": "soc-sensor-01", "primary_ip": "10.20.120.10", "os": "rhel-9", "source": "soc"},
    "commvault": {"hostname": "cv-mediaagent-01", "primary_ip": "10.20.130.10", "os": "rhel-9", "source": "commvault"},
    "netapp": {"hostname": "ontap-cluster-01", "primary_ip": "10.20.140.10", "os": "ontap", "source": "netapp"},
    "dellemc": {"hostname": "powermax-array-01", "primary_ip": "10.20.150.10", "os": "powermax-os", "source": "dellemc"},
    "storage": {"hostname": "storage-array-01", "primary_ip": "10.20.160.10", "os": "storage-os", "source": "storage"},
    "azure": {"hostname": "vm-web01", "primary_ip": "10.10.1.4", "os": "linux", "source": "azure"},
    "gcp": {"hostname": "web01", "primary_ip": "10.128.0.4", "os": "linux", "source": "gcp"},
}


def _infer_persona(sim_type: str, slug: str) -> str:
    low = (slug or "").lower()
    st = (sim_type or "").lower()
    if st in _PERSONA_DEFAULTS:
        return st
    for key in _PERSONA_DEFAULTS:
        if key in low or key in st:
            return key
    if "nvidia" in low or "cuda" in low:
        return "gpu"
    if "k8s" in low or "kube" in low:
        return "kubernetes"
    if "awx" in low or "tower" in low:
        return "awx"
    if "win-" in low or "windows" in low:
        return "windows"
    return "linux"


def _scenarios_root() -> Path:
    # backend/apps/labs/provisioner/simulation/server_identity.py → repo root
    return Path(__file__).resolve().parents[5] / "scenarios"


def load_scenario_lab_server_decls(slug: str) -> list[dict[str, Any]]:
    """Load ``lab_servers`` from scenarios/**/<slug>/scenario.yaml when present."""
    if not slug:
        return []
    root = _scenarios_root()
    if not root.is_dir():
        return []
    path = None
    for candidate in root.rglob("scenario.yaml"):
        if candidate.parent.name == slug:
            path = candidate
            break
    if path is None:
        return []
    try:
        import yaml  # local optional; scenarios already require PyYAML in tooling
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        logger.debug("Could not parse scenario YAML for %s", slug, exc_info=True)
        return []
    decls = data.get("lab_servers") or []
    return [d for d in decls if isinstance(d, dict)]


def _seed_from_lab_server_decls(
    session_id: str,
    decls: list[dict[str, Any]],
    *,
    slug: str = "",
    engine=None,
) -> dict | None:
    """Materialize YAML-declared LabServers into this session."""
    sid = str(session_id)
    primary: dict | None = None
    for decl in decls:
        persona = str(decl.get("persona") or "linux").lower()
        defaults = dict(_PERSONA_DEFAULTS.get(persona, _PERSONA_DEFAULTS["linux"]))
        hostname = str(decl.get("hostname") or defaults["hostname"])
        role = str(decl.get("role") or "secondary")
        server_id = str(decl.get("id") or f"{defaults['source']}-{hostname}")
        primary_ip = str(decl.get("primary_ip") or defaults["primary_ip"])
        # Prefer explicit YAML hostname; only pull IP from the live shell for primary.
        if role == "primary" and engine and getattr(engine, "shell", None):
            st = engine.shell.state
            if not decl.get("hostname"):
                hostname = getattr(st, "hostname", None) or hostname
            nics = getattr(st, "nics", None) or []
            for nic in nics:
                ip = getattr(nic, "ip", None) if not isinstance(nic, dict) else nic.get("ip")
                if ip:
                    primary_ip = str(ip).split("/")[0]
                    break
        patch: dict[str, Any] = {
            "id": server_id,
            "hostname": hostname,
            "primary_ip": primary_ip,
            "os": decl.get("os") or defaults.get("os", "rhel-9"),
            "cpu": decl.get("cpu") or defaults.get("cpu", 4),
            "mem_mb": decl.get("mem_mb") or defaults.get("mem_mb", 8192),
            "tags": {
                "role": role if role != "secondary" else ("primary" if primary is None else role),
                "persona": persona,
                "scenario": slug or "",
                "appears_in": decl.get("appears_in") or [],
            },
        }
        loc = decl.get("physical_location")
        if isinstance(loc, dict):
            patch["physical_location"] = loc
        elif persona in ("baremetal", "datacenter"):
            patch["physical_location"] = {
                "room": "Data Hall A",
                "rack": "R12",
                "u_position": 10,
            }
        if persona in ("baremetal", "datacenter") or patch.get("physical_location"):
            patch.setdefault(
                "bmc",
                {
                    "endpoint": f"https://bmc-{hostname}.corp.local",
                    "protocol": "redfish",
                    "power": "on",
                    "sensors": {"inlet_c": 22.0},
                },
            )
        rec = upsert_server(sid, patch, source=defaults.get("source", "lab"))
        if role == "primary" or primary is None:
            if role == "primary":
                primary = rec
            elif primary is None:
                primary = rec
    return primary or get_primary(sid)


def seed_scenario_lab_servers(
    session_id: str,
    *,
    sim_type: str = "generic",
    slug: str = "",
    engine=None,
    force: bool = False,
    lab_servers: list[dict[str, Any]] | None = None,
) -> dict | None:
    """Ensure this lab session has LabServer(s) for the scenario persona.

    Prefer ``lab_servers`` from the scenario YAML (scenario-scoped hosts). Falls
    back to a single persona default. Skips if VMware/AWS/GPU dedicated seeders
    already created a primary, unless ``force`` is True. Never creates a
    platform-global server.
    """
    sid = str(session_id)
    if not force and get_primary(sid):
        return get_primary(sid)

    persona = _infer_persona(sim_type, slug)
    # Dedicated paths already ran for these.
    if persona in ("aws",) or (sim_type or "").lower() == "aws":
        return get_primary(sid)
    if persona == "gpu" or "gpu" in (slug or "").lower():
        healthy = bool(getattr(getattr(engine, "shell", None), "state", None) and getattr(engine.shell.state, "gpu_healthy", False))
        hostname = "gpu-node-01"
        if engine and getattr(engine, "shell", None):
            hostname = getattr(engine.shell.state, "hostname", None) or hostname
        return seed_gpu_node(sid, hostname=hostname, healthy=healthy)

    decls = lab_servers if lab_servers is not None else load_scenario_lab_server_decls(slug)
    if decls:
        return _seed_from_lab_server_decls(sid, decls, slug=slug, engine=engine)

    defaults = dict(_PERSONA_DEFAULTS.get(persona, _PERSONA_DEFAULTS["linux"]))
    hostname = defaults["hostname"]
    primary_ip = defaults["primary_ip"]
    if engine and getattr(engine, "shell", None):
        st = engine.shell.state
        hostname = getattr(st, "hostname", None) or hostname
        # Prefer first NIC IP from the shell if present.
        nics = getattr(st, "nics", None) or []
        for nic in nics:
            ip = getattr(nic, "ip", None) if not isinstance(nic, dict) else nic.get("ip")
            if ip:
                primary_ip = str(ip).split("/")[0]
                break

    patch: dict[str, Any] = {
        "id": f"{defaults['source']}-{hostname}",
        "hostname": hostname,
        "primary_ip": primary_ip,
        "os": defaults.get("os", "rhel-9"),
        "cpu": defaults.get("cpu", 4),
        "mem_mb": defaults.get("mem_mb", 8192),
        "tags": {"role": "primary", "persona": persona, "scenario": slug or ""},
    }
    if persona == "baremetal" or persona == "datacenter":
        patch["physical_location"] = {
            "room": "Data Hall A",
            "rack": "R12",
            "u_position": 10,
        }
        patch["bmc"] = {
            "endpoint": f"https://bmc-{hostname}.corp.local",
            "protocol": "redfish",
            "power": "on",
            "sensors": {"inlet_c": 22.0},
        }
    return upsert_server(sid, patch, source=defaults.get("source", "lab"))
