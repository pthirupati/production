"""
Sync FixitLab lab sessions with Jira Cloud tickets.

When a user starts a lab:
  - Create or reuse a Jira ticket for user+scenario
  - Transition to "In Progress"
  - On restart of same scenario: reset ticket (To Do → In Progress), increment run_count

When lab completes/stops: transition accordingly and log audit trail.
"""

import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone

from apps.question_bank.scenario_copy import incident_summary, public_objectives

from .client import JiraClient, JiraClientError
from .models import JiraTicketLog, UserScenarioJiraTicket

logger = logging.getLogger(__name__)


def _client() -> Optional[JiraClient]:
    from .simulated import use_simulated_jira
    if use_simulated_jira():
        return None
    client = JiraClient()
    return client if client.enabled else None


def _log_action(session, issue_key, issue_url, action, jira_status="", details=None):
    JiraTicketLog.objects.create(
        session=session,
        issue_key=issue_key,
        issue_url=issue_url,
        action=action,
        jira_status=jira_status,
        details=details or {},
    )


def _build_issue_body(session=None, user=None, scenario=None) -> str:
    if session is not None:
        scenario = session.scenario
        user = session.user
    site = settings.SITE_URL.rstrip("/")
    scenario_url = f"{site}/scenarios/{scenario.slug}"
    lab_url = f"{site}/lab/{session.id}" if session else scenario_url

    custom = (getattr(scenario, "jira_issue_template", "") or "").strip()
    if custom:
        return custom.format(
            scenario_title=scenario.title,
            scenario_slug=scenario.slug,
            scenario_description=scenario.description,
            objectives="\n".join(f"- {o}" for o in public_objectives(scenario.objectives or [])),
            initial_state=scenario.initial_state,
            difficulty=scenario.difficulty,
            technology=scenario.technology.name,
            user=user.username,
            user_email=user.email,
            session_id=str(session.id) if session else "",
            lab_url=lab_url,
            scenario_url=scenario_url,
            site_url=site,
        )

    outcomes = public_objectives(scenario.objectives or [])
    outcome_text = (
        "\n".join(f"• {o}" for o in outcomes)
        if outcomes
        else "• Restore normal service for the affected system."
    )
    incident = incident_summary(scenario)

    return (
        f"h2. Production Incident — {scenario.title}\n\n"
        f"*Technology:* {scenario.technology.name}\n"
        f"*Difficulty:* {scenario.difficulty}\n"
        f"*Reporter:* {user.get_full_name() or user.username} ({user.email})\n"
        f"*Time limit:* {scenario.time_limit // 60} minutes\n\n"
        f"h3. Summary\n"
        f"{scenario.subtitle or scenario.title}\n\n"
        f"h3. Incident description\n"
        f"{incident}\n\n"
        f"h3. Expected outcome\n"
        f"{outcome_text}\n\n"
        f"h3. FixitLab Links\n"
        f"* [Open lab|{lab_url}]\n"
        f"* [Scenario details|{scenario_url}]\n\n"
        f"*Session ID:* {session.id if session else 'pending'}\n"
        f"*Site:* {site}"
    )


def _ticket_response(mapping, enabled=True, **extra):
    return {
        "jira_issue_key": mapping.issue_key,
        "jira_issue_url": mapping.issue_url,
        "jira_enabled": enabled,
        "jira_status": mapping.jira_status,
        "jira_run_count": mapping.run_count,
        **extra,
    }


def ensure_scenario_ticket(user, scenario) -> dict:
    """
    Get or create a Jira ticket when user opens a scenario (no active lab required).
    Does not transition to In Progress — that happens on lab start.
    """
    from .simulated import ensure_scenario_ticket as sim_ensure
    from .simulated import use_simulated_jira

    if use_simulated_jira():
        return sim_ensure(user, scenario)

    client = _client()
    if not client:
        return _empty_response()

    try:
        mapping, created = UserScenarioJiraTicket.objects.get_or_create(
            user=user,
            scenario=scenario,
            defaults={"issue_key": "", "issue_url": ""},
        )

        needs_create = created or not mapping.issue_key
        if needs_create:
            summary = f"[FixitLab] {scenario.title} — {user.username}"
            priority = getattr(scenario, "jira_priority", "") or "Medium"
            body = _build_issue_body(user=user, scenario=scenario)
            result = client.create_issue(
                summary=summary,
                description=body,
                priority=priority,
                labels=["fixitlab", scenario.slug, scenario.technology.name.lower()],
            )
            issue_key = result["key"]
            issue_url = client.issue_url(issue_key)
            mapping.issue_key = issue_key
            mapping.issue_url = issue_url
            mapping.jira_status = client.get_issue_status(issue_key)
            if mapping.run_count < 1:
                mapping.run_count = 1
            mapping.save()

        return _ticket_response(mapping, jira_created=needs_create)

    except JiraClientError as exc:
        logger.error("Jira ensure_scenario_ticket failed user=%s scenario=%s: %s", user.id, scenario.id, exc)
        return {**_empty_response(), "jira_error": str(exc)[:200]}


