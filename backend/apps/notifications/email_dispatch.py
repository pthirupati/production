"""Email dispatch — sync for auth-critical flows, async for everything else."""

from __future__ import annotations

import logging

from django.conf import settings

from .email import send_email

logger = logging.getLogger(__name__)


def send_email_now(subject: str, to_email: str, template: str, context=None) -> bool:
    """Send immediately; returns True only when delivery succeeds."""
    return send_email(
        subject=subject,
        to_email=to_email,
        template=template,
        context=context or {},
    )


def dispatch_notification_email(
    subject: str,
    to_email: str,
    template: str,
    context=None,
    *,
    critical: bool = False,
) -> bool:
    """
    Deliver email. Auth flows (OTP, password reset) use synchronous delivery so
    users are not told "sent" when Celery/Redis is down and the task never runs.
    """
    context = context or {}

    if critical or getattr(settings, "EMAIL_SYNC_AUTH", True):
        ok = send_email_now(subject, to_email, template, context)
        if not ok:
            raise RuntimeError(
                "Email could not be delivered. Check EMAIL_HOST_USER, Gmail API, or SendGrid settings."
            )
        return True

    try:
        from .tasks import send_notification_email

        send_notification_email.delay(
            subject=subject,
            to_email=to_email,
            template=template,
            context=context,
        )
        return True
    except Exception as exc:
        logger.warning("Celery email queue unavailable (%s) — falling back to sync send", exc)
        ok = send_email_now(subject, to_email, template, context)
        if not ok:
            raise RuntimeError("Email could not be delivered") from exc
        return True
