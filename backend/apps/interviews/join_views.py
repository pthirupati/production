"""Admin join-request and observer APIs."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.adminpanel.permissions import IsPlatformAdmin
from apps.interviews.models import InterviewAdminJoinRequest, InterviewRound
from apps.interviews.serializers import InterviewMessageSerializer, InterviewRoundSerializer
from apps.interviews.services.admin_host import (
    admin_join_session,
    admin_post_question,
    admin_rate_answer,
    admin_rate_target,
    admin_set_ai_enabled,
    host_state,
)
from apps.interviews.services.interview_settings import get_platform_settings


def _approved_request(request, token: str) -> InterviewAdminJoinRequest:
    return get_object_or_404(
        InterviewAdminJoinRequest.objects.select_related("round", "round__campaign"),
        observer_token=token,
        status="approved",
        admin_user=request.user,
    )


class AdminRequestJoinInterviewView(APIView):
    """POST /api/admin/interviews/join-request/ { round_id, message }"""

    permission_classes = [IsPlatformAdmin]

    def post(self, request):
        if not get_platform_settings().allow_admin_observer:
            return Response({"error": "Admin observer disabled in settings"}, status=403)
        round_id = request.data.get("round_id")
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign", "campaign__user"),
            id=round_id,
        )
        if round_obj.status != "in_progress":
            return Response({"error": "Round is not live"}, status=400)
        existing = InterviewAdminJoinRequest.objects.filter(
            round=round_obj, admin_user=request.user, status="pending",
        ).first()
        if existing:
            return Response({"request": _join_payload(existing), "already_pending": True})
        req = InterviewAdminJoinRequest.objects.create(
            round=round_obj,
            admin_user=request.user,
            candidate_user=round_obj.campaign.user,
            message=(request.data.get("message") or "Admin would like to observe this interview session."),
        )
        return Response({"request": _join_payload(req)}, status=201)


class AdminJoinRequestsListView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = InterviewAdminJoinRequest.objects.select_related(
            "round", "admin_user", "candidate_user", "round__campaign",
        ).order_by("-created_at")[:100]
        return Response({"requests": [_join_payload(r) for r in qs]})


class AdminLiveInterviewSessionsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        live = InterviewRound.objects.filter(
            status="in_progress",
        ).select_related("campaign", "campaign__user").order_by("-started_at")[:50]
        scheduled = InterviewRound.objects.filter(
            status__in=("scheduled", "ready", "schedulable"),
            scheduled_at__isnull=False,
        ).select_related("campaign", "campaign__user").order_by("scheduled_at")[:50]
        return Response({
            "live": [_live_payload(r) for r in live],
            "scheduled": [_live_payload(r) for r in scheduled],
        })


class AdminObserverSessionView(APIView):
    """GET approved observer transcript (admin). POST actions: join, ask, ai toggle."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request, token):
        req = _approved_request(request, token)
        round_obj = req.round
        return Response({
            "round": InterviewRoundSerializer(round_obj).data,
            "messages": InterviewMessageSerializer(round_obj.messages.all(), many=True).data,
            "observer_mode": True,
            "host_state": host_state(round_obj),
            "rate_target": admin_rate_target(round_obj),
        })

    def post(self, request, token):
        req = _approved_request(request, token)
        round_obj = req.round
        if round_obj.status != "in_progress":
            return Response({"error": "Round is not live"}, status=400)

        action = (request.data.get("action") or "join").strip().lower()
        if action == "join":
            result = admin_join_session(
                round_obj,
                admin_user=request.user,
                display_name=request.data.get("display_name"),
            )
            msgs = InterviewMessageSerializer(result.get("messages") or [], many=True).data
            return Response({
                "host_state": result["host_state"],
                "messages": msgs,
                "already_joined": result.get("already_joined", False),
            })

        if action == "ask":
            text = (request.data.get("question") or request.data.get("text") or "").strip()
            if not text:
                return Response({"error": "question required"}, status=400)
            try:
                msg = admin_post_question(
                    round_obj,
                    text=text,
                    admin_user=request.user,
                    spoken=bool(request.data.get("spoken")),
                )
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)
            return Response({
                "message": InterviewMessageSerializer(msg).data,
                "host_state": host_state(round_obj),
            })

        if action == "ai":
            enabled = bool(request.data.get("enabled"))
            result = admin_set_ai_enabled(round_obj, enabled=enabled, admin_user=request.user)
            return Response({
                "host_state": result["host_state"],
                "messages": InterviewMessageSerializer(result.get("messages") or [], many=True).data,
                "next_question": (
                    InterviewMessageSerializer(result["next_question"]).data
                    if result.get("next_question") else None
                ),
            })

        if action == "rate":
            try:
                raw_score = request.data.get("score")
                score_val = float(raw_score) if raw_score is not None and raw_score != "" else None
                result = admin_rate_answer(
                    round_obj,
                    admin_user=request.user,
                    candidate_message_id=request.data.get("candidate_message_id"),
                    score=score_val,
                    quality=(request.data.get("quality") or "").strip() or None,
                    feedback=(request.data.get("feedback") or "").strip() or None,
                    use_ai=request.data.get("use_ai", True) is not False,
                )
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)
            return Response({
                "host_state": result["host_state"],
                "score_result": result["score_result"],
                "candidate_message": InterviewMessageSerializer(result["candidate_message"]).data,
                "feedback_message": InterviewMessageSerializer(result["feedback_message"]).data,
                "rate_target": admin_rate_target(round_obj),
            })

        return Response({"error": "Unknown action"}, status=400)


class UserPendingJoinRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, round_id):
        round_obj = get_object_or_404(
            InterviewRound.objects.select_related("campaign"),
            id=round_id,
            campaign__user=request.user,
        )
        qs = round_obj.admin_join_requests.filter(status="pending")
        return Response({"requests": [_join_payload(r) for r in qs]})


class UserRespondJoinRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        req = get_object_or_404(
            InterviewAdminJoinRequest.objects.select_related("round", "round__campaign"),
            id=request_id,
            candidate_user=request.user,
            status="pending",
        )
        approve = bool(request.data.get("approve"))
        req.status = "approved" if approve else "rejected"
        req.responded_at = timezone.now()
        req.save(update_fields=["status", "responded_at"])
        if approve:
            meta = req.round.metadata or {}
            meta["admin_observer_token"] = str(req.observer_token)
            meta["admin_observer_email"] = req.admin_user.email
            req.round.metadata = meta
            req.round.save(update_fields=["metadata"])
        return Response({"request": _join_payload(req)})


def _join_payload(req: InterviewAdminJoinRequest) -> dict:
    return {
        "id": str(req.id),
        "round_id": str(req.round_id),
        "status": req.status,
        "message": req.message,
        "observer_token": str(req.observer_token) if req.status == "approved" else None,
        "admin": {"id": req.admin_user_id, "email": req.admin_user.email},
        "candidate": {"id": req.candidate_user_id, "email": req.candidate_user.email},
        "created_at": req.created_at.isoformat(),
        "responded_at": req.responded_at.isoformat() if req.responded_at else None,
        "round_title": req.round.title,
        "campaign_title": req.round.campaign.title,
    }


def _live_payload(r: InterviewRound) -> dict:
    return {
        "round_id": str(r.id),
        "title": r.title,
        "status": r.status,
        "round_type": r.round_type,
        "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "user": {"id": r.campaign.user_id, "email": r.campaign.user.email},
        "campaign_id": str(r.campaign_id),
    }
