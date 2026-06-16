# Generated manually for Interview Studio free platform controls

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("interviews", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="interviewentitlement",
            name="is_admin_granted_free",
            field=models.BooleanField(
                default=False,
                help_text="Admin granted unlimited/free interview access",
            ),
        ),
        migrations.CreateModel(
            name="InterviewPlatformSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                ("staff_free_by_default", models.BooleanField(default=True)),
                ("free_campaigns_per_month", models.PositiveSmallIntegerField(default=1)),
                ("av_grace_seconds", models.PositiveIntegerField(default=300)),
                ("schedule_window_hours", models.PositiveSmallIntegerField(default=48)),
                ("default_pass_threshold", models.FloatField(default=65.0)),
                ("allow_admin_observer", models.BooleanField(default=True)),
                (
                    "voice_engine",
                    models.CharField(
                        default="browser",
                        help_text="browser = free Web Speech API (no paid APIs)",
                        max_length=32,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Interview platform settings",
                "verbose_name_plural": "Interview platform settings",
            },
        ),
        migrations.CreateModel(
            name="InterviewVoiceOption",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.SlugField(max_length=64, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("locale", models.CharField(default="en-IN", max_length=16)),
                (
                    "gender",
                    models.CharField(
                        choices=[
                            ("female", "Female"),
                            ("male", "Male"),
                            ("neutral", "Neutral"),
                        ],
                        default="female",
                        max_length=16,
                    ),
                ),
                (
                    "region",
                    models.CharField(
                        choices=[
                            ("india", "India"),
                            ("uk", "United Kingdom"),
                            ("us", "United States"),
                            ("neutral", "Neutral"),
                        ],
                        default="india",
                        max_length=16,
                    ),
                ),
                (
                    "browser_voice_hint",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Substring to match window.speechSynthesis voice name",
                        max_length=120,
                    ),
                ),
                ("pitch", models.FloatField(default=1.0)),
                ("rate", models.FloatField(default=0.95)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("order", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "ordering": ["order", "label"],
            },
        ),
        migrations.CreateModel(
            name="InterviewAdminJoinRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                (
                    "observer_token",
                    models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                ("responded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admin_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_join_requests_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "candidate_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_join_requests_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="admin_join_requests",
                        to="interviews.interviewround",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
