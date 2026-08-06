"""Tests for scenario catalog validation helpers."""
import shutil
from pathlib import Path

import yaml

from apps.question_bank.management.commands.validate_scenario_catalog import (
    GUIDED_HINT_RE,
    _ensure_schema_stubs,
    _known_course_slugs,
    validate_scenario_file,
)


def _write_coding_lab(tmp_path, spec, **extra):
    """A coding scenario that is clean apart from whatever `spec` breaks.

    Every unrelated gap (hints, description, schema) is satisfied so a test can
    assert on the exact coding_spec rule under test without the noise.
    """
    d = tmp_path / "python" / "code-lab"
    d.mkdir(parents=True)
    payload = {
        "slug": "code-lab",
        "description": "A" * 100,
        "objectives": ["a", "b"],
        "hints": [
            {"order": 1, "content": "Where to look: inspect the traceback first."},
            {"order": 2, "content": "Diagnostic steps:\n1. Run the test suite."},
            {"order": 3, "content": "Exact fix:\n1. Patch the function."},
        ],
        "coding_mode": True,
        "coding_spec": spec,
    }
    payload.update(extra)
    (d / "scenario.yaml").write_text(yaml.dump(payload), encoding="utf-8")
    return d / "scenario.yaml"


def test_guided_hint_regex_matches_step_format():
    assert GUIDED_HINT_RE.search("Orient yourself before changing anything:\n1. Inspect")
    assert GUIDED_HINT_RE.search("Guided walkthrough:\n1. Re-check")


def test_validate_scenario_file_flags_short_description(tmp_path):
    d = tmp_path / "linux" / "demo-lab"
    d.mkdir(parents=True)
    (d / "scenario.yaml").write_text(
        yaml.dump({
            "slug": "demo-lab",
            "description": "Too short.",
            "objectives": ["one"],
            "hints": [{"order": 1, "content": "x"}],
        }),
        encoding="utf-8",
    )
    gaps = validate_scenario_file(d / "scenario.yaml")
    assert any("description" in g for g in gaps)
    assert any("hint" in g for g in gaps)


def test_validate_flags_coding_lab_without_hidden_tests(tmp_path):
    d = tmp_path / "python" / "py-lab"
    d.mkdir(parents=True)
    (d / "scenario.yaml").write_text(
        yaml.dump({
            "slug": "py-lab",
            "description": "A" * 100,
            "objectives": ["a", "b"],
            "hints": [
                {"order": 1, "content": "Where to look: inspect the traceback first."},
                {"order": 2, "content": "Diagnostic steps:\n1. Run the test suite."},
                {"order": 3, "content": "Exact fix:\n1. Patch the function."},
            ],
            "coding_mode": True,
            "coding_spec": {"hidden_tests": []},
        }),
        encoding="utf-8",
    )
    (d / "check.sh").write_text(
        '#!/bin/bash\nMARKER="/tmp/scenario-fixed"\ngrep -q FIXED-OK "$MARKER"\n',
        encoding="utf-8",
    )
    gaps = validate_scenario_file(d / "scenario.yaml")
    assert any("hidden tests" in g for g in gaps)
    assert not any("marker" in g.lower() for g in gaps)


def test_validate_skips_marker_for_dedicated_sim(tmp_path):
    d = tmp_path / "nmap" / "scan-lab"
    d.mkdir(parents=True)
    (d / "scenario.yaml").write_text(
        yaml.dump({
            "slug": "scan-lab",
            "description": "A" * 100,
            "objectives": ["a", "b"],
            "hints": [
                {"order": 1, "content": "Where to look: start with host discovery."},
                {"order": 2, "content": "Diagnostic steps:\n1. Run nmap -sn."},
                {"order": 3, "content": "Exact fix:\n1. Apply the filter."},
            ],
            "simulation_type": "nmap",
        }),
        encoding="utf-8",
    )
    (d / "check.sh").write_text(
        '#!/bin/bash\nMARKER="/tmp/scenario-fixed"\ngrep -q FIXED-OK "$MARKER"\n',
        encoding="utf-8",
    )
    gaps = validate_scenario_file(d / "scenario.yaml")
    assert not any("marker" in g.lower() for g in gaps)


