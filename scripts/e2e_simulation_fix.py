"""Apply in-memory fixes to simulation labs for E2E validation."""
from __future__ import annotations

from apps.labs.provisioner.simulation.ops_state import apply_team_ops_action
from apps.labs.provisioner.simulation.shell import get_sim_session
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


def _engine_for_session(session) -> UnifiedSimulationEngine | None:
    entry = get_sim_session(str(session.id))
    if not entry:
        return None
    engine = entry.get("state", {}).get("engine")
    return engine if isinstance(engine, UnifiedSimulationEngine) else None


def _boot_login(engine: UnifiedSimulationEngine) -> None:
    if not engine.boot:
        return
    if engine.boot.phase in ("grub", "grub_rescue", "mbr", "initramfs", "panic", "booting"):
        engine._handle_boot("")
    if engine.boot.phase == "login":
        engine._handle_boot("root")
    if engine.boot.phase == "password_wait":
        engine._handle_boot("redhat")


def _fix_boot_issue(engine: UnifiedSimulationEngine, slug: str) -> None:
    boot = engine.boot
    if not boot:
        return
    if "initramfs" in slug or "dracut" in slug:
        engine._handle_boot("dracut -f")
    elif "kernel-panic" in slug or ("kernel" in slug and "panic" in slug):
        engine._handle_boot("dracut -f")
        boot.kernel_fixed = True
        engine.shell.state.kernel_fixed = True
    elif "mbr" in slug:
        engine._handle_boot("grub2-install /dev/sda")
        boot.mbr_fixed = True
        engine.shell.state.mbr_fixed = True
    elif "grub-rescue" in slug or ("grub" in slug and "rescue" in slug):
        engine._handle_boot("grub2-install /dev/sda")
        engine._handle_boot("grub2-mkconfig -o /boot/grub2/grub.cfg")
        boot.grub_fixed = True
        engine.shell.state.grub_fixed = True
    elif "grub" in slug or "boot" in slug:
        engine._handle_boot("grub2-mkconfig -o /boot/grub2/grub.cfg")
        boot.grub_fixed = True
        engine.shell.state.grub_fixed = True
    _boot_login(engine)


def apply_simulation_fix(session) -> tuple[bool, str]:
    """Run the scenario fix, then persist the engine so cross-worker validation
    (which may restore the engine from LabSession.simulation_snapshot) sees the
    repaired state instead of the stale pre-fix snapshot."""
    result = _apply_simulation_fix(session)
    try:
        if result and result[0]:
            from apps.labs.provisioner.simulation.sim_persistence import persist_session_snapshot
            persist_session_snapshot(str(session.id))
    except Exception:
        pass
    return result


