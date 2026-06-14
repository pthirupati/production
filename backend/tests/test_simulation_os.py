"""Tests for simulated RHEL OS shell, engines, and validation."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.base_sim import BaseRHELSimulator
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.scenario_presets import apply_scenario_preset
from apps.labs.provisioner.simulation.validation import (
    validate_simulation_state,
    resolve_simulation_validation_script,
    is_trivial_validation_script,
)
from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner


class RHELOSStateTests(SimpleTestCase):
    def test_base_users_and_services(self):
        state = RHELOSState()
        self.assertIn("root", state.users)
        self.assertEqual(state.services["sshd"].active, "active")

    def test_add_user_syncs_passwd(self):
        shell = RHELShell(scenario_slug="sim-rhel-broken-useradd")
        shell.run("sed -i 's/corrupt::99999:99999:bad:\\/bad:\\/bin\\/bash//' /etc/passwd")
        shell.run("useradd -m appuser")
        passwd = shell.state.read_file("/etc/passwd") or ""
        self.assertIn("appuser", passwd)


class RHELShellCommandTests(SimpleTestCase):
    def setUp(self):
        self.shell = RHELShell(scenario_slug="sim-rhel-broken-nginx")

    def test_nginx_config_invalid_initially(self):
        out = self.shell.run("nginx -t")
        self.assertIn("listn", out)
        self.assertIn("failed", out.lower())

    def test_fix_nginx_and_start(self):
        self.shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
        out = self.shell.run("nginx -t")
        self.assertIn("successful", out)
        self.shell.run("systemctl start nginx")
        self.assertEqual(self.shell.state.services["nginx"].active, "active")
        curl = self.shell.run("curl http://localhost")
        self.assertIn("Welcome to nginx", curl)

    def test_useradd_passwd_systemctl(self):
        shell = RHELShell()
        shell.run("useradd -m devops")
        self.assertIn("devops", shell.state.users)
        out = shell.run("passwd devops")
        self.assertIn("updated successfully", out)
        out = shell.run("systemctl status sshd")
        self.assertIn("active", out)

    def test_ps_and_kill(self):
        shell = RHELShell()
        before = len(shell.state.processes)
        pid_out = shell.run("pgrep sshd")
        if pid_out.strip():
            pid = int(pid_out.splitlines()[0])
            shell.run(f"kill {pid}")
            self.assertLess(len(shell.state.processes), before)

    def test_clone_for_companion_host(self):
        state = RHELOSState(hostname="primary")
        apply_scenario_preset("sim-rhel-broken-nginx", state)
        companion = state.clone_for_host("web1")
        self.assertEqual(companion.hostname, "web1")
        self.assertIn("/etc/nginx/sites-enabled/default", companion.vfs)


class ValidationTests(SimpleTestCase):
    NGINX_CHECK = """#!/bin/bash
nginx -t 2>/dev/null
pgrep -x nginx
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80)
exit 0
"""

    USERADD_CHECK = """#!/bin/bash