def test_validate_flags_tmp_marker_on_generic_sim(tmp_path):
    d = tmp_path / "simulation" / "sim-lab"
    d.mkdir(parents=True)
    (d / "scenario.yaml").write_text(
        yaml.dump({
            "slug": "sim-lab",
            "description": "A" * 100,
            "objectives": ["a", "b"],
            "hints": [
                {"order": 1, "content": "Where to look: check systemctl --failed."},
                {"order": 2, "content": "Diagnostic steps:\n1. Inspect logs."},
                {"order": 3, "content": "Exact fix:\n1. Start the unit."},
            ],
            "simulation_type": "generic",
        }),
        encoding="utf-8",
    )
    (d / "check.sh").write_text(
        '#!/bin/bash\nMARKER="/tmp/scenario-fixed"\ngrep -q FIXED-OK "$MARKER"\n',
        encoding="utf-8",
    )
    gaps = validate_scenario_file(d / "scenario.yaml")
    assert any("completion sentinel" in g for g in gaps)


def test_validate_flags_missing_b1_schema_fields(tmp_path):
    d = tmp_path / "linux" / "thin-lab"
    d.mkdir(parents=True)
    (d / "scenario.yaml").write_text(
        yaml.dump({
            "slug": "thin-lab",
            "title": "Thin lab",
            "description": "A" * 100,
            "objectives": ["one", "two"],
            "hints": [
                {"order": 1, "content": "Where to look: inspect service state first."},
                {"order": 2, "content": "Diagnostic steps:\n1. Run systemctl status."},
                {"order": 3, "content": "Exact fix:\n1. Start the unit."},
            ],
        }),
        encoding="utf-8",
    )
    (d / "check.sh").write_text("#!/bin/bash\nsystemctl is-active nginx\n", encoding="utf-8")

    gaps = validate_scenario_file(d / "scenario.yaml")

    assert "missing summary" in gaps
    assert "missing linked_tutorial" in gaps
    assert "missing environment.nodes" in gaps
    assert "missing tasks" in gaps
    assert any("description missing CONTEXT" in g for g in gaps)


def test_fix_stubs_patches_missing_b1_schema_fields(tmp_path):
    d = tmp_path / "linux" / "thin-lab"
    d.mkdir(parents=True)
    scenario_path = d / "scenario.yaml"
    scenario_path.write_text(
        yaml.dump({
            "slug": "thin-lab",
            "title": "Repair Nginx",
            "description": "nginx is down",
            "objectives": ["nginx is active", "status check passes"],
            "hints": [
                {"order": 1, "content": "Where to look: inspect service state first."},
                {"order": 2, "content": "Diagnostic steps:\n1. Run systemctl status nginx."},
                {"order": 3, "content": "Exact fix:\n1. Start nginx."},
            ],
            "time_limit": 900,
            "max_score": 100,
        }),
        encoding="utf-8",
    )
    (d / "check.sh").write_text("#!/bin/bash\nsystemctl is-active nginx\n", encoding="utf-8")

    gaps = validate_scenario_file(scenario_path, fix_stubs=True)
    data = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))

    assert data["summary"].startswith("TODO:")
    assert data["technology"] == "linux"
    assert data["estimated_minutes"] == 15
    assert data["xp_reward"] == 100
    assert len(data["what_you_will_learn"]) >= 3
    assert data["environment"]["nodes"][0]["role"] == "primary"
    assert data["tasks"][0]["validation"]["type"] == "service_active"
    assert data["solution"]["summary"].startswith("TODO:")
    assert not any("missing summary" in g for g in gaps)
    assert not any("missing tasks" in g for g in gaps)


# ---------------------------------------------------------------------------
# Catalog CI rules R3/R5/R6/R7/R8/R10, the `grader:` guardrail, slug identity,
# and cross-layer slug resolution.
#
# These are django.test.SimpleTestCase rather than bare pytest functions on
# purpose: this package has no __init__.py and the repo ships no pytest, so the
# module-level `def test_*(tmp_path)` style above is only reachable by a direct
# file run. SimpleTestCase works under `manage.py test` either way.
# ---------------------------------------------------------------------------
import tempfile
import unittest

from django.test import SimpleTestCase


class _CodingRuleCase(SimpleTestCase):
    """Shared fixture: a coding lab that is clean apart from the rule under test."""

    def lab(self, spec, **extra):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        return _write_coding_lab(tmp, spec, **extra)

    def gaps(self, spec, **extra):
        return validate_scenario_file(self.lab(spec, **extra))

    # A spec that satisfies every rule, so subclasses can perturb one field.
    HEALTHY = {
        "language": "python",
        "entrypoint": "solution.py",
        "hidden_tests": [{"code": "assert solution(2) == 4"}],
        "files": [{"path": "solution.py", "content": "", "readonly": False}],
    }

    def healthy(self, **overrides):
        spec = {k: (list(v) if isinstance(v, list) else v) for k, v in self.HEALTHY.items()}
        spec.update(overrides)
        return spec