def mask_jira_url_for_user(info: dict, user) -> dict:
    """All users get in-app simulation URLs (no Atlassian login required)."""
    from .helpers import resolve_jira_issue_url

    if not user:
        return info
    masked = dict(info)
    key = info.get("jira_issue_key") or masked.get("jira_issue_key")
    if key:
        masked["jira_issue_url"] = resolve_jira_issue_url(key, info.get("jira_issue_url", ""))
        masked["simulated"] = True
    return masked


def _empty_response():
    return {"jira_issue_key": "", "jira_issue_url": "", "jira_enabled": False}


def sync_lab_started(session) -> dict:
    """Create or reuse Jira ticket and set status to In Progress."""
    from .simulated import sync_lab_started as sim_started
    from .simulated import use_simulated_jira

    if use_simulated_jira():
        return sim_started(session)

    client = _client()
    if not client:
        return _empty_response()

    scenario = session.scenario
    user = session.user
    is_reset = False

    try:
        mapping, created = UserScenarioJiraTicket.objects.get_or_create(
            user=user,
            scenario=scenario,
            defaults={"issue_key": "", "issue_url": ""},
        )

        if created or not mapping.issue_key:
            summary = f"[FixitLab] {scenario.title} — {user.username}"
            priority = getattr(scenario, "jira_priority", "") or "Medium"
            body = _build_issue_body(session=session)
            result = client.create_issue(
                summary=summary,
                description=body,
                priority=priority,
                labels=["fixitlab", scenario.slug, scenario.technology.name.lower()],
            )
            issue_key = result["key"]
            issue_url = client.issue_url(issue_key)
            mapping.issue_key = issue_key
            mapping.issue_url = issue_url
            mapping.run_count = 1
            mapping.last_session = session
            mapping.save()
            _log_action(session, issue_key, issue_url, "created", details={"run": 1})
        else:
            is_reset = True
            mapping.run_count += 1
            mapping.last_session = session
            mapping.save(update_fields=["run_count", "last_session", "updated_at"])

            issue_key = mapping.issue_key
            issue_url = mapping.issue_url

            client.add_comment(
                issue_key,
                f"Lab restarted (run #{mapping.run_count}). "
                f"Session: {session.id}. Open lab: {settings.SITE_URL.rstrip('/')}/lab/{session.id}",
            )
            client.transition_issue(issue_key, settings.JIRA_TRANSITION_TODO)
            _log_action(
                session, issue_key, issue_url, "reset",
                details={"run_count": mapping.run_count},
            )

        client.transition_issue(issue_key, settings.JIRA_TRANSITION_IN_PROGRESS)
        status_name = client.get_issue_status(issue_key)

        mapping.jira_status = status_name
        mapping.save(update_fields=["jira_status", "updated_at"])

        session.jira_issue_key = issue_key
        session.jira_issue_url = issue_url
        session.save(update_fields=["jira_issue_key", "jira_issue_url"])

        _log_action(
            session, issue_key, issue_url, "in_progress", jira_status=status_name,
            details={"reset": is_reset, "run_count": mapping.run_count},
        )

        return {
            "jira_issue_key": issue_key,
            "jira_issue_url": issue_url,
            "jira_enabled": True,
            "jira_run_count": mapping.run_count,
            "jira_reset": is_reset,
        }

    except JiraClientError as exc:
        logger.error("Jira sync_lab_started failed for session %s: %s", session.id, exc)
        return _empty_response()


