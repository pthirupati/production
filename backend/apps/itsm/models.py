"""ServiceNow-style ITSM ticket model for scenario labs.

A scenario can declare it uses the ITSM flow (Scenario.itsm_enabled). When a lab
starts, an `ItsmTicket` (Incident by default) is opened for the user+scenario,
assigned to the configured team. From the parent ticket the user can raise
*sub-tickets* (children) to other teams — e.g. "Storage team: add a 50GB disk".
A simulated team then actions the sub-ticket; for the disk case that mutation
hot-adds a disk via the existing vmware_bridge so it appears in the lab terminal
after a SCSI rescan. See apps.itsm.engine.

These are real DB rows (unlike the Jira simulated tickets which live partly in
cache) because tickets persist across lab restarts (run_count) and sub-tickets
form a parent/child tree we query.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from . import constants as C


class ItsmTicket(models.Model):
    """An Incident / Service Request / Change / Problem record.

    Parent tickets have parent=None. Sub-tickets (child requests routed to another
    team) point at their parent and usually carry an `action_kind` the engine knows
    how to fulfil (e.g. "add_disk").
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    number = models.CharField(
        max_length=20, unique=True, db_index=True,
        help_text="ServiceNow-style record number, e.g. INC0010023 / RITM0010024",
    )
    ticket_type = models.CharField(max_length=20, choices=C.TICKET_TYPES, default=C.TYPE_INCIDENT)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="itsm_tickets",
    )
    scenario = models.ForeignKey(
        "question_bank.Scenario", on_delete=models.CASCADE, related_name="itsm_tickets",
        null=True, blank=True,
    )
    # The lab session this ticket is bound to. Sub-ticket team actions mutate the
    # simulation for THIS session (the disk appears on that session's server).
    session = models.ForeignKey(
        "labs.LabSession", on_delete=models.SET_NULL, related_name="itsm_tickets",
        null=True, blank=True,
    )

    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="children",
        null=True, blank=True,
        help_text="Set on a sub-ticket; the parent ticket it was raised from.",
    )

    short_description = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")

    state = models.CharField(max_length=20, choices=C.TICKET_STATES, default=C.STATE_NEW)
    priority = models.CharField(max_length=2, choices=C.PRIORITIES, default=C.PRIORITY_MODERATE)
    assignment_group = models.CharField(
        max_length=30, choices=C.TEAMS, default=C.TEAM_SERVICE_DESK,
        help_text="The team / assignment group that owns this ticket.",
    )

    # For sub-tickets: which team-action the engine should run when this child is
    # actioned (e.g. add_disk / add_nic / restore_file). Blank for plain tickets.
    action_kind = models.CharField(max_length=40, blank=True, default="")
    # Free-form params for the action (e.g. {"size_gb": 50}). Result of the action
    # (e.g. the /dev path the disk will appear as) is stored back here too.
    action_params = models.JSONField(default=dict, blank=True)
    action_result = models.JSONField(default=dict, blank=True)

    close_code = models.CharField(max_length=40, blank=True, default="", choices=C.CLOSE_CODES)
    close_notes = models.TextField(blank=True, default="")

    # SLA — target derived from priority at open time; breach computed live.
    sla_due_at = models.DateTimeField(null=True, blank=True)

    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        indexes = [
            models.Index(fields=["user", "scenario"], name="itsm_user_scenario_idx"),
            models.Index(fields=["parent"], name="itsm_parent_idx"),
            models.Index(fields=["session", "state"], name="itsm_session_state_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.number} — {self.short_description[:50]}"

    # ── Derived helpers ──
    @property
    def is_sub_ticket(self) -> bool:
        return self.parent_id is not None

    @property
    def is_active(self) -> bool:
        return self.state in C.ACTIVE_STATES

    @property
    def is_closed(self) -> bool:
        return self.state in C.TERMINAL_STATES

    @property
    def allowed_transitions(self) -> list[str]:
        return list(C.ALLOWED_TRANSITIONS.get(self.state, []))

    @property
    def sla_breached(self) -> bool:
        if not self.sla_due_at or self.state in C.TERMINAL_STATES:
            return False
        return timezone.now() > self.sla_due_at

    @property
    def sla_seconds_remaining(self) -> int | None:
        if not self.sla_due_at:
            return None
        delta = (self.sla_due_at - timezone.now()).total_seconds()
        return int(delta)

    def set_sla_from_priority(self) -> None:
        minutes = C.SLA_MINUTES.get(self.priority, C.SLA_MINUTES[C.PRIORITY_MODERATE])
        base = self.opened_at or timezone.now()
        self.sla_due_at = base + timezone.timedelta(minutes=minutes)


class ItsmWorkNote(models.Model):
    """An entry in a ticket's activity stream — work notes, state changes, system
    (team-bot) messages, comments. Modeled on the ServiceNow journal field."""

    KIND_WORK_NOTE = "work_note"      # internal work note (operator)
    KIND_COMMENT = "comment"          # customer-visible comment
    KIND_STATE = "state_change"       # automatic state-change record
    KIND_SYSTEM = "system"            # team bot / fulfilment message
    KIND_CHOICES = [
        (KIND_WORK_NOTE, "Work Note"),
        (KIND_COMMENT, "Additional Comment"),
        (KIND_STATE, "State Change"),
        (KIND_SYSTEM, "System"),
    ]

    ticket = models.ForeignKey(ItsmTicket, on_delete=models.CASCADE, related_name="notes")
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_WORK_NOTE)
    author = models.CharField(max_length=120, default="System")
    # Null author_user = a simulated bot/team; set when a real user wrote it.
    author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["ticket", "created_at"], name="itsm_note_ticket_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket.number} [{self.kind}] {self.body[:40]}"