pwck
getent passwd appuser
exit 0
"""

    def test_trivial_script_always_fails(self):
        passed, msg = validate_simulation_state(RHELOSState(), "true\nexit 0")
        self.assertFalse(passed)
        self.assertIn("not configured", msg.lower())

    def test_nginx_validation_fails_then_passes(self):
        sim = BaseRHELSimulator(scenario_slug="sim-rhel-broken-nginx")
        passed, _ = validate_simulation_state(sim.state, self.NGINX_CHECK)
        self.assertFalse(passed)
        sim.shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
        sim.shell.run("systemctl start nginx")
        passed, msg = validate_simulation_state(sim.state, self.NGINX_CHECK)
        self.assertTrue(passed, msg)

    def test_useradd_validation(self):
        sim = BaseRHELSimulator(scenario_slug="sim-rhel-broken-useradd")
        passed, _ = validate_simulation_state(sim.state, self.USERADD_CHECK)
        self.assertFalse(passed)
        sim.shell.run("sed -i 's/corrupt::99999:99999:bad:\\/bad:\\/bin\\/bash//' /etc/passwd")
        sim.shell.run("useradd -m appuser")
        passed, msg = validate_simulation_state(sim.state, self.USERADD_CHECK)
        self.assertTrue(passed, msg)

    def test_stub_scripts_resolved_by_slug(self):
        self.assertIn("nginx -t", resolve_simulation_validation_script("sim-rhel-broken-nginx", "true\nexit 0"))
        self.assertIn("mysqladmin", resolve_simulation_validation_script("sim-mysql-wont-start", "true\nexit 0"))
        self.assertIn("kubectl", resolve_simulation_validation_script("pod-crashloop", "true\nexit 0"))
        self.assertFalse(is_trivial_validation_script(resolve_simulation_validation_script("gpu-fallen-off", "true")))

    def test_stub_scenarios_fail_without_fix(self):
        from apps.labs.provisioner.simulation_provisioner import SimulationProvisioner
        from unittest.mock import MagicMock

        prov = SimulationProvisioner()
        stubs = [
            ("sim-mysql-wont-start", "database"),
            ("pod-crashloop", "kubernetes"),
            ("sim-rhel-gpu-fallen-off", "gpu"),
            ("sim-rhel-ansible-ssh", "ansible"),
        ]
        for slug, sim_type in stubs:
            session = MagicMock()
            session.id = f"stub-{slug}"
            session.scenario.slug = slug
            session.scenario.simulation_type = sim_type
            session.scenario.validation_script = "true\nexit 0\n"
            session.scenario.requires_companion_hosts = False
            resource_id, _ = prov.provision(session)
            passed, _ = prov.run_validation(resource_id, session.scenario.validation_script, slug)
            self.assertFalse(passed, f"{slug} should not pass before fix")
            prov.terminate(resource_id, session_id=str(session.id))


class EngineTests(SimpleTestCase):
    def test_gpu_modprobe_recovery(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-rhel-gpu-fallen-off", simulation_type="gpu")
        out = sim.shell.run("nvidia-smi")
        self.assertIn("failed", out.lower())
        sim.shell.run("modprobe nvidia")
        out = sim.shell.run("nvidia-smi")
        self.assertIn("NVIDIA-SMI", out)

    def test_ansible_ssh_key_fix(self):
        sim = UnifiedSimulationEngine(scenario_slug="sim-rhel-ansible-ssh", simulation_type="ansible")
        out = sim.shell.run("ansible webservers -m ping")
        self.assertIn("UNREACHABLE", out)
        sim.shell.run("ssh-copy-id root@web2")
        out = sim.shell.run("ansible webservers -m ping")
        self.assertNotIn("UNREACHABLE", out)

    def test_boot_grub_to_shell(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-boot-grub", simulation_type="rhel")
        self.assertIsNotNone(boot.boot)
        out = boot._handle_boot("boot")
        self.assertIn("login", out.lower())
        boot._handle_boot("root")
        boot._handle_boot("password")
        out = boot._handle_boot("systemctl status sshd")
        self.assertIn("sshd", out)


class ProvisionerTests(SimpleTestCase):
    def test_run_validation_via_resource_lookup(self):
        from unittest.mock import MagicMock

        prov = SimulationProvisioner()
        session = MagicMock()
        session.id = "test-session-uuid"
        session.scenario.slug = "sim-rhel-broken-nginx"
        session.scenario.validation_script = "nginx -t\npgrep nginx\n"
        resource_id, _ = prov.provision(session)
        passed, _ = prov.run_validation(resource_id, session.scenario.validation_script)
        self.assertFalse(passed)
        entry = __import__(
            "apps.labs.provisioner.simulation.shell",
            fromlist=["get_sim_session"],
        ).get_sim_session("test-session-uuid")
        entry["state"]["engine"].shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
        entry["state"]["engine"].shell.run("systemctl start nginx")
        passed, msg = prov.run_validation(resource_id, session.scenario.validation_script)
        self.assertTrue(passed, msg)
        prov.terminate(resource_id, session_id="test-session-uuid")
