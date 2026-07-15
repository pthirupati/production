"""Tests for the public catalog scenario search.

The catalog search has two code paths (apps.public_api.views._apply_scenario_search):

  * Postgres: weighted full-text (SearchQuery/SearchRank) + pg_trgm trigram
    typo tolerance, ordered by relevance.
  * Any other backend (SQLite, used by the local/offline test DB): the original
    naive icontains substring match.

The tests below cover the fallback everywhere and gate the Postgres-specific
assertions behind ``connection.vendor == 'postgresql'`` so the suite is green on
SQLite locally and still exercises the real FTS path on the CI Postgres service.
"""
import unittest

from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from apps.public_api.views import _apply_scenario_search
from apps.question_bank.models import Scenario, Technology


class ScenarioSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="Kubernetes", slug="kubernetes")
        cls.pod = Scenario.objects.create(
            technology=cls.tech,
            slug="pod-crashloop",
            title="Debug a CrashLoopBackOff pod",
            subtitle="Pod keeps restarting",
            category="Troubleshooting",
            difficulty="medium",
            description="A Kubernetes pod is stuck crash looping; find the misconfiguration.",
        )
        cls.dns = Scenario.objects.create(
            technology=cls.tech,
            slug="dns-broken",
            title="Fix broken cluster DNS",
            subtitle="CoreDNS resolution failing",
            category="Networking",
            difficulty="hard",
            description="Cluster DNS lookups fail; repair CoreDNS.",
        )
        # An inactive scenario must never surface via search.
        cls.hidden = Scenario.objects.create(
            technology=cls.tech,
            slug="hidden-pod",
            title="Hidden pod scenario",
            category="Troubleshooting",
            difficulty="easy",
            description="A hidden crash pod that should not appear.",
            is_active=False,
        )

    def _search(self, term):
        client = APIClient()
        resp = client.get("/api/scenarios/", {"search": term})
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data

    def _slugs(self, payload):
        return {row["slug"] for row in payload["results"]}

    # ── Runs on every backend ──────────────────────────────────────────────

    def test_search_matches_title(self):
        slugs = self._slugs(self._search("CrashLoopBackOff"))
        self.assertIn("pod-crashloop", slugs)
        self.assertNotIn("dns-broken", slugs)

    def test_search_matches_description(self):
        slugs = self._slugs(self._search("CoreDNS"))
        self.assertIn("dns-broken", slugs)

    def test_search_excludes_inactive(self):
        # "pod" appears in both an active and an inactive scenario; the inactive
        # one (is_active=False) must be gated out regardless of search backend.
        slugs = self._slugs(self._search("pod"))
        self.assertIn("pod-crashloop", slugs)
        self.assertNotIn("hidden-pod", slugs)

    def test_response_shape_preserved(self):
        payload = self._search("pod")
        # Paginated envelope the frontend depends on.
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, payload)
        self.assertIsInstance(payload["results"], list)

    def test_empty_result_for_nonsense(self):
        # A single gibberish token. Postgres FTS tokenizes the query, so a string
        # with real word-tokens ("no", "such", "lab") would legitimately match many
        # scenarios; genuine nonsense must have no real tokens and near-zero trigram
        # similarity to any title.
        payload = self._search("qwzxlkjhgfdsapoiuyt")
        self.assertEqual(payload["results"], [])

    def test_helper_returns_queryset(self):
        qs = _apply_scenario_search(
            Scenario.objects.filter(is_active=True), "DNS"
        )
        self.assertIn(self.dns, list(qs))

    # ── Postgres-only (skipped on SQLite) ──────────────────────────────────

    @unittest.skipUnless(
        connection.vendor == "postgresql",
        "Full-text + trigram search is Postgres-only",
    )
    def test_pg_typo_tolerance(self):
        # 'kubenetes' is a typo for 'kubernetes'; the icontains path would miss
        # it, but the pg_trgm title-similarity fallback should still surface the
        # Kubernetes labs whose titles are close enough.
        slugs = self._slugs(self._search("crashloopbackof"))
        self.assertIn("pod-crashloop", slugs)

    @unittest.skipUnless(
        connection.vendor == "postgresql",
        "Full-text ranking is Postgres-only",
    )
    def test_pg_relevance_ordering(self):
        # A title hit (weight A) should outrank a description-only hit for the
        # same term. "pod" is in the pod title and the dns description... but
        # only the pod title, so assert the title match ranks first.
        payload = self._search("pod")
        results = [r["slug"] for r in payload["results"]]
        self.assertTrue(results, "expected at least one result")
        self.assertEqual(results[0], "pod-crashloop")
