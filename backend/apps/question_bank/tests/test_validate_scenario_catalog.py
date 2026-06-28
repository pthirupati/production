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
