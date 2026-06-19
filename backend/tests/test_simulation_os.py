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

    def test_real_check_sh_script_passes_after_fix(self):
        """check.sh uses if/exit 1 blocks — parser must not treat those as unconditional failures."""
        check_sh = """#!/bin/bash
nginx -t 2>/dev/null
if [ $? -ne 0 ]; then
    echo "FAIL: nginx configuration is invalid"
    exit 1
fi
if ! pgrep -x nginx > /dev/null 2>&1; then
    echo "FAIL: nginx is not running"
    exit 1
fi
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80 2>/dev/null)
if [ "$HTTP_CODE" != "200" ]; then
    echo "FAIL: nginx not responding on port 80 (got HTTP $HTTP_CODE)"
    exit 1
fi
echo "PASS"
exit 0
"""
        sim = BaseRHELSimulator(scenario_slug="sim-rhel-broken-nginx")
        passed, msg = validate_simulation_state(sim.state, check_sh)
        self.assertFalse(passed)
        sim.shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
        sim.shell.run("systemctl start nginx")
        passed, msg = validate_simulation_state(sim.state, check_sh)
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
        boot._handle_boot("redhat")
        out = boot._handle_boot("systemctl status sshd")
        self.assertIn("sshd", out)


class SELinuxCommandTests(SimpleTestCase):
    def test_getenforce_setenforce_roundtrip(self):
        shell = RHELShell()
        self.assertEqual(shell.run("getenforce"), "Enforcing")
        self.assertEqual(shell.run("setenforce 0"), "")
        self.assertEqual(shell.run("getenforce"), "Permissive")
        self.assertEqual(shell.state.selinux_mode, "Permissive")
        shell.run("setenforce Enforcing")
        self.assertEqual(shell.run("getenforce"), "Enforcing")
        shell.run("setenforce 1")
        self.assertEqual(shell.state.selinux_mode, "Enforcing")

    def test_sestatus_reflects_mode(self):
        shell = RHELShell()
        shell.run("setenforce 0")
        out = shell.run("sestatus")
        self.assertIn("Current mode:", out)
        self.assertIn("permissive", out)

    def test_semanage_port_adds_state(self):
        shell = RHELShell()
        shell.run("semanage port -a -t http_port_t -p tcp 8080")
        self.assertIn(8080, shell.state.selinux_ports.get("http_port_t", []))
        self.assertIn("8080", shell.run("semanage port -l"))

    def test_chcon_and_restorecon_set_context(self):
        shell = RHELShell()
        shell.run("echo data > /var/www/index.html")
        shell.run("chcon -t httpd_sys_content_t /var/www/index.html")
        ctx = shell.state.file_contexts.get("/var/www/index.html", "")
        self.assertIn("httpd_sys_content_t", ctx)
        shell.run("semanage fcontext -a -t httpd_sys_content_t /var/www/index.html")
        shell.run("restorecon -v /var/www/index.html")
        self.assertIn("/var/www/index.html", shell.state.file_contexts)


