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
    """Run scenario-specific fix commands against the simulation engine."""
    engine = _engine_for_session(session)
    if not engine:
        return False, "no simulation session"

    slug = (session.scenario.slug or "").lower()
    shell = engine.shell
    state = shell.state

    try:
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

        if "crashloop" in slug or ("k8s" in slug and "pod" in slug):
            shell.run("kubectl rollout restart deployment/nginx")
            return True, "k8s pods fixed"

        if "k8s" in slug or "kubernetes" in slug:
            shell.run("kubectl rollout restart deployment/nginx")
            return True, "k8s fixed"

        if "ipmi" in slug or "baremetal" in slug or "vmware" in slug:
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
            shell.run("vgextend rhel /dev/sdb")
            return True, "storage disk provisioned"

        if "network-nic" in slug:
            apply_team_ops_action(engine, "network_nic_added", slug)
            return True, "network nic provisioned"

        return False, f"no simulation fix map for {slug}"
    except Exception as exc:
        return False, str(exc)[:200]
