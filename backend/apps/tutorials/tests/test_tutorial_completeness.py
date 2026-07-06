"""Tests for tutorial richness/completeness checks."""

from django.core.management import call_command
from django.test import TestCase

from apps.tutorials.completeness import enrich_body, validate_tutorial
from apps.tutorials.quiz_bank import build_module_quiz
from apps.tutorials.models import Tutorial, TutorialSection


class TutorialCompletenessTest(TestCase):
    def test_enrich_body_adds_required_offline_blocks(self):
        body = enrich_body("Linux", "Linux Basics", "Short lesson.")
        self.assertIn("```mermaid", body)
        self.assertIn("| What to check | Command / signal | Why it matters |", body)
        self.assertIn("> [!NOTE]", body)
        self.assertIn("```bash", body)
        self.assertIn("Hands-on playbook", body)
        self.assertNotIn("Core concept", body)
        self.assertNotIn("Check solution", body)

    def test_generated_quiz_requires_80_percent(self):
        quiz = build_module_quiz("Linux", "Linux Basics")
        self.assertEqual(quiz["pass_score"], 0.8)
        self.assertEqual(len(quiz["questions"]), 5)

    def test_validate_tutorial_flags_gaps(self):
        tutorial = Tutorial.objects.create(
            slug="thin",
            title="Thin Tutorial",
            topic="Linux",
            summary="Thin",
            scenario_slug="",
        )
        TutorialSection.objects.create(tutorial=tutorial, order=1, heading="Intro", body="Too thin")
        gaps = validate_tutorial(tutorial).gaps
        self.assertIn("missing Mermaid/diagram block", gaps)
        self.assertIn("missing linked lab/scenario_slug", gaps)

    def test_check_tutorial_completeness_passes_rich_lesson(self):
        tutorial = Tutorial.objects.create(
            slug="rich",
            title="Rich Tutorial",
            topic="Linux",
            summary="Rich",
            scenario_slug="academy-linux-001-learn-users-groups",
        )
        TutorialSection.objects.create(
            tutorial=tutorial,
            order=1,
            heading="Overview & why it matters / Quiz",
            body=enrich_body("Linux", "Rich Tutorial", "Start here."),
        )
        TutorialSection.objects.create(
            tutorial=tutorial,
            order=2,
            heading="Assessment",
            body="Answer the module quiz.",
        )
        call_command("check_tutorial_completeness", "--all")
