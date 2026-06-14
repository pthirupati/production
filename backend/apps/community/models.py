import uuid
from django.db import models
from django.conf import settings


class Thread(models.Model):
    """A community discussion thread."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="threads",
    )
    title = models.CharField(max_length=300)
    body = models.TextField()
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="threads",
        help_text="Optional: associate thread with a technology",
    )
    is_pinned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False, help_text="Prevent new replies")
    is_deleted = models.BooleanField(default=False, help_text="Soft delete")
    upvotes = models.PositiveIntegerField(default=0)
    reply_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["author"]),
            models.Index(fields=["technology"]),
        ]

    def __str__(self):
        return self.title


class Reply(models.Model):
    """A reply to a community thread."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="thread_replies",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text="For nested replies",
    )
    body = models.TextField()
    is_deleted = models.BooleanField(default=False)
    upvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def __str__(self):
        return f"Reply by {self.author} on {self.thread.title[:30]}"


class ThreadAttachment(models.Model):
    """Screenshot or file attached to a thread or reply."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments",
    )
    reply = models.ForeignKey(
        Reply, on_delete=models.CASCADE, null=True, blank=True, related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thread_attachments",
    )
    file = models.FileField(upload_to="community/%Y/%m/")
    original_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ReplyReaction(models.Model):
    """Emoji reaction on a reply."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reply = models.ForeignKey(Reply, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reply_reactions")
    emoji = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reply", "user", "emoji"], name="unique_reply_emoji"),
        ]


class ThreadVote(models.Model):
    """Track who voted on what (prevent duplicate votes)."""
    VOTE_CHOICES = [
        ("up", "Upvote"),
        ("down", "Downvote"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="thread_votes",
    )
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="votes",
    )
    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="votes",
    )
    vote_type = models.CharField(max_length=4, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "thread"],
                name="unique_thread_vote",
                condition=models.Q(thread__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "reply"],
                name="unique_reply_vote",
                condition=models.Q(reply__isnull=False),
            ),
        ]

    def __str__(self):
        target = self.thread or self.reply
        return f"{self.user} {self.vote_type} on {target}"


class ThreadReport(models.Model):
    """User report for moderation."""
    REASON_CHOICES = [
        ("spam", "Spam"),
        ("abuse", "Abuse or harassment"),
        ("off_topic", "Off topic"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("reviewed", "Reviewed"),
        ("dismissed", "Dismissed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="thread_reports",
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default="other")
    details = models.TextField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "reporter"],
                name="unique_thread_report_per_user",
            ),
        ]
