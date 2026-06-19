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


def _preset_disk_missing(state: RHELOSState) -> None:
    """A freshly attached disk is invisible to the kernel until a SCSI rescan.

    Workflow: lsblk does not show /dev/sdc → echo to the scsi scan node (or
    rescan-scsi-bus.sh) → /dev/sdc appears → mkfs → mount → df.
    """
    state.add_block_device("/dev/sdc", "20G", "disk", present=False)
    state._mkdir("/mnt")
    state._mkdir("/mnt/data")


def _preset_mkfs_mount(state: RHELOSState) -> None:
    """A spare disk is present but unformatted; user must mkfs + mount it."""
    state.add_block_device("/dev/sdc", "20G", "disk", present=True)
    state._mkdir("/mnt")
    state._mkdir("/mnt/data")


def _preset_selinux_port(state: RHELOSState) -> None:
    """SELinux is Enforcing and blocks a non-standard service port until the
    admin adds a port label (semanage port) — or relabels with restorecon."""
    state.selinux_mode = "Enforcing"
    state._mkdir("/var/www/html")
    state._write_file("/var/www/html/index.html", "<html><body>OK</body></html>\n")


def _preset_swap_add(state: RHELOSState) -> None:
    """A disk is available to be turned into additional swap."""
    state.add_block_device("/dev/sdc", "4G", "disk", present=True)


# ── New high-value scenarios ─────────────────────────────────────────


def _preset_selinux_httpd_port(state: RHELOSState) -> None:
    """SELinux Enforcing; nginx wants port 8080 which is NOT in http_port_t, so
    the bind is denied and nginx fails to start. Fix = semanage port -a."""
    state.selinux_mode = "Enforcing"
    # 8080 is intentionally absent from http_port_t so the name_bind is denied.
    state.selinux_ports.setdefault("http_port_t", [80, 443, 8008, 8009, 8443])
    state._mkdir("/etc/nginx")
    state._write_file(
        "/etc/nginx/nginx.conf",
        "user nginx;\nworker_processes auto;\n"
        "server {\n    listen 8080;\n    server_name localhost;\n    root /var/www/html;\n}\n",
    )
    state._mkdir("/var/www/html")
    state._write_file("/var/www/html/index.html", "<html><body>OK</body></html>\n")
    state.services["nginx"].active = "failed"
    state.services["nginx"].sub_state = "failed"


def _preset_disk_missing_fs(state: RHELOSState) -> None:
    """A new /dev/sdc is hidden until a SCSI rescan; then it must be formatted,
    mounted at /data, and persisted in fstab."""
    state.add_block_device("/dev/sdc", "20G", "disk", present=False)
    state._mkdir("/data")


def _preset_swap_not_active(state: RHELOSState) -> None:
    """A spare /dev/sdc disk exists but swap is not active and not in fstab."""
    state.add_block_device("/dev/sdc", "4G", "disk", present=True)


def _preset_lvm_create_mount(state: RHELOSState) -> None:
    """A spare /dev/sdc with no LVM metadata; build PV/VG/LV, mount at /data.

    The disk is registered as a known LVM-capable device (pvs shell command only
    operates on devices it already knows), but it carries NO volume group — the
    scenario is solved only once it is added to the new vgdata VG and the LV is
    created/mounted. Validation keys on PV→VG membership so a bare device is not
    treated as solved.
    """
    from .lvm_state import SimPV

    state.add_block_device("/dev/sdc", "20G", "disk", present=True)
    state.lvm.pvs["/dev/sdc"] = SimPV("/dev/sdc", vg="", size="20.00g", free="20.00g")
    state._mkdir("/data")


def _preset_default_gateway_missing(state: RHELOSState) -> None:
    """eth0 has an address but there is no persistent default gateway."""
    state._mkdir("/etc/sysconfig")
    # Network config exists but carries no GATEWAY line.
    state._write_file("/etc/sysconfig/network", "NETWORKING=yes\nHOSTNAME=rhel-sim\n")


def _preset_sysctl_ip_forward(state: RHELOSState) -> None:
    """net.ipv4.ip_forward is off and no sysctl drop-in enables it."""
    state._mkdir("/etc/sysctl.d")
    state._write_file("/etc/sysctl.conf", "# sysctl settings\n")


def _preset_kernel_module_not_loaded(state: RHELOSState) -> None:
    """br_netfilter is not loaded and not configured to load at boot."""
    state._mkdir("/etc/modules-load.d")


def _preset_postgres_max_connections(state: RHELOSState) -> None:
    """PostgreSQL is down and max_connections is far too low in postgresql.conf."""
    from .rhel_os import SimService

    state.services["postgresql"] = SimService(
        "postgresql", active="failed", enabled="enabled", description="PostgreSQL",
    )
    state._mkdir("/var/lib/pgsql")
    state._mkdir("/var/lib/pgsql/data")
    state._write_file(
        "/var/lib/pgsql/data/postgresql.conf",
        "listen_addresses = '*'\nmax_connections = 20\nshared_buffers = 128MB\n",
    )


def _preset_mysql_table_crashed(state: RHELOSState) -> None:
    """mysqld has failed and a MyISAM table is marked crashed."""
    from .rhel_os import SimService

    state.services["mysqld"] = SimService(
        "mysqld", active="failed", enabled="enabled", description="MySQL Server",
    )
    state._mkdir("/var/lib/mysql")
    state._mkdir("/var/lib/mysql/appdb")
    state._write_file("/var/lib/mysql/appdb/orders.MYI", "MyISAM index (corrupt)\n")
    # The crashed marker is what the validator watches; repair removes it.
    state._write_file(
        "/var/lib/mysql/appdb/orders.CRASHED",
        "Table './appdb/orders' is marked as crashed and should be repaired\n",
    )


def _preset_postgres_disk_full_archive(state: RHELOSState) -> None:
    """PostgreSQL stopped because the data filesystem filled with archived WAL."""
    from .rhel_os import SimService

    state.services["postgresql"] = SimService(
        "postgresql", active="failed", enabled="enabled", description="PostgreSQL",
    )
    state._mkdir("/var/lib/pgsql")
    state._mkdir("/var/lib/pgsql/archive")
    state._mkdir("/var/lib/pgsql/data")
    state._mkdir("/var/lib/pgsql/data/pg_wal")
    # Stale already-archived WAL segments consuming the disk; clearing them frees space.
    for i in range(1, 6):
        state._write_file(
            f"/var/lib/pgsql/archive/0000000100000000000000{i:02d}.wal",
            "X" * 16,
        )


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
    "sim-rhel-disk-missing": _preset_disk_missing,
    "sim-rhel-mkfs-mount": _preset_mkfs_mount,
    "sim-rhel-selinux-port": _preset_selinux_port,
    "sim-rhel-swap-add": _preset_swap_add,
    # New high-value scenarios
    "linux-selinux-httpd-port-denied": _preset_selinux_httpd_port,
    "linux-disk-missing-rescan-fs": _preset_disk_missing_fs,
    "linux-swap-not-active": _preset_swap_not_active,
    "linux-lvm-create-mount": _preset_lvm_create_mount,
    "linux-default-gateway-missing": _preset_default_gateway_missing,
    "linux-sysctl-ip-forward": _preset_sysctl_ip_forward,
    "linux-kernel-module-not-loaded": _preset_kernel_module_not_loaded,
    "db-postgres-max-connections": _preset_postgres_max_connections,
    "db-mysql-table-crashed": _preset_mysql_table_crashed,
    "db-postgres-disk-full-archive": _preset_postgres_disk_full_archive,
}
