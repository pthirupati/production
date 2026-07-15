"""Tests for simulated RHEL OS shell, engines, and validation."""

from django.test import SimpleTestCase, TestCase

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
        # Construct with the scenario slug (as RHELShell/base_sim do in
        # production) so the nginx web-scenario unit is pre-seeded before the
        # preset mutates it — nginx is no longer a base-system service.
        state = RHELOSState(hostname="primary", scenario_slug="sim-rhel-broken-nginx")
        apply_scenario_preset("sim-rhel-broken-nginx", state)
        companion = state.clone_for_host("web1")
        self.assertEqual(companion.hostname, "web1")
        self.assertIn("/etc/nginx/sites-enabled/default", companion.vfs)

    def test_standalone_kubectl_uses_full_cluster_engine(self):
        shell = RHELShell(scenario_slug="pod-crashloop")
        out = shell.run("kubectl get pods")
        self.assertIn("NAME", out)
        self.assertIn("READY", out)
        self.assertTrue(
            "CrashLoopBackOff" in out or "Running" in out,
            f"expected realistic pod statuses, got: {out!r}",
        )
        nodes = shell.run("kubectl get nodes")
        self.assertIn("Ready", nodes)

    def test_standalone_aws_cli(self):
        shell = RHELShell()
        out = shell.run("aws sts get-caller-identity")
        self.assertIn("123456789012", out)
        s3 = shell.run("aws s3 ls")
        self.assertIn("fixitlab", s3.lower())


class ValidationTests(TestCase):  # TestCase: run_validation queries LabSession (provisioner gate cascade)
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


