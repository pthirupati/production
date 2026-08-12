"""R9 — unmodified starter files must not pass the grader (audit §Y2f / R9).

Static tautology detection (R8 / scan_grader_integrity) catches the cheap cases.
This test grades the shipped stub for every *active* host-runnable coding lab so
a clever fail-open assertion that looks real still fails CI.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from django.test import SimpleTestCase

from apps.labs.code_exec import (
    SUPPORTED_LANGUAGES,
    compose_user_code_from_files,
    grade_submission,
)

ROOT = Path(__file__).resolve().parents[2] / "scenarios"


def _iter_active_coding_labs():
    if not ROOT.is_dir():
        return
    for tech_dir in sorted(ROOT.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        for sd in sorted(tech_dir.iterdir()):
            yml = sd / "scenario.yaml"
            if not sd.is_dir() or not yml.is_file():
                continue
            try:
                data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            if data.get("is_active", True) is False:
                continue
            spec = data.get("coding_spec") or {}
            if not data.get("coding_mode") and not spec:
                continue
            if (spec.get("kind") or "").strip().lower() == "prompt":
                continue
            lang = (spec.get("language") or "python").strip().lower()
            if lang not in SUPPORTED_LANGUAGES:
                continue
            visible = list(spec.get("visible_tests") or [])
            hidden = list(spec.get("hidden_tests") or [])
            if not visible and not hidden:
                continue
            files = {
                (f.get("path") or f.get("name") or ""): (f.get("content") or "")
                for f in (spec.get("files") or [])
                if isinstance(f, dict)
            }
            if not files:
                continue
            entry = (spec.get("entrypoint") or next(iter(files))).strip()
            slug = data.get("slug") or sd.name
            tests = [{**t, "hidden": False} for t in visible if isinstance(t, dict)]
            tests += [{**t, "hidden": True} for t in hidden if isinstance(t, dict)]
            yield slug, lang, files, entry, tests


class CodingStubMustFailTests(SimpleTestCase):
    """Catalog-wide R9: the untouched stub must fail for every active coding lab."""

    def test_active_coding_stubs_do_not_pass(self):
        failures: list[str] = []
        checked = 0
        for slug, lang, files, entry, tests in _iter_active_coding_labs():
            code = compose_user_code_from_files(files, entry)
            result = grade_submission(lang, code, tests, timeout=4)
            checked += 1
            if result.all_passed:
                failures.append(slug)

        self.assertGreater(checked, 50, "R9 found too few runnable coding labs — iterator broken?")
        self.assertEqual(
            failures,
            [],
            f"R9 fail-OPEN: unmodified stub passes for {len(failures)} lab(s): "
            f"{failures[:25]}{'…' if len(failures) > 25 else ''}",
        )
