from django.db import models
from django.conf import settings


class EmailLog(models.Model):
    """Track all emails sent by the system for monitoring and debugging."""
    id = models.BigAutoField(primary_key=True)
    STATUS_CHOICES = [
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    subject = models.CharField(max_length=500)
    to_email = models.EmailField()
    template = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="sent")
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"], name="notificatio_created_4c6dec_idx"),
            models.Index(fields=["status"], name="notificatio_status_18a272_idx"),
        ]

    def __str__(self):
        return f"[{self.status}] {self.subject} → {self.to_email}"


class NotificationPreference(models.Model):
    """User preferences for email and in-app notifications."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    # Email preferences
    email_achievements = models.BooleanField(default=True, help_text="Email when earning achievements")
    email_lab_completed = models.BooleanField(default=False, help_text="Email when completing a lab")
    email_lab_expired = models.BooleanField(default=False, help_text="Email when a lab session expires")
    email_subscription = models.BooleanField(default=True, help_text="Email for subscription confirmations")
    # Marketing consent must be opt-IN (audit Z4-8). This defaulted to True, which
    # is pre-ticked consent: invalid under GDPR Art.4(11)/Recital 32 and inconsistent
    # with DPDP's affirmative-action standard. The fields above stay True because
    # they are transactional — an achievement or subscription-receipt email is
    # service communication about something the user did, not marketing.
    #
    # NOTE: this changes the default for NEW rows only. Existing users are
    # deliberately left as-is; mass-flipping the installed base to False is a
    # revenue-affecting decision for the owner, not something a schema change should
    # do silently. See the data-migration note in the audit doc (Z4-8).
    email_marketing = models.BooleanField(
        default=False,
        help_text="Subscribe reminders, product tips, and benefit emails (opt-in)",
    )

    # In-app preferences
    inapp_achievements = models.BooleanField(default=True)
    inapp_lab_events = models.BooleanField(default=True)
    inapp_system = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification Preference"

    def __str__(self):
        return f"NotificationPrefs({self.user})"

    @classmethod
    def get_for_user(cls, user):
        """Get or create preferences for a user with sensible defaults."""
        prefs, _ = cls.objects.get_or_create(user=user)
        return prefs

    def should_email(self, email_type):
        """Check if user wants email for a given type."""
        mapping = {
            "achievement": self.email_achievements,
            "lab_completed": self.email_lab_completed,
            "lab_expired": self.email_lab_expired,
            "subscription": self.email_subscription,
            "marketing": self.email_marketing,
        }
        return mapping.get(email_type, True)

    def should_notify_inapp(self, notification_type):
        """Check if user wants in-app notification for a given type."""
        mapping = {
            "achievement": self.inapp_achievements,
            "lab_expired": self.inapp_lab_events,
            "system": self.inapp_system,
            "welcome": True,  # Always show welcome
            "streak": self.inapp_achievements,
        }
        return mapping.get(notification_type, True)


class Notification(models.Model):
    """In-app notification for user engagement and alerts."""

    TYPE_CHOICES = [
        ("achievement", "Achievement Unlocked"),
        ("lab_expired", "Lab Expired"),
        ("streak", "Streak Alert"),
        ("system", "System Message"),
        ("welcome", "Welcome"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=30, choices=TYPE_CHOICES, default="system")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    read = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="notificatio_user_id_05b4bc_idx"),
            models.Index(fields=["user", "read"], name="notificatio_user_id_878a13_idx"),
        ]

    def __str__(self):
        return f"{self.type}: {self.title} → {self.user}"


class MarketingEmailLog(models.Model):
    """Tracks nurture/marketing emails to enforce cadence (e.g. every 5 days)."""

    CAMPAIGN_CHOICES = [
        ("interview_sample_nudge", "Interview sample → subscribe"),
        ("technology_subscribe_nudge", "No tech subscription nudge"),
        ("combined_subscribe_nudge", "Interview + technology combined nudge"),
        ("interview_renewal_reminder", "Interview plan renewal reminder"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="marketing_emails",
    )
    campaign = models.CharField(max_length=64, choices=CAMPAIGN_CHOICES, db_index=True)
    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["user", "campaign", "-sent_at"], name="notificatio_user_id_8a1f2c_idx"),
        ]

    def __str__(self):
        return f"{self.campaign} → {self.user_id} @ {self.sent_at}"
