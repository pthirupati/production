"""Guard against the academy E2E-fix / check.sh desync class of regression.

An academy service lab is graded by check.sh running `systemctl is-active <unit>`.
The preset plants that <unit> failed, and the universal E2E fix
(ACADEMY_SERVICE_FIX[slug]) is supposed to `systemctl start` the SAME <unit>.

If ACADEMY_SERVICE_FIX points at a different unit (e.g. a "topic" unit like
model-server while check.sh grades nginx), the fix starts the wrong service,
the graded unit stays inactive, and the lab becomes fail-closed-but-UNSOLVABLE
(verify_grader_fix classifies it BROKEN_FIX). That does NOT show up as a
fail-open grader, so it slips past scan_grader_integrity + sampled E2E — which
is exactly how ~1.3k academy labs shipped broken once. This fast, static test
(no simulation) fails the build the moment the two drift apart again.
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.academy_service_e2e_fixes import ACADEMY_SERVICE_FIX

SCENARIOS_DIR = Path(settings.BASE_DIR).parent / "scenarios"
_IS_ACTIVE = re.compile(r"systemctl is-active\s+(\S+)")


def _check_graded_units() -> dict[str, str]:
    """slug -> the unit its check.sh probes via `systemctl is-active`."""
    units: dict[str, str] = {}
    for check in SCENARIOS_DIR.glob("*/*/check.sh"):
        try:
            text = check.read_text()
        except OSError:
            continue
        m = _IS_ACTIVE.search(text)
        if m:
            units[check.parent.name] = m.group(1).strip()
    return units


class AcademyFixAlignmentTest(SimpleTestCase):
    def test_fix_unit_matches_check_graded_unit(self):
        graded = _check_graded_units()
        # The scenarios/ corpus lives in the repo (present in CI), but a deployed
        # backend container mounts it elsewhere — skip rather than false-fail when
        # it isn't on disk here; CI (repo checked out) still enforces the check.
        if len(graded) < 100:
            self.skipTest(f"academy check.sh corpus not present in this environment ({SCENARIOS_DIR})")
        mismatches = []
        for slug, fix_unit in ACADEMY_SERVICE_FIX.items():
            graded_unit = graded.get(slug)
            if graded_unit and graded_unit != fix_unit:
                mismatches.append(f"{slug}: E2E fix starts '{fix_unit}' but check.sh grades '{graded_unit}'")
        self.assertEqual(
            mismatches,
            [],
            f"{len(mismatches)} academy E2E-fix/check.sh unit mismatches would make those labs "
            f"fail-closed-but-unsolvable (BROKEN_FIX). First 10: " + "; ".join(mismatches[:10]),
        )
