"""
In-app Jira simulation — full ticket lifecycle without Atlassian Cloud.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .helpers import is_jira_closed
from .models import JiraCommentLog, JiraTicketLog, UserScenarioJiraTicket

logger = logging.getLogger(__name__)

SIMULATED_STATUSES = ("To Do", "In Progress", "On Hold", "Done", "Closed")

ALLOWED_TRANSITIONS = {
    "To Do": {"In Progress", "On Hold"},
    "In Progress": {"On Hold", "Done", "To Do"},
    "On Hold": {"In Progress", "To Do"},
    "Done": {"Closed", "In Progress"},
    "Closed": {"To Do"},
}


def use_simulated_jira() -> bool:
    """Use local ticket simulation instead of Jira Cloud API."""
    return getattr(settings, "JIRA_SIMULATION_MODE", True)


def _next_issue_key() -> str:
    prefix = getattr(settings, "JIRA_SIMULATION_PREFIX", "KAN")
    with transaction.atomic():
        last = (
            UserScenarioJiraTicket.objects.filter(simulated=True, issue_key__startswith=f"{prefix}-")
            .order_by("-id")
            .values_list("issue_key", flat=True)
            .first()
        )
        num = 1
        if last and "-" in last:
            try:
                num = int(last.split("-", 1)[1]) + 1
            except ValueError:
                num = UserScenarioJiraTicket.objects.filter(simulated=True).count() + 1
        return f"{prefix}-{num}"


def _build_summary(scenario, user) -> str:
    return f"[FixitLab] {scenario.title} — {user.username}"


def _build_description(session=None, user=None, scenario=None) -> str:
    from .sync import _build_issue_body
    return _build_issue_body(session=session, user=user, scenario=scenario)


def _log(session, issue_key, issue_url, action, jira_status="", details=None):
    if session is None:
        return
    JiraTicketLog.objects.create(
        session=session,
        issue_key=issue_key,
        issue_url=issue_url,
        action=action,
        jira_status=jira_status,
        details=details or {},
    )


def _ticket_url(issue_key: str) -> str:
    site = settings.SITE_URL.rstrip("/")
    return f"{site}/jira/{issue_key}"


def ensure_scenario_ticket(user, scenario) -> dict:
    mapping, created = UserScenarioJiraTicket.objects.get_or_create(
        user=user,
        scenario=scenario,
        defaults={"issue_key": "", "issue_url": "", "simulated": True},
    )

    needs_create = created or not mapping.issue_key
    if needs_create:
        issue_key = _next_issue_key()
        mapping.issue_key = issue_key
        mapping.issue_url = _ticket_url(issue_key)
        mapping.summary = _build_summary(scenario, user)
        mapping.description = _build_description(user=user, scenario=scenario)
        mapping.priority = getattr(scenario, "jira_priority", "") or "Medium"
        mapping.jira_status = "To Do"
        mapping.simulated = True
        if mapping.run_count < 1:
            mapping.run_count = 1
        mapping.save()

    return {
        "jira_issue_key": mapping.issue_key,
        "jira_issue_url": mapping.issue_url,
        "jira_enabled": True,
        "jira_status": mapping.jira_status,
        "jira_run_count": mapping.run_count,
        "jira_created": needs_create,
        "simulated": True,
    }


def sync_lab_started(session) -> dict:
    scenario = session.scenario
    user = session.user
    is_reset = False

    mapping, created = UserScenarioJiraTicket.objects.get_or_create(
        user=user,
        scenario=scenario,
        defaults={"issue_key": "", "issue_url": "", "simulated": True},
    )

    if created or not mapping.issue_key:
        issue_key = _next_issue_key()
        mapping.issue_key = issue_key
        mapping.issue_url = _ticket_url(issue_key)
        mapping.summary = _build_summary(scenario, user)
        mapping.description = _build_description(session=session)
        mapping.priority = getattr(scenario, "jira_priority", "") or "Medium"
        mapping.run_count = 1
        mapping.jira_status = "In Progress"
        mapping.simulated = True
        mapping.last_session = session
        mapping.save()
        _log(session, issue_key, mapping.issue_url, "created", "In Progress", {"run": 1})
    else:
        is_reset = True
        mapping.run_count += 1
        mapping.last_session = session
        mapping.jira_status = "In Progress"
        mapping.save()
        add_comment(
            mapping,
            user,
            f"Lab restarted (run #{mapping.run_count}). Session: {session.id}.",
            session=session,
        )
        _log(session, mapping.issue_key, mapping.issue_url, "reset", "In Progress", {"run_count": mapping.run_count})

    session.jira_issue_key = mapping.issue_key
    session.jira_issue_url = mapping.issue_url
    session.save(update_fields=["jira_issue_key", "jira_issue_url"])

    _log(session, mapping.issue_key, mapping.issue_url, "in_progress", mapping.jira_status, {"reset": is_reset})

    return {
        "jira_issue_key": mapping.issue_key,
        "jira_issue_url": mapping.issue_url,
        "jira_enabled": True,
        "jira_run_count": mapping.run_count,
        "jira_reset": is_reset,
        "simulated": True,
    }


def sync_lab_completed(session, score=0, time_taken=0) -> dict:
    if not session.jira_issue_key:
        return {}
    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user, issue_key=session.jira_issue_key
    ).first()
    if not ticket:
        return {}
    minutes = time_taken // 60 if time_taken else 0
    add_comment(
        ticket,
        session.user,
        f"Lab completed successfully.\nScore: {score}/100\nTime: {minutes} min\nSession: {session.id}",
        session=session,
    )
    transition_ticket(ticket, session.user, "Done", session=session)
    _log(session, ticket.issue_key, ticket.issue_url, "completed", "Done", {"score": score})
    return {"jira_issue_key": ticket.issue_key, "jira_issue_url": ticket.issue_url, "jira_enabled": True}


def sync_lab_stopped(session, reason="Lab stopped") -> dict:
    if not session.jira_issue_key:
        return {}
    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user, issue_key=session.jira_issue_key
    ).first()
    if not ticket:
        return {}
    add_comment(ticket, session.user, f"Lab stopped: {reason}. Session: {session.id}.", session=session)
    transition_ticket(ticket, session.user, "To Do", session=session)
    _log(session, ticket.issue_key, ticket.issue_url, "cancelled", "To Do", {"reason": reason})
    return {"jira_issue_key": ticket.issue_key, "jira_issue_url": ticket.issue_url, "jira_enabled": True}


def sync_lab_in_progress(session) -> dict:
    if not session.jira_issue_key:
        return {}
    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user, issue_key=session.jira_issue_key
    ).first()
    if ticket:
        transition_ticket(ticket, session.user, "In Progress", session=session)
    return {"jira_issue_key": session.jira_issue_key, "jira_issue_url": session.jira_issue_url, "jira_enabled": True}


def get_ticket_for_user(issue_key: str, user) -> Optional[UserScenarioJiraTicket]:
    return UserScenarioJiraTicket.objects.filter(
        issue_key=issue_key, user=user
    ).select_related("scenario", "last_session").first()


def ticket_detail_payload(ticket: UserScenarioJiraTicket) -> dict:
    comments = JiraCommentLog.objects.filter(issue_key=ticket.issue_key).order_by("-created_at")[:20]
    logs = JiraTicketLog.objects.filter(issue_key=ticket.issue_key).order_by("-created_at")[:15]
    return {
        "issue_key": ticket.issue_key,
        "issue_url": ticket.issue_url,
        "summary": ticket.summary or _build_summary(ticket.scenario, ticket.user),
        "description": ticket.description or "",
        "jira_status": ticket.jira_status or "To Do",
        "priority": ticket.priority or "Medium",
        "simulated": ticket.simulated,
        "is_closed": is_jira_closed(ticket.jira_status),
        "run_count": ticket.run_count,
        "allowed_transitions": sorted(ALLOWED_TRANSITIONS.get(ticket.jira_status or "To Do", set())),
        "scenario": {
            "id": ticket.scenario_id,
            "slug": ticket.scenario.slug,
            "title": ticket.scenario.title,
        },
        "last_session_id": str(ticket.last_session_id) if ticket.last_session_id else None,
        "updated_at": ticket.updated_at.isoformat(),
        "comments": [
            {"author": c.author, "text": c.text, "created_at": c.created_at.isoformat()}
            for c in comments
        ],
        "activity": [
            {
                "action": log.action,
                "jira_status": log.jira_status,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


def transition_ticket(ticket, user, new_status: str, session=None) -> UserScenarioJiraTicket:
    current = ticket.jira_status or "To Do"
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed and new_status != current:
        raise ValueError(f"Cannot transition from '{current}' to '{new_status}'")

    ticket.jira_status = new_status
    ticket.save(update_fields=["jira_status", "updated_at"])
    _log(session or ticket.last_session, ticket.issue_key, ticket.issue_url, "webhook", new_status, {"by": user.username})
    return ticket


def add_comment(ticket, user, text: str, session=None) -> JiraCommentLog:
    comment_id = f"sim-{ticket.issue_key}-{int(timezone.now().timestamp() * 1000)}"
    return JiraCommentLog.objects.create(
        session=session or ticket.last_session,
        issue_key=ticket.issue_key,
        jira_comment_id=comment_id,
        author=user.get_full_name() or user.username,
        text=text[:8000],
        created_at=timezone.now(),
    )
