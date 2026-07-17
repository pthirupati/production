"""Cross-technology bridge: Azure Portal console simulator ⇄ Linux lab terminal.

Mirrors aws_bridge.py's seam for the Azure console (apps.vmware_sim.azure_engine)
and this package's UnifiedSimulationEngine — two separate in-memory engines that
describe the SAME Azure VM for a cross-technology lab, sharing one lab session
id. This is specifically what closes the master-prompt's canonical example:

    Azure: Resize VM -> CPU and RAM change inside Linux

A resize in the Azure console queues a pending vCPU/RAM change here; the Linux
terminal for the SAME session applies it (via RHELOSState.set_hardware) the
next time a command runs, so `nproc`/`free -h`/`lscpu`/`/proc/cpuinfo` all
agree with whatever size the learner picked in the portal — never a scripted
number that can drift out of sync.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"azure_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_resize": None, "instance_power": None}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_resize", None)
    data.setdefault("instance_power", None)
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_vm_resize(session_id: str, size: dict) -> None:
    """Azure console resize -> queue a pending vCPU/RAM change for the Linux
    guest terminal to apply on its next command (see consume_pending_resize)."""
    data = _load(session_id)
    data["pending_resize"] = {"vcpus": int(size.get("vcpus", 2)), "ram_gb": int(size.get("ram_gb", 4))}
    _save(session_id, data)


def consume_pending_resize(session_id: str) -> dict | None:
    """Drain a pending vCPU/RAM change (returns {"vcpus", "ram_gb"} or None).
    Called by the Linux terminal shell before each command so hardware
    inspection commands always reflect the latest Azure Portal size."""
    data = _load(session_id)
    resize = data.get("pending_resize")
    if not resize:
        return None
    data["pending_resize"] = None
    _save(session_id, data)
    return resize


def record_vm_power(session_id: str, action: str) -> None:
    """Azure console -> terminal: the VM changed power state (start/stop/restart)."""
    if action not in ("start", "stop", "restart"):
        return
    data = _load(session_id)
    data["instance_power"] = action
    _save(session_id, data)
    try:
        from .server_identity import get_primary, set_power
        primary = get_primary(session_id)
        if primary:
            power = "off" if action == "stop" else ("reboot_pending" if action == "restart" else "on")
            set_power(session_id, primary["id"], power, source="azure")
    except Exception:
        pass


def consume_power(session_id: str) -> str | None:
    data = _load(session_id)
    action = data.get("instance_power")
    if not action:
        return None
    data.pop("instance_power", None)
    _save(session_id, data)
    return action


def record_disk_attach(session_id: str, disk_name: str, *, size_gb: int = 128) -> None:
    """Azure console managed-disk attach -> also mirrored into ServerIdentity
    so the terminal's disk inventory (and any other open console) agrees."""
    try:
        from .server_identity import attach_disk, get_primary
        primary = get_primary(session_id)
        if primary:
            attach_disk(session_id, primary["id"], name=disk_name, size_gb=int(size_gb), source="azure")
    except Exception:
        pass


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
