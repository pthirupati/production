import logging
from datetime import timedelta

from django.utils import timezone

from .models import Subscription, Plan

logger = logging.getLogger(__name__)


def user_has_complimentary_access(user) -> bool:
    """True when an admin has granted this user complimentary (free) access.

    Complimentary users get unlimited daily labs, just like staff — granting
    free access must lift the daily cap, not only the per-technology paywall.
    """
    try:
        profile = getattr(user, "profile", None)
        return bool(profile and profile.complimentary_access)
    except Exception:
        return False


def has_unlimited_access(user) -> bool:
    return bool(user.is_staff or user.is_superuser or user_has_complimentary_access(user))


def _free_plan():
    plan, _ = Plan.objects.get_or_create(
        code="free",
        defaults={
            "name": "Free",
            "price": 0,
            "max_labs_per_day": 5,
            "max_lab_duration_minutes": 30,
        },
    )
    return plan


def plan_subscription_is_current(sub) -> bool:
    """True when a plan subscription should still confer its plan's limits.

    ``expires_at`` was never checked anywhere -- ``get_user_subscription`` filtered
    on ``is_active=True`` only, and ``can_start_lab`` / ``can_extend_lab`` read
    ``subscription.plan.max_labs_per_day`` straight off it. So a Pro plan that
    lapsed months ago kept its elevated daily lab cap and duration indefinitely.
    ``get_user_plan_info`` merely *reported* ``expires_at``, which is what made it
    look handled.

    Uses the same GRACE_PERIOD_DAYS window already established for per-technology
    subscriptions (subscription_utils.is_tech_subscription_in_grace) rather than
    inventing a second expiry rule -- a renewal that lands a day late should not
    drop a paying user to the free tier.

    ``expires_at is None`` means perpetual (free tier, comped access) and stays current.
    """
    if not sub or not sub.is_active:
        return False
    if not sub.expires_at:
        return True
    from .subscription_utils import GRACE_PERIOD_DAYS

    return timezone.now() <= sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS)


def get_user_subscription(user):
    try:
        sub = Subscription.objects.select_related("plan").get(user=user, is_active=True)
        if plan_subscription_is_current(sub):
            return sub
        # Lapsed past the grace window. Deliberately NOT flipping is_active here:
        # this is a read path called on every lab start, and a silent write in a
        # getter is the kind of surprise that makes concurrency bugs. Reconciling
        # the flag belongs in a beat task; refusing to honour the plan is enough to
        # stop the entitlement leak.
        logger.info(
            "Plan subscription for user=%s lapsed at %s — serving free-tier limits",
            user.id, sub.expires_at,
        )
        sub.plan = _free_plan()
        return sub
    except Subscription.DoesNotExist:
        # Auto-assign free plan
        free_plan, _ = Plan.objects.get_or_create(
            code="free",
            defaults={
                "name": "Free",
                "price": 0,
                "max_labs_per_day": 5,
                "max_lab_duration_minutes": 30,
            },
        )
        return Subscription.objects.create(user=user, plan=free_plan)


def can_start_lab(user, labs_started_today):
    # Admin / staff and admin-granted complimentary users have unlimited access.
    if has_unlimited_access(user):
        return True
    subscription = get_user_subscription(user)
    return labs_started_today < subscription.plan.max_labs_per_day


def can_extend_lab(user, duration_minutes):
    subscription = get_user_subscription(user)
    return duration_minutes <= subscription.plan.max_lab_duration_minutes


def get_user_plan_info(user):
    """Return plan details and usage for the current user."""
    from apps.labs.models import LabSession
    from django.utils import timezone

    subscription = get_user_subscription(user)
    plan = subscription.plan
    today_count = LabSession.objects.filter(
        user=user,
        started_at__date=timezone.now().date(),
    ).exclude(status="FAILED").count()

    # Admin / staff and complimentary (admin-granted free) users see unlimited.
    is_admin = user.is_staff or user.is_superuser
    is_complimentary = user_has_complimentary_access(user)
    unlimited = is_admin or is_complimentary
    max_labs = 999999 if unlimited else plan.max_labs_per_day

    if is_admin:
        plan_code, plan_name = "admin", "Admin (Unlimited)"
    elif is_complimentary:
        plan_code, plan_name = "complimentary", "Free Access (Unlimited)"
    else:
        plan_code, plan_name = plan.code, plan.name

    return {
        "plan": {
            "code": plan_code,
            "name": plan_name,
            "max_labs_per_day": max_labs,
            "max_lab_duration_minutes": 1440 if unlimited else plan.max_lab_duration_minutes,
        },
        "usage": {
            "labs_today": today_count,
            "labs_remaining": max_labs - today_count,
        },
        "subscription": {
            "is_active": subscription.is_active,
            "started_at": subscription.started_at,
            "expires_at": subscription.expires_at,
        },
        "is_admin": is_admin,
        "is_complimentary": is_complimentary,
        "unlimited": unlimited,
    }

