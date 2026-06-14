"""Email dispatch — Celery worker first (Gmail API), sync fallback if queue unavailable."""

from __future__ import annotations

import logging

from .email import send_email

logger = logging.getLogger(__name__)


def send_email_now(subject: str, to_email: str, template: str, context=None) -> bool:
    """Send in the current process (Gmail API → SendGrid → SMTP)."""
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
    Same delivery path as subscription/invoice emails:
    1. Queue on Celery worker (Gmail API / SendGrid — non-blocking)
    2. If Redis/Celery unavailable and critical=True, send in-process immediately

    Does NOT block the HTTP request waiting for delivery (avoids 504 gateway timeouts).
    """
    context = context or {}
    kwargs = {
        "subject": subject,
        "to_email": to_email,
        "template": template,
        "context": context,
    }

    try:
        from .tasks import send_notification_email

        send_notification_email.delay(**kwargs)
        logger.info("Email queued via Celery for %s", to_email)
        return True
    except Exception as exc:
        logger.warning(
            "Celery email queue failed for %s (%s)",
            to_email,
            exc,
        )
        if not critical:
            return False
        ok = send_email_now(subject, to_email, template, context)
        if not ok:
            raise RuntimeError(
                "Email could not be delivered. Check Gmail API, SendGrid, or SMTP settings."
            ) from exc
        logger.info("Email delivered in-process (queue fallback) to %s", to_email)
        return True
