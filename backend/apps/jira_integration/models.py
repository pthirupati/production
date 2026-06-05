from django.conf import settings
from django.db import models


class JiraTicketLog(models.Model):
    """Audit trail for Jira ticket lifecycle per lab session."""

    ACTION_CHOICES = [
        ("created", "Created"),
        ("in_progress", "In Progress"),
        ("reset", "Reset"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
        ("comment", "Comment"),
        ("webhook", "Webhook"),
    ]

    session = models.ForeignKey(
        "labs.LabSession",
        on_delete=models.CASCADE,
        related_name="jira_logs",
    )
    issue_key = models.CharField(max_length=50)
    issue_url = models.URLField(max_length=500, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    jira_status = models.CharField(max_length=50, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["issue_key"]),
            models.Index(fields=["session", "created_at"]),
        ]

    def __str__(self):
        return f"{self.issue_key} — {self.action}"


class UserScenarioJiraTicket(models.Model):
    """Active Jira ticket for a user+scenario pair; reset on lab restart."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scenario_jira_tickets",
    )
    scenario = models.ForeignKey(
        "question_bank.Scenario",
        on_delete=models.CASCADE,
        related_name="jira_tickets",
    )
    issue_key = models.CharField(max_length=50)
    issue_url = models.URLField(max_length=500, blank=True)
    jira_status = models.CharField(max_length=50, blank=True, default="")
    last_session = models.ForeignKey(
        "labs.LabSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    run_count = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "scenario")
        indexes = [
            models.Index(fields=["issue_key"]),
        ]

    def __str__(self):
        return f"{self.user_id}/{self.scenario.slug} → {self.issue_key}"


class JiraCommentLog(models.Model):
    """Comments synced from Jira webhooks."""

    session = models.ForeignKey(
        "labs.LabSession",
        on_delete=models.CASCADE,
        related_name="jira_comments",
        null=True,
        blank=True,
    )
    issue_key = models.CharField(max_length=50, db_index=True)
    jira_comment_id = models.CharField(max_length=50, unique=True, db_index=True)
    author = models.CharField(max_length=255)
    text = models.TextField()
    created_at = models.DateTimeField()
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class JiraWebhookEvent(models.Model):
    """Raw Jira webhook payloads for debugging."""

    webhook_type = models.CharField(max_length=80, db_index=True)
    jira_issue_key = models.CharField(max_length=50, db_index=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["jira_issue_key", "processed"]),
        ]
