"""Jira integration REST endpoints."""

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.question_bank.models import Scenario

from apps.billing.subscription_utils import user_has_technology_access, user_has_complimentary_access

from .models import JiraCommentLog, UserScenarioJiraTicket
from .helpers import is_jira_closed, resolve_jira_issue_url
from .sync import ensure_scenario_ticket


def _user_can_open_scenario_jira(user, scenario: Scenario) -> bool:
    """Jira incident details require the same access as starting the lab."""
    if not user or not user.is_authenticated:
        return False
    if user_has_complimentary_access(user):
        return True
    if scenario.is_free:
        return True
    if not scenario.technology_id:
        return True
    return user_has_technology_access(user, scenario.technology_id)


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
        from .simulated import use_simulated_jira

        client = JiraClient()
        live_sync = request.query_params.get("sync") == "1" and client.enabled and not use_simulated_jira()

        open_tickets = []
        closed_tickets = []
        for t in tickets_qs:
            if t.scenario is None:
                continue
            status = _sync_ticket_status(t, client) if live_sync else (t.jira_status or "")
            entry = {
                "issue_key": t.issue_key,
                "issue_url": resolve_jira_issue_url(t.issue_key, t.issue_url),
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
    from .helpers import resolve_jira_issue_url
    from .simulated import ticket_detail_payload, use_simulated_jira

    session_filter = {"session": ticket.last_session} if ticket.last_session_id else {}
    comments = (
        JiraCommentLog.objects.filter(issue_key=ticket.issue_key, **session_filter)
        .order_by("-created_at")[:10]
    )
    payload = {
        "ticket": {
            "issue_key": ticket.issue_key,
            "issue_url": resolve_jira_issue_url(ticket.issue_key, ticket.issue_url),
            "jira_status": ticket.jira_status,
            "run_count": ticket.run_count,
            "simulated": ticket.simulated or use_simulated_jira(),
            "created_at": ticket.created_at.isoformat(),
        },
        "recent_comments": [
            {"author": c.author, "text": c.text, "created_at": c.created_at.isoformat()}
            for c in comments
        ],
    }
    if include_details:
        if ticket.simulated or use_simulated_jira():
            detail = ticket_detail_payload(ticket)
            payload["ticket"]["summary"] = detail["summary"]
            payload["ticket"]["description"] = detail["description"]
            payload["ticket"]["priority"] = detail["priority"]
            payload["ticket"]["jira_status"] = detail["jira_status"]
            payload["ticket"]["allowed_transitions"] = detail["allowed_transitions"]
            payload["activity"] = detail.get("activity", [])
        elif ticket.issue_key:
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
        scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)
        if not _user_can_open_scenario_jira(request.user, scenario):
            return Response(
                {
                    "ticket": None,
                    "recent_comments": [],
                    "code": "SUBSCRIPTION_REQUIRED",
                    "error": "Subscribe to this technology to open the incident ticket.",
                },
                status=403,
            )
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
        if not _user_can_open_scenario_jira(request.user, scenario):
            return Response(
                {
                    "ticket": None,
                    "recent_comments": [],
                    "code": "SUBSCRIPTION_REQUIRED",
                    "error": "Subscribe to this technology to open the incident ticket.",
                },
                status=403,
            )
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


class JiraIssueDetailView(APIView):
    """GET /api/jira/issues/<issue_key>/ — full in-app ticket view."""

    permission_classes = [IsAuthenticated]

    def get(self, request, issue_key):
        from .simulated import get_ticket_for_user, ticket_detail_payload

        ticket = get_ticket_for_user(issue_key, request.user)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)
        return Response(ticket_detail_payload(ticket))


class JiraIssueTransitionView(APIView):
    """POST /api/jira/issues/<issue_key>/transition/ — change ticket status."""

    permission_classes = [IsAuthenticated]

    def post(self, request, issue_key):
        from .simulated import get_ticket_for_user, ticket_detail_payload, transition_ticket, use_simulated_jira

        if not use_simulated_jira():
            return Response({"error": "Status updates require Jira simulation mode"}, status=400)

        ticket = get_ticket_for_user(issue_key, request.user)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)

        new_status = (request.data.get("status") or "").strip()
        if not new_status:
            return Response({"error": "status is required"}, status=400)

        try:
            transition_ticket(ticket, request.user, new_status, session=ticket.last_session)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        ticket.refresh_from_db()
        return Response(ticket_detail_payload(ticket))


class JiraIssueCommentView(APIView):
    """POST /api/jira/issues/<issue_key>/comments/ — add a comment."""

    permission_classes = [IsAuthenticated]

    def post(self, request, issue_key):
        from .simulated import add_comment, get_ticket_for_user, ticket_detail_payload, use_simulated_jira

        if not use_simulated_jira():
            return Response({"error": "Comments require Jira simulation mode"}, status=400)

        ticket = get_ticket_for_user(issue_key, request.user)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)

        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"error": "text is required"}, status=400)

        add_comment(ticket, request.user, text, session=ticket.last_session)

        from .team_bots import parse_team_mentions, schedule_team_replies
        from .simulated import add_customer_reply, ticket_detail_payload

        teams = parse_team_mentions(text)
        team_meta = {}
        if teams:
            team_meta = schedule_team_replies(ticket, text, session=ticket.last_session)
            # Customer bot only when not a pure team-ops request
            if any(w in text.lower() for w in ("customer", "reporter", "impact", "when was")):
                add_customer_reply(ticket, text, session=ticket.last_session)
        else:
            add_customer_reply(ticket, text, session=ticket.last_session)

        payload = ticket_detail_payload(ticket)
        payload["team_reply"] = team_meta
        return Response(payload)
