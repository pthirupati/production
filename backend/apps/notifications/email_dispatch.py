"""Email dispatch — Celery worker for bulk mail; in-process thread for critical OTP."""

from __future__ import annotations

import atexit
import logging
import threading
import time

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


# In-flight critical sends, so shutdown can wait for them (audit Z6-16).
#
# `daemon=True` threads are killed when the interpreter exits, so a deploy landing
# mid-send silently dropped an OTP: no queue, no retry, no record. The user saw
# "code sent" and nothing arrived, and nothing anywhere said why.
#
# The threads stay daemons deliberately. Making them non-daemon would let a hung
# SMTP connection block interpreter exit indefinitely — turning a dropped email into
# a stuck deploy, which is a worse failure. Instead they are tracked, and an atexit
# handler gives them a bounded chance to finish.
_inflight_lock = threading.Lock()
_inflight: set = set()

# Long enough for a normal Gmail API call, short enough not to hold up a rolling
# deploy. A send that has not completed in this window was not going to.
CRITICAL_DRAIN_TIMEOUT_SECONDS = 5.0


def _drain_inflight_sends() -> None:
    """Give in-flight critical emails a bounded chance to finish before exit.

    Registered with `atexit`. The timeout is the whole point: the common case is
    that a send completes in well under a second and nobody notices, and the
    pathological case (a hung connection) still lets the process exit — but says
    so, with the recipient, so the drop is recoverable instead of invisible.
    """
    with _inflight_lock:
        pending = list(_inflight)
    if not pending:
        return

    logger.info("Waiting for %d in-flight critical email(s) before exit", len(pending))
    deadline = time.monotonic() + CRITICAL_DRAIN_TIMEOUT_SECONDS
    for thread, recipient in pending:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)

    with _inflight_lock:
        stranded = [r for t, r in _inflight if t.is_alive()]
    if stranded:
        # The one thing that must not happen quietly. A user is waiting for one of
        # these and will retry; this line is how anyone finds out.
        logger.error(
            "Process exiting with %d undelivered critical email(s): %s — these "
            "recipients did NOT receive their message and must retry",
            len(stranded), ", ".join(stranded),
        )


atexit.register(_drain_inflight_sends)


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
    finally:
        # Deregister whatever happened, or the set grows for the process lifetime
        # and the drain waits on threads that finished hours ago.
        current = threading.current_thread()
        with _inflight_lock:
            _inflight.discard((current, to_email))


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
        thread = threading.Thread(
            target=_deliver_in_background,
            args=(subject, to_email, template, context),
            daemon=True,
        )
        # Registered BEFORE start(), so a thread cannot complete and deregister
        # before it was ever tracked — which would leave the entry behind forever.
        with _inflight_lock:
            _inflight.add((thread, to_email))
        thread.start()
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
