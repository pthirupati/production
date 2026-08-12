"""The two AI-vertical 'Learn Lab' on-ramps must actually teach something.

Audit L915 (A10): `academy-ai-ml-001-learn-dataset` and
`academy-gpu-001-learn-drivers` are the on-ramp *by name* but shipped as the
bulk-generated incident template — a self-contradicting description ("a
customer-facing workflow is degraded" next to "Nothing is on fire — focus on
observation"), objectives that only say "understand how X works", and hints that
name a single command. The ai-ml one was worse than the audit recorded: its
`tasks.validation`, `solution` and `guided_mode` all referenced **nginx** while
the graded unit (check.sh, and the seeded preset in
`academy_service_presets.ACADEMY_SERVICE_PRESETS`) is **model-server**.

Grading is NOT affected by these files: `seed_scenarios` reads
`validation_script` from check.sh, never from `scenario.yaml:tasks.validation`.
So this is a content contract, and check.sh stays byte-identical — deliberately,
because test_ai_vertical_checkers_fail_closed and test_gpu_ansible_fail_closed
pin those exact bodies, and rewriting a checker to match new prose is the
BROKEN_FIX class that once made ~1400 academy labs unsolvable.

What is pinned here: the on-ramps name the concepts a fresher needs, the
walkthrough uses only commands the simulator really implements, and no lab
instructs the learner to operate a unit that is not the one being graded.
"""

from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase

SCENARIOS_DIR = Path(settings.BASE_DIR).parent / "scenarios"

ONRAMPS = {
    "academy-ai-ml-001-learn-dataset": SCENARIOS_DIR
    / "ai-ml"
    / "academy-ai-ml-001-learn-dataset",
    "academy-gpu-001-learn-drivers": SCENARIOS_DIR
    / "gpu"
    / "academy-gpu-001-learn-drivers",
}

# The generated incident template. A Learn lab that still carries this sentence
# is framing observation practice as a customer-facing outage.
INCIDENT_TEMPLATE = "A customer-facing workflow is degraded and the on-call engineer"

# Concepts the audit says are missing platform-wide ("nothing explains what a
# token, embedding, GPU memory hierarchy, or batch *is*"). Each on-ramp must
# define at least this many of its own domain's terms in prose.
CONCEPTS = {
    "academy-ai-ml-001-learn-dataset": (
        "split",
        "leakage",
        "label",
        "schema",
    ),
    "academy-gpu-001-learn-drivers": (
        "kernel module",
        "userspace",
        "pcie",
        "hbm",
    ),
}

# The unit each lab is actually graded on, per check.sh and the seeded preset.
GRADED_SUBJECT = {
    "academy-ai-ml-001-learn-dataset": "model-server",
    "academy-gpu-001-learn-drivers": "nvidia",
}

# Units named by the bulk generator that are NOT part of these labs. Mentioning
# one sends the learner to operate a service the grader never looks at.
FOREIGN_UNITS = ("nginx", "jupyter", "httpd")


def _load(slug: str) -> dict:
    return yaml.safe_load((ONRAMPS[slug] / "scenario.yaml").read_text(encoding="utf-8"))


def _all_prose(data: dict) -> str:
    """Every learner-visible string in the scenario, lowercased."""
    chunks = [
        str(data.get("description", "")),
        str(data.get("initial_state", "")),
        " ".join(str(x) for x in data.get("objectives", []) or []),
        " ".join(str(x) for x in data.get("what_you_will_learn", []) or []),
        " ".join(str(h.get("content", "")) for h in data.get("hints", []) or []),
    ]
    for step in (data.get("guided_mode", {}) or {}).get("steps", []) or []:
        chunks.append(" ".join(str(v) for v in step.values()))
    return "\n".join(chunks).lower()


class AiOnrampLearnLabTests(SimpleTestCase):
    def setUp(self):
        if not SCENARIOS_DIR.exists():
            self.skipTest(f"scenarios corpus not present ({SCENARIOS_DIR})")

    def test_learn_labs_are_not_framed_as_incidents(self):
        """A Learn lab must not open with the degraded-customer incident template."""
        for slug in ONRAMPS:
            with self.subTest(slug=slug):
                self.assertNotIn(
                    INCIDENT_TEMPLATE,
                    _load(slug).get("description", ""),
                    f"{slug}: still the generated incident template — it contradicts "
                    f"its own 'Nothing is on fire' starting state",
                )

    def test_learn_labs_define_their_domain_concepts(self):
        """The on-ramp is where a fresher learns vocabulary, not just commands."""
        for slug, terms in CONCEPTS.items():
            with self.subTest(slug=slug):
                prose = _all_prose(_load(slug))
                missing = [t for t in terms if t not in prose]
                self.assertEqual(
                    missing,
                    [],
                    f"{slug}: on-ramp never explains {missing} — a fresher "
                    f"cannot learn the domain from it",
                )

    def test_no_lab_instructs_a_unit_it_is_not_graded_on(self):
        """The ai-ml on-ramp shipped nginx prose against a model-server grader."""
        for slug in ONRAMPS:
            with self.subTest(slug=slug):
                data = _load(slug)
                blob = _all_prose(data) + "\n" + yaml.safe_dump(
                    {
                        "tasks": data.get("tasks"),
                        "solution": data.get("solution"),
                    }
                ).lower()
                self.assertIn(
                    GRADED_SUBJECT[slug],
                    blob,
                    f"{slug}: never mentions the thing it is graded on",
                )
                strays = [u for u in FOREIGN_UNITS if u in blob]
                self.assertEqual(
                    strays,
                    [],
                    f"{slug}: references {strays}, which this lab does not grade — "
                    f"following the instructions would not pass the checker",
                )

    def test_task_validation_matches_the_real_checker(self):
        """`tasks.validation` is learner-facing; it must not drift from check.sh."""
        for slug in ONRAMPS:
            with self.subTest(slug=slug):
                data = _load(slug)
                check = (ONRAMPS[slug] / "check.sh").read_text(encoding="utf-8")
                probe = next(
                    ln.strip()
                    for ln in check.splitlines()
                    if ln.strip()
                    and not ln.startswith("#!")
                    and ln.strip() != "exit 0"
                )
                command = str(
                    (data["tasks"][0].get("validation") or {}).get("command", "")
                )
                self.assertEqual(
                    command,
                    probe,
                    f"{slug}: documented validation command does not match check.sh",
                )

    def test_walkthrough_uses_commands_the_simulator_implements(self):
        """Guided steps must be runnable, or the on-ramp teaches a dead end.

        Measured against the live engine rather than a hardcoded allowlist: an
        unrecognised command in this shell returns a `command not found` error.
        """
        from apps.labs.provisioner.simulation.scenario_presets import (
            apply_scenario_preset,
        )
        from apps.labs.provisioner.simulation.unified_sim import (
            UnifiedSimulationEngine,
        )

        for slug in ONRAMPS:
            with self.subTest(slug=slug):
                data = _load(slug)
                sim_type = data.get("simulation_type")
                engine = UnifiedSimulationEngine(
                    scenario_slug=slug, simulation_type=sim_type
                )
                engine.shell.state.scenario_slug = slug
                apply_scenario_preset(slug, engine.shell.state)
                for step in data["guided_mode"]["steps"]:
                    command = str(step.get("command", "")).strip()
                    if not command or command.startswith("#"):
                        continue
                    out = str(engine.shell.run(command))
                    self.assertNotIn(
                        "command not found",
                        out.lower(),
                        f"{slug}: guided step {step.get('step')} runs "
                        f"`{command}`, which this simulator does not implement",
                    )
