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
    from .helpers import in_app_jira_url
    return in_app_jira_url(issue_key)


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


def _clear_ticket_history(ticket: UserScenarioJiraTicket) -> None:
    """Remove prior run comments/activity so relaunch shows a fresh ticket."""
    JiraCommentLog.objects.filter(issue_key=ticket.issue_key).delete()
    JiraTicketLog.objects.filter(issue_key=ticket.issue_key).delete()


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
        _clear_ticket_history(mapping)
        mapping.run_count += 1
        mapping.last_session = session
        mapping.jira_status = "In Progress"
        mapping.description = _build_description(session=session)
        mapping.save()
        add_comment(
            mapping,
            user,
            f"Lab attempt #{mapping.run_count} started.\nSession: {session.id}",
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
    """Add resolution comment only — ticket status must be updated manually by the engineer."""
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
        (
            f"Lab validation passed.\n"
            f"Score: {score}/100\n"
            f"Time: {minutes} min\n"
            f"Session: {session.id}\n\n"
            f"Please update the ticket status and close it when the incident is resolved."
        ),
        session=session,
    )
    _log(session, ticket.issue_key, ticket.issue_url, "validated", ticket.jira_status, {"score": score})
    return {"jira_issue_key": ticket.issue_key, "jira_issue_url": ticket.issue_url, "jira_enabled": True}


def sync_lab_stopped(session, reason="Lab stopped") -> dict:
    """Lab stopped — log only; Jira status stays under engineer control."""
    if not session.jira_issue_key:
        return {}
    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user, issue_key=session.jira_issue_key
    ).first()
    if not ticket:
        return {}
    add_comment(
        ticket,
        session.user,
        f"Lab session ended: {reason}. Session: {session.id}.",
        session=session,
    )
    _log(session, ticket.issue_key, ticket.issue_url, "lab_stopped", ticket.jira_status, {"reason": reason})
    return {"jira_issue_key": ticket.issue_key, "jira_issue_url": ticket.issue_url, "jira_enabled": True}


def sync_lab_expired(session) -> dict:
    """Auto-close Jira ticket when lab session times out."""
    if not session.jira_issue_key:
        return {}
    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user, issue_key=session.jira_issue_key
    ).first()
    if not ticket:
        return {}
    minutes = session.duration_limit // 60 if session.duration_limit else 0
    add_comment(
        ticket,
        session.user,
        (
            f"Lab session auto-expired after {minutes} minutes.\n"
            f"Session: {session.id}\n"
            f"Closing ticket due to lab timeout."
        ),
        session=session,
    )
    close_status = "Closed" if "Closed" in ALLOWED_TRANSITIONS.get(ticket.jira_status or "In Progress", set()) else "Done"
    try:
        transition_ticket(ticket, session.user, close_status, session=session)
    except ValueError:
        ticket.jira_status = "Closed"
        ticket.save(update_fields=["jira_status", "updated_at"])
        from .completion import finalize_lab_completion_if_ready
        finalize_lab_completion_if_ready(session)
    _log(session, ticket.issue_key, ticket.issue_url, "expired", ticket.jira_status, {})
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
    """Return ticket if owned by user, or any ticket when viewer is platform staff."""
    qs = UserScenarioJiraTicket.objects.filter(
        issue_key=issue_key,
    ).select_related("scenario", "last_session", "user")
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return qs.first()
    return qs.filter(user=user).first()


def ticket_detail_payload(ticket: UserScenarioJiraTicket) -> dict:
    session_filter = {"session": ticket.last_session} if ticket.last_session_id else {}
    comments = (
        JiraCommentLog.objects.filter(issue_key=ticket.issue_key, **session_filter)
        .order_by("-created_at")[:20]
    )
    logs = (
        JiraTicketLog.objects.filter(issue_key=ticket.issue_key, **session_filter)
        .order_by("-created_at")[:15]
    )
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
        "created_at": ticket.created_at.isoformat(),
        "allowed_transitions": sorted(ALLOWED_TRANSITIONS.get(ticket.jira_status or "To Do", set())),
        "scenario": {
            "id": ticket.scenario_id,
            "slug": ticket.scenario.slug,
            "title": ticket.scenario.title,
        },
        "owner": {
            "id": ticket.user_id,
            "username": ticket.user.username,
            "email": ticket.user.email,
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


CUSTOMER_AUTHOR = "Customer (Reporter)"


def _customer_persona_name(scenario) -> str:
    return getattr(scenario, "subtitle", None) or scenario.title.split("—")[0].strip() or "End User"


def generate_customer_bot_reply(ticket, user_text: str) -> str:
    """Simulated end-user reply — acts as the customer who reported the incident."""
    scenario = ticket.scenario
    text = (user_text or "").lower()
    created = ticket.created_at.strftime("%B %d, %Y at %H:%M UTC")
    impact = (scenario.description or "")[:400]
    error_detail = (scenario.initial_state or scenario.description or "The service is not working as expected.")[:500]
    persona = _customer_persona_name(scenario)

    if any(w in text for w in ("when", "created", "raised", "reported", "opened")):
        return (
            f"Hi, this was reported on {created}. "
            f"I noticed the problem during our morning checks and raised it immediately.\n\n— {persona}"
        )
    if any(w in text for w in ("impact", "affect", "business", "users", "severity")):
        return (
            f"The impact is significant — {impact}\n\n"
            f"Our team is blocked until this is resolved. Please treat this as urgent.\n\n— {persona}"
        )
    if any(w in text for w in ("error", "symptom", "issue", "problem", "detail", "describe", "log")):
        return (
            f"Here is what we are seeing:\n\n{error_detail}\n\n"
            f"Let me know if you need more logs or screenshots.\n\n— {persona}"
        )
    if any(w in text for w in ("hold", "waiting", "customer", "update")):
        return (
            f"We are waiting on your update. The issue is still affecting us. "
            f"Can you share an ETA?\n\n— {persona}"
        )
    return (
        f"Thanks for looking into this. To recap: {error_detail[:300]}\n\n"
        f"Please keep me posted on progress.\n\n— {persona}"
    )


def transition_ticket(ticket, user, new_status: str, session=None) -> UserScenarioJiraTicket:
    current = ticket.jira_status or "To Do"
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if new_status not in allowed and new_status != current:
        raise ValueError(f"Cannot transition from '{current}' to '{new_status}'")

    ticket.jira_status = new_status
    ticket.save(update_fields=["jira_status", "updated_at"])
    _log(session or ticket.last_session, ticket.issue_key, ticket.issue_url, "webhook", new_status, {"by": user.username})

    if is_jira_closed(new_status):
        from .completion import finalize_lab_completion_if_ready
        target_session = session or ticket.last_session
        if target_session:
            finalize_lab_completion_if_ready(target_session)

    return ticket


def add_comment(ticket, user, text: str, session=None, author: str | None = None) -> JiraCommentLog:
    comment_id = f"sim-{ticket.issue_key}-{int(timezone.now().timestamp() * 1000)}"
    if author:
        author_name = author
    elif user is None:
        author_name = CUSTOMER_AUTHOR
    else:
        author_name = user.get_full_name() or user.username
    return JiraCommentLog.objects.create(
        session=session or ticket.last_session,
        issue_key=ticket.issue_key,
        jira_comment_id=comment_id,
        author=author_name,
        text=text[:8000],
        created_at=timezone.now(),
    )


def add_customer_reply(ticket, user_text: str, session=None) -> JiraCommentLog:
    reply = generate_customer_bot_reply(ticket, user_text)
    return add_comment(ticket, None, reply, session=session, author=CUSTOMER_AUTHOR)
