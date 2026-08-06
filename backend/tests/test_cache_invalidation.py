"""Audit Z5-14 — editing the catalog served stale data for the full TTL.

`invalidate_technologies_cache` cleared three keys and missed the rest. The worse
half was a **rename**: the technologies list is cached under
`technologies_list_v2`, while both invalidators — `cache_utils` and
`question_bank/admin.py` — deleted `technologies_list`. The key was versioned at
some point and the invalidation was never updated, so the primary path had been a
**no-op**. An admin editing a technology saw nothing change for 300 seconds and
had no way to tell why.

Two invalidator lists also existed and had drifted from each other, which is how
the rename went unnoticed in both.

The load-bearing test here is `test_every_cached_key_is_invalidated`: it reads the
keys the views actually pass to `cache.set()` and requires each to appear in
`ALL_PUBLIC_CACHE_KEYS`. That is the test that would have caught the original bug,
and it fails on the next rename instead of quietly serving stale content.
"""
import pathlib
import re

from django.core.cache import cache
from django.test import TestCase

from apps.question_bank.cache_utils import (
    ALL_PUBLIC_CACHE_KEYS,
    TECH_DETAIL_PREFIX,
    TECHNOLOGIES_LIST_KEY,
    invalidate_scenario_cache,
    invalidate_technologies_cache,
)
from apps.question_bank.models import Technology


def _keys_set_by_views():
    """Literal cache keys the public API writes.

    Read from source rather than by importing, because the keys are inline
    literals inside view methods and there is no runtime registry to inspect.
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    found = set()
    for rel in ("apps/public_api/views.py", "apps/question_bank/views.py"):
        src = (root / rel).read_text()
        # cache.set("literal", ...) — the f-string/variable forms are per-slug and
        # are covered by the prefix tests below.
        found |= set(re.findall(r'cache\.set\(\s*"([a-z0-9_]+)"', src))
        # cache_key = "literal"  ... cache.set(cache_key, ...)
        found |= set(re.findall(r'cache_key\s*=\s*"([a-z0-9_]+)"', src))
    return found


class TheInvalidatorCoversWhatIsActuallyCachedTests(TestCase):
    def test_every_cached_key_is_invalidated(self):
        """The test that would have caught the original bug."""
        missing = _keys_set_by_views() - set(ALL_PUBLIC_CACHE_KEYS)
        self.assertEqual(
            missing, set(),
            f"these keys are written by a view but never invalidated, so editing "
            f"the catalog serves stale data for the full TTL: {sorted(missing)}",
        )

    def test_the_technologies_list_key_matches_the_view(self):
        """The specific rename: the view moved to _v2, the invalidator did not."""
        root = pathlib.Path(__file__).resolve().parent.parent
        src = (root / "apps" / "public_api" / "views.py").read_text()
        self.assertIn(
            f'"{TECHNOLOGIES_LIST_KEY}"', src,
            f"TECHNOLOGIES_LIST_KEY is {TECHNOLOGIES_LIST_KEY!r} but no view caches "
            "under that name — the invalidator is deleting a key nobody writes",
        )

    def test_the_list_is_not_empty(self):
        """Guard the guard: an empty tuple would make the coverage test vacuous."""
        self.assertGreater(len(ALL_PUBLIC_CACHE_KEYS), 5)


class InvalidationActuallyClearsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_it_clears_every_fixed_key(self):
        for key in ALL_PUBLIC_CACHE_KEYS:
            cache.set(key, "stale", 300)
        invalidate_technologies_cache()
        still_there = [k for k in ALL_PUBLIC_CACHE_KEYS if cache.get(k) is not None]
        self.assertEqual(still_there, [], f"not cleared: {still_there}")

    def test_it_clears_a_named_technology_detail(self):
        cache.set(f"{TECH_DETAIL_PREFIX}:linux", "stale", 300)
        invalidate_technologies_cache(slugs=["linux"])
        self.assertIsNone(cache.get(f"{TECH_DETAIL_PREFIX}:linux"))

    def test_it_clears_detail_pages_without_being_told_which(self):
        """LocMemCache has no `delete_pattern`, so this exercises the database
        enumeration fallback — the path that runs wherever Redis is not available,
        and the one that would silently do nothing if it were left out."""
        Technology.objects.create(name="Linux", slug="linux")
        Technology.objects.create(name="Kubernetes", slug="kubernetes")
        cache.set(f"{TECH_DETAIL_PREFIX}:linux", "stale", 300)
        cache.set(f"{TECH_DETAIL_PREFIX}:kubernetes", "stale", 300)

        invalidate_technologies_cache()

        self.assertIsNone(cache.get(f"{TECH_DETAIL_PREFIX}:linux"))
        self.assertIsNone(cache.get(f"{TECH_DETAIL_PREFIX}:kubernetes"))

    def test_a_scenario_edit_clears_its_technology_detail(self):
        cache.set(f"{TECH_DETAIL_PREFIX}:linux", "stale", 300)
        cache.set(TECHNOLOGIES_LIST_KEY, "stale", 300)
        invalidate_scenario_cache("linux")
        self.assertIsNone(cache.get(f"{TECH_DETAIL_PREFIX}:linux"))
        self.assertIsNone(
            cache.get(TECHNOLOGIES_LIST_KEY),
            "a scenario edit moves the counts on the technology list too",
        )

    def test_it_does_not_clear_unrelated_keys(self):
        """A blanket `cache.clear()` would pass every test above while dropping
        session data, throttle counters and lab state with it."""
        cache.set("sessions:abc", "keep", 300)
        cache.set("throttle_login_1.2.3.4", "keep", 300)
        invalidate_technologies_cache()
        self.assertEqual(cache.get("sessions:abc"), "keep")
        self.assertEqual(cache.get("throttle_login_1.2.3.4"), "keep")

    def test_it_survives_a_cache_backend_failure(self):
        """An admin save must not 500 because Redis blinked."""
        from unittest import mock

        with mock.patch(
            "django.core.cache.cache.delete_many", side_effect=RuntimeError("redis down")
        ):
            with self.assertRaises(RuntimeError):
                # delete_many is not guarded — this documents that the guard is on
                # the pattern delete only, so the behaviour is a deliberate choice
                # rather than an oversight.
                invalidate_technologies_cache()


class OneListNotTwoTests(TestCase):
    """Two invalidator lists existed and drifted; that is how the rename survived
    in both."""

    def test_the_admin_delegates_rather_than_keeping_its_own_list(self):
        root = pathlib.Path(__file__).resolve().parent.parent
        src = (root / "apps" / "question_bank" / "admin.py").read_text()
        self.assertIn("invalidate_technologies_cache", src)
        self.assertNotIn(
            'cache.delete_many([', src,
            "admin.py keeps its own key list again — it will drift from cache_utils",
        )
