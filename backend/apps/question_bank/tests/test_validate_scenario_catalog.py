"""Tests for scenario catalog validation helpers."""
from pathlib import Path

import yaml

from apps.question_bank.management.commands.validate_scenario_catalog import (
    GUIDED_HINT_RE,
    validate_scenario_file,
)


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

