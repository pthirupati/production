"""Subscription lifecycle helpers — 1-year term, renewal, complimentary access."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

SUBSCRIPTION_TERM_DAYS = 365
RENEWAL_WARNING_DAYS = 7
GRACE_PERIOD_DAYS = 3  # Read-only window after expiry before full lockout

# Always-valid certificate for admin/E2E verification tests
TEST_CERTIFICATE_ID = "FIXIT-TEST-ADMIN-CERT-2026"


def apply_dunning_status(subscription, sub_status: str) -> dict:
    """Apply Stripe-like subscription status with a past_due dunning grace.

    ``past_due`` keeps ``is_active`` True so plan limits continue while retries
    run (same GRACE_PERIOD_DAYS spirit as expiry grace). ``unpaid`` /
    ``cancelled`` deactivate. Returns a small audit dict for tests/logs.
    """
    status = (sub_status or "").strip().lower()
    if status == "past_due":
        # Do not hard-kill — dunning / retry window.
        if not subscription.is_active:
            subscription.is_active = True
            subscription.save(update_fields=["is_active"])
        return {"action": "dunning_grace", "is_active": True, "status": status}
    if status in ("unpaid", "cancelled", "canceled"):
        subscription.is_active = False
        subscription.save(update_fields=["is_active"])
        return {"action": "deactivate", "is_active": False, "status": status}
    if status == "active":
        subscription.is_active = True
        subscription.save(update_fields=["is_active"])
        return {"action": "activate", "is_active": True, "status": status}
    return {"action": "noop", "is_active": bool(subscription.is_active), "status": status}


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


def technology_access_denied_response(user, technology_slug: str):
    """
    Return a DRF Response when the user may not open a standalone console for
    this technology, or None when access is allowed.

    Free technologies and complimentary/staff users always pass. Used to close
    the revenue hole where any authenticated user could open /vmware-sim (or
    similar demo APIs) without a technology subscription.
    """
    from rest_framework.response import Response

    from apps.question_bank.models import Technology

    if not user or not user.is_authenticated:
        return Response(
            {"error": "Authentication required", "code": "AUTH_REQUIRED"},
            status=401,
        )
    if user_has_complimentary_access(user):
        return None
    tech = Technology.objects.filter(slug=technology_slug).first()
    if not tech:
        # Unknown slug — fail closed for paid-console surfaces.
        return Response(
            {
                "error": "Subscription required",
                "code": "SUBSCRIPTION_REQUIRED",
                "technology": technology_slug,
            },
            status=403,
        )
    if tech.is_free or tech.price == 0:
        return None
    if user_has_technology_access(user, tech.id):
        return None
    return Response(
        {
            "error": "Subscription required. Purchase access to this technology first.",
            "code": "SUBSCRIPTION_REQUIRED",
            "technology": tech.name,
            "technology_slug": tech.slug,
            "renew_url": f"/payment?technology={tech.slug}",
        },
        status=403,
    )


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
    # A cancelled subscription keeps access to the end of its paid term
    # (audit Z1-11), so it is still `active` — but prompting the customer to renew
    # something they just cancelled would be the wrong message.
    cancelled = bool(getattr(sub, "cancelled_at", None))
    if sub.expires_at:
        delta = (sub.expires_at - now).days
        days_left = max(0, delta)
        needs_renewal = active and not cancelled and delta <= RENEWAL_WARNING_DAYS
    return {
        "is_active": active,
        "in_grace_period": in_grace,
        "has_access": active or in_grace,
        "cancelled": cancelled,
        "cancelled_at": sub.cancelled_at.isoformat() if cancelled else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "expires_at": sub.expires_at.isoformat() if sub.expires_at else None,
        "days_until_expiry": days_left,
        "needs_renewal": (needs_renewal or in_grace) and not cancelled,
        "is_expired": bool(sub.expires_at and sub.expires_at <= now and not in_grace),
    }
