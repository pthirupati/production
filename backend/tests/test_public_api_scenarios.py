"""Tests for the public scenario-browsing endpoints.

Covers the bugs fixed in the scenario browsing experience:
  - filtering the list by technology (id AND slug) returns ONLY that
    technology's scenarios,
  - a slug accidentally passed as the integer `technology` param must not 500,
  - the list endpoint never 500s for anonymous users or empty/garbage params,
  - the `is_accessible` subscription flag is present and correct for anon users
    (free scenarios accessible, paid scenarios locked but still listed).
"""

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.question_bank.models import Scenario, Technology


class ScenariosListFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.vmware = Technology.objects.create(name="VMware", slug="vmware", is_active=True)
        cls.linux = Technology.objects.create(name="Linux", slug="linux", is_active=True)

        # 2 VMware scenarios (one free, one paid), 1 Linux scenario.
        cls.vm_free = Scenario.objects.create(
            technology=cls.vmware, slug="vmware-guest-powered-off",
            title="Guest Powered Off", category="compute",
            difficulty="easy", description="x", is_free=True, is_active=True,
        )
        cls.vm_paid = Scenario.objects.create(
            technology=cls.vmware, slug="vmware-ha-failure",
            title="HA Failure", category="ha",
            difficulty="hard", description="x", is_free=False, is_active=True,
        )
        cls.linux_paid = Scenario.objects.create(
            technology=cls.linux, slug="linux-disk-full",
            title="Disk Full", category="storage",
            difficulty="medium", description="x", is_free=False, is_active=True,
        )

    def setUp(self):
        # The anonymous scenario list is cached for 2 min in a process-global
        # LocMemCache under test settings; clear it so a sibling test's cached
        # slice (e.g. a fixture with different scenarios) can't leak in here.
        cache.clear()
        self.client = APIClient()

    def _results(self, resp):
        data = resp.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    def test_filter_by_technology_slug_returns_only_that_tech(self):
        resp = self.client.get("/api/scenarios/", {"technology_slug": "vmware"})
        self.assertEqual(resp.status_code, 200)
        slugs = {s["slug"] for s in self._results(resp)}
        self.assertEqual(slugs, {"vmware-guest-powered-off", "vmware-ha-failure"})
        self.assertNotIn("linux-disk-full", slugs)

    def test_slug_passed_as_technology_id_does_not_500(self):
        # Regression: TechnologyDetail linked to /scenarios?technology=<slug>,
        # which the backend read as technology_id=<slug> and raised ValueError.
        resp = self.client.get("/api/scenarios/", {"technology": "vmware"})
        self.assertEqual(resp.status_code, 200)
        slugs = {s["slug"] for s in self._results(resp)}
        self.assertEqual(slugs, {"vmware-guest-powered-off", "vmware-ha-failure"})

    def test_filter_by_numeric_technology_id(self):
        resp = self.client.get("/api/scenarios/", {"technology": str(self.linux.id)})
        self.assertEqual(resp.status_code, 200)
        slugs = {s["slug"] for s in self._results(resp)}
        self.assertEqual(slugs, {"linux-disk-full"})

    def test_empty_and_anonymous_does_not_500(self):
        resp = self.client.get("/api/scenarios/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self._results(resp)), 3)

    def test_unknown_technology_slug_returns_empty_not_error(self):
        resp = self.client.get("/api/scenarios/", {"technology_slug": "does-not-exist"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._results(resp), [])

    def test_garbage_page_size_does_not_500(self):
        resp = self.client.get("/api/scenarios/", {"page_size": "abc"})
        self.assertEqual(resp.status_code, 200)

    def test_accessible_flag_for_anonymous_user(self):
        # Anonymous: free scenario accessible, paid scenarios locked, but ALL
        # scenarios are still returned (gating only, never hidden).
        resp = self.client.get("/api/scenarios/")
        self.assertEqual(resp.status_code, 200)
        by_slug = {s["slug"]: s for s in self._results(resp)}
        self.assertTrue(by_slug["vmware-guest-powered-off"]["is_accessible"])
        self.assertFalse(by_slug["vmware-ha-failure"]["is_accessible"])
        self.assertFalse(by_slug["linux-disk-full"]["is_accessible"])

    def test_difficulty_filter(self):
        resp = self.client.get("/api/scenarios/", {"difficulty": "hard"})
        self.assertEqual(resp.status_code, 200)
        slugs = {s["slug"] for s in self._results(resp)}
        self.assertEqual(slugs, {"vmware-ha-failure"})

    def test_free_filter(self):
        resp = self.client.get("/api/scenarios/", {"free": "1"})
        self.assertEqual(resp.status_code, 200)
        slugs = {s["slug"] for s in self._results(resp)}
        self.assertEqual(slugs, {"vmware-guest-powered-off"})


class ScenarioDetailAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tech = Technology.objects.create(name="Kubernetes", slug="kubernetes", is_active=True)
        cls.free = Scenario.objects.create(
            technology=cls.tech, slug="k8s-pod-pending", title="Pod Pending",
            category="scheduling", difficulty="easy", description="x",
            is_free=True, is_active=True,
        )
        cls.paid = Scenario.objects.create(
            technology=cls.tech, slug="k8s-crashloop", title="CrashLoop",
            category="workloads", difficulty="hard", description="x",
            is_free=False, is_active=True,
        )

    def setUp(self):
        cache.clear()  # avoid anon-response cache leaking between tests
        self.client = APIClient()

    def test_detail_viewable_anonymous_and_flags_access(self):
        # Paid scenario is viewable by anon (200) but flagged not accessible.
        resp = self.client.get("/api/scenarios/k8s-crashloop/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["is_accessible"])

        resp = self.client.get("/api/scenarios/k8s-pod-pending/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["is_accessible"])

    def test_detail_unknown_slug_404s(self):
        resp = self.client.get("/api/scenarios/nope/")
        self.assertEqual(resp.status_code, 404)
