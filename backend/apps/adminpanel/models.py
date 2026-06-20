"""Persistent platform configuration (emails, maintenance, promos)."""

import uuid

from django.conf import settings
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


class Campaign(models.Model):
    """In-platform marketing banner / announcement / offer.

    Admins create these to promote current or upcoming features. A campaign
    renders as a banner (top bar, modal, dashboard card or pricing strip) once
    enabled and inside its optional schedule window. The same model also backs
    plain "announcements" and "offers" via the ``kind`` field.
    """

    KIND_CHOICES = [
        ("campaign", "Campaign"),
        ("announcement", "Announcement"),
        ("offer", "Offer"),
    ]
    MEDIA_CHOICES = [
        ("none", "None"),
        ("image", "Image"),
        ("video", "Video"),
    ]
    PLACEMENT_CHOICES = [
        ("banner_top", "Top banner"),
        ("modal", "Modal"),
        ("dashboard", "Dashboard card"),
        ("pricing", "Pricing strip"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("enabled", "Enabled"),
        ("cancelled", "Cancelled"),
    ]
    AUDIENCE_CHOICES = [
        ("all", "Everyone"),
        ("free", "Free users"),
        ("paid", "Paid users"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="campaign")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="", help_text="Rich text / markdown body")

    media_type = models.CharField(max_length=10, choices=MEDIA_CHOICES, default="none")
    media_url = models.URLField(blank=True, default="")

    placement = models.CharField(max_length=20, choices=PLACEMENT_CHOICES, default="banner_top")

    bg_color = models.CharField(max_length=120, blank=True, default="", help_text="CSS color or gradient")
    text_color = models.CharField(max_length=40, blank=True, default="")
    text_style = models.JSONField(
        default=dict,
        blank=True,
        help_text='Text style overrides: {"font_size": "15px", "font_weight": 600, "text_align": "left"}',
    )

    cta_label = models.CharField(max_length=80, blank=True, default="")
    cta_url = models.CharField(max_length=500, blank=True, default="")

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    audience = models.CharField(max_length=8, choices=AUDIENCE_CHOICES, default="all")

    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    dismissible = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "placement"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()}: {self.title}"

    def is_live(self, now=None):
        """True when enabled and inside the optional schedule window."""
        from django.utils import timezone as _tz

        if self.status != "enabled":
            return False
        now = now or _tz.now()
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at < now:
            return False
        return True


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
