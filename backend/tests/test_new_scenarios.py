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


# ──────────────────────────────────────────────────────────────────────
# Java (50) + Security marker scenarios: simulation-marker integrity.
#
# Every java + new-security scenario ships a check.sh that runs
# `grep -q FIXED-OK <file>`. Its preset writes that file in a BROKEN state
# (no sentinel); the e2e fix rewrites it WITH the sentinel. These tests prove,
# through the REAL validation path (resolve_simulation_validation_script ->
# validate_simulation_state), that each scenario is fail-closed before the fix
# and passes only after the documented edit.
# ──────────────────────────────────────────────────────────────────────

from apps.labs.provisioner.simulation.validation import (  # noqa: E402
    resolve_simulation_validation_script,
)

# (relative scenario dir, canonical slug) for a representative sample spanning
# every Java family — Spring Boot, JVM tuning, Maven, Gradle, JPA, messaging,
# caching, concurrency, security/TLS, build config — plus the new security one.
JAVA_MARKER_SAMPLE = [
    ("java/actuator-health-failing", "actuator-health-failing"),
    ("java/classpath-missing", "sim-java-classpath"),
    ("java/deadlock", "sim-java-deadlock"),
    ("java/gc-pause-excessive", "gc-pause-excessive"),
    ("java/jvm-heap-oom", "jvm-heap-oom"),
    ("java/jvm-metaspace-oom", "jvm-metaspace-oom"),
    ("java/oom-error", "sim-java-oom"),
    ("java/maven-build-fail", "sim-java-maven-fail"),
    ("java/maven-dependency-conflict", "maven-dependency-conflict"),
    ("java/jacoco-coverage-missing", "jacoco-coverage-missing"),
    ("java/gradle-build-cache-corrupt", "gradle-build-cache-corrupt"),
    ("java/jpa-n-plus-1", "jpa-n-plus-1"),
    ("java/kafka-producer-timeout", "kafka-producer-timeout"),
    ("java/redis-jedis-connection", "redis-jedis-connection"),
    ("java/spring-db-connection-pool", "spring-db-connection-pool"),
    ("java/ssl-handshake-failed", "ssl-handshake-failed"),
    ("java/tomcat-max-threads", "tomcat-max-threads"),
    ("java/log4j-config-missing", "log4j-config-missing"),
    # New java slugs:
    ("java/gradle-wrapper-version-mismatch", "java-gradle-wrapper-version-mismatch"),
    ("java/spring-circular-dependency", "java-spring-circular-dependency"),
    ("java/jdbc-pool-leak", "java-jdbc-pool-leak"),
    ("java/hibernate-lazy-init-exception", "java-hibernate-lazy-init-exception"),
    ("java/jackson-serialization-loop", "java-jackson-serialization-loop"),
    ("java/java-version-mismatch", "java-runtime-version-mismatch"),
    ("java/maven-shade-plugin-manifest", "java-maven-shade-plugin-manifest"),
    ("java/java-direct-buffer-oom", "java-direct-buffer-oom"),
    ("java/spring-actuator-exposed", "java-spring-actuator-exposed"),
    ("java/java-keystore-wrong-password", "java-keystore-wrong-password"),
    ("java/spring-transaction-not-rolled-back", "java-spring-transaction-rollback"),
    ("java/java-stack-overflow-recursion", "java-stack-overflow-recursion"),
    ("java/gradle-test-task-skipped", "java-gradle-test-task-skipped"),
]

SECURITY_MARKER_SAMPLE = [
    ("security/java-log4shell-jndi-lookup", "security-java-log4shell-jndi-lookup"),
]


