"""Persistent platform configuration (emails, maintenance, promos)."""

from django.db import models


class PlatformSettings(models.Model):
    """Singleton row (pk=1) for admin-editable platform settings."""

    primary_email = models.EmailField(blank=True, default="")
    payment_email = models.EmailField(blank=True, default="")
    support_email = models.EmailField(blank=True, default="")
    admin_display_currency = models.CharField(max_length=3, default="INR")

    maintenance_enabled = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default="")
    maintenance_banner_image = models.URLField(blank=True, default="")
    maintenance_banner_style = models.JSONField(default=dict, blank=True)
    maintenance_scheduled_start = models.DateTimeField(null=True, blank=True)
    maintenance_scheduled_end = models.DateTimeField(null=True, blank=True)
    maintenance_notify_users = models.BooleanField(default=True)

    promo_banners = models.JSONField(default=list, blank=True)
    promo_banners_enabled = models.BooleanField(default=True)
    maintenance_banner_enabled = models.BooleanField(default=True)

    theme_colors = models.JSONField(
        default=dict,
        blank=True,
        help_text="Admin-editable accent colors: cyan, purple, amber, green, etc.",
    )
    changelog = models.JSONField(
        default=list,
        blank=True,
        help_text="Platform changelog entries shown on About page",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform settings"
        verbose_name_plural = "Platform settings"

    def __str__(self):
        return "Platform settings"
