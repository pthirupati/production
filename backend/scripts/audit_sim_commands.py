"""Audit every simulation scenario: run its guided/solution commands through the
unified simulation engine and report commands that are missing or error out.

Usage:
    python scripts/audit_sim_commands.py [tech ...]     # e.g. linux rhel-linux windows
    python scripts/audit_sim_commands.py --all

Output: a summary of `command not found` hits grouped by command, plus per-tech
failure counts, so missing shell features can be added to the engine.
"""

from __future__ import annotations

import glob
import os
import re
import sys
from collections import Counter, defaultdict

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
django.setup()

import yaml  # noqa: E402

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine  # noqa: E402

SCENARIOS_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "scenarios")

# Sim types that run through the RHEL unified engine terminal.
TERMINAL_SIM_TYPES = {
    "generic", "rhel", "linux", "gpu", "database", "networking", "devops",
    "terraform", "windows", "ansible", "kubernetes", "docker", "baremetal",
}

SKIP_COMMAND_PREFIXES = (
    "#", "<", "your ", "…", "...", "check.sh", "bash check.sh", "./check.sh",
)

NOT_FOUND_RE = re.compile(r"command not found|Unknown operation|no such command", re.I)


def commands_for(doc: dict) -> list[str]:
    cmds: list[str] = []
    gm = doc.get("guided_mode") or {}
    for step in gm.get("steps") or []:
        c = (step.get("command") or "").strip()
        if c:
            cmds.append(c)
    sol = doc.get("solution") or {}
    for c in sol.get("commands_run") or []:
        c = (c or "").strip()
        if c:
            cmds.append(c)
    for task in doc.get("tasks") or []:
        val = task.get("validation") or {}
        c = (val.get("command") or "").strip()
        if c:
            cmds.append(c)
    out = []
    for c in cmds:
        low = c.lower()
        if any(low.startswith(p) for p in SKIP_COMMAND_PREFIXES):
            continue
        out.append(c)
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    techs = args or ["linux", "rhel-linux", "windows", "devops", "networking", "shell-script", "database", "security"]
    if "--all" in sys.argv:
        techs = sorted(
            d for d in os.listdir(SCENARIOS_ROOT)
            if os.path.isdir(os.path.join(SCENARIOS_ROOT, d))
        )

    missing = Counter()
    missing_examples: dict[str, str] = {}
    per_tech_fail = defaultdict(int)
    per_tech_total = defaultdict(int)
    scanned = 0

    for tech in techs:
        pattern = os.path.join(SCENARIOS_ROOT, tech, "*", "scenario.yaml")
        for path in sorted(glob.glob(pattern)):
            try:
                doc = yaml.safe_load(open(path)) or {}
            except Exception:
                continue
            if (doc.get("lab_mode") or "") != "simulation":
                continue
            sim_type = doc.get("simulation_type") or "generic"
            if sim_type not in TERMINAL_SIM_TYPES:
                continue
            slug = doc.get("slug") or os.path.basename(os.path.dirname(path))
            cmds = commands_for(doc)
            if not cmds:
                continue
            scanned += 1
            per_tech_total[tech] += 1
            try:
                engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
            except Exception as exc:
                per_tech_fail[tech] += 1
                missing[f"<engine boot failure: {exc}>"] += 1
                continue
            sh = engine.shell
            had_fail = False
            for cmd in cmds:
                try:
                    out = sh.run(cmd) or ""
                except Exception as exc:
                    had_fail = True
                    key = cmd.split()[0] if cmd.split() else cmd
                    missing[f"<exception:{key}: {type(exc).__name__}>"] += 1
                    missing_examples.setdefault(f"<exception:{key}>", f"{slug}: {cmd}")
                    continue
                if NOT_FOUND_RE.search(out):
                    had_fail = True
                    key = cmd.split()[0] if cmd.split() else cmd
                    missing[key] += 1
                    missing_examples.setdefault(key, f"{slug}: {cmd}")
            if had_fail:
                per_tech_fail[tech] += 1

    print(f"\nScanned {scanned} simulation scenarios across {len(techs)} technologies\n")
    print("=== Scenarios with at least one failing command, by technology ===")
    for tech in sorted(per_tech_total):
        print(f"  {tech:<16} {per_tech_fail[tech]:>4} / {per_tech_total[tech]}")
    print("\n=== Missing / failing commands (count, first example) ===")
    for cmd, count in missing.most_common(60):
        print(f"  {count:>5}  {cmd:<28} e.g. {missing_examples.get(cmd, '')[:90]}")


if __name__ == "__main__":
    main()
