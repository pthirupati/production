"""Subscription lifecycle helpers — 1-year term, renewal, complimentary access."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

SUBSCRIPTION_TERM_DAYS = 365
RENEWAL_WARNING_DAYS = 7

# Always-valid certificate for admin/E2E verification tests
TEST_CERTIFICATE_ID = "FIXIT-TEST-ADMIN-CERT-2026"


def subscription_expires_at(from_dt=None):
    base = from_dt or timezone.now()
    return base + timedelta(days=SUBSCRIPTION_TERM_DAYS)


def is_tech_subscription_active(sub) -> bool:
    if not sub or not sub.is_active:
        return False
    if sub.expires_at and sub.expires_at <= timezone.now():
        return False
    return True


def active_tech_subscriptions_qs(user):
    """QuerySet filter for currently valid technology subscriptions."""
    now = timezone.now()
    return (
        user.tech_subscriptions.filter(is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    )


def user_has_complimentary_access(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    try:
        return bool(user.profile.complimentary_access)
    except Exception:
        return False


def user_has_all_technology_access(user) -> bool:
    return user_has_complimentary_access(user)


def get_subscribed_technology_ids(user):
    """Return None for full access, else set of technology ids."""
    if user_has_complimentary_access(user):
        return None
    return set(
        active_tech_subscriptions_qs(user).values_list("technology_id", flat=True)
    )


def activate_technology_subscription(sub, *, renew=False):
    """Mark subscription active with a fresh 1-year expiry."""
    now = timezone.now()
    sub.is_active = True
    sub.payment_verified = True
    sub.expires_at = subscription_expires_at(now)
    if renew:
        sub.renewal_reminder_at = None
    sub.save(update_fields=["is_active", "payment_verified", "expires_at", "renewal_reminder_at"])


def grant_complimentary_access(user, enabled: bool = True):
    from apps.accounts.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.complimentary_access = enabled
    profile.save(update_fields=["complimentary_access"])
    return profile


def subscription_status_payload(sub) -> dict:
    now = timezone.now()
    active = is_tech_subscription_active(sub)
    days_left = None
    needs_renewal = False
    if sub.expires_at:
        delta = (sub.expires_at - now).days
        days_left = max(0, delta)
        needs_renewal = active and delta <= RENEWAL_WARNING_DAYS
    return {
        "is_active": active,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "days_until_expiry": days_left,
        "needs_renewal": needs_renewal,
        "is_expired": bool(sub.expires_at and sub.expires_at <= now),
    }