class FilesystemCommandTests(SimpleTestCase):
    def test_mkfs_mount_df_workflow(self):
        shell = RHELShell(scenario_slug="sim-rhel-mkfs-mount")
        out = shell.run("mkfs.xfs /dev/sdc")
        self.assertIn("UUID", out)
        dev = shell.state.find_block_device("/dev/sdc")
        self.assertEqual(dev.fstype, "xfs")
        self.assertTrue(dev.uuid)
        self.assertIn("/dev/sdc", shell.run("blkid"))
        self.assertEqual(shell.run("mount /dev/sdc /mnt/data"), "")
        self.assertEqual(dev.mountpoint, "/mnt/data")
        df = shell.run("df")
        self.assertIn("/mnt/data", df)
        self.assertIn("/dev/sdc", df)

    def test_mount_unformatted_device_fails(self):
        shell = RHELShell(scenario_slug="sim-rhel-mkfs-mount")
        out = shell.run("mount /dev/sdc /mnt/data")
        self.assertIn("wrong fs type", out)

    def test_mount_by_uuid(self):
        shell = RHELShell(scenario_slug="sim-rhel-mkfs-mount")
        shell.run("mkfs.ext4 /dev/sdc")
        uuid = shell.state.find_block_device("/dev/sdc").uuid
        self.assertEqual(shell.run(f"mount UUID={uuid} /mnt/data"), "")
        self.assertIn("/mnt/data", shell.run("df"))

    def test_lvcreate_creates_lv_and_blockdev(self):
        shell = RHELShell()
        out = shell.run("lvcreate -L 5G -n appdata rhel")
        self.assertIn("created", out.lower())
        self.assertIn("rhel/appdata", shell.state.lvm.lvs)
        self.assertIsNotNone(shell.state.find_block_device("/dev/mapper/rhel-appdata"))
        self.assertIn("appdata", shell.run("lvs"))

    def test_lvcreate_then_mkfs_then_mount(self):
        shell = RHELShell()
        shell.run("lvcreate -L 5G -n appdata rhel")
        shell.run("mkfs.xfs /dev/mapper/rhel-appdata")
        shell.run("mkdir /data")
        self.assertEqual(shell.run("mount /dev/mapper/rhel-appdata /data"), "")
        self.assertIn("/data", shell.run("df"))

    def test_swapon_swapoff(self):
        shell = RHELShell(scenario_slug="sim-rhel-swap-add")
        shell.run("mkswap /dev/sdc")
        self.assertEqual(shell.state.find_block_device("/dev/sdc").fstype, "swap")
        self.assertEqual(shell.run("swapon /dev/sdc"), "")
        self.assertIn("/dev/sdc", shell.state.swaps)
        self.assertIn("/dev/sdc", shell.run("swapon -s"))
        shell.run("swapoff /dev/sdc")
        self.assertNotIn("/dev/sdc", shell.state.swaps)

    def test_lsblk_tree(self):
        shell = RHELShell()
        out = shell.run("lsblk")
        self.assertIn("sda", out)
        self.assertIn("rhel-root", out)
        self.assertIn("disk", out)

    def test_disk_missing_rescan_workflow(self):
        """Classic: disk invisible until a SCSI rescan reveals it, then mkfs+mount."""
        shell = RHELShell(scenario_slug="sim-rhel-disk-missing")
        self.assertIsNone(shell.state.find_block_device("/dev/sdc"))
        self.assertNotIn("sdc", shell.run("lsblk"))
        # Rescan via the SCSI host scan node.
        shell.run('echo "- - -" > /sys/class/scsi_host/host0/scan')
        self.assertIsNotNone(shell.state.find_block_device("/dev/sdc"))
        self.assertIn("sdc", shell.run("lsblk"))
        shell.run("mkfs.xfs /dev/sdc")
        shell.run("mkdir /mnt/new")
        self.assertEqual(shell.run("mount /dev/sdc /mnt/new"), "")
        self.assertIn("/mnt/new", shell.run("df"))

    def test_rescan_scsi_bus_script(self):
        shell = RHELShell(scenario_slug="sim-rhel-disk-missing")
        out = shell.run("rescan-scsi-bus.sh")
        self.assertIn("new", out.lower())
        self.assertIsNotNone(shell.state.find_block_device("/dev/sdc"))

    def test_fdisk_parted_create_partition(self):
        shell = RHELShell(scenario_slug="sim-rhel-mkfs-mount")
        shell.run("parted /dev/sdc --script mkpart primary xfs 0% 100%")
        self.assertIsNotNone(shell.state.find_block_device("/dev/sdc1"))

    def test_fsck_and_xfs_repair(self):
        shell = RHELShell(scenario_slug="sim-rhel-mkfs-mount")
        shell.run("mkfs.ext4 /dev/sdc")
        self.assertIn("clean", shell.run("fsck /dev/sdc"))
        shell.run("mkfs.xfs /dev/sdc")
        self.assertIn("done", shell.run("xfs_repair /dev/sdc"))

    def test_resize2fs_grows_after_lvextend(self):
        shell = RHELShell()
        shell.run("lvcreate -L 5G -n grow rhel")
        shell.run("mkfs.ext4 /dev/mapper/rhel-grow")
        shell.run("mkdir /grow")
        shell.run("mount /dev/mapper/rhel-grow /grow")
        shell.run("lvextend -L +5G /dev/mapper/rhel-grow")
        out = shell.run("resize2fs /dev/mapper/rhel-grow")
        self.assertIn("resized", out)


