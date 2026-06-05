"""Jira integration REST endpoints."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import JiraCommentLog, UserScenarioJiraTicket


class UserJiraTicketsView(APIView):
    """GET /api/jira/tickets/ — user's Jira tickets across scenarios."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets = UserScenarioJiraTicket.objects.filter(user=request.user).select_related(
            "scenario", "last_session"
        )
        data = [
            {
                "issue_key": t.issue_key,
                "issue_url": t.issue_url,
                "jira_status": t.jira_status,
                "run_count": t.run_count,
                "scenario": {
                    "id": t.scenario_id,
                    "slug": t.scenario.slug,
                    "title": t.scenario.title,
                },
                "last_session_id": str(t.last_session_id) if t.last_session_id else None,
                "updated_at": t.updated_at.isoformat(),
            }
            for t in tickets
        ]
        return Response({"tickets": data, "count": len(data)})


class ScenarioJiraTicketView(APIView):
    """GET /api/jira/tickets/scenario/<scenario_id>/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, scenario_id):
        ticket = UserScenarioJiraTicket.objects.filter(
            user=request.user, scenario_id=scenario_id
        ).first()
        if not ticket:
            return Response({"ticket": None})
        comments = JiraCommentLog.objects.filter(issue_key=ticket.issue_key).order_by("-created_at")[:10]
        return Response({
            "ticket": {
                "issue_key": ticket.issue_key,
                "issue_url": ticket.issue_url,
                "jira_status": ticket.jira_status,
                "run_count": ticket.run_count,
            },
            "recent_comments": [
                {"author": c.author, "text": c.text, "created_at": c.created_at.isoformat()}
                for c in comments
            ],
        })
