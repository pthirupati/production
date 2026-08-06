"""Finalize scenario progress when a Jira ticket is closed after lab validation."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.question_bank.models import Scenario

from .helpers import is_jira_closed

logger = logging.getLogger(__name__)


def finalize_lab_completion_if_ready(session) -> bool:
    """
    Record scenario completion when validation passed and Jira ticket is closed.
    Idempotent AND concurrency-safe: the completion_finalized guard is re-checked
    under a row lock (SELECT ... FOR UPDATE), so duplicate finalizes — duplicate
    Jira webhooks, a double-clicked "Check", or a WS+HTTP race — can never
    double-count XP, attempts, or completions (audit P0-3).
    """
    if session is None:
        return False
    # Cheap pre-check to avoid taking a lock in the common already-done case.
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

    from apps.labs.models import LabSession
    from apps.progress.services import record_attempt, award_xp_for_completion

    with transaction.atomic():
        # Re-fetch under a row lock and re-check the guard. If a concurrent
        # request already finalized this session, the WHERE no longer matches
        # (completion_finalized=True) and .first() returns None → we bail out
        # without awarding anything a second time.
        locked = (
            LabSession.objects.select_for_update()
            .filter(pk=session.pk, completion_finalized=False)
            .first()
        )
        if locked is None:
            return False

        # Was this scenario ALREADY completed before this attempt? Must be read
        # before record_attempt(), which sets completed_at on first success.
        from apps.progress.models import UserScenarioProgress

        already_completed = UserScenarioProgress.objects.filter(
            user=session.user, scenario=session.scenario, completed=True,
        ).exists()

        record_attempt(
            user=session.user,
            scenario=session.scenario,
            score=score,
            completed=True,
            time_seconds=elapsed,
            hints_used=session.hints_used,
        )

        # Grant XP only on the FIRST completion of a given scenario.
        #
        # The completion_finalized lock above makes this idempotent per SESSION —
        # it correctly defeats duplicate Jira webhooks and double-clicked Check.
        # But restarting a lab creates a NEW session with completion_finalized
        # False, so re-solving the same scenario re-awarded the full 50 + score +
        # difficulty bonus (150-250 XP) every time. compute_score even rewards
        # speed, so the fastest replay paid the most: grinding one easy scenario
        # was the cheapest route up the XP and level ladder.
        #
        # Replaying for practice is still fine and still updates best_score,
        # best_time and achievements via record_attempt — it just does not mint
        # new XP. This mirrors the weekly leaderboard, which now sums per-scenario
        # bests rather than every session.
        if already_completed:
            logger.info(
                "XP not re-awarded: user=%s already completed scenario=%s",
                session.user_id, session.scenario.slug,
            )
        else:
            award_xp_for_completion(
                session.user, score=score,
                difficulty=getattr(session.scenario, "difficulty", None),
            )

        Scenario.objects.filter(pk=session.scenario.pk).update(
            completions_count=F("completions_count") + 1
        )

        locked.completion_finalized = True
        locked.save(update_fields=["completion_finalized"])
        session.completion_finalized = True  # keep caller's instance in sync

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
