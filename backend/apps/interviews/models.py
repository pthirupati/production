"""AI Interview Studio — multi-round voice & practical mock interviews."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class InterviewPlanTier(models.Model):
    """Subscription tiers for interview studio."""

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    price_inr = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    interviews_per_month = models.PositiveIntegerField(default=1)
    max_rounds = models.PositiveSmallIntegerField(default=3)
    voice_enabled = models.BooleanField(default=True)
    practical_enabled = models.BooleanField(default=True)
    certificate_enabled = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "price_inr"]

    def __str__(self):
        return self.name


class CandidateProfile(models.Model):
    """Resume + career inputs for personalized interviews."""

    LEVEL_CHOICES = [
        ("junior", "Junior"),
        ("mid", "Mid-level"),
        ("senior", "Senior"),
        ("lead", "Lead / Principal"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_profile",
    )
    resume_file = models.FileField(upload_to="interviews/resumes/", blank=True, null=True)
    resume_text = models.TextField(blank=True, default="")
    resume_parsed = models.JSONField(default=dict, blank=True)
    primary_technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interview_profiles_primary",
    )
    secondary_technologies = models.JSONField(default=list, blank=True)
    experience_level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default="mid")
    years_experience = models.PositiveSmallIntegerField(default=3)
    current_company = models.CharField(max_length=200, blank=True, default="")
    current_package_lpa = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    target_role = models.CharField(max_length=200, blank=True, default="")
    target_companies = models.JSONField(default=list, blank=True)
    voice_id = models.CharField(max_length=64, blank=True, default="default")
    voice_locale = models.CharField(max_length=16, blank=True, default="en-IN")
    location = models.CharField(max_length=120, blank=True, default="")
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview profile: {self.user_id}"


class InterviewCampaign(models.Model):
    """Full interview cycle (3–5 rounds)."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_campaigns",
    )
    title = models.CharField(max_length=200, blank=True, default="")
    round_count = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    profile_snapshot = models.JSONField(default=dict, blank=True)
    primary_technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    experience_level = models.CharField(max_length=16, default="mid")
    current_round_number = models.PositiveSmallIntegerField(default=1)
    overall_score = models.FloatField(null=True, blank=True)
    plan_tier = models.ForeignKey(
        InterviewPlanTier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_sample = models.BooleanField(
        default=False,
        help_text="One-time free trial interview (short duration, no certificate)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"])]

    def __str__(self):
        return f"Campaign {self.id} ({self.status})"


class InterviewRound(models.Model):
    """Single round within a campaign."""

    ROUND_TYPES = [
        ("technical", "Technical"),
        ("manager", "Techno-Manager"),
        ("hr", "HR"),
        ("deep_dive", "Deep Dive"),
        ("leadership", "Leadership"),
    ]
    STATUS_CHOICES = [
        ("locked", "Locked"),
        ("schedulable", "Schedulable"),
        ("scheduled", "Scheduled"),
        ("ready", "Ready"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("abandoned", "Abandoned"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(
        InterviewCampaign,
        on_delete=models.CASCADE,
        related_name="rounds",
    )
    round_number = models.PositiveSmallIntegerField()
    round_type = models.CharField(max_length=20, choices=ROUND_TYPES)
    title = models.CharField(max_length=200, blank=True, default="")
    duration_minutes = models.PositiveSmallIntegerField(default=45)
    extension_minutes = models.PositiveSmallIntegerField(default=0)
    max_extension_minutes = models.PositiveSmallIntegerField(default=10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="locked")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    schedule_deadline = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Must schedule next round before this time (48h after previous pass)",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    pass_threshold = models.FloatField(default=65.0)
    overall_score = models.FloatField(null=True, blank=True)
    persona_name = models.CharField(max_length=80, blank=True, default="Alex")
    persona_voice_id = models.CharField(max_length=64, blank=True, default="default")
    invite_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invite_email_sent = models.BooleanField(default=False)
    questions_asked = models.PositiveSmallIntegerField(default=0)
    strong_answers_streak = models.PositiveSmallIntegerField(default=0)
    difficulty_level = models.PositiveSmallIntegerField(default=2)
    av_compliant = models.BooleanField(default=False)
    av_warning_started_at = models.DateTimeField(null=True, blank=True)
    practical_lab_session_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["round_number"]
        unique_together = ("campaign", "round_number")

    def __str__(self):
        return f"Round {self.round_number} ({self.round_type})"


class InterviewQuestion(models.Model):
    """Curated question bank."""

    CATEGORY_CHOICES = [
        ("technical", "Technical"),
        ("behavioral", "Behavioral"),
        ("troubleshooting", "Troubleshooting"),
        ("scenario", "Scenario-based"),
        ("itil", "ITIL / Process"),
        ("sla", "SLA / Incident"),
        ("casual", "Casual / Icebreaker"),
        ("tricky", "Tricky / Edge case"),
        ("practical", "Practical / Hands-on"),
        ("system_design", "System Design"),
    ]

    slug = models.SlugField(max_length=120, unique=True)
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interview_questions",
    )
    technology_tags = models.JSONField(default=list, blank=True)
    experience_levels = models.JSONField(default=list, blank=True)
    round_types = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=24, choices=CATEGORY_CHOICES, default="technical")
    difficulty = models.PositiveSmallIntegerField(default=2)
    question_text = models.TextField()
    follow_ups = models.JSONField(default=list, blank=True)
    expected_keywords = models.JSONField(default=list, blank=True)
    practical_config = models.JSONField(default=dict, blank=True)
    discussion_prompts = models.JSONField(default=list, blank=True)
    times_asked = models.PositiveIntegerField(default=0)
    avg_score = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "difficulty"]

    def __str__(self):
        return self.slug


