"""Test helpers that re-enable behaviour `test_settings` disables by default."""
from __future__ import annotations

import contextlib

from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle


@contextlib.contextmanager
def real_throttling(**rates: str):
    """Restore genuine rate limiting for the duration of the block.

    `config/test_settings.py` patches `SimpleRateThrottle.allow_request` to always
    return True so the suite is never rate-limited — a reasonable default with one
    serious consequence: **no throttle could be tested at all**. One could be removed,
    pointed at the wrong scope, or lose its rate entirely, and every test still passed.
    The protection existed only by inspection.

    Pass scope rates to make a limit small enough to trip, e.g.::

        with real_throttling(contact="3/hour"):
            ...

    `override_settings(REST_FRAMEWORK=...)` does **not** work for this. DRF binds
    ``SimpleRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES`` as a
    CLASS attribute at import time, so changing the setting afterwards has no effect —
    a test that tried it would silently keep the 10000/minute test rate and pass
    without ever throttling. The rates are therefore patched on the class directly.
    """
    patched = SimpleRateThrottle.allow_request
    real = getattr(SimpleRateThrottle, "_real_allow_request", None)
    if real is None:  # running under production settings — nothing to restore
        yield
        return

    original_rates = SimpleRateThrottle.THROTTLE_RATES
    SimpleRateThrottle.allow_request = real
    if rates:
        SimpleRateThrottle.THROTTLE_RATES = {**original_rates, **rates}
    cache.clear()
    try:
        yield
    finally:
        SimpleRateThrottle.allow_request = patched
        SimpleRateThrottle.THROTTLE_RATES = original_rates
        cache.clear()
