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

from .client import JiraClient, JiraClientError
from .models import JiraTicketLog, UserScenarioJiraTicket

logger = logging.getLogger(__name__)


def _client() -> Optional[JiraClient]:
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


def _build_issue_body(session) -> str:
    scenario = session.scenario
    site = settings.SITE_URL.rstrip("/")
    lab_url = f"{site}/lab/{session.id}"
    scenario_url = f"{site}/scenarios/{scenario.slug}"

    custom = (getattr(scenario, "jira_issue_template", "") or "").strip()
    if custom:
        return custom.format(
            scenario_title=scenario.title,
            scenario_slug=scenario.slug,
            scenario_description=scenario.description,
            objectives="\n".join(f"- {o}" for o in (scenario.objectives or [])),
            initial_state=scenario.initial_state,
            difficulty=scenario.difficulty,
            technology=scenario.technology.name,
            user=session.user.username,
            user_email=session.user.email,
            session_id=str(session.id),
            lab_url=lab_url,
            scenario_url=scenario_url,
            site_url=site,
        )

    objectives = scenario.objectives or []
    obj_text = "\n".join(f"• {o}" for o in objectives) if objectives else "See scenario page."

    return (
        f"Production incident reported for {scenario.technology.name} environment.\n\n"
        f"ISSUE SUMMARY\n"
        f"{scenario.title}\n\n"
        f"DESCRIPTION\n"
        f"{scenario.description}\n\n"
        f"OBJECTIVES\n"
        f"{obj_text}\n\n"
        f"INITIAL STATE\n"
        f"{scenario.initial_state or 'SSH access to a Linux server with a misconfiguration.'}\n\n"
        f"ASSIGNED TO\n"
        f"{session.user.get_full_name() or session.user.username} ({session.user.email})\n\n"
        f"FIXITLAB LINKS\n"
        f"Start lab: {lab_url}\n"
        f"Scenario details: {scenario_url}\n\n"
        f"Session ID: {session.id}\n"
        f"Difficulty: {scenario.difficulty}\n"
        f"Time limit: {scenario.time_limit // 60} minutes"
    )


def _empty_response():
    return {"jira_issue_key": "", "jira_issue_url": "", "jira_enabled": False}


def sync_lab_started(session) -> dict:
    """Create or reuse Jira ticket and set status to In Progress."""
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
            body = _build_issue_body(session)
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
    """Mark Jira ticket as Done when lab validation passes."""
    client = _client()
    if not client or not session.jira_issue_key:
        return _empty_response()

    try:
        issue_key = session.jira_issue_key
        issue_url = session.jira_issue_url
        minutes = time_taken // 60 if time_taken else 0

        client.add_comment(
            issue_key,
            f"Lab completed successfully.\n"
            f"Score: {score}/100\n"
            f"Time: {minutes} min\n"
            f"Session: {session.id}",
        )
        client.transition_issue(issue_key, settings.JIRA_TRANSITION_DONE)
        status_name = client.get_issue_status(issue_key)
        _log_action(session, issue_key, issue_url, "completed", jira_status=status_name, details={"score": score})

        return {"jira_issue_key": issue_key, "jira_issue_url": issue_url, "jira_enabled": True}
    except JiraClientError as exc:
        logger.error("Jira sync_lab_completed failed: %s", exc)
        return _empty_response()


def sync_lab_stopped(session, reason="Lab stopped") -> dict:
    """Reset Jira ticket to To Do when user stops lab without completing."""
    client = _client()
    if not client or not session.jira_issue_key:
        return _empty_response()

    try:
        issue_key = session.jira_issue_key
        issue_url = session.jira_issue_url

        client.add_comment(issue_key, f"Lab stopped: {reason}. Session: {session.id}")
        client.transition_issue(issue_key, settings.JIRA_TRANSITION_TODO)
        status_name = client.get_issue_status(issue_key)
        _log_action(session, issue_key, issue_url, "cancelled", jira_status=status_name, details={"reason": reason})

        return {"jira_issue_key": issue_key, "jira_issue_url": issue_url, "jira_enabled": True}
    except JiraClientError as exc:
        logger.error("Jira sync_lab_stopped failed: %s", exc)
        return _empty_response()
