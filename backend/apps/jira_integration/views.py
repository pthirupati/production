"""Jira integration REST endpoints."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.question_bank.models import Scenario

from .models import JiraCommentLog, UserScenarioJiraTicket
from .sync import ensure_scenario_ticket


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


def _scenario_ticket_payload(ticket, include_details=False):
    comments = JiraCommentLog.objects.filter(issue_key=ticket.issue_key).order_by("-created_at")[:10]
    payload = {
        "ticket": {
            "issue_key": ticket.issue_key,
            "jira_status": ticket.jira_status,
            "run_count": ticket.run_count,
        },
        "recent_comments": [
            {"author": c.author, "text": c.text, "created_at": c.created_at.isoformat()}
            for c in comments
        ],
    }
    if include_details and ticket.issue_key:
        from .client import JiraClient, JiraClientError
        client = JiraClient()
        if client.enabled:
            try:
                details = client.get_issue_details(ticket.issue_key)
                payload["ticket"]["summary"] = details.get("summary", "")
                payload["ticket"]["description"] = details.get("description", "")
                payload["ticket"]["jira_status"] = details.get("status") or ticket.jira_status
            except JiraClientError:
                pass
    return payload


class ScenarioJiraTicketView(APIView):
    """GET/POST /api/jira/tickets/scenario/<scenario_id>/"""

    permission_classes = [IsAuthenticated]

    def get(self, request, scenario_id):
        ticket = UserScenarioJiraTicket.objects.filter(
            user=request.user, scenario_id=scenario_id
        ).first()
        if not ticket or not ticket.issue_key:
            return Response({"ticket": None, "recent_comments": []})
        return Response(_scenario_ticket_payload(ticket, include_details=True))

    def post(self, request, scenario_id):
        """Ensure a Jira ticket exists for this user+scenario (create if missing)."""
        scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)
        result = ensure_scenario_ticket(request.user, scenario)
        if not result.get("jira_enabled"):
            return Response(
                {
                    "ticket": None,
                    "recent_comments": [],
                    "jira_error": result.get("jira_error", "Jira integration disabled"),
                },
                status=200,
            )
        ticket = UserScenarioJiraTicket.objects.get(user=request.user, scenario=scenario)
        payload = _scenario_ticket_payload(ticket, include_details=True)
        payload["jira_created"] = result.get("jira_created", False)
        return Response(payload, status=201 if result.get("jira_created") else 200)
