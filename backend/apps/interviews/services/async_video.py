"""One-way (async) video interview mode.

Parity with TestGorilla / aiinterviews.io one-way video: the candidate is shown
a fixed set of prompts and records a video answer to each (browser MediaRecorder
on the client). The clip is stored in the EXISTING Django storage — no paid video
service. The browser also provides a free Web-Speech transcript, which we score
with the same free engine the live interview uses, plus heuristic confidence.

Runs ALONGSIDE the live interview — an async round just has ``mode='async_video'``.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.interviews.models import AsyncVideoResponse, InterviewMessage, InterviewRound
from apps.interviews.services.question_generator import generate_question, plan_round_topics


def build_async_prompts(round_obj: InterviewRound, count: int = 5) -> list[dict]:
    """Generate (and persist on the round) the fixed prompt set for a one-way
    video round. Uses the same free generator the live engine uses, so prompts
    are resume/role aware. Idempotent — returns the stored set if already built.
    """
    meta = dict(round_obj.metadata or {})
    existing = meta.get("async_prompts")
    if existing:
        return existing

    snap = round_obj.campaign.profile_snapshot or {}
    agenda = plan_round_topics(round_obj.round_type, snap)
    prompts: list[dict] = []
    asked: list[str] = []
    for i in range(max(3, min(8, count))):
        gen = generate_question(
            round_type=round_obj.round_type,
            profile_snapshot=snap,
            difficulty=round_obj.difficulty_level or 2,
            questions_asked=i,
            last_answer="",
            topic_agenda=agenda,
            asked_texts=asked,
        )
        asked.append(gen.text)
        prompts.append({
            "index": i,
            "text": gen.text,
            "topic": gen.topic,
            "category": gen.category,
        })

    meta["async_prompts"] = prompts
    round_obj.metadata = meta
    round_obj.save(update_fields=["metadata"])
    return prompts


def record_async_response(
    round_obj: InterviewRound,
    *,
    question_index: int,
    prompt_text: str,
    transcript: str = "",
    duration_seconds: float = 0,
    video_file=None,
) -> AsyncVideoResponse:
    """Store one recorded answer, score its transcript, and attach heuristic
    confidence signals — all free. Upserts on (round, question_index) so a
    re-record overwrites.
    """
    from apps.interviews.services.scorecard import analyze_confidence
    from apps.interviews.services.scoring import score_answer

    transcript = (transcript or "").strip()
    score_result = score_answer(None, transcript, {"round_type": round_obj.round_type})

    # Per-answer confidence from this single clip's transcript + duration.
    fake_msg = InterviewMessage(role="candidate", content=transcript, message_type="voice")
    started = timezone.now()
    ended = started + timedelta(seconds=max(1.0, float(duration_seconds or 1)))
    confidence = analyze_confidence([fake_msg], started_at=started, ended_at=ended)

    analysis = {
        "score": score_result,
        "confidence": confidence,
    }

    defaults = {
        "prompt_text": prompt_text or "",
        "transcript": transcript,
        "duration_seconds": float(duration_seconds or 0),
        "score": score_result["score"],
        "analysis": analysis,
    }
    if video_file is not None:
        defaults["video_file"] = video_file

    obj, _created = AsyncVideoResponse.objects.update_or_create(
        round=round_obj,
        question_index=question_index,
        defaults=defaults,
    )

    # Mirror into the transcript so the report (which aggregates candidate
    # message scores) and playback see this answer too. A JSON-key lookup can't
    # be a create kwarg, so filter-then-update/create explicitly and upsert on
    # (round, question_index) for re-records.
    msg_content = transcript or "(recorded video answer)"
    msg_meta = {**score_result, "question_index": question_index, "is_async_video": True}
    existing = (
        InterviewMessage.objects.filter(
            round=round_obj,
            role="candidate",
            message_type="async_video",
            metadata__question_index=question_index,
        )
        .order_by("created_at")
        .first()
    )
    if existing:
        existing.content = msg_content
        existing.score = score_result["score"]
        existing.metadata = msg_meta
        existing.save(update_fields=["content", "score", "metadata"])
    else:
        InterviewMessage.objects.create(
            round=round_obj,
            role="candidate",
            content=msg_content,
            message_type="async_video",
            score=score_result["score"],
            metadata=msg_meta,
        )
    return obj


def finalize_async_round(round_obj: InterviewRound) -> dict:
    """Score the full one-way round from its recorded answers and produce the
    standard report via the existing engine.end_round path so async rounds share
    the same scorecard, certificate, and analytics plumbing as live rounds.
    """
    from apps.interviews.services import engine

    # Ensure each recorded answer has a candidate message + score before ending
    # so engine.end_round aggregates them (it reads candidate message scores).
    if round_obj.status == "in_progress":
        return engine.end_round(round_obj, reason="completed")
    # If not in progress (e.g. resumed), still return existing report if any.
    report = getattr(round_obj, "report", None)
    return {"report": report, "passed": round_obj.status == "passed", "already_ended": True}
