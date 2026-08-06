"""The AI verticals' `exit 0` checkers must still grade fail-closed.

The 2026-08 audit (L197/L198) read `^exit 0` in 639 of the AI-vertical check.sh
files as "grading is neutralized" and proposed rewriting all of them. That
premise is wrong for THIS platform: simulation labs are not graded by executing
check.sh in a shell. `validate_simulation_state` parses the script line-by-line
and applies fail-closed semantics per probe, and `is_trivial_validation_script`
explicitly discards bare `exit 0` lines — so the trailing `exit 0` is inert. A
measured sweep of all 639 files found 0 fail-open.

Deleting those lines would touch 639 files for no grading change while risking
the BROKEN_FIX class of regression that once made ~1400 academy labs unsolvable
(see incident: academy BROKEN_FIX). This test pins the property that actually
matters — broken state must FAIL — so the neutralization claim cannot silently
become true later.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.scenario_presets import apply_scenario_preset
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.validation import (
    is_trivial_validation_script,
    validate_simulation_state,
)

SCENARIOS_DIR = Path(settings.BASE_DIR).parent / "scenarios"

# One representative per grading idiom found across the 639 `exit 0` checkers:
# marker .conf grep, two service probes, and the bare nvidia-smi GPU probe.
# Each is the exact shipped check.sh body, trailing `exit 0` included.
REPRESENTATIVES = (
    (
        "academy-ai-infra-034-troubleshoot-nvidia-smi-4",
        "#!/usr/bin/env bash\ngrep -q FIXED-OK "
        "/opt/fixitlab/academy/academy-ai-infra-034-troubleshoot-nvidia-smi-4.conf\nexit 0\n",
    ),
    (
        "academy-prompt-engineering-041-learn-instructions-5",
        "#!/usr/bin/env bash\nsystemctl is-active model-server\nexit 0\n",
    ),
    (
        "academy-data-science-056-security-statistics-6",
        "#!/usr/bin/env bash\nsystemctl is-active jupyter\nexit 0\n",
    ),
    ("academy-gpu-001-learn-drivers", "#!/usr/bin/env bash\nnvidia-smi\nexit 0\n"),
)


class AiVerticalCheckerFailClosedTests(SimpleTestCase):
    def test_trailing_exit_zero_does_not_make_script_trivial(self):
        """A real probe + `exit 0` must keep its probe, not be discarded wholesale."""
        for slug, script in REPRESENTATIVES:
            with self.subTest(slug=slug):
                self.assertFalse(
                    is_trivial_validation_script(script),
                    f"{slug}: checker treated as trivial — it would stop grading",
                )

    def test_broken_state_fails_despite_exit_zero(self):
        """The seeded (unfixed) lab must NOT pass. This is the audit's actual claim."""
        for slug, script in REPRESENTATIVES:
            with self.subTest(slug=slug):
                engine = UnifiedSimulationEngine(scenario_slug=slug)
                state = engine.shell.state
                state.scenario_slug = slug
                apply_scenario_preset(slug, state)
                passed, msg = validate_simulation_state(state, script, engine)
                self.assertFalse(
                    passed,
                    f"{slug}: FAIL-OPEN — broken lab passed with `exit 0` present ({msg})",
                )

    def test_removing_exit_zero_would_not_change_grading(self):
        """Pins WHY the 639-file rewrite is churn: the line is inert either way."""
        for slug, script in REPRESENTATIVES:
            with self.subTest(slug=slug):
                without = "\n".join(
                    ln for ln in script.splitlines() if ln.strip() != "exit 0"
                ) + "\n"
                results = []
                for variant in (script, without):
                    engine = UnifiedSimulationEngine(scenario_slug=slug)
                    state = engine.shell.state
                    state.scenario_slug = slug
                    apply_scenario_preset(slug, state)
                    results.append(validate_simulation_state(state, variant, engine)[0])
                self.assertEqual(
                    results[0],
                    results[1],
                    f"{slug}: grading differs with/without `exit 0` — the audit's "
                    f"rewrite premise would then be real and this test must be revisited",
                )

    def test_shipped_checkers_on_disk_still_carry_a_real_probe(self):
        """Guard the corpus itself: an `exit 0`-only checker WOULD be fail-open."""
        if not SCENARIOS_DIR.exists():
            self.skipTest(f"scenarios corpus not present ({SCENARIOS_DIR})")
        empty: list[str] = []
        for vertical in ("gpu", "ai-ml", "ai-infra", "data-science", "prompt-engineering"):
            for check in sorted((SCENARIOS_DIR / vertical).glob("*/check.sh")):
                if is_trivial_validation_script(check.read_text()):
                    empty.append(check.parent.name)
        # Known, intentional exception: agent/dashboard labs whose grading runs
        # in-process (aiml_engine.validate_aiml_lab /
        # datascience_engine.validate_datascience_lab, dispatched from
        # simulation_provisioner) rather than through check.sh. Their check.sh is a
        # documented stub. Anything else with no probe is a real fail-open hole.
        unexpected = [
            slug
            for slug in empty
            if "agent" not in slug and not slug.startswith("ds-dashboard-")
        ]
        self.assertEqual(
            unexpected,
            [],
            f"{len(unexpected)} AI-vertical checkers have no substantive probe at all "
            f"and would grade fail-open: {unexpected[:10]}",
        )
