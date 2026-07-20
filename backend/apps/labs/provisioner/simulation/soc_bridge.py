"""Cross-technology bridge: SOC console ⇄ Linux lab terminal.

Block-IP / quarantine actions in the SOC console register pending guest firewall
and containment events so the same lab session's RHEL terminal can reflect them.
Fail-closed: with nothing pending the terminal sees no new blocks.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"soc_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_blocked_ips": [], "pending_quarantine": []}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_blocked_ips", [])
    data.setdefault("pending_quarantine", [])
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_block_ip(session_id: str, ip: str) -> None:
    """SOC block-IP → queue an address the guest firewall should treat as blocked."""
    if not ip:
        return
    data = _load(session_id)
    if ip not in data["pending_blocked_ips"]:
        data["pending_blocked_ips"].append(ip)
        _save(session_id, data)


def consume_blocked_ips(session_id: str) -> list[str]:
    data = _load(session_id)
    pending = data.get("pending_blocked_ips", [])
    if not pending:
        return []
    data["pending_blocked_ips"] = []
    _save(session_id, data)
    return list(pending)


def record_quarantine(session_id: str, asset: str) -> None:
    """SOC quarantine → queue a host/asset the guest lab should treat as isolated."""
    if not asset:
        return
    data = _load(session_id)
    data["pending_quarantine"].append({"asset": asset})
    _save(session_id, data)


def consume_quarantine(session_id: str) -> list:
    data = _load(session_id)
    pending = data.get("pending_quarantine", [])
    if not pending:
        return []
    data["pending_quarantine"] = []
    _save(session_id, data)
    return pending


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))


def clear_blocked_ips(session_id: str) -> None:
    data = _load(session_id)
    data["pending_blocked_ips"] = []
    _save(session_id, data)


def clear_quarantine(session_id: str) -> None:
    data = _load(session_id)
    data["pending_quarantine"] = []
    _save(session_id, data)
