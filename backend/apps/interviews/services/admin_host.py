"""Admin live-host mode — founder joins, asks questions, toggles AI on/off.

While AI is paused the engine still scores answers and updates conversation
memory so handing back to AI resumes with full context.
"""

from __future__ import annotations

from django.utils import timezone

from apps.interviews.models import InterviewMessage, InterviewRound


def host_state(round_obj: InterviewRound) -> dict:
    meta = round_obj.metadata if isinstance(round_obj.metadata, dict) else {}
    host = meta.get("admin_host") if isinstance(meta.get("admin_host"), dict) else {}
    joined = bool(host.get("joined"))
    return {
        "joined": joined,
        "ai_enabled": bool(host.get("ai_enabled", True)) if joined else True,
        "display_name": host.get("display_name") or "",
        "admin_email": host.get("admin_email") or "",
        "joined_at": host.get("joined_at"),
    }


def ai_interviewer_active(round_obj: InterviewRound) -> bool:
    st = host_state(round_obj)
    if not st["joined"]:
        return True
    return bool(st["ai_enabled"])


def _save_host(round_obj: InterviewRound, host: dict) -> None:
    meta = dict(round_obj.metadata or {})
    meta["admin_host"] = host
    round_obj.metadata = meta
    round_obj.save(update_fields=["metadata"])


def _display_name_for(admin_user) -> str:
    name = (getattr(admin_user, "first_name", "") or "").strip()
    if name:
        return name
    email = (getattr(admin_user, "email", "") or "").split("@")[0]
    return email.replace(".", " ").replace("_", " ").title() or "our founder"


def admin_join_session(
    round_obj: InterviewRound,
    *,
    admin_user,
    display_name: str | None = None,
) -> dict:
    """Mark admin as live host, pause AI, post welcome lines."""
    st = host_state(round_obj)
    if st["joined"]:
        return {"already_joined": True, "host_state": st, "messages": []}

    label = (display_name or _display_name_for(admin_user)).strip() or "our founder"
    host = {
        "joined": True,
        "ai_enabled": False,
        "display_name": label,
        "admin_email": admin_user.email,
        "admin_user_id": admin_user.id,
        "joined_at": timezone.now().isoformat(),
    }
    _save_host(round_obj, host)

    sys_msg = InterviewMessage.objects.create(
        round=round_obj,
        role="system",
        content=f"{label} joined the session.",
        message_type="system",
        metadata={"admin_host": True, "event": "admin_join"},
    )
    welcome = (
        f"Quick heads-up — {label} from FixitLab is joining us live for a few minutes. "
        "Take a breath; this is still your interview. I'll step back while they ask a question or two, "
        "and we'll pick back up right after."
    )
    intro_msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=welcome,
        message_type="follow_up",
        metadata={"admin_host": True, "event": "admin_welcome", "advanced": False},
    )
    return {
        "host_state": host_state(round_obj),
        "messages": [sys_msg, intro_msg],
    }


def admin_post_question(
    round_obj: InterviewRound,
    *,
    text: str,
    admin_user,
    spoken: bool = False,
) -> InterviewMessage:
    """Admin asks the candidate — AI stays off for this turn."""
    st = host_state(round_obj)
    if not st["joined"]:
        admin_join_session(round_obj, admin_user=admin_user)

    host = dict((round_obj.metadata or {}).get("admin_host") or {})
    host["ai_enabled"] = False
    host["joined"] = True
    _save_host(round_obj, host)

    label = host.get("display_name") or _display_name_for(admin_user)
    content = (text or "").strip()
    if not content:
        raise ValueError("Question text required")

    return InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=content,
        message_type="question",
        metadata={
            "admin_host": True,
            "asked_by": label,
            "admin_user_id": admin_user.id,
            "kind": "admin_question",
            "spoken": bool(spoken),
        },
    )


