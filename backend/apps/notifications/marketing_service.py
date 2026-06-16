"""Marketing nurture emails — sample interview & technology subscribe reminders."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()

INTERVIEW_BENEFITS = [
    "10 full interview attempts per year — each with 3–5 voice rounds",
    "Resume-aware technical, manager, and HR panels",
    "Hands-on troubleshooting labs inside interviews",
    "Verifiable FIXIT-INT certificates for LinkedIn",
    "Detailed score reports and study plans after every round",
]

TECH_BENEFITS = [
    "1 year access to every scenario in your chosen technology",
    "Real terminal labs — break-fix environments, not slides",
    "Hints, leaderboards, and completion certificates",
    "New scenarios added regularly from production incidents",
    "Community threads and Jira-style practice tickets",
]


def _nudge_interval() -> timedelta:
    days = int(getattr(settings, "MARKETING_NUDGE_INTERVAL_DAYS", 5))
    return timedelta(days=max(1, days))


def _marketing_enabled() -> bool:
    return bool(getattr(settings, "MARKETING_EMAILS_ENABLED", True))


def _last_nudge(user, campaign: str):
    from .models import MarketingEmailLog

    return (
        MarketingEmailLog.objects.filter(user=user, campaign=campaign)
        .order_by("-sent_at")
        .first()
    )


def _cadence_allows(user, campaign: str, anchor=None) -> bool:
    """True if enough time passed since last send (or since anchor for first send)."""
    interval = _nudge_interval()
    last = _last_nudge(user, campaign)
    if last:
        return timezone.now() - last.sent_at >= interval
    if anchor:
        return timezone.now() - anchor >= interval
    return True


def has_paid_interview_subscription(user) -> bool:
    from apps.interviews.models import InterviewEntitlement

    ent = InterviewEntitlement.objects.filter(user=user).first()
    if not ent:
        return False
    if ent.is_complimentary or ent.is_admin_granted_free:
        return True
    if not ent.is_active or not ent.plan_tier:
        return False
    if ent.plan_tier.code not in ("pro", "premium"):
        return False
    if ent.period_end and ent.period_end <= timezone.now():
        return False
    return True


def has_active_technology_subscription(user) -> bool:
    from apps.billing.models import TechnologySubscription
    from apps.billing.subscription_utils import is_tech_subscription_active, user_has_complimentary_access

    if user_has_complimentary_access(user):
        return True
    for sub in TechnologySubscription.objects.filter(user=user).select_related("technology"):
        if is_tech_subscription_active(sub):
            return True
    return False


def _latest_completed_sample(user):
    from apps.interviews.models import InterviewCampaign

    return (
        InterviewCampaign.objects.filter(user=user, is_sample=True, status="completed")
        .order_by("-completed_at")
        .first()
    )


def eligible_interview_sample_base(user) -> bool:
    if not _marketing_enabled() or not user.is_active or user.is_staff:
        return False
    if has_paid_interview_subscription(user):
        return False
    sample = _latest_completed_sample(user)
    return bool(sample and sample.completed_at)


def eligible_technology_subscribe_base(user) -> bool:
    if not _marketing_enabled() or not user.is_active or user.is_staff:
        return False
    if not user.last_login:
        return False
    if has_active_technology_subscription(user):
        return False
    min_age = timedelta(days=int(getattr(settings, "MARKETING_MIN_ACCOUNT_AGE_DAYS", 3)))
    if user.date_joined and timezone.now() - user.date_joined < min_age:
        return False
    stale_days = int(getattr(settings, "MARKETING_INACTIVE_LOGIN_DAYS", 120))
    if user.last_login and timezone.now() - user.last_login > timedelta(days=stale_days):
        return False
    return True


def eligible_interview_sample_nudge(user) -> bool:
    sample = _latest_completed_sample(user)
    if not sample or not eligible_interview_sample_base(user):
        return False
    return _cadence_allows(user, "interview_sample_nudge", anchor=sample.completed_at)


def eligible_technology_subscribe_nudge(user) -> bool:
    if not eligible_technology_subscribe_base(user):
        return False
    return _cadence_allows(user, "technology_subscribe_nudge", anchor=user.date_joined)


def eligible_combined_subscribe_nudge(user) -> bool:
    if not eligible_interview_sample_base(user) or not eligible_technology_subscribe_base(user):
        return False
    sample = _latest_completed_sample(user)
    min_age = timedelta(days=int(getattr(settings, "MARKETING_MIN_ACCOUNT_AGE_DAYS", 3)))
    anchor = sample.completed_at
    account_ready = user.date_joined + min_age
    if account_ready > anchor:
        anchor = account_ready
    return _cadence_allows(user, "combined_subscribe_nudge", anchor=anchor)


def _featured_technologies(limit: int = 4) -> list[dict]:
    from apps.question_bank.models import Technology

    techs = Technology.objects.filter(is_active=True, coming_soon=False).order_by("order", "name")[:limit]
    return [
        {
            "name": t.name,
            "slug": t.slug,
            "price": int(t.price or 0),
            "url": f"{settings.FRONTEND_URL}/technologies/{t.slug}",
        }
        for t in techs
    ]


def send_interview_sample_nudge(user) -> bool:
    from .email_helpers import queue_user_email
    from .models import MarketingEmailLog

    if not eligible_interview_sample_nudge(user):
        return False

    name = user.get_full_name() or user.username
    ok = queue_user_email(
        user,
        subject="Ready for the full mock interview experience?",
        template="emails/marketing_interview_subscribe.html",
        context={
            "username": name,
            "pricing_url": f"{settings.FRONTEND_URL}/interviews#interview-plans",
            "interviews_url": f"{settings.FRONTEND_URL}/interviews",
            "subscriptions_url": f"{settings.FRONTEND_URL}/subscriptions",
            "benefits": INTERVIEW_BENEFITS,
        },
        email_type="marketing",
    )
    if ok:
        MarketingEmailLog.objects.create(user=user, campaign="interview_sample_nudge")
        _inapp_nudge(
            user,
            "Unlock full mock interviews",
            "Subscribe for 10 attempts/year, multi-round voice panels, and certificates.",
            f"{settings.FRONTEND_URL}/interviews#interview-plans",
        )
    return ok


def send_technology_subscribe_nudge(user) -> bool:
    from .email_helpers import queue_user_email
    from .models import MarketingEmailLog

    if not eligible_technology_subscribe_nudge(user):
        return False

    techs = _featured_technologies()
    name = user.get_full_name() or user.username
    ok = queue_user_email(
        user,
        subject="Unlock hands-on labs — subscribe to a technology",
        template="emails/marketing_technology_subscribe.html",
        context={
            "username": name,
            "pricing_url": f"{settings.FRONTEND_URL}/pricing",
            "technologies_url": f"{settings.FRONTEND_URL}/technologies",
            "dashboard_url": f"{settings.FRONTEND_URL}/dashboard",
            "featured_technologies": techs,
            "benefits": TECH_BENEFITS,
        },
        email_type="marketing",
    )
    if ok:
        MarketingEmailLog.objects.create(user=user, campaign="technology_subscribe_nudge")
        _inapp_nudge(
            user,
            "Subscribe to a technology",
            "Get 1-year access to all scenarios, labs, and certificates.",
            f"{settings.FRONTEND_URL}/pricing",
        )
    return ok


def send_combined_subscribe_nudge(user) -> bool:
    from .email_helpers import queue_user_email
    from .models import MarketingEmailLog

    if not eligible_combined_subscribe_nudge(user):
        return False

    name = user.get_full_name() or user.username
    ok = queue_user_email(
        user,
        subject="Complete your FixitLab journey — interviews & hands-on labs",
        template="emails/marketing_combined_subscribe.html",
        context={
            "username": name,
            "interview_benefits": INTERVIEW_BENEFITS,
            "technology_benefits": TECH_BENEFITS,
            "featured_technologies": _featured_technologies(),
            "interview_plans_url": f"{settings.FRONTEND_URL}/interviews#interview-plans",
            "pricing_url": f"{settings.FRONTEND_URL}/pricing",
            "subscriptions_url": f"{settings.FRONTEND_URL}/subscriptions",
        },
        email_type="marketing",
    )
    if ok:
        MarketingEmailLog.objects.create(user=user, campaign="combined_subscribe_nudge")
        _inapp_nudge(
            user,
            "Subscribe to unlock everything",
            "Get interview plans and technology labs — all in one place.",
            f"{settings.FRONTEND_URL}/subscriptions",
        )
    return ok


def _inapp_nudge(user, title: str, message: str, url: str) -> None:
    try:
        from .tasks import create_in_app_notification

        create_in_app_notification.delay(
            user_id=user.id,
            notification_type="system",
            title=title,
            message=message,
            metadata={"category": "marketing", "url": url},
        )
    except Exception as exc:
        logger.warning("Marketing in-app nudge failed for %s: %s", user.id, exc)


def run_marketing_nudges() -> dict:
    """Scan users and send due nurture emails. Returns counts."""
    interview_sent = 0
    tech_sent = 0
    combined_sent = 0

    user_ids = set()
    qs = User.objects.filter(is_active=True, is_staff=False).only(
        "id", "email", "username", "last_login", "date_joined", "is_active", "is_staff",
    )

    for user in qs.iterator(chunk_size=200):
        if user.id in user_ids:
            continue
        try:
            if eligible_combined_subscribe_nudge(user):
                if send_combined_subscribe_nudge(user):
                    combined_sent += 1
                    user_ids.add(user.id)
                    continue
            if eligible_interview_sample_nudge(user):
                if send_interview_sample_nudge(user):
                    interview_sent += 1
                    user_ids.add(user.id)
                    continue
            if eligible_technology_subscribe_nudge(user):
                if send_technology_subscribe_nudge(user):
                    tech_sent += 1
                    user_ids.add(user.id)
        except Exception as exc:
            logger.warning("Marketing nudge failed user=%s: %s", user.id, exc)

    return {
        "interview_nudges_sent": interview_sent,
        "technology_nudges_sent": tech_sent,
        "combined_nudges_sent": combined_sent,
        "users_touched": len(user_ids),
    }
