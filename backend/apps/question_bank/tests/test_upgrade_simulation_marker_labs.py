"""Tests for generic simulation marker-lab upgrade (B3 sweep)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

from upgrade_simulation_marker_labs import MARKER_RE  # noqa: E402
from upgrade_academy_labs import assign_service_unit, check_script_for_mode  # noqa: E402


def test_check_script_service_has_no_marker():
    body = check_script_for_mode("service", "crond")
    assert "FIXED-OK" not in body
    assert "scenario-fixed" not in body
    assert "systemctl is-active crond" in body


def test_assign_service_unit_for_simulation_tech():
    unit = assign_service_unit("simulation", "simulation-lab-16")
    assert unit in ("nginx", "crond")


def test_no_simulation_check_sh_uses_tmp_marker():
    """Regression: generic simulation labs must not use /tmp/scenario-fixed."""
    root = Path(__file__).resolve().parents[4]
    offenders = []
    for path in (root / "scenarios" / "simulation").glob("*/check.sh"):
        body = path.read_text(encoding="utf-8")
        if MARKER_RE.search(body):
            offenders.append(str(path.relative_to(root)))
    assert offenders == [], f"marker checks remain: {offenders[:5]}"


def test_simulation_marker_presets_module_loads():
    from apps.labs.provisioner.simulation.simulation_marker_presets import (
        SIMULATION_MARKER_PRESETS,
    )
    assert "simulation-lab-16" in SIMULATION_MARKER_PRESETS
    assert len(SIMULATION_MARKER_PRESETS) >= 40


def test_simulation_e2e_fix_map_loads():
    from apps.labs.provisioner.simulation.simulation_marker_e2e_fixes import (
        SIMULATION_SERVICE_FIX,
    )
    assert SIMULATION_SERVICE_FIX.get("simulation-lab-16") in ("nginx", "crond")
