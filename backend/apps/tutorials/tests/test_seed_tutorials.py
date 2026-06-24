"""Verify seed_tutorials loads the built-in tutorials AND the original
tutorials authored as data in data/tutorials_extra.json."""

from django.core.management import call_command
from django.test import TestCase

from apps.tutorials.models import Tutorial, TutorialSection


class SeedTutorialsTest(TestCase):
    def test_seed_loads_builtin_and_extra(self):
        call_command("seed_tutorials")
        # 8 built-in + 32 original (data/tutorials_extra.json).
        self.assertGreaterEqual(Tutorial.objects.count(), 750)
        self.assertGreater(TutorialSection.objects.count(), 15000)

    def test_course_module_has_full_sections(self):
        call_command("seed_tutorials")
        t = Tutorial.objects.filter(course_slug="database-engineering-zero-hero").order_by("module_order").first()
        self.assertIsNotNone(t)
        self.assertEqual(t.level_track, "beginner")
        self.assertGreaterEqual(t.sections.count(), 20)
        first = t.sections.order_by("order").first()
        self.assertGreater(len(first.body or ""), 2500, "Theory section should have book-level prose")
        notes = t.sections.filter(heading="Notes and key takeaways").first()
        self.assertIsNotNone(notes)
        self.assertIn("checklist", (notes.body or "").lower())

    def test_grafana_module_has_book_content(self):
        call_command("seed_tutorials")
        t = Tutorial.objects.filter(course_slug="grafana-visualization-zero-hero").order_by("module_order").first()
        self.assertIsNotNone(t)
        self.assertGreaterEqual(t.sections.count(), 20)
        theory = t.sections.filter(heading="Theory").first()
        self.assertGreater(len(theory.body or ""), 2500)
        self.assertIn("Grafana", theory.body)

    def test_extra_tutorial_has_sections(self):
        call_command("seed_tutorials")
        t = Tutorial.objects.filter(
            slug="linux-file-permissions-ownership-deep-dive"
        ).first()
        self.assertIsNotNone(t)
        self.assertEqual(t.topic, "Linux")
        self.assertGreaterEqual(t.sections.count(), 5)
        first = t.sections.order_by("order").first()
        self.assertTrue(first.heading)

    def test_seed_is_idempotent(self):
        call_command("seed_tutorials")
        n1 = Tutorial.objects.count()
        call_command("seed_tutorials")
        self.assertEqual(Tutorial.objects.count(), n1)
