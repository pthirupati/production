"""§Y2c — authoring language and gradeable runtime are separable."""

from django.test import SimpleTestCase

from apps.labs.code_exec import resolve_runtime
from apps.question_bank.management.commands.validate_scenario_catalog import (
    _coding_spec_gaps,
)


class ResolveRuntimeTests(SimpleTestCase):
    def test_explicit_runtime_wins(self):
        self.assertEqual(
            resolve_runtime({"language": "html", "runtime": "javascript"}),
            "javascript",
        )

    def test_html_authoring_language_maps_to_javascript(self):
        self.assertEqual(resolve_runtime({"language": "html"}), "javascript")

    def test_react_maps_to_javascript(self):
        self.assertEqual(resolve_runtime({"language": "react"}), "javascript")

    def test_sql_stays_sql(self):
        self.assertEqual(resolve_runtime({"language": "sql"}), "sql")

    def test_language_override_is_mapped(self):
        self.assertEqual(
            resolve_runtime({"language": "python"}, language_override="html"),
            "javascript",
        )

    def test_catalog_r5_accepts_html_language(self):
        spec = {
            "language": "html",
            "entrypoint": "solution.js",
            "files": [
                {"path": "index.html", "content": "<h1>Hi</h1>"},
                {"path": "solution.js", "content": "// harness", "readonly": True},
            ],
        }
        self.assertEqual(_coding_spec_gaps(spec), [])

    def test_catalog_r5_still_rejects_java_without_runtime(self):
        spec = {
            "language": "java",
            "entrypoint": "Main.java",
            "files": [{"path": "Main.java", "content": "class Main {}"}],
        }
        gaps = _coding_spec_gaps(spec)
        self.assertTrue(any("no server grader" in g for g in gaps), gaps)
