"""Candidate invitation endpoints (parity: shareable interview links).

Recruiter: create / list / revoke invitations (free email delivery).
Public: look up an invitation by token; the invitee accepts (auth required) and
gets an interview provisioned. No paid email/video service.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.models import InterviewInvitation, InterviewTemplate
from apps.interviews.serializers import (
    InterviewCampaignDetailSerializer,
    InterviewInvitationSerializer,
)
from apps.interviews.services.invitations import (
    accept_invitation,
    create_invitation,
    mark_opened,
    send_invitation_email,
)
from common.throttles import StrictAnonRateThrottle


class InvitationListCreateView(APIView):
    """GET — invitations the signed-in recruiter created.
    POST — create + (optionally) email a new invitation. Any authenticated user
    may act as a recruiter (generate a shareable link)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = InterviewInvitation.objects.filter(created_by=request.user).select_related("template")
        return Response({"invitations": InterviewInvitationSerializer(qs, many=True).data})

    def post(self, request):
        template = None
        template_id = request.data.get("template")
        if template_id:
            template = InterviewTemplate.objects.filter(id=template_id, is_active=True).first()
        inv = create_invitation(
            created_by=request.user,
            template=template,
            candidate_email=request.data.get("candidate_email", ""),
            candidate_name=request.data.get("candidate_name", ""),
            role_title=request.data.get("role_title", ""),
            mode=request.data.get("mode", "live"),
            message=request.data.get("message", ""),
            expires_in_days=int(request.data.get("expires_in_days", 14) or 14),
        )
        if inv.candidate_email and request.data.get("send_email", True):
            send_invitation_email(inv)
        return Response(InterviewInvitationSerializer(inv).data, status=201)


class InvitationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, invitation_id):
        inv = get_object_or_404(InterviewInvitation, id=invitation_id, created_by=request.user)
        inv.status = "revoked"
        inv.save(update_fields=["status"])
        return Response({"status": "revoked"})


class PublicInvitationView(APIView):
    """GET — public preview of an invitation by token (no auth). The invitee
    sees the role/mode before signing in to accept."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def get(self, request, token):
        inv = InterviewInvitation.objects.filter(token=token).select_related("template").first()
        if not inv:
            return Response({"valid": False, "error": "Invitation not found"}, status=404)
        if inv.status == "revoked":
            return Response({"valid": False, "error": "This invitation was revoked"})
        if inv.is_expired:
            return Response({"valid": False, "error": "This invitation has expired"})
        mark_opened(inv)
        return Response({
            "valid": True,
            "role_title": inv.role_title or (inv.template.name if inv.template else "Interview"),
            "candidate_name": inv.candidate_name,
            "mode": inv.mode,
            "message": inv.message,
            "template_name": inv.template.name if inv.template else "",
            "round_count": inv.template.round_count if inv.template else 3,
            "status": inv.status,
            "already_accepted": bool(inv.campaign_id),
        })


class AcceptInvitationView(APIView):
    """POST — the signed-in invitee accepts; an interview campaign is provisioned."""

    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        inv = InterviewInvitation.objects.filter(token=token).select_related("template").first()
        if not inv:
            return Response({"error": "Invitation not found"}, status=404)
        if inv.status == "revoked":
            return Response({"error": "This invitation was revoked"}, status=400)
        if inv.is_expired:
            return Response({"error": "This invitation has expired"}, status=400)
        # An invitee who already accepted is taken straight to their campaign.
        if inv.campaign_id and inv.accepted_by_id and inv.accepted_by_id != request.user.id:
            return Response({"error": "This invitation was already used by another account"}, status=403)
        campaign = accept_invitation(inv, request.user)
        return Response(
            InterviewCampaignDetailSerializer(campaign).data,
            status=201,
        )
