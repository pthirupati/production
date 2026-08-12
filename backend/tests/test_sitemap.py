"""Tests for the dynamic full-catalog sitemap (apps.public_api.sitemaps).

Verifies the /sitemap.xml index and per-section sitemaps:
  - are public (200, no auth) and don't 500 with an unseeded/empty DB,
  - the index links to the section sitemaps,
  - seeded scenarios/tutorials/technologies appear as absolute frontend URLs.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.adminpanel.models import BlogPost
from apps.question_bank.models import LearningJourney, Project, Scenario, Technology
from apps.tutorials.models import Tutorial


class SitemapEmptyDbTests(TestCase):
    """The sitemap must render (not 500) even when the catalog is empty."""

    def setUp(self):
        self.client = APIClient()

    def test_index_ok_when_empty(self):
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        # Index links to each declared section sitemap.
        for section in ("static", "technologies", "scenarios", "tutorials", "projects", "blog", "journeys"):
            self.assertIn(f"sitemap-{section}.xml", body)

    def test_scenario_section_ok_when_empty(self):
        resp = self.client.get("/sitemap-scenarios.xml")
        self.assertEqual(resp.status_code, 200)
        # Empty catalog -> a valid, urlset with no <loc> scenario entries.
        self.assertIn("<urlset", resp.content.decode())

    def test_static_section_always_has_marketing_urls(self):
        resp = self.client.get("/sitemap-static.xml")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("/scenarios", body)
        self.assertIn("/technologies", body)
        # Audit Z6-1 remainder — these were claimed done but missing until session 26.
        for path in ("/faq", "/blog", "/privacy", "/terms", "/refunds", "/acceptable-use",
                     "/projects", "/journeys", "/mock-interviews", "/register"):
            self.assertIn(path, body)


class SitemapSeededTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.linux = Technology.objects.create(
            name="Linux", slug="linux", is_active=True, coming_soon=False
        )
        cls.soon = Technology.objects.create(
            name="Soon Tech", slug="soon-tech", is_active=True, coming_soon=True
        )
        cls.scenario = Scenario.objects.create(
            technology=cls.linux,
            slug="linux-disk-full",
            title="Disk Full",
            category="storage",
            difficulty="easy",
            description="x",
            is_active=True,
        )
        cls.inactive_scenario = Scenario.objects.create(
            technology=cls.linux,
            slug="hidden-scenario",
            title="Hidden",
            category="misc",
            difficulty="easy",
            description="x",
            is_active=False,
        )
        cls.tutorial = Tutorial.objects.create(
            title="Intro to systemd", slug="intro-to-systemd", is_published=True
        )
        cls.draft_tutorial = Tutorial.objects.create(
            title="Draft", slug="draft-tut", is_published=False
        )
        cls.project = Project.objects.create(
            technology=cls.linux, slug="linux-webapp-project", description="x", is_active=True
        )
        cls.blog = BlogPost.objects.create(
            slug="hello-fixit", title="Hello", content="body", is_published=True
        )
        cls.draft_blog = BlogPost.objects.create(
            slug="draft-post", title="Draft", content="body", is_published=False
        )
        cls.journey = LearningJourney.objects.create(
            slug="junior-linux", title="Junior Linux", is_active=True
        )

    def setUp(self):
        self.client = APIClient()

    def test_scenario_section_lists_active_scenarios(self):
        resp = self.client.get("/sitemap-scenarios.xml")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("/scenarios/linux-disk-full", body)
        # Inactive scenarios must NOT be listed.
        self.assertNotIn("/scenarios/hidden-scenario", body)

    def test_tutorial_section_lists_published_only(self):
        resp = self.client.get("/sitemap-tutorials.xml")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("/tutorials/intro-to-systemd", body)
        self.assertNotIn("/tutorials/draft-tut", body)

    def test_technology_section_excludes_coming_soon(self):
        resp = self.client.get("/sitemap-technologies.xml")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("/technologies/linux", body)
        self.assertNotIn("/technologies/soon-tech", body)

    def test_project_section_lists_project_detail_urls(self):
        resp = self.client.get("/sitemap-projects.xml")
        self.assertEqual(resp.status_code, 200)
        # §C3 added /projects/:slug — do not emit technology hubs as a stand-in.
        body = resp.content.decode()
        self.assertIn("/projects/linux-webapp-project", body)
        self.assertNotIn("/technologies/linux", body)

    def test_blog_section_lists_published_only(self):
        resp = self.client.get("/sitemap-blog.xml")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("/blog/hello-fixit", body)
        self.assertNotIn("/blog/draft-post", body)

    def test_journey_section_lists_active(self):
        resp = self.client.get("/sitemap-journeys.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("/journeys/junior-linux", resp.content.decode())

    def test_urls_are_absolute(self):
        resp = self.client.get("/sitemap-scenarios.xml")
        # Absolute URL derived from settings.SITE_URL (has a scheme + host).
        self.assertRegex(resp.content.decode(), r"https?://[^/]+/scenarios/linux-disk-full")
