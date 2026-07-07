"""Audit simulation scenarios for solvability.

For every simulation scenario, classify:
  NO_VALIDATION  — no usable validation script resolves: Check Solution can
                   never pass (the bug users report as "always failed").
  AUTO_PASS      — validation passes before any fix: lab grades itself done.
  OK             — validation fails initially (a real broken state to fix).

Usage: python scripts/audit_sim_solvability.py [--all | tech ...]
"""

from __future__ import annotations

import glob
import os
import sys
from collections import defaultdict

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
django.setup()

import yaml  # noqa: E402

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine  # noqa: E402
from apps.labs.provisioner.simulation.validation import (  # noqa: E402
    is_trivial_validation_script,
    resolve_simulation_validation_script,
    validate_simulation_state,
)

SCENARIOS_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "scenarios")

TERMINAL_SIM_TYPES = {
    "generic", "rhel", "linux", "gpu", "database", "networking", "devops",
    "terraform", "windows", "ansible", "kubernetes", "docker", "baremetal",
}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--all" in sys.argv or not args:
        techs = sorted(
            d for d in os.listdir(SCENARIOS_ROOT)
            if os.path.isdir(os.path.join(SCENARIOS_ROOT, d))
        )
    else:
        techs = args

    counts = defaultdict(lambda: defaultdict(int))
    no_validation: list[str] = []
    auto_pass: list[str] = []

    for tech in techs:
        for path in sorted(glob.glob(os.path.join(SCENARIOS_ROOT, tech, "*", "scenario.yaml"))):
            try:
                doc = yaml.safe_load(open(path)) or {}
            except Exception:
                continue
            if (doc.get("lab_mode") or "") != "simulation":
                continue
            # coding_mode labs (code IDE / prompt playground) are graded by the
            # coding validators, not the terminal simulation engine.
            if doc.get("coding_mode"):
                continue
            sim_type = doc.get("simulation_type") or "generic"
            if sim_type not in TERMINAL_SIM_TYPES:
                continue
            slug = doc.get("slug") or os.path.basename(os.path.dirname(path))
            check_path = os.path.join(os.path.dirname(path), "check.sh")
            raw_script = ""
            if os.path.exists(check_path):
                raw_script = open(check_path).read()
            script = resolve_simulation_validation_script(slug, raw_script)
            if not script or is_trivial_validation_script(script):
                counts[tech]["NO_VALIDATION"] += 1
                no_validation.append(f"{tech}/{slug}")
                continue
            try:
                engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
                ok, _msg = validate_simulation_state(engine.shell.state, script, engine=engine)
            except Exception as exc:
                counts[tech]["ERROR"] += 1
                no_validation.append(f"{tech}/{slug} <error {type(exc).__name__}>")
                continue
            if ok:
                counts[tech]["AUTO_PASS"] += 1
                auto_pass.append(f"{tech}/{slug}")
            else:
                counts[tech]["OK"] += 1

    print("\n=== Solvability by technology (OK = broken state + gradeable) ===")
    total = defaultdict(int)
    for tech in sorted(counts):
        row = counts[tech]
        for k, v in row.items():
            total[k] += v
        print(f"  {tech:<16} OK={row['OK']:>4}  NO_VALIDATION={row['NO_VALIDATION']:>4}  AUTO_PASS={row['AUTO_PASS']:>4}  ERROR={row['ERROR']:>3}")
    print(f"\n  TOTAL            OK={total['OK']}  NO_VALIDATION={total['NO_VALIDATION']}  AUTO_PASS={total['AUTO_PASS']}  ERROR={total['ERROR']}")

    if no_validation:
        print("\n=== First 40 NO_VALIDATION scenarios ===")
        for s in no_validation[:40]:
            print("  ", s)
    if auto_pass:
        print("\n=== First 40 AUTO_PASS scenarios ===")
        for s in auto_pass[:40]:
            print("  ", s)


if __name__ == "__main__":
    main()
