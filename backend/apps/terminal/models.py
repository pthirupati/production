"""
War-Room models: collaborative incident-response rooms layered on top of the
existing single-user terminal. A WarRoomSession is keyed by a room UUID and
optionally linked to a LabSession (the incident/lab under investigation).
Participants join with an incident-response role (IC/OPS/COMMS/SCRIBE).

These models exist so team-MTTR scoring can be computed deterministically and
so the behaviour is unit-testable without a live channel layer. The
WarRoomConsumer also mirrors presence into the Channels group, but the model is
the source of truth for scoring.

Additive only — nothing here touches the terminal's single-user flow.
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class WarRoomSession(models.Model):
    STATUS_ACTIVE = "ACTIVE"
    STATUS_INVESTIGATING = "INVESTIGATING"
    STATUS_MITIGATING = "MITIGATING"
    STATUS_RESOLVED = "RESOLVED"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INVESTIGATING, "Investigating"),
        (STATUS_MITIGATING, "Mitigating"),
        (STATUS_RESOLVED, "Resolved"),
    ]

    # Non-resolved statuses a participant may broadcast via a status update.
    OPEN_STATUSES = {STATUS_ACTIVE, STATUS_INVESTIGATING, STATUS_MITIGATING}

    room_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Optional link to the incident/lab under investigation. Kept nullable so a
    # war-room can exist as a standalone drill without a provisioned lab.
    lab_session = models.ForeignKey(
        "labs.LabSession",
        on_delete=models.SET_NULL,
        related_name="war_rooms",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    # started_at marks the moment the incident clock begins (defaults to
    # creation). first_action_at is stamped on the first participant action.
    started_at = models.DateTimeField(default=timezone.now)
    first_action_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Deterministic MTTR scoring, persisted on resolve.
    time_to_first_action_seconds = models.FloatField(null=True, blank=True)
    mttr_seconds = models.FloatField(null=True, blank=True)
    team_score = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"WarRoom {self.room_key} ({self.status})"

    @property
    def is_resolved(self):
        return self.status == self.STATUS_RESOLVED and self.resolved_at is not None

    def mark_first_action(self, when=None):
        """Stamp the first-action clock exactly once. Returns True if stamped now."""
        if self.first_action_at is not None:
            return False
        self.first_action_at = when or timezone.now()
        return True

    def compute_scores(self):
        """
        Compute time-to-first-action, MTTR, and a simple team score.

        Deterministic and offline. Values are derived purely from the timestamps
        already on the row, so re-running yields the same result.

          - time_to_first_action = first_action_at - started_at
          - mttr                 = resolved_at    - started_at
          - team_score           = base 100, decaying with MTTR, with a small
                                    bonus for a fast first action. Clamped 0..100.
        """
        if self.resolved_at is None or self.started_at is None:
            return None

        mttr = max(0.0, (self.resolved_at - self.started_at).total_seconds())
        self.mttr_seconds = mttr

        if self.first_action_at is not None:
            ttfa = max(0.0, (self.first_action_at - self.started_at).total_seconds())
        else:
            # No recorded action before resolve — treat first action as resolve.
            ttfa = mttr
        self.time_to_first_action_seconds = ttfa

        # Score: full marks for a sub-5-minute resolution, losing 1 point per
        # 30 s beyond that, with up to a 10-point bonus for acting within 60 s.
        base = 100.0
        over = max(0.0, mttr - 300.0)
        base -= over / 30.0
        if ttfa <= 60.0:
            base += 10.0 * (1.0 - ttfa / 60.0)
        self.team_score = int(max(0, min(100, round(base))))
        return self.team_score

    def resolve(self, when=None):
        """Mark resolved, stamp resolved_at, and compute + return the team score."""
        self.resolved_at = when or timezone.now()
        self.status = self.STATUS_RESOLVED
        return self.compute_scores()


class WarRoomParticipant(models.Model):
    ROLE_IC = "IC"
    ROLE_OPS = "OPS"
    ROLE_COMMS = "COMMS"
    ROLE_SCRIBE = "SCRIBE"

    ROLE_CHOICES = [
        (ROLE_IC, "Incident Commander"),
        (ROLE_OPS, "Ops"),
        (ROLE_COMMS, "Comms"),
        (ROLE_SCRIBE, "Scribe"),
    ]

    VALID_ROLES = {ROLE_IC, ROLE_OPS, ROLE_COMMS, ROLE_SCRIBE}

    room = models.ForeignKey(
        WarRoomSession,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="war_room_participations",
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_OPS,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # One membership row per (room, user); rejoining updates the role.
        unique_together = [("room", "user")]

    def __str__(self):
        return f"{self.user_id} as {self.role} in {self.room.room_key}"
