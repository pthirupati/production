"""ITSM service layer — ticket lifecycle, sub-tickets, team fulfilment.

Thin orchestration over the models + engine so views/tests share one code path.
"""

from __future__ import annotations

import random

from django.db import transaction
from django.utils import timezone

from . import constants as C
from .engine import default_team_for_action, run_team_action
from .models import ItsmTicket, ItsmWorkNote


def _gen_number(ticket_type: str) -> str:
    """ServiceNow-style number, e.g. INC0010023. Random 7 digits + uniqueness."""
    prefix = C.TYPE_PREFIX.get(ticket_type, "INC")
    for _ in range(10):
        number = f"{prefix}{random.randint(1_000_000, 9_999_999)}"
        if not ItsmTicket.objects.filter(number=number).exists():
            return number
    # Extremely unlikely fallback.
    return f"{prefix}{random.randint(10_000_000, 99_999_999)}"


def add_note(
    ticket: ItsmTicket,
    body: str,
    *,
    kind: str = ItsmWorkNote.KIND_WORK_NOTE,
    author: str = "System",
    author_user=None,
) -> ItsmWorkNote:
    return ItsmWorkNote.objects.create(
        ticket=ticket,
        kind=kind,
        author=author,
        author_user=author_user,
        body=body,
    )


@transaction.atomic
def open_ticket(
    *,
    user,
    scenario=None,
    session=None,
    ticket_type: str = C.TYPE_INCIDENT,
    short_description: str,
    description: str = "",
    priority: str = C.PRIORITY_MODERATE,
    assignment_group: str = C.TEAM_SERVICE_DESK,
    parent: ItsmTicket | None = None,
    action_kind: str = "",
    action_params: dict | None = None,
    author_user=None,
) -> ItsmTicket:
    """Create a ticket (or sub-ticket when `parent` is set) and stamp its SLA."""
    ticket = ItsmTicket.objects.create(
        number=_gen_number(ticket_type),
        ticket_type=ticket_type,
        user=user,
        scenario=scenario,
        session=session,
        parent=parent,
        short_description=short_description[:255],
        description=description or "",
        priority=priority,
        assignment_group=assignment_group,
        action_kind=action_kind or "",
        action_params=action_params or {},
        state=C.STATE_NEW,
    )
    ticket.set_sla_from_priority()
    ticket.save(update_fields=["sla_due_at"])
    add_note(
        ticket,
        f"{ticket.get_ticket_type_display()} opened and assigned to "
        f"{C.team_label(ticket.assignment_group)}.",
        kind=ItsmWorkNote.KIND_STATE,
        author=author_user.get_username() if author_user else "System",
        author_user=author_user,
    )
    return ticket


def ensure_scenario_ticket(user, scenario, session=None) -> tuple[ItsmTicket, bool]:
    """Get-or-create the parent ITSM ticket for this user+scenario.

    On a fresh lab run we (re)bind the ticket to the new session and bump the
    run_count-equivalent by re-opening if it was closed. Returns (ticket, created).
    """
    cfg = scenario_itsm_config(scenario)
    existing = (
        ItsmTicket.objects.filter(user=user, scenario=scenario, parent__isnull=True)
        .order_by("-opened_at")
        .first()
    )
    if existing:
        # Rebind to the current session so sub-ticket actions hit the right sim.
        if session and existing.session_id != session.id:
            existing.session = session
            existing.save(update_fields=["session", "updated_at"])
        return existing, False

    ticket = open_ticket(
        user=user,
        scenario=scenario,
        session=session,
        ticket_type=cfg["ticket_type"],
        short_description=cfg["short_description"],
        description=cfg["description"],
        priority=cfg["priority"],
        assignment_group=cfg["assignment_group"],
    )
    return ticket, True


