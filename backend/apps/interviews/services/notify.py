"""In-app notifications for Interview Studio events."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_interview(user_id: int, title: str, message: str, metadata: dict | None = None) -> None:
    try:
        from apps.notifications.tasks import create_in_app_notification

        create_in_app_notification.delay(
            user_id=user_id,
            notification_type="system",
            title=title,
            message=message,
            metadata={"category": "interview", **(metadata or {})},
        )
    except Exception as exc:
        logger.warning("Interview notification failed: %s", exc)


def notify_round_scheduled(round_obj) -> None:
    user = round_obj.campaign.user
    when = round_obj.scheduled_at.strftime("%b %d, %Y %H:%M UTC") if round_obj.scheduled_at else "soon"
    notify_interview(
        user.id,
        f"Interview scheduled: {round_obj.title}",
        f"Round {round_obj.round_number} with {round_obj.persona_name} — {when}",
        {"round_id": str(round_obj.id), "event": "scheduled"},
    )


def notify_round_results(round_obj, passed: bool, score: float) -> None:
    user = round_obj.campaign.user
    notify_interview(
        user.id,
        f"Round {'passed' if passed else 'complete'}: {round_obj.title}",
        f"Score {score:.0f}/100 — {'Schedule your next round within 48h.' if passed else 'Review feedback and retry.'}",
        {"round_id": str(round_obj.id), "event": "results", "passed": passed, "score": score},
    )


def notify_certificate_issued(campaign, cert) -> None:
    user = campaign.user
    notify_interview(
        user.id,
        "Interview certificate issued",
        f"{cert.certificate_id} — share on LinkedIn or verify publicly.",
        {"certificate_id": cert.certificate_id, "event": "certificate"},
    )
