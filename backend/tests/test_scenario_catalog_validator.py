"""Coding-spec rules R1/R2 in validate_scenario_catalog.

R1 — coding_spec.language must be declared. Both the frontend
(``spec?.language || 'python'``) and the backend runtime selection read this
field, so an omitted language silently grades a lab with the wrong runtime.

R2 — the entrypoint extension must agree with the declared language, otherwise
``language: python`` + ``entrypoint: solution.js`` grades a JS file with the
Python harness.
"""
from django.test import SimpleTestCase

from apps.question_bank.management.commands.validate_scenario_catalog import (
    _coding_spec_gaps,
)


class CodingSpecLanguageRuleTests(SimpleTestCase):
    """R1: language must be declared explicitly."""

    def test_missing_language_is_a_gap(self):
        gaps = _coding_spec_gaps({"entrypoint": "solution.py"})
        self.assertTrue(any("language not declared" in g for g in gaps), gaps)

    def test_empty_language_is_a_gap(self):
        gaps = _coding_spec_gaps({"language": "   ", "entrypoint": "solution.py"})
        self.assertTrue(any("language not declared" in g for g in gaps), gaps)

    def test_declared_language_with_matching_entrypoint_is_clean(self):
        self.assertEqual(_coding_spec_gaps({"language": "python", "entrypoint": "solution.py"}), [])

    def test_unrecognised_language_is_reported(self):
        gaps = _coding_spec_gaps({"language": "cobol", "entrypoint": "solution.cob"})
        self.assertTrue(any("not a recognised language" in g for g in gaps), gaps)

    def test_language_is_case_and_space_insensitive(self):
        self.assertEqual(_coding_spec_gaps({"language": " Python ", "entrypoint": "solution.py"}), [])


class CodingSpecEntrypointRuleTests(SimpleTestCase):
    """R2: entrypoint extension must agree with the declared language."""

    def test_python_language_with_js_entrypoint_is_a_gap(self):
        gaps = _coding_spec_gaps({"language": "python", "entrypoint": "solution.js"})
        self.assertTrue(any("does not match language" in g for g in gaps), gaps)

    def test_javascript_language_with_py_entrypoint_is_a_gap(self):
        gaps = _coding_spec_gaps({"language": "javascript", "entrypoint": "solution.py"})
        self.assertTrue(any("does not match language" in g for g in gaps), gaps)

    def test_multi_extension_languages_are_allowed(self):
        for entrypoint in ("solution.js", "solution.mjs", "solution.cjs"):
            self.assertEqual(
                _coding_spec_gaps({"language": "javascript", "entrypoint": entrypoint}), [],
                f"{entrypoint} should be valid for javascript",
            )

    def test_html_labs_declaring_javascript_harness_are_not_flagged(self):
        # The ~155 HTML labs ship `language: javascript` with a solution.js
        # grader harness; R2 must not false-positive across all of them.
        self.assertEqual(
            _coding_spec_gaps({"language": "javascript", "entrypoint": "solution.js"}), [],
        )

    def test_sql_entrypoint(self):
        self.assertEqual(_coding_spec_gaps({"language": "sql", "entrypoint": "solution.sql"}), [])

    def test_missing_entrypoint_is_a_gap_for_executable_languages(self):
        gaps = _coding_spec_gaps({"language": "python"})
        self.assertTrue(any("entrypoint missing" in g for g in gaps), gaps)

    def test_text_labs_may_omit_the_entrypoint(self):
        # The 150 prompt-engineering labs grade a text answer; there is no file
        # to execute, so requiring an entrypoint would be a false positive.
        self.assertEqual(_coding_spec_gaps({"language": "text"}), [])

    def test_entrypoint_in_a_subdirectory_is_matched_on_extension(self):
        self.assertEqual(
            _coding_spec_gaps({"language": "python", "entrypoint": "src/pkg/solution.py"}), [],
        )

    def test_r2_is_not_evaluated_without_a_declared_language(self):
        # Only the R1 gap should be reported; guessing an extension rule from an
        # undeclared language would be noise.
        gaps = _coding_spec_gaps({"entrypoint": "solution.js"})
        self.assertEqual(len(gaps), 1, gaps)

    def test_non_mapping_spec_is_reported_rather_than_crashing(self):
        self.assertTrue(_coding_spec_gaps([]))
