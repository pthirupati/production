"""Interview platform settings singleton + staff auto-free."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.interviews.models import InterviewEntitlement, InterviewPlatformSettings, InterviewPlanTier


def get_platform_settings() -> InterviewPlatformSettings:
    from django.conf import settings as dj_settings

    defaults = {
        "enabled": getattr(dj_settings, "INTERVIEW_ENABLED", True),
        "staff_free_by_default": getattr(dj_settings, "INTERVIEW_STAFF_FREE_BY_DEFAULT", True),
        "free_campaigns_per_month": getattr(dj_settings, "INTERVIEW_FREE_CAMPAIGNS_PER_MONTH", 1),
        "av_grace_seconds": getattr(dj_settings, "INTERVIEW_AV_GRACE_SECONDS", 300),
        "schedule_window_hours": getattr(dj_settings, "INTERVIEW_ROUND_SCHEDULE_HOURS", 48),
        "allow_admin_observer": getattr(dj_settings, "INTERVIEW_ALLOW_ADMIN_OBSERVER", True),
        "voice_engine": getattr(dj_settings, "INTERVIEW_VOICE_ENGINE", "browser"),
    }
    row, created = InterviewPlatformSettings.objects.get_or_create(pk=1, defaults=defaults)
    if created:
        return row
    return row


def ensure_staff_entitlement(user) -> InterviewEntitlement | None:
    """Staff/superuser get free interview access when enabled in settings."""
    if not user or not user.is_authenticated:
        return None
    if not (user.is_staff or user.is_superuser):
        return None
    settings_row = get_platform_settings()
    if not settings_row.staff_free_by_default:
        return None
    premium = InterviewPlanTier.objects.filter(code="premium", is_active=True).first()
    ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
    ent.plan_tier = premium
    ent.is_active = True
    ent.is_complimentary = True
    ent.is_admin_granted_free = True
    ent.interviews_remaining = 999
    ent.period_start = timezone.now()
    ent.period_end = timezone.now() + timedelta(days=3650)
    ent.save()
    return ent


def settings_payload() -> dict:
    row = get_platform_settings()
    return {
        "enabled": row.enabled,
        "staff_free_by_default": row.staff_free_by_default,
        "free_campaigns_per_month": row.free_campaigns_per_month,
        "sample_enabled": row.sample_enabled,
        "sample_duration_minutes": row.sample_duration_minutes,
        "av_grace_seconds": row.av_grace_seconds,
        "schedule_window_hours": row.schedule_window_hours,
        "default_pass_threshold": row.default_pass_threshold,
        "allow_admin_observer": row.allow_admin_observer,
        "voice_engine": row.voice_engine,
        "pricing_managed_in_db": True,
        "uses_paid_apis": False,
    }
