"""ITSM REST endpoints — ServiceNow-style ticket panel for the lab runner.

All endpoints are user-scoped: a user only ever sees their own tickets. Access to
a scenario's ticket follows the same technology-subscription gate as starting the
lab (mirrors apps.jira_integration.views).
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.billing.subscription_utils import (
    user_has_complimentary_access,
    user_has_technology_access,
)
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario

from . import constants as C
from .models import ItsmTicket
from .serializers import meta_payload, serialize_note, serialize_ticket
from .services import (
    ask_assignment_group,
    ensure_scenario_ticket,
    fulfil_sub_ticket,
    raise_sub_ticket,
    scenario_itsm_config,
    transfer_ticket,
    transition_ticket,
)


def _user_can_access_scenario(user, scenario: Scenario) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user_has_complimentary_access(user):
        return True
    if scenario.is_free:
        return True
    if not scenario.technology_id:
        return True
    return user_has_technology_access(user, scenario.technology_id)


def _get_user_ticket(user, ticket_id) -> ItsmTicket | None:
    return (
        ItsmTicket.objects.select_related("parent", "scenario", "session")
        .filter(pk=ticket_id, user=user)
        .first()
    )


class ItsmMetaView(APIView):
    """GET /api/itsm/meta/ — ticket-type/state/priority/team vocabulary + actions."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(meta_payload())


class ScenarioItsmTicketView(APIView):
    """GET/POST /api/itsm/scenario/<scenario_id>/ — the parent ticket for a scenario.

    GET returns the existing ticket (or null). POST ensures it exists (opening it
    on first call), binding it to the supplied/active lab session.
    """

    permission_classes = [IsAuthenticated]

    def _resolve_session(self, request, scenario):
        session_id = request.data.get("session_id") or request.query_params.get("session_id")
        if session_id:
            return LabSession.objects.filter(pk=session_id, user=request.user).first()
        return (
            LabSession.objects.filter(user=request.user, scenario=scenario, status="RUNNING")
            .order_by("-started_at")
            .first()
        )

    def get(self, request, scenario_id):
        scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)
        if not _user_can_access_scenario(request.user, scenario):
            return Response(
                {"ticket": None, "code": "SUBSCRIPTION_REQUIRED",
                 "error": "Subscribe to this technology to open the ticket."},
                status=403,
            )
        ticket = (
            ItsmTicket.objects.filter(user=request.user, scenario_id=scenario_id, parent__isnull=True)
            .order_by("-opened_at")
            .first()
        )
        if not ticket:
            return Response({"ticket": None, "config": scenario_itsm_config(scenario)})
        return Response({
            "ticket": serialize_ticket(ticket, include_notes=True, include_children=True),
            "config": scenario_itsm_config(scenario),
        })

    def post(self, request, scenario_id):
        scenario = get_object_or_404(Scenario, pk=scenario_id, is_active=True)
        if not _user_can_access_scenario(request.user, scenario):
            return Response(
                {"ticket": None, "code": "SUBSCRIPTION_REQUIRED",
                 "error": "Subscribe to this technology to open the ticket."},
                status=403,
            )
        if not getattr(scenario, "itsm_enabled", False):
            return Response(
                {"ticket": None, "error": "This scenario does not use the ITSM ticket flow."},
                status=400,
            )
        session = self._resolve_session(request, scenario)
        ticket, created = ensure_scenario_ticket(request.user, scenario, session=session)
        return Response(
            {"ticket": serialize_ticket(ticket, include_notes=True, include_children=True),
             "created": created, "config": scenario_itsm_config(scenario)},
            status=201 if created else 200,
        )


class ItsmTicketDetailView(APIView):
    """GET /api/itsm/tickets/<id>/ — full ticket with notes + sub-tickets."""

    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        ticket = _get_user_ticket(request.user, ticket_id)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)
        return Response(serialize_ticket(ticket, include_notes=True, include_children=True))


