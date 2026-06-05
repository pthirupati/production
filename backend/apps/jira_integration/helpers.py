"""Shared Jira status helpers."""

CLOSED_STATUSES = frozenset({
    "done", "closed", "resolved", "cancelled", "complete", "completed",
})


def is_jira_closed(status: str) -> bool:
    if not status:
        return False
    normalized = status.strip().lower()
    return normalized in CLOSED_STATUSES or any(
        word in normalized for word in ("done", "closed", "resolved", "cancelled")
    )
