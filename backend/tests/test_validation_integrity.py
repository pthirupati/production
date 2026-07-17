"""Integrity tests: clicking Check Solution must NEVER pass without a real fix.

These guard against the class of bug where a validation handler "recognises" a
command but returns success without confirming the lab state was actually
repaired (auto-completion). Every scenario family must fail-closed.
"""
from django.test import TestCase

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.validation import (
    CANONICAL_ANSIBLE_CHECK,
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

    def test_ansible_fails_without_engine(self):
        """Ansible ping must not auto-pass when the lab engine is missing."""
        state = RHELOSState("academy-ansible-001-learn-inventory")
        state.scenario_slug = "academy-ansible-001-learn-inventory"
        ok, msg = validate_simulation_state(state, CANONICAL_ANSIBLE_CHECK, engine=None)
        self.assertFalse(ok, f"ansible auto-passed without engine: {msg}")

    def test_ansible_fails_until_ssh_keys_distributed(self):
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
        engine = UnifiedSimulationEngine(
            scenario_slug="academy-ansible-001-learn-inventory",
            simulation_type="ansible",
        )
        ok, _ = validate_simulation_state(engine.state, CANONICAL_ANSIBLE_CHECK, engine=engine)
        self.assertFalse(ok, "ansible passed before ssh-copy-id")
        engine._ssh_key_fixed = True
        ok, msg = validate_simulation_state(engine.state, CANONICAL_ANSIBLE_CHECK, engine=engine)
        self.assertTrue(ok, msg)

    def test_gpu_identity_facet(self):
        from apps.labs.provisioner.simulation import server_identity as si
        sid = "gpu-identity-test"
        si.drop_session(sid)
        self.addCleanup(si.drop_session, sid)
        node = si.seed_gpu_node(sid, healthy=False)
        self.assertEqual(node["gpu"]["health"], "failed")
        si.set_gpu(sid, node["id"], driver_loaded=True, health="healthy", source="test")
        again = si.get_server(sid, node["id"])
        self.assertEqual(again["gpu"]["health"], "healthy")
        self.assertTrue(again["gpu"]["driver_loaded"])

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

    def test_fix_flags_survive_serialization_roundtrip(self):
        """Cross-worker (Redis) validation must see fix-flags set by a fix.

        ldconfig/terraform/windows fixes set plain attributes; if those aren't
        serialized they're lost when another worker reloads the engine, and the
        scenario validates as unfixed (the recurring ldconfig CI failure).
        """
        import json
        from apps.labs.provisioner.simulation import sim_persistence as sp
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine

        engine = UnifiedSimulationEngine("ldconfig-missing-library", simulation_type="generic")
        st = engine.shell.state
        st._mkdir("/etc/ld.so.conf.d")
        st._write_file("/etc/ld.so.conf.d/fixitlab.conf", "/usr/local/lib\n")
        st.ldconfig_updated = True
        st.myapp_working = True
        st.terraform_fixed = True
        st.windows_fixed = True

        restored = sp.restore_engine(json.loads(json.dumps(sp.snapshot_engine(engine))))
        rst = restored.shell.state
        self.assertTrue(rst.ldconfig_updated)
        self.assertTrue(rst.myapp_working)
        self.assertTrue(rst.terraform_fixed)
        self.assertTrue(rst.windows_fixed)


class MonitoringScenarioIntegrityTests(TestCase):
    """Grafana + Prometheus marker scenarios must fail-closed until the config
    is rewritten with the FIXED-OK sentinel (and never auto-pass)."""

    SAMPLES = [
        "grafana-datasource-misconfigured-no-data",
        "grafana-alert-rule-for-too-short",
        "grafana-contact-point-missing",
        "grafana-notification-policy-misrouted",
        "prometheus-target-down-scrape-refused",
        "prometheus-alertmanager-route-misrouted",
        "prometheus-high-cardinality-label",
        "prometheus-recording-rule-parse-error",
        "prometheus-remote-write-unreachable",
    ]

    def test_monitoring_presets_break_state_without_marker(self):
        from apps.labs.provisioner.simulation.scenario_presets import apply_scenario_preset
        for slug in self.SAMPLES:
            state = RHELOSState(scenario_slug=slug)
            state.scenario_slug = slug
            apply_scenario_preset(slug, state)
            # The preset must have written *some* broken config that does NOT
            # already contain the success marker (else Check Solution fail-opens).
            wrote_marker_free = False
            for path, node in state.vfs.items():
                if isinstance(node, dict) and node.get("type") == "file":
                    content = node.get("content", "")
                    if "broken configuration" in content:
                        self.assertNotIn("FIXED-OK", content,
                                         f"{slug}: broken preset must not contain FIXED-OK")
                        wrote_marker_free = True
            self.assertTrue(wrote_marker_free, f"{slug}: preset wrote no broken config file")

    def test_monitoring_fail_closed_then_pass_after_fix(self):
        """Read each scenario's real check.sh, confirm it fails before the fix
        and passes once the config carries FIXED-OK."""
        import os
        from apps.labs.provisioner.simulation.scenario_presets import apply_scenario_preset

        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        scen_root = os.path.join(repo_root, "scenarios")
        for slug in self.SAMPLES:
            tech = "grafana" if slug.startswith("grafana") else "prometheus"
            check_path = os.path.join(scen_root, tech, slug, "check.sh")
            if not os.path.isfile(check_path):
                self.skipTest(f"scenario file missing: {check_path}")
            with open(check_path) as fh:
                script = resolve_simulation_validation_script(slug, fh.read())

            state = RHELOSState(scenario_slug=slug)
            state.scenario_slug = slug
            apply_scenario_preset(slug, state)

            ok_before, _ = validate_simulation_state(state, script)
            self.assertFalse(ok_before, f"{slug}: passed BEFORE the fix (fail-open)")

            # The target file is the one the check.sh greps for FIXED-OK.
            target = None
            for line in script.splitlines():
                s = line.strip()
                if "grep" in s and "FIXED-OK" in s and not s.startswith("#"):
                    target = next((p for p in s.split() if p.startswith("/")), None)
                    break
            self.assertIsNotNone(target, f"{slug}: could not find FIXED-OK target in check.sh")
            existing = state.read_file(target) or ""
            state.write_file(target, existing + "\n# FIXED-OK: corrected per the documented remediation\n")

            ok_after, msg = validate_simulation_state(state, script)
            self.assertTrue(ok_after, f"{slug}: failed AFTER the fix: {msg}")
