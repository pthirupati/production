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
    elif "patch" in slug:
        _preset_patching(state)
    elif "boot" in slug or "grub" in slug:
        _preset_boot_issue(state)


def _preset_wrong_nginx_root(state: RHELOSState) -> None:
    """Nginx runs but serves wrong document root."""
    state._mkdir("/etc/nginx")
    state._mkdir("/etc/nginx/sites-enabled")
    state._mkdir("/var/www/html")
    state._mkdir("/var/www/wrong")
    state._write_file(
        "/var/www/html/index.html",
        "<html><body><h1>Correct Site</h1></body></html>\n",
    )
    state._write_file(
        "/var/www/wrong/index.html",
        "<html><body><h1>Wrong Site</h1></body></html>\n",
    )
    state._write_file(
        "/etc/nginx/nginx.conf",
        "user nginx;\nworker_processes auto;\ninclude /etc/nginx/sites-enabled/*;\n",
    )
    state._write_file(
        "/etc/nginx/sites-enabled/default",
        "server {\n    listen 80;\n    server_name localhost;\n    root /var/www/wrong;\n    index index.html;\n}\n",
    )
    state.services["nginx"].active = "active"
    state.services["nginx"].sub_state = "running"


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


def _preset_initramfs(state: RHELOSState) -> None:
    state.initramfs_fixed = False
    state.fstab_valid = False
    state._write_file("/etc/fstab", "UUID=bad-uuid / xfs defaults 0 0\n")


def _preset_mbr(state: RHELOSState) -> None:
    state.mbr_fixed = False
    state.grub_fixed = False


def _preset_kernel_panic(state: RHELOSState) -> None:
    state.kernel_fixed = False
    state._write_file("/etc/fstab", "UUID=missing / xfs defaults 0 0\n")


def _preset_mysql_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services["mysqld"] = SimService("mysqld", active="failed", enabled="enabled", description="MySQL")
    state._write_file("/etc/my.cnf", "[mysqld]\nsocket=/var/lib/mysql/mysql.sock\n")


def _preset_postgres_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services["postgresql"] = SimService("postgresql", active="failed", enabled="enabled", description="PostgreSQL")


def _preset_firewalld_blocked(state: RHELOSState) -> None:
    state._mkdir("/etc/nginx")
    state._mkdir("/etc/nginx/sites-enabled")
    state._write_file(
        "/etc/nginx/sites-enabled/default",
        "server {\n    listen 80;\n    server_name localhost;\n    root /var/www/html;\n}\n",
    )
    state.services["nginx"].active = "active"
    state.services["nginx"].sub_state = "running"
    state.firewall.runtime["public"] = {"services": ["ssh", "dhcpv6-client"], "ports": []}
    state.firewall.permanent["public"] = {"services": ["ssh", "dhcpv6-client"], "ports": []}


def _preset_patching(state: RHELOSState) -> None:
    from .boot_sequence import OLD_KERNEL
    from .ops_state import init_patching_ops

    state.kernel = OLD_KERNEL
    state.patching_done = False
    state.precheck_ran = False
    state.postcheck_ran = False
    state.rebooted_after_patch = False
    init_patching_ops(state)
    if "mysqld" not in state.services:
        from .rhel_os import SimService
        state.services["mysqld"] = SimService("mysqld", "active", "enabled", "MySQL Server")
    if "nginx" not in state.services:
        from .rhel_os import SimService
        state.services["nginx"] = SimService("nginx", "active", "enabled", "nginx web server")
    state._write_file(
        "/opt/fixitlab/PRECHECK_BASELINE",
        f"kernel={OLD_KERNEL}\npatching_done=False\nrebooted=False\n",
    )
    state._write_file(
        "/opt/fixitlab/precheck.sh",
        "#!/bin/bash\n# Records pre-patch baseline — requires Jira change window\necho kernel=$(uname -r)\n",
    )
    state._write_file(
        "/opt/fixitlab/postcheck.sh",
        "#!/bin/bash\n# Verifies post-patch state matches baseline\nuname -r\n",
    )


def _preset_lvm_extend(state: RHELOSState) -> None:
    from .ops_state import init_lvm_storage_ops

    init_lvm_storage_ops(state)


def _preset_network_nic(state: RHELOSState) -> None:
    from .ops_state import init_network_ops

    init_network_ops(state, "10.0.0.20/24")


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
    "sim-rhel-grub-rescue": _preset_boot_issue,
    "sim-rhel-initramfs-dracut": _preset_initramfs,
    "sim-rhel-mbr-corrupt": _preset_mbr,
    "sim-rhel-kernel-panic": _preset_kernel_panic,
    "sim-mysql-wont-start": _preset_mysql_down,
    "sim-postgres-refused": _preset_postgres_down,
    "sim-html-nginx-root": _preset_wrong_nginx_root,
    "sim-rhel-firewalld-port": _preset_firewalld_blocked,
    "sim-rhel-firewalld-dual": _preset_firewalld_blocked,
    "sim-rhel-mysql-dual": _preset_mysql_down,
    "sim-rhel-patching": _preset_patching,
    "rhel-patching": _preset_patching,
    "sim-rhel-lvm-extend": _preset_lvm_extend,
    "lvm-extend": _preset_lvm_extend,
    "sim-rhel-network-nic": _preset_network_nic,
}
