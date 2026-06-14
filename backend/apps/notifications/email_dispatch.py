"""Email dispatch — Celery worker for bulk mail; in-process thread for critical OTP."""

from __future__ import annotations

import logging
import threading

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


def _celery_notifications_worker_alive() -> bool:
    """Return True if at least one Celery worker responds to ping."""
    try:
        from celery_app.celery import app

        inspect = app.control.inspect(timeout=2.0)
        ping = inspect.ping() or {}
        return bool(ping)
    except Exception as exc:
        logger.debug("Celery worker ping failed: %s", exc)
        return False


def _deliver_in_background(subject: str, to_email: str, template: str, context: dict) -> None:
    """Fire-and-forget delivery from the web process (avoids HTTP blocking)."""
    try:
        ok = send_email_now(subject, to_email, template, context)
        if ok:
            logger.info("Critical email delivered in-process to %s", to_email)
        else:
            logger.error("Critical email delivery failed for %s (template=%s)", to_email, template)
    except Exception:
        logger.exception("Critical email thread failed for %s", to_email)


def dispatch_notification_email(
    subject: str,
    to_email: str,
    template: str,
    context=None,
    *,
    critical: bool = False,
) -> bool:
    """
    Delivery paths:
    - critical=True (OTP, password reset): send from web process in a daemon thread
      so delivery does not depend on Celery and the HTTP request is not blocked.
    - critical=False: queue on Celery notifications worker; sync fallback if queue down.
    """
    context = context or {}
    kwargs = {
        "subject": subject,
        "to_email": to_email,
        "template": template,
        "context": context,
    }

    if critical:
        threading.Thread(
            target=_deliver_in_background,
            args=(subject, to_email, template, context),
            daemon=True,
        ).start()
        return True

    try:
        from .tasks import send_notification_email

        send_notification_email.apply_async(kwargs=kwargs, queue="notifications")
        logger.info("Email queued via Celery for %s", to_email)
        return True
    except Exception as exc:
        logger.warning("Celery email queue failed for %s (%s)", to_email, exc)
        if not _celery_notifications_worker_alive():
            ok = send_email_now(subject, to_email, template, context)
            if ok:
                logger.info("Email delivered in-process (queue fallback) to %s", to_email)
                return True
        return False
