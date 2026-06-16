"""Apply in-memory fixes to simulation labs for E2E validation."""
from __future__ import annotations

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
    engine._handle_boot("")
    engine._handle_boot("root")
    engine._handle_boot("redhat")


def apply_simulation_fix(session) -> tuple[bool, str]:
    """Run scenario-specific fix commands against the simulation engine."""
    engine = _engine_for_session(session)
    if not engine:
        return False, "no simulation session"

    slug = (session.scenario.slug or "").lower()
    shell = engine.shell

    try:
        if "patch" in slug:
            shell.run("bash /opt/fixitlab/precheck.sh")
            shell.run("dnf update -y")
            reboot_out = engine._reboot_from_shell()
            _boot_login(engine)
            post = shell.run("bash /opt/fixitlab/postcheck.sh")
            if "PASSED" not in post:
                return False, post[:200]
            return True, (reboot_out or post)[:200]

        if "nginx" in slug:
            shell.run("sed -i 's/listn/listen/' /etc/nginx/sites-enabled/default")
            shell.run("systemctl start nginx")
            return True, "nginx fixed"

        if "useradd" in slug:
            shell.run("useradd -m appuser")
            return True, "useradd fixed"

        if "gpu" in slug or "nvidia" in slug:
            shell.run("modprobe nvidia")
            engine.state.gpu_healthy = True
            return True, "gpu fixed"

        if "grub" in slug or "mbr" in slug:
            shell.run("grub2-install /dev/sda")
            shell.run("grub2-mkconfig -o /boot/grub2/grub.cfg")
            if engine.boot:
                engine._reboot_from_shell()
                _boot_login(engine)
            return True, "grub fixed"

        if "initramfs" in slug or "dracut" in slug:
            shell.run("dracut -f")
            if engine.boot:
                engine._reboot_from_shell()
                _boot_login(engine)
            return True, "initramfs fixed"

        if "kernel-panic" in slug or ("kernel" in slug and "panic" in slug):
            shell.run("dracut -f")
            if engine.boot:
                engine._reboot_from_shell()
                _boot_login(engine)
            return True, "kernel panic fixed"

        if "ansible" in slug:
            shell.run("ssh-copy-id root@web1")
            return True, "ssh key fixed"

        if "ssh-stop" in slug or "sshd-down" in slug:
            shell.run("systemctl start sshd")
            return True, "sshd started"

        if "firewalld" in slug:
            shell.run("firewall-cmd --permanent --add-service=http")
            shell.run("firewall-cmd --reload")
            return True, "firewall fixed"

        return False, f"no simulation fix map for {slug}"
    except Exception as exc:
        return False, str(exc)[:200]
