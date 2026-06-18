import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.question_bank.models import Scenario


class CommandHistory(models.Model):
    """Records every command a user types during a lab session (like SadServers)."""
    session = models.ForeignKey(
        "LabSession",
        on_delete=models.CASCADE,
        related_name="command_history",
    )
    command = models.TextField()
    output = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)
    exit_code = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["session", "timestamp"], name="labs_comman_session_bfa6ad_idx"),
        ]

    def __str__(self):
        return f"{self.session_id}: {self.command[:60]}"


class SessionRecording(models.Model):
    """Stores terminal I/O recording for session replay (asciinema-style)."""
    session = models.OneToOneField(
        "LabSession",
        on_delete=models.CASCADE,
        related_name="recording",
    )
    events = models.JSONField(
        default=list,
        help_text="List of [timestamp, type, data] events for replay",
    )
    total_duration = models.FloatField(default=0, help_text="Total duration in seconds")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Recording for {self.session_id}"


class LabSession(models.Model):
    STATUS_CHOICES = [
        ("PROVISIONING", "Provisioning"),
        ("RUNNING", "Running"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("TERMINATED", "Terminated"),
        ("EXPIRED", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lab_sessions",
    )

    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="lab_sessions",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PROVISIONING",
    )

    provider = models.CharField(
        max_length=50,
        help_text="docker | aws_ec2 | digitalocean",
        default="docker",
    )

    # Docker container info
    container_id = models.CharField(max_length=255, blank=True, null=True)
    container_name = models.CharField(max_length=255, blank=True, null=True)

    # AWS instance info
    instance_id = models.CharField(max_length=255, blank=True, null=True)
    ssh_host = models.CharField(max_length=255, blank=True)
    ssh_user = models.CharField(max_length=50, blank=True, default="root")
    ssh_key_path = models.CharField(max_length=255, blank=True)

    # Timing
    duration_limit = models.PositiveIntegerField(
        default=3600, help_text="Max duration in seconds"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Computed: started_at + duration_limit seconds.",
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    # Jira integration
    jira_issue_key = models.CharField(max_length=50, blank=True, default="")
    jira_issue_url = models.URLField(max_length=500, blank=True, default="")

    # Scoring
    score = models.PositiveIntegerField(default=0)
    hints_used = models.PositiveIntegerField(default=0)
    validation_passed = models.BooleanField(default=False)
    completion_finalized = models.BooleanField(
        default=False,
        help_text="True once scenario progress was recorded (after Jira ticket closed)",
    )

    # Multi-host labs (companion containers on same session network)
    lab_hosts = models.JSONField(
        default=list,
        blank=True,
        help_text="[{name, role, container_id, ip, ssh_user}] for SSH/SCP/NFS scenarios",
    )

    simulation_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Persisted in-memory simulation engine state for worker restarts",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Arbitrary session metadata (e.g. ai_review generated post-lab)",
    )
    extensions_used = models.PositiveSmallIntegerField(
        default=0,
        help_text="Free self-service time extensions used today (quota: 2/day)",
    )
    last_extension_date = models.DateField(
        null=True, blank=True,
        help_text="Date the last self-service extension was granted",
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="labs_labses_user_id_386172_idx"),
            models.Index(fields=["status", "started_at"], name="labs_labses_status_8decd6_idx"),
            models.Index(fields=["user", "started_at"], name="labs_labses_user_started_idx"),
            models.Index(fields=["instance_id"], name="labs_labses_instance_idx"),
            models.Index(fields=["container_id"], name="labs_labses_container_idx"),
            models.Index(fields=["status", "expires_at"], name="labs_labses_status_expires_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.started_at and self.duration_limit:
            from datetime import timedelta
            self.expires_at = self.started_at + timedelta(seconds=self.duration_limit)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.scenario.slug} ({self.status})"

    @property
    def is_expired(self):
        if self.status != "RUNNING":
            return False
        elapsed = (timezone.now() - self.started_at).total_seconds()
        return elapsed > self.duration_limit

    @property
    def time_remaining(self):
        if self.status != "RUNNING":
            return 0
        elapsed = (timezone.now() - self.started_at).total_seconds()
        remaining = self.duration_limit - elapsed
        return max(0, int(remaining))

    def mark_completed(self, score=100):
        self.status = "COMPLETED"
        self.score = score
        self.validation_passed = True
        self.ended_at = timezone.now()
        self.save()

    def mark_failed(self):
        self.status = "FAILED"
        self.ended_at = timezone.now()
        self.save()

    def mark_terminated(self):
        self.status = "TERMINATED"
        self.ended_at = timezone.now()
        self.save()

