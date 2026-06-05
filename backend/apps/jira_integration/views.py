"""Jira integration REST endpoints."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.question_bank.models import Scenario

from .models import JiraCommentLog, UserScenarioJiraTicket
from .helpers import is_jira_closed
from .sync import ensure_scenario_ticket


def _sync_ticket_status(ticket, client=None):
    """Refresh jira_status from Jira API when possible."""
    if not ticket.issue_key:
        return ticket.jira_status or ""
    if client is None:
        from .client import JiraClient
        client = JiraClient()
    if not client.enabled:
        return ticket.jira_status or ""
    try:
        status = client.get_issue_status(ticket.issue_key)
        if status and status != ticket.jira_status:
            ticket.jira_status = status
            ticket.save(update_fields=["jira_status", "updated_at"])
        return status or ticket.jira_status or ""
    except Exception:
        return ticket.jira_status or ""


class UserJiraTicketsView(APIView):
    """GET /api/jira/tickets/ — user's Jira tickets across scenarios."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        tickets_qs = UserScenarioJiraTicket.objects.filter(
            user=request.user,
            issue_key__gt="",
        ).select_related("scenario", "last_session").order_by("-updated_at")

        from .client import JiraClient
        client = JiraClient()
        live_sync = request.query_params.get("sync") == "1" and client.enabled

        open_tickets = []
        closed_tickets = []
        for t in tickets_qs:
            status = _sync_ticket_status(t, client) if live_sync else (t.jira_status or "")
            entry = {
                "issue_key": t.issue_key,
                "issue_url": t.issue_url if (request.user.is_staff or request.user.is_superuser) else "",
                "jira_status": status,
                "is_closed": is_jira_closed(status),
                "run_count": t.run_count,
                "scenario": {
                    "id": t.scenario_id,
                    "slug": t.scenario.slug,
                    "title": t.scenario.title,
                },
                "last_session_id": str(t.last_session_id) if t.last_session_id else None,
                "updated_at": t.updated_at.isoformat(),
            }
            if entry["is_closed"]:
                closed_tickets.append(entry)
            else:
                open_tickets.append(entry)

        all_tickets = open_tickets + closed_tickets
        return Response({
            "tickets": all_tickets,
            "open_tickets": open_tickets,
            "closed_tickets": closed_tickets,
            "count": len(all_tickets),
        })


def _scenario_ticket_payload(ticket, user=None, include_details=False):
    comments = JiraCommentLog.objects.filter(issue_key=ticket.issue_key).order_by("-created_at")[:10]
    show_url = user and (user.is_staff or user.is_superuser)
    payload = {
        "ticket": {
            "issue_key": ticket.issue_key,
            "issue_url": ticket.issue_url if show_url else "",
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
        include_details = request.query_params.get("details") == "1"
        return Response(_scenario_ticket_payload(ticket, user=request.user, include_details=include_details))

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
        payload = _scenario_ticket_payload(ticket, user=request.user, include_details=True)
        payload["jira_created"] = result.get("jira_created", False)
        return Response(payload, status=201 if result.get("jira_created") else 200)
