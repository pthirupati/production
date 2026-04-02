from .models import Subscription, Plan


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
    # Admin / staff users have unlimited access
    if user.is_staff or user.is_superuser:
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

    # Admin / staff users see unlimited
    is_admin = user.is_staff or user.is_superuser
    max_labs = 999999 if is_admin else plan.max_labs_per_day

    return {
        "plan": {
            "code": "admin" if is_admin else plan.code,
            "name": "Admin (Unlimited)" if is_admin else plan.name,
            "max_labs_per_day": max_labs,
            "max_lab_duration_minutes": 1440 if is_admin else plan.max_lab_duration_minutes,
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
    }

