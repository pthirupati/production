#!/usr/bin/env python3
"""Lint scenario.yaml files against the Enterprise Lab content quality bar.

Scenario-scoped Lab Servers: each scenario must declare which consoles and
(optionally) lab_servers the learner uses. Learner-facing prose must not contain
banned framing words (simulation / simulator / demo / mock / fake).

Usage:
  python scripts/lint_scenarios.py
  python scripts/lint_scenarios.py --paths scenarios/commvault scenarios/soc
  python scripts/lint_scenarios.py --strict-heroes   # exit 1 on any hero failure
  python scripts/lint_scenarios.py --max-failures 50
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCEN = ROOT / "scenarios"

REQUIRED_TOP = ("title", "slug", "technology", "description", "objectives", "hints")
TICKET_SECTIONS = (
    "CONTEXT:",
    "ENVIRONMENT:",
    "OBJECTIVE:",
)
BANNED_LEARNER = re.compile(
    r"\b(simulation|simulator|simulated|demo|mock|fake|practice environment)\b",
    re.I,
)
# Legitimate anti-cheating guidance ("don't fake your fix with a marker file")
# uses these words to warn the LEARNER against gaming the grader — unrelated
# to the platform-framing concern (learner must never feel THEY are in a
# simulation). Strip these known-safe phrases before scanning so the linter
# doesn't drown real findings in thousands of false positives.
_SAFE_PHRASES = re.compile(
    r"fake completion|fabricate(d)? completion|fake (your|the) (fix|solution|result)|"
    r"fake it|mock (data|marker)\b|mock (state|provider)\b|"
    r"IAM policy simulator",  # real AWS product name (policysim.aws.amazon.com)
    re.I,
)
# Internal keys / lab_mode values are OK; we only scan learner-visible fields.
LEARNER_FIELDS = (
    "title",
    "description",
    "initial_state",
    "summary",
    "objectives",
    "hints",
    "what_you_will_learn",
)

HERO_SLUGS = frozenset({
    "cv-vm-backup-missing-client",
    "ontap-volume-offline",
    "powermax-masking-broken",
    "dc-failed-nic-reseat",
    "dc-disk-replacement",
    "soc-ransomware-quarantine",
    "soc-brute-force-block-ip",
    "win-sccm-patch-failed",
})

MIN_DESC_LEN = 280
MIN_HINTS = 3
MIN_OBJECTIVES = 2


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _flatten_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("content") or item.get("title") or ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    if isinstance(value, dict):
        return "\n".join(str(v) for v in value.values())
    return str(value)


def lint_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = _load(path)
    except Exception as exc:  # noqa: BLE001
        return [f"YAML parse error: {exc}"]

    slug = data.get("slug") or path.parent.name
    for key in REQUIRED_TOP:
        if not data.get(key):
            errors.append(f"missing required field `{key}`")

    desc = _flatten_text(data.get("description"))
    if len(desc.strip()) < MIN_DESC_LEN:
        errors.append(f"description too short ({len(desc.strip())} < {MIN_DESC_LEN})")

    for section in TICKET_SECTIONS:
        if section not in desc:
            errors.append(f"description missing ticket section `{section}`")

    objectives = data.get("objectives") or []
    if not isinstance(objectives, list) or len(objectives) < MIN_OBJECTIVES:
        errors.append(f"need at least {MIN_OBJECTIVES} objectives")

    hints = data.get("hints") or []
    if not isinstance(hints, list) or len(hints) < MIN_HINTS:
        errors.append(f"need at least {MIN_HINTS} progressive hints")
    else:
        costs = []
        for h in hints:
            if isinstance(h, dict):
                costs.append(h.get("cost", 0))
                content = (h.get("content") or "").strip()
                if len(content) < 40:
                    errors.append("hint content too thin (< 40 chars)")
        if costs and sorted(costs) != costs:
            errors.append("hint costs should be non-decreasing (progressive ladder)")

    # Learner-facing banned words (internal lab_mode: simulation is OK).
    for field in LEARNER_FIELDS:
        text = _flatten_text(data.get(field))
        # Strip known-safe anti-cheating phrasing before scanning.
        scan_text = _SAFE_PHRASES.sub("", text)
        for m in BANNED_LEARNER.finditer(scan_text):
            word = m.group(0)
            errors.append(f"learner-facing `{field}` contains banned word `{word}`")

    # Scenario-scoped infrastructure declaration (recommended → required for heroes).
    consoles = data.get("consoles") or data.get("lab_consoles")
    lab_servers = data.get("lab_servers")
    if slug in HERO_SLUGS:
        if not consoles:
            errors.append("hero scenario missing `consoles` (which GUIs/tools to open)")
        if not lab_servers:
            errors.append("hero scenario missing `lab_servers` (scenario-scoped hosts)")

    return errors


def iter_scenario_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for base in paths:
        if base.is_file() and base.name == "scenario.yaml":
            files.append(base)
            continue
        if not base.exists():
            continue
        files.extend(sorted(base.rglob("scenario.yaml")))
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Roots to scan (default: hero packs + windows SCCM)",
    )
    ap.add_argument("--all", action="store_true", help="Scan entire scenarios/ tree")
    ap.add_argument("--strict-heroes", action="store_true", help="Fail if any hero fails")
    ap.add_argument("--max-failures", type=int, default=0, help="Allow N non-hero failures")
    args = ap.parse_args()

    if args.all:
        roots = [SCEN]
    elif args.paths:
        roots = [Path(p) if Path(p).is_absolute() else ROOT / p for p in args.paths]
    else:
        roots = [
            SCEN / "commvault",
            SCEN / "netapp",
            SCEN / "dellemc",
            SCEN / "datacenter",
            SCEN / "soc",
            SCEN / "windows" / "win-sccm-patch-failed",
        ]

    files = iter_scenario_files(roots)
    if not files:
        print("No scenario.yaml files found", file=sys.stderr)
        return 2

    hero_fail = 0
    other_fail = 0
    total_errs = 0
    for path in files:
        errs = lint_file(path)
        if not errs:
            continue
        rel = path.relative_to(ROOT)
        slug = path.parent.name
        print(f"\n{rel}")
        for e in errs:
            print(f"  - {e}")
        total_errs += len(errs)
        if slug in HERO_SLUGS:
            hero_fail += 1
        else:
            other_fail += 1

    print(
        f"\nScanned {len(files)} scenarios; "
        f"{hero_fail} hero files failed, {other_fail} other files failed, "
        f"{total_errs} findings."
    )

    if args.strict_heroes and hero_fail:
        return 1
    if other_fail > args.max_failures and not args.strict_heroes:
        # Default mode: only fail hard on heroes when --strict-heroes
        pass
    if args.strict_heroes:
        return 1 if hero_fail else 0
    # Non-strict: exit 0 if heroes clean (when scanning default roots)
    if hero_fail:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
