"""Tests for the Simulation scenario schema authoring helper."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_simulation_scenario_schema import enrich  # noqa: E402
from apps.question_bank.management.commands.validate_scenario_catalog import validate_scenario_file


def test_enrich_simulation_schema_authors_required_fields(tmp_path):
    folder = tmp_path / "simulation" / "academy-simulation-001-learn-terminal"
    folder.mkdir(parents=True)
    scenario = folder / "scenario.yaml"
    scenario.write_text(
        yaml.dump({
            "title": "Simulation Labs: Terminal Simulation — Fundamentals Lab",
            "slug": "academy-simulation-001-learn-terminal",
            "technology": "Simulation Labs",
            "category": "Core Skills",
            "difficulty": "easy",
            "scenario_type": "do",
            "lab_mode": "simulation",
            "simulation_type": "generic",
            "time_limit": 900,
            "max_score": 100,
            "description": "nginx is down",
            "objectives": ["nginx active", "status check passes"],
            "initial_state": "The nginx service is inactive.",
            "hints": [
                {"order": 1, "cost": 10, "content": "old"},
                {"order": 2, "cost": 20, "content": "old"},
                {"order": 3, "cost": 20, "content": "old"},
            ],
        }),
        encoding="utf-8",
    )
    (folder / "check.sh").write_text("#!/bin/bash\nsystemctl is-active nginx\nexit 0\n", encoding="utf-8")

    assert enrich(scenario) is True
    data = yaml.safe_load(scenario.read_text(encoding="utf-8"))

    assert data["title"] == "Terminal Simulation Fundamentals"
    assert data["technology"] == "simulation"
    assert data["category"] == "Learn"
    assert data["hints"][0]["cost"] == 0
    assert data["hints"][1]["cost"] == 25
    assert data["hints"][2]["cost"] == 50
    assert data["tasks"][0]["validation"]["type"] == "service_active"
    assert data["guided_mode"]["enabled"] is True
    assert validate_scenario_file(scenario) == []


def test_enrich_simulation_schema_writes_special_check(tmp_path):
    folder = tmp_path / "simulation" / "rhel-ansible-ssh"
    folder.mkdir(parents=True)
    scenario = folder / "scenario.yaml"
    scenario.write_text(
        yaml.dump({
            "title": "RHEL Simulation: Ansible SSH Key Failure",
            "slug": "sim-rhel-ansible-ssh",
            "technology": "simulation",
            "category": "Fix",
            "difficulty": "medium",
            "lab_mode": "simulation",
            "simulation_type": "ansible",
            "time_limit": 1200,
            "max_score": 100,
            "description": "web2 rejects publickey authentication",
            "objectives": ["identify web2 failure", "install key", "verify ping"],
            "initial_state": "web2 rejects publickey authentication.",
            "hints": [
                {"order": 1, "cost": 10, "content": "old"},
                {"order": 2, "cost": 20, "content": "old"},
                {"order": 3, "cost": 20, "content": "old"},
            ],
        }),
        encoding="utf-8",
    )
    (folder / "check.sh").write_text("#!/bin/bash\ntrue\nexit 0\n", encoding="utf-8")

    assert enrich(scenario) is True
    data = yaml.safe_load(scenario.read_text(encoding="utf-8"))

    assert "ansible webservers -m ping" in (folder / "check.sh").read_text(encoding="utf-8")
    assert data["tasks"][0]["validation"]["type"] == "command_output"
    assert data["tasks"][0]["validation"]["command"] == "ansible webservers -m ping"
    assert "Ansible reachability" in data["hints"][0]["content"]
    assert validate_scenario_file(scenario) == []
