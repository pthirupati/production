"""Single source of truth for marking a LabSession solved.

Both the terminal/simulation validator (ValidateLabView) and the coding-IDE
validator (CodeValidateView) funnel through finalize_validated_session() so
there is exactly ONE completion path. There is deliberately no "lighter" way to
mark a session complete — every caller pays the same scoring, Jira, webhook,
progress, and notification side-effects.
"""

from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def compute_score(session) -> int:
    """Score == base 100 + time bonus − hint penalty, floored at 10.

    Identical formula to the original ValidateLabView so coding scenarios score
    consistently with every other lab type.
    """
    duration = session.duration_limit or 1
    time_bonus = max(0, int(session.time_remaining * 100 / duration))
    hint_penalty = session.hints_used * 10
    return max(10, 100 + time_bonus - hint_penalty)


def finalize_validated_session(session, request_user, provisioner):
    """Mark `session` validated/completed and run all completion side-effects.

    Returns a dict payload (score, message, jira flags, solution) for the API
    response. Callers must have already confirmed the solution genuinely passed
    — this function trusts that and performs the irreversible completion.
    """
    from apps.jira_integration.sync import sync_lab_completed
    from apps.labs.provisioner import terminate_lab_session

    elapsed = (timezone.now() - session.started_at).total_seconds()
    score = compute_score(session)

    session.validation_passed = True
    session.score = score
    session.status = "COMPLETED"
    session.ended_at = timezone.now()
    session.save(update_fields=["validation_passed", "score", "status", "ended_at"])

    sync_lab_completed(session, score=score, time_taken=int(elapsed))

    try:
        from apps.jira_integration.simulated import schedule_jira_reset_after_lab_close
        schedule_jira_reset_after_lab_close(session)
    except Exception as e:
        logger.warning(f"Jira reset schedule failed: {e}")

    try:
        from apps.accounts.models import OrganizationMember
        from apps.accounts.webhooks import fire_org_webhook
        membership = (
            OrganizationMember.objects.filter(user=request_user)
            .select_related("organization").first()
        )
        if membership:
            fire_org_webhook(membership.organization, "lab.completed", {
                "user": request_user.username,
                "scenario": session.scenario.slug,
                "score": score,
            })
    except Exception:
        pass

    from apps.jira_integration.helpers import is_jira_closed
    from apps.jira_integration.models import UserScenarioJiraTicket

    ticket = UserScenarioJiraTicket.objects.filter(
        user=request_user, issue_key=session.jira_issue_key
    ).first()
    jira_closed = ticket and is_jira_closed(ticket.jira_status or "")

    if jira_closed:
        from apps.jira_integration.completion import finalize_lab_completion_if_ready
        finalize_lab_completion_if_ready(session)
        completion_message = "Congratulations! Challenge solved and Jira ticket closed!"
    else:
        completion_message = (
            "Validation passed! Update the Jira ticket status and close it "
            "to mark this scenario complete."
        )

    if provisioner is not None:
        try:
            terminate_lab_session(provisioner, session)
        except Exception as e:
            logger.warning(f"Lab termination after completion failed: {e}")

    try:
        from apps.progress.learning_path import sync_learning_path_on_completion
        sync_learning_path_on_completion(request_user, session.scenario)
    except Exception as e:
        logger.warning(f"Learning-path sync failed: {e}")

    try:
        from apps.notifications.tasks import send_lab_completion_notification
        send_lab_completion_notification.delay(
            user_id=request_user.id,
            scenario_id=session.scenario_id,
            score=score,
            time_seconds=int(elapsed),
        )
    except Exception:
        pass  # never fail completion due to email errors

    return {
        "passed": True,
        "score": score,
        "time_taken": int(elapsed),
        "message": completion_message,
        "jira_pending_close": not jira_closed,
        "scenario_completed": jira_closed or session.completion_finalized,
        "solution": session.scenario.solution_explanation or None,
    }
