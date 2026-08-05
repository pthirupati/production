"""In-memory MAAS / LXD / KVM bare-metal Lab Environment for training labs.

MAAS machines model a real commissioning/deploy lifecycle that advances on
wall-clock time (New -> Commissioning -> Ready -> Allocated -> Deploying ->
Deployed, plus Failed / Releasing / Broken / Testing / Rescue mode).  A machine
started commissioning at t0 keeps advancing even when no request comes in —
every read/action/validate calls ``_tick`` which recomputes status + progress
from ``time.time()`` deltas.

Grading (``validate_baremetal_lab``) is unchanged in contract: the lab passes
only when the ``broken`` map is empty.  The ``broken`` flags are cleared by the
action that *initiates* the fix (commission / deploy / start / power-on), so a
learner who kicks off the right action grades as complete; the visible machine
status advances afterwards over wall-clock to look realistic.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

from .baremetal_v2_facades import apply_v2_action, ensure_v2
from . import packer_factory

SESSION_TTL = 7200

# Wall-clock durations (seconds) for each async phase.  Kept short so a learner
# sees the machine reach the terminal state within a single lab sitting.
COMMISSION_SECONDS = 18
DEPLOY_SECONDS = 22
TEST_SECONDS = 6
RELEASE_SECONDS = 3
RESCUE_SECONDS = 4

# Canonical MAAS lifecycle order used for detail-view rendering / validation.
LIFECYCLE = [
    "New",
    "Commissioning",
    "Failed commissioning",
    "Ready",
    "Allocated",
    "Deploying",
    "Deployed",
    "Failed deployment",
    "Releasing",
    "Broken",
    "Testing",
    "Rescue mode",
    "Failed",
]

_GPU_HOST_HINTS = ("gpu", "h100", "h200", "b300", "mi300")

# Legacy/alternate action names accepted from the frontend, normalized to the
# canonical action handled below.
_ALIASES = {
    "maas_dhcp_configure": "maas_dhcp_toggle",
    "maas_add_zone": "maas_create_zone",
    "maas_add_pool": "maas_create_pool",
}


def _session_key(session_id: str) -> str:
    return f"baremetal_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)
    _notify_session(session_id)


def _notify_session(session_id: str) -> None:
    """Best-effort push to any open baremetal WebSocket for this session."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"baremetal_{session_id}",
            {"type": "baremetal.push", "session_id": str(session_id)},
        )
    except Exception:
        pass


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now() -> float:
    return time.time()


def _log(machine: dict, message: str) -> None:
    machine.setdefault("log", []).append({"time": _now_iso(), "message": message})
    # Keep the boot/commissioning log bounded.
    if len(machine["log"]) > 40:
        machine["log"] = machine["log"][-40:]


def _machine_event(machine: dict, message: str) -> None:
    """Append a machine-level event (separate from the boot/commissioning log)."""
    machine.setdefault("events", []).append({"time": _now_iso(), "message": message})
    if len(machine["events"]) > 40:
        machine["events"] = machine["events"][-40:]


def _is_gpu_host(hostname: str) -> bool:
    h = (hostname or "").lower()
    return any(hint in h for hint in _GPU_HOST_HINTS)


def _default_interfaces(mid: int) -> list[dict]:
    return [
        {
            "name": "eth0",
            "mac": f"52:54:00:aa:bb:{mid:02d}",
            "link": "up",
            "vlan": "pxe",
            "fabric": "fabric-0",
            "subnet": "10.10.1.0/24",
            "ip_mode": "auto",
            "link_speed": 25000,
            "is_boot": True,
        },
        {
            "name": "eth1",
            "mac": f"52:54:00:cc:dd:{mid:02d}",
            "link": "down",
            "vlan": "mgmt",
            "fabric": "fabric-0",
            "subnet": "10.10.1.0/24",
            "ip_mode": "unconfigured",
            "link_speed": 1000,
            "is_boot": False,
        },
    ]


def _default_storage() -> list[dict]:
    return [
        {"name": "sda", "size_gb": 480, "type": "SSD", "role": "root"},
        {"name": "sdb", "size_gb": 1920, "type": "NVMe", "role": "unused"},
    ]


def _storage_totals(storage: list[dict] | None) -> tuple[int, int]:
    disks = storage or []
    return len(disks), int(sum(float(d.get("size_gb") or 0) for d in disks))


def _enrich_iface(iface: dict) -> None:
    iface.setdefault("fabric", "fabric-0")
    iface.setdefault("subnet", "10.10.1.0/24")
    iface.setdefault("ip_mode", "auto" if iface.get("name") == "eth0" else "unconfigured")
    iface.setdefault("link_speed", 25000 if iface.get("name") == "eth0" else 1000)
    iface.setdefault("is_boot", iface.get("name") == "eth0")


def _machine(mid: int, hostname: str, status: str, power: str, ip: str) -> dict:
    """Build a machine record with lifecycle + Canonical-like MAAS detail fields."""
    storage = _default_storage()
    disk_count, storage_gb = _storage_totals(storage)
    ready_like = status in ("Ready", "Deployed", "Allocated")
    # PCI / GPU inventory is empty until commissioning completes (Ready+).
    pci_devices: list[dict] = []
    commissioning_results: list[dict] = []
    if ready_like:
        pci_devices = _build_pci_inventory(hostname)
        commissioning_results = _default_commissioning_results(hostname)
    return {
        "id": mid,
        "hostname": hostname,
        "status": status,
        "power": power,
        "ip": ip,
        "progress": 100 if ready_like else 0,
        "phase_started_at": None,
        "phase_duration": 0,
        "arch": "amd64/generic",
        "cpu_count": 32,
        "ram_gb": 256,
        "os": "Ubuntu 22.04 LTS" if status == "Deployed" else "",
        "owner": "",
        "pool": "default",
        "zone": "default",
        "locked": False,
        "tags": [],
        "fabric": "fabric-0",
        "domain": "maas",
        "power_type": "ipmi",
        "bmc_address": f"10.20.0.{100 + mid}",
        "bmc_user": "maas",
        "disk_count": disk_count,
        "storage_gb": storage_gb,
        "pci_devices": pci_devices,
        "usb_devices": [],
        "events": [],
        "commissioning_results": commissioning_results,
        "test_results": [],
        "storage_layout": "flat",
        "interfaces": _default_interfaces(mid),
        "storage": storage,
        "log": [],
    }


def _build_pci_inventory(hostname: str) -> list[dict]:
    pci = [
        {"slot": "0000:00:00.0", "vendor": "Intel Corporation", "product": "Host Bridge", "type": "bridge"},
        {"slot": "0000:00:1f.2", "vendor": "Intel Corporation", "product": "SATA Controller", "type": "storage"},
        {"slot": "0000:01:00.0", "vendor": "Mellanox Technologies", "product": "ConnectX-6 Dx", "type": "network"},
        {"slot": "0000:02:00.0", "vendor": "Mellanox Technologies", "product": "ConnectX-6 Dx", "type": "network"},
    ]
    if _is_gpu_host(hostname):
        product = "H100"
        hl = (hostname or "").lower()
        if "h200" in hl:
            product = "H200"
        elif "b300" in hl:
            product = "B300"
        elif "mi300" in hl:
            product = "Instinct MI300X"
        vendor = "AMD" if "mi300" in hl else "NVIDIA"
        for i in range(8):
            pci.append({
                "slot": f"0000:{0x10 + i:02x}:00.0",
                "vendor": vendor,
                "product": product,
                "type": "gpu",
            })
    return pci


def _default_commissioning_results(hostname: str) -> list[dict]:
    results = [
        {"name": "00-maas-01-dhcp-nic", "status": "passed", "runtime": 1.2},
        {"name": "20-maas-hardware-info", "status": "passed", "runtime": 4.5},
        {"name": "30-maas-01-bmc-config", "status": "passed", "runtime": 2.1},
        {"name": "50-maas-01-cpu-firmware", "status": "passed", "runtime": 3.0},
    ]
    if _is_gpu_host(hostname):
        results.append({"name": "50-fixitlab-gpu-check", "status": "passed", "runtime": 6.0})
    return results


def _enrich_machine(m: dict) -> None:
    """Backfill Canonical-like fields on machines from older Lab sessions."""
    mid = int(m.get("id") or 0)
    m.setdefault("owner", "")
    m.setdefault("pool", "default")
    m.setdefault("zone", "default")
    m.setdefault("locked", False)
    m.setdefault("tags", [])
    m.setdefault("fabric", "fabric-0")
    m.setdefault("domain", "maas")
    m.setdefault("power_type", "ipmi")
    m.setdefault("bmc_address", f"10.20.0.{100 + mid}")
    m.setdefault("bmc_user", "maas")
    m.setdefault("usb_devices", [])
    m.setdefault("events", [])
    m.setdefault("commissioning_results", [])
    m.setdefault("test_results", [])
    m.setdefault("storage_layout", "flat")
    m.setdefault("pci_devices", [])
    if not m.get("storage"):
        m["storage"] = _default_storage()
    if not m.get("interfaces"):
        m["interfaces"] = _default_interfaces(mid)
    for iface in m.get("interfaces") or []:
        _enrich_iface(iface)
    disk_count, storage_gb = _storage_totals(m.get("storage"))
    m["disk_count"] = disk_count
    m["storage_gb"] = storage_gb


def _apply_storage_layout(m: dict, layout: str) -> None:
    layout = (layout or "flat").lower().strip()
    if layout not in ("flat", "lvm", "bcache", "raid10"):
        layout = "flat"
    m["storage_layout"] = layout
    storage = list(m.get("storage") or _default_storage())
    if not storage:
        storage = _default_storage()
    if layout == "flat":
        for i, d in enumerate(storage):
            d["role"] = "root" if i == 0 else "unused"
            d.pop("vg", None)
            d.pop("cache_for", None)
            d.pop("raid", None)
    elif layout == "lvm":
        for d in storage:
            d["role"] = "lvm-pv"
            d["vg"] = "vgroot"
            d.pop("cache_for", None)
            d.pop("raid", None)
    elif layout == "bcache":
        # Fastest disk as cache, rest as backing.
        by_size = sorted(storage, key=lambda d: float(d.get("size_gb") or 0))
        cache_disk = by_size[0]
        for d in storage:
            if d is cache_disk or d.get("name") == cache_disk.get("name"):
                d["role"] = "bcache-cache"
                d.pop("vg", None)
                d.pop("raid", None)
            else:
                d["role"] = "bcache-backing"
                d["cache_for"] = cache_disk.get("name")
                d.pop("vg", None)
                d.pop("raid", None)
    elif layout == "raid10":
        for d in storage:
            d["role"] = "raid-member"
            d["raid"] = "raid10"
            d.pop("vg", None)
            d.pop("cache_for", None)
        if len(storage) < 4:
            # Pad to a minimal RAID10 set for the Lab Environment.
            for i in range(len(storage), 4):
                storage.append({
                    "name": f"sd{chr(ord('a') + i)}",
                    "size_gb": 480,
                    "type": "SSD",
                    "role": "raid-member",
                    "raid": "raid10",
                })
    m["storage"] = storage
    disk_count, storage_gb = _storage_totals(storage)
    m["disk_count"] = disk_count
    m["storage_gb"] = storage_gb


