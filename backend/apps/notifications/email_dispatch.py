"""Email dispatch — Celery worker first (Gmail API), sync fallback in-process."""

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
    Deliver email the same way as subscription/invoice mail:
    1. Celery worker (Gmail API / SendGrid — works when SMTP ports are blocked)
    2. In-process sync fallback if the queue is unavailable

    critical=True waits for worker delivery before returning (OTP, password reset).
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

        if critical:
            result = send_notification_email.apply_async(kwargs=kwargs)
            ok = result.get(timeout=60)
            if not ok:
                raise RuntimeError(f"Worker reported email delivery failed for {to_email}")
            logger.info("Email delivered via Celery worker to %s", to_email)
            return True

        send_notification_email.delay(**kwargs)
        return True
    except Exception as exc:
        logger.warning(
            "Celery email dispatch failed for %s (%s) — trying in-process send",
            to_email,
            exc,
        )
        ok = send_email_now(subject, to_email, template, context)
        if critical and not ok:
            raise RuntimeError(
                "Email could not be delivered. Check Gmail API, SendGrid, or SMTP settings."
            ) from exc
        return ok
