"""Tests for technology catalog linking."""

from django.test import SimpleTestCase

from apps.question_bank.technology_catalog import (
    build_learning_path_steps,
    enrich_catalog_specs,
    resolve_module_scenario_slug,
    topic_to_tech_slug,
)


class TechnologyCatalogTests(SimpleTestCase):
    def test_topic_mapping(self):
        self.assertEqual(topic_to_tech_slug("Linux"), "linux")
        self.assertEqual(topic_to_tech_slug("Bash"), "shell-script")
        self.assertEqual(topic_to_tech_slug("RHEL"), "rhel-linux")

    def test_resolve_linux_module_slug(self):
        slug = resolve_module_scenario_slug("Linux", 1)
        self.assertTrue(slug.startswith("academy-linux-") or slug)

    def test_learning_path_has_steps(self):
        steps = build_learning_path_steps("linux", limit=10)
        self.assertGreaterEqual(len(steps), 5)
        self.assertIn("scenario_slug", steps[0])

    def test_enrich_catalog_specs(self):
        specs = [
            {
                "topic": "Linux",
                "module_order": 1,
                "scenario_slug": "",
            }
        ]
        enrich_catalog_specs(specs)
        self.assertTrue(specs[0]["scenario_slug"])
