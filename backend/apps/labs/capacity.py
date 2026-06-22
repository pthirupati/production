"""
Global lab-capacity gate (PRODUCTION_AUDIT SCALE-01).

There is a single Docker labs engine (D4). It has a finite amount of RAM/CPU,
so only a bounded number of containers can run at once. The per-user cap
(``MAX_CONCURRENT_LABS_PER_USER``) stops one user hogging the engine, but says
nothing about the platform as a whole: with enough distinct users the engine
saturates and the (N+1)th ``provision_docker_lab`` throws — surfacing to the
user as an opaque 500.

This module provides a *platform-wide* ceiling (``MAX_CONCURRENT_LABS``) that is
checked atomically BEFORE a session is created, so concurrent starts shed
gracefully (caller returns 503) instead of overshooting and crashing the engine.

Why count live rows instead of a hand-maintained counter
---------------------------------------------------------
The "current usage" is simply the number of ``LabSession`` rows that still
occupy the engine, i.e. status in ``RUNNING``/``PROVISIONING`` for an
engine-backed provider. We count those rows directly rather than incrementing a
Redis/DB counter on start and decrementing on teardown. Sessions reach a
terminal state (TERMINATED/FAILED/EXPIRED/COMPLETED) through *many* code paths —
``StopLabView``, the admin actions, ``cleanup.py``, the expiry/stuck-cleanup
Celery beats, and provisioner failure handlers. A decrement-based counter would
leak a slot every time one of those paths forgot to decrement (or double-count
on a double teardown), and would drift permanently out of sync with reality.
Counting the authoritative session rows means a slot is released the instant a
session leaves the active states — there is nothing to leak and nothing to
remember to release.

Race-safety
-----------
A naive "count then create" has a TOCTOU window: two concurrent starts at
``capacity - 1`` could both read "under cap" and both insert, overshooting. To
close it we serialise the count→create critical section behind a single
Postgres transaction-scoped advisory lock (``pg_advisory_xact_lock``). The lock
is released automatically when the surrounding transaction commits/rolls back,
so it can never be leaked. On non-Postgres backends (the SQLite test DB) the
lock is a no-op — true cross-connection concurrency is only meaningful on
Postgres, which is what production and CI use.
"""
import logging

from django.conf import settings
from django.db import connection, transaction

from apps.labs.models import LabSession

logger = logging.getLogger(__name__)

# Statuses that mean the session is still occupying engine resources.
ACTIVE_LAB_STATUSES = ("RUNNING", "PROVISIONING")

# A stable, arbitrary 64-bit key identifying the "global lab capacity" advisory
# lock. Any value works as long as it is unique within the app's advisory-lock
# namespace; this one is "FIXITLB1" loosely encoded.
_CAPACITY_ADVISORY_LOCK_KEY = 4779917001


def consumes_engine_capacity(provider: str) -> bool:
    """
    True when a session with this provider occupies the shared Docker labs
    engine and therefore counts against the global ceiling.

    ``simulation`` labs run in-process (no container) and ``aws_ec2`` /
    ``digitalocean`` labs are one VM each with their own provider-side quotas —
    none of them contend for the single D4 Docker engine, so they are excluded.
    """
    return (provider or "docker") == "docker"


def get_max_concurrent_labs() -> int:
    """Configured platform-wide concurrent-lab ceiling."""
    return int(getattr(settings, "MAX_CONCURRENT_LABS", 60))


def count_active_engine_labs() -> int:
    """Number of engine-backed sessions currently RUNNING or PROVISIONING."""
    return LabSession.objects.filter(
        provider="docker",
        status__in=ACTIVE_LAB_STATUSES,
    ).count()


def acquire_global_capacity_lock() -> None:
    """
    Serialise the capacity check across all concurrent lab-starts.

    MUST be called inside an open ``transaction.atomic()`` block: the advisory
    lock is transaction-scoped and auto-released on commit/rollback. No-op on
    non-Postgres backends (e.g. the SQLite test DB).
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_CAPACITY_ADVISORY_LOCK_KEY])


def at_global_capacity(provider: str) -> bool:
    """
    Race-safe check: is the platform at (or over) the global lab ceiling for an
    engine-backed start?

    Returns False immediately for providers that don't touch the shared engine
    (simulation / cloud). For engine-backed starts, takes the global advisory
    lock and re-counts live sessions under it so concurrent callers serialise
    and cannot collectively overshoot the cap.

    Caller contract: invoke inside the SAME ``transaction.atomic()`` block that
    then creates the ``LabSession``. Holding the lock from the check through the
    INSERT is what makes "count < cap ⇒ create" atomic.
    """
    if not consumes_engine_capacity(provider):
        return False

    acquire_global_capacity_lock()
    active = count_active_engine_labs()
    cap = get_max_concurrent_labs()
    if active >= cap:
        logger.warning(
            "Global lab capacity reached: %s/%s engine-backed labs active; "
            "shedding new start.", active, cap,
        )
        return True
    return False
