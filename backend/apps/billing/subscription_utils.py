"""Subscription lifecycle helpers — 1-year term, renewal, complimentary access."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

SUBSCRIPTION_TERM_DAYS = 365
RENEWAL_WARNING_DAYS = 7
GRACE_PERIOD_DAYS = 3  # Read-only window after expiry before full lockout

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


def is_tech_subscription_in_grace(sub) -> bool:
    """True during post-expiry grace window (labs blocked, renew encouraged)."""
    if not sub or not sub.expires_at:
        return False
    now = timezone.now()
    if now <= sub.expires_at:
        return False
    grace_end = sub.expires_at + timedelta(days=GRACE_PERIOD_DAYS)
    return now <= grace_end


def user_has_technology_access(user, technology_id) -> bool:
    """Active subscription, grace period, org grant, or complimentary/staff access."""
    if user_has_complimentary_access(user):
        return True
    if user_has_org_technology_access(user, technology_id):
        return True
    sub = (
        user.tech_subscriptions.filter(technology_id=technology_id)
        .order_by("-created_at")
        .first()
    )
    if not sub:
        return False
    return is_tech_subscription_active(sub) or is_tech_subscription_in_grace(sub)


def user_has_org_technology_access(user, technology_id) -> bool:
    """True if user's organization has an active grant for this technology."""
    if not user or not user.is_authenticated:
        return False
    try:
        from apps.accounts.models import OrganizationMember, OrganizationTechnologyGrant
        from django.utils import timezone

        org_ids = OrganizationMember.objects.filter(
            user=user,
            organization__is_active=True,
        ).values_list("organization_id", flat=True)
        if not org_ids:
            return False
        now = timezone.now()
        grants = OrganizationTechnologyGrant.objects.filter(
            organization_id__in=org_ids,
            technology_id=technology_id,
            is_active=True,
        )
        for grant in grants:
            if grant.is_valid_now():
                return True
    except Exception:
        return False
    return False


def get_subscribed_technology_ids(user):
    """Return None for full access, else set of technology ids."""
    if user_has_complimentary_access(user):
        return None
    ids = set(active_tech_subscriptions_qs(user).values_list("technology_id", flat=True))
    try:
        from apps.accounts.models import OrganizationMember, OrganizationTechnologyGrant

        org_ids = OrganizationMember.objects.filter(
            user=user,
            organization__is_active=True,
        ).values_list("organization_id", flat=True)
        for grant in OrganizationTechnologyGrant.objects.filter(
            organization_id__in=org_ids,
            is_active=True,
        ):
            if grant.is_valid_now():
                ids.add(grant.technology_id)
    except Exception:
        pass
    return ids


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


def activate_technology_subscription(sub, *, renew=False):
    """Mark subscription active with a fresh 1-year expiry."""
    now = timezone.now()
    sub.is_active = True
    sub.payment_verified = True
    sub.expires_at = subscription_expires_at(now)
    if renew:
        sub.renewal_reminder_at = None
    sub.save(update_fields=["is_active", "payment_verified", "expires_at", "renewal_reminder_at"])


def get_or_create_technology_subscription(user, technology, *, defaults=None):
    """
    Atomically get or create a per-technology subscription.
    Uses select_for_update to prevent duplicate rows under concurrent payment confirmations.
    """
    from django.db import IntegrityError, transaction
    from .models import TechnologySubscription

    defaults = dict(defaults or {})
    with transaction.atomic():
        existing = (
            TechnologySubscription.objects.select_for_update()
            .filter(user=user, technology=technology)
            .first()
        )
        if existing:
            return existing, False
        try:
            sub = TechnologySubscription.objects.create(
                user=user,
                technology=technology,
                **defaults,
            )
            return sub, True
        except IntegrityError:
            return TechnologySubscription.objects.get(user=user, technology=technology), False


def grant_complimentary_access(user, enabled: bool = True, *, granted_by=None):
    from apps.accounts.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.complimentary_access = enabled
    profile.save(update_fields=["complimentary_access"])

    if granted_by:
        try:
            from apps.audit.models import AuditLog
            AuditLog.objects.create(
                user=granted_by,
                action="admin_action",
                resource=f"/admin/users/{user.id}/complimentary_access",
                metadata={
                    "event": "complimentary_access",
                    "enabled": enabled,
                    "target_user_id": user.id,
                    "target_email": user.email,
                    "target_username": user.username,
                },
            )
        except Exception:
            pass

    return profile


def subscription_status_payload(sub) -> dict:
    now = timezone.now()
    active = is_tech_subscription_active(sub)
    in_grace = is_tech_subscription_in_grace(sub)
    days_left = None
    needs_renewal = False
    if sub.expires_at:
        delta = (sub.expires_at - now).days
        days_left = max(0, delta)
        needs_renewal = active and delta <= RENEWAL_WARNING_DAYS
    return {
        "is_active": active,
        "in_grace_period": in_grace,
        "has_access": active or in_grace,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "days_until_expiry": days_left,
        "needs_renewal": needs_renewal or in_grace,
        "is_expired": bool(sub.expires_at and sub.expires_at <= now and not in_grace),
    }
