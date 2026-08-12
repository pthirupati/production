"""Seed certification tracks, objectives, and their scenario mappings.

Run AFTER ``seed_scenarios`` (the scenarios must exist first). Idempotent —
re-running ``update_or_create``s tracks/objectives and (re)links scenarios.

Two mapping sources, both honored:
  1. Inline lists in each track's ``data/<track>.yaml`` (primary, used today).
  2. An optional ``cert_objectives: [code, ...]`` key on any
     ``scenarios/<tech>/<slug>/scenario.yaml`` (for new original scenarios that
     want to self-declare their objective). The scan is best-effort and skipped
     if the scenarios directory can't be located.

Scenario slugs that don't resolve are reported and skipped — never fatal.
"""

import glob
import os

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.certifications.models import (
    CertificationTrack,
    CertObjective,
    TrackScenario,
)
from apps.question_bank.models import Scenario, Technology

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TRACK_FILES = [
    "rhcsa.yaml",
    "rhce.yaml",
    "cka.yaml",
    "ckad.yaml",
    "cks.yaml",
    "lfcs.yaml",
    "terraform-associate.yaml",
    "aws-solutions-architect-associate.yaml",
    "azure-administrator-associate.yaml",
    "gcp-associate-cloud-engineer.yaml",
    "python-developer.yaml",
    "linux-security-engineer.yaml",
    "network-engineer.yaml",
    # Expert tier — sits above every associate/professional track above.
    "platform-architect-expert.yaml",
]


class Command(BaseCommand):
    help = "Seed certification tracks, objectives, and scenario mappings."

    def handle(self, *args, **options):
        total_tracks = 0
        total_links = 0
        missing = []

        for fname in TRACK_FILES:
            path = os.path.join(DATA_DIR, fname)
            if not os.path.exists(path):
                self.stderr.write(f"  ! track file not found: {fname}")
                continue
            with open(path, "r", encoding="utf-8") as fh:
                spec = yaml.safe_load(fh) or {}
            links, miss = self._seed_track(spec)
            total_tracks += 1
            total_links += links
            missing.extend(miss)

        scanned = self._scan_scenario_tags()
        total_links += scanned

        self.stdout.write(
            self.style.SUCCESS(
                f"Certifications seeded: {total_tracks} track(s), "
                f"{total_links} scenario link(s)."
            )
        )
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"  {len(missing)} mapped slug(s) not found and skipped: "
                    + ", ".join(sorted(set(missing))[:20])
                    + ("..." if len(set(missing)) > 20 else "")
                )
            )

    def _seed_track(self, spec):
        t = spec.get("track") or {}
        slug = t.get("slug")
        if not slug:
            self.stderr.write("  ! track spec missing slug; skipping")
            return 0, []

        technology = None
        tech_slug = t.get("technology_slug")
        if tech_slug:
            technology = Technology.objects.filter(slug=tech_slug).first()

        track, _ = CertificationTrack.objects.update_or_create(
            slug=slug,
            defaults={
                "code": t.get("code", slug.upper()),
                "name": t.get("name", slug),
                "vendor": t.get("vendor", ""),
                "description": (t.get("description") or "").strip(),
                "technology": technology,
                "exam_duration_minutes": t.get("exam_duration_minutes", 180),
                "passing_score": t.get("passing_score", 70),
                "validity_months": t.get("validity_months", 36),
                "is_active": t.get("is_active", True),
                "order": t.get("order", 0),
            },
        )

        links = 0
        missing = []
        for obj_spec in spec.get("objectives", []):
            objective, _ = CertObjective.objects.update_or_create(
                track=track,
                code=obj_spec["code"],
                defaults={
                    "title": obj_spec.get("title", obj_spec["code"]),
                    "description": (obj_spec.get("description") or "").strip(),
                    "weight": obj_spec.get("weight", 1),
                    "order": obj_spec.get("order", 0),
                },
            )
            for order, scen_slug in enumerate(obj_spec.get("scenarios", [])):
                scenario = Scenario.objects.filter(slug=scen_slug).first()
                if not scenario:
                    missing.append(scen_slug)
                    continue
                TrackScenario.objects.update_or_create(
                    objective=objective,
                    scenario=scenario,
                    defaults={"order": order, "in_exam_pool": True},
                )
                links += 1

        self.stdout.write(f"  • {track.code}: {links} scenario(s) linked")
        return links, missing

    def _find_scenarios_dir(self):
        candidates = [
            os.path.join(getattr(settings, "BASE_DIR", ""), "scenarios"),
            os.path.join(os.path.dirname(getattr(settings, "BASE_DIR", "")), "scenarios"),
        ]
        for c in candidates:
            if c and os.path.isdir(c):
                return c
        return None

    def _scan_scenario_tags(self):
        """Best-effort: link scenarios that self-declare `cert_objectives`."""
        root = self._find_scenarios_dir()
        if not root:
            return 0
        objectives_by_code = {o.code: o for o in CertObjective.objects.all()}
        if not objectives_by_code:
            return 0
        links = 0
        for path in glob.glob(os.path.join(root, "*", "*", "scenario.yaml")):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
            except Exception:
                continue
            codes = data.get("cert_objectives") or []
            slug = data.get("slug")
            if not codes or not slug:
                continue
            scenario = Scenario.objects.filter(slug=slug).first()
            if not scenario:
                continue
            for code in codes:
                objective = objectives_by_code.get(code)
                if not objective:
                    continue
                _, created = TrackScenario.objects.update_or_create(
                    objective=objective,
                    scenario=scenario,
                    # Stable, non-colliding order for tag-linked scenarios
                    # (the inline-list path uses a 0-based index instead).
                    defaults={"in_exam_pool": True, "order": scenario.id},
                )
                if created:
                    links += 1
        return links
