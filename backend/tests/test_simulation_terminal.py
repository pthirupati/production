"""Tests for simulation terminal input and boot sequence."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.boot_sequence import BootState, NEW_KERNEL, OLD_KERNEL
from apps.labs.provisioner.simulation.terminal_input import TerminalLineEditor
from apps.labs.provisioner.simulation.validation import validate_simulation_state, resolve_simulation_validation_script


class TerminalInputTests(SimpleTestCase):
    def test_arrow_left_right(self):
        ed = TerminalLineEditor()
        for ch in "hello":
            ed.process(ch)
        ed.process("\x1b[D")
        ed.process("\x1b[C")
        events = ed.process("\r")
        self.assertEqual(events[0], ("submit", "hello"))

    def test_history_up_down(self):
        ed = TerminalLineEditor()
        ed.process("first command\r")
        ed.process("\x1b[A")
        self.assertEqual(ed.buffer, "first command")

    def test_backspace(self):
        ed = TerminalLineEditor()
        ed.process("ab\x7f\r")
        ed2 = TerminalLineEditor()
        ed2.process("ab")
        ed2.process("\x7f")
        self.assertEqual(ed2.buffer, "a")


class BootSequenceTests(SimpleTestCase):
    def test_reboot_shows_grub(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-boot-grub", simulation_type="rhel")
        boot._handle_boot("boot")
        boot._handle_boot("root")
        boot._handle_boot("redhat")
        out = boot._handle_boot("reboot")
        self.assertIn("grub", out.lower())

    def test_patching_starts_in_shell_not_grub(self):
        engine = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        self.assertTrue(engine.boot.start_at_shell)
        self.assertTrue(engine.boot.logged_in)
        self.assertEqual(engine.boot.phase, "shell")

    def test_patching_full_workflow(self):
        engine = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        shell = engine.shell
        shell.state.ops_backup_taken = True
        shell.state.ops_db_stopped = True
        shell.state.ops_app_stopped = True
        out = shell.run("bash /opt/fixitlab/precheck.sh")
        self.assertIn("Precheck", out)
        self.assertTrue(shell.state.precheck_ran)
        shell.run("dnf update -y")
        self.assertTrue(shell.state.patching_done)
        reboot_out = engine._reboot_from_shell()
        self.assertTrue(shell.state.rebooted_after_patch)
        shell.run("mount -a")
        shell.state.ops_services_restarted = True
        engine._handle_boot("")
        engine._handle_boot("root")
        engine._handle_boot("redhat")
        out = shell.run("bash /opt/fixitlab/postcheck.sh")
        self.assertIn("PASSED", out)
        script = resolve_simulation_validation_script("sim-rhel-patching", "true")
        ok, msg = validate_simulation_state(shell.state, script, engine=engine)
        self.assertTrue(ok, msg)

    def test_initramfs_fix_with_dracut(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-initramfs-dracut", simulation_type="rhel")
        out = boot._handle_boot("dracut -f")
        self.assertIn("initramfs", out.lower())
        self.assertTrue(boot.boot.initramfs_fixed)

    def test_patching_dnf(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        out = boot._handle_shell("dnf update -y")
        self.assertIn("Complete", out)

    def test_mbr_issue_on_reboot(self):
        state = BootState()
        state.apply_issue("sim-rhel-mbr-corrupt")
        out = state.reboot()
        self.assertIn("Error 15", out)

    def test_grub_shows_kernel_versions(self):
        state = BootState()
        state.kernel = OLD_KERNEL
        self.assertIn(OLD_KERNEL, state.grub_banner())

    def test_grub_edit_then_boot(self):
        boot = BootState()
        boot.handle_grub("e")
        self.assertEqual(boot.phase, "grub_edit")
        boot.handle_grub_edit("linux /vmlinuz-custom ro single")
        out = boot.handle_grub_edit("boot")
        self.assertIn("login", out.lower())

    def test_bash_postcheck_requires_reboot(self):
        from apps.labs.provisioner.simulation.rhel_shell import RHELShell
        shell = RHELShell(scenario_slug="sim-rhel-patching")
        shell.run("bash /opt/fixitlab/precheck.sh")
        shell.run("dnf update -y")
        out = shell.run("bash /opt/fixitlab/postcheck.sh")
        self.assertIn("reboot required", out)

    def test_reboot_after_patch_shows_new_kernel(self):
        state = BootState()
        state.apply_issue("sim-rhel-patching")
        state.patching_done = True
        out = state.reboot()
        self.assertIn(NEW_KERNEL, out)

    def test_ip_addr_add(self):
        from apps.labs.provisioner.simulation.rhel_shell import RHELShell
        shell = RHELShell()
        shell.run("ip addr add 10.0.0.99/24 dev eth0")
        out = shell.run("ip addr")
        self.assertIn("10.0.0.99", out)

    def test_lvm_df_reflects_extend(self):
        from apps.labs.provisioner.simulation.rhel_shell import RHELShell
        shell = RHELShell(scenario_slug="sim-rhel-lvm-extend")
        shell.run("vgextend rhel /dev/sdb")
        shell.run("lvextend -L +5G /dev/rhel/root")
        out = shell.run("df -h")
        self.assertIn("rhel-root", out)

    def test_sim_snapshot_roundtrip(self):
        from apps.labs.provisioner.simulation.sim_persistence import snapshot_engine, restore_engine
        from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
        engine = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        engine.shell.run("dnf update -y")
        snap = snapshot_engine(engine)
        restored = restore_engine(snap)
        self.assertIsNotNone(restored)
        self.assertTrue(restored.shell.state.patching_done)
