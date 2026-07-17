"""Cross-technology bridge: AWS console simulator ⇄ Linux lab terminal.

The AWS simulator (apps.vmware_sim.aws_engine) and the Linux lab simulator
(this package's UnifiedSimulationEngine) are SEPARATE in-memory engines, but for
a cross-technology lab they describe the SAME EC2 instance and share one lab
session id. This module is the seam between them, mirroring vmware_bridge.py's
disk/power reveal pattern for the AWS console:

- Attaching an EBS volume in the AWS console (or from the frontend AWS UI when
  it cannot call the console REST API directly) registers a pending volume
  event here. The Linux terminal for the SAME session reveals the new block
  device only once it actually inspects the disks (e.g. `lsblk`, `fdisk -l`),
  exactly like the VMware hot-add-disk train.
- A power action performed on the EC2 instance from the AWS console (start /
  stop / reboot) is recorded here so the terminal side can reflect the guest's
  power state without the two engines sharing process memory.

Storage is Django cache (Redis in prod), so an attach performed on the AWS web
worker is visible to the terminal WebSocket worker. Fail-closed by
construction: with no pending volume event the terminal sees nothing new.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200  # match the AWS/Linux session TTLs (2h)

_DISK_LETTERS = "fghijklmnop"  # AWS block devices for hot-attached volumes start at /dev/sdf


def _key(session_id: str) -> str:
    return f"aws_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_volumes": [], "revealed_volumes": [], "removed_volumes": []}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_volumes", [])
    data.setdefault("revealed_volumes", [])
    data.setdefault("removed_volumes", [])
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def _next_device(data: dict) -> str:
    used = {e.get("device") for e in data.get("pending_volumes", [])}
    used |= set(data.get("revealed_volumes", []))
    for letter in _DISK_LETTERS:
        dev = f"/dev/sd{letter}"
        if dev not in used:
            return dev
    return "/dev/sdz"


def record_volume_attach(
    session_id: str,
    volume_id: str,
    *,
    size_gb: int = 20,
    device: str | None = None,
    instance_id: str | None = None,
) -> str:
    """AWS console EBS attach → register a hot-attached volume the guest cannot
    yet see. Returns the /dev path the volume will appear as once revealed."""
    data = _load(session_id)
    dev = device or _next_device(data)
    if not any(e.get("device") == dev for e in data["pending_volumes"]) and dev not in data["revealed_volumes"]:
        data["pending_volumes"].append({
            "device": dev,
            "volume_id": volume_id,
            "size_gb": int(size_gb),
            "instance_id": instance_id or "",
        })
        _save(session_id, data)
    try:
        from .server_identity import attach_disk, get_primary, upsert_server
        primary = get_primary(session_id)
        if primary:
            letter = (dev or "/dev/sdf").rstrip("0123456789").split("/")[-1]
            attach_disk(session_id, primary["id"], name=letter or "sdf", size_gb=int(size_gb), source="aws")
        elif instance_id:
            upsert_server(session_id, {"id": f"aws-{instance_id}", "hostname": instance_id}, source="aws")
    except Exception:
        pass
    return dev


def record_volume_detach(
    session_id: str,
    device: str,
    *,
    instance_id: str | None = None,
) -> None:
    """AWS console EBS detach → the guest should stop seeing this block device
    on its next disk inspection (mirrors record_volume_attach in reverse)."""
    data = _load(session_id)
    # A device that never made it out of "pending" (never revealed) just gets
    # dropped from the queue instead of round-tripping through "removed".
    data["pending_volumes"] = [e for e in data["pending_volumes"] if e.get("device") != device]
    if device in data.get("revealed_volumes", []):
        data["revealed_volumes"] = [d for d in data["revealed_volumes"] if d != device]
        if device not in data["removed_volumes"]:
            data["removed_volumes"].append(device)
    _save(session_id, data)
    try:
        from .server_identity import detach_disk, get_primary
        primary = get_primary(session_id)
        if primary:
            letter = (device or "").rstrip("0123456789").split("/")[-1]
            detach_disk(session_id, primary["id"], name=letter or "sdf", source="aws")
    except Exception:
        pass


def consume_removed_volume_events(session_id: str) -> list[str]:
    """Drain every volume detach event the guest should now see (device
    disappears from lsblk on the terminal's next disk inspection)."""
    data = _load(session_id)
    removed = data.get("removed_volumes", [])
    if not removed:
        return []
    data["removed_volumes"] = []
    _save(session_id, data)
    return removed


def has_pending_volumes(session_id: str) -> bool:
    return bool(_load(session_id).get("pending_volumes"))


def pending_volumes(session_id: str) -> list[dict]:
    return list(_load(session_id).get("pending_volumes", []))


def consume_volume_events(session_id: str) -> list[dict]:
    """Drain every volume attach event the guest should now see (e.g. on the
    terminal's next `lsblk`/disk inspection). Moves pending -> revealed so a
    second inspection does not re-reveal the same device."""
    data = _load(session_id)
    pending = data.get("pending_volumes", [])
    if not pending:
        return []
    data["pending_volumes"] = []
    data["revealed_volumes"] = list(data.get("revealed_volumes", [])) + [e["device"] for e in pending]
    _save(session_id, data)
    return pending


def record_instance_power(session_id: str, action: str) -> None:
    """AWS console → terminal: the EC2 instance changed power state from the
    console (`start` | `stop` | `reboot`). Drained by the terminal side the
    next time it checks guest power/uptime. Last-writer-wins semantics."""
    if action not in ("start", "stop", "reboot"):
        return
    data = _load(session_id)
    data["instance_power"] = action
    _save(session_id, data)
    try:
        from .server_identity import get_primary, set_power
        primary = get_primary(session_id)
        if primary:
            power = "on" if action == "start" else ("reboot_pending" if action == "reboot" else "off")
            set_power(session_id, primary["id"], power, source="aws")
    except Exception:
        pass


def consume_power(session_id: str) -> str | None:
    """Drain a pending instance power event (returns 'start'|'stop'|'reboot'|None)."""
    data = _load(session_id)
    action = data.get("instance_power")
    if not action:
        return None
    data.pop("instance_power", None)
    _save(session_id, data)
    return action


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