def scenario_itsm_config(scenario) -> dict:
    """Resolve the ITSM config for a scenario, merging field overrides + defaults."""
    cfg = dict(getattr(scenario, "itsm_config", None) or {})
    title = getattr(scenario, "title", "") or "Issue"
    return {
        "ticket_type": cfg.get("ticket_type") or getattr(scenario, "itsm_ticket_type", "") or C.TYPE_INCIDENT,
        "short_description": cfg.get("short_description") or title,
        "description": cfg.get("description") or (getattr(scenario, "description", "") or ""),
        "priority": cfg.get("priority") or C.PRIORITY_MODERATE,
        "assignment_group": cfg.get("assignment_group") or C.TEAM_SERVICE_DESK,
        # Which sub-ticket actions this scenario expects to be available (the UI
        # always offers the full catalog, but this can highlight the intended one).
        "allowed_actions": cfg.get("allowed_actions") or [],
        "teams": cfg.get("teams") or [],
    }


@transaction.atomic
def transition_ticket(ticket: ItsmTicket, new_state: str, *, user=None, close_code: str = "", close_notes: str = "") -> ItsmTicket:
    """Move a ticket to a new state, enforcing the allowed-transition matrix."""
    if new_state == ticket.state:
        return ticket
    allowed = C.ALLOWED_TRANSITIONS.get(ticket.state, [])
    if new_state not in allowed:
        raise ValueError(
            f"Cannot move {ticket.number} from '{ticket.state}' to '{new_state}'. "
            f"Allowed: {', '.join(allowed) or 'none'}."
        )
    if new_state in (C.STATE_RESOLVED, C.STATE_CLOSED) and ticket.parent_id is None:
        # Closing the PARENT requires its sub-tickets to be done — like a real
        # change/incident you cannot close with open child requests.
        open_children = ticket.children.filter(state__in=C.ACTIVE_STATES)
        if open_children.exists():
            raise ValueError(
                f"Cannot resolve {ticket.number}: it has open sub-tickets "
                f"({', '.join(open_children.values_list('number', flat=True))})."
            )

    prev = ticket.state
    ticket.state = new_state
    now = timezone.now()
    if new_state == C.STATE_RESOLVED and not ticket.resolved_at:
        ticket.resolved_at = now
    if new_state == C.STATE_CLOSED:
        ticket.closed_at = now
        if not ticket.resolved_at:
            ticket.resolved_at = now
    if close_code:
        ticket.close_code = close_code
    if close_notes:
        ticket.close_notes = close_notes
    ticket.save()

    label_from = dict(C.TICKET_STATES).get(prev, prev)
    label_to = dict(C.TICKET_STATES).get(new_state, new_state)
    body = f"State changed: {label_from} → {label_to}."
    if close_code:
        body += f" Close code: {dict(C.CLOSE_CODES).get(close_code, close_code)}."
    add_note(
        ticket, body, kind=ItsmWorkNote.KIND_STATE,
        author=user.get_username() if user else "System", author_user=user,
    )
    return ticket


@transaction.atomic
def transfer_ticket(ticket: ItsmTicket, new_team: str, *, user=None, reason: str = "") -> ItsmTicket:
    """Reassign a ticket to a different assignment group (team transfer)."""
    if new_team not in C.TEAM_LABELS:
        raise ValueError(f"Unknown team '{new_team}'.")
    if new_team == ticket.assignment_group:
        return ticket
    prev = ticket.assignment_group
    ticket.assignment_group = new_team
    # A transfer of a New ticket implicitly moves it to In Progress for the new team.
    if ticket.state == C.STATE_NEW:
        ticket.state = C.STATE_IN_PROGRESS
    ticket.save(update_fields=["assignment_group", "state", "updated_at"])
    body = f"Transferred from {C.team_label(prev)} to {C.team_label(new_team)}."
    if reason:
        body += f" Reason: {reason}"
    add_note(
        ticket, body, kind=ItsmWorkNote.KIND_STATE,
        author=user.get_username() if user else "System", author_user=user,
    )
    return ticket


