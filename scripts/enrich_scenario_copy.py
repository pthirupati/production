#!/usr/bin/env python3
"""Rewrite scenario descriptions, objectives, and hints for clarity.

Updates academy labs with topic-specific narratives and lightly improves
thin/generic hand-authored scenarios.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from scenario_copy_library import enrich_scenario_data, is_generic_academy_copy

ROOT = Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios"


def enrich_file(path: Path, *, dry_run: bool = False, force: bool = False) -> str:
    tech_dir = path.parent.parent.name
    folder = path.parent.name
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return "skip"
    if not force and not is_generic_academy_copy(data) and folder.startswith("academy-"):
        return "skip"

    enriched = enrich_scenario_data(data, folder_name=folder, tech_dir=tech_dir)
    if not enriched:
        return "skip"

    if dry_run:
        return "would_update"

    path.write_text(
        yaml.dump(enriched, default_flow_style=False, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return "updated"


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich scenario descriptions and hints")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-enrich even if copy looks custom")
    parser.add_argument("--technology", default="", help="Comma-separated tech folder slugs")
    args = parser.parse_args()

    tech_filter = {t.strip() for t in args.technology.split(",") if t.strip()}
    stats = {"updated": 0, "skip": 0, "would_update": 0, "error": 0}

    for tech_path in sorted(SCEN.iterdir()):
        if not tech_path.is_dir() or tech_path.name == "shared":
            continue
        if tech_filter and tech_path.name not in tech_filter:
            continue
        for yaml_path in sorted(tech_path.glob("*/scenario.yaml")):
            try:
                result = enrich_file(yaml_path, dry_run=args.dry_run, force=args.force)
            except Exception:
                stats["error"] = stats.get("error", 0) + 1
                continue
            stats[result] = stats.get(result, 0) + 1

    print(
        f"Enrichment complete — updated: {stats.get('updated', 0)}, "
        f"would_update: {stats.get('would_update', 0)}, skipped: {stats.get('skip', 0)}"
    )


if __name__ == "__main__":
    main()
