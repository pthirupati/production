"""One-time free sample interview per user (default 10 minutes)."""

from __future__ import annotations

from django.db import transaction

from apps.interviews.models import (
    CandidateProfile,
    InterviewCampaign,
    InterviewEntitlement,
    InterviewPlanTier,
    InterviewRound,
)
from apps.interviews.serializers import CandidateProfileSerializer
from apps.interviews.services.interview_settings import get_platform_settings


def sample_available_for_user(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return False
    platform = get_platform_settings()
    if not platform.enabled or not platform.sample_enabled:
        return False
    ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
    if ent.sample_interview_used:
        return False
    active = InterviewCampaign.objects.filter(user=user, is_sample=True).exclude(status="completed").first()
    if active:
        return True
    if InterviewCampaign.objects.filter(user=user, is_sample=True, status="completed").exists():
        return False
    return True


def get_or_resume_sample_campaign(user) -> InterviewCampaign | None:
    return InterviewCampaign.objects.filter(user=user, is_sample=True).prefetch_related("rounds").first()


def create_sample_campaign(user) -> InterviewCampaign:
    existing = get_or_resume_sample_campaign(user)
    if existing:
        return existing

    platform = get_platform_settings()
    if not platform.sample_enabled:
        raise ValueError("Sample interviews are disabled")

    with transaction.atomic():
        ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
        ent = InterviewEntitlement.objects.select_for_update().get(pk=ent.pk)
        if ent.sample_interview_used:
            raise ValueError("You have already used your free sample interview")

        profile, _ = CandidateProfile.objects.get_or_create(user=user)
        duration = int(platform.sample_duration_minutes or 10)
        free_tier = InterviewPlanTier.objects.filter(code="free", is_active=True).first()
        snap = CandidateProfileSerializer(profile).data
        title = f"Free sample — {profile.target_role or 'Mock Interview'}"

        campaign = InterviewCampaign.objects.create(
            user=user,
            title=title,
            round_count=1,
            status="scheduled",
            is_sample=True,
            profile_snapshot=snap,
            primary_technology=profile.primary_technology,
            experience_level=profile.experience_level,
            plan_tier=free_tier,
        )
        InterviewRound.objects.create(
            campaign=campaign,
            round_number=1,
            round_type="technical",
            title=f"Sample — {duration}-minute intro",
            duration_minutes=duration,
            max_extension_minutes=0,
            status="ready",
            persona_name="Alex Chen",
            persona_voice_id="indian-female",
            pass_threshold=50.0,
        )
    return campaign


def mark_sample_used(user) -> None:
    ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
    if not ent.sample_interview_used:
        ent.sample_interview_used = True
        ent.save(update_fields=["sample_interview_used", "updated_at"])
