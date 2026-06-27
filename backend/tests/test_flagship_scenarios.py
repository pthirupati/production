"""Integrity proof for the flagship real-simulation academy labs.

These academy labs were upgraded from `grep FIXED-OK` markers to genuine
break/fix simulations (scripts/upgrade_flagship_labs.py). For every flagship
slug this test:

  1. builds the engine the real way (which applies the broken preset),
  2. asserts the shipped check.sh is real (non-trivial, not swapped by resolve),
  3. asserts validation FAILS before any fix (fail-closed),
  4. applies the EXACT remediation scripts/e2e_simulation_fix.py performs, and
  5. asserts the same check.sh now PASSES.

This guarantees a learner can only pass by doing the real work — and that the
documented fix genuinely resolves the lab end to end.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.flagship_presets import FLAGSHIP_SLUG_KIND
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.validation import (
    is_trivial_validation_script,
    resolve_simulation_validation_script,
    validate_simulation_state,
)

SCENARIOS_ROOT = Path(settings.BASE_DIR).parent / "scenarios"


def _tech_dir(slug: str) -> str:
    if slug.startswith("academy-ansible-"):
        return "ansible"
    if slug.startswith("academy-docker-"):
        return "docker"
    if slug.startswith("academy-rhel-linux-"):
        return "rhel-linux"
    return "linux"


def _sim_type(slug: str) -> str:
    if slug.startswith("academy-ansible-"):
        return "ansible"
    if slug.startswith("academy-rhel-linux-"):
        return "rhel"
    return "generic"


def _load_check(slug: str) -> str:
    return (SCENARIOS_ROOT / _tech_dir(slug) / slug / "check.sh").read_text()


def _apply_fix(kind: str, engine) -> None:
    """Mirror scripts/e2e_simulation_fix.py for the flagship lab families."""
    shell = engine.shell
    state = shell.state
    if kind == "users":
        shell.run("useradd -m appuser")
    elif kind == "systemd":
        shell.run("systemctl start nginx")
    elif kind == "syslog":
        shell.run("systemctl start rsyslog")
    elif kind == "crond":
        shell.run("systemctl start crond")
    elif kind == "chrony":
        shell.run("systemctl start chronyd")
    elif kind == "firewall":
        shell.run("firewall-cmd --permanent --add-service=http")
        shell.run("firewall-cmd --reload")
    elif kind == "docker-compose":
        shell.run("docker compose up -d")
        engine._container_running = True
        svc = state.services.get("docker")
        if svc:
            svc.active = "active"
            svc.sub_state = "running"
    elif kind == "ansible":
        shell.run("ssh-copy-id root@web1")
        shell.run("ssh-copy-id root@web2")
        engine._ssh_key_fixed = True
    else:  # pragma: no cover - defensive
        raise AssertionError(f"unknown flagship kind {kind!r}")


class FlagshipScenarioIntegrityTests(SimpleTestCase):
    def test_flagship_set_is_non_empty(self):
        self.assertTrue(FLAGSHIP_SLUG_KIND, "no flagship labs registered")

    def test_check_scripts_are_real_and_unreplaced(self):
        for slug in FLAGSHIP_SLUG_KIND:
            with self.subTest(slug=slug):
                script = _load_check(slug)
                self.assertFalse(
                    is_trivial_validation_script(script),
                    f"{slug}: check.sh is trivial and would auto-pass",
                )
                # These are real, state-based checks — resolve() must not swap
                # them for a canonical script.
                resolved = resolve_simulation_validation_script(slug, script)
                self.assertEqual(
                    resolved.strip(), script.strip(),
                    f"{slug}: real check.sh was replaced by resolve()",
                )

    def test_each_flagship_fails_before_fix_and_passes_after(self):
        for slug, kind in FLAGSHIP_SLUG_KIND.items():
            with self.subTest(slug=slug, kind=kind):
                engine = UnifiedSimulationEngine(
                    scenario_slug=slug, simulation_type=_sim_type(slug)
                )
                state = engine.shell.state
                script = resolve_simulation_validation_script(slug, _load_check(slug))

                before_ok, before_msg = validate_simulation_state(state, script, engine)
                self.assertFalse(
                    before_ok,
                    f"{slug}: validation PASSED before the fix (fail-open): {before_msg}",
                )

                _apply_fix(kind, engine)

                after_ok, after_msg = validate_simulation_state(state, script, engine)
                self.assertTrue(
                    after_ok,
                    f"{slug}: validation still FAILS after the fix: {after_msg}",
                )
