from .models import Subscription, Plan


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


def get_user_subscription(user):
    try:
        return Subscription.objects.get(user=user, is_active=True)
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

