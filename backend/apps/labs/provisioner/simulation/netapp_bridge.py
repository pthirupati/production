"""Cross-technology bridge: NetApp ONTAP ⇄ Linux lab terminal.

LUN map / NFS export actions in the NetApp console register pending guest
block/export events so the same lab session's RHEL terminal can reveal them.
Fail-closed: with nothing pending the terminal sees no new devices.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"netapp_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_luns": [], "pending_exports": []}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_luns", [])
    data.setdefault("pending_exports", [])
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_lun_mapped(
    session_id: str,
    path: str,
    size_gb: int,
    device: str = "/dev/mapper/netapp0",
) -> None:
    """ONTAP LUN map → queue a multipath block device for the guest to reveal."""
    data = _load(session_id)
    if not any(e.get("device") == device for e in data["pending_luns"]):
        data["pending_luns"].append({
            "path": path or "",
            "size_gb": int(size_gb),
            "device": device or "/dev/mapper/netapp0",
        })
        _save(session_id, data)


def consume_lun_mapped(session_id: str) -> list:
    data = _load(session_id)
    pending = data.get("pending_luns", [])
    if not pending:
        return []
    data["pending_luns"] = []
    _save(session_id, data)
    return pending


def record_export_ready(session_id: str, volume: str, export_path: str) -> None:
    """ONTAP NFS export → queue an export the guest can mount."""
    data = _load(session_id)
    data["pending_exports"].append({
        "volume": volume or "",
        "export_path": export_path or "",
    })
    _save(session_id, data)


def consume_export_ready(session_id: str) -> list:
    data = _load(session_id)
    pending = data.get("pending_exports", [])
    if not pending:
        return []
    data["pending_exports"] = []
    _save(session_id, data)
    return pending


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