def _fill_commission_complete(m: dict) -> None:
    """Inventory + commissioning results when Commissioning → Ready."""
    hostname = m.get("hostname") or ""
    m["pci_devices"] = _build_pci_inventory(hostname)
    m["commissioning_results"] = _default_commissioning_results(hostname)
    _machine_event(m, "Node changed status - Ready")
    if not m.get("storage") or len(m.get("storage") or []) < 1:
        m["storage"] = _default_storage()
    mid = int(m.get("id") or 0)
    if not m.get("interfaces") or len(m.get("interfaces") or []) < 2:
        m["interfaces"] = _default_interfaces(mid)
    for iface in m.get("interfaces") or []:
        _enrich_iface(iface)
        if iface.get("name") == "eth0":
            iface["link"] = "up"
            iface["ip_mode"] = iface.get("ip_mode") or "auto"
    disk_count, storage_gb = _storage_totals(m.get("storage"))
    m["disk_count"] = disk_count
    m["storage_gb"] = storage_gb


def _clear_phase(m: dict) -> None:
    m["phase_started_at"] = None
    m["phase_duration"] = 0
    m["progress"] = 100 if m.get("status") in ("Ready", "Deployed", "Allocated", "Broken") else 0


def _machine_ids_from_payload(payload: dict, broken: dict, *, default: int = 2) -> list[int]:
    ids = payload.get("machine_ids")
    if ids:
        return [int(x) for x in ids]
    if payload.get("machine_id") is not None:
        return [int(payload["machine_id"])]
    return [int(broken.get("machine_needs_commission") or default)]


def _maas_infra_seed() -> dict:
    """Canonical-like MAAS region/rack infra for the Lab Environment UI."""
    return {
        "controllers": [
            {
                "name": "region-1",
                "type": "region",
                "version": "3.4.0",
                "services": {
                    "regiond": "ok",
                    "bind9": "ok",
                    "proxy": "ok",
                    "ntp": "ok",
                    "syslog": "ok",
                    "http": "ok",
                },
            },
            {
                "name": "rack-1",
                "type": "rack",
                "version": "3.4.0",
                "services": {
                    "rackd": "ok",
                    "dhcpd": "ok",
                    "tftp": "ok",
                    "http": "ok",
                    "ntp": "ok",
                    "proxy": "degraded",
                    "syslog": "ok",
                    "bind9": "ok",
                },
            },
        ],
        "domains": [
            {
                "name": "maas",
                "authoritative": True,
                "records": [
                    {"type": "A", "name": "region-1", "data": "10.10.1.2"},
                    {"type": "A", "name": "rack-1", "data": "10.10.1.3"},
                    {"type": "A", "name": "gpu-node-01", "data": "10.10.1.11"},
                ],
            },
        ],
        "zones": [
            {"name": "default", "description": "Default availability zone"},
            {"name": "az-a", "description": "Availability zone A"},
            {"name": "az-b", "description": "Availability zone B"},
        ],
        "resource_pools": [
            {"name": "default", "description": "Default resource pool", "machine_count": 3},
            {"name": "gpu", "description": "GPU training nodes", "machine_count": 2},
            {"name": "storage", "description": "Storage nodes", "machine_count": 1},
        ],
        "devices": [
            {
                "id": 101,
                "hostname": "pdu-rack-a",
                "ip": "10.10.1.50",
                "parent": None,
                "deployable": False,
                "ip_reservation": "10.10.1.50",
            },
            {
                "id": 102,
                "hostname": "mgmt-switch-01",
                "ip": "10.10.1.51",
                "parent": None,
                "deployable": False,
                "ip_reservation": "10.10.1.51",
            },
        ],
        "dhcp": {
            "enabled": True,
            "vlan": "pxe",
            "primary_rack": "rack-1",
            "dynamic_ranges": [{"start": "10.10.1.100", "end": "10.10.1.200"}],
            "snippets": [],
        },
        "settings": {
            "maas_name": "fixitlab",
            "maas_url": "http://10.10.1.2:5240/MAAS",
            "default_distro": "ubuntu/jammy",
            "default_osystem": "ubuntu",
            "ntp_servers": "ntp.ubuntu.com",
            "dns_forwarder": "8.8.8.8",
            "http_proxy": "",
            "upstream_dns": "8.8.8.8",
            "enable_http_proxy": False,
            "commissioning_distro_series": "jammy",
            "kernel_opts": "",
            "enable_disk_erasing_on_release": False,
            "network_discovery": "enabled",
            "syslog_host": "",
            "package_repositories": ["main", "restricted", "universe", "multiverse"],
            "default_min_hwe_kernel": "ga-22.04",
            "windows_kms_host": "",
            "hardware_sync_interval": "15m",
            "curtin_verbose": False,
            "apt_http_proxy": "",
            "maas_auto_ipmi_user": "maas",
            "maas_auto_ipmi_user_privilege_level": "ADMIN",
            "remote_syslog": "",
            "use_peer_proxy": False,
            "prefer_v4_proxy": True,
            "dnssec_validation": "auto",
            "active_discovery_interval": "10m",
        },
        "users": [
            {"username": "admin", "is_admin": True, "email": "admin@maas.local"},
            {"username": "operator", "is_admin": False, "email": "ops@maas.local"},
        ],
    }


def _ensure_maas_infra(state: dict) -> None:
    maas = state.setdefault("maas", {})
    seed = _maas_infra_seed()
    for key, value in seed.items():
        if key not in maas or maas.get(key) is None:
            maas[key] = value
    for m in maas.get("machines") or []:
        _enrich_machine(m)
    # Keep resource_pool machine_count roughly in sync.
    pools = {p.get("name"): p for p in maas.get("resource_pools") or []}
    if pools:
        counts: dict[str, int] = {}
        for m in maas.get("machines") or []:
            pname = m.get("pool") or "default"
            counts[pname] = counts.get(pname, 0) + 1
        for name, pool in pools.items():
            if name in counts:
                pool["machine_count"] = counts[name]


def _lxd_instance(
    name: str,
    *,
    status: str = "Stopped",
    itype: str = "container",
    ipv4: str = "",
    ipv6: str = "",
    image: str = "ubuntu:22.04",
    profiles: list | None = None,
    snapshots: list | None = None,
    devices: dict | None = None,
    config: dict | None = None,
    project: str = "default",
    location: str = "none",
    nvidia_smi_ok: bool = False,
) -> dict:
    """Canonical LXD instance row shared by GUI and CLI inventory."""
    return {
        "name": name,
        "status": status,
        "type": itype,
        "ipv4": ipv4,
        "ipv6": ipv6,
        "image": image,
        "profiles": list(profiles if profiles is not None else ["default"]),
        "snapshots": list(snapshots if snapshots is not None else []),
        "devices": dict(devices if devices is not None else {
            "root": {"path": "/", "pool": "default", "type": "disk"},
            "eth0": {"name": "eth0", "network": "lxdbr0", "type": "nic"},
        }),
        "config": dict(config if config is not None else {}),
        "project": project,
        "location": location,
        "nvidia_smi_ok": bool(nvidia_smi_ok),
    }


def _enrich_lxd_instance(inst: dict) -> dict:
    """Upgrade a legacy {name,status,ipv4,image} row to the full instance shape."""
    if not isinstance(inst, dict):
        return inst
    defaults = _lxd_instance(
        inst.get("name") or "unnamed",
        status=inst.get("status") or "Stopped",
        itype=inst.get("type") or "container",
        ipv4=inst.get("ipv4") or "",
        ipv6=inst.get("ipv6") or "",
        image=inst.get("image") or "ubuntu:22.04",
        profiles=inst.get("profiles"),
        snapshots=inst.get("snapshots"),
        devices=inst.get("devices"),
        config=inst.get("config"),
        project=inst.get("project") or "default",
        location=inst.get("location") or "none",
        nvidia_smi_ok=bool(inst.get("nvidia_smi_ok")),
    )
    for key, value in defaults.items():
        if key not in inst or inst.get(key) is None:
            inst[key] = value
    if not isinstance(inst.get("profiles"), list):
        inst["profiles"] = ["default"]
    if not isinstance(inst.get("snapshots"), list):
        inst["snapshots"] = []
    if not isinstance(inst.get("devices"), dict):
        inst["devices"] = defaults["devices"]
    if not isinstance(inst.get("config"), dict):
        inst["config"] = {}
    return inst


