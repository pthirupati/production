"""Cross-technology bridge: Dell EMC Unisphere ⇄ Linux lab terminal.

Volume map / SRDF failover actions in the Unisphere console register pending
guest block/SRDF events so the same lab session's RHEL terminal can reveal them.
Fail-closed: with nothing pending the terminal sees no new devices.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"dellemc_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_volumes": [], "pending_srdf": []}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_volumes", [])
    data.setdefault("pending_srdf", [])
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_volume_mapped(
    session_id: str,
    volume_id: str,
    size_gb: int,
    device: str = "/dev/sdx",
) -> None:
    """Unisphere volume map → queue a SCSI block device for the guest to reveal."""
    data = _load(session_id)
    if not any(e.get("device") == device for e in data["pending_volumes"]):
        data["pending_volumes"].append({
            "volume_id": volume_id or "",
            "size_gb": int(size_gb),
            "device": device or "/dev/sdx",
        })
        _save(session_id, data)


def consume_volume_mapped(session_id: str) -> list:
    data = _load(session_id)
    pending = data.get("pending_volumes", [])
    if not pending:
        return []
    data["pending_volumes"] = []
    _save(session_id, data)
    return pending


def record_srdf_failover(session_id: str, name: str) -> None:
    """Unisphere SRDF failover → queue an event the guest/lab can observe."""
    data = _load(session_id)
    data["pending_srdf"].append({"name": name or "", "action": "failover"})
    _save(session_id, data)


def consume_srdf_events(session_id: str) -> list:
    data = _load(session_id)
    pending = data.get("pending_srdf", [])
    if not pending:
        return []
    data["pending_srdf"] = []
    _save(session_id, data)
    return pending


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