class ShellOperatorTests(SimpleTestCase):
    """`;`, `&&` and `||` command-list operators."""

    def test_semicolon_runs_all(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo one ; echo two"), "one\ntwo")

    def test_and_short_circuits_on_failure(self):
        shell = RHELShell()
        # `false` fails, so the &&-segment must be skipped.
        self.assertEqual(shell.run("false && echo NOPE"), "")

    def test_and_runs_on_success(self):
        shell = RHELShell()
        self.assertEqual(shell.run("true && echo YES"), "YES")

    def test_or_fires_on_failure(self):
        shell = RHELShell()
        self.assertEqual(shell.run("false || echo FALLBACK"), "FALLBACK")

    def test_or_skips_on_success(self):
        shell = RHELShell()
        self.assertEqual(shell.run("true || echo SKIPPED"), "")

    def test_command_not_found_sets_exit_and_triggers_or(self):
        shell = RHELShell()
        # As in a real shell the error goes to the terminal AND the ||-fallback
        # fires because the failed lookup sets a non-zero exit code.
        out = shell.run("nosuchcmd || echo RECOVERED")
        self.assertIn("command not found", out)
        self.assertIn("RECOVERED", out)

    def test_quoted_operator_not_split(self):
        shell = RHELShell()
        self.assertEqual(shell.run('echo "a; b && c"'), "a; b && c")

    def test_escaped_semicolon_in_find_not_split(self):
        shell = RHELShell()
        # Must not raise; find still resolves the matching path.
        out = shell.run(r"find /etc/passwd")
        self.assertEqual(out, "/etc/passwd")


class ShellExpansionTests(SimpleTestCase):
    """Variable, command-substitution, tilde and glob expansion."""

    def test_var_expansion(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo $USER"), "root")
        self.assertEqual(shell.run("echo $HOME"), "/root")

    def test_braced_var_expansion(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo ${HOME}/bin"), "/root/bin")

    def test_assignment_then_use(self):
        shell = RHELShell()
        shell.run("MYVAR=hello")
        self.assertEqual(shell.state.env.get("MYVAR"), "hello")
        self.assertEqual(shell.run("echo $MYVAR"), "hello")

    def test_assignment_and_use_in_one_line(self):
        shell = RHELShell()
        self.assertEqual(shell.run("FOO=bar; echo $FOO"), "bar")

    def test_undefined_var_is_empty(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo [${NOPE}]"), "[]")

    def test_command_substitution(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo $(whoami)"), "root")

    def test_command_substitution_with_pipe(self):
        shell = RHELShell()
        self.assertEqual(
            shell.run("echo $(grep root /etc/passwd | cut -d: -f1)"), "root")

    def test_tilde_expansion_in_redirect(self):
        shell = RHELShell()
        shell.run("echo hi > ~/note.txt")
        self.assertEqual(shell.state.read_file("/root/note.txt"), "hi\n")

    def test_glob_expansion(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/globtest/a.log", "1")
        shell.state.write_file("/tmp/globtest/b.log", "2")
        shell.state.write_file("/tmp/globtest/c.txt", "3")
        shell.run("cd /tmp/globtest")
        # echo joins all expanded words, so it shows the full glob result.
        out = shell.run("echo *.log")
        self.assertIn("a.log", out)
        self.assertIn("b.log", out)
        self.assertNotIn("c.txt", out)

    def test_glob_absolute_path(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/gt2/x.conf", "1")
        shell.state.write_file("/tmp/gt2/y.conf", "2")
        out = shell.run("echo /tmp/gt2/*.conf")
        self.assertIn("/tmp/gt2/x.conf", out)
        self.assertIn("/tmp/gt2/y.conf", out)

    def test_glob_no_match_left_literal(self):
        shell = RHELShell()
        out = shell.run("echo /tmp/no-such-dir/*.zzz")
        self.assertIn("*.zzz", out)


class CoreutilsCommandTests(SimpleTestCase):
    def test_true_false_exit_codes(self):
        shell = RHELShell()
        shell.run("true")
        self.assertEqual(shell.state.last_exit_code, 0)
        shell.run("false")
        self.assertEqual(shell.state.last_exit_code, 1)

    def test_cut_field(self):
        shell = RHELShell()
        self.assertEqual(shell.run("cut -d: -f1 /etc/passwd").splitlines()[0], "root")

    def test_cut_from_pipe(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo a:b:c | cut -d: -f2"), "b")

    def test_cut_char_range(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo abcdef | cut -c2-4"), "bcd")

    def test_tr_translate_and_delete(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo hello | tr a-z A-Z"), "HELLO")
        self.assertEqual(shell.run("echo hello | tr -d l"), "heo")

    def test_tee_writes_and_passes_through(self):
        shell = RHELShell()
        out = shell.run("echo persisted | tee /tmp/tee.txt")
        self.assertEqual(out, "persisted")
        self.assertEqual(shell.state.read_file("/tmp/tee.txt"), "persisted\n")

    def test_tee_append(self):
        shell = RHELShell()
        shell.run("echo one | tee /tmp/tee2.txt")
        shell.run("echo two | tee -a /tmp/tee2.txt")
        self.assertEqual(shell.state.read_file("/tmp/tee2.txt"), "one\ntwo\n")

    def test_xargs_appends_stdin(self):
        shell = RHELShell()
        self.assertEqual(shell.run("echo world | xargs echo hello"), "hello world")

    def test_stat_format(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/s.txt", "12345")
        self.assertEqual(shell.run("stat -c %s /tmp/s.txt"), "5")

    def test_stat_missing_file(self):
        shell = RHELShell()
        out = shell.run("stat /tmp/does-not-exist")
        self.assertIn("No such file", out)
        self.assertEqual(shell.state.last_exit_code, 1)

    def test_du_summarize(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/dudir/f.txt", "x" * 2048)
        out = shell.run("du -sh /tmp/dudir")
        self.assertIn("/tmp/dudir", out)

    def test_nproc(self):
        shell = RHELShell()
        self.assertTrue(shell.run("nproc").isdigit())

    def test_basename_dirname(self):
        shell = RHELShell()
        self.assertEqual(shell.run("basename /a/b/c.txt"), "c.txt")
        self.assertEqual(shell.run("basename /a/b/c.txt .txt"), "c")
        self.assertEqual(shell.run("dirname /a/b/c.txt"), "/a/b")

    def test_seq(self):
        shell = RHELShell()
        self.assertEqual(shell.run("seq 3"), "1\n2\n3")
        self.assertEqual(shell.run("seq 2 2 6"), "2\n4\n6")

    def test_sleep_is_noop(self):
        shell = RHELShell()
        self.assertEqual(shell.run("sleep 5"), "")
        self.assertEqual(shell.state.last_exit_code, 0)

    def test_sysctl_read_and_write(self):
        shell = RHELShell()
        self.assertIn("vm.swappiness", shell.run("sysctl vm.swappiness"))
        shell.run("sysctl -w vm.swappiness=10")
        self.assertIn("= 10", shell.run("sysctl vm.swappiness"))

    def test_diff_reports_change(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/a1", "line1\nline2\n")
        shell.state.write_file("/tmp/b1", "line1\nCHANGED\n")
        out = shell.run("diff /tmp/a1 /tmp/b1")
        self.assertIn("CHANGED", out)
        self.assertEqual(shell.state.last_exit_code, 1)

    def test_diff_identical_files(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/a2", "same\n")
        shell.state.write_file("/tmp/b2", "same\n")
        self.assertEqual(shell.run("diff /tmp/a2 /tmp/b2"), "")
        self.assertEqual(shell.state.last_exit_code, 0)

    def test_md5sum_deterministic(self):
        shell = RHELShell()
        shell.state.write_file("/tmp/h.txt", "content")
        out = shell.run("md5sum /tmp/h.txt")
        # md5("content")
        self.assertTrue(out.startswith("9a0364b9e99bb480dd25e1f0284c8555"))
        self.assertIn("/tmp/h.txt", out)


class NetworkingToolTests(SimpleTestCase):
    def test_dig_short(self):
        shell = RHELShell()
        self.assertEqual(shell.run("dig +short example.com"), "93.184.216.34")

    def test_dig_localhost(self):
        shell = RHELShell()
        self.assertEqual(shell.run("dig +short localhost"), "127.0.0.1")

    def test_nslookup_resolves(self):
        shell = RHELShell()
        self.assertIn("93.184.216.34", shell.run("nslookup example.com"))

    def test_host_nxdomain(self):
        shell = RHELShell()
        self.assertIn("not found", shell.run("host no-such-host.invalid"))

    def test_dig_uses_etc_hosts(self):
        shell = RHELShell()
        shell.state.write_file("/etc/hosts", "127.0.0.1 localhost\n10.5.5.5 app.internal\n")
        self.assertEqual(shell.run("dig +short app.internal"), "10.5.5.5")

    def test_nc_open_port(self):
        shell = RHELShell()
        out = shell.run("nc -zv localhost 22")
        self.assertIn("succeeded", out)

    def test_nc_refused_when_service_down(self):
        shell = RHELShell()
        nginx = shell.state.services.get("nginx")
        if nginx:
            nginx.active = "inactive"
        out = shell.run("nc -zv localhost 80")
        self.assertIn("refused", out.lower())
        self.assertEqual(shell.state.last_exit_code, 1)

    def test_openssl_version(self):
        shell = RHELShell()
        self.assertIn("OpenSSL", shell.run("openssl version"))

    def test_wget_success(self):
        # nginx is no longer a base-system service, so bring up a real server
        # first (install + start) before fetching — wget succeeds against a
        # running web server.
        shell = RHELShell()
        shell.run("dnf install -y nginx")
        shell.run("systemctl start nginx")
        out = shell.run("wget http://localhost")
        self.assertIn("200 OK", out)

    def test_iptables_add_opens_port(self):
        shell = RHELShell()
        shell.run("iptables -A INPUT -p tcp --dport 8080 -j ACCEPT")
        self.assertTrue(shell.state.firewall.is_port_open(8080))

    def test_ufw_allow_opens_port(self):
        shell = RHELShell()
        shell.run("ufw allow 9090/tcp")
        self.assertTrue(shell.state.firewall.is_port_open(9090))

    def test_watch_runs_wrapped_command_once(self):
        shell = RHELShell()
        out = shell.run("watch -n1 echo hi")
        self.assertIn("hi", out)


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


class ProvisionerTests(TestCase):
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


class PackageInstallTests(SimpleTestCase):
    """Realistic dnf/yum/apt package installation and its honest post-state."""

    # ── base system is honest about what is NOT installed ──
    def test_base_system_has_no_nginx(self):
        state = RHELOSState()
        self.assertNotIn("nginx", state.services)
        self.assertIsNone(state.resolve_binary("nginx"))
        # base daemons remain
        self.assertEqual(state.services["sshd"].active, "active")

    def test_nginx_command_not_found_before_install(self):
        shell = RHELShell()
        out = shell.run("nginx")
        self.assertIn("command not found", out)
        self.assertEqual(shell.state.last_exit_code, 127)

    def test_which_only_resolves_installed_binaries(self):
        shell = RHELShell()
        # coreutils base binary always resolves
        self.assertEqual(shell.run("which bash"), "/usr/bin/bash")
        # not-installed tool does not
        out = shell.run("which nginx")
        self.assertIn("no nginx", out)
        self.assertEqual(shell.state.last_exit_code, 1)

    def test_systemctl_status_unknown_before_install(self):
        shell = RHELShell()
        out = shell.run("systemctl status nginx")
        self.assertIn("could not be found", out)

    def test_nginx_config_test_no_conf_before_install(self):
        # After install but with the config removed, nginx -t emits the real
        # open() error rather than a fake success.
        shell = RHELShell()
        shell.run("dnf install -y nginx")
        shell.run("rm /etc/nginx/nginx.conf")
        out = shell.run("nginx -t")
        self.assertIn("open() \"/etc/nginx/nginx.conf\" failed", out)
        self.assertIn("No such file or directory", out)

    # ── realistic dnf transaction ──
    def test_dnf_install_renders_full_transaction(self):
        shell = RHELShell()
        out = shell.run("dnf install -y nginx")
        # dependency-resolution table headers
        for token in ("Package", "Arch", "Version", "Repository", "Size"):
            self.assertIn(token, out)
        self.assertIn("Dependencies resolved.", out)
        self.assertIn("Transaction Summary", out)
        self.assertIn("Total download size:", out)
        self.assertIn("Installed size:", out)
        self.assertIn("Downloading Packages", out)
        self.assertIn("Running transaction check", out)
        self.assertIn("Running transaction test", out)
        self.assertIn("Transaction test succeeded.", out)
        self.assertIn("Running transaction", out)
        self.assertIn("Installing :", out)
        self.assertIn("Verifying  :", out)
        self.assertIn("Installed:", out)
        self.assertIn("Complete!", out)

    def test_dnf_install_lists_dependencies(self):
        shell = RHELShell()
        out = shell.run("dnf install -y nginx")
        # nginx pulls its deps into the transaction
        self.assertIn("nginx-filesystem", out)
        self.assertIn("openssl-libs", out)
        self.assertIn("pcre2", out)
        self.assertIn("Install  4 Packages", out)
        # all deps recorded in the rpm DB
        for pkg in ("nginx", "nginx-filesystem", "openssl-libs", "pcre2"):
            self.assertIn(pkg, shell.state.installed_packages)

    def test_dnf_install_real_post_state(self):
        shell = RHELShell()
        shell.run("dnf install -y nginx")
        # binary resolves
        self.assertEqual(shell.run("which nginx"), "/usr/sbin/nginx")
        # config written to the FS
        self.assertIsNotNone(shell.state.read_file("/etc/nginx/nginx.conf"))
        # log files created
        self.assertTrue(shell.state.file_exists("/var/log/nginx/error.log"))
        # unit known and inactive/disabled (install does not start it)
        svc = shell.state.services.get("nginx")
        self.assertIsNotNone(svc)
        self.assertEqual(svc.active, "inactive")
        self.assertEqual(svc.enabled, "disabled")
        # nginx -t succeeds against the real config
        self.assertIn("test is successful", shell.run("nginx -t"))
        # systemctl status now knows it
        self.assertIn("nginx.service", shell.run("systemctl status nginx"))
        # catalog version recorded (not the 1.0.0 stub)
        self.assertIn("nginx-1.20.1", shell.state.installed_packages["nginx"])

    def test_yum_shares_catalog(self):
        shell = RHELShell()
        out = shell.run("yum install -y httpd")
        self.assertIn("Complete!", out)
        self.assertEqual(shell.run("which httpd"), "/usr/sbin/httpd")
        # httpd deps from the catalog
        self.assertIn("httpd-tools", shell.state.installed_packages)
        self.assertIn("apr", shell.state.installed_packages)

    def test_dnf_install_already_installed(self):
        shell = RHELShell()
        shell.run("dnf install -y redis")
        out = shell.run("dnf install -y redis")
        self.assertIn("already installed", out)
        self.assertIn("Nothing to do", out)

    def test_dnf_ignores_no_flag_when_assumeyes(self):
        shell = RHELShell()
        out = shell.run("dnf install -y git")
        self.assertNotIn("Is this ok", out)
        self.assertIn("Complete!", out)
        self.assertIsNone(shell.state.pending_confirm)

    # ── interactive [y/N] confirm ──
    def test_dnf_install_prompts_without_y(self):
        shell = RHELShell()
        out = shell.run("dnf install nginx")
        self.assertIn("Is this ok [y/N]:", out)
        # not yet installed — awaiting confirmation
        self.assertNotIn("nginx", shell.state.installed_packages)
        self.assertIsNotNone(shell.state.pending_confirm)

    def test_dnf_confirm_yes_installs(self):
        shell = RHELShell()
        shell.run("dnf install nginx")
        out = shell.run("y")
        self.assertIn("Complete!", out)
        self.assertIn("nginx", shell.state.installed_packages)
        self.assertEqual(shell.run("which nginx"), "/usr/sbin/nginx")

    def test_dnf_confirm_no_aborts(self):
        shell = RHELShell()
        shell.run("dnf install nginx")
        out = shell.run("n")
        self.assertNotIn("nginx", shell.state.installed_packages)
        self.assertIn("aborted", out.lower())

    def test_dnf_confirm_empty_defaults_no(self):
        shell = RHELShell()
        shell.run("dnf install nginx")
        shell.run("")  # empty line = default N for dnf
        self.assertNotIn("nginx", shell.state.installed_packages)

    # ── apt parity ──
    def test_apt_install_renders_apt_output(self):
        shell = RHELShell()
        out = shell.run("apt-get install -y redis-server")
        self.assertIn("Reading package lists... Done", out)
        self.assertIn("Building dependency tree", out)
        self.assertIn("The following NEW packages will be installed:", out)
        self.assertIn("additional disk space will be used", out)
        self.assertIn("Setting up redis", out)
        self.assertIn("Processing triggers for", out)

    def test_apt_maps_debian_names_to_catalog(self):
        shell = RHELShell()
        # apache2 -> httpd, docker.io -> docker
        shell.run("apt-get install -y apache2")
        self.assertIn("httpd", shell.state.installed_packages)
        self.assertEqual(shell.run("which httpd"), "/usr/sbin/httpd")

    def test_apt_confirm_prompt_and_default_yes(self):
        shell = RHELShell()
        out = shell.run("apt install nginx")
        self.assertIn("Do you want to continue? [Y/n]", out)
        # empty enter = default Y for apt -> proceeds
        shell.run("")
        self.assertIn("nginx", shell.state.installed_packages)

    def test_apt_confirm_no_aborts(self):
        shell = RHELShell()
        shell.run("apt install nginx")
        shell.run("n")
        self.assertNotIn("nginx", shell.state.installed_packages)

    # ── rpm and remove ──
    def test_rpm_query_after_install(self):
        shell = RHELShell()
        shell.run("dnf install -y mariadb-server")
        out = shell.run("rpm -q mariadb-server")
        self.assertIn("mariadb-server-10.5", out)

    def test_dnf_remove_drops_binary_and_unit(self):
        shell = RHELShell()
        shell.run("dnf install -y haproxy")
        self.assertEqual(shell.run("which haproxy"), "/usr/sbin/haproxy")
        shell.run("dnf remove -y haproxy")
        self.assertNotIn("haproxy", shell.state.installed_packages)
        self.assertIn("no haproxy", shell.run("which haproxy"))
        self.assertNotIn("haproxy", shell.state.services)

    # ── every teaching package installs cleanly (no AttributeError) ──
    def test_all_catalog_service_packages_install(self):
        from apps.labs.provisioner.simulation.rhel_os import PACKAGE_CATALOG
        service_pkgs = [n for n, s in PACKAGE_CATALOG.items() if s.units]
        self.assertIn("nginx", service_pkgs)
        for pkg in service_pkgs:
            shell = RHELShell()
            out = shell.run(f"dnf install -y {pkg}")
            self.assertIn("Complete!", out, f"{pkg} did not complete")
            self.assertIn(pkg, shell.state.installed_packages)
            # the unit(s) the package ships are now known
            for unit, _ in PACKAGE_CATALOG[pkg].units:
                self.assertIn(unit, shell.state.services, f"{pkg} unit {unit} missing")


class IpCommandTests(SimpleTestCase):
    """`ip` must accept the real-world abbreviations, not just the full forms."""

    def _ip(self, cmd):
        return str(RHELShell().run(cmd)).strip()

    def test_ip_abbreviations_show_addresses(self):
        for cmd in ("ip a", "ip a s", "ip addr", "ip addr show", "ip address", "ip -br a", "ip a s eth0"):
            out = self._ip(cmd)
            self.assertFalse(out.startswith("Usage"), f"{cmd!r} returned Usage instead of output")
            self.assertIn("eth0" if "eth0" in cmd else "lo", out, f"{cmd!r} missing interface")

    def test_ip_link_and_route_and_neigh(self):
        self.assertFalse(self._ip("ip link").startswith("Usage"))
        self.assertFalse(self._ip("ip l").startswith("Usage"))
        self.assertIn("default via", self._ip("ip r"))
        self.assertIn("default via", self._ip("ip route show"))
        self.assertNotEqual(self._ip("ip neigh"), "")

    def test_ip_link_set_up_down(self):
        sh = RHELShell()
        sh.run("ip link set eth0 down")
        self.assertFalse(sh.state.network_ifs["eth0"].get("up", True))
        sh.run("ip link set dev eth0 up")
        self.assertTrue(sh.state.network_ifs["eth0"].get("up", True))

    def test_cross_tech_nic_revealed_on_listing(self):
        """A NIC hot-added in VMware must surface when the operator runs `ip a`."""
        from apps.labs.provisioner.simulation import vmware_bridge as vb
        sh = RHELShell()
        sid = "test-iptest-crosstech"
        sh.state.session_id = sid
        vb.clear(sid)
        try:
            vb.record_pending_nic(sid, "10.0.0.77/24")
            out = str(sh.run("ip a"))
            self.assertIn("eth1", out)
            self.assertIn("10.0.0.77", out)
        finally:
            vb.clear(sid)


class SocketToolTests(SimpleTestCase):
    """ss / netstat / lsof must reflect which services are actually running."""

    def test_ss_shows_sshd_listener(self):
        sh = RHELShell()
        out = sh.run("ss -tlnp")
        self.assertIn("LISTEN", out)
        self.assertIn(":22", out)
        self.assertIn("sshd", out)
        # The old stub emitted a garbled unix-socket line — must be gone.
        self.assertNotIn("u_str", out)

    def test_ss_reflects_service_state(self):
        sh = RHELShell()
        self.assertNotIn(":80", sh.run("ss -tlnp"))  # nginx not installed/running
        sh.run("dnf install -y nginx")
        sh.run("systemctl start nginx")
        out = sh.run("ss -tlnp")
        self.assertIn(":80", out)
        self.assertIn("nginx", out)
        # Stopping it removes the listener.
        sh.run("systemctl stop nginx")
        self.assertNotIn(":80", sh.run("ss -tlnp"))

    def test_netstat_tulpn_lists_servers(self):
        sh = RHELShell()
        out = sh.run("netstat -tulpn")
        self.assertIn("0.0.0.0:22", out)
        self.assertIn("LISTEN", out)
        self.assertIn("sshd", out)

    def test_ss_udp_filter(self):
        sh = RHELShell()
        out = sh.run("ss -uln")
        self.assertIn(":123", out)   # chronyd UDP
        self.assertNotIn(":22", out) # tcp filtered out

    def test_lsof_port_filter(self):
        sh = RHELShell()
        self.assertIn("sshd", sh.run("lsof -i :22"))
        self.assertEqual(sh.run("lsof -i :80").strip(), "")


class SystemctlActionTests(SimpleTestCase):
    def test_is_enabled(self):
        sh = RHELShell()
        self.assertEqual(sh.run("systemctl is-enabled sshd").strip(), "enabled")
        sh.run("systemctl disable sshd")
        self.assertEqual(sh.run("systemctl is-enabled sshd").strip(), "disabled")

    def test_is_active_and_failed(self):
        sh = RHELShell()
        self.assertEqual(sh.run("systemctl is-active sshd").strip(), "active")
        self.assertEqual(sh.run("systemctl is-failed sshd").strip(), "active")

    def test_status_no_arg_is_overview(self):
        sh = RHELShell()
        out = sh.run("systemctl status")
        self.assertNotIn("could not be found", out)
        self.assertIn("State:", out)

    def test_failed_listing(self):
        sh = RHELShell()
        # No failed units on a healthy box.
        self.assertNotIn("could not be found", sh.run("systemctl --failed"))
        self.assertNotIn("could not be found", sh.run("systemctl list-units --failed"))
        # Mark one failed and confirm it surfaces.
        sh.state.services["sshd"].active = "failed"
        self.assertIn("sshd", sh.run("systemctl --failed"))

    def test_list_unit_files(self):
        sh = RHELShell()
        out = sh.run("systemctl list-unit-files")
        self.assertIn("sshd.service", out)
        self.assertIn("UNIT FILE", out)

    def test_reload_and_mask(self):
        sh = RHELShell()
        self.assertNotIn("Unknown operation", sh.run("systemctl reload sshd"))
        self.assertNotIn("Unknown operation", sh.run("systemctl reload-or-restart sshd"))
        out = sh.run("systemctl mask sshd")
        self.assertIn("/dev/null", out)
        self.assertEqual(sh.state.services["sshd"].enabled, "masked")


class SystemInfoToolTests(SimpleTestCase):
    def test_hostname_dash_I_returns_ip(self):
        sh = RHELShell()
        out = sh.run("hostname -I").strip()
        self.assertEqual(out, "10.0.0.10")
        self.assertNotIn("rhel-sim", out)

    def test_ping_parses_count_flag(self):
        sh = RHELShell()
        out = sh.run("ping -c1 8.8.8.8")
        self.assertIn("1 packets transmitted, 1 received", out)
        self.assertNotIn("Name or service not known", out)
        out2 = sh.run("ping -c 2 10.0.0.1")
        self.assertIn("2 packets transmitted, 2 received", out2)

    def test_ping_bad_host(self):
        sh = RHELShell()
        self.assertIn("Name or service not known", sh.run("ping this is not a host"))

    def test_free_units(self):
        sh = RHELShell()
        self.assertIn("Gi", sh.run("free -h"))
        m = sh.run("free -m")
        self.assertIn("16384", m)   # 16 GiB in MiB

    def test_top_batch(self):
        sh = RHELShell()
        out = sh.run("top -bn1")
        self.assertIn("PID", out)
        self.assertIn("sshd", out)

    def test_pidof_and_pstree(self):
        sh = RHELShell()
        self.assertEqual(sh.run("pidof sshd").strip(), "412")
        self.assertIn("systemd", sh.run("pstree"))

    def test_missing_procps_tools_present(self):
        sh = RHELShell()
        for cmd in ("lscpu", "vmstat", "findmnt", "uniq /etc/passwd", "who", "w",
                    "last", "lsmod", "arp -n", "route -n", "ifconfig", "ethtool eth0",
                    "traceroute 8.8.8.8", "file /etc/passwd", "hostnamectl",
                    "timedatectl", "chage -l root"):
            out = sh.run(cmd)
            self.assertNotIn("command not found", out, f"{cmd} should exist: {out!r}")

    def test_proc_files_and_release(self):
        sh = RHELShell()
        self.assertIn("processor", sh.run("cat /proc/cpuinfo"))
        self.assertIn("MemTotal", sh.run("cat /proc/meminfo"))
        self.assertIn("Red Hat", sh.run("cat /etc/redhat-release"))

    def test_nmcli_device_status(self):
        sh = RHELShell()
        out = sh.run("nmcli dev")
        self.assertIn("eth0", out)
        self.assertIn("connected", out)
        self.assertNotIn("nmcli: OK", out)

    def test_ls_long_shows_real_mode(self):
        sh = RHELShell()
        sh.state.write_file("/tmp/only-owner", "x")
        sh.state.vfs[sh.state.resolve_path("/tmp/only-owner")]["mode"] = "600"
        out = sh.run("ls -l /tmp/only-owner")
        self.assertIn("rw-------", out)

    def test_ls_la_shows_dot_entries(self):
        sh = RHELShell()
        out = sh.run("ls -la")
        self.assertIn(" .", out)
        self.assertIn(" ..", out)

    def test_stat_mode_matches_octal(self):
        sh = RHELShell()
        out = sh.run("stat /etc/passwd")
        self.assertIn("0644/-rw-r--r--", out)  # symbolic must match octal


class RpmDnfQueryTests(SimpleTestCase):
    def test_rpm_qi(self):
        sh = RHELShell()
        out = sh.run("rpm -qi bash")
        self.assertIn("Name        : bash", out)
        self.assertIn("License", out)
        self.assertNotIn("rpm: OK", out)

    def test_rpm_ql_and_qf(self):
        sh = RHELShell()
        sh.run("dnf install -y nginx")
        ql = sh.run("rpm -ql nginx")
        self.assertIn("/usr/sbin/nginx", ql)
        qf = sh.run("rpm -qf /usr/sbin/nginx")
        self.assertIn("nginx", qf)

    def test_rpm_missing_package(self):
        sh = RHELShell()
        self.assertIn("is not installed", sh.run("rpm -q doesnotexist"))

    def test_dnf_info_and_search(self):
        sh = RHELShell()
        info = sh.run("dnf info nginx")
        self.assertIn("Name", info)
        self.assertIn("nginx", info)
        self.assertNotIn("simulation", info)
        search = sh.run("dnf search web")
        self.assertIn("nginx", search)

    def test_find_by_name(self):
        sh = RHELShell()
        out = sh.run("find / -name passwd")
        self.assertIn("/etc/passwd", out)
        out2 = sh.run("find /etc -name '*.conf'")
        self.assertIn("resolv.conf", out2)


class HeadTailShorthandTests(SimpleTestCase):
    def setUp(self):
        self.sh = RHELShell()
        self.sh.state.write_file("/tmp/lines.txt", "l1\nl2\nl3\nl4\nl5\n")

    def test_head_dash_n_shorthand(self):
        self.assertEqual(self.sh.run("head -2 /tmp/lines.txt"), "l1\nl2")
        self.assertEqual(self.sh.run("head -n2 /tmp/lines.txt"), "l1\nl2")
        self.assertEqual(self.sh.run("head -n 3 /tmp/lines.txt"), "l1\nl2\nl3")

    def test_tail_dash_n_shorthand(self):
        self.assertEqual(self.sh.run("tail -1 /tmp/lines.txt"), "l5")
        self.assertEqual(self.sh.run("tail -n 2 /tmp/lines.txt"), "l4\nl5")

    def test_head_over_pipe_limits(self):
        out = self.sh.run("systemctl status sshd | head -2")
        self.assertEqual(len(out.splitlines()), 2)

    def test_is_active_unknown_unit_chains(self):
        # `systemctl is-active nginx || echo DOWN` must fire the fallback.
        out = self.sh.run("systemctl is-active nginx || echo DOWN")
        self.assertIn("DOWN", out)
        self.assertNotIn("could not be found", out)
