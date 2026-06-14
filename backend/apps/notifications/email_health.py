"""Email delivery health checks for admin dashboards and alerts."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone


def email_delivery_health(window_minutes: int = 15) -> dict:
    """
    Return recent EmailLog stats and whether operators should be alerted.

    Alert when failures persist in the window:
    - any failures with zero successes, or
    - failure rate >= 50% with at least 3 attempts.
    """
    from .models import EmailLog

    since = timezone.now() - timedelta(minutes=window_minutes)
    sent = EmailLog.objects.filter(status="sent", created_at__gte=since).count()
    failed = EmailLog.objects.filter(status="failed", created_at__gte=since).count()
    total = sent + failed

    alert = False
    message = ""
    if failed > 0 and sent == 0:
        alert = True
        message = (
            f"Email delivery failing: {failed} failed, 0 sent in the last {window_minutes} minutes. "
            "Check GMAIL_OAUTH_* on backend and celery_worker."
        )
    elif total >= 3 and failed / total >= 0.5:
        alert = True
        message = (
            f"High email failure rate: {failed}/{total} failed in the last {window_minutes} minutes."
        )

    return {
        "window_minutes": window_minutes,
        "sent": sent,
        "failed": failed,
        "total": total,
        "failure_rate": round((failed / total) * 100, 1) if total else 0.0,
        "alert": alert,
        "message": message,
    }