class EntrypointInFilesRuleTests(_CodingRuleCase):
    """R3: the entrypoint must be one of the files the IDE hydrates."""

    def test_entrypoint_missing_from_files_is_a_gap(self):
        gaps = self.gaps(self.healthy(
            files=[{"path": "main.py", "content": "", "readonly": False}],
        ))
        self.assertTrue(any("is not in files[]" in g for g in gaps), gaps)

    def test_declared_entrypoint_is_clean(self):
        self.assertFalse([g for g in self.gaps(self.healthy()) if "files[]" in g])

    def test_spec_without_a_files_block_is_not_judged(self):
        """The 150 prompt labs declare no files; R3 must not invent a gap."""
        spec = self.healthy()
        spec.pop("files")
        self.assertFalse([g for g in self.gaps(spec) if "files[]" in g])


class LanguageRuntimeRuleTests(_CodingRuleCase):
    """R5: a declared language must be one code_exec can actually run."""

    def test_language_without_a_server_runtime_is_a_gap(self):
        gaps = self.gaps(self.healthy(
            language="java",
            entrypoint="Solution.java",
            files=[{"path": "Solution.java", "content": "", "readonly": False}],
        ))
        self.assertTrue(any("no server runtime" in g for g in gaps), gaps)

    def test_text_prompt_labs_are_exempt(self):
        """`text` has no interpreter by design; 150 labs would fail otherwise."""
        gaps = self.gaps({"language": "text", "kind": "prompt"})
        self.assertFalse([g for g in gaps if "runtime" in g])

    def test_supported_language_is_clean(self):
        self.assertFalse([g for g in self.gaps(self.healthy()) if "runtime" in g])


class EditableFileRuleTests(_CodingRuleCase):
    """R6: a lab made entirely of read-only harness has nowhere to type."""

    def test_all_readonly_files_is_a_gap(self):
        gaps = self.gaps(self.healthy(
            language="javascript",
            entrypoint="solution.js",
            files=[
                {"path": "solution.js", "content": "", "readonly": True},
                {"path": "harness.js", "content": "", "readonly": True},
            ],
        ))
        self.assertTrue(any("no editable file" in g for g in gaps), gaps)

    def test_html_harness_shape_is_clean(self):
        """html labs ship a readonly solution.js grader plus editable index.html."""
        gaps = self.gaps(self.healthy(
            language="javascript",
            entrypoint="solution.js",
            files=[
                {"path": "solution.js", "content": "", "readonly": True},
                {"path": "index.html", "content": "", "readonly": False},
            ],
        ))
        self.assertFalse([g for g in gaps if "editable" in g])


class HiddenTestQualityRuleTests(_CodingRuleCase):
    """R7 (presence) and R8 (not tautological)."""

    def test_tautological_hidden_test_is_a_gap(self):
        gaps = self.gaps(self.healthy(
            hidden_tests=[{"code": "assert callable(solution)"}],
        ))
        self.assertTrue(any("tautological" in g for g in gaps), gaps)

    def test_multi_statement_test_is_not_called_weak(self):
        """A body doing real work must not be flagged for one soft line."""
        gaps = self.gaps(self.healthy(
            hidden_tests=[{"code": "assert callable(solution)\nassert solution(2) == 4"}],
        ))
        self.assertFalse([g for g in gaps if "tautological" in g])

    def test_prompt_kind_is_exempt_from_tautology_rule(self):
        """`kind` lives on coding_spec; prompt labs carry a vestigial assert True."""
        gaps = self.gaps({
            "language": "text", "kind": "prompt",
            "hidden_tests": [{"code": "assert True"}],
        })
        self.assertFalse([g for g in gaps if "tautological" in g])

    def test_prompt_lab_without_hidden_tests_is_exempt(self):
        """All 100 hidden-test-less coding labs are kind=prompt, graded elsewhere."""
        gaps = self.gaps({"language": "text", "kind": "prompt"})
        self.assertFalse([g for g in gaps if "hidden tests" in g])

    def test_non_prompt_lab_without_hidden_tests_is_still_a_gap(self):
        spec = self.healthy()
        spec.pop("hidden_tests")
        self.assertTrue([g for g in self.gaps(spec) if "hidden tests" in g])


