#!/usr/bin/env python3
"""
Rewrite scenario.yaml copy so descriptions/symptoms stay in description+initial_state
and fix steps live only in hints.

Run from repo root: python3 scripts/sanitize_scenario_copy.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"

FIX_VERBS = re.compile(
    r"^\s*(fix|repair|restore|correct|update|edit|change|replace|remove|delete|"
    r"extend|grow|resize|remount|rebuild|add|create|run|execute|use|set|point|"
    r"mount|enable|disable|start|stop|restart|configure|install|apply|chmod|chown|"
    r"compare|inspect|verify|test with|uncomment|comment|adjust|reset|clear|free)\b",
    re.I,
)


def is_fix_step(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if FIX_VERBS.search(t):
        return True
    if "`" in t:
        return True
    return False


def outcome_from_fix(text: str) -> str:
    t = text.strip()
    low = t.lower()
    if low.startswith("verify ") or low.startswith("confirm "):
        return t
    if "getent hosts" in low:
        return "Internal hostname resolution works"
    if "blkid" in low or "uuid" in low:
        return "/mnt/data is mounted and data is accessible"
    if "mount -a" in low:
        return "All fstab entries mount successfully"
    if "vgs" in low or "lvs" in low or "df" in low:
        return "Storage layout and utilization are understood"
    if "extend" in low and "lv" in low:
        return "/data has sufficient free space for applications"
    if "grow" in low and "xfs" in low:
        return "Filesystem on /data accepts new writes"
    if "remount" in low:
        return "/data accepts writes again"
    if "nameserver" in low or "resolv" in low:
        return "DNS lookups succeed for required hostnames"
    return "Affected service behaves normally"


def strip_fix_from_description(desc: str) -> str:
    """Remove trailing fix sentences from description paragraphs."""
    if not desc:
        return desc
    lines = []
    for line in desc.splitlines():
        stripped = line.strip()
        if is_fix_step(stripped):
            continue
        if re.search(r"\b(you must|extend the|fix the|repair the|add .+ disk|rebuild)\b", stripped, re.I):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def process_file(path: Path) -> bool:
    data = yaml.safe_load(path.read_text()) or {}
    changed = False
    hints = list(data.get("hints") or [])
    hint_contents = {h.get("content", "") for h in hints if isinstance(h, dict)}

    objectives = list(data.get("objectives") or [])
    new_objectives = []
    for obj in objectives:
        if not isinstance(obj, str):
            new_objectives.append(obj)
            continue
        if is_fix_step(obj):
            if obj not in hint_contents:
                order = max((h.get("order", 0) for h in hints), default=0) + 1
                hints.append({"order": order, "cost": 15, "content": obj})
                hint_contents.add(obj)
                changed = True
            outcome = outcome_from_fix(obj)
            if outcome not in new_objectives:
                new_objectives.append(outcome)
            changed = True
        else:
            new_objectives.append(obj)

    desc = data.get("description") or ""
    new_desc = strip_fix_from_description(desc)
    if new_desc != desc:
        data["description"] = new_desc
        changed = True

    if new_objectives != objectives:
        data["objectives"] = new_objectives
        changed = True
    if hints != data.get("hints"):
        data["hints"] = sorted(hints, key=lambda h: h.get("order", 0))
        changed = True

    if changed:
        path.write_text(yaml.dump(data, sort_keys=False, allow_unicode=True, width=1000))
    return changed


def main() -> int:
    updated = 0
    for yaml_path in sorted(SCENARIOS.glob("**/scenario.yaml")):
        if process_file(yaml_path):
            print(f"updated {yaml_path.relative_to(ROOT)}")
            updated += 1
    print(f"Done — {updated} scenario(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
