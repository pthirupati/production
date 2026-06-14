"""Finalize scenario progress when a Jira ticket is closed after lab validation."""

from __future__ import annotations

import logging

from django.db.models import F
from django.utils import timezone

from apps.question_bank.models import Scenario

from .helpers import is_jira_closed

logger = logging.getLogger(__name__)


def finalize_lab_completion_if_ready(session) -> bool:
    """
    Record scenario completion when validation passed and Jira ticket is closed.
    Idempotent via session.completion_finalized.
    """
    if session is None:
        return False
    if session.completion_finalized:
        return False
    if not session.validation_passed:
        return False

    from apps.jira_integration.models import UserScenarioJiraTicket

    ticket = UserScenarioJiraTicket.objects.filter(
        user=session.user,
        scenario=session.scenario,
        issue_key=session.jira_issue_key or "",
    ).first()
    if ticket and not is_jira_closed(ticket.jira_status or ""):
        return False

    elapsed = 0
    if session.started_at and session.ended_at:
        elapsed = int((session.ended_at - session.started_at).total_seconds())
    elif session.started_at:
        elapsed = int((timezone.now() - session.started_at).total_seconds())

    score = session.score or 100

    from apps.progress.services import record_attempt

    record_attempt(
        user=session.user,
        scenario=session.scenario,
        score=score,
        completed=True,
        time_seconds=elapsed,
        hints_used=session.hints_used,
    )

    Scenario.objects.filter(pk=session.scenario.pk).update(
        completions_count=F("completions_count") + 1
    )

    session.completion_finalized = True
    session.save(update_fields=["completion_finalized"])

    try:
        from apps.notifications.tasks import notify_lab_completed

        notify_lab_completed.delay(
            user_id=session.user_id,
            scenario_title=session.scenario.title,
            score=score,
            time_taken=elapsed,
            hints_used=session.hints_used,
        )
    except Exception as exc:
        logger.warning("Failed to notify lab completion: %s", exc)

    logger.info(
        "Scenario completion finalized for session %s (Jira closed)",
        session.id,
    )
    return True
