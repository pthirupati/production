"""Scenario-specific broken states applied to RHELOSState."""

from __future__ import annotations

from .rhel_os import RHELOSState, SimUser


def apply_scenario_preset(slug: str, state: RHELOSState) -> None:
    """Configure simulated OS to match scenario slug."""
    preset = _PRESETS.get(slug)
    if preset:
        preset(state)
        return
    if "nginx" in slug:
        _preset_broken_nginx(state)
    elif "useradd" in slug or "user" in slug:
        _preset_broken_useradd(state)
    elif "gpu" in slug or "nvidia" in slug:
        _preset_gpu_fallen_off(state)
    elif "ansible" in slug:
        _preset_ansible_control(state)
    elif "boot" in slug or "grub" in slug:
        _preset_boot_issue(state)


def _preset_broken_nginx(state: RHELOSState) -> None:
    state._mkdir("/etc/nginx")
    state._mkdir("/etc/nginx/sites-enabled")
    state._write_file(
        "/etc/nginx/nginx.conf",
        "user nginx;\nworker_processes auto;\ninclude /etc/nginx/sites-enabled/*;\n",
    )
    state._write_file(
        "/etc/nginx/sites-enabled/default",
        "server {\n    listn 80;\n    server_name localhost;\n    root /var/www/html;\n}\n",
    )
    state.services["nginx"].active = "failed"
    state.services["nginx"].sub_state = "failed"


def _preset_broken_useradd(state: RHELOSState) -> None:
    state._write_file(
        "/etc/passwd",
        "root:x:0:0:root:/root:/bin/bash\ncorrupt::99999:99999:bad:/bad:/bin/bash\n",
        mode="600",
    )
    state._write_file("/etc/group", "root:x:0:\n", mode="600")
    state._write_file("/etc/shadow", "root:*:19000:0:99999:7:::\n", mode="644")


def _preset_gpu_fallen_off(state: RHELOSState) -> None:
    state.dmesg_extra = [
        "[  412.331] NVRM: GPU at 0000:01:00.0 has fallen off the bus.",
        "[  412.332] NVRM: GPU 0000:01:00.0: RmInitAdapter failed! (0x26:0x65:0x1)",
    ]
    state.gpu_healthy = False


def _preset_ansible_control(state: RHELOSState) -> None:
    state.hostname = "ansible-control"
    state.current_user = "ansible"
    state.cwd = "/home/ansible"
    if "ansible" not in state.users:
        state.users["ansible"] = SimUser("ansible", 1001, 1001, "/home/ansible", "/bin/bash", "ansible")
    state._mkdir("/home/ansible")
    state._mkdir("/home/ansible/inventory")
    state._write_file(
        "/home/ansible/inventory/hosts",
        "[webservers]\nweb1 ansible_host=10.0.0.11\nweb2 ansible_host=10.0.0.12\n",
    )
    state._mkdir("/etc/ansible")
    state._write_file("/etc/ansible/hosts", "[webservers]\nweb1\nweb2\n")


def _preset_boot_issue(state: RHELOSState) -> None:
    state._write_file("/etc/default/grub", 'GRUB_CMDLINE_LINUX="crashkernel=auto rhgb quiet"\n')


def _preset_dual_host_db(state: RHELOSState) -> None:
    from .rhel_os import SimService

    state._mkdir("/var/lib/mysql")
    state.services["mysqld"] = SimService(
        "mysqld", active="inactive", enabled="enabled", description="MySQL Server",
    )
    state._write_file("/etc/my.cnf", "[mysqld]\nbind-address=127.0.0.1\n")


_PRESETS: dict[str, callable] = {
    "broken-nginx": _preset_broken_nginx,
    "sim-broken-nginx": _preset_broken_nginx,
    "sim-rhel-broken-nginx": _preset_broken_nginx,
    "broken-useradd-sim": _preset_broken_useradd,
    "sim-rhel-broken-useradd": _preset_broken_useradd,
    "rhel-boot-grub-rescue": _preset_boot_issue,
    "sim-rhel-boot-grub": _preset_boot_issue,
    "gpu-nvidia-fallen-off-bus": _preset_gpu_fallen_off,
    "sim-rhel-gpu-fallen-off": _preset_gpu_fallen_off,
    "ansible-ssh-key-failure": _preset_ansible_control,
    "sim-rhel-ansible-ssh": _preset_ansible_control,
    "sim-rhel-dual-host-mysql": _preset_dual_host_db,
}
