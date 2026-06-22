"""Interview template (job-role library) endpoints.

Candidate-facing: browse public templates + launch an interview from one.
Admin/recruiter: full CRUD + a question-set builder (pin curated questions).
Reuses the existing free engine — templates only configure it. No paid API.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.models import (
    CandidateProfile,
    InterviewCampaign,
    InterviewTemplate,
)
from apps.interviews.serializers import (
    CandidateProfileSerializer,
    InterviewCampaignDetailSerializer,
    InterviewTemplateSerializer,
)
from apps.interviews.services.entitlements import consume_interview_credit, user_has_interview_access


class InterviewTemplateListView(APIView):
    """GET — public/active template gallery for candidates.
    POST — create a template (staff or a recruiter who has sent invitations)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.interviews.services.templates import ensure_default_templates

        ensure_default_templates()
        qs = InterviewTemplate.objects.filter(is_active=True, is_public=True)
        return Response({"templates": InterviewTemplateSerializer(qs, many=True).data})

    def post(self, request):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Admin access required to create templates"}, status=403)
        data = dict(request.data)
        if not data.get("slug") and data.get("name"):
            data["slug"] = slugify(data["name"])[:140]
        ser = InterviewTemplateSerializer(data=data)
        ser.is_valid(raise_exception=True)
        tmpl = ser.save(created_by=request.user)
        return Response(InterviewTemplateSerializer(tmpl).data, status=201)


class InterviewTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, template_id):
        tmpl = get_object_or_404(InterviewTemplate, id=template_id, is_active=True)
        return Response(InterviewTemplateSerializer(tmpl).data)

    def put(self, request, template_id):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Admin access required"}, status=403)
        tmpl = get_object_or_404(InterviewTemplate, id=template_id)
        ser = InterviewTemplateSerializer(tmpl, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, template_id):
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({"error": "Admin access required"}, status=403)
        InterviewTemplate.objects.filter(id=template_id).update(is_active=False)
        return Response(status=204)


class InterviewTemplateLaunchView(APIView):
    """POST — start an interview campaign from a template (one click).

    Honours the candidate's entitlement/credits exactly like the normal campaign
    create flow, then builds the rounds from the template configuration.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, template_id):
        tmpl = get_object_or_404(InterviewTemplate, id=template_id, is_active=True)
        if not user_has_interview_access(request.user):
            return Response(
                {"error": "Interview subscription required", "code": "SUBSCRIPTION_REQUIRED"},
                status=403,
            )
        if not consume_interview_credit(request.user):
            return Response({"error": "No interview credits remaining this period"}, status=403)

        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        snap = CandidateProfileSerializer(profile).data
        snap.setdefault("target_role", tmpl.role_title)
        if not snap.get("experience_level"):
            snap["experience_level"] = tmpl.experience_level
        if tmpl.primary_technology_id and not snap.get("primary_technology_name"):
            snap["primary_technology_name"] = tmpl.primary_technology.name

        mode = request.data.get("mode", "live")
        mode = mode if mode in ("live", "async_video") else "live"

        campaign = InterviewCampaign.objects.create(
            user=request.user,
            title=tmpl.name,
            round_count=tmpl.round_count,
            status="scheduled",
            profile_snapshot=snap,
            primary_technology=tmpl.primary_technology,
            experience_level=tmpl.experience_level,
            template=tmpl,
            mode=mode,
        )
        from apps.interviews.services.templates import create_rounds_from_template

        create_rounds_from_template(campaign, tmpl)
        return Response(
            InterviewCampaignDetailSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )
