"""Persistent platform configuration (emails, maintenance, promos)."""

import uuid

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

    support_bot_enabled = models.BooleanField(default=True)
    support_bot_name = models.CharField(max_length=80, blank=True, default="FixitLab Assistant")
    support_bot_welcome_message = models.TextField(blank=True, default="")
    support_bot_quick_topics = models.JSONField(default=list, blank=True)
    support_bot_custom_faq = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {"keywords": ["disk"], "answer": "..."}',
    )
    support_bot_typing_delay_ms = models.PositiveIntegerField(default=1200)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform settings"
        verbose_name_plural = "Platform settings"

    def __str__(self):
        return "Platform settings"


class BlogPost(models.Model):
    """Admin-managed blog content (replaces hardcoded Blog.jsx)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True, max_length=120)
    title = models.CharField(max_length=300)
    excerpt = models.TextField(blank=True, default="")
    content = models.TextField(help_text="Markdown or plain text body")
    author_name = models.CharField(max_length=120, blank=True, default="FixitLab Team")
    category = models.CharField(max_length=80, blank=True, default="Product")
    read_minutes = models.PositiveIntegerField(default=5)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title
