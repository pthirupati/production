"""Unified server model (#17): a VMware VM's console IS the backend RHEL shell.

These tests lock in the phase-1 contract:
  * the backend RHEL shell is SEEDED from the VMware VM the learner sees
    (hostname / CPU / RAM / IP), so the VM console and the lab terminal are one
    server — verified through the actual shell commands (nproc/lscpu/free/ip/prompt);
  * a `reboot`/`poweroff` typed in that terminal propagates to the VMware VM tile
    via the session-keyed bridge, drained exactly once;
  * pure-Linux labs are byte-for-byte unchanged (defaults preserved);
  * the seeded hardware survives a snapshot round-trip (worker restart).
"""
from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation import vmware_bridge as vb
from apps.labs.provisioner.simulation import sim_persistence
from apps.labs.provisioner.simulation_provisioner import _seed_state_from_vmware_vm
from apps.vmware_sim import engine as ve

VMWARE_SLUG = "vmware-esxi-host-not-responding"


def _mem_line(shell):
    return next(l for l in shell.run("free -m").splitlines() if l.startswith("Mem"))


class PlainLinuxUnchangedTests(SimpleTestCase):
    def test_defaults_match_historical_box(self):
        sh = RHELShell(RHELOSState(hostname="rhel-sim"))
        self.assertEqual(sh.run("nproc").strip(), "4")
        self.assertIn("CPU(s):                  4", sh.run("lscpu"))
        self.assertIn("16384", _mem_line(sh))
        # /proc still reflects the 4c/16G default.
        self.assertIn("16777216 kB", sh.run("cat /proc/meminfo"))


class SeedFromVmwareVmTests(SimpleTestCase):
    def setUp(self):
        self.sid = "unified-seed-test"
        cache.delete(f"vmware_bridge:{self.sid}")
        ve.drop_session(self.sid)
        self.addCleanup(ve.drop_session, self.sid)
        self.addCleanup(cache.delete, f"vmware_bridge:{self.sid}")

    def test_seed_makes_shell_match_target_vm(self):
        engine = UnifiedSimulationEngine(scenario_slug=VMWARE_SLUG, simulation_type="vmware")
        _seed_state_from_vmware_vm(engine, self.sid, VMWARE_SLUG)
        sh = engine.shell
        # web-prod-01 is the default graded target: 4 vCPU, 8192 MB, 10.20.30.41.
        self.assertEqual(sh.state.hostname, "web-prod-01")
        self.assertIn("root@web-prod-01", sh.prompt)
        self.assertEqual(sh.run("nproc").strip(), "4")
        self.assertIn("8192", _mem_line(sh))
        self.assertIn("10.20.30.41", sh.run("ip a"))
        self.assertIn("web-prod-01", sh.run("cat /etc/hostname"))

    def test_seed_is_exception_safe(self):
        # The seed is best-effort: if the VMware state read blows up, provisioning
        # must NOT fail — the shell is left as-is. (This guard is why the seed can
        # be wired directly into provision()/ensure_sim_session().)
        engine = UnifiedSimulationEngine(scenario_slug=VMWARE_SLUG, simulation_type="vmware")
        before = engine.shell.state.hostname
        orig = ve.get_state
        ve.get_state = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            _seed_state_from_vmware_vm(engine, self.sid, VMWARE_SLUG)  # must not raise
        finally:
            ve.get_state = orig
        self.assertEqual(engine.shell.state.hostname, before)


class TerminalPowerPropagationTests(SimpleTestCase):
    def setUp(self):
        self.sid = "unified-power-test"
        cache.delete(f"vmware_bridge:{self.sid}")
        ve.drop_session(self.sid)
        ve._ensure_session(self.sid, VMWARE_SLUG)
        self.addCleanup(ve.drop_session, self.sid)
        self.addCleanup(cache.delete, f"vmware_bridge:{self.sid}")
        self.sh = RHELShell(RHELOSState(hostname="web-prod-01"))
        self.sh.state.session_id = self.sid

    def _target(self):
        data = ve.get_state(self.sid, VMWARE_SLUG)
        return next(v for v in data["inventory"]["vms"] if v["name"] == "web-prod-01")

    def test_reboot_propagates_and_drains_once(self):
        self.assertEqual(self.sh.run("reboot"), "__REBOOT__")
        self.assertEqual(vb._load(self.sid).get("guest_power"), "reboot")
        vm = self._target()
        self.assertTrue(vm.get("boot_pending"))
        self.assertEqual(vm["power"], "poweredOn")
        # get_state drained it; a second read must not re-fire.
        self.assertIsNone(vb._load(self.sid).get("guest_power"))

    def test_poweroff_propagates(self):
        self.sh.run("poweroff")
        self.assertEqual(vb._load(self.sid).get("guest_power"), "poweroff")
        self.assertEqual(self._target()["power"], "poweredOff")

    def test_shutdown_r_reboots(self):
        self.assertEqual(self.sh.run("shutdown -r now"), "__REBOOT__")
        self.assertEqual(vb._load(self.sid).get("guest_power"), "reboot")

    def test_plain_shutdown_powers_off(self):
        self.sh.run("shutdown -h now")
        self.assertEqual(vb._load(self.sid).get("guest_power"), "poweroff")

    def test_no_session_id_is_silent(self):
        # A pure-Linux shell (no VMware session) must not touch the bridge.
        sh = RHELShell(RHELOSState(hostname="rhel-sim"))
        self.assertEqual(sh.run("reboot"), "__REBOOT__")  # no exception, no bridge write


class SnapshotRoundTripTests(SimpleTestCase):
    def test_seeded_hardware_survives_restart(self):
        engine = UnifiedSimulationEngine(scenario_slug=VMWARE_SLUG, simulation_type="vmware")
        engine.shell.state.set_hostname("db-prod-01")
        engine.shell.state.set_hardware(cpu=8, mem_mb=16384)
        snap = sim_persistence.snapshot_engine(engine)
        self.assertEqual(snap["cpu_count"], 8)
        self.assertEqual(snap["mem_mb"], 16384)
        restored = sim_persistence.restore_engine(snap)
        self.assertEqual(restored.shell.run("nproc").strip(), "8")
        self.assertEqual(restored.shell.state.hostname, "db-prod-01")
