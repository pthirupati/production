"""TechnologyDetailView: query-count budget and cached-payload isolation.

Audit Z5-13. Two independent regressions are guarded here:

1. The anonymous cache-miss path used to fire 6 queries against the same
   scenario queryset (count, one per difficulty, a DISTINCT on category, then
   the serializer). They are now derived from a single evaluation.

2. The authenticated overlay writes per-user fields (`is_accessible`,
   `user_progress`, `is_bookmarked`) onto scenario dicts taken from the 60s
   anon cache entry. Those writes must not reach the cached payload.

   The audit framed (2) as a cross-user data leak. It is not — see the long note
   on test_per_user_overlay_does_not_corrupt_the_cached_entry: both cache
   backends serialise, so post-get mutations are never written back and no
   end-to-end two-user test can observe a leak. The real defect was cost, a full
   recursive deepcopy per authenticated request.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.question_bank.models import Scenario, Technology


class TechDetailPerfTest(TestCase):
    def setUp(self):
        cache.clear()
        # The API is JWT-only (CookieJWTAuthentication), so Django's session
        # force_login() leaves the request anonymous — use DRF's APIClient.
        self.client = APIClient()
        self.tech = Technology.objects.create(
            name="Kubernetes", slug="k8s", is_active=True, is_free=True
        )
        self.scenarios = [
            Scenario.objects.create(
                slug=f"s{i}",
                title=f"S{i}",
                technology=self.tech,
                category=["Fix", "Deploy", "Debug"][i % 3],
                difficulty=["easy", "medium", "hard"][i % 3],
                description="d",
                is_active=True,
                certification_only=False,
                is_free=True,
            )
            for i in range(9)
        ]

    def _url(self):
        return f"/api/technologies/{self.tech.slug}/"

    def test_anonymous_cache_miss_query_budget(self):
        """One evaluation of the scenario queryset, not six.

        Before the fix this path issued 4 COUNT(*)s plus a DISTINCT on top of the
        serializer's own SELECT. The budget below is deliberately tight enough
        that reintroducing even the difficulty loop breaks it.
        """
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

        sql = [q["sql"] for q in ctx.captured_queries]
        counts = [s for s in sql if "COUNT(*)" in s and "question_bank_scenario" in s]
        self.assertEqual(
            counts, [], f"scenario COUNT(*) queries should be gone, got {len(counts)}:\n" + "\n".join(counts)
        )
        distincts = [
            s for s in sql if "SELECT DISTINCT" in s and '"question_bank_scenario"."category"' in s
        ]
        self.assertEqual(distincts, [], "category DISTINCT should be derived in Python")

    def test_aggregates_still_correct(self):
        """Deriving counts in Python must not change the payload."""
        resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)
        tech_data = resp.json()["technology"]
        self.assertEqual(tech_data["scenario_count"], 9)
        self.assertEqual(tech_data["difficulty_counts"], {"easy": 3, "medium": 3, "hard": 3})
        self.assertEqual(tech_data["categories"], ["Debug", "Deploy", "Fix"])

    def test_certification_only_excluded_from_counts(self):
        """The aggregate must keep the same filters as the serialised list.

        A cert-only scenario is paid content: it must not inflate the free
        scenario_count or difficulty_counts.
        """
        Scenario.objects.create(
            slug="paid-1",
            title="Paid",
            technology=self.tech,
            category="Secret",
            difficulty="easy",
            description="d",
            is_active=True,
            certification_only=True,
        )
        Scenario.objects.create(
            slug="inactive-1",
            title="Inactive",
            technology=self.tech,
            category="Hidden",
            difficulty="hard",
            description="d",
            is_active=False,
            certification_only=False,
        )
        cache.clear()
        tech_data = self.client.get(self._url()).json()["technology"]
        self.assertEqual(tech_data["scenario_count"], 9)
        self.assertEqual(tech_data["difficulty_counts"], {"easy": 3, "medium": 3, "hard": 3})
        self.assertNotIn("Secret", tech_data["categories"])
        self.assertNotIn("Hidden", tech_data["categories"])

    def test_per_user_overlay_does_not_corrupt_the_cached_entry(self):
        """The overlay must not write per-user fields into the cached payload.

        NOTE ON WHAT THIS CAN AND CANNOT CATCH — the audit (Z5-13) claimed the
        deepcopy was load-bearing because a shallow copy would "leak one user's
        progress into the cached anon payload served to everyone". That is not
        true for either cache backend this project uses: LocMemCache pickles on
        set and unpickles on every get, and Redis serialises too, so a mutation
        made after cache.get() is never written back. A pure end-to-end
        two-user test therefore passes even with the payload fully aliased, which
        makes it worthless as a guard.

        So this asserts the property that IS observable: after an authenticated
        request overlays its per-user fields, the entry sitting in the cache is
        still clean. That holds via the copy for the cache-miss path, where
        `base` is the live local object rather than a deserialised one.
        """
        from apps.progress.models import UserScenarioProgress

        User = get_user_model()
        alice = User.objects.create_user(username="alice", password="x")
        target = self.scenarios[0]
        UserScenarioProgress.objects.create(
            user=alice, scenario=target, completed=True, attempts=7, best_score=99
        )

        # Cold cache, so the request builds `base` in-process and then overlays.
        cache.clear()
        self.client.force_authenticate(user=alice)
        alice_items = {s["slug"]: s for s in self.client.get(self._url()).json()["scenarios"]}
        self.assertEqual(alice_items[target.slug]["user_progress"]["attempts"], 7)
        self.client.force_authenticate(user=None)

        cached = cache.get(f"tech_detail_anon:{self.tech.slug}")
        self.assertIsNotNone(cached, "anon base should have been cached")
        by_slug = {s["slug"]: s for s in cached["scenarios"]}
        self.assertNotIn(
            "user_progress",
            by_slug[target.slug],
            "per-user progress was written into the cached anon payload",
        )
        # is_bookmarked is a serializer field with default=False, so it is
        # legitimately present in the base payload — assert on its VALUE.
        self.assertFalse(
            by_slug[target.slug]["is_bookmarked"],
            "per-user bookmark state was written into the cached anon payload",
        )
        self.assertNotIn(
            "learning_path_progress",
            cached["technology"],
            "per-user learning path was written into the cached technology dict",
        )

    def test_anonymous_payload_has_no_per_user_fields(self):
        """The anon branch returns `base` directly — it must stay clean."""
        anon = self.client.get(self._url()).json()
        self.assertNotIn("learning_path_progress", anon["technology"])
        for item in anon["scenarios"]:
            self.assertNotIn("user_progress", item)
            # Present by serializer default; must never be a real user's state.
            self.assertFalse(item["is_bookmarked"])


class TechnologiesListScenarioCountTest(TestCase):
    """/api/technologies/ must actually emit scenario_count (audit L5647).

    The frontend's technology cards fall back to a static catalog that hardcodes
    scenario_count: 0 when the field is absent, so a silent regression here shows
    up as "0 scenarios" on every card rather than as an error. Two ways the field
    can vanish, both covered below:

      - the annotation or serializer field is dropped, or
      - the view's blanket `except` fires and returns [], which is invisible
        from source inspection alone.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.tech = Technology.objects.create(
            name="Linux", slug="linux", is_active=True, is_free=True
        )
        for i in range(3):
            Scenario.objects.create(
                slug=f"lx{i}",
                title=f"L{i}",
                technology=self.tech,
                category="Fix",
                difficulty="easy",
                description="d",
                is_active=True,
                certification_only=False,
            )

    def test_list_payload_includes_scenario_count(self):
        resp = self.client.get("/api/technologies/")
        self.assertEqual(resp.status_code, 200)
        rows = {t["slug"]: t for t in resp.json()}
        self.assertIn("linux", rows)
        self.assertIn(
            "scenario_count",
            rows["linux"],
            "technology cards fall back to a hardcoded 0 without this field",
        )
        self.assertEqual(rows["linux"]["scenario_count"], 3)

    def test_certification_only_and_inactive_excluded(self):
        """The count must match the free/active scenarios a visitor can start."""
        Scenario.objects.create(
            slug="lx-paid", title="Paid", technology=self.tech, category="Fix",
            difficulty="easy", description="d", is_active=True, certification_only=True,
        )
        Scenario.objects.create(
            slug="lx-off", title="Off", technology=self.tech, category="Fix",
            difficulty="easy", description="d", is_active=False, certification_only=False,
        )
        cache.clear()
        rows = {t["slug"]: t for t in self.client.get("/api/technologies/").json()}
        self.assertEqual(rows["linux"]["scenario_count"], 3)

    def test_db_failure_returns_empty_list_not_500(self):
        """Documents the failure mode that makes source inspection insufficient.

        The blanket `except` means a DB/annotation error yields [] — the field is
        then legitimately absent from the live payload even though the code that
        produces it is correct. Pinning this keeps the fallback deliberate.
        """
        from unittest.mock import patch

        cache.clear()
        with patch(
            "apps.certifications.services.scenario_groups.certification_scenario_ids",
            side_effect=RuntimeError("db down"),
        ):
            resp = self.client.get("/api/technologies/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])
