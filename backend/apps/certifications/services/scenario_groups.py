"""Certification vs normal scenario listing helpers."""

from django.core.cache import cache

from apps.certifications.models import TrackScenario

_CACHE_KEY = "cert:scenario_ids"
_CACHE_TTL = 120


def certification_scenario_ids():
    """Scenario PKs mapped to any certification track objective."""
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached
    ids = set(TrackScenario.objects.values_list("scenario_id", flat=True).distinct())
    cache.set(_CACHE_KEY, ids, _CACHE_TTL)
    return ids


def invalidate_cert_scenario_cache():
    cache.delete(_CACHE_KEY)
