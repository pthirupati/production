"""Tests for the full-catalog scenario schema enricher."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

from enrich_scenario_catalog_schema import enrich  # noqa: E402
from apps.question_bank.management.commands.validate_scenario_catalog import validate_scenario_file


def test_enrich_catalog_restores_nginx_hints(tmp_path):
    folder = tmp_path / "linux" / "rhel-broken-nginx"
    folder.mkdir(parents=True)
    scenario = folder / "scenario.yaml"
    scenario.write_text(
        yaml.dump({
            "title": "RHEL Simulation: Fix Broken Nginx",
            "slug": "sim-rhel-broken-nginx",
            "technology": "linux",
            "category": "Fix",
            "difficulty": "easy",
            "lab_mode": "simulation",
            "simulation_type": "generic",
            "time_limit": 900,
            "max_score": 100,
            "description": "nginx typo in config",
            "objectives": [
                "Run nginx -t to locate the configuration syntax error",
                "Fix the misspelled directive",
                "Start nginx and verify port 80",
            ],
            "initial_state": "nginx fails to start; nginx -t reports syntax error.",
            "hints": [
                {
                    "order": 1,
                    "cost": 0,
                    "content": "Where to look: status commands and logs for nginx before changing anything.",
                },
                {"order": 2, "cost": 25, "content": "Diagnostic steps:\n1. Gather evidence."},
                {
                    "order": 3,
                    "cost": 50,
                    "content": "Exact fix:\n2. Re-run `the verification command from the objectives`.",
                },
            ],
        }),
        encoding="utf-8",
    )
    (folder / "check.sh").write_text(
        '#!/bin/bash\ncurl -s -o /dev/null -w "%{http_code}" http://localhost | grep -q 200\nexit 0\n',
        encoding="utf-8",
    )

    assert enrich(scenario) is True
    data = yaml.safe_load(scenario.read_text(encoding="utf-8"))

    assert "`nginx -t`" in data["hints"][0]["content"]
    assert data["hints"][1]["cost"] == 25
    assert "systemctl enable --now nginx" in data["hints"][2]["content"]
    assert data["tasks"][0]["validation"]["type"] == "http_response"
    assert validate_scenario_file(scenario) == []

    assert enrich(scenario) is False


def test_enrich_catalog_preserves_existing_rich_hints(tmp_path):
    folder = tmp_path / "linux" / "custom-lab"
    folder.mkdir(parents=True)
    scenario = folder / "scenario.yaml"
    rich = (
        'Where to look: Run `journalctl -u custom-app -n 50` and '
        '`systemctl status custom-app` before editing `/etc/custom-app/config.yml`.'
    )
    scenario.write_text(
        yaml.dump({
            "title": "Custom App Lab",
            "slug": "custom-app-lab",
            "technology": "linux",
            "description": "custom app is down",
            "objectives": ["restore custom-app service"],
            "initial_state": "custom-app failed",
            "hints": [
                {"order": 1, "cost": 0, "content": rich},
                {"order": 2, "cost": 25, "content": "Diagnostic steps:\n1. Read logs."},
                {"order": 3, "cost": 50, "content": "Exact fix:\n1. Restart service."},
            ],
        }),
        encoding="utf-8",
    )
    (folder / "check.sh").write_text("#!/bin/bash\nsystemctl is-active custom-app\nexit 0\n", encoding="utf-8")

    enrich(scenario)
    data = yaml.safe_load(scenario.read_text(encoding="utf-8"))
    assert data["hints"][0]["content"] == rich
