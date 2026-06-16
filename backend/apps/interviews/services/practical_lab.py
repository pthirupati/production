"""Start FixitLab lab sessions for interview practical segments."""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404

from apps.interviews.models import InterviewRound
from apps.labs.models import LabSession
from apps.labs.sessions import start_lab_session
from apps.question_bank.models import Scenario

logger = logging.getLogger(__name__)


def _practical_scenario_slug(round_obj: InterviewRound) -> str | None:
    msg = (
        round_obj.messages.filter(message_type="practical", question__isnull=False)
        .select_related("question")
        .order_by("-created_at")
        .first()
    )
    if not msg and round_obj.messages.filter(question__category="practical").exists():
        msg = (
            round_obj.messages.filter(question__category="practical", question__isnull=False)
            .select_related("question")
            .order_by("-created_at")
            .first()
        )
    if not msg or not msg.question:
        return None
    return (msg.question.practical_config or {}).get("scenario_slug")


def start_practical_lab(user, round_obj: InterviewRound) -> dict:
    """Provision lab for current practical question; idempotent per round."""
    if round_obj.practical_lab_session_id:
        session = LabSession.objects.filter(id=round_obj.practical_lab_session_id).first()
        if session:
            return _session_payload(session)

    slug = _practical_scenario_slug(round_obj)
    if not slug:
        return {"error": "No practical scenario configured for this round", "code": "NO_PRACTICAL"}

    scenario = Scenario.objects.filter(slug=slug, is_active=True).first()
    if not scenario:
        return {"error": f"Scenario '{slug}' not found on this server", "code": "SCENARIO_MISSING"}

    try:
        session = start_lab_session(user, scenario)
        round_obj.practical_lab_session_id = session.id
        round_obj.save(update_fields=["practical_lab_session_id"])
        return _session_payload(session)
    except Exception as exc:
        logger.exception("Interview practical lab failed round=%s", round_obj.id)
        return {"error": str(exc)[:200], "code": "PROVISION_FAILED"}


def _session_payload(session: LabSession) -> dict:
    return {
        "session_id": str(session.id),
        "status": session.status,
        "scenario_slug": session.scenario.slug if session.scenario_id else "",
        "scenario_title": session.scenario.title if session.scenario_id else "",
        "lab_url": f"/lab/{session.id}",
    }
