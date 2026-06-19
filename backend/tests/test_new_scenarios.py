"""Integrity proof for the newly-added simulation scenarios.

For every new scenario this test:
  1. builds the engine the real way — RHELShell(scenario_slug=<slug>) — which
     applies the scenario's broken preset,
  2. asserts the scenario's shipped check.sh FAILS validation before any fix
     (fail-closed: a fresh broken lab must never pass),
  3. applies the canonical fix via real shell commands (the same commands
     scripts/e2e_simulation_fix.py runs),
  4. asserts the same check.sh now PASSES.

This is the integrity guarantee: clicking "Check Solution" can only succeed
after a genuine fix.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_shell import RHELShell
from apps.labs.provisioner.simulation.validation import (
    is_trivial_validation_script,
    validate_simulation_state,
)

SCENARIOS_ROOT = Path(settings.BASE_DIR).parent / "scenarios"

# slug -> (relative scenario dir, [canonical fix commands])
NEW_SCENARIOS: dict[str, tuple[str, list[str]]] = {
    "linux-selinux-httpd-port-denied": (
        "linux/linux-selinux-httpd-port-denied",
        ["semanage port -a -t http_port_t -p tcp 8080", "systemctl start nginx"],
    ),
    "linux-disk-missing-rescan-fs": (
        "linux/linux-disk-missing-rescan-fs",
        [
            'echo "- - -" > /sys/class/scsi_host/host0/scan',
            "mkfs.xfs /dev/sdc",
            "mkdir -p /data",
            "mount /dev/sdc /data",
            'echo "/dev/sdc /data xfs defaults 0 0" >> /etc/fstab',
        ],
    ),
    "linux-swap-not-active": (
        "linux/linux-swap-not-active",
        [
            "mkswap /dev/sdc",
            "swapon /dev/sdc",
            'echo "/dev/sdc none swap sw 0 0" >> /etc/fstab',
        ],
    ),
    "linux-lvm-create-mount": (
        "linux/linux-lvm-create-mount",
        [
            "pvcreate /dev/sdc",
            "vgcreate vgdata /dev/sdc",
            "lvcreate -L 10G -n lvdata vgdata",
            "mkfs.xfs /dev/vgdata/lvdata",
            "mkdir -p /data",
            "mount /dev/vgdata/lvdata /data",
            'echo "/dev/vgdata/lvdata /data xfs defaults 0 0" >> /etc/fstab',
        ],
    ),
    "linux-default-gateway-missing": (
        "linux/linux-default-gateway-missing",
        [
            "ip route add default via 10.0.0.1 dev eth0",
            'echo "GATEWAY=10.0.0.1" >> /etc/sysconfig/network',
        ],
    ),
    "linux-sysctl-ip-forward": (
        "linux/linux-sysctl-ip-forward",
        ['echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-ipforward.conf'],
    ),
    "linux-kernel-module-not-loaded": (
        "linux/linux-kernel-module-not-loaded",
        [
            "modprobe br_netfilter",
            'echo "br_netfilter" > /etc/modules-load.d/k8s.conf',
        ],
    ),
    "db-postgres-max-connections": (
        "database/db-postgres-max-connections",
        [
            "sed -i 's/max_connections = 20/max_connections = 200/' "
            "/var/lib/pgsql/data/postgresql.conf",
            "systemctl restart postgresql",
        ],
    ),
    "db-mysql-table-crashed": (
        "database/db-mysql-table-crashed",
        ["rm -f /var/lib/mysql/appdb/orders.CRASHED", "systemctl restart mysqld"],
    ),
    "db-postgres-disk-full-archive": (
        "database/db-postgres-disk-full-archive",
        ["rm -rf /var/lib/pgsql/archive", "systemctl start postgresql"],
    ),
}


def _load_check(rel_dir: str) -> str:
    return (SCENARIOS_ROOT / rel_dir / "check.sh").read_text()


class NewScenarioIntegrityTests(SimpleTestCase):
    def test_check_scripts_are_non_trivial(self):
        """Every shipped check.sh must perform real validation (not auto-pass)."""
        for slug, (rel_dir, _) in NEW_SCENARIOS.items():
            script = _load_check(rel_dir)
            self.assertFalse(
                is_trivial_validation_script(script),
                f"{slug}: check.sh is trivial and would auto-pass",
            )

    def test_each_scenario_fails_before_fix_and_passes_after(self):
        for slug, (rel_dir, fix_cmds) in NEW_SCENARIOS.items():
            with self.subTest(slug=slug):
                script = _load_check(rel_dir)

                # Built the real way: the preset applies the broken state.
                shell = RHELShell(scenario_slug=slug)
                before_ok, before_msg = validate_simulation_state(shell.state, script)
                self.assertFalse(
                    before_ok,
                    f"{slug}: validation passed BEFORE any fix ({before_msg})",
                )

                # Apply the canonical fix via real shell commands.
                for cmd in fix_cmds:
                    shell.run(cmd)

                after_ok, after_msg = validate_simulation_state(shell.state, script)
                self.assertTrue(
                    after_ok,
                    f"{slug}: validation still FAILS after the fix ({after_msg})",
                )

    def test_partial_fix_does_not_pass(self):
        """A representative spot-check: starting the DB without the real repair
        must NOT pass — guarding against 'restart-only' shortcuts."""
        # postgres max_connections: starting the service without raising the
        # limit must still fail.
        shell = RHELShell(scenario_slug="db-postgres-max-connections")
        script = _load_check("database/db-postgres-max-connections")
        shell.run("systemctl start postgresql")
        ok, _ = validate_simulation_state(shell.state, script)
        self.assertFalse(ok, "postgres passed with a restart but no config change")

        # mysql crashed table: restarting without clearing the crash marker fails.
        shell = RHELShell(scenario_slug="db-mysql-table-crashed")
        script = _load_check("database/db-mysql-table-crashed")
        shell.run("systemctl start mysqld")
        ok, _ = validate_simulation_state(shell.state, script)
        self.assertFalse(ok, "mysql passed with a restart but the table still crashed")
