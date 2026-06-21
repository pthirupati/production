"""Serialization helpers for ITSM tickets (plain dicts, matching DRF style)."""

from __future__ import annotations

from . import constants as C
from .models import ItsmTicket, ItsmWorkNote


def serialize_note(note: ItsmWorkNote) -> dict:
    return {
        "id": note.id,
        "kind": note.kind,
        "author": note.author,
        "body": note.body,
        "created_at": note.created_at.isoformat(),
    }


def serialize_ticket(ticket: ItsmTicket, *, include_notes: bool = False, include_children: bool = False) -> dict:
    data = {
        "id": str(ticket.id),
        "number": ticket.number,
        "ticket_type": ticket.ticket_type,
        "ticket_type_label": ticket.get_ticket_type_display(),
        "short_description": ticket.short_description,
        "description": ticket.description,
        "state": ticket.state,
        "state_label": ticket.get_state_display(),
        "priority": ticket.priority,
        "priority_label": ticket.get_priority_display(),
        "assignment_group": ticket.assignment_group,
        "assignment_group_label": C.team_label(ticket.assignment_group),
        "is_sub_ticket": ticket.is_sub_ticket,
        "parent_number": ticket.parent.number if ticket.parent_id else None,
        "action_kind": ticket.action_kind,
        "action_result": ticket.action_result or {},
        "close_code": ticket.close_code,
        "close_code_label": dict(C.CLOSE_CODES).get(ticket.close_code, ""),
        "allowed_transitions": ticket.allowed_transitions,
        "is_active": ticket.is_active,
        "is_closed": ticket.is_closed,
        "sla_due_at": ticket.sla_due_at.isoformat() if ticket.sla_due_at else None,
        "sla_breached": ticket.sla_breached,
        "sla_seconds_remaining": ticket.sla_seconds_remaining,
        "opened_at": ticket.opened_at.isoformat() if ticket.opened_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
    }
    if include_children:
        data["children"] = [
            serialize_ticket(c, include_notes=False, include_children=False)
            for c in ticket.children.all().order_by("opened_at")
        ]
    if include_notes:
        data["notes"] = [serialize_note(n) for n in ticket.notes.all().order_by("created_at")]
    return data


def meta_payload() -> dict:
    """Static vocabulary the UI needs to render dropdowns / labels."""
    from .engine import available_actions

    return {
        "ticket_types": [{"value": v, "label": l} for v, l in C.TICKET_TYPES],
        "states": [{"value": v, "label": l} for v, l in C.TICKET_STATES],
        "priorities": [{"value": v, "label": l} for v, l in C.PRIORITIES],
        "teams": [{"value": v, "label": l} for v, l in C.TEAMS],
        "close_codes": [{"value": v, "label": l} for v, l in C.CLOSE_CODES],
        "actions": available_actions(),
    }
