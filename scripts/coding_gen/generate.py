#!/usr/bin/env python3
"""Generate FixitLab coding-IDE scenarios with built-in integrity verification.

For EVERY scenario we run its (visible + hidden) tests through the real backend
grader twice — once against the broken starter (must FAIL) and once against the
reference solution (must PASS) — BEFORE writing any YAML. A scenario that fails
either gate is refused and reported; nothing is written for it.

Usage (from repo root):
    cd backend && DJANGO_SETTINGS_MODULE=config.test_settings \
        .venv/bin/python ../scripts/coding_gen/generate.py [--write] [--check]

  (default)  verify all scenarios and print the integrity report; no files written
  --write    additionally write scenario.yaml for every scenario that PASSES both gates
  --check    alias for the default (verify only)

Run it via manage.py-style path bootstrapping handled here so code_exec imports.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND = os.path.join(REPO, "backend")

# Make `framework`, scenario banks, and Django (config.*) importable.
sys.path.insert(0, HERE)
sys.path.insert(0, BACKEND)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")

import django  # noqa: E402

django.setup()

from apps.labs.code_exec import grade_submission  # noqa: E402

from framework import verify_scenario, write_scenario  # noqa: E402
import scenarios_python  # noqa: E402
import scenarios_javascript  # noqa: E402


def main() -> int:
    write = "--write" in sys.argv

    all_scenarios = list(scenarios_python.S) + list(scenarios_javascript.S)

    # Guard against duplicate slugs (would clobber on disk / in seeder).
    slugs = [s.slug for s in all_scenarios]
    dupes = {s for s in slugs if slugs.count(s) > 1}
    if dupes:
        print(f"FATAL: duplicate slugs: {sorted(dupes)}")
        return 2

    passed = []
    failed = []
    for scn in all_scenarios:
        problems = verify_scenario(scn, grade_submission)
        if problems:
            failed.append((scn, problems))
        else:
            passed.append(scn)

    # Per-language / per-kind tally of the scenarios that passed integrity.
    by_lang: dict[str, dict[str, int]] = {}
    for scn in passed:
        by_lang.setdefault(scn.language, {}).setdefault(scn.kind, 0)
        by_lang[scn.language][scn.kind] += 1

    print("=" * 64)
    print("INTEGRITY VERIFICATION (fail-before / pass-after via real grader)")
    print("=" * 64)
    print(f"Total scenarios authored : {len(all_scenarios)}")
    print(f"Passed both gates        : {len(passed)}")
    print(f"Failed                   : {len(failed)}")
    print()
    for lang in sorted(by_lang):
        kinds = by_lang[lang]
        total = sum(kinds.values())
        kind_str = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
        print(f"  {lang:11s} {total:3d}  ({kind_str})")
    print()

    if failed:
        print("FAILED SCENARIOS (NOT written):")
        for scn, problems in failed:
            for p in problems:
                print(f"  - {p}")
        print()

    written = 0
    if write:
        for scn in passed:
            path = write_scenario(scn)
            written += 1
        print(f"Wrote {written} scenario.yaml files under scenarios/{{python,javascript}}/.")
    else:
        print("(verify-only; pass --write to emit YAML)")

    # Fail-closed exit code: nonzero if any scenario failed its integrity gates.
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
