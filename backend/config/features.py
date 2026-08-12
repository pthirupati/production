"""Runtime feature-flag lookup (audit Z6-15).

Read flags through :func:`feature_enabled`, never by importing
``settings.FEATURES`` and branching at module scope::

    # WRONG -- evaluated once at import, caches for the worker's whole life,
    # so flipping the flag appears to do nothing until a restart.
    from django.conf import settings
    if settings.FEATURES["currency_conversion"]:
        do_the_thing()

    # RIGHT -- re-read on every call.
    from config.features import feature_enabled
    if feature_enabled("currency_conversion"):
        do_the_thing()

The indirection exists purely so that ``override_settings`` in tests and a live
settings reload both take effect immediately. It is intentionally thin: there is
no database table and no cache, because a flag lookup that can fail or go stale
is worse than no flag at all.
"""

from django.conf import settings


class UnknownFeature(KeyError):
    """Raised when code asks for a flag that is not declared in settings.

    Deliberately loud. A typo'd flag name that silently returned False would
    disable a feature in production and look exactly like a working kill switch.
    """


def feature_enabled(name: str) -> bool:
    """Return whether feature ``name`` is currently on.

    Resolved on every call against the *live* settings object, so
    ``override_settings`` and a settings reload are both honoured immediately.
    """
    flags = getattr(settings, "FEATURES", {})
    try:
        return bool(flags[name])
    except KeyError:
        raise UnknownFeature(
            f"Unknown feature flag {name!r}. Declare it in settings.FEATURES "
            f"(known: {sorted(flags)})."
        ) from None


def all_features() -> dict:
    """Snapshot of every flag, for health/debug endpoints and tests."""
    return dict(getattr(settings, "FEATURES", {}))
