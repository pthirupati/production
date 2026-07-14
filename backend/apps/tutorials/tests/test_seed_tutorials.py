"""Verify seed_tutorials loads the built-in tutorials AND the original
tutorials authored as data in data/tutorials_extra.json."""

from django.core.management import call_command
from django.test import TestCase

from apps.tutorials.models import Tutorial, TutorialSection


class SeedTutorialsTest(TestCase):
    def test_seed_loads_builtin_and_extra(self):
        call_command("seed_tutorials")
        # 8 built-in + extra JSON + hundreds of course-catalog modules.
        self.assertGreaterEqual(Tutorial.objects.count(), 750)
        # Lean redesign: course modules are 6 sections each (was 20), so the
        # section total is far lower than the old ~16k — but still substantial.
        self.assertGreater(TutorialSection.objects.count(), 4000)

    def test_course_module_has_lean_six_sections(self):
        call_command("seed_tutorials")
        t = Tutorial.objects.filter(course_slug="database-engineering-zero-hero").order_by("module_order").first()
        self.assertIsNotNone(t)
        self.assertEqual(t.level_track, "beginner")
        # Lean redesign: exactly six sections (no quiz-only extra for course modules).
        self.assertEqual(t.sections.count(), 6)
        headings = list(t.sections.order_by("order").values_list("heading", flat=True))
        self.assertEqual(
            headings,
            ["Overview", "Key concepts", "Hands-on walkthrough",
             "Common pitfalls & fixes", "Practice & assess", "Key takeaways"],
        )
        takeaways = t.sections.filter(heading="Key takeaways").first()
        self.assertIsNotNone(takeaways)
        self.assertIn("further reading", (takeaways.body or "").lower())

    def test_course_module_has_exactly_two_diagrams(self):
        call_command("seed_tutorials")
        t = Tutorial.objects.filter(course_slug="grafana-visualization-zero-hero").order_by("module_order").first()
        self.assertIsNotNone(t)
        self.assertEqual(t.sections.count(), 6)
        blob = "\n".join(s.body or "" for s in t.sections.all())
        # Exactly one architecture (flowchart) diagram + one sequenceDiagram, no dupes.
        self.assertEqual(blob.count("```mermaid"), 2, "should have exactly 2 diagrams")
        self.assertEqual(blob.count("flowchart"), 1)
        self.assertEqual(blob.count("sequenceDiagram"), 1)
        overview = t.sections.filter(heading="Overview").first()
        self.assertIn("Grafana", overview.body)

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
