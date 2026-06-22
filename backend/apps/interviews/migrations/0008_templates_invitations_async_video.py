import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("question_bank", "0010_alter_scenario_simulation_type"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("interviews", "0007_campaign_is_archived_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="InterviewTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("role_title", models.CharField(blank=True, default="", max_length=160)),
                ("description", models.TextField(blank=True, default="")),
                ("technology_tags", models.JSONField(blank=True, default=list)),
                ("experience_level", models.CharField(default="mid", max_length=16)),
                ("round_count", models.PositiveSmallIntegerField(default=3)),
                (
                    "round_plan",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="List of {round_type, duration_minutes, title} — overrides the default plan",
                    ),
                ),
                ("pass_threshold", models.FloatField(default=65.0)),
                (
                    "competencies",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Named competencies this role is rated on (scorecard)",
                    ),
                ),
                ("pinned_question_ids", models.JSONField(blank=True, default=list)),
                (
                    "is_public",
                    models.BooleanField(
                        default=True, help_text="Visible to all candidates in the template gallery"
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("times_used", models.PositiveIntegerField(default=0)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="interview_templates_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "primary_technology",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="interview_templates",
                        to="question_bank.technology",
                    ),
                ),
            ],
            options={"ordering": ["order", "name"]},
        ),
        migrations.AddField(
            model_name="interviewcampaign",
            name="mode",
            field=models.CharField(
                choices=[("live", "Live"), ("async_video", "One-way async video")],
                default="live",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="interviewcampaign",
            name="template",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="campaigns",
                to="interviews.interviewtemplate",
            ),
        ),
        migrations.AddField(
            model_name="interviewround",
            name="mode",
            field=models.CharField(
                choices=[("live", "Live"), ("async_video", "One-way async video")],
                default="live",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="interviewreport",
            name="recommendation",
            field=models.CharField(
                blank=True,
                choices=[
                    ("strong_hire", "Strong hire"),
                    ("hire", "Hire"),
                    ("maybe", "Maybe / lean hire"),
                    ("no_hire", "No hire"),
                ],
                default="",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="interviewreport",
            name="competency_ratings",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="[{name, score, rating, note}] per-competency scorecard rows",
            ),
        ),
        migrations.AddField(
            model_name="interviewreport",
            name="confidence_analysis",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Heuristic confidence/communication signals (filler words, pace, length)",
            ),
        ),
        migrations.CreateModel(
            name="InterviewInvitation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("token", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("candidate_email", models.EmailField(blank=True, default="", max_length=254)),
                ("candidate_name", models.CharField(blank=True, default="", max_length=160)),
                ("role_title", models.CharField(blank=True, default="", max_length=160)),
                (
                    "mode",
                    models.CharField(
                        choices=[("live", "Live interview"), ("async_video", "One-way async video")],
                        default="live",
                        max_length=16,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("opened", "Opened"),
                            ("accepted", "Accepted"),
                            ("completed", "Completed"),
                            ("expired", "Expired"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("opened_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("email_sent", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "accepted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="interview_invitations_accepted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invitations",
                        to="interviews.interviewcampaign",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="interview_invitations_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invitations",
                        to="interviews.interviewtemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["created_by", "status"], name="iv_invite_creator_status_idx")
                ],
            },
        ),
        migrations.CreateModel(
            name="AsyncVideoResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("question_index", models.PositiveSmallIntegerField(default=0)),
                ("prompt_text", models.TextField(blank=True, default="")),
                (
                    "video_file",
                    models.FileField(blank=True, null=True, upload_to="interviews/async_video/"),
                ),
                ("transcript", models.TextField(blank=True, default="")),
                ("duration_seconds", models.FloatField(default=0)),
                ("score", models.FloatField(blank=True, null=True)),
                ("analysis", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "round",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="async_responses",
                        to="interviews.interviewround",
                    ),
                ),
            ],
            options={
                "ordering": ["question_index", "created_at"],
                "unique_together": {("round", "question_index")},
            },
        ),
    ]
