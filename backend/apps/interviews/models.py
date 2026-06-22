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
    template = models.ForeignKey(
        "interviews.InterviewTemplate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    mode = models.CharField(
        max_length=16,
        default="live",
        choices=[("live", "Live"), ("async_video", "One-way async video")],
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Soft-deleted by user from history; excluded from list view",
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
    # Parity: one-way async video mode runs ALONGSIDE the live interview. Async
    # rounds present prompts the candidate records answers to (MediaRecorder).
    mode = models.CharField(
        max_length=16,
        default="live",
        choices=[("live", "Live"), ("async_video", "One-way async video")],
    )
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
    # Parity: structured scorecard — hiring recommendation + per-competency
    # ratings + heuristic confidence/communication signals. All free/derived.
    RECOMMENDATION_CHOICES = [
        ("strong_hire", "Strong hire"),
        ("hire", "Hire"),
        ("maybe", "Maybe / lean hire"),
        ("no_hire", "No hire"),
    ]
    recommendation = models.CharField(
        max_length=16, choices=RECOMMENDATION_CHOICES, blank=True, default=""
    )
    competency_ratings = models.JSONField(
        default=list,
        blank=True,
        help_text="[{name, score, rating, note}] per-competency scorecard rows",
    )
    confidence_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text="Heuristic confidence/communication signals (filler words, pace, length)",
    )
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
    # Maintenance mode — interview feature
    maintenance_enabled = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default="")
    maintenance_scheduled_start = models.DateTimeField(null=True, blank=True)
    maintenance_scheduled_end = models.DateTimeField(null=True, blank=True)
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


class InterviewTemplate(models.Model):
    """Reusable job-role interview template / question-set (parity: TestGorilla
    job-role library, interviewai.io role templates).

    Defines the round plan, target technology/level, pass threshold, and an
    optional curated set of ``InterviewQuestion`` ids the question-set builder
    pins for this role. The live engine still GENERATES questions dynamically;
    pinned questions seed the round (and carry practical configs). 100% free.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=140, unique=True)
    name = models.CharField(max_length=160)
    role_title = models.CharField(max_length=160, blank=True, default="")
    description = models.TextField(blank=True, default="")
    primary_technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interview_templates",
    )
    technology_tags = models.JSONField(default=list, blank=True)
    experience_level = models.CharField(max_length=16, default="mid")
    round_count = models.PositiveSmallIntegerField(default=3)
    round_plan = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {round_type, duration_minutes, title} — overrides the default plan",
    )
    pass_threshold = models.FloatField(default=65.0)
    competencies = models.JSONField(
        default=list,
        blank=True,
        help_text="Named competencies this role is rated on (scorecard)",
    )
    pinned_question_ids = models.JSONField(default=list, blank=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Visible to all candidates in the template gallery",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interview_templates_created",
    )
    times_used = models.PositiveIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class InterviewInvitation(models.Model):
    """Shareable interview invitation (parity: aiinterviews.io / TestGorilla
    candidate invite links). A recruiter generates a tokenised link; the invitee
    opens it, (optionally) signs in, and takes the interview. Reuses the existing
    free email for delivery — no paid email service.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("opened", "Opened"),
        ("accepted", "Accepted"),
        ("completed", "Completed"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]
    MODE_CHOICES = [
        ("live", "Live interview"),
        ("async_video", "One-way async video"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_invitations_sent",
    )
    template = models.ForeignKey(
        InterviewTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )
    candidate_email = models.EmailField(blank=True, default="")
    candidate_name = models.CharField(max_length=160, blank=True, default="")
    role_title = models.CharField(max_length=160, blank=True, default="")
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="live")
    message = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    # Filled once the invitee starts — links the invite to the resulting work.
    campaign = models.ForeignKey(
        InterviewCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invitations",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interview_invitations_accepted",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "status"], name="iv_invite_creator_status_idx")
        ]

    def __str__(self):
        return f"Invite {self.token} ({self.status})"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at < timezone.now())


class AsyncVideoResponse(models.Model):
    """A candidate's recorded answer to one prompt in a one-way async video
    interview (parity: TestGorilla / aiinterviews.io one-way video). The browser
    MediaRecorder captures the clip; it's stored in the existing Django storage —
    no paid video service. Heuristic confidence/communication signals are derived
    from the free transcript + duration (no paid vision/NLP).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(
        InterviewRound,
        on_delete=models.CASCADE,
        related_name="async_responses",
    )
    question_index = models.PositiveSmallIntegerField(default=0)
    prompt_text = models.TextField(blank=True, default="")
    video_file = models.FileField(upload_to="interviews/async_video/", blank=True, null=True)
    transcript = models.TextField(blank=True, default="")
    duration_seconds = models.FloatField(default=0)
    score = models.FloatField(null=True, blank=True)
    analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question_index", "created_at"]
        unique_together = ("round", "question_index")

    def __str__(self):
        return f"AsyncVideo r{self.round_id} q{self.question_index}"
