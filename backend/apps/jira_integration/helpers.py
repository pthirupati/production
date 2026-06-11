"""Shared Jira status helpers."""

from django.conf import settings

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


def in_app_jira_url(issue_key: str) -> str:
    """Always return the in-app Jira simulation URL for a ticket key."""
    if not issue_key:
        return ""
    return f"{settings.SITE_URL.rstrip('/')}/jira/{issue_key}"


def resolve_jira_issue_url(issue_key: str, stored_url: str = "", *, external: bool = False) -> str:
    """
    Resolve the URL shown for a Jira ticket.
    Learners always get the in-app simulation; staff may opt into external Atlassian links.
    """
    if not issue_key:
        return ""
    if external and stored_url and stored_url.startswith("http"):
        return stored_url
    return in_app_jira_url(issue_key)
