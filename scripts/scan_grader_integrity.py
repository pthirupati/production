#!/usr/bin/env python
"""Grader-integrity scanner (standalone, READ-ONLY diagnostic).

For every scenario, replicate the RUNTIME simulation validation on the UNFIXED
(broken) state and classify the outcome:

  FAIL-OPEN   — validate_simulation_state returned passed=True on the broken
                state (the grader auto-passes without any fix; a real problem).
  NO-MATCH    — validation ran but matched no substantive checks
                ("No validation checks matched this simulation script").
  FAIL-CLOSED — validation correctly returned passed=False for a real reason
                (the desired behaviour on the unfixed state).

Faithful to the runtime path used by the provisioner for terminal/simulation
labs (apps.labs.provisioner.simulation_provisioner.SimulationProvisioner
.run_validation, ~L597-599):

  script = resolve_simulation_validation_script(slug, db_script)
  engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
  passed, output = validate_simulation_state(engine.state, script, engine=engine)

The UnifiedSimulationEngine applies the scenario preset automatically when its
RHELShell is constructed with the scenario slug (scenario_presets
.apply_scenario_preset), so the engine.state IS the broken/unfixed state — the
same construction the provisioner uses.

Scenario source: the seeded DB when available (Scenario.validation_script holds
the check.sh text, as seed_scenarios.py loads it); otherwise walks
scenarios/<tech>/<slug>/scenario.yaml + check.sh from the filesystem.

Run:  backend/.venv/bin/python scripts/scan_grader_integrity.py
This script performs NO writes.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ── Django bootstrap (mirrors scripts/e2e_dynamic_catalog.py, but uses the
#    test settings + the repo's backend/ on sys.path so it runs off the checked
#    out tree with backend/.venv/bin/python). ──
_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _REPO_ROOT / "backend"
sys.path.insert(0, str(_BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

import django  # noqa: E402

django.setup()

from apps.labs.provisioner.simulation.sim_types import normalize_sim_type  # noqa: E402
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine  # noqa: E402
from apps.labs.provisioner.simulation.validation import (  # noqa: E402
    resolve_simulation_validation_script,
    validate_simulation_state,
)

# Outputs validate_simulation_state emits for the "nothing matched" case.
_NO_MATCH_OUTPUTS = {
    "No validation checks matched this simulation script",
    "NO_VALIDATION_SCRIPT",
    "Validation not configured — fix the scenario before checking",
}


def scenarios_root() -> Path:
    for candidate in (Path("/scenarios"), _REPO_ROOT / "scenarios"):
        if candidate.is_dir():
            return candidate
    return _REPO_ROOT / "scenarios"


def _iter_from_db():
    """Yield (slug, technology, sim_type, db_script) from the seeded DB, or None."""
    try:
        from apps.question_bank.models import Scenario

        qs = (
            Scenario.objects.filter(is_active=True)
            .select_related("technology")
            .only("slug", "validation_script", "simulation_type", "technology__slug")
        )
        rows = []
        for sc in qs.iterator():
            tech = sc.technology.slug if sc.technology_id else "unknown"
            rows.append(
                (
                    sc.slug or "",
                    tech,
                    getattr(sc, "simulation_type", "") or "generic",
                    sc.validation_script or "",
                )
            )
        return rows or None
    except Exception:
        return None


def _iter_from_fs():
    """Yield (slug, technology, sim_type, db_script) by walking the scenarios tree."""
    import yaml

    root = scenarios_root()
    rows = []
    if not root.is_dir():
        return rows
    for tech_dir in sorted(root.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        tech = tech_dir.name
        for sd in sorted(tech_dir.iterdir()):
            if not sd.is_dir():
                continue
            y = sd / "scenario.yaml"
            if not y.is_file():
                continue
            try:
                data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            slug = data.get("slug") or sd.name
            sim_type = data.get("simulation_type") or "generic"
            check = sd / "check.sh"
            script = check.read_text(encoding="utf-8") if check.is_file() else ""
            rows.append((slug, data.get("technology") or tech, sim_type, script))
    return rows


def _first_check_line(script: str) -> str:
    """First substantive (non-comment, non-shebang) line of the check script."""
    for raw in (script or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line in ("true", ":", "exit 0"):
            continue
        return line[:120]
    return "(empty)"


def classify(slug: str, sim_type: str, db_script: str) -> tuple[str, str]:
    """Return (classification, output) replicating the runtime validation path."""
    norm_type = normalize_sim_type(sim_type)
    try:
        engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=norm_type)
        script = resolve_simulation_validation_script(slug, db_script or "")
        passed, output = validate_simulation_state(engine.state, script, engine=engine)
    except Exception as exc:  # engine/preset/validation error — record, don't crash
        return "ERROR", f"{type(exc).__name__}: {exc}"

    if passed:
        return "FAIL-OPEN", output
    if output in _NO_MATCH_OUTPUTS or "No validation checks matched" in (output or ""):
        return "NO-MATCH", output
    return "FAIL-CLOSED", output


def main() -> int:
    rows = _iter_from_db()
    source = "database"
    if not rows:
        rows = _iter_from_fs()
        source = "filesystem"

    classes: Counter[str] = Counter()
    fail_open: list[dict] = []
    fail_open_by_tech: Counter[str] = Counter()
    fail_open_by_first_line: dict[str, list[str]] = defaultdict(list)

    for slug, tech, sim_type, db_script in rows:
        cls, output = classify(slug, sim_type, db_script)
        classes[cls] += 1
        if cls == "FAIL-OPEN":
            first = _first_check_line(db_script)
            fail_open.append(
                {
                    "slug": slug,
                    "technology": tech,
                    "simulation_type": sim_type,
                    "first_check_line": first,
                    "grader_output": output,
                }
            )
            fail_open_by_tech[tech] += 1
            fail_open_by_first_line[first].append(slug)

    total = sum(classes.values())
    print("=" * 72)
    print(f"GRADER-INTEGRITY SCAN  (source: {source})")
    print("=" * 72)
    print(f"Scenarios scanned : {total}")
    for cls in ("FAIL-OPEN", "NO-MATCH", "FAIL-CLOSED", "ERROR"):
        if classes.get(cls):
            print(f"  {cls:<12}: {classes[cls]}")
    print()

    print("FAIL-OPEN by technology")
    print("-" * 40)
    for tech, cnt in fail_open_by_tech.most_common():
        print(f"  {tech:<18}: {cnt}")
    print()

    print("FAIL-OPEN grouped by first check line (count : line)")
    print("-" * 40)
    grouped = sorted(
        fail_open_by_first_line.items(), key=lambda kv: len(kv[1]), reverse=True
    )
    for line, slugs in grouped:
        print(f"  {len(slugs):>4} : {line}")
    print()

    payload = {
        "source": source,
        "total_scanned": total,
        "counts": dict(classes),
        "fail_open_count": classes.get("FAIL-OPEN", 0),
        "fail_open_by_technology": dict(fail_open_by_tech.most_common()),
        "fail_open_by_first_check_line": {
            line: sorted(slugs) for line, slugs in grouped
        },
        "fail_open_slugs": sorted(f["slug"] for f in fail_open),
    }
    print("JSON SUMMARY")
    print("-" * 40)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
