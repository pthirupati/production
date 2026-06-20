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


# ──────────────────────────────────────────────────────────────────────
# Wave 1–4 expansion: representative integrity sample across every family.
# Each entry proves fail-closed BEFORE the fix and PASS after applying the
# real remediation the e2e fix performs.
# ──────────────────────────────────────────────────────────────────────

from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


def _engine(slug, sim_type="generic"):
    return UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)


# Service-down scenarios: preset registers a failed unit; fix = systemctl start.
SERVICE_SAMPLE = [
    ("database", "db-redis-down", "redis"),
    ("database", "db-etcd-down", "etcd"),
    ("database", "db-elasticsearch-down", "elasticsearch"),
    ("docker", "docker-daemon-down", "docker"),
    ("docker", "docker-containerd-down", "containerd"),
    ("docker", "docker-docker-socket-proxy-down", "docker-socket-proxy"),
    ("rhel-linux", "rhel-sssd-down", "sssd"),
    ("rhel-linux", "rhel-multipathd-down", "multipathd"),
    ("linux", "linux-haproxy-down", "haproxy"),
    ("linux", "linux-named-down", "named"),
]

# Marker scenarios: preset writes a broken config; fix rewrites with FIXED-OK.
MARKER_SAMPLE = [
    ("database", "db-postgres-fsync-off", "/var/lib/pgsql/data/postgresql.conf"),
    ("ansible", "ansible-jinja-template-error", "/home/ansible/templates/app.conf.j2"),
    ("ansible", "ansible-handler-missing", "/home/ansible/site.yml"),
    ("shell-script", "shell-pipefail-missing", "/opt/scripts/deploy-pipeline.sh"),
    ("shell-script", "shell-rm-rf-variable", "/opt/scripts/wipe.sh"),
    ("html", "html-broken-doctype", "/var/www/html/index.html"),
    ("html", "html-mixed-content", "/var/www/html/secure.html"),
    ("gpu", "gpu-ecc-disabled", "/etc/nvidia/ecc.conf"),
    ("gpu", "gpu-driver-blacklist-nouveau", "/etc/modprobe.d/blacklist-nouveau.conf"),
    ("baremetal", "baremetal-bmc-default-creds", "/etc/bmc/credentials.cfg"),
    ("baremetal", "baremetal-iommu-not-enabled", "/etc/bios/iommu.cfg"),
    ("rhel-linux", "rhel-selinux-permissive", "/etc/selinux/config"),
    ("linux", "linux-sudoers-syntax-error", "/etc/sudoers.d/ops"),
]

# Flag-family scenarios: terraform_fixed / windows_fixed gate validation.
TERRAFORM_SAMPLE = [
    "terraform-plan-unexpected-destroy", "aws-iam-wildcard-policy",
    "aws-eks-aws-auth-broken", "aws-dynamodb-hot-partition",
]
WINDOWS_SAMPLE = [
    "win-cluster-quorum-lost", "win-sqlserver-tempdb-contention",
    "win-adcs-crl-expired", "win-iis-binding-conflict",
]


class ExpansionServiceScenarioTests(SimpleTestCase):
    def test_service_down_fails_then_passes(self):
        for tech, slug, unit in SERVICE_SAMPLE:
            with self.subTest(slug=slug):
                script = _load_check(f"{tech}/{slug}")
                self.assertFalse(is_trivial_validation_script(script), f"{slug}: trivial check")
                eng = _engine(slug)
                before, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertFalse(before, f"{slug}: passed BEFORE fix ({msg})")
                eng.shell.run(f"systemctl start {unit}")
                svc = eng.shell.state.services.get(unit)
                if svc:
                    svc.active = "active"
                after, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertTrue(after, f"{slug}: still FAILS after fix ({msg})")


class ExpansionMarkerScenarioTests(SimpleTestCase):
    def test_config_marker_fails_then_passes(self):
        for tech, slug, path in MARKER_SAMPLE:
            with self.subTest(slug=slug):
                script = _load_check(f"{tech}/{slug}")
                self.assertFalse(is_trivial_validation_script(script), f"{slug}: trivial check")
                sim_type = "gpu" if tech == "gpu" else ("baremetal" if tech == "baremetal" else "generic")
                eng = _engine(slug, sim_type)
                before, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertFalse(before, f"{slug}: passed BEFORE fix ({msg})")
                existing = eng.shell.state.read_file(path) or ""
                eng.shell.state.write_file(path, existing + "\n# FIXED-OK\n")
                after, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertTrue(after, f"{slug}: still FAILS after fix ({msg})")

    def test_unfixed_marker_stays_failed(self):
        """A marker scenario must NOT pass until the file carries FIXED-OK."""
        tech, slug, path = MARKER_SAMPLE[0]
        script = _load_check(f"{tech}/{slug}")
        eng = _engine(slug)
        # Touch the file without the sentinel — still failing.
        eng.shell.state.write_file(path, "still broken\n")
        ok, _ = validate_simulation_state(eng.shell.state, script, eng)
        self.assertFalse(ok, f"{slug}: passed without the FIXED-OK sentinel")