@transaction.atomic
def raise_sub_ticket(
    parent: ItsmTicket,
    *,
    user,
    team: str = "",
    action_kind: str = "",
    short_description: str = "",
    description: str = "",
    action_params: dict | None = None,
    priority: str = C.PRIORITY_MODERATE,
) -> ItsmTicket:
    """Raise a child request from a parent ticket, routed to another team.

    If `action_kind` is a known engine action, the target team defaults to that
    action's owner and a sensible short_description is filled in.
    """
    from .engine import TEAM_ACTIONS

    resolved_team = team or (default_team_for_action(action_kind) if action_kind else C.TEAM_SERVICE_DESK)
    meta = TEAM_ACTIONS.get(action_kind)
    if not short_description:
        short_description = (meta or {}).get("default_short") or "Request to assisting team"

    sub = open_ticket(
        user=user,
        scenario=parent.scenario,
        session=parent.session,
        ticket_type=C.TYPE_REQUEST,
        short_description=short_description,
        description=description,
        priority=priority,
        assignment_group=resolved_team,
        parent=parent,
        action_kind=action_kind,
        action_params=action_params or {},
        author_user=user,
    )
    add_note(
        parent,
        f"Sub-ticket {sub.number} raised to {C.team_label(resolved_team)}: {short_description}.",
        kind=ItsmWorkNote.KIND_STATE,
        author=user.get_username() if user else "System",
        author_user=user,
    )
    # The parent waits on the assisting team.
    if parent.state in (C.STATE_NEW, C.STATE_IN_PROGRESS):
        parent.state = C.STATE_ON_HOLD
        parent.save(update_fields=["state", "updated_at"])
        add_note(parent, "Parent placed On Hold pending the assisting team.", kind=ItsmWorkNote.KIND_STATE)
    return sub


@transaction.atomic
def fulfil_sub_ticket(sub: ItsmTicket) -> ItsmTicket:
    """Simulate the assigned team actioning a sub-ticket → mutate sim + resolve.

    This is the cross-team workflow's payoff: e.g. the Storage team adds the disk
    via the vmware_bridge so it becomes visible in the lab after a rescan.
    Idempotent: re-fulfilling an already-resolved sub-ticket is a no-op.
    """
    if sub.state in C.TERMINAL_STATES or sub.state == C.STATE_RESOLVED:
        return sub

    session_id = str(sub.session_id) if sub.session_id else ""
    team = C.team_label(sub.assignment_group)

    # Move to In Progress as the team picks it up.
    if sub.state == C.STATE_NEW:
        sub.state = C.STATE_IN_PROGRESS
        sub.save(update_fields=["state", "updated_at"])
        add_note(sub, f"{team} picked up the request.", kind=ItsmWorkNote.KIND_SYSTEM, author=team)

    outcome = run_team_action(sub.action_kind, session_id, sub.action_params or {})
    add_note(sub, outcome.note, kind=ItsmWorkNote.KIND_SYSTEM, author=team)
    sub.action_result = outcome.result or {}
    sub.save(update_fields=["action_result", "updated_at"])

    if outcome.resolve and outcome.ok:
        sub.state = C.STATE_RESOLVED
        sub.resolved_at = timezone.now()
        sub.close_code = "closed_complete"
        sub.save(update_fields=["state", "resolved_at", "close_code", "updated_at"])
        add_note(
            sub, "Request completed and resolved by the assisting team.",
            kind=ItsmWorkNote.KIND_STATE, author=team,
        )
        # Notify the parent and bring it back off hold.
        if sub.parent_id:
            parent = sub.parent
            if outcome.parent_note:
                add_note(parent, outcome.parent_note, kind=ItsmWorkNote.KIND_SYSTEM, author=team)
            if parent.state == C.STATE_ON_HOLD and not parent.children.filter(state__in=C.ACTIVE_STATES).exists():
                parent.state = C.STATE_IN_PROGRESS
                parent.save(update_fields=["state", "updated_at"])
                add_note(
                    parent,
                    "All assisting-team requests resolved — parent back In Progress. Continue your work.",
                    kind=ItsmWorkNote.KIND_STATE,
                )
    return sub
