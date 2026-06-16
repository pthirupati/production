from django.db import models
from django.conf import settings

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("login", "Login"),
        ("login_failed", "Login Failed"),
        ("logout", "Logout"),
        ("lab_start", "Lab Start"),
        ("lab_stop", "Lab Stop"),
        ("lab_reset", "Lab Reset"),
        ("validate", "Validation"),
        ("admin_action", "Admin Action"),
        ("payment_failed", "Payment Failed"),
        ("security_alert", "Security Alert"),
        ("error", "Error"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    resource = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.user} - {self.created_at}"

