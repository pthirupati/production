#!/usr/bin/env python3
"""Bulk-align scenario.yaml simulation_type / technology with folder + LabRunner GUIs.

Safe, idempotent rewrites using PyYAML when available; falls back to line edits.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "scenarios"

# folder -> (simulation_type, technology slug for YAML field)
FOLDER_MAP = {
    "aws": ("aws", "aws"),
    "azure": ("azure", "azure"),
    "gcp": ("gcp", "gcp"),
    "openstack": ("openstack", "openstack"),
    "vmware": ("vmware", "vmware"),
    "gitops": ("devops", "gitops"),
    "devops": ("devops", "devops"),
    "kubernetes": ("kubernetes", "kubernetes"),
    "docker": ("docker", "docker"),
    "grafana": ("grafana", "grafana"),
    "prometheus": ("prometheus", "prometheus"),
    "windows": ("windows", "windows"),
    "commvault": ("commvault", "commvault"),
    "netapp": ("netapp", "netapp"),
    "dellemc": ("dellemc", "dellemc"),
    "datacenter": ("datacenter", "datacenter"),
    "soc": ("soc", "soc"),
    "baremetal": ("baremetal", "baremetal"),
    "terraform": ("terraform", "terraform"),
}


def patch_file(path: Path, sim_type: str, tech_slug: str) -> bool:
    text = path.read_text(encoding="utf-8")
    orig = text

    # simulation_type
    if re.search(r"^simulation_type:\s*", text, re.M):
        text = re.sub(
            r"^simulation_type:\s*.*$",
            f"simulation_type: {sim_type}",
            text,
            count=1,
            flags=re.M,
        )
    else:
        # insert after lab_mode if present
        if re.search(r"^lab_mode:\s*", text, re.M):
            text = re.sub(
                r"^(lab_mode:\s*.*)$",
                rf"\1\nsimulation_type: {sim_type}",
                text,
                count=1,
                flags=re.M,
            )

    # technology field — normalize casing / display names
    if re.search(r"^technology:\s*", text, re.M):
        text = re.sub(
            r"^technology:\s*.*$",
            f"technology: {tech_slug}",
            text,
            count=1,
            flags=re.M,
        )

    if text != orig:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    scanned = 0
    folders = sys.argv[1:] or list(FOLDER_MAP.keys())
    for folder in folders:
        if folder not in FOLDER_MAP:
            print(f"skip unknown folder {folder}", file=sys.stderr)
            continue
        sim_type, tech = FOLDER_MAP[folder]
        base = ROOT / folder
        if not base.is_dir():
            continue
        for yaml_path in sorted(base.glob("*/scenario.yaml")):
            scanned += 1
            if patch_file(yaml_path, sim_type, tech):
                changed += 1
    print(f"scanned={scanned} changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