def _apply_simulation_fix(session) -> tuple[bool, str]:
    """Run scenario-specific fix commands against the simulation engine."""
    engine = _engine_for_session(session)
    if not engine:
        return False, "no simulation session"

    slug = (session.scenario.slug or "").lower()
    shell = engine.shell
    state = shell.state

    try:
        # ── New high-value scenarios (matched before generic substrings) ──
        if "selinux-httpd-port-denied" in slug:
            # Label the custom port with SELinux, keep Enforcing, then start nginx.
            shell.run("semanage port -a -t http_port_t -p tcp 8080")
            shell.run("systemctl start nginx")
            return True, "selinux port labelled and nginx started"

        if "disk-missing-rescan-fs" in slug:
            shell.run('echo "- - -" > /sys/class/scsi_host/host0/scan')
            shell.run("mkfs.xfs /dev/sdc")
            shell.run("mkdir -p /data")
            shell.run("mount /dev/sdc /data")
            shell.run('echo "/dev/sdc /data xfs defaults 0 0" >> /etc/fstab')
            return True, "disk rescanned, formatted, mounted, persisted"

        if "swap-not-active" in slug:
            shell.run("mkswap /dev/sdc")
            shell.run("swapon /dev/sdc")
            shell.run('echo "/dev/sdc none swap sw 0 0" >> /etc/fstab')
            return True, "swap activated and persisted"

        if "lvm-create-mount" in slug:
            shell.run("pvcreate /dev/sdc")
            shell.run("vgcreate vgdata /dev/sdc")
            shell.run("lvcreate -L 10G -n lvdata vgdata")
            shell.run("mkfs.xfs /dev/vgdata/lvdata")
            shell.run("mkdir -p /data")
            shell.run("mount /dev/vgdata/lvdata /data")
            shell.run('echo "/dev/vgdata/lvdata /data xfs defaults 0 0" >> /etc/fstab')
            return True, "lvm provisioned and mounted at /data"

        if "default-gateway-missing" in slug:
            shell.run("ip route add default via 10.0.0.1 dev eth0")
            shell.run('echo "GATEWAY=10.0.0.1" >> /etc/sysconfig/network')
            return True, "default gateway configured and persisted"

        if "sysctl-ip-forward" in slug:
            shell.run('echo "net.ipv4.ip_forward = 1" > /etc/sysctl.d/99-ipforward.conf')
            return True, "ip_forward enabled persistently"

        if "kernel-module-not-loaded" in slug:
            shell.run("modprobe br_netfilter")
            shell.run('echo "br_netfilter" > /etc/modules-load.d/k8s.conf')
            return True, "kernel module load made persistent"

        if "db-postgres-max-connections" in slug:
            shell.run(
                "sed -i 's/max_connections = 20/max_connections = 200/' "
                "/var/lib/pgsql/data/postgresql.conf"
            )
            shell.run("systemctl restart postgresql")
            return True, "max_connections raised and postgresql restarted"

        if "db-mysql-table-crashed" in slug:
            # Repairing the MyISAM table clears the crashed marker.
            shell.run("rm -f /var/lib/mysql/appdb/orders.CRASHED")
            shell.run("systemctl restart mysqld")
            return True, "crashed table repaired and mysqld restarted"

        if "db-postgres-disk-full-archive" in slug:
            # Reclaim disk by clearing the already-archived WAL backlog, then start.
            shell.run("rm -rf /var/lib/pgsql/archive")
            shell.run("systemctl start postgresql")
            return True, "disk reclaimed and postgresql started"

        if "patch" in slug:
            state.ops_backup_taken = True
            state.ops_db_stopped = True
            state.ops_app_stopped = True
            shell.run("bash /opt/fixitlab/precheck.sh")
            shell.run("dnf update -y")
            engine._reboot_from_shell()
            shell.run("mount -a")
            state.mount_filesystems_fixed = True
            state.ops_services_restarted = True
            _boot_login(engine)
            post = shell.run("bash /opt/fixitlab/postcheck.sh")
            if "PASSED" not in post:
                return False, post[:200]
            return True, "patching fixed"

        if "nginx" in slug and "root" in slug:
            sites = state.read_file("/etc/nginx/sites-enabled/default") or ""
            if "/var/www/wrong" in sites:
                state._write_file(
                    "/etc/nginx/sites-enabled/default",
                    sites.replace("/var/www/wrong", "/var/www/html"),
                )
            return True, "nginx root fixed"

        if "nginx" in slug:
            shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
            shell.run("systemctl start nginx")
            return True, "nginx fixed"

        if "useradd" in slug:
            shell.run(
                "sed -i 's/corrupt::99999:99999:bad:\\/bad:\\/bin\\/bash//' /etc/passwd"
            )
            shell.run("useradd -m appuser")
            return True, "useradd fixed"

        if "gpu" in slug or "nvidia" in slug:
            shell.run("modprobe nvidia")
            state.gpu_healthy = True
            return True, "gpu fixed"

        if "initramfs" in slug or "dracut" in slug or "kernel-panic" in slug:
            _fix_boot_issue(engine, slug)
            return True, "boot issue fixed"

        if "grub" in slug or "mbr" in slug or "boot" in slug:
            _fix_boot_issue(engine, slug)
            return True, "grub fixed"

        if "ansible" in slug:
            shell.run("ssh-copy-id root@web1")
            shell.run("ssh-copy-id root@web2")
            return True, "ssh key fixed"

        if "ssh-stop" in slug or "sshd-down" in slug:
            shell.run("systemctl start sshd")
            return True, "sshd started"

        if "firewalld" in slug:
            shell.run("firewall-cmd --permanent --add-service=http")
            shell.run("firewall-cmd --reload")
            return True, "firewall fixed"

        if "mysql-dual" in slug:
            shell.run("systemctl start mysqld")
            return True, "mysqld started"

        if "mysql" in slug:
            shell.run("systemctl start mysqld")
            return True, "mysqld started"

        if "postgres" in slug:
            shell.run("systemctl start postgresql")
            return True, "postgresql started"

        if "docker" in slug:
            if "daemon-stopped" in slug or "stopped" in slug:
                shell.run("systemctl start docker")
            elif "exited" in slug or "container" in slug:
                shell.run("docker start web")
            elif "pull" in slug:
                shell.run("docker pull nginx:latest")
            elif "network" in slug:
                shell.run("docker network connect bridge web")
                engine._docker_network_fixed = True
            elif "compose" in slug:
                shell.run("docker compose up -d")
            else:
                shell.run("docker start web")
            engine._container_running = True
            docker_svc = state.services.get("docker")
            if docker_svc:
                docker_svc.active = "active"
                docker_svc.sub_state = "running"
            return True, "docker fixed"

        if "endpoint" in slug or "service-not-ready" in slug:
            shell.run("kubectl patch service api -p '{\"spec\":{\"selector\":{\"app\":\"api\"}}}'")
            return True, "k8s endpoints fixed"

        sim_type = getattr(session.scenario, "simulation_type", "") or ""
        if sim_type == "vmware" or "vmware" in slug:
            from e2e_vmware_fix import apply_vmware_simulation_fix
            return apply_vmware_simulation_fix(session)

        if "crashloop" in slug or ("k8s" in slug and "pod" in slug):
            shell.run("kubectl rollout restart deployment/nginx")
            return True, "k8s pods fixed"

        if "node-notready" in slug:
            shell.run("kubectl uncordon worker-1")
            return True, "k8s node fixed"

        if "configmap" in slug:
            shell.run("kubectl create configmap app-config --from-literal=key=value")
            return True, "k8s configmap fixed"

        if "imagepull" in slug or "image-pull" in slug:
            shell.run("kubectl set image deployment/api api=api:v1")
            return True, "k8s image pull fixed"

        if "rbac" in slug:
            shell.run("kubectl create rolebinding fix --clusterrole=edit --serviceaccount=default:default")
            return True, "k8s rbac fixed"

        if "k8s" in slug or "kubernetes" in slug:
            shell.run("kubectl rollout restart deployment/nginx")
            return True, "k8s fixed"

        if "ipmi" in slug or "baremetal" in slug:
            shell.run("ipmitool power on")
            engine._power_state = "on"
            return True, "power on"

        if "pip" in slug and "python" in slug:
            state._mkdir("/opt/app")
            state._write_file("/opt/app/main.py", 'import requests\nprint("ok")\n')
            return True, "python deps fixed"

        if "python" in slug:
            state._mkdir("/opt/app")
            state._write_file("/opt/app/main.py", 'print("hello")\n')
            return True, "python syntax fixed"

        if "bash" in slug or "unbound" in slug:
            state._mkdir("/opt/scripts")
            state._write_file(
                "/opt/scripts/deploy.sh",
                "#!/bin/bash\nset -u\n: ${VAR:-}\n",
            )
            return True, "bash script fixed"

        if "lvm" in slug:
            apply_team_ops_action(engine, "storage_disk_added", slug)
            shell.run("pvcreate /dev/sdb")
            # Extend whichever VG this scenario actually uses (rhel, fixitlab, …)
            # instead of assuming "rhel" — otherwise vgextend no-ops and the PV
            # never joins a VG (e.g. lvm-add-pv-extend uses the "fixitlab" VG).
            vgs = list(getattr(getattr(state, "lvm", None), "vgs", {}) or {})
            for vg in (vgs or ["rhel"]):
                shell.run(f"vgextend {vg} /dev/sdb")
            for vg in (vgs or ["rhel"]):
                shell.run(f"lvextend -r -l +100%FREE /dev/{vg}/datalv")
            return True, "storage disk provisioned"

        if "network-nic" in slug:
            apply_team_ops_action(engine, "network_nic_added", slug)
            return True, "network nic provisioned"

        if "readonly" in slug or ("fs" in slug and "fix" in slug):
            shell.run("mount -o remount,rw /")
            state.mount_filesystems_fixed = True
            return True, "readonly fs remounted rw"

        if "remount" in slug:
            shell.run("mount -o remount,rw /")
            state.mount_filesystems_fixed = True
            return True, "fs remounted"

        if "ldconfig" in slug or "missing-library" in slug:
            state._mkdir("/etc/ld.so.conf.d")
            state._write_file("/etc/ld.so.conf.d/fixitlab.conf", "/usr/local/lib\n")
            state.ldconfig_updated = True
            state.myapp_working = True
            return True, "ldconfig conf restored"

        if "terraform" in slug or any(w in slug for w in (
            "aws-", "cloudwatch", "lambda", "s3-", "eks", "iam-", "ec2-", "elb",
            "ecr", "rds", "vpc", "kinesis", "sqs", "cloudfront", "secrets-manager",
        )):
            state.terraform_fixed = True
            return True, "terraform/aws issue resolved"

        if any(w in slug for w in (
            "windows", "win-", "iis", "hyper-v", "kerberos", "gpo", "ntfs", "smb-",
            "winrm", "wmi", "sql-server", "dhcp-", "replication-", "dns-zone",
            "ad-user", "certificate-enrollment", "file-server", "gpo-not",
            "print-spooler", "remote-desktop", "service-dependency", "windows-update",
        )):
            state.windows_fixed = True
            return True, "windows issue resolved"

        return False, f"no simulation fix map for {slug}"
    except Exception as exc:
        return False, str(exc)[:200]
