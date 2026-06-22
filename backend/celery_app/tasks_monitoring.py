"""Business-signal monitoring beat task (PRODUCTION_AUDIT OBS-02).

A single periodic task, :func:`check_business_signals`, evaluates the
operational signals the audit flagged as unmonitored and fires an alert (via
:mod:`common.alerting`) when any crosses its threshold:

  * payment-failure spike  — failed PaymentTransactions in the last window
  * stale backup heartbeat — last successful backup older than the grace period
    (dead-man's-switch; see ``common.backup_heartbeat``)
  * deep Celery queue      — total reserved/active tasks across workers
  * login-failure spike    — ``login_failed`` audit rows in the last window

Everything is **gated**: when no alert channel is configured
(``ALERT_WEBHOOK_URL`` / ``ALERT_EMAIL`` both unset) the task still runs and
logs findings but :func:`common.alerting.send_alert` performs no I/O — so the
default deploy is behaviour-unchanged. Each individual check is wrapped so one
failing probe (e.g. broker inspect timeout) can never break the others, and the
task itself never raises into the worker.

Thresholds are Django settings with sane defaults (see ``config.settings`` —
the ``ALERT_*`` block). The beat schedule entry is in
``celery_app.beat_schedule``.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from common.alerting import send_alert

logger = logging.getLogger(__name__)


def _check_payment_failures() -> list[str]:
    """Alert when failed payments in the recent window exceed the threshold."""
    window_min = int(getattr(settings, "ALERT_PAYMENT_FAILURE_WINDOW_MINUTES", 60))
    threshold = int(getattr(settings, "ALERT_PAYMENT_FAILURE_THRESHOLD", 10))
    from apps.billing.models import PaymentTransaction

    since = timezone.now() - timedelta(minutes=window_min)
    failed = PaymentTransaction.objects.filter(
        status="failed", updated_at__gte=since
    ).count()
    if failed >= threshold:
        return [
            f"Payment failures spiked: {failed} failed transaction(s) in the "
            f"last {window_min}m (threshold {threshold})."
        ]
    logger.info("monitor: payment failures=%s window=%sm threshold=%s", failed, window_min, threshold)
    return []


def _check_backup_heartbeat() -> list[str]:
    """Dead-man's-switch: alert when the last backup is too old / unknown."""
    max_age_hours = float(getattr(settings, "ALERT_BACKUP_MAX_AGE_HOURS", 26))
    from common.backup_heartbeat import backup_age_seconds, read_last_backup_epoch

    epoch = read_last_backup_epoch()
    if epoch is None:
        # Unknown heartbeat. Only alert once a backup has ever been expected —
        # i.e. when an alert channel is configured (the owner has opted in to
        # operating the backup). Without a channel this is a no-op anyway.
        return [
            "Backup heartbeat is MISSING (no last-successful-backup timestamp "
            "found in Redis). The off-site backup may not be running."
        ]
    age = backup_age_seconds()
    if age is not None and age > max_age_hours * 3600:
        hrs = age / 3600.0
        return [
            f"Backup heartbeat is STALE: last successful backup was "
            f"{hrs:.1f}h ago (threshold {max_age_hours:.0f}h)."
        ]
    logger.info("monitor: backup age=%ss threshold=%sh", age, max_age_hours)
    return []


def _check_celery_queue_depth() -> list[str]:
    """Alert when total reserved+active tasks across workers is too deep.

    Uses Celery's control inspect (broker-agnostic). If inspection returns
    nothing (no workers responded, broker is the in-memory test broker, or the
    call timed out) we DO NOT alert — inability to measure is not a backlog.
    """
    threshold = int(getattr(settings, "ALERT_CELERY_QUEUE_THRESHOLD", 200))
    try:
        from celery_app.celery import app as celery_app

        inspector = celery_app.control.inspect(timeout=3)
        reserved = inspector.reserved() or {}
        active = inspector.active() or {}
    except Exception as exc:  # noqa: BLE001
        logger.info("monitor: celery inspect unavailable: %s", exc)
        return []
    if not reserved and not active:
        # No worker responded — cannot measure; skip rather than false-alarm.
        return []
    depth = sum(len(v or []) for v in reserved.values()) + sum(
        len(v or []) for v in active.values()
    )
    if depth >= threshold:
        return [
            f"Celery queue is deep: {depth} reserved/active task(s) across "
            f"workers (threshold {threshold})."
        ]
    logger.info("monitor: celery depth=%s threshold=%s", depth, threshold)
    return []


def _check_login_failures() -> list[str]:
    """Alert on a login-failure spike (possible brute force)."""
    window_min = int(getattr(settings, "ALERT_LOGIN_FAILURE_WINDOW_MINUTES", 15))
    threshold = int(getattr(settings, "ALERT_LOGIN_FAILURE_THRESHOLD", 50))
    from apps.audit.models import AuditLog

    since = timezone.now() - timedelta(minutes=window_min)
    failures = AuditLog.objects.filter(
        action="login_failed", created_at__gte=since
    ).count()
    if failures >= threshold:
        return [
            f"Login failures spiked: {failures} failed login(s) in the last "
            f"{window_min}m (threshold {threshold}) — possible brute force."
        ]
    logger.info("monitor: login failures=%s window=%sm threshold=%s", failures, window_min, threshold)
    return []


# Probe names (resolved at call time via module globals so each probe — and the
# data sources it reads — can be patched in tests). A probe raising is logged
# and skipped, never fatal.
_PROBE_NAMES = (
    "_check_payment_failures",
    "_check_backup_heartbeat",
    "_check_celery_queue_depth",
    "_check_login_failures",
)


@shared_task(name="monitoring.check_business_signals")
def check_business_signals():
    """Evaluate business-critical signals and alert on threshold breaches.

    Returns a short summary string. Safe no-op for alerting when no channel is
    configured (alerts are logged only). Wired to Celery Beat every few minutes.
    """
    alerts: list[str] = []
    for name in _PROBE_NAMES:
        probe = globals().get(name)
        try:
            alerts.extend(probe())
        except Exception as exc:  # noqa: BLE001 — one bad probe must not break the rest
            logger.warning("monitor: probe %s failed: %s", name, exc)

    for message in alerts:
        # send_alert is itself a no-op (logs only) when no channel is configured.
        send_alert(message, level="warning", title="FixitLab operational alert")

    if alerts:
        return f"Fired {len(alerts)} alert(s): " + " | ".join(alerts)
    return "All business signals within thresholds."