def _lxd_infra_seed() -> dict:
    return {
        "profiles": [
            {
                "name": "default",
                "description": "Default LXD profile",
                "config": {},
                "devices": {
                    "root": {"path": "/", "pool": "default", "type": "disk"},
                    "eth0": {"name": "eth0", "network": "lxdbr0", "type": "nic"},
                },
            },
            {
                "name": "gpu-passthrough",
                "description": "NVIDIA GPU passthrough",
                "config": {"nvidia.runtime": "true"},
                "devices": {
                    "gpu0": {"type": "gpu", "gputype": "physical", "pci": "0000:19:00.0"},
                },
            },
        ],
        "storage_pools": [
            {"name": "default", "driver": "dir", "source": "/var/snap/lxd/common/lxd/storage-pools/default", "used_by": 2},
            {"name": "gpu-pool", "driver": "zfs", "source": "tank/lxd", "used_by": 0},
        ],
        "networks": [
            {"name": "lxdbr0", "type": "bridge", "managed": True, "ipv4": "10.10.2.1/24", "ipv6": "fd42::1/64", "used_by": 2},
            {"name": "gpu-fabric", "type": "bridge", "managed": True, "ipv4": "10.150.0.1/24", "ipv6": "", "used_by": 0},
        ],
        "projects": [
            {"name": "default", "description": "Default LXD project", "used_by": 2},
            {"name": "inference", "description": "Inference workloads", "used_by": 0},
        ],
        "cluster": [
            {"name": "node1", "url": "https://10.64.12.11:8443", "roles": ["database"], "architecture": "x86_64", "failure_domain": "default", "status": "Online"},
            {"name": "node2", "url": "https://10.64.12.12:8443", "roles": ["database"], "architecture": "x86_64", "failure_domain": "default", "status": "Online"},
            {"name": "node3", "url": "https://10.64.12.13:8443", "roles": ["database-standby"], "architecture": "x86_64", "failure_domain": "default", "status": "Online"},
        ],
        "images": [
            {"alias": "ubuntu:22.04", "fingerprint": "a1b2c3d4e5f6", "public": True, "description": "ubuntu 22.04 LTS amd64 (cloud)", "architecture": "x86_64", "type": "container"},
            {"alias": "ubuntu:24.04", "fingerprint": "f6e5d4c3b2a1", "public": True, "description": "ubuntu 24.04 LTS amd64 (cloud)", "architecture": "x86_64", "type": "container"},
            {"alias": "ubuntu:22.04/vm", "fingerprint": "vm22aabbccdd", "public": True, "description": "ubuntu 22.04 LTS amd64 (VM)", "architecture": "x86_64", "type": "virtual-machine"},
        ],
        "operations": [],
        "settings": {
            "core.https_address": "[::]:8443",
            "core.trust_password": True,
            "images.auto_update_interval": "6",
            "cluster.https_address": "10.64.12.11:8443",
        },
    }


def _normalize_lxd_profiles(lxd: dict) -> None:
    """Accept legacy string profile names and upgrade to profile dicts."""
    profiles = lxd.get("profiles")
    if not profiles:
        lxd["profiles"] = _lxd_infra_seed()["profiles"]
        return
    if profiles and isinstance(profiles[0], str):
        seed_by_name = {p["name"]: p for p in _lxd_infra_seed()["profiles"]}
        upgraded = []
        for name in profiles:
            if name in seed_by_name:
                upgraded.append(copy.deepcopy(seed_by_name[name]))
            else:
                upgraded.append({
                    "name": name,
                    "description": "",
                    "config": {},
                    "devices": {},
                })
        lxd["profiles"] = upgraded


def _ensure_lxd_infra(state: dict) -> None:
    lxd = state.setdefault("lxd", {})
    seed = _lxd_infra_seed()
    for key, value in seed.items():
        if key not in lxd or lxd.get(key) is None:
            lxd[key] = copy.deepcopy(value)
    _normalize_lxd_profiles(lxd)
    containers = lxd.setdefault("containers", [])
    for c in containers:
        _enrich_lxd_instance(c)
    # Alias for callers that prefer "instances"
    lxd["instances"] = containers


def _find_lxd_instance(state: dict, name: str) -> dict | None:
    for c in (state.get("lxd") or {}).get("containers") or []:
        if (c.get("name") or "") == name:
            return c
    return None


def _lxd_next_ipv4(state: dict) -> str:
    used = set()
    for c in (state.get("lxd") or {}).get("containers") or []:
        ip = (c.get("ipv4") or "").strip()
        if ip:
            used.add(ip)
    for n in range(5, 250):
        candidate = f"10.10.2.{n}"
        if candidate not in used:
            return candidate
    return "10.10.2.200"


def _lxd_event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {
        "time": _now_iso(),
        "message": message,
        "severity": severity,
    })
    ops = state.setdefault("lxd", {}).setdefault("operations", [])
    ops.insert(0, {
        "id": f"op-{int(_now())}-{len(ops)}",
        "class": "task",
        "description": message,
        "status": "Success",
        "created_at": _now_iso(),
    })
    del ops[40:]


def _base_state() -> dict:
    m1 = _machine(1, "gpu-node-01", "Ready", "on", "10.10.1.11")
    m2 = _machine(2, "gpu-node-02", "Failed", "off", "")
    m3 = _machine(3, "storage-01", "Deployed", "on", "10.10.1.20")
    _log(m2, "Enlisted via PXE — commissioning aborted (no response from BMC)")
    _log(m1, "Commissioning complete — hardware inventory captured")
    _log(m3, "Deployment complete — Ubuntu 22.04 LTS")
    _machine_event(m1, "Node changed status - Ready")
    _machine_event(m3, "Node changed status - Deployed")
    maas = {
        "machines": [m1, m2, m3],
        "fabrics": [{"name": "fabric-0", "vlans": ["pxe", "mgmt"]}],
    }
    maas.update(_maas_infra_seed())
    lxd = {
        "containers": [
            _lxd_instance(
                "infer-svc",
                status="Running",
                ipv4="10.10.2.5",
                image="ubuntu:22.04",
                profiles=["default"],
                config={"limits.cpu": "2", "limits.memory": "2GiB"},
            ),
            _lxd_instance(
                "batch-job",
                status="Stopped",
                ipv4="",
                image="ubuntu:22.04",
                profiles=["default"],
            ),
            _lxd_instance(
                "gpu-worker-1",
                status="Running",
                ipv4="10.10.2.10",
                image="ubuntu:22.04",
                profiles=["default", "gpu-passthrough"],
                devices={
                    "root": {"path": "/", "pool": "default", "type": "disk"},
                    "eth0": {"name": "eth0", "network": "lxdbr0", "type": "nic"},
                    "gpu": {"type": "gpu", "gputype": "physical", "pci": "0000:19:00.0"},
                },
                nvidia_smi_ok=True,
                location="node1",
            ),
        ],
    }
    lxd.update(_lxd_infra_seed())
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"site": "fixitlab", "version": "MAAS 3.4 / LXD 5.x / KVM 8.x"},
        "maas": maas,
        "lxd": lxd,
        "kvm": {
            "vms": [
                {"name": "train-vm-1", "state": "running", "vcpu": 8, "ram_gb": 32, "ip": "192.168.122.10"},
                {"name": "train-vm-2", "state": "shut off", "vcpu": 4, "ram_gb": 16, "ip": ""},
            ],
            "networks": ["default", "br-ai"],
            "pools": ["default"],
        },
        "ipmi": {"bmc_hosts": [{"name": "gpu-node-02", "reachable": False, "power": "unknown"}]},
        "goal": {"title": "Fix bare metal", "objective": "Commission the failed MAAS machine and deploy it."},
        "broken": {"machine_needs_commission": 2, "bmc_unreachable": True},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "lxd" in slug or "lxc" in slug:
        state["goal"] = {"title": "LXD container", "objective": "Start the stopped container and verify it has an IP."}
        state["broken"] = {"container_stopped": "batch-job"}
    elif "kvm" in slug or "virsh" in slug:
        state["goal"] = {"title": "KVM VM", "objective": "Start the shut-off VM and confirm it is running."}
        state["broken"] = {"vm_stopped": "train-vm-2"}
    elif "rescue" in slug:
        machines = state["maas"]["machines"]
        m2 = next((m for m in machines if m.get("id") == 2), None)
        if "exit" in slug or "leave" in slug:
            state["goal"] = {
                "title": "Exit rescue mode",
                "objective": "Exit rescue mode on gpu-node-02 and confirm it returns to Deployed.",
            }
            if m2 is not None:
                m2["status"] = "Rescue mode"
                m2["power"] = "on"
                m2["os"] = m2.get("os") or "Ubuntu 22.04 LTS"
                m2["status_before_rescue"] = "Deployed"
            state["broken"] = {"needs_rescue_exit": 2}
        else:
            state["goal"] = {
                "title": "Enter rescue mode",
                "objective": "Boot gpu-node-02 into rescue mode to recover its filesystem.",
            }
            if m2 is not None:
                m2["status"] = "Deployed"
                m2["power"] = "on"
                m2["os"] = m2.get("os") or "Ubuntu 22.04 LTS"
            state["broken"] = {"needs_rescue_enter": 2}
    elif ("dhcp" in slug and "maas" in slug) or "enable-dhcp" in slug:
        state["goal"] = {"title": "Enable MAAS DHCP", "objective": "Enable DHCP on the PXE VLAN so machines can enlist."}
        state["maas"].setdefault("dhcp", {})["enabled"] = False
        state["broken"] = {"dhcp_disabled": True}
    elif "settings" in slug:
        state["goal"] = {"title": "Fix MAAS settings", "objective": "Configure NTP servers and the commissioning distro series."}
        state["maas"].setdefault("settings", {})["ntp_servers"] = ""
        state["maas"]["settings"]["commissioning_distro_series"] = ""
        state["broken"] = {"settings_ntp_wrong": True, "settings_commissioning_incomplete": True}
    elif "scripts" in slug and "maas" in slug:
        state["goal"] = {
            "title": "Scripts and users",
            "objective": "Attach the commissioning script and create an operator user.",
        }
        # Drop the seeded operator so the learner must create one.
        users = state["maas"].setdefault("users", [])
        state["maas"]["users"] = [u for u in users if u.get("username") != "operator"]
        state["broken"] = {"scripts_unattached": True, "needs_operator_user": True}
    elif "maas" in slug:
        state["goal"] = {"title": "MAAS commission", "objective": "Commission gpu-node-02 and deploy Ubuntu."}
        state["broken"] = {"machine_needs_commission": 2, "bmc_unreachable": True}
    elif "pxe" in slug:
        state["goal"] = {"title": "PXE boot", "objective": "Fix VLAN tagging so PXE discovery succeeds."}
        state["broken"] = {"pxe_vlan_wrong": True}
    elif "ipmi" in slug and "unreachable" in slug:
        state["goal"] = {"title": "IPMI unreachable", "objective": "Restore BMC connectivity and verify IPMI responds."}
        state["broken"] = {"bmc_unreachable": True, "machine_needs_commission": 2}
    elif "thermal" in slug or "gpu" in slug and "commission" in slug:
        state["goal"] = {"title": "GPU thermal commission", "objective": "Clear thermal alert and complete MAAS commissioning."}
        state["broken"] = {"thermal_alert": True, "machine_needs_commission": 2}
    elif "commission" in slug and "stuck" in slug:
        state["goal"] = {"title": "Commission stuck", "objective": "Reset stuck commissioning state and redeploy the node."}
        state["broken"] = {"commission_stuck": 2}
    elif "matrix" in slug and ("imagedev" in slug or "packer" in slug):
        state["goal"] = {
            "title": "ImageDev GPU matrix",
            "objective": "Build and publish H100/H200/B300/MI300 boot resources into MAAS.",
        }
        state["broken"] = {
            "packer_image_unpublished": True,
            "needs_custom_image_deploy": True,
            "missing_boot_resources": [
                "custom/h100-jammy",
                "custom/h200-jammy",
                "custom/b300-jammy",
                "custom/mi300-jammy",
            ],
        }
        packer_factory.ensure_factory(state)
    elif "packer" in slug or "image-factory" in slug or "image_factory" in slug or "imagedev" in slug:
        state["goal"] = {
            "title": "Packer Image Factory",
            "objective": "Build a GPU image, publish to MAAS boot-resources, and deploy a node from the custom image.",
        }
        state["broken"] = {
            "packer_image_unpublished": True,
            "needs_custom_image_deploy": True,
            "missing_boot_resource": "custom/h100-jammy",
        }
        packer_factory.ensure_factory(state)
    elif "bringup" in slug or "gpu-host" in slug:
        state["goal"] = {
            "title": "GPU host bring-up",
            "objective": "Commission the GPU node, deploy the ImageDev image, and verify nvidia-smi.",
        }
        state["broken"] = {
            "machine_needs_commission": 2,
            "bmc_unreachable": True,
            "needs_custom_image_deploy": True,
            "missing_boot_resource": "custom/h100-jammy",
        }
        packer_factory.ensure_factory(state)
    elif "psinfra" in slug or "gm1" in slug or "escalation" in slug:
        state["goal"] = {
            "title": "PSINFRA → ImageDev → DCOps handoff",
            "objective": "Clear thermal, publish the image, and restore the node via MAAS + AWX.",
        }
        state["broken"] = {
            "thermal_alert": True,
            "machine_needs_commission": 2,
            "packer_image_unpublished": True,
            "needs_custom_image_deploy": True,
        }
        packer_factory.ensure_factory(state)