def admin_set_ai_enabled(
    round_obj: InterviewRound,
    *,
    enabled: bool,
    admin_user,
) -> dict:
    """Toggle AI interviewer. When enabling, hand off and ask the next question."""
    st = host_state(round_obj)
    if not st["joined"]:
        admin_join_session(round_obj, admin_user=admin_user)
        st = host_state(round_obj)

    host = dict((round_obj.metadata or {}).get("admin_host") or {})
    host["ai_enabled"] = bool(enabled)
    host["joined"] = True
    _save_host(round_obj, host)

    messages: list[InterviewMessage] = []
    next_q = None

    if enabled:
        handoff = (
            f"Thanks {host.get('display_name') or 'everyone'} — I'll take it from here and "
            "continue where we left off."
        )
        handoff_msg = InterviewMessage.objects.create(
            round=round_obj,
            role="interviewer",
            content=handoff,
            message_type="follow_up",
            metadata={"admin_host": True, "event": "ai_resume", "advanced": False},
        )
        messages.append(handoff_msg)
        try:
            from apps.interviews.services.engine import ask_next_question

            next_q = ask_next_question(round_obj)
            if next_q:
                messages.append(next_q)
        except Exception:  # noqa: BLE001
            next_q = None

    return {
        "host_state": host_state(round_obj),
        "messages": messages,
        "next_question": next_q,
    }


def host_mode_ack_reply(display_name: str = "") -> str:
    label = display_name or "the team"
    return (
        f"Got it — I've noted that. {label} may follow up, or we'll continue in a moment."
    )


_QUALITY_SCORES = {
    "strong": 86.0,
    "adequate": 68.0,
    "brief": 52.0,
    "weak": 38.0,
    "skipped": 0.0,
}


def _question_for_message(q_msg: InterviewMessage | None) -> object | None:
    if not q_msg:
        return None
    if q_msg.question_id and q_msg.question:
        return q_msg.question

    class _GenQ:
        question_text = q_msg.content or ""
        expected_keywords = []
        technology_id = None

    meta = q_msg.metadata if isinstance(q_msg.metadata, dict) else {}
    pc = meta.get("practical_config") if isinstance(meta.get("practical_config"), dict) else {}
    _GenQ.expected_keywords = list(pc.get("expected_signals") or pc.get("validate_commands") or [])
    return _GenQ()


def _pair_for_candidate(round_obj: InterviewRound, cand_msg: InterviewMessage) -> InterviewMessage | None:
    return (
        round_obj.messages.filter(
            role="interviewer",
            created_at__lt=cand_msg.created_at,
        )
        .exclude(message_type="system")
        .order_by("-created_at")
        .first()
    )


def admin_ai_score_suggestion(
    round_obj: InterviewRound,
    cand_msg: InterviewMessage,
    q_msg: InterviewMessage | None = None,
) -> dict:
    """Same free/heuristic scoring the AI uses — for admin preview or auto-fill."""
    from apps.interviews.services.scoring import score_answer

    q_msg = q_msg or _pair_for_candidate(round_obj, cand_msg)
    qmeta = q_msg.metadata if q_msg and isinstance(q_msg.metadata, dict) else {}
    meta = {
        "round_type": round_obj.round_type,
        "question_text": (q_msg.content if q_msg else ""),
        "question_category": qmeta.get("category") or "",
        "question_kind": qmeta.get("kind") or "",
    }
    if isinstance(cand_msg.metadata, dict) and cand_msg.metadata.get("command_validated"):
        meta["command_validated"] = True
    return score_answer(_question_for_message(q_msg), cand_msg.content or "", meta)


def admin_rate_target(round_obj: InterviewRound) -> dict | None:
    """Latest candidate answer the host can rate (same fields as AI scoring)."""
    st = host_state(round_obj)
    if not st["joined"]:
        return None
    cand = (
        round_obj.messages.filter(role="candidate")
        .order_by("-created_at")
        .first()
    )
    if not cand or not (cand.content or "").strip():
        return None
    cmeta = cand.metadata if isinstance(cand.metadata, dict) else {}
    if cmeta.get("admin_rated"):
        return None
    q_msg = _pair_for_candidate(round_obj, cand)
    suggestion = admin_ai_score_suggestion(round_obj, cand, q_msg)
    return {
        "candidate_message_id": str(cand.id),
        "answer_preview": (cand.content or "")[:280],
        "question_preview": ((q_msg.content if q_msg else "")[:280]),
        "current_score": cand.score,
        "ai_suggestion": suggestion,
    }


