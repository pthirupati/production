"""Cross-technology bridge: Data Center Floor ⇄ Linux lab terminal.

Physical component actions (disk replace, NIC reseat) publish pending guest
changes so the scenario Lab Server OS reflects the same hardware the tech
touched on the floor.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"datacenter_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_disk": None, "pending_nic": None, "instance_power": None, "power_asset_id": None}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_disk", None)
    data.setdefault("pending_nic", None)
    data.setdefault("instance_power", None)
    data.setdefault("power_asset_id", None)
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_power(session_id: str, action: str, *, asset_id: str = "") -> None:
    """BMC / chassis power change → Lab Server terminal freeze/thaw."""
    if action not in ("on", "off", "start", "stop", "reset", "cycle"):
        return
    data = _load(session_id)
    # Normalize to consume_power vocabulary used by RHELShell.
    data["instance_power"] = "stop" if action in ("off", "stop") else "start"
    data["power_asset_id"] = asset_id or None
    _save(session_id, data)


def consume_power(session_id: str) -> str | None:
    data = _load(session_id)
    action = data.get("instance_power")
    if not action:
        return None
    data["instance_power"] = None
    _save(session_id, data)
    return action


def record_disk_replaced(session_id: str, asset_id: str, *, size_gb: int = 1920) -> None:
    data = _load(session_id)
    data["pending_disk"] = {"asset_id": asset_id, "size_gb": size_gb, "action": "replaced"}
    _save(session_id, data)
    try:
        from .server_identity import get_primary, set_power
        # Touch primary so consoles refresh; disk inventory sync is best-effort.
        primary = get_primary(session_id)
        if primary and primary.get("power") == "off":
            set_power(session_id, primary["id"], "on", source="datacenter")
    except Exception:
        pass


def record_nic_reseated(session_id: str, asset_id: str) -> None:
    data = _load(session_id)
    data["pending_nic"] = {"asset_id": asset_id, "action": "reseated"}
    _save(session_id, data)


def consume_pending_disk(session_id: str) -> dict | None:
    data = _load(session_id)
    pending = data.get("pending_disk")
    if not pending:
        return None
    data["pending_disk"] = None
    _save(session_id, data)
    return pending


def consume_pending_nic(session_id: str) -> dict | None:
    data = _load(session_id)
    pending = data.get("pending_nic")
    if not pending:
        return None
    data["pending_nic"] = None
    _save(session_id, data)
    return pending
