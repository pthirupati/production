"""Cross-technology bridge: Google Cloud Console simulator ⇄ Linux lab terminal.

Mirrors azure_bridge.py's seam for GCP (apps.vmware_sim.gcp_engine) and this
package's UnifiedSimulationEngine — two separate in-memory engines that
describe the SAME Compute Engine instance for a cross-technology lab, sharing
one lab session id. Closes the same canonical cross-tech example every cloud
in this platform commits to:

    Change machine type -> vCPU and RAM change inside Linux

A machine-type change in the GCP console queues a pending vCPU/RAM change
here; the Linux terminal for the SAME session applies it (via
RHELOSState.set_hardware) the next time a command runs, so
`nproc`/`free -h`/`lscpu`/`/proc/cpuinfo` all agree with whatever machine type
the learner picked in the console.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"gcp_bridge:{session_id}"


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


def record_instance_resize(session_id: str, machine_type: dict) -> None:
    """GCP console machine-type change -> queue a pending vCPU/RAM change for
    the Linux guest terminal to apply on its next command."""
    data = _load(session_id)
    data["pending_resize"] = {"vcpus": int(machine_type.get("vcpus", 2)), "ram_gb": int(machine_type.get("ram_gb", 4))}
    _save(session_id, data)


def consume_pending_resize(session_id: str) -> dict | None:
    """Drain a pending vCPU/RAM change (returns {"vcpus", "ram_gb"} or None).
    Called by the Linux terminal shell before each command."""
    data = _load(session_id)
    resize = data.get("pending_resize")
    if not resize:
        return None
    data["pending_resize"] = None
    _save(session_id, data)
    return resize


def record_instance_power(session_id: str, action: str) -> None:
    """GCP console -> terminal: the instance changed power state."""
    if action not in ("start", "stop", "reset"):
        return
    data = _load(session_id)
    data["instance_power"] = action
    _save(session_id, data)
    try:
        from .server_identity import get_primary, set_power
        primary = get_primary(session_id)
        if primary:
            power = "off" if action == "stop" else ("reboot_pending" if action == "reset" else "on")
            set_power(session_id, primary["id"], power, source="gcp")
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


def record_disk_attach(session_id: str, disk_name: str, *, size_gb: int = 100) -> None:
    try:
        from .server_identity import attach_disk, get_primary
        primary = get_primary(session_id)
        if primary:
            attach_disk(session_id, primary["id"], name=disk_name, size_gb=int(size_gb), source="gcp")
    except Exception:
        pass


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
