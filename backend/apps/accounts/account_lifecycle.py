"""Inactive account warnings and deletion for users without subscriptions."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()


def _inactive_months() -> int:
    return int(getattr(settings, "INACTIVE_ACCOUNT_MONTHS", 3))


def _warning_days_before() -> int:
    return int(getattr(settings, "INACTIVE_ACCOUNT_WARNING_DAYS", 14))


def _lifecycle_enabled() -> bool:
    return bool(getattr(settings, "INACTIVE_ACCOUNT_CLEANUP_ENABLED", True))


def user_has_any_paid_subscription(user) -> bool:
    """True if user has paid tech or interview access."""
    from apps.billing.subscription_utils import (
        active_tech_subscriptions_qs,
        user_has_complimentary_access,
    )
    from apps.interviews.models import InterviewEntitlement

    if user_has_complimentary_access(user):
        return True
    if user.is_staff or user.is_superuser:
        return True

    if active_tech_subscriptions_qs(user).filter(payment_verified=True).exists():
        return True

    ent = InterviewEntitlement.objects.filter(user=user).first()
    if ent and ent.is_active and ent.plan_tier_id:
        if ent.is_complimentary or ent.is_admin_granted_free:
            return True
        if ent.plan_tier.code in ("pro", "premium"):
            if not ent.period_end or ent.period_end > timezone.now():
                return True
    return False


def eligible_for_inactive_warning(user) -> bool:
    if not _lifecycle_enabled() or not user.is_active or user.is_staff:
        return False
    if user_has_any_paid_subscription(user):
        return False

    from apps.accounts.models import AccountLifecycleEvent

    cutoff = timezone.now() - timedelta(days=_inactive_months() * 30 - _warning_days_before())
    if user.date_joined > cutoff:
        return False
    if AccountLifecycleEvent.objects.filter(user=user, event_type="inactive_warning").exists():
        return False
    return True


def eligible_for_inactive_deletion(user) -> bool:
    if not _lifecycle_enabled() or not user.is_active or user.is_staff:
        return False
    if user_has_any_paid_subscription(user):
        return False

    delete_after = user.date_joined + timedelta(days=_inactive_months() * 30)
    if timezone.now() < delete_after:
        return False

    from apps.accounts.models import AccountLifecycleEvent
    return AccountLifecycleEvent.objects.filter(user=user, event_type="inactive_warning").exists()


def send_inactive_warning(user) -> bool:
    from apps.notifications.email_helpers import queue_user_email
    from apps.accounts.models import AccountLifecycleEvent

    if not eligible_for_inactive_warning(user):
        return False

    delete_date = user.date_joined + timedelta(days=_inactive_months() * 30)
    name = user.get_full_name() or user.username
    pricing_url = f"{settings.FRONTEND_URL}/pricing"
    interviews_url = f"{settings.FRONTEND_URL}/interviews"

    ok = queue_user_email(
        user,
        subject="Action required: Your FixitLab account will be removed soon",
        template="emails/account_inactive_warning.html",
        context={
            "username": name,
            "delete_date": delete_date.strftime("%B %d, %Y"),
            "months": _inactive_months(),
            "pricing_url": pricing_url,
            "interviews_url": interviews_url,
            "profile_url": f"{settings.FRONTEND_URL}/profile",
        },
        email_type="marketing",
    )
    if ok:
        AccountLifecycleEvent.objects.create(
            user=user,
            email=user.email,
            event_type="inactive_warning",
        )
    return ok


def delete_inactive_user(user) -> bool:
    """Permanently delete user and all related data (CASCADE)."""
    from apps.accounts.models import AccountLifecycleEvent

    if not eligible_for_inactive_deletion(user):
        return False

    user_id = user.id
    email = user.email
    AccountLifecycleEvent.objects.create(
        user=None,
        email=email,
        event_type="deleted",
        metadata={"user_id": user_id, "username": user.username},
    )
    user.delete()
    logger.info("Deleted inactive account user_id=%s email=%s", user_id, email)
    return True


def run_account_lifecycle() -> dict:
    warnings = 0
    deleted = 0

    qs = User.objects.filter(is_active=True, is_staff=False).only(
        "id", "email", "username", "date_joined", "is_active", "is_staff",
    )
    for user in qs.iterator(chunk_size=200):
        try:
            if eligible_for_inactive_deletion(user):
                if delete_inactive_user(user):
                    deleted += 1
                continue
            if eligible_for_inactive_warning(user):
                if send_inactive_warning(user):
                    warnings += 1
        except Exception as exc:
            logger.warning("Account lifecycle failed user=%s: %s", user.id, exc)

    return {"warnings_sent": warnings, "accounts_deleted": deleted}