# ── Wall-clock lifecycle advance ──────────────────────────────────────────────
_COMMISSION_STEPS = [
    (10, "PXE boot — loading MAAS ephemeral environment"),
    (30, "Running hardware discovery (lshw, lldp)"),
    (55, "Probing storage devices and NICs"),
    (80, "Uploading hardware inventory to region controller"),
    (100, "Commissioning scripts passed — machine Ready"),
]
_DEPLOY_STEPS = [
    (5, "Machine allocated — waiting for power-on"),
    (12, "DHCP DISCOVER on eth0 (vlan pxe)"),
    (20, "DHCP OFFER from rack controller"),
    (28, "DHCP REQUEST / ACK — next-server set"),
    (38, "TFTP: downloading pxelinux.0"),
    (48, "Loading kernel + initrd from MAAS rack"),
    (60, "Curtin: partitioning root disk"),
    (75, "Curtin: writing OS image"),
    (88, "Curtin: installing bootloader"),
    (95, "Rebooting into deployed OS"),
    (100, "Deployment complete"),
]
_TEST_STEPS = [
    (40, "Running smartctl short self-test"),
    (70, "Running network link + stress scripts"),
    (100, "Hardware testing complete"),
]
_RELEASE_STEPS = [
    (50, "Powering down and clearing allocated owner"),
    (100, "Release complete — machine Ready"),
]
_RESCUE_ENTER_STEPS = [
    (40, "Booting ephemeral rescue environment via PXE"),
    (75, "Mounting rescue kernel + initrd"),
    (100, "Ephemeral rescue environment ready"),
]
_RESCUE_EXIT_STEPS = [
    (50, "Exiting rescue mode — rebooting into deployed OS"),
    (100, "Rescue mode exited — machine back online"),
]


def _boot_resource_os_label(resource: dict | None) -> str:
    """Human OS string for a MAAS boot resource (custom Packer images included)."""
    if not resource:
        return "Ubuntu 22.04 LTS"
    name = (resource.get("name") or "").strip()
    if resource.get("os_title"):
        return str(resource["os_title"])
    if name.startswith("custom/"):
        sku = name.replace("custom/", "").replace("-jammy", "").upper()
        return f"{name} (Jammy GPU {sku})" if sku else name
    if "noble" in name:
        return "Ubuntu 24.04 LTS"
    if "jammy" in name or name.startswith("ubuntu/"):
        return "Ubuntu 22.04 LTS"
    return name or "Ubuntu 22.04 LTS"


def _resolve_boot_resource(state: dict, name: str | None) -> dict | None:
    resources = (state.get("maas") or {}).get("boot_resources") or []
    want = (name or "").strip()
    if want:
        for r in resources:
            if (r.get("name") or "").strip() == want:
                return r
        # Allow short sku form: h100 → custom/h100-jammy
        short = want.replace("custom/", "").replace("-jammy", "")
        for r in resources:
            rn = (r.get("name") or "")
            if rn == f"custom/{short}-jammy" or r.get("sku") == short:
                return r
        # Explicit name was requested but not present — do not silently default.
        return None
    for r in resources:
        if "ubuntu/jammy" in (r.get("name") or ""):
            return r
    return resources[0] if resources else None


def _advance_machine(m: dict, now: float, *, session_id: str = "") -> None:
    """Advance a single machine's async phase based on wall-clock elapsed time."""
    status = m.get("status")
    started = m.get("phase_started_at")
    duration = m.get("phase_duration") or 0
    async_statuses = (
        "Commissioning", "Deploying", "Testing", "Releasing",
        "Entering rescue mode", "Exiting rescue mode",
    )
    if status not in async_statuses or not started or duration <= 0:
        return

    elapsed = max(0.0, now - float(started))
    pct = int(min(100, round((elapsed / duration) * 100)))
    prev = m.get("progress") or 0

    if status == "Commissioning":
        steps = _COMMISSION_STEPS
    elif status == "Deploying":
        steps = _DEPLOY_STEPS
    elif status == "Testing":
        steps = _TEST_STEPS
    elif status == "Entering rescue mode":
        steps = _RESCUE_ENTER_STEPS
    elif status == "Exiting rescue mode":
        steps = _RESCUE_EXIT_STEPS
    else:
        steps = _RELEASE_STEPS
    for threshold, message in steps:
        if prev < threshold <= pct:
            _log(m, message)

    m["progress"] = pct
    if pct >= 100:
        # Phase finished — transition to the terminal state for this phase.
        m["phase_started_at"] = None
        m["phase_duration"] = 0
        if status == "Commissioning":
            m["status"] = "Ready"
            m["power"] = "on"
            if not m.get("ip"):
                m["ip"] = f"10.10.1.{10 + int(m.get('id') or 0)}"
            for iface in m.get("interfaces", []):
                if iface.get("name") == "eth0":
                    iface["link"] = "up"
            _fill_commission_complete(m)
        elif status == "Deploying":
            m["status"] = "Deployed"
            m["power"] = "on"
            m["os"] = m.get("pending_os") or m.get("os") or "Ubuntu 22.04 LTS"
            m.pop("pending_os", None)
            _machine_event(m, "Node changed status - Deployed")
        elif status == "Testing":
            m["status"] = m.pop("status_before_test", None) or "Ready"
            m["test_results"] = [
                {"name": "smartctl-short", "status": "passed"},
                {"name": "internet-connectivity", "status": "passed"},
                {"name": "cpu-stress", "status": "passed"},
            ]
            _machine_event(m, f"Node changed status - {m['status']}")
            _log(m, "Hardware tests passed")
        elif status == "Releasing":
            m["status"] = "Ready"
            m["os"] = ""
            m["power"] = "off"
            m.pop("pending_os", None)
            m.pop("boot_resource", None)
            if m.get("erase_disks_on_release"):
                for d in m.get("storage") or []:
                    d["wiped"] = True
                m.pop("erase_disks_on_release", None)
                _log(m, "Disks erased on release")
            _machine_event(m, "Node changed status - Ready")
        elif status == "Entering rescue mode":
            m["status"] = "Rescue mode"
            m["power"] = "on"
            _log(m, "Ephemeral rescue environment ready")
            _machine_event(m, "Node changed status - Rescue mode")
        elif status == "Exiting rescue mode":
            m["status"] = m.pop("status_before_rescue", None) or "Deployed"
            _log(m, f"Rescue mode exited — status {m['status']}")
            _machine_event(m, f"Node changed status - {m['status']}")
        # S1: Ready/Deployed → unified asset registry (same session as AWX/DC).
        if session_id and m.get("status") in ("Ready", "Deployed"):
            try:
                from apps.labs.provisioner.simulation.server_identity import upsert_from_maas_machine

                upsert_from_maas_machine(session_id, m, source="baremetal")
            except Exception:
                pass


def _tick(state: dict, now: float | None = None, *, session_id: str = "") -> bool:
    """Advance every machine's lifecycle to the current wall-clock. Returns True if
    anything changed (so callers can persist)."""
    now = _now() if now is None else now
    changed = False
    for m in state.get("maas", {}).get("machines", []):
        before = (m.get("status"), m.get("progress"), len(m.get("log", [])), len(m.get("events", [])))
        _advance_machine(m, now, session_id=session_id)
        if before != (m.get("status"), m.get("progress"), len(m.get("log", [])), len(m.get("events", []))):
            changed = True
    return changed