def sync_lab_in_progress(session) -> dict:
    """Ensure ticket is In Progress (idempotent)."""
    from .simulated import sync_lab_in_progress as sim_progress
    from .simulated import use_simulated_jira

    if use_simulated_jira():
        return sim_progress(session)

    client = _client()
    if not client or not session.jira_issue_key:
        return _empty_response()

    try:
        client.transition_issue(session.jira_issue_key, settings.JIRA_TRANSITION_IN_PROGRESS)
        status_name = client.get_issue_status(session.jira_issue_key)
        _log_action(session, session.jira_issue_key, session.jira_issue_url, "in_progress", jira_status=status_name)
        return {
            "jira_issue_key": session.jira_issue_key,
            "jira_issue_url": session.jira_issue_url,
            "jira_enabled": True,
        }
    except JiraClientError as exc:
        logger.error("Jira sync_lab_in_progress failed: %s", exc)
        return _empty_response()


def sync_lab_completed(session, score=0, time_taken=0) -> dict:
    """Add resolution comment when lab validation passes — no auto status change."""
    from .simulated import sync_lab_completed as sim_completed
    from .simulated import use_simulated_jira

    if use_simulated_jira():
        return sim_completed(session, score=score, time_taken=time_taken)

    client = _client()
    if not client or not session.jira_issue_key:
        return _empty_response()

    try:
        issue_key = session.jira_issue_key
        issue_url = session.jira_issue_url
        minutes = time_taken // 60 if time_taken else 0

        client.add_comment(
            issue_key,
            f"Lab validation passed.\n"
            f"Score: {score}/100\n"
            f"Time: {minutes} min\n"
            f"Session: {session.id}\n\n"
            f"Please update the ticket status and close it when resolved.",
        )
        status_name = client.get_issue_status(issue_key)
        _log_action(session, issue_key, issue_url, "validated", jira_status=status_name, details={"score": score})

        return {"jira_issue_key": issue_key, "jira_issue_url": issue_url, "jira_enabled": True}
    except JiraClientError as exc:
        logger.error("Jira sync_lab_completed failed: %s", exc)
        return _empty_response()


def sync_lab_expired(session) -> dict:
    """Auto-close Jira ticket when lab session expires."""
    from .simulated import sync_lab_expired as sim_expired
    from .simulated import use_simulated_jira

    if use_simulated_jira():
        return sim_expired(session)

    client = _client()
    if not client or not session.jira_issue_key:
        return _empty_response()

    try:
        issue_key = session.jira_issue_key
        issue_url = session.jira_issue_url
        minutes = session.duration_limit // 60 if session.duration_limit else 0
        client.add_comment(
            issue_key,
            f"Lab session auto-expired after {minutes} minutes.\n"
            f"Session: {session.id}\nClosing ticket due to lab timeout.",
        )
        client.transition_issue(issue_key, settings.JIRA_TRANSITION_DONE)
        status_name = client.get_issue_status(issue_key)
        _log_action(session, issue_key, issue_url, "expired", jira_status=status_name)
        from .completion import finalize_lab_completion_if_ready
        finalize_lab_completion_if_ready(session)
        return {"jira_issue_key": issue_key, "jira_issue_url": issue_url, "jira_enabled": True}
    except JiraClientError as exc:
        logger.error("Jira sync_lab_expired failed: %s", exc)
        return _empty_response()


def sync_lab_stopped(session, reason="Lab stopped") -> dict:
    """Log lab stop — Jira status remains under engineer control."""
    from .simulated import sync_lab_stopped as sim_stopped
    from .simulated import use_simulated_jira

    if use_simulated_jira():
        return sim_stopped(session, reason=reason)

    client = _client()
    if not client or not session.jira_issue_key:
        return _empty_response()

    try:
        issue_key = session.jira_issue_key
        issue_url = session.jira_issue_url

        client.add_comment(issue_key, f"Lab session ended: {reason}. Session: {session.id}.")
        status_name = client.get_issue_status(issue_key)
        _log_action(session, issue_key, issue_url, "lab_stopped", jira_status=status_name, details={"reason": reason})

        return {"jira_issue_key": issue_key, "jira_issue_url": issue_url, "jira_enabled": True}
    except JiraClientError as exc:
        logger.error("Jira sync_lab_stopped failed: %s", exc)
        return _empty_response()
