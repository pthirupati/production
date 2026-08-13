"""Durable pending Jira @team replies (audit X2b).

Celery ``countdown`` delivery can be silently dropped when a worker restarts
or the message expires. This module keeps a DB-backed pending row that a
beat sweeper re-delivers when due.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from django.utils import timezone

from apps.jira_integration.models import PendingTeamReply

logger = logging.getLogger(__name__)


def _as_aware(now: float | None) -> datetime:
    if now is None:
        return timezone.now()
    return datetime.fromtimestamp(float(now), tz=dt_timezone.utc)


def _row_to_dict(row: PendingTeamReply) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "issue_key": row.issue_key,
        "session_id": row.session_id or "",
        "author": row.author,
        "message": row.message,
        "actions": list(row.actions or []),
        "scenario_slug": row.scenario_slug or "",
        "created_at": row.created_at,
        "deliver_at": row.deliver_at,
        "attempts": row.attempts,
    }


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
    now = timezone.now()
    row = PendingTeamReply.objects.create(
        issue_key=issue_key,
        session_id=session_id or "",
        author=author,
        message=message,
        actions=list(actions or []),
        scenario_slug=scenario_slug or "",
        deliver_at=now + timedelta(seconds=max(0, int(delay_seconds))),
    )
    return _row_to_dict(row)


def cancel_pending_for_issue(issue_key: str) -> int:
    deleted, _ = PendingTeamReply.objects.filter(issue_key=issue_key).delete()
    return deleted


def list_pending() -> list[dict]:
    return [_row_to_dict(r) for r in PendingTeamReply.objects.all()]


def deliver_due_pending_team_replies(now: float | None = None) -> dict[str, int]:
    """Beat/worker entrypoint: deliver every pending row whose ``deliver_at`` ≤ now."""
    from apps.jira_integration.team_bots import deliver_team_reply_now

    now_dt = _as_aware(now)
    due = list(PendingTeamReply.objects.filter(deliver_at__lte=now_dt).order_by("deliver_at"))
    if not due:
        return {
            "delivered": 0,
            "remaining": PendingTeamReply.objects.count(),
            "failed": 0,
        }

    delivered = 0
    failed = 0
    for row in due:
        try:
            deliver_team_reply_now(
                row.issue_key or "",
                row.session_id or "",
                row.author or "ops-bot",
                row.message or "",
                list(row.actions or []),
                row.scenario_slug or "",
            )
            row.delete()
            delivered += 1
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "pending team reply delivery failed id=%s issue=%s: %s",
                row.id, row.issue_key, exc,
            )
            row.attempts = int(row.attempts or 0) + 1
            if row.attempts < 5:
                row.deliver_at = now_dt + timedelta(seconds=30)
                row.save(update_fields=["attempts", "deliver_at"])
            else:
                row.delete()
            failed += 1

    return {
        "delivered": delivered,
        "remaining": PendingTeamReply.objects.count(),
        "failed": failed,
    }
