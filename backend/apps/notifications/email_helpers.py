"""Preference-aware email dispatch helpers."""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def user_wants_email(user, email_type: str) -> bool:
    from .models import NotificationPreference

    prefs = NotificationPreference.get_for_user(user)
    return prefs.should_email(email_type)


def queue_user_email(user, subject, template, context, email_type: str) -> bool:
    """
    Queue email via Celery if the user opted in for this type.
    Returns False when skipped due to preferences.
    """
    if not user_wants_email(user, email_type):
        logger.debug("Skipping %s email for %s (prefs)", email_type, user.email)
        return False
    # Never let a marketing blast eat the quota OTP and password resets depend on.
    if email_type == "marketing":
        allowed, reason = marketing_send_allowed()
        if not allowed:
            logger.warning("Skipping marketing email for %s — %s", user.email, reason)
            return False

    # Suppression (audit Z6-16). An address that has hard-failed repeatedly was
    # previously retried forever, and on a shared ~500/day Gmail allowance every
    # send to a dead mailbox is one fewer message available to someone trying to
    # sign in. Critical mail is exempt inside `is_suppressed` — suppression must
    # never become an account lockout.
    from .suppression import is_suppressed

    if is_suppressed(user.email, email_type):
        logger.info(
            "Skipping %s email for %s — address suppressed after repeated failures",
            email_type, user.email,
        )
        return False
    from .tasks import send_notification_email

    ctx = dict(context or {})
    extra_headers = None
    if email_type == "marketing":
        from .unsubscribe import list_unsubscribe_headers, marketing_unsubscribe_url
        ctx.setdefault("unsubscribe_url", marketing_unsubscribe_url(user.id))
        ctx.setdefault("profile_notifications_url", f"{settings.FRONTEND_URL}/profile#notifications")
        # RFC 8058 one-click headers, required of bulk senders by Gmail and Yahoo
        # since Feb 2024 (audit Z6-4). Marketing only: attaching List-Unsubscribe to
        # a password-reset mail would invite a provider to offer "unsubscribe" from
        # transactional mail the user needs.
        extra_headers = list_unsubscribe_headers(user.id)

    send_notification_email.delay(
        subject=subject,
        to_email=user.email,
        template=template,
        context=ctx,
        headers=extra_headers,
    )
    return True


# ── Transactional headroom (audit Z6-3) ─────────────────────────────────────
#
# Marketing and transactional mail share one consumer Gmail account and one
# ~500/day cap, and the same _deliver chain. So a nurture blast that exhausts the
# quota does not merely fail to market — it stops OTP and password-reset delivery,
# i.e. nobody can sign in or recover an account until midnight UTC. An auth outage
# caused by a marketing campaign is the worst trade in the system.
#
# The real fix is a separate sending identity for bulk mail (owner task: a second
# account or a proper ESP). Until then, reserve the tail of the daily quota so
# transactional mail always has room: marketing is refused once the day's sends
# reach cap - reserve, while OTP and resets keep sending straight through.

def _sent_today() -> int:
    """Emails successfully sent since UTC midnight, cached briefly.

    Counted from EmailLog rather than a counter in cache because it must survive a
    Redis flush or a worker restart — losing the count would silently restore the
    exact behaviour this guard exists to prevent. The 60s cache keeps a nurture loop
    from issuing one COUNT per recipient; 60s of drift is irrelevant against a
    reserve measured in the hundreds.
    """
    from django.core.cache import cache
    from django.utils import timezone

    cached = cache.get("email:sent_today")
    if cached is not None:
        return cached
    from .models import EmailLog

    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = EmailLog.objects.filter(status="sent", created_at__gte=start).count()
    cache.set("email:sent_today", count, 60)
    return count


def marketing_send_allowed() -> tuple[bool, str]:
    """(allowed, reason) — whether a marketing send may proceed right now."""
    cap = int(getattr(settings, "EMAIL_DAILY_SEND_CAP", 500) or 0)
    reserve = int(getattr(settings, "EMAIL_TRANSACTIONAL_RESERVE", 150) or 0)
    if cap <= 0:
        return True, ""  # no cap configured (e.g. a real ESP) — nothing to protect
    budget = max(cap - reserve, 0)
    used = _sent_today()
    if used >= budget:
        return False, (
            f"marketing paused: {used} sent today, marketing budget is {budget} "
            f"(cap {cap} minus {reserve} reserved for OTP/password-reset delivery)"
        )
    return True, ""


def deliver_inapp_notification(user, notification_type, title, message="",
                               metadata=None, *, force=False):
    """Create an in-app notification, honouring the user's preferences.

    The single choke point for in-app delivery (audit Z3-6). `should_notify_inapp`
    already existed and was consulted by three specific tasks, but the *generic*
    `create_in_app_notification` task and both direct writers
    (`jira_integration/webhooks.py`, `community/views.py`) called
    `Notification.objects.create` straight — so switching "System notifications" off
    in Profile silently did nothing for the notifications users actually receive
    most. A preference the UI offers and the backend ignores is worse than no
    preference: it tells the user they are in control when they are not.

    Centralised deliberately rather than adding a fourth and fifth copy of the
    check. Scattered gates drift — that is exactly how these three writers ended up
    bypassing one that already existed.

    `force=True` is for notifications that must land regardless (account lifecycle,
    security). Preferences govern what a user finds *useful*, not whether we may
    tell them their account is being deleted.

    Returns the Notification, or None when suppressed.
    """
    from .models import Notification, NotificationPreference

    if not force:
        try:
            prefs = NotificationPreference.get_for_user(user)
            if not prefs.should_notify_inapp(notification_type):
                logger.debug(
                    "Suppressing in-app %s for %s (prefs)", notification_type, user
                )
                return None
        except Exception as exc:  # noqa: BLE001 - never lose a notification to a pref lookup
            logger.warning("in-app pref lookup failed for %s: %s", user, exc)

    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        message=message,
        metadata=metadata or {},
    )
