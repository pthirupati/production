"""Academy JS/React coding labs grade via hidden_tests (not systemd)."""

from pathlib import Path

import yaml
from django.test import SimpleTestCase

from apps.labs.code_exec import grade_submission

ROOT = Path(__file__).resolve().parents[2]


class AcademyCodingIdeTests(SimpleTestCase):
    def test_javascript_academy_arrays_grades(self):
        path = ROOT / "scenarios/javascript/academy-javascript-001-learn-arrays/scenario.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertTrue(data.get("coding_mode"))
        spec = data["coding_spec"]
        self.assertEqual(spec["language"], "javascript")
        tests = [{**t, "hidden": False} for t in spec["visible_tests"]] + [
            {**t, "hidden": True} for t in spec["hidden_tests"]
        ]
        stub = grade_submission("javascript", spec["files"][0]["content"], tests, timeout=8)
        self.assertFalse(stub.all_passed)
        fixed = (
            "function arraySum(arr) {\n"
            "  return arr.reduce((a, b) => a + Number(b), 0);\n"
            "}\n"
        )
        ok = grade_submission("javascript", fixed, tests, timeout=8)
        self.assertTrue(ok.all_passed, ok.error or ok.outcomes)

    def test_react_academy_components_grades(self):
        path = ROOT / "scenarios/react/academy-react-001-learn-components/scenario.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertTrue(data.get("coding_mode"))
        spec = data["coding_spec"]
        tests = [{**t, "hidden": False} for t in spec["visible_tests"]] + [
            {**t, "hidden": True} for t in spec["hidden_tests"]
        ]
        fixed = (
            "function createGreeting(name) {\n"
            "  return { type: 'h1', props: { children: 'Hello, ' + name } };\n"
            "}\n"
        )
        ok = grade_submission("javascript", fixed, tests, timeout=8)
        self.assertTrue(ok.all_passed, ok.error or ok.outcomes)

    def test_service_presets_exclude_coding_academies(self):
        from apps.labs.provisioner.simulation.academy_service_presets import (
            ACADEMY_SERVICE_PRESETS,
        )
        for slug in ACADEMY_SERVICE_PRESETS:
            self.assertFalse(
                slug.startswith(("academy-javascript-", "academy-react-", "academy-html-")),
                msg=slug,
            )

    def test_html_academy_semantic_grades_via_page_html(self):
        from apps.labs.code_exec import compose_user_code_from_files, grade_submission

        path = ROOT / "scenarios/html/academy-html-001-learn-semantic-html/scenario.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertTrue(data.get("coding_mode"))
        spec = data["coding_spec"]
        files = {f["path"]: f["content"] for f in spec["files"]}
        tests = [{**t, "hidden": False} for t in spec["visible_tests"]] + [
            {**t, "hidden": True} for t in spec["hidden_tests"]
        ]
        stub_code = compose_user_code_from_files(files, "solution.js")
        stub = grade_submission("javascript", stub_code, tests, timeout=8)
        self.assertFalse(stub.all_passed)
        files["index.html"] = (
            "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"/>"
            "<title>Lab</title></head><body><main><h1>Welcome</h1></main></body></html>"
        )
        fixed_code = compose_user_code_from_files(files, "solution.js")
        ok = grade_submission("javascript", fixed_code, tests, timeout=8)
        self.assertTrue(ok.all_passed, ok.error or ok.outcomes)