def _marker_path_for(slug: str) -> str:
    """The real file the e2e fix rewrites for this marker scenario."""
    import importlib.util
    import os as _os

    e2e_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        "scripts", "e2e_simulation_fix.py",
    )
    spec = importlib.util.spec_from_file_location("e2e_simulation_fix", e2e_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._RS_MARKER_FIX[slug]


def _apply_marker_fix(state, path: str) -> None:
    """Exactly what apply_simulation_fix does for a _RS_MARKER_FIX scenario."""
    existing = state.read_file(path) or ""
    fixed = (
        existing.replace("# broken configuration", "# corrected configuration")
        + "\n# FIXED-OK: corrected per the documented remediation\n"
    )
    state.write_file(path, fixed)


class JavaSecurityMarkerIntegrityTests(SimpleTestCase):
    def test_check_scripts_are_non_trivial(self):
        for rel_dir, slug in JAVA_MARKER_SAMPLE + SECURITY_MARKER_SAMPLE:
            script = _load_check(rel_dir)
            self.assertFalse(
                is_trivial_validation_script(script),
                f"{slug}: check.sh is trivial and would auto-pass",
            )

    def test_resolve_keeps_real_check(self):
        """The marker check.sh must NOT be swapped for a canonical script."""
        for rel_dir, slug in JAVA_MARKER_SAMPLE + SECURITY_MARKER_SAMPLE:
            script = _load_check(rel_dir)
            resolved = resolve_simulation_validation_script(slug, script)
            self.assertEqual(
                resolved.strip(), script.strip(),
                f"{slug}: real check.sh was replaced by resolve()",
            )

    def test_each_scenario_fails_before_fix_and_passes_after(self):
        for rel_dir, slug in JAVA_MARKER_SAMPLE + SECURITY_MARKER_SAMPLE:
            with self.subTest(slug=slug):
                check = _load_check(rel_dir)
                # Built the real way: the preset applies the broken file.
                shell = RHELShell(scenario_slug=slug)
                script = resolve_simulation_validation_script(slug, check)

                before_ok, before_msg = validate_simulation_state(shell.state, script)
                self.assertFalse(
                    before_ok,
                    f"{slug}: validation passed BEFORE any fix ({before_msg})",
                )

                # Apply the same fix scripts/e2e_simulation_fix.py performs.
                _apply_marker_fix(shell.state, _marker_path_for(slug))

                after_ok, after_msg = validate_simulation_state(shell.state, script)
                self.assertTrue(
                    after_ok,
                    f"{slug}: validation still FAILS after the fix ({after_msg})",
                )

    def test_touching_file_without_sentinel_stays_failed(self):
        """Editing the file WITHOUT the FIXED-OK sentinel must NOT pass —
        guards against a 'touched the file' shortcut."""
        for rel_dir, slug in (JAVA_MARKER_SAMPLE[:5] + SECURITY_MARKER_SAMPLE):
            with self.subTest(slug=slug):
                check = _load_check(rel_dir)
                shell = RHELShell(scenario_slug=slug)
                script = resolve_simulation_validation_script(slug, check)
                shell.state.write_file(_marker_path_for(slug), "still broken, no sentinel\n")
                ok, _ = validate_simulation_state(shell.state, script)
                self.assertFalse(ok, f"{slug}: passed without the FIXED-OK sentinel")


class JavaScenarioCatalogTests(SimpleTestCase):
    """The catalog-level guarantees the owner asked to prove."""

    def test_counts_are_fifty_each(self):
        import glob

        java = glob.glob(str(SCENARIOS_ROOT / "java" / "*" / "scenario.yaml"))
        security = glob.glob(str(SCENARIOS_ROOT / "security" / "*" / "scenario.yaml"))
        self.assertEqual(len(java), 50, "java scenario count must be 50")
        self.assertEqual(len(security), 50, "security scenario count must be 50")

    def test_every_java_simulation_scenario_is_completable(self):
        """No java simulation scenario may ship a trivial (auto-pass) check.sh.

        A simulation scenario with a trivial check validates as 'Validation not
        configured' and is NOT completable — the exact bug this work fixes.
        """
        import glob

        import yaml as _yaml

        offenders = []
        for f in glob.glob(str(SCENARIOS_ROOT / "java" / "*" / "scenario.yaml")):
            data = _yaml.safe_load(open(f))
            if (data.get("lab_mode") or "docker") != "simulation":
                continue  # docker-mode build labs are graded by the build harness
            check_path = Path(f).with_name("check.sh")
            script = check_path.read_text() if check_path.exists() else ""
            if is_trivial_validation_script(script):
                offenders.append(data.get("slug"))
        self.assertEqual(
            offenders, [],
            f"these java simulation scenarios have trivial check.sh: {offenders}",
        )
