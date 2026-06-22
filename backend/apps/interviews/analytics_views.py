"""Candidate + recruiter analytics endpoints (parity: progress dashboards,
candidate comparison). Reuses existing result models. 100% local — no paid API.
"""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.interviews.services.analytics import candidate_dashboard, recruiter_comparison


class CandidateAnalyticsView(APIView):
    """GET — score trend + competency radar + headline stats for the signed-in
    candidate across every interview attempt."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            return Response(candidate_dashboard(request.user))
        except Exception:  # noqa: BLE001 - analytics must never 500 the dashboard
            import logging

            logging.getLogger(__name__).exception(
                "candidate analytics failed for user %s", request.user.pk
            )
            return Response({
                "attempts": 0, "trend": [], "radar": [],
                "best_score": 0, "average_score": 0, "pass_rate": 0, "improvement": 0,
            })


class RecruiterComparisonView(APIView):
    """GET — rank/compare completed candidates for a role/template.

    Available to staff or any user who has created at least one invitation
    (a 'recruiter'). Filter by ?template_id= or ?technology_id=.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.interviews.models import InterviewInvitation

        is_recruiter = (
            request.user.is_staff
            or request.user.is_superuser
            or InterviewInvitation.objects.filter(created_by=request.user).exists()
        )
        if not is_recruiter:
            return Response(
                {"error": "Recruiter access required — invite a candidate first."},
                status=403,
            )
        template_id = request.query_params.get("template_id") or None
        technology_id = request.query_params.get("technology_id") or None
        try:
            return Response(
                recruiter_comparison(template_id=template_id, technology_id=technology_id)
            )
        except Exception:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("recruiter comparison failed")
            return Response({"count": 0, "candidates": [], "dimensions": []})