class InterviewMessage(models.Model):
    """Transcript entry for a round."""

    ROLE_CHOICES = [
        ("interviewer", "Interviewer"),
        ("candidate", "Candidate"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(
        InterviewRound,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    message_type = models.CharField(max_length=24, default="text")
    question = models.ForeignKey(
        InterviewQuestion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    score = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class InterviewReport(models.Model):
    """Post-round feedback."""

    round = models.OneToOneField(
        InterviewRound,
        on_delete=models.CASCADE,
        related_name="report",
    )
    passed = models.BooleanField(default=False)
    technical_score = models.FloatField(default=0)
    communication_score = models.FloatField(default=0)
    problem_solving_score = models.FloatField(default=0)
    practical_score = models.FloatField(default=0)
    presence_score = models.FloatField(default=0)
    resume_alignment_score = models.FloatField(default=0)
    overall_score = models.FloatField(default=0)
    strengths = models.JSONField(default=list, blank=True)
    improvements = models.JSONField(default=list, blank=True)
    dressing_notes = models.TextField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    study_plan = models.JSONField(default=list, blank=True)
    question_breakdown = models.JSONField(default=list, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report round {self.round_id}"


class InterviewCertificate(models.Model):
    """Issued when all rounds passed."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.OneToOneField(
        InterviewCampaign,
        on_delete=models.CASCADE,
        related_name="certificate",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_certificates",
    )
    certificate_id = models.CharField(max_length=80, unique=True)
    holder_name = models.CharField(max_length=200)
    technology_name = models.CharField(max_length=120, blank=True, default="")
    level = models.CharField(max_length=32, blank=True, default="")
    rounds_cleared = models.PositiveSmallIntegerField(default=3)
    overall_score = models.FloatField(default=0)
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    linkedin_share_text = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.certificate_id


class InterviewEntitlement(models.Model):
    """Per-user interview subscription / credits."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_entitlement",
    )
    plan_tier = models.ForeignKey(
        InterviewPlanTier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    interviews_remaining = models.PositiveIntegerField(default=0)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_complimentary = models.BooleanField(default=False)
    is_admin_granted_free = models.BooleanField(
        default=False,
        help_text="Admin granted unlimited/free interview access",
    )
    sample_interview_used = models.BooleanField(default=False)
    renewal_reminder_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Entitlement {self.user_id}"


class InterviewPlatformSettings(models.Model):
    """Singleton (pk=1) — admin controls pricing, voice, and platform flags."""

    enabled = models.BooleanField(default=True)
    staff_free_by_default = models.BooleanField(default=True)
    free_campaigns_per_month = models.PositiveSmallIntegerField(default=1)
    sample_enabled = models.BooleanField(default=True)
    sample_duration_minutes = models.PositiveSmallIntegerField(default=10)
    av_grace_seconds = models.PositiveIntegerField(default=300)
    schedule_window_hours = models.PositiveSmallIntegerField(default=48)
    default_pass_threshold = models.FloatField(default=65.0)
    allow_admin_observer = models.BooleanField(default=True)
    voice_engine = models.CharField(
        max_length=32,
        default="browser",
        help_text="browser = free Web Speech API (no paid APIs)",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Interview platform settings"
        verbose_name_plural = "Interview platform settings"

    def __str__(self):
        return "Interview platform settings"


class InterviewVoiceOption(models.Model):
    """Admin-selectable browser voices — Indian, UK, US accents (free)."""

    GENDER_CHOICES = [("female", "Female"), ("male", "Male"), ("neutral", "Neutral")]
    REGION_CHOICES = [
        ("india", "India"),
        ("uk", "United Kingdom"),
        ("us", "United States"),
        ("neutral", "Neutral"),
    ]

    code = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=120)
    locale = models.CharField(max_length=16, default="en-IN")
    gender = models.CharField(max_length=16, choices=GENDER_CHOICES, default="female")
    region = models.CharField(max_length=16, choices=REGION_CHOICES, default="india")
    browser_voice_hint = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Substring to match window.speechSynthesis voice name",
    )
    pitch = models.FloatField(default=1.0)
    rate = models.FloatField(default=0.95)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "label"]

    def __str__(self):
        return self.label


class InterviewAdminJoinRequest(models.Model):
    """Admin requests to observe a live interview; candidate must approve."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(
        InterviewRound,
        on_delete=models.CASCADE,
        related_name="admin_join_requests",
    )
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_join_requests_sent",
    )
    candidate_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_join_requests_received",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    message = models.TextField(blank=True, default="")
    observer_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