class ItsmTransitionView(APIView):
    """POST /api/itsm/tickets/<id>/transition/ — change state (+ optional close code)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        ticket = _get_user_ticket(request.user, ticket_id)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)
        new_state = (request.data.get("state") or "").strip()
        if not new_state:
            return Response({"error": "state is required"}, status=400)
        try:
            transition_ticket(
                ticket, new_state, user=request.user,
                close_code=(request.data.get("close_code") or "").strip(),
                close_notes=(request.data.get("close_notes") or "").strip(),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        ticket.refresh_from_db()
        return Response(serialize_ticket(ticket, include_notes=True, include_children=True))


class ItsmTransferView(APIView):
    """POST /api/itsm/tickets/<id>/transfer/ — reassign to another team."""

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        ticket = _get_user_ticket(request.user, ticket_id)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)
        team = (request.data.get("team") or "").strip()
        if not team:
            return Response({"error": "team is required"}, status=400)
        try:
            transfer_ticket(ticket, team, user=request.user, reason=(request.data.get("reason") or "").strip())
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)
        ticket.refresh_from_db()
        return Response(serialize_ticket(ticket, include_notes=True, include_children=True))


class ItsmSubTicketView(APIView):
    """POST /api/itsm/tickets/<id>/sub-tickets/ — raise a child request to a team."""

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        parent = _get_user_ticket(request.user, ticket_id)
        if not parent:
            return Response({"error": "Ticket not found"}, status=404)
        if parent.is_sub_ticket:
            return Response({"error": "Cannot raise a sub-ticket from a sub-ticket."}, status=400)

        action_kind = (request.data.get("action_kind") or "").strip()
        team = (request.data.get("team") or "").strip()
        if not action_kind and not team:
            return Response({"error": "action_kind or team is required"}, status=400)

        params = request.data.get("action_params") or {}
        if not isinstance(params, dict):
            return Response({"error": "action_params must be an object"}, status=400)

        sub = raise_sub_ticket(
            parent,
            user=request.user,
            team=team,
            action_kind=action_kind,
            short_description=(request.data.get("short_description") or "").strip(),
            description=(request.data.get("description") or "").strip(),
            action_params=params,
            priority=(request.data.get("priority") or C.PRIORITY_MODERATE),
        )

        # Auto-fulfil so the cross-team workflow plays out without manual steps
        # (mirrors the simulated team picking up and completing the request).
        # Caller can pass auto_fulfil=false to leave it New for a manual fulfil.
        auto = request.data.get("auto_fulfil", True)
        if auto:
            fulfil_sub_ticket(sub)

        parent.refresh_from_db()
        sub.refresh_from_db()
        return Response(
            {"sub_ticket": serialize_ticket(sub, include_notes=True),
             "parent": serialize_ticket(parent, include_notes=True, include_children=True)},
            status=201,
        )


class ItsmFulfilView(APIView):
    """POST /api/itsm/tickets/<id>/fulfil/ — (re)run the team action for a sub-ticket.

    Lets the UI offer an explicit "let the team action this" button when a
    sub-ticket was created with auto_fulfil=false.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        sub = _get_user_ticket(request.user, ticket_id)
        if not sub:
            return Response({"error": "Ticket not found"}, status=404)
        if not sub.is_sub_ticket:
            return Response({"error": "Only sub-tickets can be fulfilled by a team."}, status=400)
        fulfil_sub_ticket(sub)
        sub.refresh_from_db()
        payload = {"sub_ticket": serialize_ticket(sub, include_notes=True)}
        if sub.parent_id:
            payload["parent"] = serialize_ticket(sub.parent, include_notes=True, include_children=True)
        return Response(payload)


class ItsmAskBotView(APIView):
    """POST /api/itsm/tickets/<id>/ask/ — ask the assignment group a question.

    Records the user's message as a comment on the ticket and posts the assigned
    team's bot reply (free intent engine, scoped to the ticket's team/scenario) to
    the same activity stream. Returns the refreshed ticket plus the two new notes.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        ticket = _get_user_ticket(request.user, ticket_id)
        if not ticket:
            return Response({"error": "Ticket not found"}, status=404)
        question = (request.data.get("message") or request.data.get("question") or "").strip()
        if not question:
            return Response({"error": "message is required"}, status=400)
        if len(question) > 2000:
            question = question[:2000]
        result = ask_assignment_group(ticket, question, user=request.user)
        ticket.refresh_from_db()
        return Response(
            {
                "comment": serialize_note(result["comment"]),
                "reply": serialize_note(result["reply"]),
                "ticket": serialize_ticket(ticket, include_notes=True, include_children=True),
            },
            status=201,
        )
