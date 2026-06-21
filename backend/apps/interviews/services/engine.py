"""Core interview session orchestration."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.interviews.models import (
    InterviewCampaign,
    InterviewMessage,
    InterviewReport,
    InterviewRound,
)
from apps.interviews.services.campaign_builder import unlock_next_round
from apps.interviews.services.certificate import issue_certificate
from apps.interviews.services.interview_ai import generate_interviewer_reply
from apps.interviews.services.question_generator import (
    generate_question,
    plan_round_topics,
    starting_difficulty,
)
from apps.interviews.services.question_selector import round_category_mix, select_next_question
from apps.interviews.services.scoring import aggregate_round_scores, build_strengths_and_improvements, score_answer


INTRO_TEMPLATES = {
    "technical": (
        "Hi, I'm {persona}. Thanks for joining — I've got your resume pulled up. "
        "We'll spend about {minutes} minutes on technical depth, troubleshooting, and maybe a hands-on scenario. "
        "Camera and mic stay on please; if either drops for five minutes we'll need to end the session. Ready when you are — "
        "tell me briefly what you're working on at {company} and what drew you to this {role} track."
    ),
    "manager": (
        "Hey, {persona} here — engineering manager round. We'll talk incidents, SLAs, ITIL-style process, "
        "and how you work with teams. About {minutes} minutes. How do you usually handle a SEV-1 when you're on call?"
    ),
    "hr": (
        "Hi! I'm {persona} from people ops. Casual chat — background, motivation, logistics. "
        "Roughly {minutes} minutes. How's your day going so far?"
    ),
    "deep_dive": (
        "I'm {persona}. This round goes deeper on gaps or strengths from round one — architecture, trade-offs, war stories. "
        "{minutes} minutes. What area do you feel strongest in technically right now?"
    ),
    "leadership": (
        "I'm {persona}. Leadership and stakeholder round — influence without authority, mentoring, delivery under pressure. "
        "Tell me about a time you had to push back on a deadline."
    ),
}


def _profile_for_round(round_obj: InterviewRound) -> dict:
    return round_obj.campaign.profile_snapshot or {}


def start_round(round_obj: InterviewRound) -> dict:
    # Re-fetch with lock to prevent concurrent starts.
    # "schedulable" is the initial status of round 1 (and of unlocked later
    # rounds); the start endpoint allows starting directly from it, so it must
    # be a valid startable status here too — otherwise we return a payload with
    # no "message" key and the view 500s with KeyError.
    from django.db import transaction as db_transaction
    with db_transaction.atomic():
        locked = InterviewRound.objects.select_for_update().get(pk=round_obj.pk)
        if locked.status == "in_progress":
            # Already started — return the existing intro so the caller can resume
            # instead of 500ing. Idempotent restart.
            round_obj.status = locked.status
            round_obj.started_at = locked.started_at
            round_obj.ends_at = locked.ends_at
            existing_intro = (
                locked.messages.filter(role="interviewer", message_type="introduction")
                .order_by("created_at")
                .first()
            )
            if existing_intro:
                return {
                    "message": existing_intro,
                    "ends_at": locked.ends_at.isoformat() if locked.ends_at else None,
                    "already_started": True,
                }
            # In progress but somehow no intro — fall through to create one below
            # without resetting the running timer.
        elif locked.status not in ("scheduled", "ready", "schedulable"):
            # Ended/cancelled/locked — not startable. Signal to the caller.
            round_obj.status = locked.status
            return {"not_startable": True, "status": locked.status}
        now = timezone.now()
        was_in_progress = locked.status == "in_progress"
        locked.status = "in_progress"
        if not was_in_progress:
            locked.started_at = now
            locked.ends_at = now + timedelta(minutes=locked.duration_minutes + locked.extension_minutes)
        locked.save(update_fields=["status", "started_at", "ends_at"])
    round_obj.status = "in_progress"
    round_obj.started_at = locked.started_at
    round_obj.ends_at = locked.ends_at

    campaign = round_obj.campaign
    if getattr(campaign, "is_sample", False):
        from apps.interviews.services.sample_interview import mark_sample_used
        mark_sample_used(campaign.user)

    snap = _profile_for_round(round_obj)

    # Resume/JD analysis drives this round: seed a topic agenda from the resume +
    # chosen tech, and set a seniority/years-aware starting difficulty. Stored on
    # the round so every generated question this round pulls from the same plan.
    # Guarded so a malformed snapshot can never block the start.
    try:
        meta = dict(round_obj.metadata or {})
        if "topic_agenda" not in meta:
            meta["topic_agenda"] = plan_round_topics(round_obj.round_type, snap)
        round_obj.metadata = meta
        seed_difficulty = starting_difficulty(snap)
        # Deep-dive / leadership push one notch harder than the baseline level.
        if round_obj.round_type in ("deep_dive", "leadership"):
            seed_difficulty = min(5, seed_difficulty + 1)
        round_obj.difficulty_level = seed_difficulty
        round_obj.save(update_fields=["metadata", "difficulty_level"])
    except Exception:  # noqa: BLE001 - planning is best-effort, never fatal
        pass
    # Resolve these defensively: snapshot values can be explicitly None (not just
    # missing), and "None + ' role'" would raise TypeError and 500 the start.
    level = snap.get("experience_level") or "mid"
    target_role = snap.get("target_role") or ""
    company = snap.get("current_company") or "your current company"
    if getattr(campaign, "is_sample", False):
        intro = (
            f"Hi, I'm {round_obj.persona_name}. Welcome to your free {round_obj.duration_minutes}-minute sample interview. "
            "We'll cover a few quick technical questions so you can experience voice Q&A, scoring, and feedback. "
            "Camera and mic must stay on. This is a preview — subscribe for full 3–5 round cycles and certificates. "
            f"What are you currently working on as a {target_role or level}-level engineer?"
        )
    else:
        tpl = INTRO_TEMPLATES.get(round_obj.round_type, INTRO_TEMPLATES["technical"])
        intro = tpl.format(
            persona=round_obj.persona_name or "your interviewer",
            minutes=round_obj.duration_minutes,
            company=company,
            role=target_role or f"{level} role",
        )
    msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=intro,
        message_type="introduction",
    )
    return {"message": msg, "ends_at": round_obj.ends_at.isoformat()}


def _last_candidate_answer(round_obj: InterviewRound):
    """Most recent candidate message + its stored quality (for probing)."""
    cand = (
        round_obj.messages.filter(role="candidate")
        .order_by("-created_at")
        .first()
    )
    if not cand:
        return "", ""
    quality = (cand.metadata or {}).get("quality", "") if isinstance(cand.metadata, dict) else ""
    return cand.content or "", quality


def _asked_question_texts(round_obj: InterviewRound) -> list[str]:
    """Texts the generated question must NOT duplicate. Covers every interviewer
    question/practical turn already asked this round (both generated and banked),
    plus the recent conversational follow-up replies — so the next *question*
    never simply echoes the acknowledgement the engine just spoke."""
    questions = list(
        round_obj.messages.filter(
            role="interviewer", message_type__in=("question", "practical")
        ).values_list("content", flat=True)
    )
    recent_replies = list(
        round_obj.messages.filter(role="interviewer", message_type="follow_up")
        .order_by("-created_at")
        .values_list("content", flat=True)[:3]
    )
    return questions + recent_replies


def _maybe_supplemental_practical(round_obj, snap, asked_ids, category):
    """The DB bank is now a SUPPLEMENT, not the driver. Its highest-value use is
    seeding *practical* (hands-on) questions, because those carry a real
    ``practical_config`` that powers inline command/code validation (P2.4) — the
    generator only produces prose questions. So when the round's rotation lands
    on a practical slot AND the admin has seeded a matching practical question,
    surface it. If the bank is empty this simply returns None and generation
    takes over — the interview still runs fully.
    """
    if category != "practical":
        return None
    try:
        return select_next_question(
            round_type=round_obj.round_type,
            experience_level=snap.get("experience_level", round_obj.campaign.experience_level),
            technology_id=round_obj.campaign.primary_technology_id,
            technology_tags=snap.get("secondary_technologies"),
            difficulty=round_obj.difficulty_level,
            exclude_ids=asked_ids,
            category_preference="practical",
            strong_streak=round_obj.strong_answers_streak,
        )
    except Exception:  # noqa: BLE001 - bank lookup must never break generation
        return None


def ask_next_question(round_obj: InterviewRound) -> InterviewMessage | None:
    """Ask the next question — DYNAMIC GENERATION FIRST, bank as a supplement.

    The interview is now driven by ``question_generator.generate_question``,
    which builds the next question from the candidate's last answer (quoting /
    cross-questioning it), the resume-derived topic agenda, the chosen
    tech/level, and the running conversation. The curated ``InterviewQuestion``
    bank is used only as a *seed/supplement* — specifically to surface
    admin-authored *practical* questions (which carry hands-on validation
    config). With an empty bank the round still runs entirely on generation.
    """
    campaign = round_obj.campaign
    snap = _profile_for_round(round_obj)
    category = round_category_mix(round_obj.round_type, round_obj.questions_asked)

    # SUPPLEMENT: only practical slots may borrow a curated banked question,
    # because those carry the practical_config the generator can't synthesize.
    asked_ids = list(
        round_obj.messages.filter(question__isnull=False).values_list("question_id", flat=True)
    )
    banked = _maybe_supplemental_practical(round_obj, snap, asked_ids, category)
    if banked is not None and getattr(banked, "category", "") == "practical":
        content = banked.question_text
        if banked.practical_config.get("setup"):
            content = f"{banked.question_text}\n\n{banked.practical_config['setup']}"
        msg = InterviewMessage.objects.create(
            round=round_obj,
            role="interviewer",
            content=content,
            message_type="practical",
            question=banked,
            metadata={
                "category": "practical",
                "practical_config": banked.practical_config,
                "source": "bank_supplement",
            },
        )
        round_obj.questions_asked += 1
        round_obj.save(update_fields=["questions_asked"])
        return msg

    # PRIMARY: generate the next question dynamically (never returns None).
    last_answer, last_quality = _last_candidate_answer(round_obj)
    tail = [
        {"role": m.role, "content": (m.content or "")[:200]}
        for m in reversed(list(round_obj.messages.order_by("-created_at")[:8]))
    ]
    agenda = (round_obj.metadata or {}).get("topic_agenda") if isinstance(round_obj.metadata, dict) else None

    gen = generate_question(
        round_type=round_obj.round_type,
        profile_snapshot=snap,
        difficulty=round_obj.difficulty_level,
        questions_asked=round_obj.questions_asked,
        last_answer=last_answer,
        last_answer_quality=last_quality,
        topic_agenda=agenda,
        asked_texts=_asked_question_texts(round_obj),
        conversation_tail=tail,
        strong_streak=round_obj.strong_answers_streak,
        category_preference=category,
    )

    msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=gen.text,
        message_type=gen.message_type,
        question=None,  # dynamically generated — not a DB bank row
        metadata={
            "category": gen.category,
            "practical_config": gen.practical_config,
            "topic": gen.topic,
            "difficulty": gen.difficulty,
            "kind": gen.kind,
            "source": "generated",
        },
    )
    round_obj.questions_asked += 1
    round_obj.save(update_fields=["questions_asked"])
    return msg


def submit_answer(round_obj: InterviewRound, answer_text: str, metadata: dict | None = None) -> dict:
    meta = metadata or {}
    # Tell the scorer which round type this is so behavioral/HR answers are
    # weighted on STAR coverage rather than always defaulting to "technical".
    meta.setdefault("round_type", round_obj.round_type)
    # The last question asked is now usually a DYNAMICALLY GENERATED message with
    # no DB ``question`` FK, so match on message_type (question/practical) rather
    # than on a non-null FK — otherwise we'd score against a stale banked row (or
    # nothing) and the reply wouldn't reference what was actually just asked.
    last_q_msg = (
        round_obj.messages.filter(
            role="interviewer", message_type__in=("question", "practical")
        )
        .order_by("-created_at")
        .first()
    )
    question = last_q_msg.question if last_q_msg else None

    # If the candidate already validated their inline practical command/code for
    # THIS question (P2.4), honour that verified correctness in scoring (+15) even
    # if the typed answer here is a prose recap of what they did.
    if question is not None and getattr(question, "category", "") == "practical" and not meta.get("command_validated"):
        try:
            from apps.interviews.services.practical_lab import practical_validation_passed
            if practical_validation_passed(round_obj, question.id):
                meta["command_validated"] = True
        except Exception:  # noqa: BLE001 - never let the bonus lookup break scoring
            pass

    score_result = score_answer(question, answer_text, meta)
    cand_msg = InterviewMessage.objects.create(
        round=round_obj,
        role="candidate",
        content=answer_text,
        message_type=meta.get("input_type", "text"),
        question=question,
        score=score_result["score"],
        metadata=score_result,
    )

    if score_result["quality"] == "strong":
        round_obj.strong_answers_streak += 1
        if round_obj.strong_answers_streak >= 5:
            round_obj.difficulty_level = min(5, round_obj.difficulty_level + 1)
    else:
        round_obj.strong_answers_streak = 0

    round_obj.save(update_fields=["strong_answers_streak", "difficulty_level"])

    tail = [
        {"role": m.role, "content": m.content[:200]}
        for m in round_obj.messages.order_by("-created_at")[:6]
    ]
    # The reply uses the free rule-based engine; guard it anyway so a single bad
    # answer or snapshot can never 500 the live interview.
    try:
        reply = generate_interviewer_reply(
            persona_name=round_obj.persona_name,
            round_type=round_obj.round_type,
            question_text=last_q_msg.content if last_q_msg else "",
            candidate_answer=answer_text,
            score_hint=score_result,
            profile_snapshot=_profile_for_round(round_obj),
            conversation_tail=list(reversed(tail)),
            strong_streak=round_obj.strong_answers_streak,
        )
    except Exception:  # noqa: BLE001
        reply = "Got it — thanks. Let's keep going."

    interviewer_msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=reply,
        message_type="follow_up",
        metadata={"prior_score": score_result["score"]},
    )

    next_q = None
    if _should_ask_another(round_obj):
        try:
            next_q = ask_next_question(round_obj)
        except Exception:  # noqa: BLE001
            next_q = None

    return {
        "candidate_message": cand_msg,
        "interviewer_reply": interviewer_msg,
        "score": score_result,
        "next_question": next_q,
        "skipped": score_result.get("quality") == "skipped",
    }


def _target_question_count(round_obj: InterviewRound) -> int:
    base = max(5, round_obj.duration_minutes // 5)
    if round_obj.round_type == "hr":
        return min(8, base)
    if round_obj.round_type == "technical":
        return min(12, base + 2)
    return min(10, base)


def _should_ask_another(round_obj: InterviewRound) -> bool:
    """Skip-on-silence pacing (P2.2).

    The fixed-count cap (`_target_question_count`) is the *baseline* — enough
    questions to fill a round where the candidate answers fully. But when the
    candidate keeps skipping (silence → empty answers posted by the client),
    each question is consumed in seconds, so the baseline count would run out
    while plenty of clock remains and the round would end early.

    To "use the fixed round time", keep asking past the baseline *as long as
    there's still meaningful time left on the clock* — capped at a hard ceiling
    so a runaway can never ask forever. When the round has no ``ends_at`` (e.g.
    legacy rows), fall back to the static baseline.
    """
    baseline = _target_question_count(round_obj)
    asked = round_obj.questions_asked
    if asked < baseline:
        return True

    ends_at = round_obj.ends_at
    if not ends_at:
        return False

    seconds_left = (ends_at - timezone.now()).total_seconds()
    # Stop padding once under a minute remains — no time for another exchange.
    if seconds_left < 60:
        return False

    # Hard ceiling: never exceed ~2x the baseline regardless of skips.
    return asked < baseline * 2


def extend_round(round_obj: InterviewRound, minutes: int = 10) -> bool:
    if getattr(round_obj.campaign, "is_sample", False):
        return False
    if round_obj.extension_minutes + minutes > round_obj.max_extension_minutes:
        return False
    round_obj.extension_minutes += minutes
    if round_obj.ends_at:
        round_obj.ends_at = round_obj.ends_at + timedelta(minutes=minutes)
    round_obj.save(update_fields=["extension_minutes", "ends_at"])
    InterviewMessage.objects.create(
        round=round_obj,
        role="system",
        content=f"Interview extended by {minutes} minutes for Q&A.",
        message_type="system",
    )
    return True


def record_av_status(round_obj: InterviewRound, mic_on: bool, camera_on: bool) -> dict:
    compliant = mic_on and camera_on
    now = timezone.now()
    if compliant:
        round_obj.av_compliant = True
        round_obj.av_warning_started_at = None
        round_obj.save(update_fields=["av_compliant", "av_warning_started_at"])
        return {"action": "ok", "compliant": True}

    if not round_obj.av_warning_started_at:
        round_obj.av_warning_started_at = now
        round_obj.save(update_fields=["av_warning_started_at"])
        InterviewMessage.objects.create(
            round=round_obj,
            role="system",
            content="Please enable microphone and camera. Interview will auto-end in 5 minutes if not enabled.",
            message_type="av_warning",
        )
        return {"action": "warn", "compliant": False, "exit_in_seconds": 300}

    elapsed = (now - round_obj.av_warning_started_at).total_seconds()
    if elapsed >= 300:
        out = end_round(round_obj, reason="av_timeout")
        out["action"] = "end"
        return out

    return {"action": "warn", "compliant": False, "exit_in_seconds": max(0, 300 - int(elapsed))}


def end_round(round_obj: InterviewRound, reason: str = "completed") -> dict:
    from django.db import transaction as db_transaction
    with db_transaction.atomic():
        locked = InterviewRound.objects.select_for_update().get(pk=round_obj.pk)
        if locked.status != "in_progress":
            # Already ended by a concurrent request
            return {"already_ended": True, "status": locked.status}

        now = timezone.now()
        round_obj.status = "completed"
        round_obj.ended_at = now
        round_obj.save(update_fields=["status", "ended_at"])

        scores = list(
            round_obj.messages.filter(role="candidate", score__isnull=False).values_list("score", flat=True)
        )
        agg = aggregate_round_scores(scores)
        passed = agg["overall_score"] >= round_obj.pass_threshold and reason != "av_timeout"
        strengths, improvements = build_strengths_and_improvements(
            [{"score": s} for s in scores],
            round_obj.round_type,
        )

        report = InterviewReport.objects.create(
            round=round_obj,
            passed=passed,
            **agg,
            strengths=strengths,
            improvements=improvements,
            summary=_build_summary(round_obj, passed, reason),
            study_plan=_study_plan(round_obj),
            question_breakdown=list(
                round_obj.messages.filter(role="candidate", score__isnull=False).values(
                    "content", "score", "metadata"
                )[:20]
            ),
        )

        round_obj.overall_score = agg["overall_score"]
        round_obj.status = "passed" if passed else "failed"
        round_obj.save(update_fields=["overall_score", "status"])

        campaign = round_obj.campaign
        result = {"report": report, "passed": passed, "reason": reason}

        if getattr(campaign, "is_sample", False):
            campaign.status = "completed"
            campaign.completed_at = now
            campaign.save(update_fields=["status", "completed_at", "updated_at"])
            report.summary = (
                report.summary + " This was your free sample — subscribe for full multi-round interviews, "
                "hands-on labs, and FIXIT-INT certificates."
            )
            report.save(update_fields=["summary"])
            result["is_sample"] = True
            result["upgrade_required"] = True
            return result

        if passed:
            nxt = unlock_next_round(campaign, round_obj)
            result["next_round"] = nxt
            if not nxt:
                _finalize_campaign(campaign)
        else:
            campaign.status = "failed"
            campaign.save(update_fields=["status", "updated_at"])

    try:
        from apps.notifications.tasks import send_notification_email
        from django.conf import settings as dj_settings
        from apps.interviews.services.notify import notify_round_results

        notify_round_results(round_obj, passed, agg["overall_score"])

        send_notification_email.delay(
            subject=f"Interview round {round_obj.round_number} results — FixitLab",
            to_email=campaign.user.email,
            template="emails/interview_round_results.html",
            context={
                "round_title": round_obj.title,
                "passed": passed,
                "score": f"{agg['overall_score']:.0f}",
                "summary": report.summary[:500],
                "dashboard_url": f"{getattr(dj_settings, 'FRONTEND_URL', '')}/interviews",
            },
        )
    except Exception:
        pass

    return result


def _build_summary(round_obj: InterviewRound, passed: bool, reason: str) -> str:
    if reason == "av_timeout":
        return "Session ended: microphone/camera were not enabled within the grace period."
    if passed:
        return (
            f"{round_obj.persona_name} recommends proceeding — solid performance for "
            f"{round_obj.round_type} at {round_obj.campaign.experience_level} level."
        )
    return (
        f"Below passing threshold ({round_obj.pass_threshold}). Focus on depth, structure, "
        "and hands-on practice before retrying."
    )


def _study_plan(round_obj: InterviewRound) -> list:
    tech = round_obj.campaign.primary_technology
    slug = tech.slug if tech else "linux"
    return [
        {"title": "Practice scenarios", "url": f"/technologies/{slug}"},
        {"title": "Simulation labs", "url": "/scenarios?mode=simulation"},
        {"title": "Review round transcript", "url": f"/interviews/round/{round_obj.id}/report"},
    ]


def _finalize_campaign(campaign: InterviewCampaign) -> InterviewCampaign:
    rounds = campaign.rounds.all()
    scores = [r.overall_score for r in rounds if r.overall_score is not None]
    campaign.overall_score = sum(scores) / len(scores) if scores else 0
    campaign.status = "completed"
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=["overall_score", "status", "completed_at", "updated_at"])
    issue_certificate(campaign)
    return campaign
