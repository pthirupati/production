"""Tests for the public Tutorials API (list + detail) and the seed command."""

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tutorials.models import Tutorial, TutorialSection


class TutorialModelTests(TestCase):
    def test_slug_autofills_from_title(self):
        t = Tutorial.objects.create(title="My First Tutorial", topic="Linux")
        self.assertEqual(t.slug, "my-first-tutorial")

    def test_meta_fallbacks(self):
        t = Tutorial.objects.create(title="X", topic="Linux", summary="A summary")
        # No explicit SEO fields → fall back to title/summary.
        self.assertEqual(t.meta_title, "X")
        self.assertEqual(t.meta_description, "A summary")
        t.seo_title = "SEO X"
        t.seo_description = "SEO desc"
        self.assertEqual(t.meta_title, "SEO X")
        self.assertEqual(t.meta_description, "SEO desc")


class TutorialApiTests(TestCase):
    def setUp(self):
        cache.clear()  # avoid throttle state leaking between tests
        self.client = APIClient()
        self.t1 = Tutorial.objects.create(
            slug="linux-basics", title="Linux Basics", topic="Linux",
            summary="Shell basics", playground_slug="linux", order=1,
        )
        TutorialSection.objects.create(
            tutorial=self.t1, order=0, heading="Intro", body="Body text",
            code="ls -la", code_language="bash",
        )
        self.t2 = Tutorial.objects.create(
            slug="git-basics", title="Git Basics", topic="Git",
            summary="Version control", playground_slug="git", order=2,
        )
        # Unpublished tutorial must never appear publicly.
        self.hidden = Tutorial.objects.create(
            slug="secret", title="Secret Draft", topic="Linux",
            is_published=False, order=3,
        )

    def test_list_is_public_and_excludes_unpublished(self):
        resp = self.client.get("/api/tutorials/")
        self.assertEqual(resp.status_code, 200)
        slugs = {t["slug"] for t in resp.data["tutorials"]}
        self.assertEqual(slugs, {"linux-basics", "git-basics"})
        self.assertNotIn("secret", slugs)

    def test_list_returns_topics_and_section_counts(self):
        resp = self.client.get("/api/tutorials/")
        self.assertIn("Linux", resp.data["topics"])
        self.assertIn("Git", resp.data["topics"])
        linux = next(t for t in resp.data["tutorials"] if t["slug"] == "linux-basics")
        self.assertEqual(linux["section_count"], 1)

    def test_list_filter_by_topic(self):
        resp = self.client.get("/api/tutorials/", {"topic": "git"})
        slugs = {t["slug"] for t in resp.data["tutorials"]}
        self.assertEqual(slugs, {"git-basics"})

    def test_detail_returns_ordered_sections(self):
        resp = self.client.get("/api/tutorials/linux-basics/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "Linux Basics")
        self.assertEqual(len(resp.data["sections"]), 1)
        self.assertEqual(resp.data["sections"][0]["code"], "ls -la")
        self.assertEqual(resp.data["playground_slug"], "linux")

    def test_detail_includes_related_same_topic(self):
        Tutorial.objects.create(
            slug="linux-advanced", title="Linux Advanced", topic="Linux", order=5,
        )
        resp = self.client.get("/api/tutorials/linux-basics/")
        related_slugs = {r["slug"] for r in resp.data["related"]}
        self.assertIn("linux-advanced", related_slugs)
        self.assertNotIn("linux-basics", related_slugs)  # never includes self

    def test_detail_unpublished_returns_404(self):
        resp = self.client.get("/api/tutorials/secret/")
        self.assertEqual(resp.status_code, 404)

    def test_detail_missing_returns_404(self):
        resp = self.client.get("/api/tutorials/does-not-exist/")
        self.assertEqual(resp.status_code, 404)


class SeedTutorialsCommandTests(TestCase):
    def test_seed_is_idempotent(self):
        cache.clear()
        call_command("seed_tutorials")
        first_count = Tutorial.objects.count()
        first_sections = TutorialSection.objects.count()
        self.assertGreaterEqual(first_count, 8)
        self.assertGreater(first_sections, 0)

        # Re-running must not duplicate rows (update_or_create + section replace).
        call_command("seed_tutorials")
        self.assertEqual(Tutorial.objects.count(), first_count)
        self.assertEqual(TutorialSection.objects.count(), first_sections)

    def test_seeded_tutorials_are_published_and_have_sections(self):
        call_command("seed_tutorials")
        for t in Tutorial.objects.all():
            self.assertTrue(t.is_published)
            self.assertGreater(t.sections.count(), 0, t.slug)

    def test_seeded_tutorials_link_to_known_playgrounds(self):
        from apps.labs import playground_engine as pg

        call_command("seed_tutorials")
        for t in Tutorial.objects.exclude(playground_slug=""):
            self.assertIsNotNone(
                pg.get_definition(t.playground_slug),
                f"{t.slug} links to unknown playground {t.playground_slug}",
            )
