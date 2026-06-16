"""
engine_v2.py — Drop-in replacement for engine.py with LLM integration.

Changes from engine.py:
  1. generate_interviewer_reply() → llm_engine.generate_interviewer_reply()
     with prior_round_summaries for cross-round memory
  2. submit_answer() optionally generates a dynamic follow-up via LLM
  3. end_round() uses llm_engine.generate_ai_scorecard() for richer reports
  4. _collect_prior_summaries() builds cross-round context

To activate: replace engine.py imports in views.py:
  from apps.interviews.services.engine import start_round, submit_answer, ...
with:
  from apps.interviews.services.engine_v2 import start_round, submit_answer, ...
"""

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
from apps.interviews.services.llm_engine import (
    generate_ai_scorecard,
    generate_follow_up_question,
    generate_interviewer_reply,
)
from apps.interviews.services.question_selector import round_category_mix, select_next_question
from apps.interviews.services.scoring import score_answer
from apps.interviews.services.notify import notify_round_results


INTRO_TEMPLATES = {
    "technical": (
        "Hi, I'm {persona}. Thanks for joining — I've got your resume pulled up. "
        "We'll spend about {minutes} minutes on technical depth, troubleshooting, and maybe a hands-on scenario. "
        "Camera and mic stay on please. Ready when you are — "
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
        "I'm {persona}. This round goes deeper on gaps or strengths from earlier rounds — architecture, trade-offs, war stories. "
        "{minutes} minutes. What area do you feel strongest in technically right now?"
    ),
    "leadership": (
        "I'm {persona}. Leadership and stakeholder round — influence without authority, mentoring, delivery under pressure. "
        "Tell me about a time you had to push back on a deadline."
    ),
}


# ---------------------------------------------------------------------------
# Cross-round context
# ---------------------------------------------------------------------------

def _collect_prior_summaries(round_obj: InterviewRound) -> list[dict]:
    """Collect completed round reports for cross-round LLM context."""
    prior = []
    completed_rounds = (
        round_obj.campaign.rounds
        .filter(status__in=["passed", "failed", "completed"])
        .exclude(id=round_obj.id)
        .order_by("round_number")
        .prefetch_related("report")
    )
    for r in completed_rounds:
        try:
            report = r.report
            prior.append({
                "round_number": r.round_number,
                "round_type": r.round_type,
                "overall_score": report.overall_score,
                "summary": (report.summary or "")[:200],
                "strengths": report.strengths[:2] if report.strengths else [],
                "improvements": report.improvements[:2] if report.improvements else [],
            })
        except Exception:
            pass
    return prior


def _profile_for_round(round_obj: InterviewRound) -> dict:
    return round_obj.campaign.profile_snapshot or {}


def _total_rounds(round_obj: InterviewRound) -> int:
    return round_obj.campaign.rounds.count()


# ---------------------------------------------------------------------------
# start_round — unchanged from engine.py
# ---------------------------------------------------------------------------

def start_round(round_obj: InterviewRound) -> dict:
    now = timezone.now()
    round_obj.status = "in_progress"
    round_obj.started_at = now
    round_obj.ends_at = now + timedelta(minutes=round_obj.duration_minutes + round_obj.extension_minutes)
    round_obj.save(update_fields=["status", "started_at", "ends_at"])

    campaign = round_obj.campaign
    if getattr(campaign, "is_sample", False):
        from apps.interviews.services.sample_interview import mark_sample_used
        mark_sample_used(campaign.user)

    snap = _profile_for_round(round_obj)
    if getattr(campaign, "is_sample", False):
        intro = (
            f"Hi, I'm {round_obj.persona_name}. Welcome to your free {round_obj.duration_minutes}-minute sample interview. "
            "We'll cover a few quick technical questions so you can experience voice Q&A, scoring, and feedback. "
            "Camera and mic must stay on. This is a preview — subscribe for full 3–5 round cycles and certificates. "
            f"What are you currently working on as a {snap.get('target_role') or snap.get('experience_level', 'mid')}-level engineer?"
        )
    else:
        tpl = INTRO_TEMPLATES.get(round_obj.round_type, INTRO_TEMPLATES["technical"])
        intro = tpl.format(
            persona=round_obj.persona_name,
            minutes=round_obj.duration_minutes,
            company=snap.get("current_company") or "your current company",
            role=snap.get("target_role") or snap.get("experience_level", "mid") + " role",
        )

    msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=intro,
        message_type="introduction",
    )
    return {"message": msg, "ends_at": round_obj.ends_at.isoformat()}


# ---------------------------------------------------------------------------
# ask_next_question — unchanged from engine.py
# ---------------------------------------------------------------------------

