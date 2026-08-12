"""Durable pending Jira @team replies (audit X2b).

Celery ``countdown`` delivery can be silently dropped when a worker restarts
or the message expires. This module keeps a cache-backed pending row that a
beat sweeper re-delivers when due — fail-closed if cache is empty (nothing to
replay).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from django.core.cache import cache

logger = logging.getLogger(__name__)

PENDING_KEY = "jira:pending_team_replies"
PENDING_TTL = 86400  # 24h — replies older than this are abandoned


def _load() -> list[dict]:
    raw = cache.get(PENDING_KEY)
    if raw is None:
        return []
    data = json.loads(raw) if isinstance(raw, str) else raw
    return list(data) if isinstance(data, list) else []


def _save(rows: list[dict]) -> None:
    cache.set(PENDING_KEY, json.dumps(rows, default=str), PENDING_TTL)


def enqueue_pending_team_reply(
    *,
    issue_key: str,
    session_id: str,
    author: str,
    message: str,
    actions: list[str] | None = None,
    scenario_slug: str = "",
    delay_seconds: int = 30,
) -> dict[str, Any]:
    """Record a pending reply that beat will deliver at ``deliver_at``."""
    now = time.time()
    row = {
        "id": str(uuid.uuid4()),
        "issue_key": issue_key,
        "session_id": session_id or "",
        "author": author,
        "message": message,
        "actions": list(actions or []),
        "scenario_slug": scenario_slug or "",
        "created_at": now,
        "deliver_at": now + max(0, int(delay_seconds)),
        "attempts": 0,
    }
    rows = _load()
    rows.append(row)
    _save(rows)
    return row


def cancel_pending_for_issue(issue_key: str) -> int:
    rows = _load()
    keep = [r for r in rows if r.get("issue_key") != issue_key]
    removed = len(rows) - len(keep)
    if removed:
        _save(keep)
    return removed


def list_pending() -> list[dict]:
    return _load()


def deliver_due_pending_team_replies(now: float | None = None) -> dict[str, int]:
    """Beat/worker entrypoint: deliver every pending row whose ``deliver_at`` ≤ now."""
    from apps.jira_integration.team_bots import deliver_team_reply_now

    now = time.time() if now is None else now
    rows = _load()
    if not rows:
        return {"delivered": 0, "remaining": 0, "failed": 0}

    remaining: list[dict] = []
    delivered = 0
    failed = 0
    for row in rows:
        if float(row.get("deliver_at") or 0) > now:
            remaining.append(row)
            continue
        try:
            deliver_team_reply_now(
                row.get("issue_key") or "",
                row.get("session_id") or "",
                row.get("author") or "ops-bot",
                row.get("message") or "",
                list(row.get("actions") or []),
                row.get("scenario_slug") or "",
            )
            delivered += 1
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "pending team reply delivery failed id=%s issue=%s: %s",
                row.get("id"), row.get("issue_key"), exc,
            )
            row["attempts"] = int(row.get("attempts") or 0) + 1
            if row["attempts"] < 5:
                row["deliver_at"] = now + 30
                remaining.append(row)
            failed += 1

    _save(remaining)
    return {"delivered": delivered, "remaining": len(remaining), "failed": failed}