class PreviewRootRuleTests(_CodingRuleCase):
    """R10: a declared preview root must resolve to a real file."""

    HTML_FILES = [
        {"path": "solution.js", "content": "", "readonly": True},
        {"path": "index.html", "content": "", "readonly": False},
    ]

    def test_preview_root_not_in_files_is_a_gap(self):
        gaps = self.gaps(
            self.healthy(language="javascript", entrypoint="solution.js", files=self.HTML_FILES),
            preview={"enabled": True, "root": "home.html"},
        )
        self.assertTrue(any("preview.root" in g for g in gaps), gaps)

    def test_declared_preview_root_is_clean(self):
        gaps = self.gaps(
            self.healthy(language="javascript", entrypoint="solution.js", files=self.HTML_FILES),
            preview={"enabled": True, "root": "index.html"},
        )
        self.assertFalse([g for g in gaps if "preview" in g])

    def test_preview_block_without_a_root_is_a_gap(self):
        gaps = self.gaps(
            self.healthy(language="javascript", entrypoint="solution.js", files=self.HTML_FILES),
            preview={"enabled": True},
        )
        self.assertTrue(any("without preview.root" in g for g in gaps), gaps)


class GraderFieldGuardrailTests(_CodingRuleCase):
    """A future `grader:` field must not republish ungraded labs (audit L2673)."""

    def test_grader_cannot_activate_a_lab_with_no_hidden_tests(self):
        spec = self.healthy()
        spec.pop("hidden_tests")
        gaps = self.gaps(spec, grader={"type": "pytest"}, is_active=True)
        self.assertTrue(any("cannot activate" in g for g in gaps), gaps)

    def test_grader_must_declare_a_type(self):
        gaps = self.gaps(self.healthy(), grader={"notes": "todo"})
        self.assertTrue(any("grader declared with no type" in g for g in gaps), gaps)

    def test_grader_does_not_suppress_the_tautology_rule(self):
        """Declaring a grader must not buy an exemption from R8."""
        gaps = self.gaps(
            self.healthy(hidden_tests=[{"code": "assert True"}]),
            grader={"type": "pytest"},
        )
        self.assertTrue(any("tautological" in g for g in gaps), gaps)


class SlugIdentityTests(SimpleTestCase):
    """A scenario's slug must be declared, not inferred from the folder name."""

    def test_missing_slug_is_a_gap(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        d = tmp / "linux" / "inferred-name"
        d.mkdir(parents=True)
        (d / "scenario.yaml").write_text(
            yaml.dump({
                "description": "A" * 100,
                "objectives": ["a", "b"],
                "hints": [{"order": 1, "content": "Where to look: check the unit first."}],
            }),
            encoding="utf-8",
        )
        gaps = validate_scenario_file(d / "scenario.yaml")
        self.assertTrue(any("missing slug" in g for g in gaps), gaps)


class CrossLayerSlugResolutionTests(_CodingRuleCase):
    """Cross-layer references must resolve, not merely be present (audit L297)."""

    def test_unresolvable_linked_tutorial_is_a_gap(self):
        path = self.lab(self.healthy(), linked_tutorial="linux-fundamentals")
        gaps = validate_scenario_file(path, check_linked_tutorial=True)
        self.assertTrue(any("does not resolve to a known course" in g for g in gaps), gaps)

    def test_real_course_slug_resolves(self):
        real = sorted(_known_course_slugs())[0]
        path = self.lab(self.healthy(), linked_tutorial=real)
        gaps = validate_scenario_file(path, check_linked_tutorial=True)
        self.assertFalse([g for g in gaps if "does not resolve" in g])

    def test_linked_tutorial_check_is_off_by_default(self):
        """Opt-in until the 44-slug remap lands; on by default breaks CI."""
        gaps = self.gaps(self.healthy(), linked_tutorial="linux-fundamentals")
        self.assertFalse([g for g in gaps if "does not resolve to a known course" in g])

    def test_unresolvable_lab_scenario_slug_is_a_gap(self):
        gaps = self.gaps(self.healthy(), lab_scenario_slug="no-such-scenario-anywhere")
        self.assertTrue(any("lab_scenario_slug" in g for g in gaps), gaps)

    def test_course_catalog_is_actually_readable(self):
        """Guards the import-failure fallback from silently disabling the rule."""
        self.assertGreater(len(_known_course_slugs()), 50)


class FixStubsTests(SimpleTestCase):
    def test_fix_stubs_no_longer_fabricates_a_linked_tutorial(self):
        """The TODO placeholder satisfied the presence check by construction."""
        data = {"slug": "thin-lab", "title": "Thin lab", "time_limit": 900}
        _ensure_schema_stubs(Path("/tmp/linux/thin-lab/scenario.yaml"), data)
        self.assertNotIn("linked_tutorial", data)
