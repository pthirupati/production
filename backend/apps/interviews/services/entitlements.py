"""Interview subscription / entitlement checks."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.interviews.models import InterviewEntitlement, InterviewPlanTier
from apps.interviews.services.interview_settings import ensure_staff_entitlement, get_platform_settings
from apps.interviews.services.sample_interview import sample_available_for_user


def ensure_interview_defaults() -> None:
    """Lazy seed for plan tiers and platform settings when DB was not seeded yet."""
    if InterviewPlanTier.objects.filter(code="free", is_active=True).exists():
        return
    try:
        from apps.interviews.management.commands.seed_interview_data import DEFAULT_TIERS
        from apps.interviews.models import InterviewPlatformSettings
        from apps.interviews.services.voice_service import _default_voices
        from apps.interviews.models import InterviewVoiceOption

        for t in DEFAULT_TIERS:
            InterviewPlanTier.objects.update_or_create(code=t["code"], defaults=t)
        InterviewPlatformSettings.objects.get_or_create(pk=1)
        for i, v in enumerate(_default_voices()):
            InterviewVoiceOption.objects.update_or_create(
                code=v["code"],
                defaults={
                    "label": v["label"],
                    "locale": v["locale"],
                    "gender": v["gender"],
                    "region": v["region"],
                    "browser_voice_hint": v["browser_voice_hint"],
                    "pitch": v["pitch"],
                    "rate": v["rate"],
                    "is_default": v["is_default"],
                    "is_active": True,
                    "order": i,
                },
            )
    except Exception:
        pass


def get_or_create_entitlement(user):
    ent, _ = InterviewEntitlement.objects.get_or_create(user=user)
    ensure_staff_entitlement(user)
    ent.refresh_from_db()
    refresh_entitlement_status(ent)
    return ent


def refresh_entitlement_status(ent: InterviewEntitlement) -> None:
    """Deactivate expired paid entitlements."""
    if not ent or ent.is_admin_granted_free or ent.is_complimentary:
        return
    if ent.period_end and ent.period_end < timezone.now() and ent.is_active:
        ent.is_active = False
        ent.interviews_remaining = 0
        ent.save(update_fields=["is_active", "interviews_remaining", "updated_at"])


def user_has_interview_access(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    ensure_interview_defaults()
    platform = get_platform_settings()
    if not platform.enabled:
        return user.is_staff or user.is_superuser
    ensure_staff_entitlement(user)
    if user.is_staff or user.is_superuser:
        return True
    ent = InterviewEntitlement.objects.filter(user=user).first()
    if not ent:
        free = InterviewPlanTier.objects.filter(code="free", is_active=True).first()
        return bool(free) or platform.free_campaigns_per_month > 0
    refresh_entitlement_status(ent)
    if ent.is_admin_granted_free or ent.is_complimentary:
        return True
    if ent.is_active:
        if ent.period_end and ent.period_end < timezone.now():
            return False
        return ent.interviews_remaining > 0
    free = InterviewPlanTier.objects.filter(code="free", is_active=True).first()
    if free:
        return True
    return platform.free_campaigns_per_month > 0


def consume_interview_credit(user) -> bool:
    """Consume one interview attempt (full campaign), not per round."""
    ensure_interview_defaults()
    ensure_staff_entitlement(user)
    if user.is_staff or user.is_superuser:
        return True
    ent = get_or_create_entitlement(user)
    refresh_entitlement_status(ent)
    if ent.is_complimentary or ent.is_admin_granted_free:
        return True
    if ent.is_active and ent.period_end and ent.period_end >= timezone.now():
        if ent.interviews_remaining > 0:
            ent.interviews_remaining -= 1
            if ent.interviews_remaining <= 0:
                ent.is_active = False
            ent.save(update_fields=["interviews_remaining", "is_active", "updated_at"])
            return True
        return False
    platform = get_platform_settings()
    limit = platform.free_campaigns_per_month
    campaigns_this_month = user.interview_campaigns.filter(
        created_at__month=timezone.now().month,
        created_at__year=timezone.now().year,
    ).exclude(status="cancelled").count()
    return campaigns_this_month < limit


def _days_remaining(ent) -> int | None:
    if not ent or not ent.period_end:
        return None
    delta = ent.period_end - timezone.now()
    return max(0, delta.days)


def _attempts_total(tier) -> int:
    if not tier:
        return 0
    if tier.code in ("pro", "premium"):
        return 10
    return int(tier.interviews_per_month or 1)


def get_entitlement_payload(user) -> dict:
    ent = get_or_create_entitlement(user)
    tier = ent.plan_tier
    if not tier:
        tier = InterviewPlanTier.objects.filter(code="free").first()
    platform = get_platform_settings()
    staff_free = (user.is_staff or user.is_superuser) and platform.staff_free_by_default
    unlimited = staff_free or ent.is_admin_granted_free or ent.is_complimentary
    attempts_total = _attempts_total(tier) if tier else 0
    expired = bool(
        ent.period_end and ent.period_end < timezone.now()
        and not unlimited
    )
    days_left = _days_remaining(ent) if ent.period_end and not unlimited else None
    remaining = 999 if unlimited else ent.interviews_remaining
    if expired:
        remaining = 0
    attempts_used = 0
    if ent.period_start and attempts_total and not unlimited:
        attempts_used = user.interview_campaigns.filter(
            created_at__gte=ent.period_start,
        ).exclude(status="cancelled").count()
        attempts_used = min(attempts_used, attempts_total)

    return {
        "is_active": user_has_interview_access(user),
        "platform_enabled": platform.enabled,
        "expired": expired,
        "subscription_expired": expired and not unlimited,
        "plan": {
            "code": "premium" if staff_free else (tier.code if tier else "free"),
            "name": "Admin (Free)" if staff_free else (tier.name if tier else "Free"),
            "max_rounds": tier.max_rounds if tier else 5,
            "voice_enabled": True,
            "practical_enabled": tier.practical_enabled if tier else True,
            "certificate_enabled": tier.certificate_enabled if tier else staff_free,
        },
        "interviews_remaining": remaining,
        "interviews_total": 999 if unlimited else attempts_total,
        "interviews_used": attempts_used if not unlimited else 0,
        "days_remaining": days_left,
        "billing_period_days": 365,
        "is_complimentary": ent.is_complimentary or staff_free,
        "is_admin_granted_free": ent.is_admin_granted_free or staff_free,
        "period_start": ent.period_start.isoformat() if ent.period_start else None,
        "period_end": ent.period_end.isoformat() if ent.period_end else None,
        "uses_paid_apis": False,
        "voice_engine": platform.voice_engine,
        "renewal_required": expired or (remaining <= 0 and not unlimited and ent.plan_tier_id),
        "is_subscribed": bool(
            ent.plan_tier_id
            and ent.plan_tier.code in ("pro", "premium")
            and ent.is_active
            and not expired
            and not unlimited
        ),
        "sample_available": sample_available_for_user(user),
        "sample_interview_used": ent.sample_interview_used,
        "sample_duration_minutes": get_platform_settings().sample_duration_minutes,
    }
