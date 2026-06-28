"""Validate every scenario.yaml for catalog completeness (B6).

Checks description, guided hints, validation script quality, objectives, and
academy marker-only labs. Idempotent read-only unless --fix-hints is passed
(re-invokes enrich_scenario_copy for thin entries).

Usage:
  python manage.py validate_scenario_catalog
  python manage.py validate_scenario_catalog --technology linux
  python manage.py validate_scenario_catalog --fail-on-gaps
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

ROOT = Path(__file__).resolve().parents[5]
SCEN = ROOT / "scenarios"

MARKER_ONLY_RE = re.compile(r"grep\s+-q\s+FIXED-OK|FIXED-OK.*grep", re.I)
GUIDED_HINT_RE = re.compile(r"(Orient yourself|Plan your approach|Guided walkthrough|\n1\.\s)", re.I)
ACADEMY_SLUG_RE = re.compile(r"^academy-")


def validate_scenario_file(path: Path) -> list[str]:
    """Return list of gap messages for one scenario.yaml."""
    gaps: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]

    slug = data.get("slug") or path.parent.name
    desc = (data.get("description") or "").strip()
    if len(desc) < 80:
        gaps.append("description too short (<80 chars)")

    objectives = data.get("objectives") or []
    if len(objectives) < 2:
        gaps.append("fewer than 2 objectives")

    hints = data.get("hints") or []
    if len(hints) < 3:
        gaps.append("fewer than 3 hints")
    else:
        for i, h in enumerate(sorted(hints, key=lambda x: x.get("order", 0))[:3], 1):
            content = (h.get("content") or "").strip()
            if len(content) < 40:
                gaps.append(f"hint {i} too short")
            elif not GUIDED_HINT_RE.search(content):
                gaps.append(f"hint {i} not step-by-step guided format")

    check_sh = path.parent / "check.sh"
    validation = (data.get("validation_script") or "").strip()
    script_body = validation
    if check_sh.is_file():
        script_body = check_sh.read_text(encoding="utf-8")
    if not script_body.strip():
        gaps.append("no validation script / check.sh")
    elif MARKER_ONLY_RE.search(script_body) and not ACADEMY_SLUG_RE.match(slug):
        gaps.append("marker-only validation (FIXED-OK grep)")
    elif MARKER_ONLY_RE.search(script_body) and ACADEMY_SLUG_RE.match(slug):
        gaps.append("academy lab still uses FIXED-OK marker check")

    return gaps


class Command(BaseCommand):
    help = "Validate scenario catalog completeness (descriptions, guided hints, real validation)."

    def add_arguments(self, parser):
        parser.add_argument("--technology", default="", help="Comma-separated tech folder slugs")
        parser.add_argument(
            "--flagship-only",
            action="store_true",
            help="Only validate labs in flagship_presets.FLAGSHIP_SLUG_KIND (real-sim upgraded set)",
        )
        parser.add_argument("--fail-on-gaps", action="store_true", help="Exit 1 if any gaps found")
        parser.add_argument("--limit", type=int, default=0, help="Stop after N scenarios (smoke)")

    def handle(self, *args, **options):
        tech_filter = {t.strip() for t in options["technology"].split(",") if t.strip()}
        flagship_only = bool(options["flagship_only"])
        flagship_slugs: set[str] = set()
        if flagship_only:
            from apps.labs.provisioner.simulation.flagship_presets import FLAGSHIP_SLUG_KIND

            flagship_slugs = set(FLAGSHIP_SLUG_KIND)
        limit = int(options["limit"] or 0)
        total = 0
        gap_count = 0
        gap_rows: list[tuple[str, list[str]]] = []

        for tech_path in sorted(SCEN.iterdir()):
            if not tech_path.is_dir() or tech_path.name == "shared":
                continue
            if tech_filter and tech_path.name not in tech_filter:
                continue
            for yaml_path in sorted(tech_path.glob("*/scenario.yaml")):
                if flagship_only:
                    slug = yaml_path.parent.name
                    if slug not in flagship_slugs:
                        continue
                total += 1
                gaps = validate_scenario_file(yaml_path)
                if gaps:
                    gap_count += 1
                    rel = yaml_path.relative_to(ROOT)
                    gap_rows.append((str(rel), gaps))
                if limit and total >= limit:
                    break
            if limit and total >= limit:
                break

        self.stdout.write(f"Scanned {total} scenarios — {gap_count} with gaps, {total - gap_count} clean")
        for rel, gaps in gap_rows[:50]:
            self.stdout.write(f"  {rel}:")
            for g in gaps:
                self.stdout.write(f"    - {g}")
        if len(gap_rows) > 50:
            self.stdout.write(f"  ... and {len(gap_rows) - 50} more")

        if options["fail_on_gaps"] and gap_count:
            sys.exit(1)
