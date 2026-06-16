"""GDPR self-service: resume delete and transcript export."""

from __future__ import annotations

import json

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.models import CandidateProfile, InterviewCampaign, InterviewMessage


class InterviewDeleteResumeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        profile = get_object_or_404(CandidateProfile, user=request.user)
        if profile.resume_file:
            profile.resume_file.delete(save=False)
        profile.resume_file = None
        profile.resume_text = ""
        profile.resume_parsed = {}
        profile.save(update_fields=["resume_file", "resume_text", "resume_parsed", "updated_at"])
        return Response({"ok": True, "message": "Resume data removed from your profile."})


class InterviewExportTranscriptsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        fmt = request.query_params.get("format", "json")
        campaigns = InterviewCampaign.objects.filter(user=request.user).prefetch_related(
            "rounds__messages"
        ).order_by("-created_at")

        export = {
            "user_id": request.user_id,
            "exported_at": __import__("django.utils.timezone", fromlist=["timezone"]).timezone.now().isoformat(),
            "campaigns": [],
        }
        for c in campaigns:
            rounds_data = []
            for r in c.rounds.all():
                rounds_data.append({
                    "round_id": str(r.id),
                    "title": r.title,
                    "status": r.status,
                    "score": r.overall_score,
                    "messages": [
                        {
                            "role": m.role,
                            "content": m.content,
                            "score": m.score,
                            "created_at": m.created_at.isoformat(),
                        }
                        for m in r.messages.all()
                    ],
                })
            export["campaigns"].append({
                "campaign_id": str(c.id),
                "title": c.title,
                "status": c.status,
                "rounds": rounds_data,
            })

        if fmt == "download":
            response = HttpResponse(
                json.dumps(export, indent=2),
                content_type="application/json",
            )
            response["Content-Disposition"] = 'attachment; filename="fixitlab-interview-transcripts.json"'
            return response
        return Response(export)
