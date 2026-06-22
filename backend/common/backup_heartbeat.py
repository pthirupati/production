"""Backup heartbeat (dead-man's-switch) helper (PRODUCTION_AUDIT REL-01 / OBS-02).

The off-site backup cron (``scripts/ci-pg-backup-cron.sh`` → the generated
``/usr/local/bin/fixitlab-pg-backup.sh`` on the data droplet) records the
Unix epoch of the last *successful* backup so the app/monitoring can detect a
stale or missing backup and alert.

Cross-droplet contract
----------------------
In the four-droplet topology the backup runs on D3 (data) while the app runs on
D2 (app); a file written on D3 is not visible to the app. The one channel that
already spans both is **Redis**. The backup script therefore writes the epoch
to a fixed *raw* Redis key (``redis-cli SET``) using the same Redis the app
uses, and also drops a local timestamp file on D3 for node-local inspection.

This helper reads that raw key via django_redis' low-level connection. It is
deliberately tolerant: if Redis is down, the key is absent, or django_redis is
not the cache backend, it returns ``None`` (unknown) rather than raising —
"unknown" is treated by the alerting task as a missing heartbeat once the grace
period is configured, but never crashes a health probe.

The key is a *bare* string (not the Django cache-prefixed key) so an external
``redis-cli`` writer and the Django reader agree on the exact name.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Raw Redis key (NOT cache-prefixed) holding the Unix epoch (seconds) of the
# last successful pg backup. Kept in sync with scripts/ci-pg-backup-cron.sh.
BACKUP_HEARTBEAT_KEY = "fixitlab:backup:last_success_epoch"


def _redis_client():
    """Return a low-level Redis client, or None if unavailable.

    Uses django_redis' connection (the same Redis the cache uses) so we read
    the bare key the backup cron wrote. Returns None on any failure so callers
    never have to guard against import/connection errors.
    """
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception as exc:  # noqa: BLE001 — read path must never raise
        logger.debug("backup heartbeat: redis client unavailable: %s", exc)
        return None


def read_last_backup_epoch() -> Optional[int]:
    """Return the epoch (seconds) of the last successful backup, or None.

    None means "unknown" — Redis unreachable, key absent, or value unpar. The
    caller decides what to do (the alerting task treats a too-old or unknown
    heartbeat as an alert once enabled).
    """
    client = _redis_client()
    if client is None:
        return None
    try:
        raw = client.get(BACKUP_HEARTBEAT_KEY)
    except Exception as exc:  # noqa: BLE001
        logger.debug("backup heartbeat: redis get failed: %s", exc)
        return None
    if raw is None:
        return None
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "ignore")
        return int(float(str(raw).strip()))
    except (TypeError, ValueError):
        logger.debug("backup heartbeat: unparseable value %r", raw)
        return None


def backup_age_seconds() -> Optional[int]:
    """Seconds since the last successful backup, or None if unknown."""
    epoch = read_last_backup_epoch()
    if epoch is None:
        return None
    return max(0, int(time.time()) - epoch)


def write_last_backup_epoch(epoch: Optional[int] = None) -> bool:
    """Record a successful-backup heartbeat (used in tests / local runs).

    Production backups write the key from the shell cron via ``redis-cli``; this
    helper lets Python paths (and tests) set it through the same key. Returns
    True on success, False if Redis is unavailable. Never raises.
    """
    client = _redis_client()
    if client is None:
        return False
    try:
        client.set(BACKUP_HEARTBEAT_KEY, int(epoch if epoch is not None else time.time()))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug("backup heartbeat: redis set failed: %s", exc)
        return False
