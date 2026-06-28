"""Validate tutorial lesson richness for CI.

Usage:
  python manage.py check_tutorial_completeness --all
  python manage.py check_tutorial_completeness --technology=Linux
"""
from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from apps.tutorials.completeness import validate_tutorial
from apps.tutorials.models import Tutorial


class Command(BaseCommand):
    help = "Check tutorials for diagrams, code, tables, callouts, quizzes, and linked labs."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Check all published tutorials")
        parser.add_argument("--technology", default="", help="Filter by tutorial.topic (case-insensitive)")
        parser.add_argument("--limit", type=int, default=0, help="Stop after N tutorials (smoke)")
        parser.add_argument("--fail-on-gaps", action="store_true", default=True)

    def handle(self, *args, **options):
        qs = Tutorial.objects.filter(is_published=True).prefetch_related("sections").order_by("topic", "order")
        tech = (options.get("technology") or "").strip()
        if tech:
            qs = qs.filter(topic__iexact=tech)

        limit = int(options.get("limit") or 0)
        checked = 0
        failures: list[tuple[str, list[str]]] = []

        for tutorial in qs:
            checked += 1
            result = validate_tutorial(tutorial)
            if result.gaps:
                failures.append((tutorial.slug, result.gaps))
            if limit and checked >= limit:
                break

        self.stdout.write(
            f"Scanned {checked} tutorials — {checked - len(failures)} complete, {len(failures)} with gaps"
        )
        for slug, gaps in failures[:50]:
            self.stdout.write(f"  {slug}:")
            for gap in gaps:
                self.stdout.write(f"    - {gap}")
        if len(failures) > 50:
            self.stdout.write(f"  ... and {len(failures) - 50} more")

        if failures and options.get("fail_on_gaps", True):
            sys.exit(1)
