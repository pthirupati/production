"""Integrity tests: clicking Check Solution must NEVER pass without a real fix.

These guard against the class of bug where a validation handler "recognises" a
command but returns success without confirming the lab state was actually
repaired (auto-completion). Every scenario family must fail-closed.
"""
from django.test import TestCase

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.validation import (
    CANONICAL_GPU_CHECK,
    CANONICAL_GRUB_CHECK,
    CANONICAL_TERRAFORM_CHECK,
    CANONICAL_WINDOWS_CHECK,
    is_trivial_validation_script,
    resolve_simulation_validation_script,
    validate_simulation_state,
)


class ValidationIntegrityTests(TestCase):
    """A fresh (unfixed) simulation state must never validate as passed."""

    def _broken_state(self, slug):
        """State after the scenario's broken preset has been applied (real path)."""
        shell = RHELShell(scenario_slug=slug)
        return shell.state

    def test_trivial_scripts_never_pass(self):
        for script in ("", "exit 0", "#!/bin/bash\n# todo\nexit 0", "true\n:", None):
            self.assertTrue(is_trivial_validation_script(script or ""))
            ok, _ = validate_simulation_state(RHELOSState("x"), script or "")
            self.assertFalse(ok, f"trivial script passed: {script!r}")

    def test_terraform_fails_until_fixed(self):
        state = RHELOSState("terraform-backend-lock-stuck")
        state.scenario_slug = "terraform-backend-lock-stuck"
        ok, msg = validate_simulation_state(state, CANONICAL_TERRAFORM_CHECK)
        self.assertFalse(ok, "terraform passed without a fix")
        state.terraform_fixed = True
        ok, msg = validate_simulation_state(state, CANONICAL_TERRAFORM_CHECK)
        self.assertTrue(ok, msg)

    def test_terraform_fails_even_with_unmatched_slug(self):
        """The old bug: a terraform check passed when the slug had no keyword."""
        state = RHELOSState("some-custom-iac-lab")
        state.scenario_slug = "some-custom-iac-lab"
        ok, _ = validate_simulation_state(state, CANONICAL_TERRAFORM_CHECK)
        self.assertFalse(ok, "terraform check auto-passed for unmatched slug")

    def test_windows_fails_until_fixed(self):
        state = RHELOSState("win-iis-not-starting")
        state.scenario_slug = "win-iis-not-starting"
        ok, _ = validate_simulation_state(state, CANONICAL_WINDOWS_CHECK)
        self.assertFalse(ok, "windows passed without a fix")
        state.windows_fixed = True
        ok, msg = validate_simulation_state(state, CANONICAL_WINDOWS_CHECK)
        self.assertTrue(ok, msg)

    def test_gpu_starts_broken_and_fails_until_fixed(self):
        """A GPU scenario's preset must mark the GPU unhealthy at start."""
        state = self._broken_state("gpu-fallen-off")
        self.assertFalse(state.gpu_healthy, "GPU preset did not break the GPU")
        ok, _ = validate_simulation_state(state, CANONICAL_GPU_CHECK)
        self.assertFalse(ok, "GPU check passed before the fix")
        state.gpu_healthy = True
        ok, msg = validate_simulation_state(state, CANONICAL_GPU_CHECK)
        self.assertTrue(ok, msg)

    def test_gpu_default_flag_is_fail_closed(self):
        """Even a bare state with no preset must not auto-pass the GPU check."""
        state = RHELOSState(hostname="bare")
        # Simulate a state that never had gpu_healthy initialised.
        delattr(state, "gpu_healthy")
        ok, _ = validate_simulation_state(state, CANONICAL_GPU_CHECK)
        self.assertFalse(ok, "GPU check auto-passed with uninitialised flag")

    def test_boot_fails_without_fix_or_boot_object(self):
        """grub check used to pass when the boot object was missing."""
        state = RHELOSState(hostname="rhel", scenario_slug="grub-rescue")
        state.scenario_slug = "grub-rescue"
        ok, _ = validate_simulation_state(state, CANONICAL_GRUB_CHECK, engine=None)
        self.assertFalse(ok, "boot check auto-passed with no boot object/fix")
        state.grub_fixed = True
        ok, msg = validate_simulation_state(state, CANONICAL_GRUB_CHECK, engine=None)
        self.assertTrue(ok, msg)

    def test_resolver_does_not_misroute_pipeline_to_python(self):
        """'ci-pipeline' contains 'pip' but must resolve to the DevOps check."""
        script = resolve_simulation_validation_script("devops-ci-pipeline-failure", "exit 0")
        self.assertIn("gitlab-runner", script)
        self.assertNotIn("py_compile", script)

    def test_resolver_routes_terraform_before_generic(self):
        script = resolve_simulation_validation_script("terraform-state-backend-corrupt", "exit 0")
        self.assertIn("terraform", script)