class OutputRedirectionTests(SimpleTestCase):
    def test_stdout_redirect_any_command(self):
        shell = RHELShell()
        shell.run("uname -r > /tmp/kernel.txt")
        self.assertEqual(shell.state.read_file("/tmp/kernel.txt"), "5.14.0-362.el9.x86_64\n")

    def test_append_redirect(self):
        shell = RHELShell()
        shell.run("echo first > /tmp/log.txt")
        shell.run("echo second >> /tmp/log.txt")
        self.assertEqual(shell.state.read_file("/tmp/log.txt"), "first\nsecond\n")

    def test_stderr_redirect_captures_errors(self):
        shell = RHELShell()
        out = shell.run("cat /does/not/exist 2> /tmp/err.txt")
        self.assertEqual(out, "")
        self.assertIn("No such file", shell.state.read_file("/tmp/err.txt") or "")

    def test_blkid_redirect_to_file(self):
        shell = RHELShell()
        shell.run("blkid > /tmp/devices.txt")
        self.assertIn("UUID=", shell.state.read_file("/tmp/devices.txt") or "")


class GrepCommandTests(SimpleTestCase):
    def test_invalid_regex_returns_grep_error(self):
        shell = RHELShell()
        shell.run("echo content > /tmp/g.txt")
        out = shell.run('grep "[" /tmp/g.txt')
        self.assertIn("Invalid regular expression", out)
        self.assertNotIn("Simulation error", out)

    def test_grep_flags(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/m.txt", "Apple\nbanana\nAPPLE\ncherry\n")
        self.assertEqual(shell.run("grep -i apple /tmp/m.txt"), "Apple\nAPPLE")
        self.assertNotIn("banana", shell.run("grep -v banana /tmp/m.txt"))
        # -i a matches every line with an 'a' or 'A' (Apple, banana, APPLE) = 3.
        self.assertEqual(shell.run("grep -ic a /tmp/m.txt"), "3")
        # case-sensitive lowercase 'a' only matches banana = 1.
        self.assertEqual(shell.run("grep -c a /tmp/m.txt"), "1")

    def test_grep_recursive(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/dir/a.txt", "needle here\n")
        shell.state.write_file("/tmp/dir/b.txt", "nothing\n")
        out = shell.run("grep -r needle /tmp/dir")
        self.assertIn("needle", out)
        self.assertIn("/tmp/dir/a.txt", out)


class CopyMoveCommandTests(SimpleTestCase):
    def test_cp_recursive_directory(self):
        shell = RHELShell()
        shell.state._mkdir("/tmp/src")
        shell.state.write_file("/tmp/src/a.txt", "A")
        shell.state.write_file("/tmp/src/sub/b.txt", "B")
        self.assertEqual(shell.run("cp -r /tmp/src /tmp/dst"), "")
        self.assertEqual(shell.state.read_file("/tmp/dst/a.txt"), "A")
        self.assertEqual(shell.state.read_file("/tmp/dst/sub/b.txt"), "B")

    def test_cp_directory_without_r_fails(self):
        shell = RHELShell()
        shell.state._mkdir("/tmp/src2")
        out = shell.run("cp /tmp/src2 /tmp/dst2")
        self.assertIn("omitting directory", out)
        self.assertIsNone(shell.state.read_file("/tmp/dst2"))

    def test_mv_is_atomic_on_failure(self):
        shell = RHELShell()
        # Source missing: must NOT create dest and must NOT run rm/concat output.
        out = shell.run("mv /tmp/missing.txt /tmp/dest.txt")
        self.assertIn("cannot stat", out)
        self.assertIsNone(shell.state.read_file("/tmp/dest.txt"))

    def test_mv_moves_file(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/from.txt", "payload")
        self.assertEqual(shell.run("mv /tmp/from.txt /tmp/to.txt"), "")
        self.assertIsNone(shell.state.read_file("/tmp/from.txt"))
        self.assertEqual(shell.state.read_file("/tmp/to.txt"), "payload")

    def test_mv_directory(self):
        shell = RHELShell()
        shell.state._mkdir("/tmp/mdir")
        shell.state.write_file("/tmp/mdir/f.txt", "x")
        shell.run("mv /tmp/mdir /tmp/mdir2")
        self.assertIsNone(shell.state.read_file("/tmp/mdir/f.txt"))
        self.assertEqual(shell.state.read_file("/tmp/mdir2/f.txt"), "x")


class AwkTarCommandTests(SimpleTestCase):
    def test_awk_print_field(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/d.txt", "alice 30\nbob 25\n")
        self.assertEqual(shell.run("awk '{print $1}' /tmp/d.txt"), "alice\nbob")
        self.assertEqual(shell.run("awk '{print $2}' /tmp/d.txt"), "30\n25")

    def test_awk_field_separator(self):
        shell = RHELShell()
        self.assertEqual(shell.run("awk -F: '{print $1}' /etc/passwd").splitlines()[0], "root")

    def test_awk_pattern(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/d2.txt", "alice 30\nbob 25\n")
        self.assertEqual(shell.run("awk '/bob/ {print $2}' /tmp/d2.txt"), "25")

    def test_awk_from_pipe(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/d3.txt", "x 1\ny 2\n")
        self.assertEqual(shell.run("cat /tmp/d3.txt | awk '{print $1}'"), "x\ny")

    def test_tar_create_and_extract(self):
        shell = RHELShell()
        shell.state._mkdir("/opt/proj")
        shell.state.write_file("/opt/proj/main.py", "print(1)")
        shell.state.write_file("/opt/proj/lib/util.py", "x = 2")
        self.assertEqual(shell.run("tar -czf /tmp/proj.tar.gz /opt/proj"), "")
        self.assertIsNotNone(shell.state.read_file("/tmp/proj.tar.gz"))
        shell.run("rm -rf /opt/proj")
        self.assertIsNone(shell.state.read_file("/opt/proj/main.py"))
        shell.run("tar -xzf /tmp/proj.tar.gz")
        self.assertEqual(shell.state.read_file("/opt/proj/main.py"), "print(1)")
        self.assertEqual(shell.state.read_file("/opt/proj/lib/util.py"), "x = 2")


class EditorPersistenceTests(SimpleTestCase):
    def _drain(self, holder):
        import queue
        while True:
            try:
                holder._out_q.get_nowait()
            except queue.Empty:
                break

    def test_ctrl_o_then_ctrl_x_persists(self):
        """Regression: Ctrl+O cleared `modified`, so Ctrl+X discarded edits."""
        sim = BaseRHELSimulator()
        sim.shell.state.write_file("/tmp/edit.conf", "original")
        sim.shell.run("nano /tmp/edit.conf")
        holder = sim.create_stream()
        self._drain(holder)
        holder.send(b"PREFIX-")       # type characters
        holder.send(b"\x0f")          # Ctrl+O write out (clears modified flag)
        holder.send(b"\x18")          # Ctrl+X exit
        self.assertIsNone(sim.shell.state.editor)
        content = sim.shell.state.read_file("/tmp/edit.conf")
        self.assertIn("PREFIX-", content)

    def test_modified_on_exit_persists(self):
        sim = BaseRHELSimulator()
        sim.shell.state.write_file("/tmp/edit2.conf", "orig")
        sim.shell.run("nano /tmp/edit2.conf")
        holder = sim.create_stream()
        self._drain(holder)
        holder.send(b"ADDED")
        holder.send(b"\x18")          # Ctrl+X without explicit write
        content = sim.shell.state.read_file("/tmp/edit2.conf")
        self.assertIn("ADDED", content)

    def test_vi_wq_persists(self):
        sim = BaseRHELSimulator()
        sim.shell.state.write_file("/tmp/v.conf", "vcontent")
        sim.shell.run("vi /tmp/v.conf")
        holder = sim.create_stream()
        self._drain(holder)
        holder.send(b"NEW")
        holder.send(b":wq\r")
        self.assertIn("NEW", sim.shell.state.read_file("/tmp/v.conf"))

    def test_editor_session_dirty_after_ctrl_o(self):
        from apps.labs.provisioner.simulation.editor_mode import EditorSession
        ed = EditorSession("/tmp/f", "x")
        ed.process("abc")
        ed.process("\x0f")  # Ctrl+O
        self.assertFalse(ed.modified)
        self.assertTrue(ed.dirty)  # still flagged for save-on-close


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