def ask_next_question(round_obj: InterviewRound) -> InterviewMessage | None:
    campaign = round_obj.campaign
    snap = _profile_for_round(round_obj)
    asked_ids = list(
        round_obj.messages.filter(question__isnull=False).values_list("question_id", flat=True)
    )
    category = round_category_mix(round_obj.round_type, round_obj.questions_asked)
    q = select_next_question(
        round_type=round_obj.round_type,
        experience_level=snap.get("experience_level", campaign.experience_level),
        technology_id=campaign.primary_technology_id,
        technology_tags=snap.get("secondary_technologies"),
        difficulty=round_obj.difficulty_level,
        exclude_ids=asked_ids,
        category_preference=category,
        strong_streak=round_obj.strong_answers_streak,
    )
    if not q:
        return None

    content = q.question_text
    if q.category == "practical" and q.practical_config.get("setup"):
        content = f"{q.question_text}\n\n{q.practical_config['setup']}"

    msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=content,
        message_type="practical" if q.category == "practical" else "question",
        question=q,
        metadata={"category": q.category, "practical_config": q.practical_config},
    )
    round_obj.questions_asked += 1
    round_obj.save(update_fields=["questions_asked"])
    return msg


# ---------------------------------------------------------------------------
# submit_answer — upgraded with LLM reply + optional dynamic follow-up
# ---------------------------------------------------------------------------

def submit_answer(round_obj: InterviewRound, answer_text: str, metadata: dict | None = None) -> dict:
    meta = metadata or {}
    last_q_msg = (
        round_obj.messages.filter(role="interviewer", question__isnull=False)
        .order_by("-created_at")
        .first()
    )
    question = last_q_msg.question if last_q_msg else None
    question_text = last_q_msg.content if last_q_msg else ""

    # Heuristic score (still used for difficulty adaptation + DB storage)
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

    # Difficulty adaptation
    if score_result["quality"] == "strong":
        round_obj.strong_answers_streak += 1
        if round_obj.strong_answers_streak >= 5:
            round_obj.difficulty_level = min(5, round_obj.difficulty_level + 1)
    else:
        round_obj.strong_answers_streak = 0
    round_obj.save(update_fields=["strong_answers_streak", "difficulty_level"])

    # Build conversation tail for LLM context
    tail = [
        {"role": m.role, "content": m.content[:200], "message_type": m.message_type}
        for m in round_obj.messages.order_by("-created_at")[:10]
    ]

    # Cross-round context
    prior_summaries = _collect_prior_summaries(round_obj)

    # LLM-powered reply (falls back to rule-based automatically)
    reply = generate_interviewer_reply(
        persona_name=round_obj.persona_name,
        round_type=round_obj.round_type,
        question_text=question_text,
        candidate_answer=answer_text,
        score_hint=score_result,
        profile_snapshot=_profile_for_round(round_obj),
        conversation_tail=list(reversed(tail)),
        strong_streak=round_obj.strong_answers_streak,
        round_number=round_obj.round_number,
        total_rounds=_total_rounds(round_obj),
        prior_round_summaries=prior_summaries,
    )

    interviewer_msg = InterviewMessage.objects.create(
        round=round_obj,
        role="interviewer",
        content=reply,
        message_type="follow_up",
        metadata={"prior_score": score_result["score"]},
    )

    # Dynamic LLM-generated follow-up question (inject as next question when DB pool is exhausted)
    dynamic_followup: str | None = None
    target = _target_question_count(round_obj)
    remaining_db_questions = target - round_obj.questions_asked

    if remaining_db_questions <= 0 and score_result["quality"] in ("strong", "adequate"):
        dynamic_followup = generate_follow_up_question(
            persona_name=round_obj.persona_name,
            round_type=round_obj.round_type,
            question_text=question_text,
            candidate_answer=answer_text,
            profile_snapshot=_profile_for_round(round_obj),
            conversation_tail=list(reversed(tail)),
        )

    next_q = None
    if round_obj.questions_asked < target:
        next_q = ask_next_question(round_obj)
    elif dynamic_followup:
        # Store dynamic question as an interviewer message so it renders
        next_q = InterviewMessage.objects.create(
            round=round_obj,
            role="interviewer",
            content=dynamic_followup,
            message_type="question",
            metadata={"dynamic": True},
        )
        round_obj.questions_asked += 1
        round_obj.save(update_fields=["questions_asked"])

    return {
        "candidate_message": cand_msg,
        "interviewer_reply": interviewer_msg,
        "score": score_result,
        "next_question": next_q,
    }


