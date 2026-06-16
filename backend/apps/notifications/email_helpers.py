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
    from .tasks import send_notification_email

    ctx = dict(context or {})
    if email_type == "marketing":
        from .unsubscribe import marketing_unsubscribe_url
        ctx.setdefault("unsubscribe_url", marketing_unsubscribe_url(user.id))
        ctx.setdefault("profile_notifications_url", f"{settings.FRONTEND_URL}/profile#notifications")

    send_notification_email.delay(
        subject=subject,
        to_email=user.email,
        template=template,
        context=ctx,
    )
    return True
