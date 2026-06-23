"""Verify seed_tutorials loads the built-in tutorials AND the original
tutorials authored as data in data/tutorials_extra.json."""

from django.core.management import call_command
from django.test import TestCase

from apps.tutorials.models import Tutorial, TutorialSection


class SeedTutorialsTest(TestCase):
    def test_seed_loads_builtin_and_extra(self):
        call_command("seed_tutorials")
        # 8 built-in + 32 original (data/tutorials_extra.json).
        self.assertGreaterEqual(Tutorial.objects.count(), 40)
        self.assertGreater(TutorialSection.objects.count(), 200)

    def test_extra_tutorial_has_sections(self):
        call_command("seed_tutorials")
        t = Tutorial.objects.filter(
            slug="linux-file-permissions-ownership-deep-dive"
        ).first()
        self.assertIsNotNone(t)
        self.assertEqual(t.topic, "Linux")
        self.assertGreaterEqual(t.sections.count(), 5)
        # Sections are ordered and have headings.
        first = t.sections.order_by("order").first()
        self.assertTrue(first.heading)

    def test_seed_is_idempotent(self):
        call_command("seed_tutorials")
        n1 = Tutorial.objects.count()
        call_command("seed_tutorials")
        self.assertEqual(Tutorial.objects.count(), n1)