def _target_question_count(round_obj: InterviewRound) -> int:
    base = max(5, round_obj.duration_minutes // 5)
    if round_obj.round_type == "hr":
        return min(8, base)
    if round_obj.round_type == "technical":
        return min(12, base + 2)
    return min(10, base)


# ---------------------------------------------------------------------------
# extend_round + record_av_status — identical to engine.py
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# end_round — upgraded with AI scorecard
# ---------------------------------------------------------------------------

def end_round(round_obj: InterviewRound, reason: str = "completed") -> dict:
    now = timezone.now()
    round_obj.status = "completed"
    round_obj.ended_at = now
    round_obj.save(update_fields=["status", "ended_at"])

    # Collect all messages for AI scorecard
    all_messages = list(
        round_obj.messages
        .order_by("created_at")
        .values("role", "content", "message_type", "score")
    )
    prior_summaries = _collect_prior_summaries(round_obj)

    # AI scorecard (falls back to heuristic)
    scorecard = generate_ai_scorecard(
        round_type=round_obj.round_type,
        round_number=round_obj.round_number,
        total_rounds=_total_rounds(round_obj),
        profile_snapshot=_profile_for_round(round_obj),
        messages=all_messages,
        prior_round_summaries=prior_summaries,
    )

    passed = scorecard.get("passed", False) and reason != "av_timeout"
    if reason == "av_timeout":
        passed = False

    # Build study plan
    study_plan = _study_plan(round_obj, scorecard.get("study_plan_topics", []))

    report = InterviewReport.objects.create(
        round=round_obj,
        passed=passed,
        technical_score=scorecard.get("technical_score", 0),
        communication_score=scorecard.get("communication_score", 0),
        problem_solving_score=scorecard.get("problem_solving_score", 0),
        practical_score=scorecard.get("practical_score", 0),
        presence_score=scorecard.get("presence_score", 70),
        resume_alignment_score=scorecard.get("resume_alignment_score", 65),
        overall_score=scorecard.get("overall_score", 0),
        strengths=scorecard.get("strengths", []),
        improvements=scorecard.get("improvements", []),
        summary=_build_summary(round_obj, passed, reason, scorecard),
        study_plan=study_plan,
        question_breakdown=list(
            round_obj.messages.filter(role="candidate", score__isnull=False).values(
                "content", "score", "metadata"
            )[:20]
        ),
    )

    round_obj.overall_score = scorecard.get("overall_score", 0)
    round_obj.status = "passed" if passed else "failed"
    round_obj.save(update_fields=["overall_score", "status"])

    campaign = round_obj.campaign
    result = {
        "report": report,
        "passed": passed,
        "reason": reason,
        "scorecard_extras": {
            "confidence_signals": scorecard.get("confidence_signals", ""),
            "time_management_note": scorecard.get("time_management_note", ""),
            "benchmark_comparison": scorecard.get("benchmark_comparison", ""),
        },
    }

    if getattr(campaign, "is_sample", False):
        campaign.status = "completed"
        campaign.completed_at = now
        campaign.save(update_fields=["status", "completed_at", "updated_at"])
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
        from django.conf import settings as dj_settings
        from apps.notifications.tasks import send_notification_email

        notify_round_results(round_obj, passed, scorecard.get("overall_score", 0))
        send_notification_email.delay(
            subject=f"Interview round {round_obj.round_number} results — FixitLab",
            to_email=campaign.user.email,
            template="emails/interview_round_results.html",
            context={
                "round_title": round_obj.title,
                "passed": passed,
                "score": f"{scorecard.get('overall_score', 0):.0f}",
                "summary": (report.summary or "")[:500],
                "dashboard_url": f"{getattr(dj_settings, 'FRONTEND_URL', '')}/interviews",
            },
        )
    except Exception:
        pass

    return result


def _build_summary(round_obj: InterviewRound, passed: bool, reason: str, scorecard: dict) -> str:
    if reason == "av_timeout":
        return "Session ended: microphone/camera were not enabled within the grace period."
    # Prefer AI-generated summary if available
    if scorecard.get("summary"):
        return scorecard["summary"]
    if passed:
        return (
            f"{round_obj.persona_name} recommends proceeding — solid performance for "
            f"{round_obj.round_type} at {round_obj.campaign.experience_level} level."
        )
    return (
        f"Below passing threshold ({round_obj.pass_threshold}). Focus on depth, structure, "
        "and hands-on practice before retrying."
    )


def _study_plan(round_obj: InterviewRound, ai_topics: list[str]) -> list:
    tech = round_obj.campaign.primary_technology
    slug = tech.slug if tech else "linux"
    plan = [
        {"title": "Practice scenarios", "url": f"/technologies/{slug}"},
        {"title": "Simulation labs", "url": "/scenarios?mode=simulation"},
        {"title": "Review round transcript", "url": f"/interviews/round/{round_obj.id}/report"},
    ]
    for topic in ai_topics[:3]:
        plan.append({"title": topic, "url": f"/scenarios?q={topic.replace(' ', '+')}"})
    return plan


def _finalize_campaign(campaign: InterviewCampaign) -> InterviewCampaign:
    rounds = campaign.rounds.all()
    scores = [r.overall_score for r in rounds if r.overall_score is not None]
    campaign.overall_score = sum(scores) / len(scores) if scores else 0
    campaign.status = "completed"
    campaign.completed_at = timezone.now()
    campaign.save(update_fields=["overall_score", "status", "completed_at", "updated_at"])
    issue_certificate(campaign)
    return campaign