def admin_rate_answer(
    round_obj: InterviewRound,
    *,
    admin_user,
    candidate_message_id: str | None = None,
    score: float | None = None,
    quality: str | None = None,
    feedback: str | None = None,
    use_ai: bool = True,
) -> dict:
    """Apply a host rating — AI suggestion by default, admin can override."""
    from apps.interviews.services.conversation_intelligence import update_memory
    from apps.interviews.services.engine import _conversation_meta, _detect_topic_from_meta

    st = host_state(round_obj)
    if not st["joined"]:
        admin_join_session(round_obj, admin_user=admin_user)
        st = host_state(round_obj)

    if candidate_message_id:
        cand = round_obj.messages.filter(id=candidate_message_id, role="candidate").first()
    else:
        cand = round_obj.messages.filter(role="candidate").order_by("-created_at").first()
    if not cand:
        raise ValueError("No candidate answer to rate")

    q_msg = _pair_for_candidate(round_obj, cand)
    ai_result = admin_ai_score_suggestion(round_obj, cand, q_msg) if use_ai else {}

    final_quality = (quality or ai_result.get("quality") or "adequate").strip().lower()
    if final_quality not in _QUALITY_SCORES:
        final_quality = ai_result.get("quality") or "adequate"

    final_score = float(score) if score is not None else float(
        ai_result.get("score") if ai_result.get("score") is not None else _QUALITY_SCORES.get(final_quality, 65)
    )
    if quality and score is None:
        final_score = _QUALITY_SCORES.get(final_quality, final_score)

    final_score = round(max(0.0, min(100.0, final_score)), 1)
    final_feedback = (feedback or "").strip() or ai_result.get("feedback") or "Thanks — noted."
    label = st.get("display_name") or _display_name_for(admin_user)

    score_result = {
        **ai_result,
        "score": final_score,
        "quality": final_quality,
        "feedback": final_feedback,
        "admin_rated": True,
        "admin_rater": label,
        "admin_user_id": admin_user.id,
        "correctness": ai_result.get("correctness", "unknown"),
    }

    cand.score = final_score
    cand.metadata = {**(cand.metadata if isinstance(cand.metadata, dict) else {}), **score_result}
    cand.save(update_fields=["score", "metadata"])

    conv = _conversation_meta(round_obj)
    memory = update_memory(
        conv.get("memory") if isinstance(conv.get("memory"), dict) else {},
        answer_text=cand.content or "",
        score_result=score_result,
        question_topic=_detect_topic_from_meta(q_msg),
    )
    conv["memory"] = memory
    round_obj.metadata = {**(round_obj.metadata or {}), "conversation": conv}
    round_obj.save(update_fields=["metadata"])

    try:
        from apps.interviews.services.interview_ai import generate_interviewer_reply

        reply = generate_interviewer_reply(
            persona_name=label,
            round_type=round_obj.round_type,
            question_text=(q_msg.content if q_msg else ""),
            candidate_answer=cand.content or "",
            score_hint={**score_result, "memory": memory},
            profile_snapshot=round_obj.campaign.profile_snapshot or {},
            conversation_tail=[],
        )
    except Exception:  # noqa: BLE001
        reply = f"{final_feedback} Score: {int(final_score)}/100."

    fb_msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=reply,
        message_type="follow_up",
        metadata={
            "admin_host": True,
            "admin_rating": True,
            "rated_message_id": str(cand.id),
            "score": final_score,
            "quality": final_quality,
            "advanced": False,
        },
    )

    return {
        "candidate_message": cand,
        "feedback_message": fb_msg,
        "score_result": score_result,
        "host_state": host_state(round_obj),
    }
