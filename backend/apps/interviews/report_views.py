"""Rich report endpoints — transcript w/ timestamps + conversation playback,
and résumé highlights mapped to the questions they were probed by.

Parity: interviewai.io transcript + playback; résumé-to-question mapping. All
derived from the already-stored transcript + parsed resume. 100% free.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.models import InterviewRound


def _topic_for_message(msg) -> str:
    meta = msg.metadata if isinstance(msg.metadata, dict) else {}
    return (meta.get("topic") or meta.get("topic_detected") or "") or ""


class InterviewRoundTranscriptView(APIView):
    """GET — full transcript with per-message timestamps + relative offsets for
    conversation playback, plus résumé highlights mapped to the topics covered."""

    permission_classes = [IsAuthenticated]

    def get(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign").prefetch_related("messages"),
            id=round_id,
            campaign__user=request.user,
        )
        messages = list(round_obj.messages.all())
        base = round_obj.started_at or (messages[0].created_at if messages else None)

        transcript = []
        topics_covered: dict[str, dict] = {}
        for m in messages:
            offset = 0
            if base and m.created_at:
                offset = max(0, int((m.created_at - base).total_seconds()))
            topic = _topic_for_message(m)
            row = {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "score": m.score,
                "topic": topic,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
                "offset_seconds": offset,
            }
            transcript.append(row)
            if topic and m.role == "interviewer" and m.message_type in ("question", "practical"):
                topics_covered.setdefault(topic, {"topic": topic, "question_count": 0, "offset_seconds": offset})
                topics_covered[topic]["question_count"] += 1

        # --- Map résumé skills to whether/where they were probed. ---
        snap = round_obj.campaign.profile_snapshot or {}
        parsed = snap.get("resume_parsed") or {}
        skills = [str(s).lower() for s in (parsed.get("skills_detected") or [])]
        # Reuse the same skill->topic vocabulary the resume scorer uses.
        from apps.interviews.services.resume_parser import _TECH_KEYWORDS

        def _skill_topic(skill: str) -> str:
            for topic, kws in _TECH_KEYWORDS.items():
                if skill == topic or skill in kws:
                    return topic
            return skill

        resume_highlights = []
        for skill in skills[:20]:
            topic = _skill_topic(skill)
            covered = topic in topics_covered
            resume_highlights.append({
                "skill": skill,
                "mapped_topic": topic,
                "covered": covered,
                "question_count": topics_covered.get(topic, {}).get("question_count", 0),
                "offset_seconds": topics_covered.get(topic, {}).get("offset_seconds"),
            })

        return Response({
            "round_id": str(round_obj.id),
            "round_type": round_obj.round_type,
            "started_at": round_obj.started_at.isoformat() if round_obj.started_at else None,
            "ended_at": round_obj.ended_at.isoformat() if round_obj.ended_at else None,
            "duration_seconds": (
                int((round_obj.ended_at - round_obj.started_at).total_seconds())
                if round_obj.started_at and round_obj.ended_at else None
            ),
            "transcript": transcript,
            "topics_covered": list(topics_covered.values()),
            "resume_highlights": resume_highlights,
        })
