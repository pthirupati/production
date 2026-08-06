"""Per-user WebSocket connection slots, shared by every consumer.

Audit Z5-6. This logic existed only inline in `TerminalConsumer.connect`, so
`BaremetalConsumer` — added later, on the same 2-vCPU box — had no cap at all and
one account could open unlimited sockets. A limit implemented inside one consumer
is a limit the next consumer will not have; this module is the single place that
answers "may this user open another socket?".

The counter lives in the cache with a TTL slightly over an hour, so a process that
dies without releasing its slots does not permanently consume a user's quota. That
TTL is the reason the count is advisory rather than exact, and it is the right
trade: the failure mode of an exact-but-leaky counter is a user permanently locked
out of their own labs.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

MAX_WS_PER_USER = int(os.environ.get("TERMINAL_MAX_WS_PER_USER", "20"))

_WS_CONN_KEY = "ws_conn:{user_id}"
_WS_CONN_TTL = 3700  # slightly over an hour; auto-expires stale counts after a crash


def acquire_ws_slot(user_id) -> bool:
    """Try to take a connection slot for ``user_id``. True if allowed.

    Fails **open** on a cache error. A Redis blip must not lock every user out of
    every terminal on the platform — the cap exists to bound resource use under
    normal operation, not to be a security control, and the availability cost of
    failing closed here is far higher than the cost of an uncapped minute.
    """
    if user_id is None:
        return True
    try:
        from django.core.cache import cache

        key = _WS_CONN_KEY.format(user_id=user_id)
        try:
            current = cache.incr(key, delta=1)
            # `touch`, not `expire`. The original inline version called
            # `cache.expire(...)`, which only exists on django-redis — on any
            # Django-native backend it raises AttributeError, and the surrounding
            # `except Exception: pass` swallowed it and returned "allowed". So the
            # cap worked in production (django_redis) and silently failed open
            # everywhere else, including under LocMemCache in the test suite, which
            # is why it had never been exercised. `touch` is the standard BaseCache
            # API and django-redis implements it too.
            cache.touch(key, _WS_CONN_TTL)
        except ValueError:
            # incr() raises when the key is absent; seed it instead.
            cache.set(key, 1, timeout=_WS_CONN_TTL)
            current = 1
        if current > MAX_WS_PER_USER:
            cache.decr(key, delta=1)
            logger.warning(
                "User %s exceeded max WS connections (%s)", user_id, MAX_WS_PER_USER
            )
            return False
        return True
    except Exception:
        logger.warning("WS slot accounting unavailable; allowing connection", exc_info=True)
        return True


def release_ws_slot(user_id) -> None:
    """Give back a slot. Safe to call more than once for the same connection only
    if the caller clears its tracked id — see the consumers, which do."""
    if user_id is None:
        return
    try:
        from django.core.cache import cache

        key = _WS_CONN_KEY.format(user_id=user_id)
        new_val = cache.decr(key, delta=1)
        if new_val is not None and new_val <= 0:
            cache.delete(key)
    except Exception:
        # The TTL is the backstop: a slot we fail to release expires within the hour.
        logger.debug("WS slot release failed for user %s", user_id, exc_info=True)


def current_ws_count(user_id) -> int:
    """Slots currently held by ``user_id``. Test/ops introspection."""
    try:
        from django.core.cache import cache

        return int(cache.get(_WS_CONN_KEY.format(user_id=user_id)) or 0)
    except Exception:
        return 0
