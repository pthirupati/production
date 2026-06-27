#!/usr/bin/env python3
"""Integrity sweep across every scenario that validates via check.sh.

For each scenario whose simulation routes through `validate_simulation_state`
(generic / rhel / ansible / database / gpu / python / java / windows / k8s
marker / networking / devops / etc.), this builds the engine the real way,
runs the shipped check.sh against the FRESH (unfixed) broken state, and flags:

  • FAIL-OPEN   — validation PASSES with no fix (a learner could pass for free)
  • NO-MATCH    — no validation check matched (check.sh can't grade the lab)
  • TRIVIAL     — check.sh would always pass / is not configured
  • ERROR       — building the engine or validating raised

Scenarios that route to a dedicated engine in production (vmware / nmap /
wireshark / terraform / windows-server / peoplesoft / datascience / awx /
baremetal-virt / ai-agent) are reported as SKIPPED — they have their own
validators/tests and cannot be judged through this path.

Run from the repo root:  python3 scripts/validate_all_scenarios.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios"
sys.path.insert(0, str(ROOT / "backend"))

import yaml  # noqa: E402

from apps.labs.provisioner.simulation.unified_sim import (  # noqa: E402
    UnifiedSimulationEngine,
)
from apps.labs.provisioner.simulation.validation import (  # noqa: E402
    is_trivial_validation_script,
    resolve_simulation_validation_script,
    validate_simulation_state,
)


def routed_away(slug: str, st: str) -> str | None:
    """Mirror SimulationProvisioner.run_validation's dedicated-engine routing."""
    s = slug.lower()
    if "vmware" in s:
        return "vmware"
    if s.startswith("nmap-") or st == "nmap":
        return "nmap"
    if s.startswith("wireshark-") or st == "wireshark":
        return "wireshark"
    if s.startswith("agent-") or st == "ai-agent":
        return "ai-agent"
    if s.startswith("win-gui-") or st == "windows-server":
        return "windows-server"
    if s.startswith("ps-") or st == "peoplesoft":
        return "peoplesoft"
    if s.startswith("ds-dashboard-") or st in ("data-dashboard", "datascience"):
        return "datascience"
    if "awx" in s or "tower" in s or st == "ansible-awx":
        return "awx"
    if st == "terraform" or s.startswith("terraform-"):
        return "terraform"
    if st == "baremetal" and any(k in s for k in ("maas", "lxd", "lxc", "kvm", "virsh", "ipmi")):
        return "baremetal-virt"
    return None


def classify(slug: str, sim_type: str, check: str) -> str:
    # Production resolves a canonical script by slug FIRST — even when check.sh is
    # missing or trivial it may supply a real state-based check. Mirror that.
    script = resolve_simulation_validation_script(slug, check or "")
    if is_trivial_validation_script(script):
        return "TRIVIAL"
    engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type or "generic")
    ok, msg = validate_simulation_state(engine.shell.state, script, engine)
    if ok:
        return "FAIL-OPEN"
    if "No validation checks matched" in msg:
        return "NO-MATCH"
    if "Validation not configured" in msg:
        return "TRIVIAL"
    return "OK"


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    buckets: dict[str, list[str]] = defaultdict(list)
    skipped: dict[str, int] = defaultdict(int)
    by_tech_flagged: dict[str, int] = defaultdict(int)
    total = 0

    for yml in sorted(SCEN.glob("*/*/scenario.yaml")):
        folder = yml.parent
        tech = folder.parent.name
        if only and only != tech:
            continue
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            buckets["YAML-ERROR"].append(f"{tech}/{folder.name}: {exc}")
            continue
        slug = data.get("slug") or folder.name
        sim_type = (data.get("simulation_type") or "generic")
        total += 1

        # Only labs that actually run through the in-memory simulation engine are
        # judged here. Real Docker/VM container labs run their check.sh in a live
        # environment, and coding-IDE labs grade user code against test cases —
        # neither uses validate_simulation_state, so flagging them is a false
        # positive.
        # Match seed_scenarios: a missing lab_mode defaults to "docker" (a real
        # container lab), NOT simulation.
        lab_mode = (data.get("lab_mode") or "docker").lower()
        if lab_mode != "simulation":
            skipped[f"lab_mode:{lab_mode}"] += 1
            continue
        if data.get("coding_mode") or data.get("coding_spec"):
            skipped["coding-ide"] += 1
            continue

        away = routed_away(slug, sim_type)
        if away:
            skipped[away] += 1
            continue

        check_path = folder / "check.sh"
        check = check_path.read_text(encoding="utf-8") if check_path.is_file() else ""
        has_file = check_path.is_file()
        try:
            verdict = classify(slug, sim_type, check)
        except Exception as exc:  # noqa: BLE001
            buckets["ERROR"].append(f"{tech}/{slug}: {type(exc).__name__}: {exc}")
            by_tech_flagged[tech] += 1
            continue
        if verdict != "OK":
            # Distinguish "no check.sh AND nothing canonical resolved" from a
            # present-but-trivial check.
            if verdict == "TRIVIAL" and not has_file:
                verdict = "NO-CHECK-FILE"
            buckets[verdict].append(f"{tech}/{slug}")
            by_tech_flagged[tech] += 1

    checked = total - sum(skipped.values())
    print(f"scenarios scanned: {total}")
    print(f"  routed to dedicated engines (skipped here): {sum(skipped.values())}")
    for k, v in sorted(skipped.items(), key=lambda x: -x[1]):
        print(f"      {k:16s} {v}")
    print(f"  validated via check.sh: {checked}")
    flagged = sum(len(v) for v in buckets.values())
    print(f"  flagged: {flagged}")
    for cat in ("FAIL-OPEN", "NO-MATCH", "TRIVIAL", "NO-CHECK-FILE", "ERROR", "YAML-ERROR"):
        items = buckets.get(cat, [])
        if not items:
            continue
        print(f"\n=== {cat} ({len(items)}) ===")
        for s in items[:40]:
            print(f"  {s}")
        if len(items) > 40:
            print(f"  … +{len(items) - 40} more")
    if by_tech_flagged:
        print("\n--- flagged by tech ---")
        for t, n in sorted(by_tech_flagged.items(), key=lambda x: -x[1]):
            print(f"  {t:16s} {n}")


if __name__ == "__main__":
    main()
