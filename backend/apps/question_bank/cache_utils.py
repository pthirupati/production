"""Cache helpers for the question_bank public API.

Audit Z5-14. Invalidation cleared three keys and missed the rest, so editing a
scenario served stale data for the full TTL.

The worse half was not the missing keys, it was a **rename**. The technologies
list is cached under `technologies_list_v2` (`public_api/views.py`), while both
invalidators — this one and `question_bank/admin.py` — deleted `technologies_list`.
The key was versioned at some point and the invalidation was never updated, so the
primary path had been a **no-op**: admin edits to a technology were invisible for
the full 300-second TTL and nothing indicated why.

That is the argument for `ALL_PUBLIC_CACHE_KEYS` below. Listing the keys in one
place next to the code that clears them makes the same drift obvious rather than
silent, and `test_cache_invalidation.py` cross-checks this list against the keys
the views actually `cache.set()`, so a future rename fails a test instead of
quietly serving stale content.
"""

import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

TECHNOLOGIES_LIST_KEY = "technologies_list_v2"

# Every fixed-name key the public API caches under. Per-slug keys are handled
# separately below, since they cannot be enumerated without hitting the database.
ALL_PUBLIC_CACHE_KEYS = (
    TECHNOLOGIES_LIST_KEY,
    "technologies_list",       # pre-v2 name; harmless to delete, and a stray
                               # value under it would otherwise never expire
    "platform_stats",
    "public_platform_stats",
    "platform_config_public",
    "categories_list",
    "tags_list",
    "campaigns_active_anon",
    "scenarios_list_all",
    "pricing_technologies",
)

# `tech_detail_anon:{slug}` is written per technology. django-redis exposes
# `delete_pattern`, which the codebase never used.
TECH_DETAIL_PREFIX = "tech_detail_anon"


def _delete_pattern(pattern: str) -> bool:
    """Best-effort wildcard delete. True if the backend supported it.

    LocMemCache (the test backend) has no `delete_pattern`, and a Redis outage
    should degrade to a stale page rather than a 500 on an admin save — so this
    never raises. Callers fall back to explicit per-slug deletes.
    """
    try:
        cache.delete_pattern(pattern)
        return True
    except AttributeError:
        return False
    except Exception as exc:
        logger.warning("Cache pattern delete failed for %s: %s", pattern, exc)
        return False


def invalidate_technologies_cache(slugs=None) -> None:
    """Clear every public cache entry affected by a catalog change.

    `slugs` narrows the per-technology detail invalidation. Without it this falls
    back to a wildcard delete, and if the backend cannot do wildcards the detail
    entries are enumerated from the database instead — leaving them stale is the
    exact bug this function exists to fix.
    """
    cache.delete_many(list(ALL_PUBLIC_CACHE_KEYS))

    if slugs:
        cache.delete_many([f"{TECH_DETAIL_PREFIX}:{s}" for s in slugs if s])
        return

    if not _delete_pattern(f"{TECH_DETAIL_PREFIX}:*"):
        # No wildcard support. Enumerate from the database rather than give up:
        # the technology table is small (tens of rows).
        try:
            from .models import Technology

            known = list(Technology.objects.values_list("slug", flat=True))
            if known:
                cache.delete_many([f"{TECH_DETAIL_PREFIX}:{s}" for s in known])
        except Exception as exc:
            logger.warning("Could not enumerate technology slugs to invalidate: %s", exc)


def invalidate_scenario_cache(technology_slug: str | None = None) -> None:
    """Clear what a scenario edit affects.

    A scenario change moves the counts on the technology list and its own
    technology's detail page, so the blast radius is the same as a catalog change.
    Kept as a separate name so call sites read as what they mean.
    """
    invalidate_technologies_cache(slugs=[technology_slug] if technology_slug else None)
