"""Tests for tutorial richness/completeness checks."""

from django.core.management import call_command
from django.test import TestCase

from apps.tutorials.completeness import enrich_body, validate_tutorial
from apps.tutorials.quiz_bank import build_module_quiz
from apps.tutorials.models import Tutorial, TutorialSection


class TutorialCompletenessTest(TestCase):
    def test_enrich_body_flat_first_section_adds_offline_blocks(self):
        # A flat/standalone lesson's first section carries the full top-up.
        body = enrich_body("Linux", "Linux Basics", "Short lesson.", is_first=True)
        self.assertIn("```mermaid", body)
        self.assertIn("| What to check | Command / signal | Why it matters |", body)
        self.assertIn("> [!NOTE]", body)
        self.assertIn("```bash", body)
        self.assertNotIn("Core concept", body)
        self.assertNotIn("Check solution", body)

    def test_enrich_body_is_targeted_by_heading(self):
        # Overview carries the diagram + hero image; NOT the shell block.
        overview = enrich_body("Kubernetes", "K8s", "See the diagram.", heading="Overview")
        self.assertIn("```mermaid", overview)
        self.assertIn("![", overview)
        self.assertNotIn("```bash", overview)

        # The walkthrough carries the shell block; NOT a duplicate architecture diagram.
        walk = enrich_body("Kubernetes", "K8s", "Run the commands.", heading="Hands-on walkthrough")
        self.assertIn("```bash", walk)
        self.assertNotIn("```mermaid", walk)
        self.assertNotIn("![", walk)

        # Key takeaways gets no diagram/image/table — just a callout if it lacks one.
        take = enrich_body("Kubernetes", "K8s", "Remember these.", heading="Key takeaways")
        self.assertNotIn("```mermaid", take)
        self.assertNotIn("![", take)

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
        from apps.tutorials.management.commands.section_content import build_module_sections
        from apps.tutorials.completeness import validate_tutorial

        course = {
            "course_slug": "kubernetes-platform-zero-hero",
            "course_title": "Kubernetes Platform Engineering: Zero to Hero",
            "topic": "Kubernetes",
            "playground_slug": "kubernetes",
            "scenario_slug": "academy-kubernetes-001-learn-pods",
            "_module_order": 1,
        }
        sections = build_module_sections(course, "Pods, Deployments, and Services", "beginner")
        tutorial = Tutorial.objects.create(
            slug="rich",
            title="Kubernetes: Pods, Deployments, and Services",
            topic="Kubernetes",
            summary="Rich",
            course_slug=course["course_slug"],
            module_order=1,
            scenario_slug=course["scenario_slug"],
        )
        for i, (heading, body, code, lang, caption) in enumerate(sections):
            TutorialSection.objects.create(
                tutorial=tutorial,
                order=i,
                heading=heading,
                body=enrich_body("Kubernetes", tutorial.title, body, heading=heading, is_first=(i == 0)),
                code=code,
                code_language=lang or "bash",
                code_caption=caption,
            )
        # The lean lesson has exactly 6 sections and passes the gate.
        self.assertEqual(tutorial.sections.count(), 6)
        self.assertEqual(validate_tutorial(tutorial).gaps, [])
        call_command("check_tutorial_completeness", "--all")

    def test_gate_rejects_legacy_bloat_and_duplicate_diagrams(self):
        from apps.tutorials.completeness import validate_tutorial

        tutorial = Tutorial.objects.create(
            slug="bloated",
            title="Old Bloated Module",
            topic="Kubernetes",
            summary="Bloat",
            course_slug="kubernetes-platform-zero-hero",
            module_order=2,
            scenario_slug="academy-kubernetes-001-learn-pods",
        )
        # Two legacy section headings + two flowcharts (duplicate arch diagrams).
        TutorialSection.objects.create(
            tutorial=tutorial, order=0, heading="Interactive simulations",
            body="```mermaid\nflowchart LR\n a-->b\n```",
        )
        TutorialSection.objects.create(
            tutorial=tutorial, order=1, heading="Root cause analysis",
            body="```mermaid\nflowchart TD\n c-->d\n```",
        )
        gaps = validate_tutorial(tutorial).gaps
        self.assertTrue(any("legacy 20-section bloat" in g for g in gaps), gaps)
        self.assertTrue(any("architecture (flowchart)" in g for g in gaps), gaps)
