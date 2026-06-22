"""One-way async video interview endpoints (parity: one-way video interviews).

The candidate records answers to a fixed prompt set with the browser
MediaRecorder; clips are stored in the existing Django storage (no paid video
service). Recruiters/candidates review playback + per-answer heuristic scoring.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.models import AsyncVideoResponse, InterviewRound
from apps.interviews.serializers import AsyncVideoResponseSerializer, InterviewReportSerializer
from apps.interviews.services.async_video import (
    build_async_prompts,
    finalize_async_round,
    record_async_response,
)
from apps.interviews.services import engine
from common.throttles import InterviewRateThrottle


def _owned_round(user, round_id):
    return get_object_or_404(
        InterviewRound.objects.select_related("campaign"),
        id=round_id,
        campaign__user=user,
    )


class AsyncRoundPromptsView(APIView):
    """GET — the fixed prompt set for a one-way video round (generates + stores
    it on first call). Also marks the round in_progress so answers can be saved."""

    permission_classes = [IsAuthenticated]

    def get(self, request, round_id):
        round_obj = _owned_round(request.user, round_id)
        if round_obj.mode != "async_video":
            return Response({"error": "This round is not a one-way video round"}, status=400)
        prompts = build_async_prompts(round_obj)
        existing = AsyncVideoResponse.objects.filter(round=round_obj)
        return Response({
            "round_id": str(round_obj.id),
            "status": round_obj.status,
            "prompts": prompts,
            "responses": AsyncVideoResponseSerializer(existing, many=True).data,
        })

    def post(self, request, round_id):
        """Begin the async round (mark in_progress) so recorded answers attach."""
        round_obj = _owned_round(request.user, round_id)
        if round_obj.mode != "async_video":
            return Response({"error": "This round is not a one-way video round"}, status=400)
        if round_obj.status in ("scheduled", "ready", "schedulable"):
            from django.utils import timezone

            round_obj.status = "in_progress"
            round_obj.started_at = timezone.now()
            round_obj.save(update_fields=["status", "started_at"])
        prompts = build_async_prompts(round_obj)
        return Response({"round_id": str(round_obj.id), "status": round_obj.status, "prompts": prompts})


class AsyncRoundResponseView(APIView):
    """POST — submit one recorded answer (multipart: video clip + transcript +
    duration). Stores the clip, scores the transcript, attaches confidence."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [InterviewRateThrottle]

    def post(self, request, round_id):
        round_obj = _owned_round(request.user, round_id)
        if round_obj.mode != "async_video":
            return Response({"error": "This round is not a one-way video round"}, status=400)
        if round_obj.status != "in_progress":
            return Response({"error": "Round not in progress — start it first"}, status=400)

        try:
            question_index = int(request.data.get("question_index", 0))
        except (TypeError, ValueError):
            question_index = 0
        transcript = (request.data.get("transcript") or "")[:8000]
        try:
            duration = float(request.data.get("duration_seconds", 0) or 0)
        except (TypeError, ValueError):
            duration = 0.0
        video = request.FILES.get("video")
        if video and video.size > 60 * 1024 * 1024:
            return Response({"error": "Video clip too large (max 60 MB)"}, status=400)

        prompts = build_async_prompts(round_obj)
        prompt_text = ""
        for p in prompts:
            if p.get("index") == question_index:
                prompt_text = p.get("text", "")
                break

        resp = record_async_response(
            round_obj,
            question_index=question_index,
            prompt_text=prompt_text,
            transcript=transcript,
            duration_seconds=duration,
            video_file=video,
        )
        return Response(AsyncVideoResponseSerializer(resp).data, status=201)


class AsyncRoundFinalizeView(APIView):
    """POST — finish the one-way round; aggregate the recorded answers into the
    standard report (shared scorecard / analytics)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, round_id):
        round_obj = _owned_round(request.user, round_id)
        if round_obj.mode != "async_video":
            return Response({"error": "This round is not a one-way video round"}, status=400)
        result = finalize_async_round(round_obj)
        report = result.get("report") or getattr(round_obj, "report", None)
        data = {
            "passed": result.get("passed", round_obj.status == "passed"),
            "report": InterviewReportSerializer(report).data if report else None,
        }
        if result.get("next_round"):
            from apps.interviews.serializers import InterviewRoundSerializer

            data["next_round"] = InterviewRoundSerializer(result["next_round"]).data
        return Response(data)


class AsyncRoundReviewView(APIView):
    """GET — review playback: all recorded answers (clip URLs) + per-answer
    scoring for a one-way round. Used by the candidate and (later) recruiters."""

    permission_classes = [IsAuthenticated]

    def get(self, request, round_id):
        round_obj = _owned_round(request.user, round_id)
        responses = AsyncVideoResponse.objects.filter(round=round_obj)
        return Response({
            "round_id": str(round_obj.id),
            "status": round_obj.status,
            "responses": AsyncVideoResponseSerializer(responses, many=True).data,
        })