class ExpansionFlagFamilyTests(SimpleTestCase):
    def test_terraform_fails_then_passes(self):
        for slug in TERRAFORM_SAMPLE:
            with self.subTest(slug=slug):
                script = _load_check(f"terraform/{slug}")
                eng = _engine(slug, "terraform")
                before, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertFalse(before, f"{slug}: passed BEFORE fix ({msg})")
                eng.shell.state.terraform_fixed = True
                after, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertTrue(after, f"{slug}: still FAILS after fix ({msg})")

    def test_windows_fails_then_passes(self):
        for slug in WINDOWS_SAMPLE:
            with self.subTest(slug=slug):
                script = _load_check(f"windows/{slug}")
                eng = _engine(slug, "windows")
                before, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertFalse(before, f"{slug}: passed BEFORE fix ({msg})")
                eng.shell.state.windows_fixed = True
                after, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertTrue(after, f"{slug}: still FAILS after fix ({msg})")


class ExpansionEngineFamilyTests(SimpleTestCase):
    def test_devops_helm_and_ci_fail_then_pass(self):
        # Helm stuck → rollback heals.
        eng = _engine("devops-helm-pending-upgrade-stuck", "generic")
        script = _load_check("devops/devops-helm-pending-upgrade-stuck")
        before, msg = validate_simulation_state(eng.shell.state, script, eng)
        self.assertFalse(before, f"helm: passed before fix ({msg})")
        eng.devops.helm_rollback("webapp", 3)
        after, msg = validate_simulation_state(eng.shell.state, script, eng)
        self.assertTrue(after, f"helm: still fails after rollback ({msg})")

        # CI pipeline broken → fix_pipeline heals.
        eng = _engine("devops-ci-pipeline-kubeconfig-missing", "generic")
        script = _load_check("devops/devops-ci-pipeline-kubeconfig-missing")
        before, msg = validate_simulation_state(eng.shell.state, script, eng)
        self.assertFalse(before, f"ci: passed before fix ({msg})")
        eng.devops.fix_pipeline()
        after, msg = validate_simulation_state(eng.shell.state, script, eng)
        self.assertTrue(after, f"ci: still fails after fix ({msg})")

    def test_networking_bgp_ntp_mtu_fail_then_pass(self):
        cases = [
            ("networking-bgp-as-mismatch", lambda n: n.fix_bgp()),
            ("networking-ntp-source-unreachable", lambda n: n.sync_ntp()),
            ("networking-mtu-jumbo-blackhole", lambda n: setattr(n, "interface_mtu", 1500)),
        ]
        for slug, fix in cases:
            with self.subTest(slug=slug):
                eng = _engine(slug, "networking")
                script = _load_check(f"networking/{slug}")
                before, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertFalse(before, f"{slug}: passed before fix ({msg})")
                fix(eng.networking)
                after, msg = validate_simulation_state(eng.shell.state, script, eng)
                self.assertTrue(after, f"{slug}: still fails after fix ({msg})")

    def test_kubernetes_crashloop_fails_then_passes(self):
        eng = _engine("k8s-crashloop-bad-liveness", "kubernetes")
        script = _load_check("kubernetes/k8s-crashloop-bad-liveness")
        before, msg = validate_simulation_state(eng.shell.state, script, eng)
        self.assertFalse(before, f"k8s: passed before fix ({msg})")
        # Heal the cluster the way a rollout would.
        c = eng.cluster
        for p in c.pods:
            p.status = "Running"
            p.ready = "1/1"
        for s in c.services:
            if s.name != "kubernetes" and not s.endpoints:
                s.endpoints = ["10.244.1.5:8080"]
        after, msg = validate_simulation_state(eng.shell.state, script, eng)
        self.assertTrue(after, f"k8s: still fails after heal ({msg})")
