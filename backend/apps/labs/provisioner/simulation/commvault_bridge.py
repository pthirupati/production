"""Cross-technology bridge: Commvault CommCell ⇄ Linux lab terminal.

Restore/backup actions in the CommCell console register pending guest filesystem
changes so the same lab session's RHEL terminal can reveal restored files.
Fail-closed: with nothing pending the terminal sees no new paths.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200


def _key(session_id: str) -> str:
    return f"commvault_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending_restore_files": [], "pending_backup_marks": []}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending_restore_files", [])
    data.setdefault("pending_backup_marks", [])
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def record_restore_files(session_id: str, paths: list[str], client: str) -> None:
    """CommCell restore → queue guest paths that appear after the next reveal."""
    data = _load(session_id)
    data["pending_restore_files"].append({
        "paths": list(paths or []),
        "client": client or "",
    })
    _save(session_id, data)


def consume_restore_files(session_id: str) -> list:
    """Drain pending restore paths for the Linux terminal (empty list if none)."""
    data = _load(session_id)
    pending = data.get("pending_restore_files", [])
    if not pending:
        return []
    data["pending_restore_files"] = []
    _save(session_id, data)
    return pending


def record_backup_marked(session_id: str, paths: list) -> None:
    """CommCell backup → mark guest paths as covered by a successful backup."""
    data = _load(session_id)
    for path in paths or []:
        data["pending_backup_marks"].append({"path": path})
    _save(session_id, data)


def consume_backup_marks(session_id: str) -> list:
    data = _load(session_id)
    pending = data.get("pending_backup_marks", [])
    if not pending:
        return []
    data["pending_backup_marks"] = []
    _save(session_id, data)
    return pending


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))
