"""Certification-track models.

A *track* (e.g. RHCSA) is a weighted, ordered VIEW over scenarios that already
live in ``question_bank`` — it does not own scenario content. Objectives mirror
the vendor's published exam-domain breakdown; the ``TrackScenario`` join maps
existing scenarios into those objectives. Per-objective progress is computed
from ``apps.progress.UserScenarioProgress`` (the single source of truth for
"did this user complete scenario X"), so a track needs no progress table of its
own.

All scenario/article content referenced here is original FixitLab content; the
objective *names* are generic, published exam-domain concepts.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CertificationTrack(models.Model):
    slug = models.SlugField(max_length=120, unique=True)          # "rhcsa"
    code = models.CharField(max_length=40, unique=True)           # "RHCSA"
    name = models.CharField(max_length=200)
    vendor = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    # The technology this track primarily draws scenarios from (for branding /
    # cross-linking). Membership is the TrackScenario join, not this FK.
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cert_tracks",
    )
    exam_duration_minutes = models.PositiveIntegerField(default=180)
    passing_score = models.PositiveIntegerField(
        default=70, help_text="Percent (0-100) required to pass the timed mock exam"
    )
    validity_months = models.PositiveIntegerField(
        default=36, help_text="Months the issued certificate stays valid"
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.code


class CertObjective(models.Model):
    """One published exam-objective area within a track."""

    track = models.ForeignKey(
        CertificationTrack, on_delete=models.CASCADE, related_name="objectives"
    )
    code = models.CharField(max_length=80)        # "rhcsa.storage.lvm"
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    weight = models.PositiveIntegerField(
        default=1, help_text="Relative weight used for the overall track/exam score"
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["track", "order"]
        unique_together = ("track", "code")

    def __str__(self):
        return self.code


class TrackScenario(models.Model):
    """Maps an existing question_bank.Scenario into a track objective."""

    objective = models.ForeignKey(
        CertObjective, on_delete=models.CASCADE, related_name="track_scenarios"
    )
    scenario = models.ForeignKey(
        "question_bank.Scenario",
        on_delete=models.CASCADE,
        related_name="track_scenarios",
    )
    order = models.PositiveIntegerField(default=0)
    in_exam_pool = models.BooleanField(
        default=True, help_text="Eligible for the auto-generated timed mock exam"
    )

    class Meta:
        ordering = ["objective", "order"]
        unique_together = ("objective", "scenario")

    def __str__(self):
        return f"{self.objective.code} -> {self.scenario.slug}"


class ExamAttempt(models.Model):
    """A timed mock-exam session that scores many scenario completions at once."""

    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("submitted", "Submitted"),
        ("passed", "Passed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cert_exam_attempts",
    )
    track = models.ForeignKey(
        CertificationTrack, on_delete=models.CASCADE, related_name="exam_attempts"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="in_progress")
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0, help_text="Final percent score (0-100)")
    # {"scenarios": [{"scenario_id", "slug", "title", "objective_code", "weight",
    #                 "passed": bool, "score": int}], "objective_breakdown": {...}}
    results = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "track", "status"], name="cert_attempt_user_track_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.track.code}:{self.status}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class CertEarnedCertificate(models.Model):
    """Certificate issued for passing a track's mock exam.

    Mirrors interviews.InterviewCertificate (UUID PK + unique ``certificate_id``
    + public verify) rather than billing.UserCertificate's (user, technology)
    uniqueness, because a learner may earn a track cert across multiple attempts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cert_certificates",
    )
    track = models.ForeignKey(
        CertificationTrack, on_delete=models.CASCADE, related_name="certificates"
    )
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificate",
    )
    certificate_id = models.CharField(max_length=120, unique=True)
    holder_name = models.CharField(max_length=200)
    score = models.PositiveIntegerField(default=0)
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.certificate_id

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