def _find_machine(state: dict, mid: int) -> dict | None:
    for m in state.get("maas", {}).get("machines", []):
        if m.get("id") == mid:
            return m
    return None


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    packer_factory.ensure_factory(entry["state"])
    packer_factory.clear_needs_custom_image_deploy(entry["state"])
    ensure_v2(entry["state"])
    _ensure_maas_infra(entry["state"])
    _ensure_lxd_infra(entry["state"])
    # Advance the lifecycle on read so status/progress reflect wall-clock time
    # even when no action has been taken since the phase started.
    _tick(entry["state"], session_id=str(session_id))
    _save(session_id, entry)
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": copy.deepcopy(entry["state"]),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Bare metal session not found"}
    state = entry["state"]
    # Advance wall-clock lifecycle before handling the action so decisions are
    # made against the up-to-date state.
    _tick(state)
    action = _ALIASES.get(action, action)
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": "Signed in to bare metal console", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    # Packer Image Factory actions (available after login; get_state does not require write).
    if action in packer_factory.ACTIONS:
        if not state.get("session", {}).get("logged_in") and action != "packer_factory_get_state":
            return {"ok": False, "error": "Sign in first"}
        result = packer_factory.handle_action(state, action, payload)
        if result is not None:
            if result.get("ok"):
                state.setdefault("events", []).insert(0, {
                    "time": _now_iso(),
                    "message": result.get("message") or action,
                    "severity": "success" if "fail" not in (result.get("message") or "").lower() else "warning",
                })
            _save(session_id, entry)
            return result

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in first"}

    if action == "maas_commission":
        mids = _machine_ids_from_payload(payload, broken, default=2)
        started = []
        for mid in mids:
            m = _find_machine(state, mid)
            if not m:
                return {"ok": False, "error": f"Machine {mid} not found"}
            # BMC must be reachable to power-cycle for commissioning.
            for b in state["ipmi"]["bmc_hosts"]:
                b["reachable"] = True
                b["power"] = "on"
            m["status"] = "Commissioning"
            m["power"] = "on"
            m["progress"] = 0
            m["phase_started_at"] = _now()
            m["phase_duration"] = COMMISSION_SECONDS
            m["pci_devices"] = []  # inventory filled when Ready
            m["commissioning_results"] = []
            _log(m, "Commissioning started — powering on via IPMI")
            _machine_event(m, "Node changed status - Commissioning")
            started.append(mid)
        # Grading contract preserved: initiating the correct action clears the
        # broken flags (validation checks `broken`, not the transient status).
        broken.pop("machine_needs_commission", None)
        broken.pop("bmc_unreachable", None)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Machine {', '.join(str(x) for x in started)} commissioning started",
            "severity": "info",
        })
        _save(session_id, entry)
        return {"ok": True, "message": "Commissioning started", "machine_ids": started}

    if action == "maas_deploy":
        mids = _machine_ids_from_payload(payload, broken, default=2)
        br_name = (
            payload.get("boot_resource")
            or payload.get("distro_series")
            or payload.get("os")
            or ""
        )
        resource = _resolve_boot_resource(state, br_name)
        if br_name and resource is None:
            return {"ok": False, "error": f"Boot resource {br_name!r} not found — publish/import it under Images first"}
        if resource is None:
            resource = {"name": "ubuntu/jammy", "architecture": "amd64/generic"}
        os_label = _boot_resource_os_label(resource)
        deployed = []
        for mid in mids:
            m = _find_machine(state, mid)
            if not m:
                return {"ok": False, "error": f"Machine {mid} not found"}
            if m.get("status") not in ("Ready", "Allocated"):
                return {"ok": False, "error": f"Machine {mid} must be Ready before deploy (is {m.get('status')})"}
            if m.get("locked"):
                return {"ok": False, "error": f"Machine {mid} is locked"}
            # Canonical path: Allocated (logged) then Deploying.
            m["status"] = "Allocated"
            _log(m, "Machine allocated")
            _machine_event(m, "Node changed status - Allocated")
            state["events"].insert(0, {
                "time": _now_iso(),
                "message": f"Machine {mid} allocated",
                "severity": "info",
            })
            m["status"] = "Deploying"
            m["progress"] = 0
            m["phase_started_at"] = _now()
            m["phase_duration"] = DEPLOY_SECONDS
            m["boot_resource"] = resource.get("name")
            m["pending_os"] = os_label
            _log(m, f"Deployment started — allocating machine with {resource.get('name')}")
            _machine_event(m, "Node changed status - Deploying")
            deployed.append(mid)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Machine {', '.join(str(x) for x in deployed)} deploying {resource.get('name')}",
            "severity": "info",
        })
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Deploy started ({resource.get('name')})",
            "boot_resource": resource.get("name"),
            "machine_ids": deployed,
        }

    if action == "maas_power":
        mids = _machine_ids_from_payload(payload, broken, default=2)
        results = []
        for mid in mids:
            m = _find_machine(state, mid)
            if not m:
                return {"ok": False, "error": f"Machine {mid} not found"}
            target = (payload.get("power") or ("off" if m.get("power") == "on" else "on")).lower()
            m["power"] = "on" if target == "on" else "off"
            _log(m, f"Power {'on' if target == 'on' else 'off'} via IPMI")
            results.append(mid)
            try:
                from apps.labs.provisioner.simulation.server_identity import get_primary, set_power, upsert_server
                upsert_server(
                    session_id,
                    {
                        "id": f"maas-{m.get('hostname') or mid}",
                        "hostname": m.get("hostname") or f"node-{mid}",
                        "power": m["power"],
                        "tags": {"role": "primary"},
                    },
                    source="baremetal",
                )
                primary = get_primary(session_id)
                if primary:
                    set_power(session_id, primary["id"], m["power"], source="baremetal")
                set_power(session_id, f"maas-{m.get('hostname') or mid}", m["power"], source="baremetal")
            except Exception:
                pass
        _save(session_id, entry)
        return {"ok": True, "message": f"Power updated for {len(results)} machine(s)", "machine_ids": results}

    if action == "ipmi_power":
        # Full `ipmitool power on|off|cycle|status` verbs against a machine's BMC.
        mid = int(payload.get("machine_id") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        verb = (payload.get("verb") or payload.get("power") or "status").lower()
        # The BMC must be reachable to control power out-of-band.
        bmc = next((b for b in state["ipmi"]["bmc_hosts"]
                    if b.get("name") == m.get("hostname")), None)
        if verb == "status":
            return {"ok": True, "message": f"Chassis Power is {m.get('power', 'off')}",
                    "power": m.get("power", "off")}
        if bmc is not None and not bmc.get("reachable"):
            return {"ok": False,
                    "error": (f"IPMI to {m.get('hostname')} BMC failed — host unreachable. "
                              "Restore BMC connectivity first (ipmi_power_on).")}
        if verb == "cycle":
            # Power cycle: off, POST, PXE re-request, back on.
            m["power"] = "on"
            _log(m, "IPMI chassis power cycle — resetting host")
            _log(m, "POST: memory + CPU check passed")
            _log(m, "PXE: DHCP request on eth0 (vlan pxe) — awaiting next-server")
            state["events"].insert(0, {"time": _now_iso(),
                                       "message": f"{m.get('hostname')} power-cycled via IPMI", "severity": "info"})
            try:
                from apps.labs.provisioner.simulation.server_identity import get_primary, set_power, upsert_server
                upsert_server(
                    session_id,
                    {
                        "id": f"maas-{m.get('hostname') or mid}",
                        "hostname": m.get("hostname") or f"node-{mid}",
                        "power": "on",
                        "tags": {"role": "primary"},
                    },
                    source="baremetal",
                )
                primary = get_primary(session_id)
                if primary:
                    set_power(session_id, primary["id"], "on", source="baremetal")
                set_power(session_id, f"maas-{m.get('hostname') or mid}", "on", source="baremetal")
            except Exception:
                pass
            _save(session_id, entry)
            return {"ok": True, "message": f"Power cycle issued to {m.get('hostname')}",
                    "power": "on"}
        target = "on" if verb == "on" else "off"
        m["power"] = target
        _log(m, f"IPMI chassis power {target}")
        if bmc is not None:
            bmc["power"] = target
        try:
            from apps.labs.provisioner.simulation.server_identity import get_primary, set_power, upsert_server
            upsert_server(
                session_id,
                {
                    "id": f"maas-{m.get('hostname') or mid}",
                    "hostname": m.get("hostname") or f"node-{mid}",
                    "power": target,
                    "tags": {"role": "primary"},
                },
                source="baremetal",
            )
            primary = get_primary(session_id)
            if primary:
                set_power(session_id, primary["id"], target, source="baremetal")
            set_power(session_id, f"maas-{m.get('hostname') or mid}", target, source="baremetal")
        except Exception:
            pass
        _save(session_id, entry)
        return {"ok": True, "message": f"Chassis Power set to {target}", "power": target}

    if action == "maas_enlist":
        # A new bare-metal node PXE-boots and enlists into MAAS as "New" (the
        # first step of the enlist -> commission -> ready -> deploy lifecycle).
        machines = state["maas"]["machines"]
        new_id = (max((mm.get("id") or 0) for mm in machines) + 1) if machines else 1
        hostname = payload.get("hostname") or f"node-{new_id:02d}"
        m = _machine(new_id, hostname, "New", "off", "")
        _log(m, "PXE boot detected — enlisting into MAAS region controller")
        _log(m, "Captured BMC/MAC — machine registered as New (needs commissioning)")
        machines.append(m)
        state["ipmi"]["bmc_hosts"].append(
            {"name": hostname, "reachable": True, "power": "off"})
        state["events"].insert(0, {"time": _now_iso(),
                                   "message": f"New machine {hostname} enlisted via PXE", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {hostname} enlisted (New)", "machine_id": new_id}

    # ── LXD instance lifecycle ─────────────────────────────────────────────
    if action in ("lxd_start", "lxd_stop", "lxd_restart", "lxd_launch", "lxd_create",
                  "create_lxd", "lxd_delete", "delete_lxd", "lxd_snapshot", "lxd_restore",
                  "lxd_profile_create", "lxd_profile_set", "lxd_config_device_add",
                  "lxd_project_create", "lxd_storage_list", "lxd_network_list",
                  "lxd_cluster_list", "lxd_exec_echo", "lxd_config_set", "lxd_profile_assign",
                  "lxd_publish"):
        _ensure_lxd_infra(state)

    if action == "lxd_start":
        name = payload.get("name") or broken.get("container_stopped") or "batch-job"
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        c["status"] = "Running"
        c["ipv4"] = c.get("ipv4") or _lxd_next_ipv4(state)
        broken.pop("container_stopped", None)
        _lxd_event(state, f"Instance {name} started", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Instance {name} started"}

    if action == "lxd_stop":
        name = payload.get("name") or ""
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        c["status"] = "Stopped"
        c["ipv4"] = ""
        _lxd_event(state, f"Instance {name} stopped")
        _save(session_id, entry)
        return {"ok": True, "message": f"Instance {name} stopped"}

    if action == "lxd_restart":
        name = payload.get("name") or ""
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        c["status"] = "Running"
        c["ipv4"] = c.get("ipv4") or _lxd_next_ipv4(state)
        _lxd_event(state, f"Instance {name} restarted", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Instance {name} restarted"}

    if action in ("lxd_launch", "lxd_create", "create_lxd"):
        name = payload.get("name") or "new-svc"
        if _find_lxd_instance(state, name):
            return {"ok": False, "error": f"Instance {name} already exists"}
        itype = payload.get("type") or payload.get("instance_type") or "container"
        if itype in ("vm", "virtual-machine", "virtual_machine"):
            itype = "virtual-machine"
        else:
            itype = "container"
        image = payload.get("image") or "ubuntu:22.04"
        profiles = payload.get("profiles") or ["default"]
        if isinstance(profiles, str):
            profiles = [p.strip() for p in profiles.split(",") if p.strip()]
        project = payload.get("project") or "default"
        start = action == "lxd_launch" or payload.get("start", True)
        if action == "lxd_create" and payload.get("start") is False:
            start = False
        if action == "create_lxd" and payload.get("start") is None:
            start = True
        inst = _lxd_instance(
            name,
            status="Running" if start else "Stopped",
            itype=itype,
            ipv4=_lxd_next_ipv4(state) if start else "",
            image=image,
            profiles=profiles,
            project=project,
            location=payload.get("location") or "none",
            config=payload.get("config") or {},
            devices=payload.get("devices"),
        )
        state["lxd"]["containers"].append(inst)
        verb = "Launched" if action == "lxd_launch" else "Created"
        _lxd_event(state, f"Instance {name} {verb.lower()}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"{verb} {name}", "instance": inst}

    if action in ("lxd_delete", "delete_lxd"):
        name = payload.get("name") or ""
        before = len(state["lxd"]["containers"])
        state["lxd"]["containers"] = [
            c for c in state["lxd"]["containers"] if (c.get("name") or "") != name
        ]
        removed = before - len(state["lxd"]["containers"])
        if removed:
            _lxd_event(state, f"Instance {name} deleted")
        _save(session_id, entry)
        return {"ok": True, "message": f"Instance {name} deleted" if removed else f"Instance {name} not found"}

    if action == "lxd_snapshot":
        name = payload.get("name") or payload.get("instance") or ""
        snap_name = payload.get("snapshot") or payload.get("snapshot_name") or f"snap{int(_now()) % 10000}"
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        snaps = c.setdefault("snapshots", [])
        if any(s.get("name") == snap_name for s in snaps):
            return {"ok": False, "error": f"Snapshot {snap_name} already exists"}
        snaps.append({
            "name": snap_name,
            "created_at": _now_iso(),
            "stateful": bool(payload.get("stateful")),
        })
        _lxd_event(state, f"Snapshot {name}/{snap_name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Snapshot {snap_name} created", "snapshot": snaps[-1]}

    if action == "lxd_restore":
        name = payload.get("name") or payload.get("instance") or ""
        snap_name = payload.get("snapshot") or payload.get("snapshot_name") or ""
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        snaps = c.get("snapshots") or []
        if snap_name and not any(s.get("name") == snap_name for s in snaps):
            return {"ok": False, "error": f"Snapshot {snap_name} not found"}
        if not snap_name and snaps:
            snap_name = snaps[-1]["name"]
        if not snap_name:
            return {"ok": False, "error": "No snapshot to restore"}
        # Restoring keeps the instance stopped until explicitly started (LXD-like).
        c["status"] = "Stopped"
        c["ipv4"] = ""
        _lxd_event(state, f"Restored {name} from snapshot {snap_name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Instance {name} restored from {snap_name}"}

    if action == "lxd_profile_create":
        pname = payload.get("name") or payload.get("profile") or ""
        if not pname:
            return {"ok": False, "error": "Profile name required"}
        profiles = state["lxd"].setdefault("profiles", [])
        if any((p.get("name") if isinstance(p, dict) else p) == pname for p in profiles):
            return {"ok": False, "error": f"Profile {pname} already exists"}
        row = {
            "name": pname,
            "description": payload.get("description") or "",
            "config": payload.get("config") or {},
            "devices": payload.get("devices") or {},
        }
        profiles.append(row)
        _lxd_event(state, f"Profile {pname} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Profile {pname} created", "profile": row}

    if action == "lxd_profile_set":
        pname = payload.get("name") or payload.get("profile") or "default"
        key = payload.get("key") or ""
        value = payload.get("value")
        profiles = state["lxd"].setdefault("profiles", [])
        target = None
        for p in profiles:
            if isinstance(p, dict) and p.get("name") == pname:
                target = p
                break
        if target is None:
            return {"ok": False, "error": f"Profile {pname} not found"}
        if key:
            target.setdefault("config", {})[key] = value if value is not None else ""
        if isinstance(payload.get("config"), dict):
            target.setdefault("config", {}).update(payload["config"])
        if isinstance(payload.get("devices"), dict):
            target.setdefault("devices", {}).update(payload["devices"])
        _lxd_event(state, f"Profile {pname} updated")
        _save(session_id, entry)
        return {"ok": True, "message": f"Profile {pname} updated", "profile": target}

    if action == "lxd_profile_assign":
        name = payload.get("name") or payload.get("instance") or ""
        profiles = payload.get("profiles") or []
        if isinstance(profiles, str):
            profiles = [p.strip() for p in profiles.split(",") if p.strip()]
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        if not profiles:
            return {"ok": False, "error": "profiles required"}
        c["profiles"] = profiles
        _lxd_event(state, f"Profiles on {name} set to {','.join(profiles)}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Profiles updated on {name}"}

    if action == "lxd_config_set":
        name = payload.get("name") or payload.get("instance") or ""
        key = payload.get("key") or ""
        value = payload.get("value")
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        if not key:
            return {"ok": False, "error": "config key required"}
        c.setdefault("config", {})[key] = value if value is not None else ""
        _lxd_event(state, f"Config {key} set on {name}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Config {key} updated"}

    if action == "lxd_config_device_add":
        name = payload.get("name") or payload.get("instance") or ""
        device = payload.get("device") or payload.get("device_name") or ""
        dtype = (payload.get("type") or payload.get("device_type") or "disk").lower()
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        if not device:
            device = {"disk": "disk1", "nic": "eth1", "gpu": "gpu"}.get(dtype, "dev0")
        devices = c.setdefault("devices", {})
        if dtype == "gpu":
            devices[device] = {
                "type": "gpu",
                "gputype": payload.get("gputype") or "physical",
                "pci": payload.get("pci") or "0000:19:00.0",
            }
            c["nvidia_smi_ok"] = True
            # Convenience alias so labs can assert devices.gpu
            if device != "gpu" and "gpu" not in devices:
                devices["gpu"] = dict(devices[device])
        elif dtype == "nic":
            devices[device] = {
                "type": "nic",
                "name": payload.get("nictype_name") or device,
                "network": payload.get("network") or "lxdbr0",
                "nictype": payload.get("nictype") or "bridged",
            }
        else:  # disk
            devices[device] = {
                "type": "disk",
                "path": payload.get("path") or f"/{device}",
                "pool": payload.get("pool") or "default",
                "source": payload.get("source") or "",
                "size": payload.get("size") or "",
            }
        _lxd_event(state, f"Device {device} ({dtype}) added to {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Device {device} added", "devices": devices}

    if action == "lxd_project_create":
        pname = payload.get("name") or payload.get("project") or ""
        if not pname:
            return {"ok": False, "error": "Project name required"}
        projects = state["lxd"].setdefault("projects", [])
        if any(p.get("name") == pname for p in projects):
            return {"ok": False, "error": f"Project {pname} already exists"}
        row = {"name": pname, "description": payload.get("description") or "", "used_by": 0}
        projects.append(row)
        _lxd_event(state, f"Project {pname} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Project {pname} created", "project": row}

    if action == "lxd_storage_list":
        pools = state["lxd"].get("storage_pools") or []
        _save(session_id, entry)
        return {"ok": True, "message": "Storage pools", "storage_pools": pools}

    if action == "lxd_network_list":
        nets = state["lxd"].get("networks") or []
        _save(session_id, entry)
        return {"ok": True, "message": "Networks", "networks": nets}

    if action == "lxd_cluster_list":
        members = state["lxd"].get("cluster") or []
        _save(session_id, entry)
        return {"ok": True, "message": "Cluster members", "cluster": members}

    if action == "lxd_exec_echo":
        name = payload.get("name") or payload.get("instance") or "infer-svc"
        cmd = payload.get("command") or payload.get("cmd") or "echo ok"
        c = _find_lxd_instance(state, name)
        # Canned bash output for labs (nvidia-smi, uname, etc.)
        low_cmd = str(cmd).lower()
        if "nvidia-smi" in low_cmd:
            if c and c.get("nvidia_smi_ok"):
                output = (
                    "Thu Aug  6 00:00:00 2026\n"
                    "+-----------------------------------------------------------------------------+\n"
                    "| NVIDIA-SMI 535.104.05   Driver Version: 535.104.05   CUDA Version: 12.2     |\n"
                    "|-------------------------------+----------------------+----------------------+\n"
                    "| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |\n"
                    "|   0  NVIDIA H100 80GB HBM3 Off | 00000000:19:00.0 Off |                    0 |\n"
                    "+-------------------------------+----------------------+----------------------+"
                )
            else:
                output = "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
        elif "uname" in low_cmd:
            output = "Linux " + name + " 5.15.0-91-generic #101-Ubuntu SMP x86_64 GNU/Linux"
        elif low_cmd.strip() in ("bash", "sh", "/bin/bash"):
            output = f"root@{name}:~#"
        else:
            # Generic echo / command marker
            echoed = cmd
            if low_cmd.startswith("echo "):
                echoed = str(cmd)[5:]
            output = echoed if echoed else "ok"
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Executed on {name}",
            "output": output,
            "prompt": f"root@{name}:~#",
        }

    if action == "lxd_publish":
        name = payload.get("name") or payload.get("instance") or ""
        alias = payload.get("alias") or payload.get("image") or f"{name}-image"
        c = _find_lxd_instance(state, name)
        if not c:
            return {"ok": False, "error": f"Instance {name} not found"}
        images = state["lxd"].setdefault("images", [])
        row = {
            "alias": alias,
            "fingerprint": f"pub{int(_now()) % 10_000_000:07d}",
            "public": False,
            "description": f"Published from {name}",
            "architecture": "x86_64",
            "type": c.get("type") or "container",
        }
        images.append(row)
        _lxd_event(state, f"Published {name} as image {alias}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Image {alias} published", "image": row}

    if action == "kvm_start":
        name = payload.get("name") or broken.get("vm_stopped") or "train-vm-2"
        for v in state["kvm"]["vms"]:
            if v["name"] == name:
                v["state"] = "running"
                v["ip"] = v.get("ip") or "192.168.122.11"
        broken.pop("vm_stopped", None)
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} started"}

    if action == "kvm_stop":
        name = payload.get("name") or ""
        for v in state["kvm"]["vms"]:
            if v["name"] == name:
                v["state"] = "shut off"
                v["ip"] = ""
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} stopped"}

    if action == "fix_pxe_vlan":
        broken.pop("pxe_vlan_wrong", None)
        _save(session_id, entry)
        return {"ok": True, "message": "PXE VLAN corrected"}

    if action == "ipmi_power_on":
        for b in state["ipmi"]["bmc_hosts"]:
            b["reachable"] = True
            b["power"] = "on"
        broken.pop("bmc_unreachable", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "BMC reachable via IPMI", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "BMC power on — IPMI reachable"}

    if action == "clear_thermal_alert":
        broken.pop("thermal_alert", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "Thermal alert cleared", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Thermal threshold restored"}

    if action == "reset_commission":
        mid = int(payload.get("machine_id") or broken.get("commission_stuck") or 2)
        m = _find_machine(state, mid)
        if m:
            # Reset a stuck node back to a clean Commissioning run.
            m["status"] = "Commissioning"
            m["power"] = "on"
            m["progress"] = 0
            m["phase_started_at"] = _now()
            m["phase_duration"] = COMMISSION_SECONDS
            _log(m, "Stuck state cleared — restarting commissioning")
            if not m.get("ip"):
                m["ip"] = f"10.10.1.{10 + mid}"
        broken.pop("commission_stuck", None)
        broken.pop("machine_needs_commission", None)
        _save(session_id, entry)
        return {"ok": True, "message": "Commission reset complete"}

    if action == "create_kvm":
        name = payload.get("name") or "new-vm"
        state["kvm"]["vms"].append(
            {"name": name, "state": "running", "vcpu": 4, "ram_gb": 8, "ip": "192.168.122.12"}
        )
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} created"}

    # ── Extended MAAS actions (Canonical-like UI) ──────────────────────────
    if action == "maas_release":
        mids = _machine_ids_from_payload(payload, broken, default=3)
        released = []
        erase = bool(payload.get("erase_disks") or payload.get("erase"))
        for mid in mids:
            m = _find_machine(state, mid)
            if not m:
                return {"ok": False, "error": f"Machine {mid} not found"}
            if m.get("status") not in ("Deployed", "Allocated"):
                return {"ok": False, "error": f"Machine {mid} must be Deployed or Allocated to release (is {m.get('status')})"}
            if m.get("locked"):
                return {"ok": False, "error": f"Machine {mid} is locked"}
            m["status"] = "Releasing"
            m["progress"] = 0
            m["phase_started_at"] = _now()
            m["phase_duration"] = RELEASE_SECONDS
            if erase:
                m["erase_disks_on_release"] = True
            _log(m, "Releasing machine" + (" (erase disks)" if erase else ""))
            _machine_event(m, "Node changed status - Releasing")
            # Short phase: if duration is tiny, also allow immediate Ready via tick.
            released.append(mid)
        # Advance immediately so learners see Ready without waiting when RELEASE_SECONDS elapsed.
        _tick(state, session_id=str(session_id))
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Machine {', '.join(str(x) for x in released)} releasing",
            "severity": "info",
        })
        _save(session_id, entry)
        return {"ok": True, "message": "Release started", "machine_ids": released}

    if action == "maas_abort":
        mids = _machine_ids_from_payload(payload, broken, default=2)
        aborted = []
        for mid in mids:
            m = _find_machine(state, mid)
            if not m:
                return {"ok": False, "error": f"Machine {mid} not found"}
            cur = m.get("status")
            if cur not in ("Commissioning", "Deploying", "Testing", "Releasing"):
                return {"ok": False, "error": f"Machine {mid} has no abortable operation (is {cur})"}
            if cur == "Commissioning":
                m["status"] = "Failed commissioning"
            elif cur == "Deploying":
                m["status"] = "Failed deployment"
            else:
                m["status"] = m.pop("status_before_test", None) or "Failed"
            _clear_phase(m)
            m["progress"] = 0
            _log(m, f"Aborted — status set to {m['status']}")
            _machine_event(m, f"Node changed status - {m['status']}")
            aborted.append(mid)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Aborted operation on machine(s) {', '.join(str(x) for x in aborted)}",
            "severity": "warning",
        })
        _save(session_id, entry)
        return {"ok": True, "message": "Operation aborted", "machine_ids": aborted}

    if action == "maas_mark_broken":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        m["status_before_broken"] = m.get("status")
        m["status"] = "Broken"
        _clear_phase(m)
        comment = payload.get("comment") or payload.get("message") or ""
        _log(m, f"Marked Broken{(': ' + comment) if comment else ''}")
        _machine_event(m, "Node changed status - Broken")
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} marked Broken", "severity": "warning"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} marked Broken"}

    if action == "maas_mark_fixed":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        if m.get("status") != "Broken":
            return {"ok": False, "error": f"Machine {mid} is not Broken"}
        prev = m.pop("status_before_broken", None) or "Ready"
        if prev in ("Commissioning", "Deploying", "Testing", "Releasing", "Broken"):
            prev = "Ready"
        m["status"] = prev
        _clear_phase(m)
        m["progress"] = 100
        _log(m, f"Marked Fixed — status {prev}")
        _machine_event(m, f"Node changed status - {prev}")
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} marked Fixed", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} marked Fixed"}

    if action == "maas_lock":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        m["locked"] = True
        _log(m, "Machine locked")
        _machine_event(m, "Machine locked")
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} locked"}

    if action == "maas_unlock":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        m["locked"] = False
        _log(m, "Machine unlocked")
        _machine_event(m, "Machine unlocked")
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} unlocked"}

    if action == "maas_set_zone":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        zone = (payload.get("zone") or "default").strip()
        m["zone"] = zone
        _log(m, f"Zone set to {zone}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} zone → {zone}"}

    if action == "maas_set_pool":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        pool = (payload.get("pool") or "default").strip()
        m["pool"] = pool
        _ensure_maas_infra(state)
        _log(m, f"Pool set to {pool}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} pool → {pool}"}

    if action == "maas_set_owner":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        owner = (payload.get("owner") or "").strip()
        m["owner"] = owner
        _log(m, f"Owner set to {owner or '(none)'}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} owner → {owner or '(none)'}"}

    if action == "maas_test":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        if m.get("status") not in ("Ready", "Deployed"):
            return {"ok": False, "error": f"Machine {mid} must be Ready or Deployed to test (is {m.get('status')})"}
        m["status_before_test"] = m.get("status")
        m["status"] = "Testing"
        m["progress"] = 0
        m["phase_started_at"] = _now()
        m["phase_duration"] = TEST_SECONDS
        m["test_results"] = []
        _log(m, "Hardware testing started")
        _machine_event(m, "Node changed status - Testing")
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} testing started", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Testing started"}

    if action == "maas_override_failed_testing":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        # Allow override from Failed / Failed commissioning after tests, or Testing.
        if m.get("status") not in ("Failed", "Failed commissioning", "Testing", "Broken"):
            # Also allow if test_results contain failed entries while Ready.
            results = m.get("test_results") or []
            if not any(r.get("status") == "failed" for r in results) and m.get("status") != "Ready":
                return {"ok": False, "error": f"Machine {mid} has no failed testing to override"}
        _clear_phase(m)
        m.pop("status_before_test", None)
        m["status"] = "Ready"
        m["progress"] = 100
        m["test_results"] = [
            {"name": "smartctl-short", "status": "passed"},
            {"name": "internet-connectivity", "status": "passed"},
            {"name": "cpu-stress", "status": "passed"},
        ]
        _log(m, "Overrode failed testing — machine Ready")
        _machine_event(m, "Node changed status - Ready")
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {mid} Ready (testing overridden)"}

    if action in ("maas_delete_machine", "maas_delete"):
        hostname = payload.get("hostname") or ""
        mid = payload.get("machine_id")
        machines = state["maas"]["machines"]
        if mid is not None and not hostname:
            target = _find_machine(state, int(mid))
            hostname = (target or {}).get("hostname") or ""
        before = len(machines)
        state["maas"]["machines"] = [
            m for m in machines if (m.get("hostname") or "") != hostname
        ]
        removed = before - len(state["maas"]["machines"])
        if removed:
            state["ipmi"]["bmc_hosts"] = [
                b for b in state["ipmi"]["bmc_hosts"] if (b.get("name") or "") != hostname
            ]
            state["events"].insert(0, {
                "time": _now_iso(),
                "message": f"Machine {hostname} removed from MAAS",
                "severity": "info",
            })
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {hostname} deleted" if removed else f"Machine {hostname} not found"}

    if action == "maas_create_bond":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        names = payload.get("interfaces") or payload.get("nics") or ["eth0", "eth1"]
        if isinstance(names, str):
            names = [n.strip() for n in names.split(",") if n.strip()]
        ifaces = m.setdefault("interfaces", [])
        members = [i for i in ifaces if i.get("name") in names]
        if len(members) < 2:
            return {"ok": False, "error": "Need at least two interfaces to create a bond"}
        bond_name = payload.get("name") or "bond0"
        if any(i.get("name") == bond_name for i in ifaces):
            return {"ok": False, "error": f"Interface {bond_name} already exists"}
        mac = members[0].get("mac") or f"52:54:00:bf:{mid:02d}:01"
        for mem in members:
            mem["link"] = "up"
            mem["bond"] = bond_name
            mem["ip_mode"] = "unconfigured"
        ifaces.append({
            "name": bond_name,
            "mac": mac,
            "link": "up",
            "vlan": members[0].get("vlan") or "pxe",
            "fabric": members[0].get("fabric") or "fabric-0",
            "subnet": members[0].get("subnet") or "10.10.1.0/24",
            "ip_mode": "auto",
            "link_speed": max(int(x.get("link_speed") or 1000) for x in members),
            "is_boot": True,
            "bond_members": [x.get("name") for x in members],
        })
        for i in ifaces:
            if i.get("name") != bond_name:
                i["is_boot"] = False
        _log(m, f"Created bond {bond_name} from {', '.join(names)}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Bond {bond_name} created", "bond": bond_name}

    if action == "maas_set_boot_interface":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        iface_name = (payload.get("interface") or payload.get("name") or "eth0").strip()
        found = False
        for iface in m.get("interfaces") or []:
            is_boot = iface.get("name") == iface_name
            iface["is_boot"] = is_boot
            if is_boot:
                found = True
        if not found:
            return {"ok": False, "error": f"Interface {iface_name} not found"}
        _log(m, f"Boot interface set to {iface_name}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Boot interface → {iface_name}"}

    if action == "maas_apply_storage_layout":
        mid = int(payload.get("machine_id") or 1)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        layout = (payload.get("layout") or payload.get("storage_layout") or "flat").strip().lower()
        if layout not in ("flat", "lvm", "bcache", "raid10"):
            return {"ok": False, "error": f"Unknown storage layout {layout!r} (flat|lvm|bcache|raid10)"}
        _apply_storage_layout(m, layout)
        _log(m, f"Applied storage layout: {layout}")
        _save(session_id, entry)
        return {"ok": True, "message": f"Storage layout → {layout}", "storage_layout": layout}

    if action == "maas_add_machine":
        machines = state["maas"]["machines"]
        new_id = (max((mm.get("id") or 0) for mm in machines) + 1) if machines else 1
        hostname = (payload.get("hostname") or f"node-{new_id:02d}").strip()
        m = _machine(new_id, hostname, "New", "off", "")
        if payload.get("arch"):
            m["arch"] = payload["arch"]
        if payload.get("power_type"):
            m["power_type"] = payload["power_type"]
        if payload.get("bmc_address") or payload.get("bmc_ip"):
            m["bmc_address"] = payload.get("bmc_address") or payload.get("bmc_ip")
        if payload.get("bmc_user"):
            m["bmc_user"] = payload["bmc_user"]
        mac = payload.get("mac") or payload.get("mac_address")
        if mac and m.get("interfaces"):
            m["interfaces"][0]["mac"] = mac
        _log(m, "Machine added via MAAS add-machine wizard")
        _machine_event(m, "Node changed status - New")
        machines.append(m)
        state["ipmi"]["bmc_hosts"].append({
            "name": hostname,
            "reachable": True,
            "power": "off",
            "address": m.get("bmc_address"),
        })
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Machine {hostname} added (New)",
            "severity": "info",
        })
        try:
            from apps.labs.provisioner.simulation.server_identity import upsert_from_maas_machine
            upsert_from_maas_machine(session_id, m, source="baremetal")
        except Exception:
            pass
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {hostname} added (New)", "machine_id": new_id}

    if action == "maas_update_settings":
        _ensure_maas_infra(state)
        settings = state["maas"].setdefault("settings", {})
        # Accept flat payload or nested {settings: {...}}
        patch = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
        for key, value in (patch or {}).items():
            if key in ("machine_id", "machine_ids"):
                continue
            settings[key] = value
        # Clear scenario blockers once the relevant leaf setting looks configured.
        if str(settings.get("ntp_servers") or "").strip():
            broken.pop("settings_ntp_wrong", None)
        if str(settings.get("commissioning_distro_series") or "").strip():
            broken.pop("settings_commissioning_incomplete", None)
        if settings.get("enable_http_proxy") and str(settings.get("http_proxy") or "").strip():
            broken.pop("settings_proxy_required", None)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": "MAAS configuration updated",
            "severity": "success",
        })
        _save(session_id, entry)
        return {"ok": True, "message": "Settings saved", "settings": settings}

    if action == "maas_dhcp_toggle":
        _ensure_maas_infra(state)
        dhcp = state["maas"].setdefault("dhcp", {})
        enabled = payload.get("enabled")
        if enabled is None:
            enabled = not dhcp.get("enabled", True)
        dhcp["enabled"] = bool(enabled)
        if dhcp["enabled"]:
            broken.pop("dhcp_disabled", None)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"DHCP {'enabled' if dhcp['enabled'] else 'disabled'} on VLAN {dhcp.get('vlan') or 'untagged'}",
            "severity": "info",
        })
        _save(session_id, entry)
        return {"ok": True, "message": f"DHCP {'enabled' if dhcp['enabled'] else 'disabled'}", "dhcp": dhcp}

    if action == "maas_enter_rescue":
        mid = int(payload.get("machine_id") or broken.get("needs_rescue_enter") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        if m.get("status") not in ("Deployed", "Ready"):
            return {"ok": False, "error": f"Machine {mid} must be Deployed or Ready to enter rescue mode (is {m.get('status')})"}
        m["status_before_rescue"] = m.get("status")
        m["status"] = "Entering rescue mode"
        m["progress"] = 0
        m["phase_started_at"] = _now()
        m["phase_duration"] = RESCUE_SECONDS
        _log(m, "Entering rescue mode — booting ephemeral environment")
        _machine_event(m, "Node changed status - Entering rescue mode")
        broken.pop("needs_rescue_enter", None)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Machine {mid} entering rescue mode",
            "severity": "info",
        })
        _save(session_id, entry)
        return {"ok": True, "message": "Entering rescue mode", "machine_id": mid}

    if action == "maas_exit_rescue":
        mid = int(payload.get("machine_id") or broken.get("needs_rescue_exit") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        if m.get("status") != "Rescue mode":
            return {"ok": False, "error": f"Machine {mid} must be in Rescue mode to exit (is {m.get('status')})"}
        m["status"] = "Exiting rescue mode"
        m["progress"] = 0
        m["phase_started_at"] = _now()
        m["phase_duration"] = RESCUE_SECONDS
        _log(m, "Exiting rescue mode — rebooting into deployed OS")
        _machine_event(m, "Node changed status - Exiting rescue mode")
        broken.pop("needs_rescue_exit", None)
        broken.pop("machine_in_rescue", None)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Machine {mid} exiting rescue mode",
            "severity": "info",
        })
        _save(session_id, entry)
        return {"ok": True, "message": "Exiting rescue mode", "machine_id": mid}

    if action == "maas_add_dns_record":
        _ensure_maas_infra(state)
        domain_name = (payload.get("domain") or "maas").strip()
        domains = state["maas"].setdefault("domains", [])
        domain = next((d for d in domains if d.get("name") == domain_name), None)
        if not domain:
            domain = {"name": domain_name, "authoritative": True, "records": []}
            domains.append(domain)
        record = {
            "type": (payload.get("type") or "A").strip().upper(),
            "name": (payload.get("name") or "record").strip(),
            "data": (payload.get("data") or payload.get("value") or "").strip(),
        }
        domain.setdefault("records", []).append(record)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"DNS record {record['name']} added to {domain_name}",
            "severity": "success",
        })
        _save(session_id, entry)
        return {"ok": True, "message": f"DNS record added to {domain_name}", "record": record}

    if action == "maas_create_user":
        _ensure_maas_infra(state)
        users = state["maas"].setdefault("users", [])
        username = (payload.get("username") or "new-user").strip()
        if any(u.get("username") == username for u in users):
            return {"ok": False, "error": f"User {username} already exists"}
        row = {
            "username": username,
            "is_admin": bool(payload.get("is_admin")),
            "email": payload.get("email") or f"{username}@maas.local",
        }
        users.append(row)
        if username == "operator" or not row["is_admin"]:
            broken.pop("needs_operator_user", None)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"User {username} created",
            "severity": "success",
        })
        _save(session_id, entry)
        return {"ok": True, "message": f"User {username} created", "user": row}

    if action == "maas_delete_user":
        _ensure_maas_infra(state)
        users = state["maas"].setdefault("users", [])
        username = (payload.get("username") or "").strip()
        before = len(users)
        state["maas"]["users"] = [u for u in users if u.get("username") != username]
        removed = before - len(state["maas"]["users"])
        if removed:
            state["events"].insert(0, {
                "time": _now_iso(),
                "message": f"User {username} deleted",
                "severity": "info",
            })
        _save(session_id, entry)
        return {"ok": True, "message": f"User {username} deleted" if removed else f"User {username} not found"}

    if action == "maas_create_zone":
        _ensure_maas_infra(state)
        name = (payload.get("name") or f"zone-{len(state['maas'].get('zones') or []) + 1}").strip()
        zones = state["maas"].setdefault("zones", [])
        if any(z.get("name") == name for z in zones):
            return {"ok": False, "error": f"Zone '{name}' already exists"}
        row = {"name": name, "description": payload.get("description") or ""}
        zones.append(row)
        _save(session_id, entry)
        return {"ok": True, "message": f"Zone {name} created", "zone": row}

    if action == "maas_create_pool":
        _ensure_maas_infra(state)
        name = (payload.get("name") or f"pool-{len(state['maas'].get('resource_pools') or []) + 1}").strip()
        pools = state["maas"].setdefault("resource_pools", [])
        if any(p.get("name") == name for p in pools):
            return {"ok": False, "error": f"Pool '{name}' already exists"}
        row = {"name": name, "description": payload.get("description") or "", "machine_count": 0}
        pools.append(row)
        _save(session_id, entry)
        return {"ok": True, "message": f"Resource pool {name} created", "pool": row}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            state.setdefault("events", []).insert(0, {
                "time": _now_iso(), "message": v2.get("message") or action, "severity": "success",
            })
            _save(session_id, entry)
        return v2

    # An action may have advanced the lifecycle even if it hit no explicit branch;
    # persist so the tick is not lost.
    _save(session_id, entry)
    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_baremetal_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No bare metal session"
    # Advance the wall-clock lifecycle before grading so a machine that finished
    # commissioning/deploying between requests is scored against its real state.
    if _tick(entry["state"]):
        _save(session_id, entry)
    # Optional Image Factory grading: clear when Deployed machine uses custom/* image.
    if packer_factory.clear_needs_custom_image_deploy(entry["state"]):
        _save(session_id, entry)
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "Bare metal environment still has unresolved issues"
    return True, "Bare metal lab objectives met"
