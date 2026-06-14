"""Tests for simulation terminal input and boot sequence."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.boot_sequence import BootState
from apps.labs.provisioner.simulation.terminal_input import TerminalLineEditor


class TerminalInputTests(SimpleTestCase):
    def test_arrow_left_right(self):
        ed = TerminalLineEditor()
        for ch in "hello":
            ed.process(ch)
        ed.process("\x1b[D")  # left
        ed.process("\x1b[C")  # right
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
        events = ed.process("")
        # after backspace buffer is 'a'
        ed2 = TerminalLineEditor()
        ev = ed2.process("ab")
        ev2 = ed2.process("\x7f")
        self.assertEqual(ed2.buffer, "a")


class BootSequenceTests(SimpleTestCase):
    def test_reboot_shows_grub(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-boot-grub", simulation_type="rhel")
        boot._handle_boot("boot")
        boot._handle_boot("root")
        boot._handle_boot("pass")
        out = boot._handle_boot("reboot")
        self.assertIn("grub", out.lower())

    def test_initramfs_fix_with_dracut(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-initramfs-dracut", simulation_type="rhel")
        out = boot._handle_boot("dracut -f")
        self.assertIn("initramfs", out.lower())
        self.assertTrue(boot.boot.initramfs_fixed)

    def test_patching_dnf(self):
        boot = UnifiedSimulationEngine(scenario_slug="sim-rhel-patching", simulation_type="rhel")
        boot._handle_boot("boot")
        boot._handle_boot("root")
        boot._handle_boot("pass")
        out = boot._handle_boot("dnf update -y")
        self.assertIn("Complete", out)

    def test_mbr_issue_on_reboot(self):
        state = BootState()
        state.apply_issue("sim-rhel-mbr-corrupt")
        out = state.reboot()
        self.assertIn("Error 15", out)
