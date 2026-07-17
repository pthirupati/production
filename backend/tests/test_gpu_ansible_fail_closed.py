"""Regression: GPU and Ansible academy scenarios must be fail-closed.

Locks in the fix from commit dd164afa4 ("Harden Ansible/GPU grading and seed
virtualized GPU into ServerIdentity"): a fresh session must FAIL validation
before the real fix is applied, and PASS only once the learner performs the
actual remediation (`modprobe nvidia` / `ssh-copy-id` + a successful
`ansible-playbook` run) — never an auto-pass on an uninitialized flag.
"""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.validation import validate_simulation_state

GPU_SLUGS = [
    "academy-gpu-001-learn-drivers",
    "academy-gpu-002-build-cuda",
    "academy-gpu-003-operate-nvidia-smi",
    "academy-gpu-004-troubleshoot-mig",
    "academy-gpu-005-production-dcgm",
]

ANSIBLE_SLUGS = [
    "academy-ansible-001-learn-inventory",
    "academy-ansible-002-build-playbooks",
    "academy-ansible-004-troubleshoot-handlers",
    "academy-ansible-009-backup-awx",
]

GPU_CHECK = "nvidia-smi\nexit 0\n"
ANSIBLE_CHECK = "ansible webservers -m ping\nexit 0\n"


class GpuAcademyFailClosedTests(SimpleTestCase):
    def test_fails_before_driver_load_and_passes_after(self):
        for slug in GPU_SLUGS:
            with self.subTest(slug=slug):
                sim = UnifiedSimulationEngine(scenario_slug=slug, simulation_type="gpu")
                passed, msg = validate_simulation_state(sim.state, GPU_CHECK, engine=sim)
                self.assertFalse(passed, f"{slug} should fail before modprobe nvidia: {msg}")
                sim.shell.run("modprobe nvidia")
                passed, msg = validate_simulation_state(sim.state, GPU_CHECK, engine=sim)
                self.assertTrue(passed, f"{slug} should pass after modprobe nvidia: {msg}")

    def test_engine_none_fails_closed_not_open(self):
        sim = UnifiedSimulationEngine(scenario_slug=GPU_SLUGS[0], simulation_type="gpu")
        passed, _ = validate_simulation_state(sim.state, GPU_CHECK, engine=None)
        self.assertFalse(passed)


class AnsibleAcademyFailClosedTests(SimpleTestCase):
    def test_fails_before_ssh_key_and_passes_after(self):
        for slug in ANSIBLE_SLUGS:
            with self.subTest(slug=slug):
                sim = UnifiedSimulationEngine(scenario_slug=slug, simulation_type="ansible")
                passed, msg = validate_simulation_state(sim.state, ANSIBLE_CHECK, engine=sim)
                self.assertFalse(passed, f"{slug} should fail before ssh-copy-id: {msg}")
                sim.shell.run("ssh-copy-id root@web2")
                sim.shell.run("ansible webservers -m ping")
                passed, msg = validate_simulation_state(sim.state, ANSIBLE_CHECK, engine=sim)
                self.assertTrue(passed, f"{slug} should pass after ssh key fix: {msg}")

    def test_engine_none_fails_closed_not_open(self):
        sim = UnifiedSimulationEngine(scenario_slug=ANSIBLE_SLUGS[0], simulation_type="ansible")
        passed, msg = validate_simulation_state(sim.state, ANSIBLE_CHECK, engine=None)
        self.assertFalse(passed)
        self.assertIn("engine unavailable", msg)
