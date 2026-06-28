"""Scenario-specific broken states applied to RHELOSState."""

from __future__ import annotations

from .rhel_os import RHELOSState, SimBlockDevice, SimUser


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


def _preset_cross_lvm_vmware(state: RHELOSState, *, requires_reboot: bool = False) -> None:
    """Cross-technology LVM extend: /data is full and there is NO spare disk.

    The ONLY way to add capacity is to add a virtual disk in the VMware
    simulator (same server, same lab session). The hot-added disk is invisible
    to the guest until a SCSI rescan (rescan variant) or a reboot (reboot
    variant) — at which point /dev/sdc appears and can be pvcreate'd, added to
    the vgdata VG, and the lvdata LV extended. Fail-closed: no spare disk exists
    locally, and validation only passes once the LV is genuinely extended.
    """
    from .lvm_state import SimLV, SimPV, SimVG

    # Build a dedicated data VG/LV mounted at /data that is (nearly) full.
    state.lvm.pvs = {
        "/dev/sda2": SimPV("/dev/sda2", "rhel", "48.00g", "0"),
        "/dev/sdb": SimPV("/dev/sdb", "vgdata", "20.00g", "0"),
    }
    state.lvm.vgs["vgdata"] = SimVG("vgdata", "20.00g", "0", ["/dev/sdb"])
    state.lvm.lvs["vgdata/lvdata"] = SimLV("lvdata", "vgdata", "20.00g", "/data", "/dev/mapper/vgdata-lvdata")
    state.block_devices["/dev/mapper/vgdata-lvdata"] = SimBlockDevice(
        "/dev/mapper/vgdata-lvdata", "20G", "lvm", parent="/dev/sdb",
        fstype="xfs", uuid="eeee5555-data", mountpoint="/data")
    state.mounts["/data"] = {"device": "/dev/mapper/vgdata-lvdata", "fstype": "xfs", "size_kb": 20 * 1024 * 1024}
    state._mkdir("/data")
    # No spare disk is present and none is pending until VMware adds one. The
    # cross-tech bridge (keyed by session id) supplies /dev/sdc on rescan/reboot —
    # NOT the Jira @storage-team flow. Leave storage_disk_provisioned True and the
    # pending device unset so pvcreate is not Jira-gated once the disk is revealed.
    state.storage_disk_provisioned = True
    state.pending_storage_device = ""


def _preset_cross_lvm_vmware_rescan(state: RHELOSState) -> None:
    _preset_cross_lvm_vmware(state, requires_reboot=False)


def _preset_cross_lvm_vmware_reboot(state: RHELOSState) -> None:
    _preset_cross_lvm_vmware(state, requires_reboot=True)


def _preset_cross_datastore_full(state: RHELOSState) -> None:
    """Datastore-full variant: /var/lib/docker (on /data LV) is out of space.

    Same mechanic as the LVM-extend rescan scenario — add a disk in VMware, rescan,
    then extend the data LV — framed as 'the datastore filled, grow the volume'.
    """
    _preset_cross_lvm_vmware(state, requires_reboot=False)
    state._mkdir("/var/lib/docker")


def _preset_cross_server_hung(state: RHELOSState) -> None:
    """The guest kernel is hung; the terminal is unresponsive to fixes until the
    VM is reset from the VMware simulator (Power → Reset). After the reset the
    operator confirms the service is healthy from the terminal."""
    state.server_hung = True
    # The web service is reported down while the guest is wedged.
    if "nginx" in state.services:
        state.services["nginx"].active = "failed"
        state.services["nginx"].sub_state = "failed"


def _preset_cross_nic_add(state: RHELOSState) -> None:
    """A second NIC must be added in VMware; the guest sees the new link only
    after a rescan / `ip link set up`, then it is given the 10.0.0.30 address."""
    state.network_nic_provisioned = False
    state.pending_nic_config = "10.0.0.30/24"


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


# ── Storage / partition (fdisk / parted / LVM) scenarios ─────────────────
# A raw spare disk /dev/sdc is presented. The learner must partition it with
# fdisk/parted, lay down a filesystem (or LVM stack), mount it, and persist it.
# Validation reuses the recognized /data mount + fstab branches (slug carries a
# mkfs-mount / lvm-create-mount / disk-missing-rescan substring), the real
# `lvs | grep lvdata` LV probe, and the FIXED-OK marker for legs the engine
# cannot introspect. The e2e fix performs the genuine commands first, then writes
# the marker — so a fresh lab is always fail-closed.


def _preset_fdisk_partition_mkfs(state: RHELOSState) -> None:
    """A raw 20G /dev/sdc with no partition table; partition→mkfs→mount /data."""
    state.add_block_device("/dev/sdc", "20G", "disk", present=True)
    state._mkdir("/data")
    state._write_file("/etc/fstab", "# /etc/fstab\nUUID=root-uuid / xfs defaults 0 0\n")


def _preset_fdisk_two_part_lvm_and_fs(state: RHELOSState) -> None:
    """A raw 30G /dev/sdc; split into two partitions (LVM + plain fs)."""
    state.add_block_device("/dev/sdc", "30G", "disk", present=True)
    state._mkdir("/data")
    state._mkdir("/mnt")
    state._mkdir("/mnt/data2")
    state._write_file("/etc/fstab", "# /etc/fstab\nUUID=root-uuid / xfs defaults 0 0\n")


def _preset_parted_gpt_mkfs(state: RHELOSState) -> None:
    """A raw 20G /dev/sdc with no disk label; write GPT, partition, mount /data."""
    state.add_block_device("/dev/sdc", "20G", "disk", present=True)
    state._mkdir("/data")
    state._write_file("/etc/fstab", "# /etc/fstab\nUUID=root-uuid / xfs defaults 0 0\n")


def _preset_lvm_grow_xfs(state: RHELOSState) -> None:
    """vgdata/lvdata is mounted at /data and full; vgdata has free extents.

    A spare PV (/dev/sdc) is already in vgdata so lvextend has room to grow into.
    Fail-closed: /etc/fstab carries no FIXED-OK marker until the real lvextend +
    xfs_growfs has run.
    """
    from .lvm_state import SimLV, SimPV, SimVG

    state.lvm.pvs["/dev/sdc"] = SimPV("/dev/sdc", "vgdata", "20.00g", "20.00g")
    state.lvm.vgs["vgdata"] = SimVG("vgdata", "40.00g", "20.00g", ["/dev/sdc"])
    state.lvm.lvs["vgdata/lvdata"] = SimLV(
        "lvdata", "vgdata", "20.00g", "/data", "/dev/mapper/vgdata-lvdata")
    state.block_devices["/dev/mapper/vgdata-lvdata"] = SimBlockDevice(
        "/dev/mapper/vgdata-lvdata", "20G", "lvm", parent="vgdata",
        fstype="xfs", uuid="grow1111-data", mountpoint="/data")
    state.block_devices["/dev/vgdata/lvdata"] = state.block_devices["/dev/mapper/vgdata-lvdata"]
    state.mounts["/data"] = {
        "device": "/dev/mapper/vgdata-lvdata", "fstype": "xfs",
        "size_kb": 20 * 1024 * 1024,
    }
    state._mkdir("/data")
    state._write_file("/etc/fstab", "# /etc/fstab\n/dev/mapper/vgdata-lvdata /data xfs defaults 0 0\n")


def _preset_fdisk_corrupt_table_recovery(state: RHELOSState) -> None:
    """The partition table on /dev/sdc was wiped; the /data partition is gone.

    The whole disk is present but has NO partition, so /data cannot be mounted.
    /etc/fstab still references the old partition. Recovery = rebuild partition,
    mkfs, remount /data, repair fstab (FIXED-OK written by the fix afterwards).
    """
    state.add_block_device("/dev/sdc", "20G", "disk", present=True)
    state._mkdir("/data")
    # fstab references the now-missing partition so the mount is broken.
    state._write_file(
        "/etc/fstab",
        "# /etc/fstab\nUUID=root-uuid / xfs defaults 0 0\n/dev/sdc1 /data xfs defaults 0 0\n",
    )


def _preset_fstab_mount_by_uuid(state: RHELOSState) -> None:
    """A raw /dev/sdc; format, then mount at /data by UUID in fstab."""
    state.add_block_device("/dev/sdc", "20G", "disk", present=True)
    state._mkdir("/data")
    state._write_file("/etc/fstab", "# /etc/fstab\nUUID=root-uuid / xfs defaults 0 0\n")


def _preset_fdisk_swap_partition(state: RHELOSState) -> None:
    """A raw 4G /dev/sdc; create a swap PARTITION (fdisk→mkswap→swapon→fstab)."""
    state.add_block_device("/dev/sdc", "4G", "disk", present=True)
    state._write_file("/etc/fstab", "# /etc/fstab\nUUID=root-uuid / xfs defaults 0 0\n")


def _preset_autofs_automount(state: RHELOSState) -> None:
    """autofs master map points at the wrong/broken indirect map for /data/projects."""
    from .rhel_os import SimService

    state.services["autofs"] = SimService(
        "autofs", active="active", enabled="enabled", description="Automounts filesystems on demand")
    state._mkdir("/etc")
    state._mkdir("/data")
    # broken: master map references a non-existent map file
    state._write_file(
        "/etc/auto.master",
        "# broken configuration\n/data/projects /etc/auto.WRONG --timeout=60\n",
    )
    state._write_file(
        "/etc/auto.projects",
        "# broken configuration — malformed entry\napp -fstype=nfs,bad server:/export\n",
    )


# ── Linux-admin topic coverage (config-driven, FIXED-OK validated) ───────


def _preset_at_job_not_scheduled(state: RHELOSState) -> None:
    """A queued at job is malformed and atd is disabled."""
    from .rhel_os import SimService

    state.services["atd"] = SimService(
        "atd", active="inactive", enabled="disabled", description="Deferred execution scheduler")
    state._mkdir("/var/spool/at")
    state._write_file(
        "/var/spool/at/job-0001",
        "# broken configuration\n#!/bin/sh\n/opt/missing/backup.sh\n",
    )


def _preset_systemd_timer_not_firing(state: RHELOSState) -> None:
    """backup.timer has an invalid OnCalendar and is not enabled."""
    state._mkdir("/etc/systemd")
    state._mkdir("/etc/systemd/system")
    state._write_file(
        "/etc/systemd/system/backup.timer",
        "# broken configuration\n[Unit]\nDescription=Nightly backup\n\n[Timer]\n"
        "OnCalendar=every-night-at-2\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n",
    )
    state._write_file(
        "/etc/systemd/system/backup.service",
        "[Unit]\nDescription=Nightly backup\n\n[Service]\nType=oneshot\n"
        "ExecStart=/usr/local/bin/backup.sh\n",
    )


def _preset_nftables_port_blocked(state: RHELOSState) -> None:
    """inet filter input chain default-drops; no accept rule for 8080."""
    state._mkdir("/etc")
    state._write_file(
        "/etc/nftables.conf",
        "# broken configuration\ntable inet filter {\n"
        "  chain input {\n    type filter hook input priority 0; policy drop;\n"
        "    iif \"lo\" accept\n    ct state established,related accept\n"
        "    tcp dport 22 accept\n  }\n}\n",
    )


def _preset_quota_not_enforced(state: RHELOSState) -> None:
    """/home fstab entry lacks usrquota/grpquota so quotas cannot be enforced."""
    state._mkdir("/home")
    state._write_file(
        "/etc/fstab",
        "# broken configuration\nUUID=root-uuid / xfs defaults 0 0\n"
        "/dev/mapper/rhel-home /home xfs defaults 0 0\n",
    )


def _preset_renice_runaway_priority(state: RHELOSState) -> None:
    """A runaway analytics process runs at nice 0 with no policy pinning it lower."""
    state._mkdir("/etc/security")
    state._mkdir("/etc/security/limits.d")
    state._write_file(
        "/etc/security/limits.d/analytics.conf",
        "# broken configuration — no priority policy yet\n",
    )


# ── Real-state generated scenarios (services + config markers) ──

def _preset_rs_db_redis_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['redis'] = SimService('redis', active="failed", enabled="enabled", description='redis service')


def _preset_rs_db_mariadb_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['mariadb'] = SimService('mariadb', active="failed", enabled="enabled", description='mariadb service')


def _preset_rs_db_mongodb_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['mongod'] = SimService('mongod', active="failed", enabled="enabled", description='mongod service')


def _preset_rs_db_cassandra_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['cassandra'] = SimService('cassandra', active="failed", enabled="enabled", description='cassandra service')


def _preset_rs_db_pgbouncer_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['pgbouncer'] = SimService('pgbouncer', active="failed", enabled="enabled", description='pgbouncer service')


def _preset_rs_db_postgres_pg_hba_deny(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/pg_hba.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/pg_hba.conf', '# broken configuration for db-postgres-pg-hba-deny\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_bind_address(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-bind-address\n# this file needs the documented fix\n')


def _preset_rs_db_redis_maxmemory_noevict(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/redis/redis.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/redis/redis.conf', '# broken configuration for db-redis-maxmemory-noevict\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_fsync_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-fsync-off\n# this file needs the documented fix\n')


def _preset_rs_ansible_become_password_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/playbook.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/playbook.yml', '# broken configuration for ansible-become-password-missing\n# this file needs the documented fix\n')


def _preset_rs_ansible_jinja_template_error(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/templates/app.conf.j2')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/templates/app.conf.j2', '# broken configuration for ansible-jinja-template-error\n# this file needs the documented fix\n')


def _preset_rs_ansible_loop_wrong_var(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/loop.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/loop.yml', '# broken configuration for ansible-loop-wrong-var\n# this file needs the documented fix\n')


def _preset_rs_ansible_when_condition_bug(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/conditional.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/conditional.yml', '# broken configuration for ansible-when-condition-bug\n# this file needs the documented fix\n')


def _preset_rs_ansible_galaxy_role_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/requirements.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/requirements.yml', '# broken configuration for ansible-galaxy-role-missing\n# this file needs the documented fix\n')


def _preset_rs_ansible_vars_precedence_bug(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/group_vars/all.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/group_vars/all.yml', '# broken configuration for ansible-vars-precedence-bug\n# this file needs the documented fix\n')


def _preset_rs_ansible_no_log_leaking_secret(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/secret-task.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/secret-task.yml', '# broken configuration for ansible-no-log-leaking-secret\n# this file needs the documented fix\n')


def _preset_rs_shell_rsync_delete_danger(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/backup.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/backup.sh', '# broken configuration for shell-rsync-delete-danger\n# this file needs the documented fix\n')


def _preset_rs_shell_cron_path_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/cronjob.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/cronjob.sh', '# broken configuration for shell-cron-path-missing\n# this file needs the documented fix\n')


def _preset_rs_shell_pipefail_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/deploy-pipeline.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/deploy-pipeline.sh', '# broken configuration for shell-pipefail-missing\n# this file needs the documented fix\n')


def _preset_rs_shell_word_splitting_bug(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/process-files.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/process-files.sh', '# broken configuration for shell-word-splitting-bug\n# this file needs the documented fix\n')


def _preset_rs_shell_signal_not_trapped(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/long-job.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/long-job.sh', '# broken configuration for shell-signal-not-trapped\n# this file needs the documented fix\n')


def _preset_rs_shell_readonly_clobber(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/report.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/report.sh', '# broken configuration for shell-readonly-clobber\n# this file needs the documented fix\n')


def _preset_rs_shell_arith_division_zero(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/metrics.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/metrics.sh', '# broken configuration for shell-arith-division-zero\n# this file needs the documented fix\n')


def _preset_rs_shell_getopts_parsing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/cli-tool.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/cli-tool.sh', '# broken configuration for shell-getopts-parsing\n# this file needs the documented fix\n')


def _preset_rs_html_broken_doctype(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-broken-doctype\n# this file needs the documented fix\n')


def _preset_rs_html_missing_charset(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-missing-charset\n# this file needs the documented fix\n')


def _preset_rs_html_broken_relative_links(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-broken-relative-links\n# this file needs the documented fix\n')


def _preset_rs_html_inaccessible_form(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/contact.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/contact.html', '# broken configuration for html-inaccessible-form\n# this file needs the documented fix\n')


def _preset_rs_html_meta_viewport_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-meta-viewport-missing\n# this file needs the documented fix\n')


def _preset_rs_html_csp_blocking_assets(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-csp-blocking-assets\n# this file needs the documented fix\n')


def _preset_rs_html_duplicate_ids(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-duplicate-ids\n# this file needs the documented fix\n')


def _preset_rs_rhel_chronyd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['chronyd'] = SimService('chronyd', active="failed", enabled="enabled", description='chronyd service')


def _preset_rs_rhel_rsyslog_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['rsyslog'] = SimService('rsyslog', active="failed", enabled="enabled", description='rsyslog service')


def _preset_rs_rhel_firewalld_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['firewalld'] = SimService('firewalld', active="failed", enabled="enabled", description='firewalld service')


def _preset_rs_rhel_auditd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['auditd'] = SimService('auditd', active="failed", enabled="enabled", description='auditd service')


def _preset_rs_rhel_nfs_server_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['nfs-server'] = SimService('nfs-server', active="failed", enabled="enabled", description='nfs-server service')


def _preset_rs_rhel_subscription_manager_config(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/yum.repos.d/redhat.repo')
    if d:
        state._mkdir(d)
    state._write_file('/etc/yum.repos.d/redhat.repo', '# broken configuration for rhel-subscription-manager-config\n# this file needs the documented fix\n')


def _preset_rs_rhel_tuned_wrong_profile(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/tuned/active_profile')
    if d:
        state._mkdir(d)
    state._write_file('/etc/tuned/active_profile', '# broken configuration for rhel-tuned-wrong-profile\n# this file needs the documented fix\n')


def _preset_rs_rhel_selinux_booleans(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/selinux/booleans.local')
    if d:
        state._mkdir(d)
    state._write_file('/etc/selinux/booleans.local', '# broken configuration for rhel-selinux-booleans\n# this file needs the documented fix\n')


def _preset_rs_rhel_grub_default_target(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/systemd/default.target.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/systemd/default.target.conf', '# broken configuration for rhel-grub-default-target\n# this file needs the documented fix\n')


def _preset_rs_gpu_mps_not_enabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia-mps/config')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia-mps/config', '# broken configuration for gpu-mps-not-enabled\n# this file needs the documented fix\n')


def _preset_rs_gpu_ecc_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/ecc.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/ecc.conf', '# broken configuration for gpu-ecc-disabled\n# this file needs the documented fix\n')


def _preset_rs_gpu_persistence_mode_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/persistence.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/persistence.conf', '# broken configuration for gpu-persistence-mode-off\n# this file needs the documented fix\n')


def _preset_rs_gpu_cgroup_device_denied(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia-container-runtime/config.toml')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia-container-runtime/config.toml', '# broken configuration for gpu-cgroup-device-denied\n# this file needs the documented fix\n')


def _preset_rs_gpu_clock_throttled_power(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/power-limit.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/power-limit.conf', '# broken configuration for gpu-clock-throttled-power\n# this file needs the documented fix\n')


def _preset_rs_gpu_fabric_manager_down(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/fabricmanager.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/fabricmanager.cfg', '# broken configuration for gpu-fabric-manager-down\n# this file needs the documented fix\n')


def _preset_rs_baremetal_bios_boot_order(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/boot_order.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/boot_order.cfg', '# broken configuration for baremetal-bios-boot-order\n# this file needs the documented fix\n')


def _preset_rs_baremetal_bmc_snmp_misconfig(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/snmp.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/snmp.cfg', '# broken configuration for baremetal-bmc-snmp-misconfig\n# this file needs the documented fix\n')


def _preset_rs_baremetal_fan_curve_aggressive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/fan_curve.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/fan_curve.cfg', '# broken configuration for baremetal-fan-curve-aggressive\n# this file needs the documented fix\n')


def _preset_rs_baremetal_numa_not_enabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/numa.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/numa.cfg', '# broken configuration for baremetal-numa-not-enabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_firmware_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/firmware/nic_version.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/firmware/nic_version.cfg', '# broken configuration for baremetal-firmware-mismatch\n# this file needs the documented fix\n')


def _preset_rs_baremetal_secure_boot_blocking(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/secureboot.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/secureboot.cfg', '# broken configuration for baremetal-secure-boot-blocking\n# this file needs the documented fix\n')


def _preset_rs_docker_containerd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['containerd'] = SimService('containerd', active="failed", enabled="enabled", description='containerd service')


def _preset_rs_docker_daemon_json_invalid(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-daemon-json-invalid\n# this file needs the documented fix\n')


def _preset_rs_docker_storage_driver_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/storage.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/storage.conf', '# broken configuration for docker-storage-driver-wrong\n# this file needs the documented fix\n')


def _preset_rs_docker_insecure_registry(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/registries.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/registries.conf', '# broken configuration for docker-insecure-registry\n# this file needs the documented fix\n')


def _preset_rs_docker_default_bridge_subnet(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-default-bridge-subnet\n# this file needs the documented fix\n')


def _preset_rs_docker_logging_unbounded(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-logging-unbounded\n# this file needs the documented fix\n')


def _preset_rs_docker_userns_remap_broken(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-userns-remap-broken\n# this file needs the documented fix\n')


def _preset_rs_linux_haproxy_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['haproxy'] = SimService('haproxy', active="failed", enabled="enabled", description='haproxy service')


def _preset_rs_linux_named_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['named'] = SimService('named', active="failed", enabled="enabled", description='named service')


def _preset_rs_linux_memcached_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['memcached'] = SimService('memcached', active="failed", enabled="enabled", description='memcached service')


def _preset_rs_linux_rabbitmq_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['rabbitmq-server'] = SimService('rabbitmq-server', active="failed", enabled="enabled", description='rabbitmq-server service')


def _preset_rs_linux_nginx_stream_proxy_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['nginx'] = SimService('nginx', active="failed", enabled="enabled", description='nginx service')


def _preset_rs_linux_fstab_bad_option(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/fstab')
    if d:
        state._mkdir(d)
    state._write_file('/etc/fstab', '# broken configuration for linux-fstab-bad-option\n# this file needs the documented fix\n')


def _preset_rs_linux_limits_conf_too_low(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/security/limits.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/security/limits.conf', '# broken configuration for linux-limits-conf-too-low\n# this file needs the documented fix\n')


def _preset_rs_linux_resolv_conf_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/resolv.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/resolv.conf', '# broken configuration for linux-resolv-conf-wrong\n# this file needs the documented fix\n')


def _preset_rs_linux_sudoers_syntax_error(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/sudoers.d/ops')
    if d:
        state._mkdir(d)
    state._write_file('/etc/sudoers.d/ops', '# broken configuration for linux-sudoers-syntax-error\n# this file needs the documented fix\n')


def _preset_rs_linux_logrotate_misconfig(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/logrotate.d/app')
    if d:
        state._mkdir(d)
    state._write_file('/etc/logrotate.d/app', '# broken configuration for linux-logrotate-misconfig\n# this file needs the documented fix\n')


def _preset_rs_linux_crontab_syntax_error(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/cron.d/app-job')
    if d:
        state._mkdir(d)
    state._write_file('/etc/cron.d/app-job', '# broken configuration for linux-crontab-syntax-error\n# this file needs the documented fix\n')


def _preset_rs_linux_journald_storage_volatile(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/systemd/journald.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/systemd/journald.conf', '# broken configuration for linux-journald-storage-volatile\n# this file needs the documented fix\n')


def _preset_rs_linux_sshd_permitroot_hardening(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/ssh/sshd_config.d/hardening.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/ssh/sshd_config.d/hardening.conf', '# broken configuration for linux-sshd-permitroot-hardening\n# this file needs the documented fix\n')




# ── Real-state generated scenarios wave 2/3 ──

def _preset_rs_db_mysql_replica_stopped(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['mysqld'] = SimService('mysqld', active="failed", enabled="enabled", description='mysqld service')


def _preset_rs_db_postgres_standby_stopped(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['postgresql'] = SimService('postgresql', active="failed", enabled="enabled", description='postgresql service')


def _preset_rs_db_redis_sentinel_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['redis-sentinel'] = SimService('redis-sentinel', active="failed", enabled="enabled", description='redis-sentinel service')


def _preset_rs_db_etcd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['etcd'] = SimService('etcd', active="failed", enabled="enabled", description='etcd service')


def _preset_rs_db_influxdb_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['influxdb'] = SimService('influxdb', active="failed", enabled="enabled", description='influxdb service')


def _preset_rs_db_elasticsearch_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['elasticsearch'] = SimService('elasticsearch', active="failed", enabled="enabled", description='elasticsearch service')


def _preset_rs_db_couchdb_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['couchdb'] = SimService('couchdb', active="failed", enabled="enabled", description='couchdb service')


def _preset_rs_db_neo4j_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['neo4j'] = SimService('neo4j', active="failed", enabled="enabled", description='neo4j service')


def _preset_rs_db_clickhouse_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['clickhouse-server'] = SimService('clickhouse-server', active="failed", enabled="enabled", description='clickhouse-server service')


def _preset_rs_db_postgres_shared_buffers_low(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-shared-buffers-low\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_work_mem_low(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-work-mem-low\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_innodb_buffer_pool(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-innodb-buffer-pool\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_slow_query_log_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-slow-query-log-off\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_log_min_duration(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-log-min-duration\n# this file needs the documented fix\n')


def _preset_rs_db_mongodb_no_auth(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/mongod.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/mongod.conf', '# broken configuration for db-mongodb-no-auth\n# this file needs the documented fix\n')


def _preset_rs_db_redis_no_password(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/redis/redis.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/redis/redis.conf', '# broken configuration for db-redis-no-password\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_ssl_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-ssl-disabled\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_sql_mode_loose(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-sql-mode-loose\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_autovacuum_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-autovacuum-off\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_max_allowed_packet(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-max-allowed-packet\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_statement_timeout(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-statement-timeout\n# this file needs the documented fix\n')


def _preset_rs_db_mariadb_galera_config(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf.d/galera.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf.d/galera.cnf', '# broken configuration for db-mariadb-galera-config\n# this file needs the documented fix\n')


def _preset_rs_db_redis_rdb_aof_conflict(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/redis/redis.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/redis/redis.conf', '# broken configuration for db-redis-rdb-aof-conflict\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_hot_standby_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-hot-standby-off\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_binlog_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-binlog-disabled\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_wal_level_minimal(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-wal-level-minimal\n# this file needs the documented fix\n')


def _preset_rs_db_mongodb_oplog_too_small(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/mongod.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/mongod.conf', '# broken configuration for db-mongodb-oplog-too-small\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_tmp_table_disk(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-tmp-table-disk\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_checkpoint_spikes(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-checkpoint-spikes\n# this file needs the documented fix\n')


def _preset_rs_db_redis_thp_warning(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/redis/redis-tuning.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/redis/redis-tuning.conf', '# broken configuration for db-redis-thp-warning\n# this file needs the documented fix\n')


def _preset_rs_db_mysql_skip_name_resolve(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/my.cnf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/my.cnf', '# broken configuration for db-mysql-skip-name-resolve\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_connection_leak(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-connection-leak\n# this file needs the documented fix\n')


def _preset_rs_ansible_handler_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/site.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/site.yml', '# broken configuration for ansible-handler-missing\n# this file needs the documented fix\n')


def _preset_rs_ansible_tags_misused(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/tagged.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/tagged.yml', '# broken configuration for ansible-tags-misused\n# this file needs the documented fix\n')


def _preset_rs_ansible_delegate_to_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/delegate.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/delegate.yml', '# broken configuration for ansible-delegate-to-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_serial_too_high(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/rolling.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/rolling.yml', '# broken configuration for ansible-serial-too-high\n# this file needs the documented fix\n')


def _preset_rs_ansible_block_rescue_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/block.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/block.yml', '# broken configuration for ansible-block-rescue-missing\n# this file needs the documented fix\n')


def _preset_rs_ansible_vault_id_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/vault-vars.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/vault-vars.yml', '# broken configuration for ansible-vault-id-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_inventory_group_vars(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/inventory/hosts.ini')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/inventory/hosts.ini', '# broken configuration for ansible-inventory-group-vars\n# this file needs the documented fix\n')


def _preset_rs_ansible_fact_caching_stale(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/ansible.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/ansible.cfg', '# broken configuration for ansible-fact-caching-stale\n# this file needs the documented fix\n')


def _preset_rs_ansible_become_user_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/become.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/become.yml', '# broken configuration for ansible-become-user-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_template_trim_blocks(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/templates/nginx.conf.j2')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/templates/nginx.conf.j2', '# broken configuration for ansible-template-trim-blocks\n# this file needs the documented fix\n')


def _preset_rs_ansible_with_items_deprecated(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/legacy-loop.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/legacy-loop.yml', '# broken configuration for ansible-with-items-deprecated\n# this file needs the documented fix\n')


def _preset_rs_ansible_changed_when_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/idempotent.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/idempotent.yml', '# broken configuration for ansible-changed-when-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_failed_when_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/failwhen.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/failwhen.yml', '# broken configuration for ansible-failed-when-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_async_poll_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/async.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/async.yml', '# broken configuration for ansible-async-poll-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_uri_validate_certs(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/uri.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/uri.yml', '# broken configuration for ansible-uri-validate-certs\n# this file needs the documented fix\n')


def _preset_rs_ansible_package_name_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/pkg.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/pkg.yml', '# broken configuration for ansible-package-name-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_service_enabled_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/svc.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/svc.yml', '# broken configuration for ansible-service-enabled-missing\n# this file needs the documented fix\n')


def _preset_rs_ansible_copy_vs_template(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/copy.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/copy.yml', '# broken configuration for ansible-copy-vs-template\n# this file needs the documented fix\n')


def _preset_rs_ansible_lineinfile_regex(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/lineinfile.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/lineinfile.yml', '# broken configuration for ansible-lineinfile-regex\n# this file needs the documented fix\n')


def _preset_rs_ansible_mount_fstab_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/mount.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/mount.yml', '# broken configuration for ansible-mount-fstab-missing\n# this file needs the documented fix\n')


def _preset_rs_ansible_cron_special_time(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/cron.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/cron.yml', '# broken configuration for ansible-cron-special-time\n# this file needs the documented fix\n')


def _preset_rs_ansible_firewalld_permanent(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/firewalld.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/firewalld.yml', '# broken configuration for ansible-firewalld-permanent\n# this file needs the documented fix\n')


def _preset_rs_ansible_selinux_context(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/sefcontext.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/sefcontext.yml', '# broken configuration for ansible-selinux-context\n# this file needs the documented fix\n')


def _preset_rs_ansible_user_ssh_key(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/sshkey.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/sshkey.yml', '# broken configuration for ansible-user-ssh-key\n# this file needs the documented fix\n')


def _preset_rs_ansible_template_validate(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/sshd-template.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/sshd-template.yml', '# broken configuration for ansible-template-validate\n# this file needs the documented fix\n')


def _preset_rs_ansible_handler_flush(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/flush.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/flush.yml', '# broken configuration for ansible-handler-flush\n# this file needs the documented fix\n')


def _preset_rs_ansible_register_loop_results(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/register.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/register.yml', '# broken configuration for ansible-register-loop-results\n# this file needs the documented fix\n')


def _preset_rs_ansible_set_fact_scope(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/setfact.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/setfact.yml', '# broken configuration for ansible-set-fact-scope\n# this file needs the documented fix\n')


def _preset_rs_ansible_import_vs_include(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/include.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/include.yml', '# broken configuration for ansible-import-vs-include\n# this file needs the documented fix\n')


def _preset_rs_ansible_callback_plugin(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/ansible.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/ansible.cfg', '# broken configuration for ansible-callback-plugin\n# this file needs the documented fix\n')


def _preset_rs_ansible_strategy_free_unsafe(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/strategy.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/strategy.yml', '# broken configuration for ansible-strategy-free-unsafe\n# this file needs the documented fix\n')


def _preset_rs_ansible_connection_local_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/localconn.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/localconn.yml', '# broken configuration for ansible-connection-local-wrong\n# this file needs the documented fix\n')


def _preset_rs_ansible_env_var_not_passed(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/env.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/env.yml', '# broken configuration for ansible-env-var-not-passed\n# this file needs the documented fix\n')


def _preset_rs_ansible_retries_until(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/retry.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/retry.yml', '# broken configuration for ansible-retries-until\n# this file needs the documented fix\n')


def _preset_rs_ansible_yaml_indentation(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/home/ansible/badindent.yml')
    if d:
        state._mkdir(d)
    state._write_file('/home/ansible/badindent.yml', '# broken configuration for ansible-yaml-indentation\n# this file needs the documented fix\n')


def _preset_rs_shell_set_e_not_set(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/run.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/run.sh', '# broken configuration for shell-set-e-not-set\n# this file needs the documented fix\n')


def _preset_rs_shell_tmpfile_race(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/tmpwork.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/tmpwork.sh', '# broken configuration for shell-tmpfile-race\n# this file needs the documented fix\n')


def _preset_rs_shell_eval_injection(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/parse.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/parse.sh', '# broken configuration for shell-eval-injection\n# this file needs the documented fix\n')


def _preset_rs_shell_cd_without_check(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/clean.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/clean.sh', '# broken configuration for shell-cd-without-check\n# this file needs the documented fix\n')


def _preset_rs_shell_glob_no_match(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/archive.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/archive.sh', '# broken configuration for shell-glob-no-match\n# this file needs the documented fix\n')


def _preset_rs_shell_arithmetic_leading_zero(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/dates.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/dates.sh', '# broken configuration for shell-arithmetic-leading-zero\n# this file needs the documented fix\n')


def _preset_rs_shell_here_string_quoting(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/gen-config.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/gen-config.sh', '# broken configuration for shell-here-string-quoting\n# this file needs the documented fix\n')


def _preset_rs_shell_exit_code_masked(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/check-status.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/check-status.sh', '# broken configuration for shell-exit-code-masked\n# this file needs the documented fix\n')


def _preset_rs_shell_ifs_not_reset(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/csv.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/csv.sh', '# broken configuration for shell-ifs-not-reset\n# this file needs the documented fix\n')


def _preset_rs_shell_subshell_var_lost(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/count.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/count.sh', '# broken configuration for shell-subshell-var-lost\n# this file needs the documented fix\n')


def _preset_rs_shell_test_string_vs_int(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/threshold.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/threshold.sh', '# broken configuration for shell-test-string-vs-int\n# this file needs the documented fix\n')


def _preset_rs_shell_find_exec_unsafe(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/purge.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/purge.sh', '# broken configuration for shell-find-exec-unsafe\n# this file needs the documented fix\n')


def _preset_rs_shell_readarray_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/lines.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/lines.sh', '# broken configuration for shell-readarray-missing\n# this file needs the documented fix\n')


def _preset_rs_shell_trap_err_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/pipeline.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/pipeline.sh', '# broken configuration for shell-trap-err-missing\n# this file needs the documented fix\n')


def _preset_rs_shell_lockfile_stale(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/singleton.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/singleton.sh', '# broken configuration for shell-lockfile-stale\n# this file needs the documented fix\n')


def _preset_rs_shell_date_format_locale(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/report-date.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/report-date.sh', '# broken configuration for shell-date-format-locale\n# this file needs the documented fix\n')


def _preset_rs_shell_printf_vs_echo(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/emit.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/emit.sh', '# broken configuration for shell-printf-vs-echo\n# this file needs the documented fix\n')


def _preset_rs_shell_unset_var_default(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/params.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/params.sh', '# broken configuration for shell-unset-var-default\n# this file needs the documented fix\n')


def _preset_rs_shell_pipe_to_while_fd(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/fanout.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/fanout.sh', '# broken configuration for shell-pipe-to-while-fd\n# this file needs the documented fix\n')


def _preset_rs_shell_mktemp_cleanup(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/build-temp.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/build-temp.sh', '# broken configuration for shell-mktemp-cleanup\n# this file needs the documented fix\n')


def _preset_rs_shell_array_quoting(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/args-array.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/args-array.sh', '# broken configuration for shell-array-quoting\n# this file needs the documented fix\n')


def _preset_rs_shell_command_substitution_newline(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/capture.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/capture.sh', '# broken configuration for shell-command-substitution-newline\n# this file needs the documented fix\n')


def _preset_rs_shell_getopt_long(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/longopts.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/longopts.sh', '# broken configuration for shell-getopt-long\n# this file needs the documented fix\n')


def _preset_rs_shell_numeric_bc_scale(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/ratio.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/ratio.sh', '# broken configuration for shell-numeric-bc-scale\n# this file needs the documented fix\n')


def _preset_rs_shell_source_relative_path(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/main-with-lib.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/main-with-lib.sh', '# broken configuration for shell-source-relative-path\n# this file needs the documented fix\n')


def _preset_rs_shell_background_wait(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/parallel.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/parallel.sh', '# broken configuration for shell-background-wait\n# this file needs the documented fix\n')


def _preset_rs_shell_echo_password(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/db-login.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/db-login.sh', '# broken configuration for shell-echo-password\n# this file needs the documented fix\n')


def _preset_rs_shell_rm_rf_variable(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/wipe.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/wipe.sh', '# broken configuration for shell-rm-rf-variable\n# this file needs the documented fix\n')


def _preset_rs_shell_curl_no_fail(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/healthcheck.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/healthcheck.sh', '# broken configuration for shell-curl-no-fail\n# this file needs the documented fix\n')


def _preset_rs_shell_tar_absolute_paths(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/make-backup.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/make-backup.sh', '# broken configuration for shell-tar-absolute-paths\n# this file needs the documented fix\n')


def _preset_rs_shell_no_shebang(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/no-shebang.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/no-shebang.sh', '# broken configuration for shell-no-shebang\n# this file needs the documented fix\n')


def _preset_rs_shell_stderr_stdout_merge(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/logging.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/logging.sh', '# broken configuration for shell-stderr-stdout-merge\n# this file needs the documented fix\n')


def _preset_rs_shell_exit_trap_overwrite(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/multi-trap.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/multi-trap.sh', '# broken configuration for shell-exit-trap-overwrite\n# this file needs the documented fix\n')


def _preset_rs_shell_positional_shift(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/shift-args.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/shift-args.sh', '# broken configuration for shell-positional-shift\n# this file needs the documented fix\n')


def _preset_rs_shell_process_sub_portability(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/diff-check.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/diff-check.sh', '# broken configuration for shell-process-sub-portability\n# this file needs the documented fix\n')


def _preset_rs_shell_readonly_reassign(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/scripts/const.sh')
    if d:
        state._mkdir(d)
    state._write_file('/opt/scripts/const.sh', '# broken configuration for shell-readonly-reassign\n# this file needs the documented fix\n')


def _preset_rs_docker_daemon_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['docker'] = SimService('docker', active="failed", enabled="enabled", description='docker service')


def _preset_rs_docker_docker_socket_proxy_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['docker-socket-proxy'] = SimService('docker-socket-proxy', active="failed", enabled="enabled", description='docker-socket-proxy service')


def _preset_rs_docker_compose_env_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-compose-env-missing\n# this file needs the documented fix\n')


def _preset_rs_docker_compose_depends_on(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-compose-depends-on\n# this file needs the documented fix\n')


def _preset_rs_docker_healthcheck_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-healthcheck-wrong\n# this file needs the documented fix\n')


def _preset_rs_docker_restart_policy_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-restart-policy-missing\n# this file needs the documented fix\n')


def _preset_rs_docker_memory_limit_oom(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-memory-limit-oom\n# this file needs the documented fix\n')


def _preset_rs_docker_cpu_limit_throttle(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-cpu-limit-throttle\n# this file needs the documented fix\n')


def _preset_rs_docker_bind_mount_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-bind-mount-wrong\n# this file needs the documented fix\n')


def _preset_rs_docker_volume_permissions(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-volume-permissions\n# this file needs the documented fix\n')


def _preset_rs_docker_network_alias_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-network-alias-missing\n# this file needs the documented fix\n')


def _preset_rs_docker_ports_conflict(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-ports-conflict\n# this file needs the documented fix\n')


def _preset_rs_docker_dockerfile_cache_bust(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-dockerfile-cache-bust\n# this file needs the documented fix\n')


def _preset_rs_docker_dockerfile_root_user(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-dockerfile-root-user\n# this file needs the documented fix\n')


def _preset_rs_docker_multistage_bloat(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-multistage-bloat\n# this file needs the documented fix\n')


def _preset_rs_docker_entrypoint_shell_form(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-entrypoint-shell-form\n# this file needs the documented fix\n')


def _preset_rs_docker_no_dockerignore(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/.dockerignore')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/.dockerignore', '# broken configuration for docker-no-dockerignore\n# this file needs the documented fix\n')


def _preset_rs_docker_secrets_in_env(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-secrets-in-env\n# this file needs the documented fix\n')


def _preset_rs_docker_compose_version_deprecated(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-compose-version-deprecated\n# this file needs the documented fix\n')


def _preset_rs_docker_logging_driver_blocking(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-logging-driver-blocking\n# this file needs the documented fix\n')


def _preset_rs_docker_iptables_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-iptables-disabled\n# this file needs the documented fix\n')


def _preset_rs_docker_mtu_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-mtu-mismatch\n# this file needs the documented fix\n')


def _preset_rs_docker_default_ulimit_low(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-default-ulimit-low\n# this file needs the documented fix\n')


def _preset_rs_docker_live_restore_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-live-restore-off\n# this file needs the documented fix\n')


def _preset_rs_docker_registry_mirror_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for docker-registry-mirror-missing\n# this file needs the documented fix\n')


def _preset_rs_docker_compose_network_external(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-compose-network-external\n# this file needs the documented fix\n')


def _preset_rs_docker_build_arg_undefined(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-build-arg-undefined\n# this file needs the documented fix\n')


def _preset_rs_docker_healthcheck_interval_aggressive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-healthcheck-interval-aggressive\n# this file needs the documented fix\n')


def _preset_rs_docker_compose_restart_loop(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-compose-restart-loop\n# this file needs the documented fix\n')


def _preset_rs_docker_overlay_network_encryption(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-overlay-network-encryption\n# this file needs the documented fix\n')


def _preset_rs_docker_tmpfs_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-tmpfs-missing\n# this file needs the documented fix\n')


def _preset_rs_docker_cap_add_excessive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-cap-add-excessive\n# this file needs the documented fix\n')


def _preset_rs_docker_readonly_rootfs_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-readonly-rootfs-missing\n# this file needs the documented fix\n')


def _preset_rs_docker_network_subnet_overlap(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-network-subnet-overlap\n# this file needs the documented fix\n')


def _preset_rs_docker_init_missing_zombies(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/docker-compose.yml')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/docker-compose.yml', '# broken configuration for docker-init-missing-zombies\n# this file needs the documented fix\n')


def _preset_rs_docker_build_platform_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/opt/app/Dockerfile')
    if d:
        state._mkdir(d)
    state._write_file('/opt/app/Dockerfile', '# broken configuration for docker-build-platform-mismatch\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_version_pin(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/driver-pin.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/driver-pin.conf', '# broken configuration for gpu-driver-version-pin\n# this file needs the documented fix\n')


def _preset_rs_gpu_cuda_toolkit_path(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/profile.d/cuda.sh')
    if d:
        state._mkdir(d)
    state._write_file('/etc/profile.d/cuda.sh', '# broken configuration for gpu-cuda-toolkit-path\n# this file needs the documented fix\n')


def _preset_rs_gpu_nccl_ib_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nccl.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nccl.conf', '# broken configuration for gpu-nccl-ib-disabled\n# this file needs the documented fix\n')


def _preset_rs_gpu_mig_profile_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/mig-layout.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/mig-layout.conf', '# broken configuration for gpu-mig-profile-wrong\n# this file needs the documented fix\n')


def _preset_rs_gpu_dcgm_exporter_config(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/dcgm-exporter/config.csv')
    if d:
        state._mkdir(d)
    state._write_file('/etc/dcgm-exporter/config.csv', '# broken configuration for gpu-dcgm-exporter-config\n# this file needs the documented fix\n')


def _preset_rs_gpu_xid_errors_logging(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia/xid-monitor.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia/xid-monitor.conf', '# broken configuration for gpu-xid-errors-logging\n# this file needs the documented fix\n')


def _preset_rs_gpu_cgroups_v2_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nvidia-container-runtime/config.toml')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nvidia-container-runtime/config.toml', '# broken configuration for gpu-cgroups-v2-mismatch\n# this file needs the documented fix\n')


def _preset_rs_gpu_topology_numa_pinning(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/numa-pinning.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/numa-pinning.conf', '# broken configuration for gpu-topology-numa-pinning\n# this file needs the documented fix\n')


def _preset_rs_gpu_power_cap_cluster(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/cluster-power.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/cluster-power.conf', '# broken configuration for gpu-power-cap-cluster\n# this file needs the documented fix\n')


def _preset_rs_gpu_vbios_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/vbios-baseline.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/vbios-baseline.conf', '# broken configuration for gpu-vbios-mismatch\n# this file needs the documented fix\n')


def _preset_rs_gpu_thermal_throttle_airflow(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/thermal-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/thermal-policy.conf', '# broken configuration for gpu-thermal-throttle-airflow\n# this file needs the documented fix\n')


def _preset_rs_gpu_shared_memory_limit(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/shm-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/shm-policy.conf', '# broken configuration for gpu-shared-memory-limit\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_mode_wddm(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/driver-mode.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/driver-mode.conf', '# broken configuration for gpu-driver-mode-wddm\n# this file needs the documented fix\n')


def _preset_rs_gpu_cuda_arch_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/cuda-arch.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/cuda-arch.conf', '# broken configuration for gpu-cuda-arch-mismatch\n# this file needs the documented fix\n')


def _preset_rs_gpu_persistence_daemon_config(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/persistenced.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/persistenced.conf', '# broken configuration for gpu-persistence-daemon-config\n# this file needs the documented fix\n')


def _preset_rs_gpu_rocm_kfd_permissions(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/rocm-access.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/rocm-access.conf', '# broken configuration for gpu-rocm-kfd-permissions\n# this file needs the documented fix\n')


def _preset_rs_gpu_mps_pipe_dir(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/mps-pipe.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/mps-pipe.conf', '# broken configuration for gpu-mps-pipe-dir\n# this file needs the documented fix\n')


def _preset_rs_gpu_fan_policy_passive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/fan-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/fan-policy.conf', '# broken configuration for gpu-fan-policy-passive\n# this file needs the documented fix\n')


def _preset_rs_gpu_clock_locked_low(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/clock-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/clock-policy.conf', '# broken configuration for gpu-clock-locked-low\n# this file needs the documented fix\n')


def _preset_rs_gpu_ecc_pages_retired(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/health-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/health-policy.conf', '# broken configuration for gpu-ecc-pages-retired\n# this file needs the documented fix\n')


def _preset_rs_gpu_container_toolkit_runtime(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/docker/daemon.json')
    if d:
        state._mkdir(d)
    state._write_file('/etc/docker/daemon.json', '# broken configuration for gpu-container-toolkit-runtime\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_blacklist_nouveau(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/modprobe.d/blacklist-nouveau.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/modprobe.d/blacklist-nouveau.conf', '# broken configuration for gpu-driver-blacklist-nouveau\n# this file needs the documented fix\n')


def _preset_rs_gpu_cuda_mps_memory_limit(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/mps-memlimit.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/mps-memlimit.conf', '# broken configuration for gpu-cuda-mps-memory-limit\n# this file needs the documented fix\n')


def _preset_rs_gpu_p2p_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/p2p.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/p2p.conf', '# broken configuration for gpu-p2p-disabled\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_fabric_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/fabric-version.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/fabric-version.conf', '# broken configuration for gpu-driver-fabric-mismatch\n# this file needs the documented fix\n')


def _preset_rs_gpu_monitoring_interval(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/telemetry.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/telemetry.conf', '# broken configuration for gpu-monitoring-interval\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_debug_logging(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/driver-logging.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/driver-logging.conf', '# broken configuration for gpu-driver-debug-logging\n# this file needs the documented fix\n')


def _preset_rs_gpu_affinity_hyperthreading(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/cpu-affinity.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/cpu-affinity.conf', '# broken configuration for gpu-affinity-hyperthreading\n# this file needs the documented fix\n')


def _preset_rs_gpu_nvlink_degraded(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/nvlink-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/nvlink-policy.conf', '# broken configuration for gpu-nvlink-degraded\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_secureboot(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/secureboot-signing.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/secureboot-signing.conf', '# broken configuration for gpu-driver-secureboot\n# this file needs the documented fix\n')


def _preset_rs_gpu_cgroup_memory_accounting(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/cgroup-accounting.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/cgroup-accounting.conf', '# broken configuration for gpu-cgroup-memory-accounting\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_iommu_passthrough(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/iommu.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/iommu.conf', '# broken configuration for gpu-driver-iommu-passthrough\n# this file needs the documented fix\n')


def _preset_rs_gpu_batch_scheduler_binding(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/scheduler-binding.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/scheduler-binding.conf', '# broken configuration for gpu-batch-scheduler-binding\n# this file needs the documented fix\n')


def _preset_rs_gpu_driver_runtime_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/runtime-compat.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/runtime-compat.conf', '# broken configuration for gpu-driver-runtime-mismatch\n# this file needs the documented fix\n')


def _preset_rs_gpu_mig_not_enabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/mig-enable.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/mig-enable.conf', '# broken configuration for gpu-mig-not-enabled\n# this file needs the documented fix\n')


def _preset_rs_gpu_telemetry_export_tls(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/telemetry-tls.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/telemetry-tls.conf', '# broken configuration for gpu-telemetry-export-tls\n# this file needs the documented fix\n')


def _preset_rs_baremetal_ipmi_lan_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/lan-channel.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/lan-channel.cfg', '# broken configuration for baremetal-ipmi-lan-disabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_bmc_default_creds(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/credentials.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/credentials.cfg', '# broken configuration for baremetal-bmc-default-creds\n# this file needs the documented fix\n')


def _preset_rs_baremetal_sel_full(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/sel-policy.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/sel-policy.cfg', '# broken configuration for baremetal-sel-full\n# this file needs the documented fix\n')


def _preset_rs_baremetal_raid_write_cache(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/raid/cache-policy.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/raid/cache-policy.cfg', '# broken configuration for baremetal-raid-write-cache\n# this file needs the documented fix\n')


def _preset_rs_baremetal_raid_rebuild_rate(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/raid/rebuild-rate.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/raid/rebuild-rate.cfg', '# broken configuration for baremetal-raid-rebuild-rate\n# this file needs the documented fix\n')


def _preset_rs_baremetal_disk_predictive_fail(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/smart/policy.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/smart/policy.cfg', '# broken configuration for baremetal-disk-predictive-fail\n# this file needs the documented fix\n')


def _preset_rs_baremetal_nic_teaming_mode(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/network/teaming.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/network/teaming.cfg', '# broken configuration for baremetal-nic-teaming-mode\n# this file needs the documented fix\n')


def _preset_rs_baremetal_pxe_vlan_tag(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/pxe/vlan.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/pxe/vlan.cfg', '# broken configuration for baremetal-pxe-vlan-tag\n# this file needs the documented fix\n')


def _preset_rs_baremetal_power_redundancy(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/power-policy.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/power-policy.cfg', '# broken configuration for baremetal-power-redundancy\n# this file needs the documented fix\n')


def _preset_rs_baremetal_cpu_cstates_latency(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/cstates.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/cstates.cfg', '# broken configuration for baremetal-cpu-cstates-latency\n# this file needs the documented fix\n')


def _preset_rs_baremetal_turbo_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/turbo.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/turbo.cfg', '# broken configuration for baremetal-turbo-disabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_memory_mismatch_rank(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/memory.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/memory.cfg', '# broken configuration for baremetal-memory-mismatch-rank\n# this file needs the documented fix\n')


def _preset_rs_baremetal_ras_features_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/ras.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/ras.cfg', '# broken configuration for baremetal-ras-features-off\n# this file needs the documented fix\n')


def _preset_rs_baremetal_sr_iov_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/sriov.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/sriov.cfg', '# broken configuration for baremetal-sr-iov-disabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_watchdog_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/watchdog.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/watchdog.cfg', '# broken configuration for baremetal-watchdog-disabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_clock_source_unstable(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/clocksource.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/clocksource.cfg', '# broken configuration for baremetal-clock-source-unstable\n# this file needs the documented fix\n')


def _preset_rs_baremetal_hugepages_not_reserved(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/hugepages.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/hugepages.cfg', '# broken configuration for baremetal-hugepages-not-reserved\n# this file needs the documented fix\n')


def _preset_rs_baremetal_iommu_not_enabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/iommu.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/iommu.cfg', '# broken configuration for baremetal-iommu-not-enabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_boot_mode_legacy(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/bootmode.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/bootmode.cfg', '# broken configuration for baremetal-boot-mode-legacy\n# this file needs the documented fix\n')


def _preset_rs_baremetal_tpm_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/tpm.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/tpm.cfg', '# broken configuration for baremetal-tpm-disabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_pcie_bifurcation(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/pcie-bifurcation.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/pcie-bifurcation.cfg', '# broken configuration for baremetal-pcie-bifurcation\n# this file needs the documented fix\n')


def _preset_rs_baremetal_fan_zone_mapping(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/fan-zones.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/fan-zones.cfg', '# broken configuration for baremetal-fan-zone-mapping\n# this file needs the documented fix\n')


def _preset_rs_baremetal_ntp_bmc_drift(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/ntp.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/ntp.cfg', '# broken configuration for baremetal-ntp-bmc-drift\n# this file needs the documented fix\n')


def _preset_rs_baremetal_disk_spindown_aggressive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/storage/power-policy.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/storage/power-policy.cfg', '# broken configuration for baremetal-disk-spindown-aggressive\n# this file needs the documented fix\n')


def _preset_rs_baremetal_numa_balancing_vm(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/numa-balancing.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/numa-balancing.cfg', '# broken configuration for baremetal-numa-balancing-vm\n# this file needs the documented fix\n')


def _preset_rs_baremetal_firmware_rollback_protection(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/firmware/rollback-policy.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/firmware/rollback-policy.cfg', '# broken configuration for baremetal-firmware-rollback-protection\n# this file needs the documented fix\n')


def _preset_rs_baremetal_console_redirect(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/serial-console.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/serial-console.cfg', '# broken configuration for baremetal-console-redirect\n# this file needs the documented fix\n')


def _preset_rs_baremetal_disk_cache_flush(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/storage/cache-flush.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/storage/cache-flush.cfg', '# broken configuration for baremetal-disk-cache-flush\n# this file needs the documented fix\n')


def _preset_rs_baremetal_power_cap_enforced(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/power-cap.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/power-cap.cfg', '# broken configuration for baremetal-power-cap-enforced\n# this file needs the documented fix\n')


def _preset_rs_baremetal_sata_mode_ide(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/sata-mode.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/sata-mode.cfg', '# broken configuration for baremetal-sata-mode-ide\n# this file needs the documented fix\n')


def _preset_rs_baremetal_aspm_power_save(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/aspm.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/aspm.cfg', '# broken configuration for baremetal-aspm-power-save\n# this file needs the documented fix\n')


def _preset_rs_baremetal_memory_scrub_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bios/memory-scrub.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bios/memory-scrub.cfg', '# broken configuration for baremetal-memory-scrub-disabled\n# this file needs the documented fix\n')


def _preset_rs_baremetal_boot_watchdog_timeout(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/boot-watchdog.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/boot-watchdog.cfg', '# broken configuration for baremetal-boot-watchdog-timeout\n# this file needs the documented fix\n')


def _preset_rs_baremetal_thermal_shutdown_threshold(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/bmc/thermal-shutdown.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/bmc/thermal-shutdown.cfg', '# broken configuration for baremetal-thermal-shutdown-threshold\n# this file needs the documented fix\n')


def _preset_rs_baremetal_lldp_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/network/lldp.cfg')
    if d:
        state._mkdir(d)
    state._write_file('/etc/network/lldp.cfg', '# broken configuration for baremetal-lldp-disabled\n# this file needs the documented fix\n')


def _preset_rs_rhel_sssd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['sssd'] = SimService('sssd', active="failed", enabled="enabled", description='sssd service')


def _preset_rs_rhel_cockpit_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['cockpit'] = SimService('cockpit', active="failed", enabled="enabled", description='cockpit service')


def _preset_rs_rhel_tuned_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['tuned'] = SimService('tuned', active="failed", enabled="enabled", description='tuned service')


def _preset_rs_rhel_firewalld_restart_loop(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['firewalld'] = SimService('firewalld', active="failed", enabled="enabled", description='firewalld service')


def _preset_rs_rhel_multipathd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['multipathd'] = SimService('multipathd', active="failed", enabled="enabled", description='multipathd service')


def _preset_rs_rhel_iscsid_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['iscsid'] = SimService('iscsid', active="failed", enabled="enabled", description='iscsid service')


def _preset_rs_rhel_libvirtd_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['libvirtd'] = SimService('libvirtd', active="failed", enabled="enabled", description='libvirtd service')


def _preset_rs_rhel_postfix_down(state: RHELOSState) -> None:
    from .rhel_os import SimService
    state.services['postfix'] = SimService('postfix', active="failed", enabled="enabled", description='postfix service')


def _preset_rs_rhel_dnf_gpgcheck_off(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/dnf/dnf.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/dnf/dnf.conf', '# broken configuration for rhel-dnf-gpgcheck-off\n# this file needs the documented fix\n')


def _preset_rs_rhel_yum_proxy_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/dnf/dnf.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/dnf/dnf.conf', '# broken configuration for rhel-yum-proxy-wrong\n# this file needs the documented fix\n')


def _preset_rs_rhel_chrony_conf_no_servers(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/chrony.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/chrony.conf', '# broken configuration for rhel-chrony-conf-no-servers\n# this file needs the documented fix\n')


def _preset_rs_rhel_nsswitch_misordered(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/nsswitch.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/nsswitch.conf', '# broken configuration for rhel-nsswitch-misordered\n# this file needs the documented fix\n')


def _preset_rs_rhel_pam_faillock_lockout(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/security/faillock.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/security/faillock.conf', '# broken configuration for rhel-pam-faillock-lockout\n# this file needs the documented fix\n')


def _preset_rs_rhel_selinux_permissive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/selinux/config')
    if d:
        state._mkdir(d)
    state._write_file('/etc/selinux/config', '# broken configuration for rhel-selinux-permissive\n# this file needs the documented fix\n')


def _preset_rs_rhel_grub_cmdline_missing_param(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/default/grub')
    if d:
        state._mkdir(d)
    state._write_file('/etc/default/grub', '# broken configuration for rhel-grub-cmdline-missing-param\n# this file needs the documented fix\n')


def _preset_rs_rhel_systemd_resolved_conf(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/systemd/resolved.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/systemd/resolved.conf', '# broken configuration for rhel-systemd-resolved-conf\n# this file needs the documented fix\n')


def _preset_rs_rhel_fapolicyd_blocking(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/fapolicyd/fapolicyd.rules')
    if d:
        state._mkdir(d)
    state._write_file('/etc/fapolicyd/fapolicyd.rules', '# broken configuration for rhel-fapolicyd-blocking\n# this file needs the documented fix\n')


def _preset_rs_rhel_kdump_not_configured(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/kdump.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/kdump.conf', '# broken configuration for rhel-kdump-not-configured\n# this file needs the documented fix\n')


def _preset_rs_rhel_rsyslog_remote_forward(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/rsyslog.d/remote.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/rsyslog.d/remote.conf', '# broken configuration for rhel-rsyslog-remote-forward\n# this file needs the documented fix\n')


def _preset_rs_rhel_auditd_rules_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/audit/rules.d/audit.rules')
    if d:
        state._mkdir(d)
    state._write_file('/etc/audit/rules.d/audit.rules', '# broken configuration for rhel-auditd-rules-missing\n# this file needs the documented fix\n')


def _preset_rs_rhel_ntp_iburst_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/chrony.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/chrony.conf', '# broken configuration for rhel-ntp-iburst-missing\n# this file needs the documented fix\n')


def _preset_rs_rhel_sysctl_somaxconn_low(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/sysctl.d/99-net.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/sysctl.d/99-net.conf', '# broken configuration for rhel-sysctl-somaxconn-low\n# this file needs the documented fix\n')


def _preset_rs_rhel_sysctl_swappiness(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/sysctl.d/99-vm.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/sysctl.d/99-vm.conf', '# broken configuration for rhel-sysctl-swappiness\n# this file needs the documented fix\n')


def _preset_rs_rhel_logind_killuser(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/systemd/logind.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/systemd/logind.conf', '# broken configuration for rhel-logind-killuser\n# this file needs the documented fix\n')


def _preset_rs_rhel_coredump_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/systemd/coredump.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/systemd/coredump.conf', '# broken configuration for rhel-coredump-disabled\n# this file needs the documented fix\n')


def _preset_rs_rhel_firewalld_zone_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/firewalld/zones/public.xml')
    if d:
        state._mkdir(d)
    state._write_file('/etc/firewalld/zones/public.xml', '# broken configuration for rhel-firewalld-zone-wrong\n# this file needs the documented fix\n')


def _preset_rs_rhel_crypto_policy_legacy(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/crypto-policies/config')
    if d:
        state._mkdir(d)
    state._write_file('/etc/crypto-policies/config', '# broken configuration for rhel-crypto-policy-legacy\n# this file needs the documented fix\n')


def _preset_rs_rhel_sshd_maxstartups(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/ssh/sshd_config.d/limits.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/ssh/sshd_config.d/limits.conf', '# broken configuration for rhel-sshd-maxstartups\n# this file needs the documented fix\n')


def _preset_rs_rhel_systemd_oomd_killing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/systemd/oomd.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/systemd/oomd.conf', '# broken configuration for rhel-systemd-oomd-killing\n# this file needs the documented fix\n')


def _preset_rs_rhel_dnf_automatic_misconfig(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/dnf/automatic.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/dnf/automatic.conf', '# broken configuration for rhel-dnf-automatic-misconfig\n# this file needs the documented fix\n')




# ── Wave 4 (html bulk + toppers) ──

def _preset_rs_html_img_missing_alt(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/gallery.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/gallery.html', '# broken configuration for html-img-missing-alt\n# this file needs the documented fix\n')


def _preset_rs_html_table_no_headers(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/data.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/data.html', '# broken configuration for html-table-no-headers\n# this file needs the documented fix\n')


def _preset_rs_html_heading_skip(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/article.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/article.html', '# broken configuration for html-heading-skip\n# this file needs the documented fix\n')


def _preset_rs_html_lang_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-lang-missing\n# this file needs the documented fix\n')


def _preset_rs_html_button_vs_div(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/menu.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/menu.html', '# broken configuration for html-button-vs-div\n# this file needs the documented fix\n')


def _preset_rs_html_form_no_action(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/signup.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/signup.html', '# broken configuration for html-form-no-action\n# this file needs the documented fix\n')


def _preset_rs_html_form_no_name(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/login.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/login.html', '# broken configuration for html-form-no-name\n# this file needs the documented fix\n')


def _preset_rs_html_required_validation(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/order.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/order.html', '# broken configuration for html-required-validation\n# this file needs the documented fix\n')


def _preset_rs_html_deprecated_tags(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/old.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/old.html', '# broken configuration for html-deprecated-tags\n# this file needs the documented fix\n')


def _preset_rs_html_inline_styles(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/styled.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/styled.html', '# broken configuration for html-inline-styles\n# this file needs the documented fix\n')


def _preset_rs_html_missing_favicon(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-missing-favicon\n# this file needs the documented fix\n')


def _preset_rs_html_open_graph_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-open-graph-missing\n# this file needs the documented fix\n')


def _preset_rs_html_canonical_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/page.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/page.html', '# broken configuration for html-canonical-missing\n# this file needs the documented fix\n')


def _preset_rs_html_robots_noindex(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/landing.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/landing.html', '# broken configuration for html-robots-noindex\n# this file needs the documented fix\n')


def _preset_rs_html_mixed_content(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/secure.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/secure.html', '# broken configuration for html-mixed-content\n# this file needs the documented fix\n')


def _preset_rs_html_target_blank_noopener(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/links.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/links.html', '# broken configuration for html-target-blank-noopener\n# this file needs the documented fix\n')


def _preset_rs_html_autocomplete_password(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/account.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/account.html', '# broken configuration for html-autocomplete-password\n# this file needs the documented fix\n')


def _preset_rs_html_iframe_no_sandbox(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/embed.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/embed.html', '# broken configuration for html-iframe-no-sandbox\n# this file needs the documented fix\n')


def _preset_rs_html_script_blocking_render(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/index.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/index.html', '# broken configuration for html-script-blocking-render\n# this file needs the documented fix\n')


def _preset_rs_html_no_lazy_loading(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/feed.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/feed.html', '# broken configuration for html-no-lazy-loading\n# this file needs the documented fix\n')


def _preset_rs_html_missing_width_height(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/news.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/news.html', '# broken configuration for html-missing-width-height\n# this file needs the documented fix\n')


def _preset_rs_html_font_no_display_swap(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/typography.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/typography.html', '# broken configuration for html-font-no-display-swap\n# this file needs the documented fix\n')


def _preset_rs_html_srcset_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/responsive.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/responsive.html', '# broken configuration for html-srcset-missing\n# this file needs the documented fix\n')


def _preset_rs_html_nested_interactive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/card.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/card.html', '# broken configuration for html-nested-interactive\n# this file needs the documented fix\n')


def _preset_rs_html_unclosed_tags(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/broken.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/broken.html', '# broken configuration for html-unclosed-tags\n# this file needs the documented fix\n')


def _preset_rs_html_entity_encoding(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/comments.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/comments.html', '# broken configuration for html-entity-encoding\n# this file needs the documented fix\n')


def _preset_rs_html_base_tag_wrong(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/app.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/app.html', '# broken configuration for html-base-tag-wrong\n# this file needs the documented fix\n')


def _preset_rs_html_meta_refresh_redirect(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/redirect.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/redirect.html', '# broken configuration for html-meta-refresh-redirect\n# this file needs the documented fix\n')


def _preset_rs_html_table_layout(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/layout.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/layout.html', '# broken configuration for html-table-layout\n# this file needs the documented fix\n')


def _preset_rs_html_aria_misuse(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/widget.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/widget.html', '# broken configuration for html-aria-misuse\n# this file needs the documented fix\n')


def _preset_rs_html_form_label_wrap(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/search.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/search.html', '# broken configuration for html-form-label-wrap\n# this file needs the documented fix\n')


def _preset_rs_html_viewport_user_scalable(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/mobile.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/mobile.html', '# broken configuration for html-viewport-user-scalable\n# this file needs the documented fix\n')


def _preset_rs_html_duplicate_title(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/dup.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/dup.html', '# broken configuration for html-duplicate-title\n# this file needs the documented fix\n')


def _preset_rs_html_empty_link_text(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/icons.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/icons.html', '# broken configuration for html-empty-link-text\n# this file needs the documented fix\n')


def _preset_rs_html_form_get_sensitive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/reset.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/reset.html', '# broken configuration for html-form-get-sensitive\n# this file needs the documented fix\n')


def _preset_rs_html_charset_late(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/late.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/late.html', '# broken configuration for html-charset-late\n# this file needs the documented fix\n')


def _preset_rs_html_noscript_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/spa.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/spa.html', '# broken configuration for html-noscript-missing\n# this file needs the documented fix\n')


def _preset_rs_html_print_stylesheet(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/invoice.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/invoice.html', '# broken configuration for html-print-stylesheet\n# this file needs the documented fix\n')


def _preset_rs_html_svg_no_title(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/chart.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/chart.html', '# broken configuration for html-svg-no-title\n# this file needs the documented fix\n')


def _preset_rs_html_preload_misconfigured(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/fast.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/fast.html', '# broken configuration for html-preload-misconfigured\n# this file needs the documented fix\n')


def _preset_rs_html_doctype_xhtml(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/www/html/legacy-xhtml.html')
    if d:
        state._mkdir(d)
    state._write_file('/var/www/html/legacy-xhtml.html', '# broken configuration for html-doctype-xhtml\n# this file needs the documented fix\n')


def _preset_rs_gpu_dmabuf_permissions(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/gpu/dmabuf-access.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/gpu/dmabuf-access.conf', '# broken configuration for gpu-dmabuf-permissions\n# this file needs the documented fix\n')


def _preset_rs_rhel_needs_restarting(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/etc/rhel-patch-policy.conf')
    if d:
        state._mkdir(d)
    state._write_file('/etc/rhel-patch-policy.conf', '# broken configuration for rhel-needs-restarting\n# this file needs the documented fix\n')


def _preset_rs_db_postgres_effective_cache_size(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/var/lib/pgsql/data/postgresql.conf')
    if d:
        state._mkdir(d)
    state._write_file('/var/lib/pgsql/data/postgresql.conf', '# broken configuration for db-postgres-effective-cache-size\n# this file needs the documented fix\n')


_PRESETS: dict[str, callable] = {
    'html-img-missing-alt': _preset_rs_html_img_missing_alt,
    'html-table-no-headers': _preset_rs_html_table_no_headers,
    'html-heading-skip': _preset_rs_html_heading_skip,
    'html-lang-missing': _preset_rs_html_lang_missing,
    'html-button-vs-div': _preset_rs_html_button_vs_div,
    'html-form-no-action': _preset_rs_html_form_no_action,
    'html-form-no-name': _preset_rs_html_form_no_name,
    'html-required-validation': _preset_rs_html_required_validation,
    'html-deprecated-tags': _preset_rs_html_deprecated_tags,
    'html-inline-styles': _preset_rs_html_inline_styles,
    'html-missing-favicon': _preset_rs_html_missing_favicon,
    'html-open-graph-missing': _preset_rs_html_open_graph_missing,
    'html-canonical-missing': _preset_rs_html_canonical_missing,
    'html-robots-noindex': _preset_rs_html_robots_noindex,
    'html-mixed-content': _preset_rs_html_mixed_content,
    'html-target-blank-noopener': _preset_rs_html_target_blank_noopener,
    'html-autocomplete-password': _preset_rs_html_autocomplete_password,
    'html-iframe-no-sandbox': _preset_rs_html_iframe_no_sandbox,
    'html-script-blocking-render': _preset_rs_html_script_blocking_render,
    'html-no-lazy-loading': _preset_rs_html_no_lazy_loading,
    'html-missing-width-height': _preset_rs_html_missing_width_height,
    'html-font-no-display-swap': _preset_rs_html_font_no_display_swap,
    'html-srcset-missing': _preset_rs_html_srcset_missing,
    'html-nested-interactive': _preset_rs_html_nested_interactive,
    'html-unclosed-tags': _preset_rs_html_unclosed_tags,
    'html-entity-encoding': _preset_rs_html_entity_encoding,
    'html-base-tag-wrong': _preset_rs_html_base_tag_wrong,
    'html-meta-refresh-redirect': _preset_rs_html_meta_refresh_redirect,
    'html-table-layout': _preset_rs_html_table_layout,
    'html-aria-misuse': _preset_rs_html_aria_misuse,
    'html-form-label-wrap': _preset_rs_html_form_label_wrap,
    'html-viewport-user-scalable': _preset_rs_html_viewport_user_scalable,
    'html-duplicate-title': _preset_rs_html_duplicate_title,
    'html-empty-link-text': _preset_rs_html_empty_link_text,
    'html-form-get-sensitive': _preset_rs_html_form_get_sensitive,
    'html-charset-late': _preset_rs_html_charset_late,
    'html-noscript-missing': _preset_rs_html_noscript_missing,
    'html-print-stylesheet': _preset_rs_html_print_stylesheet,
    'html-svg-no-title': _preset_rs_html_svg_no_title,
    'html-preload-misconfigured': _preset_rs_html_preload_misconfigured,
    'html-doctype-xhtml': _preset_rs_html_doctype_xhtml,
    'gpu-dmabuf-permissions': _preset_rs_gpu_dmabuf_permissions,
    'rhel-needs-restarting': _preset_rs_rhel_needs_restarting,
    'db-postgres-effective-cache-size': _preset_rs_db_postgres_effective_cache_size,
    'db-mysql-replica-stopped': _preset_rs_db_mysql_replica_stopped,
    'db-postgres-standby-stopped': _preset_rs_db_postgres_standby_stopped,
    'db-redis-sentinel-down': _preset_rs_db_redis_sentinel_down,
    'db-etcd-down': _preset_rs_db_etcd_down,
    'db-influxdb-down': _preset_rs_db_influxdb_down,
    'db-elasticsearch-down': _preset_rs_db_elasticsearch_down,
    'db-couchdb-down': _preset_rs_db_couchdb_down,
    'db-neo4j-down': _preset_rs_db_neo4j_down,
    'db-clickhouse-down': _preset_rs_db_clickhouse_down,
    'db-postgres-shared-buffers-low': _preset_rs_db_postgres_shared_buffers_low,
    'db-postgres-work-mem-low': _preset_rs_db_postgres_work_mem_low,
    'db-mysql-innodb-buffer-pool': _preset_rs_db_mysql_innodb_buffer_pool,
    'db-mysql-slow-query-log-off': _preset_rs_db_mysql_slow_query_log_off,
    'db-postgres-log-min-duration': _preset_rs_db_postgres_log_min_duration,
    'db-mongodb-no-auth': _preset_rs_db_mongodb_no_auth,
    'db-redis-no-password': _preset_rs_db_redis_no_password,
    'db-postgres-ssl-disabled': _preset_rs_db_postgres_ssl_disabled,
    'db-mysql-sql-mode-loose': _preset_rs_db_mysql_sql_mode_loose,
    'db-postgres-autovacuum-off': _preset_rs_db_postgres_autovacuum_off,
    'db-mysql-max-allowed-packet': _preset_rs_db_mysql_max_allowed_packet,
    'db-postgres-statement-timeout': _preset_rs_db_postgres_statement_timeout,
    'db-mariadb-galera-config': _preset_rs_db_mariadb_galera_config,
    'db-redis-rdb-aof-conflict': _preset_rs_db_redis_rdb_aof_conflict,
    'db-postgres-hot-standby-off': _preset_rs_db_postgres_hot_standby_off,
    'db-mysql-binlog-disabled': _preset_rs_db_mysql_binlog_disabled,
    'db-postgres-wal-level-minimal': _preset_rs_db_postgres_wal_level_minimal,
    'db-mongodb-oplog-too-small': _preset_rs_db_mongodb_oplog_too_small,
    'db-mysql-tmp-table-disk': _preset_rs_db_mysql_tmp_table_disk,
    'db-postgres-checkpoint-spikes': _preset_rs_db_postgres_checkpoint_spikes,
    'db-redis-thp-warning': _preset_rs_db_redis_thp_warning,
    'db-mysql-skip-name-resolve': _preset_rs_db_mysql_skip_name_resolve,
    'db-postgres-connection-leak': _preset_rs_db_postgres_connection_leak,
    'ansible-handler-missing': _preset_rs_ansible_handler_missing,
    'ansible-tags-misused': _preset_rs_ansible_tags_misused,
    'ansible-delegate-to-wrong': _preset_rs_ansible_delegate_to_wrong,
    'ansible-serial-too-high': _preset_rs_ansible_serial_too_high,
    'ansible-block-rescue-missing': _preset_rs_ansible_block_rescue_missing,
    'ansible-vault-id-wrong': _preset_rs_ansible_vault_id_wrong,
    'ansible-inventory-group-vars': _preset_rs_ansible_inventory_group_vars,
    'ansible-fact-caching-stale': _preset_rs_ansible_fact_caching_stale,
    'ansible-become-user-wrong': _preset_rs_ansible_become_user_wrong,
    'ansible-template-trim-blocks': _preset_rs_ansible_template_trim_blocks,
    'ansible-with-items-deprecated': _preset_rs_ansible_with_items_deprecated,
    'ansible-changed-when-wrong': _preset_rs_ansible_changed_when_wrong,
    'ansible-failed-when-wrong': _preset_rs_ansible_failed_when_wrong,
    'ansible-async-poll-wrong': _preset_rs_ansible_async_poll_wrong,
    'ansible-uri-validate-certs': _preset_rs_ansible_uri_validate_certs,
    'ansible-package-name-wrong': _preset_rs_ansible_package_name_wrong,
    'ansible-service-enabled-missing': _preset_rs_ansible_service_enabled_missing,
    'ansible-copy-vs-template': _preset_rs_ansible_copy_vs_template,
    'ansible-lineinfile-regex': _preset_rs_ansible_lineinfile_regex,
    'ansible-mount-fstab-missing': _preset_rs_ansible_mount_fstab_missing,
    'ansible-cron-special-time': _preset_rs_ansible_cron_special_time,
    'ansible-firewalld-permanent': _preset_rs_ansible_firewalld_permanent,
    'ansible-selinux-context': _preset_rs_ansible_selinux_context,
    'ansible-user-ssh-key': _preset_rs_ansible_user_ssh_key,
    'ansible-template-validate': _preset_rs_ansible_template_validate,
    'ansible-handler-flush': _preset_rs_ansible_handler_flush,
    'ansible-register-loop-results': _preset_rs_ansible_register_loop_results,
    'ansible-set-fact-scope': _preset_rs_ansible_set_fact_scope,
    'ansible-import-vs-include': _preset_rs_ansible_import_vs_include,
    'ansible-callback-plugin': _preset_rs_ansible_callback_plugin,
    'ansible-strategy-free-unsafe': _preset_rs_ansible_strategy_free_unsafe,
    'ansible-connection-local-wrong': _preset_rs_ansible_connection_local_wrong,
    'ansible-env-var-not-passed': _preset_rs_ansible_env_var_not_passed,
    'ansible-retries-until': _preset_rs_ansible_retries_until,
    'ansible-yaml-indentation': _preset_rs_ansible_yaml_indentation,
    'shell-set-e-not-set': _preset_rs_shell_set_e_not_set,
    'shell-tmpfile-race': _preset_rs_shell_tmpfile_race,
    'shell-eval-injection': _preset_rs_shell_eval_injection,
    'shell-cd-without-check': _preset_rs_shell_cd_without_check,
    'shell-glob-no-match': _preset_rs_shell_glob_no_match,
    'shell-arithmetic-leading-zero': _preset_rs_shell_arithmetic_leading_zero,
    'shell-here-string-quoting': _preset_rs_shell_here_string_quoting,
    'shell-exit-code-masked': _preset_rs_shell_exit_code_masked,
    'shell-ifs-not-reset': _preset_rs_shell_ifs_not_reset,
    'shell-subshell-var-lost': _preset_rs_shell_subshell_var_lost,
    'shell-test-string-vs-int': _preset_rs_shell_test_string_vs_int,
    'shell-find-exec-unsafe': _preset_rs_shell_find_exec_unsafe,
    'shell-readarray-missing': _preset_rs_shell_readarray_missing,
    'shell-trap-err-missing': _preset_rs_shell_trap_err_missing,
    'shell-lockfile-stale': _preset_rs_shell_lockfile_stale,
    'shell-date-format-locale': _preset_rs_shell_date_format_locale,
    'shell-printf-vs-echo': _preset_rs_shell_printf_vs_echo,
    'shell-unset-var-default': _preset_rs_shell_unset_var_default,
    'shell-pipe-to-while-fd': _preset_rs_shell_pipe_to_while_fd,
    'shell-mktemp-cleanup': _preset_rs_shell_mktemp_cleanup,
    'shell-array-quoting': _preset_rs_shell_array_quoting,
    'shell-command-substitution-newline': _preset_rs_shell_command_substitution_newline,
    'shell-getopt-long': _preset_rs_shell_getopt_long,
    'shell-numeric-bc-scale': _preset_rs_shell_numeric_bc_scale,
    'shell-source-relative-path': _preset_rs_shell_source_relative_path,
    'shell-background-wait': _preset_rs_shell_background_wait,
    'shell-echo-password': _preset_rs_shell_echo_password,
    'shell-rm-rf-variable': _preset_rs_shell_rm_rf_variable,
    'shell-curl-no-fail': _preset_rs_shell_curl_no_fail,
    'shell-tar-absolute-paths': _preset_rs_shell_tar_absolute_paths,
    'shell-no-shebang': _preset_rs_shell_no_shebang,
    'shell-stderr-stdout-merge': _preset_rs_shell_stderr_stdout_merge,
    'shell-exit-trap-overwrite': _preset_rs_shell_exit_trap_overwrite,
    'shell-positional-shift': _preset_rs_shell_positional_shift,
    'shell-process-sub-portability': _preset_rs_shell_process_sub_portability,
    'shell-readonly-reassign': _preset_rs_shell_readonly_reassign,
    'docker-daemon-down': _preset_rs_docker_daemon_down,
    'docker-docker-socket-proxy-down': _preset_rs_docker_docker_socket_proxy_down,
    'docker-compose-env-missing': _preset_rs_docker_compose_env_missing,
    'docker-compose-depends-on': _preset_rs_docker_compose_depends_on,
    'docker-healthcheck-wrong': _preset_rs_docker_healthcheck_wrong,
    'docker-restart-policy-missing': _preset_rs_docker_restart_policy_missing,
    'docker-memory-limit-oom': _preset_rs_docker_memory_limit_oom,
    'docker-cpu-limit-throttle': _preset_rs_docker_cpu_limit_throttle,
    'docker-bind-mount-wrong': _preset_rs_docker_bind_mount_wrong,
    'docker-volume-permissions': _preset_rs_docker_volume_permissions,
    'docker-network-alias-missing': _preset_rs_docker_network_alias_missing,
    'docker-ports-conflict': _preset_rs_docker_ports_conflict,
    'docker-dockerfile-cache-bust': _preset_rs_docker_dockerfile_cache_bust,
    'docker-dockerfile-root-user': _preset_rs_docker_dockerfile_root_user,
    'docker-multistage-bloat': _preset_rs_docker_multistage_bloat,
    'docker-entrypoint-shell-form': _preset_rs_docker_entrypoint_shell_form,
    'docker-no-dockerignore': _preset_rs_docker_no_dockerignore,
    'docker-secrets-in-env': _preset_rs_docker_secrets_in_env,
    'docker-compose-version-deprecated': _preset_rs_docker_compose_version_deprecated,
    'docker-logging-driver-blocking': _preset_rs_docker_logging_driver_blocking,
    'docker-iptables-disabled': _preset_rs_docker_iptables_disabled,
    'docker-mtu-mismatch': _preset_rs_docker_mtu_mismatch,
    'docker-default-ulimit-low': _preset_rs_docker_default_ulimit_low,
    'docker-live-restore-off': _preset_rs_docker_live_restore_off,
    'docker-registry-mirror-missing': _preset_rs_docker_registry_mirror_missing,
    'docker-compose-network-external': _preset_rs_docker_compose_network_external,
    'docker-build-arg-undefined': _preset_rs_docker_build_arg_undefined,
    'docker-healthcheck-interval-aggressive': _preset_rs_docker_healthcheck_interval_aggressive,
    'docker-compose-restart-loop': _preset_rs_docker_compose_restart_loop,
    'docker-overlay-network-encryption': _preset_rs_docker_overlay_network_encryption,
    'docker-tmpfs-missing': _preset_rs_docker_tmpfs_missing,
    'docker-cap-add-excessive': _preset_rs_docker_cap_add_excessive,
    'docker-readonly-rootfs-missing': _preset_rs_docker_readonly_rootfs_missing,
    'docker-network-subnet-overlap': _preset_rs_docker_network_subnet_overlap,
    'docker-init-missing-zombies': _preset_rs_docker_init_missing_zombies,
    'docker-build-platform-mismatch': _preset_rs_docker_build_platform_mismatch,
    'gpu-driver-version-pin': _preset_rs_gpu_driver_version_pin,
    'gpu-cuda-toolkit-path': _preset_rs_gpu_cuda_toolkit_path,
    'gpu-nccl-ib-disabled': _preset_rs_gpu_nccl_ib_disabled,
    'gpu-mig-profile-wrong': _preset_rs_gpu_mig_profile_wrong,
    'gpu-dcgm-exporter-config': _preset_rs_gpu_dcgm_exporter_config,
    'gpu-xid-errors-logging': _preset_rs_gpu_xid_errors_logging,
    'gpu-cgroups-v2-mismatch': _preset_rs_gpu_cgroups_v2_mismatch,
    'gpu-topology-numa-pinning': _preset_rs_gpu_topology_numa_pinning,
    'gpu-power-cap-cluster': _preset_rs_gpu_power_cap_cluster,
    'gpu-vbios-mismatch': _preset_rs_gpu_vbios_mismatch,
    'gpu-thermal-throttle-airflow': _preset_rs_gpu_thermal_throttle_airflow,
    'gpu-shared-memory-limit': _preset_rs_gpu_shared_memory_limit,
    'gpu-driver-mode-wddm': _preset_rs_gpu_driver_mode_wddm,
    'gpu-cuda-arch-mismatch': _preset_rs_gpu_cuda_arch_mismatch,
    'gpu-persistence-daemon-config': _preset_rs_gpu_persistence_daemon_config,
    'gpu-rocm-kfd-permissions': _preset_rs_gpu_rocm_kfd_permissions,
    'gpu-mps-pipe-dir': _preset_rs_gpu_mps_pipe_dir,
    'gpu-fan-policy-passive': _preset_rs_gpu_fan_policy_passive,
    'gpu-clock-locked-low': _preset_rs_gpu_clock_locked_low,
    'gpu-ecc-pages-retired': _preset_rs_gpu_ecc_pages_retired,
    'gpu-container-toolkit-runtime': _preset_rs_gpu_container_toolkit_runtime,
    'gpu-driver-blacklist-nouveau': _preset_rs_gpu_driver_blacklist_nouveau,
    'gpu-cuda-mps-memory-limit': _preset_rs_gpu_cuda_mps_memory_limit,
    'gpu-p2p-disabled': _preset_rs_gpu_p2p_disabled,
    'gpu-driver-fabric-mismatch': _preset_rs_gpu_driver_fabric_mismatch,
    'gpu-monitoring-interval': _preset_rs_gpu_monitoring_interval,
    'gpu-driver-debug-logging': _preset_rs_gpu_driver_debug_logging,
    'gpu-affinity-hyperthreading': _preset_rs_gpu_affinity_hyperthreading,
    'gpu-nvlink-degraded': _preset_rs_gpu_nvlink_degraded,
    'gpu-driver-secureboot': _preset_rs_gpu_driver_secureboot,
    'gpu-cgroup-memory-accounting': _preset_rs_gpu_cgroup_memory_accounting,
    'gpu-driver-iommu-passthrough': _preset_rs_gpu_driver_iommu_passthrough,
    'gpu-batch-scheduler-binding': _preset_rs_gpu_batch_scheduler_binding,
    'gpu-driver-runtime-mismatch': _preset_rs_gpu_driver_runtime_mismatch,
    'gpu-mig-not-enabled': _preset_rs_gpu_mig_not_enabled,
    'gpu-telemetry-export-tls': _preset_rs_gpu_telemetry_export_tls,
    'baremetal-ipmi-lan-disabled': _preset_rs_baremetal_ipmi_lan_disabled,
    'baremetal-bmc-default-creds': _preset_rs_baremetal_bmc_default_creds,
    'baremetal-sel-full': _preset_rs_baremetal_sel_full,
    'baremetal-raid-write-cache': _preset_rs_baremetal_raid_write_cache,
    'baremetal-raid-rebuild-rate': _preset_rs_baremetal_raid_rebuild_rate,
    'baremetal-disk-predictive-fail': _preset_rs_baremetal_disk_predictive_fail,
    'baremetal-nic-teaming-mode': _preset_rs_baremetal_nic_teaming_mode,
    'baremetal-pxe-vlan-tag': _preset_rs_baremetal_pxe_vlan_tag,
    'baremetal-power-redundancy': _preset_rs_baremetal_power_redundancy,
    'baremetal-cpu-cstates-latency': _preset_rs_baremetal_cpu_cstates_latency,
    'baremetal-turbo-disabled': _preset_rs_baremetal_turbo_disabled,
    'baremetal-memory-mismatch-rank': _preset_rs_baremetal_memory_mismatch_rank,
    'baremetal-ras-features-off': _preset_rs_baremetal_ras_features_off,
    'baremetal-sr-iov-disabled': _preset_rs_baremetal_sr_iov_disabled,
    'baremetal-watchdog-disabled': _preset_rs_baremetal_watchdog_disabled,
    'baremetal-clock-source-unstable': _preset_rs_baremetal_clock_source_unstable,
    'baremetal-hugepages-not-reserved': _preset_rs_baremetal_hugepages_not_reserved,
    'baremetal-iommu-not-enabled': _preset_rs_baremetal_iommu_not_enabled,
    'baremetal-boot-mode-legacy': _preset_rs_baremetal_boot_mode_legacy,
    'baremetal-tpm-disabled': _preset_rs_baremetal_tpm_disabled,
    'baremetal-pcie-bifurcation': _preset_rs_baremetal_pcie_bifurcation,
    'baremetal-fan-zone-mapping': _preset_rs_baremetal_fan_zone_mapping,
    'baremetal-ntp-bmc-drift': _preset_rs_baremetal_ntp_bmc_drift,
    'baremetal-disk-spindown-aggressive': _preset_rs_baremetal_disk_spindown_aggressive,
    'baremetal-numa-balancing-vm': _preset_rs_baremetal_numa_balancing_vm,
    'baremetal-firmware-rollback-protection': _preset_rs_baremetal_firmware_rollback_protection,
    'baremetal-console-redirect': _preset_rs_baremetal_console_redirect,
    'baremetal-disk-cache-flush': _preset_rs_baremetal_disk_cache_flush,
    'baremetal-power-cap-enforced': _preset_rs_baremetal_power_cap_enforced,
    'baremetal-sata-mode-ide': _preset_rs_baremetal_sata_mode_ide,
    'baremetal-aspm-power-save': _preset_rs_baremetal_aspm_power_save,
    'baremetal-memory-scrub-disabled': _preset_rs_baremetal_memory_scrub_disabled,
    'baremetal-boot-watchdog-timeout': _preset_rs_baremetal_boot_watchdog_timeout,
    'baremetal-thermal-shutdown-threshold': _preset_rs_baremetal_thermal_shutdown_threshold,
    'baremetal-lldp-disabled': _preset_rs_baremetal_lldp_disabled,
    'rhel-sssd-down': _preset_rs_rhel_sssd_down,
    'rhel-cockpit-down': _preset_rs_rhel_cockpit_down,
    'rhel-tuned-down': _preset_rs_rhel_tuned_down,
    'rhel-firewalld-restart-loop': _preset_rs_rhel_firewalld_restart_loop,
    'rhel-multipathd-down': _preset_rs_rhel_multipathd_down,
    'rhel-iscsid-down': _preset_rs_rhel_iscsid_down,
    'rhel-libvirtd-down': _preset_rs_rhel_libvirtd_down,
    'rhel-postfix-down': _preset_rs_rhel_postfix_down,
    'rhel-dnf-gpgcheck-off': _preset_rs_rhel_dnf_gpgcheck_off,
    'rhel-yum-proxy-wrong': _preset_rs_rhel_yum_proxy_wrong,
    'rhel-chrony-conf-no-servers': _preset_rs_rhel_chrony_conf_no_servers,
    'rhel-nsswitch-misordered': _preset_rs_rhel_nsswitch_misordered,
    'rhel-pam-faillock-lockout': _preset_rs_rhel_pam_faillock_lockout,
    'rhel-selinux-permissive': _preset_rs_rhel_selinux_permissive,
    'rhel-grub-cmdline-missing-param': _preset_rs_rhel_grub_cmdline_missing_param,
    'rhel-systemd-resolved-conf': _preset_rs_rhel_systemd_resolved_conf,
    'rhel-fapolicyd-blocking': _preset_rs_rhel_fapolicyd_blocking,
    'rhel-kdump-not-configured': _preset_rs_rhel_kdump_not_configured,
    'rhel-rsyslog-remote-forward': _preset_rs_rhel_rsyslog_remote_forward,
    'rhel-auditd-rules-missing': _preset_rs_rhel_auditd_rules_missing,
    'rhel-ntp-iburst-missing': _preset_rs_rhel_ntp_iburst_missing,
    'rhel-sysctl-somaxconn-low': _preset_rs_rhel_sysctl_somaxconn_low,
    'rhel-sysctl-swappiness': _preset_rs_rhel_sysctl_swappiness,
    'rhel-logind-killuser': _preset_rs_rhel_logind_killuser,
    'rhel-coredump-disabled': _preset_rs_rhel_coredump_disabled,
    'rhel-firewalld-zone-wrong': _preset_rs_rhel_firewalld_zone_wrong,
    'rhel-crypto-policy-legacy': _preset_rs_rhel_crypto_policy_legacy,
    'rhel-sshd-maxstartups': _preset_rs_rhel_sshd_maxstartups,
    'rhel-systemd-oomd-killing': _preset_rs_rhel_systemd_oomd_killing,
    'rhel-dnf-automatic-misconfig': _preset_rs_rhel_dnf_automatic_misconfig,
    'db-redis-down': _preset_rs_db_redis_down,
    'db-mariadb-down': _preset_rs_db_mariadb_down,
    'db-mongodb-down': _preset_rs_db_mongodb_down,
    'db-cassandra-down': _preset_rs_db_cassandra_down,
    'db-pgbouncer-down': _preset_rs_db_pgbouncer_down,
    'db-postgres-pg-hba-deny': _preset_rs_db_postgres_pg_hba_deny,
    'db-mysql-bind-address': _preset_rs_db_mysql_bind_address,
    'db-redis-maxmemory-noevict': _preset_rs_db_redis_maxmemory_noevict,
    'db-postgres-fsync-off': _preset_rs_db_postgres_fsync_off,
    'ansible-become-password-missing': _preset_rs_ansible_become_password_missing,
    'ansible-jinja-template-error': _preset_rs_ansible_jinja_template_error,
    'ansible-loop-wrong-var': _preset_rs_ansible_loop_wrong_var,
    'ansible-when-condition-bug': _preset_rs_ansible_when_condition_bug,
    'ansible-galaxy-role-missing': _preset_rs_ansible_galaxy_role_missing,
    'ansible-vars-precedence-bug': _preset_rs_ansible_vars_precedence_bug,
    'ansible-no-log-leaking-secret': _preset_rs_ansible_no_log_leaking_secret,
    'shell-rsync-delete-danger': _preset_rs_shell_rsync_delete_danger,
    'shell-cron-path-missing': _preset_rs_shell_cron_path_missing,
    'shell-pipefail-missing': _preset_rs_shell_pipefail_missing,
    'shell-word-splitting-bug': _preset_rs_shell_word_splitting_bug,
    'shell-signal-not-trapped': _preset_rs_shell_signal_not_trapped,
    'shell-readonly-clobber': _preset_rs_shell_readonly_clobber,
    'shell-arith-division-zero': _preset_rs_shell_arith_division_zero,
    'shell-getopts-parsing': _preset_rs_shell_getopts_parsing,
    'html-broken-doctype': _preset_rs_html_broken_doctype,
    'html-missing-charset': _preset_rs_html_missing_charset,
    'html-broken-relative-links': _preset_rs_html_broken_relative_links,
    'html-inaccessible-form': _preset_rs_html_inaccessible_form,
    'html-meta-viewport-missing': _preset_rs_html_meta_viewport_missing,
    'html-csp-blocking-assets': _preset_rs_html_csp_blocking_assets,
    'html-duplicate-ids': _preset_rs_html_duplicate_ids,
    'rhel-chronyd-down': _preset_rs_rhel_chronyd_down,
    'rhel-rsyslog-down': _preset_rs_rhel_rsyslog_down,
    'rhel-firewalld-down': _preset_rs_rhel_firewalld_down,
    'rhel-auditd-down': _preset_rs_rhel_auditd_down,
    'rhel-nfs-server-down': _preset_rs_rhel_nfs_server_down,
    'rhel-subscription-manager-config': _preset_rs_rhel_subscription_manager_config,
    'rhel-tuned-wrong-profile': _preset_rs_rhel_tuned_wrong_profile,
    'rhel-selinux-booleans': _preset_rs_rhel_selinux_booleans,
    'rhel-grub-default-target': _preset_rs_rhel_grub_default_target,
    'gpu-mps-not-enabled': _preset_rs_gpu_mps_not_enabled,
    'gpu-ecc-disabled': _preset_rs_gpu_ecc_disabled,
    'gpu-persistence-mode-off': _preset_rs_gpu_persistence_mode_off,
    'gpu-cgroup-device-denied': _preset_rs_gpu_cgroup_device_denied,
    'gpu-clock-throttled-power': _preset_rs_gpu_clock_throttled_power,
    'gpu-fabric-manager-down': _preset_rs_gpu_fabric_manager_down,
    'baremetal-bios-boot-order': _preset_rs_baremetal_bios_boot_order,
    'baremetal-bmc-snmp-misconfig': _preset_rs_baremetal_bmc_snmp_misconfig,
    'baremetal-fan-curve-aggressive': _preset_rs_baremetal_fan_curve_aggressive,
    'baremetal-numa-not-enabled': _preset_rs_baremetal_numa_not_enabled,
    'baremetal-firmware-mismatch': _preset_rs_baremetal_firmware_mismatch,
    'baremetal-secure-boot-blocking': _preset_rs_baremetal_secure_boot_blocking,
    'docker-containerd-down': _preset_rs_docker_containerd_down,
    'docker-daemon-json-invalid': _preset_rs_docker_daemon_json_invalid,
    'docker-storage-driver-wrong': _preset_rs_docker_storage_driver_wrong,
    'docker-insecure-registry': _preset_rs_docker_insecure_registry,
    'docker-default-bridge-subnet': _preset_rs_docker_default_bridge_subnet,
    'docker-logging-unbounded': _preset_rs_docker_logging_unbounded,
    'docker-userns-remap-broken': _preset_rs_docker_userns_remap_broken,
    'linux-haproxy-down': _preset_rs_linux_haproxy_down,
    'linux-named-down': _preset_rs_linux_named_down,
    'linux-memcached-down': _preset_rs_linux_memcached_down,
    'linux-rabbitmq-down': _preset_rs_linux_rabbitmq_down,
    'linux-nginx-stream-proxy-down': _preset_rs_linux_nginx_stream_proxy_down,
    'linux-fstab-bad-option': _preset_rs_linux_fstab_bad_option,
    'linux-limits-conf-too-low': _preset_rs_linux_limits_conf_too_low,
    'linux-resolv-conf-wrong': _preset_rs_linux_resolv_conf_wrong,
    'linux-sudoers-syntax-error': _preset_rs_linux_sudoers_syntax_error,
    'linux-logrotate-misconfig': _preset_rs_linux_logrotate_misconfig,
    'linux-crontab-syntax-error': _preset_rs_linux_crontab_syntax_error,
    'linux-journald-storage-volatile': _preset_rs_linux_journald_storage_volatile,
    'linux-sshd-permitroot-hardening': _preset_rs_linux_sshd_permitroot_hardening,
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
    # Cross-technology (VMware ⇄ terminal) scenarios
    "linux-lvm-extend-vmware-disk-rescan": _preset_cross_lvm_vmware_rescan,
    "linux-lvm-extend-vmware-disk-reboot": _preset_cross_lvm_vmware_reboot,
    "linux-datastore-full-add-disk-vmware": _preset_cross_datastore_full,
    "linux-server-hung-needs-vmware-reset": _preset_cross_server_hung,
    "linux-nic-add-vmware-rescan": _preset_cross_nic_add,
    "linux-default-gateway-missing": _preset_default_gateway_missing,
    "linux-sysctl-ip-forward": _preset_sysctl_ip_forward,
    "linux-kernel-module-not-loaded": _preset_kernel_module_not_loaded,
    "db-postgres-max-connections": _preset_postgres_max_connections,
    "db-mysql-table-crashed": _preset_mysql_table_crashed,
    "db-postgres-disk-full-archive": _preset_postgres_disk_full_archive,
    # Storage / partition (fdisk / parted / LVM)
    "linux-fdisk-partition-mkfs-mount": _preset_fdisk_partition_mkfs,
    "linux-fdisk-two-part-lvm-create-mount-and-fs": _preset_fdisk_two_part_lvm_and_fs,
    "linux-parted-gpt-mkfs-mount": _preset_parted_gpt_mkfs,
    "linux-lvm-grow-xfs-growfs-mount": _preset_lvm_grow_xfs,
    "linux-fdisk-corrupt-partition-table-disk-missing-rescan-recovery": _preset_fdisk_corrupt_table_recovery,
    "linux-fstab-mount-by-uuid-mkfs-mount": _preset_fstab_mount_by_uuid,
    "linux-fdisk-swap-partition-mkswap-swapon": _preset_fdisk_swap_partition,
    "linux-autofs-automount-home": _preset_autofs_automount,
    # Linux-admin topic coverage
    "linux-at-job-not-scheduled": _preset_at_job_not_scheduled,
    "linux-systemd-timer-not-firing": _preset_systemd_timer_not_firing,
    "linux-nftables-port-blocked": _preset_nftables_port_blocked,
    "linux-quota-not-enforced": _preset_quota_not_enforced,
    "linux-renice-runaway-process-priority": _preset_renice_runaway_priority,
}




# === Java/Security simulation-marker scenarios (generated) ===

def _preset_jsm_actuator_health_failing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for actuator-health-failing\n# this file needs the documented fix\n')


def _preset_jsm_sim_java_classpath(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/run-app.sh')
    if d:
        state._mkdir(d)
    state._write_file('/app/run-app.sh', '# broken configuration for sim-java-classpath\n# this file needs the documented fix\n')


def _preset_jsm_sim_java_compile_error(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/App.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/App.java', '# broken configuration for sim-java-compile-error\n# this file needs the documented fix\n')


def _preset_jsm_container_startup_probe(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/k8s/deployment.yaml')
    if d:
        state._mkdir(d)
    state._write_file('/app/k8s/deployment.yaml', '# broken configuration for container-startup-probe\n# this file needs the documented fix\n')


def _preset_jsm_sim_java_deadlock(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/TransferService.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/TransferService.java', '# broken configuration for sim-java-deadlock\n# this file needs the documented fix\n')


def _preset_jsm_gc_pause_excessive(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/jvm.options')
    if d:
        state._mkdir(d)
    state._write_file('/app/jvm.options', '# broken configuration for gc-pause-excessive\n# this file needs the documented fix\n')


def _preset_jsm_gradle_build_cache_corrupt(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/root/.gradle/gradle.properties')
    if d:
        state._mkdir(d)
    state._write_file('/root/.gradle/gradle.properties', '# broken configuration for gradle-build-cache-corrupt\n# this file needs the documented fix\n')


def _preset_jsm_jacoco_coverage_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/pom.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/pom.xml', '# broken configuration for jacoco-coverage-missing\n# this file needs the documented fix\n')


def _preset_jsm_jpa_n_plus_1(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for jpa-n-plus-1\n# this file needs the documented fix\n')


def _preset_jsm_junit_flaky_test(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/test/java/com/example/OrderServiceTest.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/test/java/com/example/OrderServiceTest.java', '# broken configuration for junit-flaky-test\n# this file needs the documented fix\n')


def _preset_jsm_jvm_heap_oom(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/jvm.options')
    if d:
        state._mkdir(d)
    state._write_file('/app/jvm.options', '# broken configuration for jvm-heap-oom\n# this file needs the documented fix\n')


def _preset_jsm_jvm_metaspace_oom(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/jvm.options')
    if d:
        state._mkdir(d)
    state._write_file('/app/jvm.options', '# broken configuration for jvm-metaspace-oom\n# this file needs the documented fix\n')


def _preset_jsm_jwt_token_expired(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for jwt-token-expired\n# this file needs the documented fix\n')


def _preset_jsm_kafka_producer_timeout(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for kafka-producer-timeout\n# this file needs the documented fix\n')


def _preset_jsm_log4j_config_missing(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/log4j2.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/log4j2.xml', '# broken configuration for log4j-config-missing\n# this file needs the documented fix\n')


def _preset_jsm_sim_java_maven_fail(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/pom.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/pom.xml', '# broken configuration for sim-java-maven-fail\n# this file needs the documented fix\n')


def _preset_jsm_maven_dependency_conflict(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/pom.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/pom.xml', '# broken configuration for maven-dependency-conflict\n# this file needs the documented fix\n')


def _preset_jsm_sim_java_oom(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/jvm.options')
    if d:
        state._mkdir(d)
    state._write_file('/app/jvm.options', '# broken configuration for sim-java-oom\n# this file needs the documented fix\n')


def _preset_jsm_rabbitmq_consumer_stuck(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for rabbitmq-consumer-stuck\n# this file needs the documented fix\n')


def _preset_jsm_redis_jedis_connection(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for redis-jedis-connection\n# this file needs the documented fix\n')


def _preset_jsm_spring_boot_startup_fail(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for spring-boot-startup-fail\n# this file needs the documented fix\n')


def _preset_jsm_spring_db_connection_pool(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for spring-db-connection-pool\n# this file needs the documented fix\n')


def _preset_jsm_sim_java_spring_fail(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.properties')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.properties', '# broken configuration for sim-java-spring-fail\n# this file needs the documented fix\n')


def _preset_jsm_ssl_handshake_failed(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for ssl-handshake-failed\n# this file needs the documented fix\n')


def _preset_jsm_thread_deadlock(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/CacheManager.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/CacheManager.java', '# broken configuration for thread-deadlock\n# this file needs the documented fix\n')


def _preset_jsm_tomcat_max_threads(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for tomcat-max-threads\n# this file needs the documented fix\n')


def _preset_jsm_java_gradle_wrapper_version_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/gradle/wrapper/gradle-wrapper.properties')
    if d:
        state._mkdir(d)
    state._write_file('/app/gradle/wrapper/gradle-wrapper.properties', '# broken configuration for java-gradle-wrapper-version-mismatch\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_circular_dependency(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/config/BeanConfig.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/config/BeanConfig.java', '# broken configuration for java-spring-circular-dependency\n# this file needs the documented fix\n')


def _preset_jsm_java_logback_rolling_policy(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/logback-spring.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/logback-spring.xml', '# broken configuration for java-logback-rolling-policy\n# this file needs the documented fix\n')


def _preset_jsm_java_maven_surefire_no_tests(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/pom.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/pom.xml', '# broken configuration for java-maven-surefire-no-tests\n# this file needs the documented fix\n')


def _preset_jsm_java_jdbc_pool_leak(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/repo/ReportDao.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/repo/ReportDao.java', '# broken configuration for java-jdbc-pool-leak\n# this file needs the documented fix\n')


def _preset_jsm_java_hibernate_lazy_init_exception(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-hibernate-lazy-init-exception\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_profile_not_active(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-spring-profile-not-active\n# this file needs the documented fix\n')


def _preset_jsm_java_jackson_serialization_loop(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/model/Order.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/model/Order.java', '# broken configuration for java-jackson-serialization-loop\n# this file needs the documented fix\n')


def _preset_jsm_java_runtime_version_mismatch(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/pom.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/pom.xml', '# broken configuration for java-runtime-version-mismatch\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_cors_misconfigured(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/config/WebConfig.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/config/WebConfig.java', '# broken configuration for java-spring-cors-misconfigured\n# this file needs the documented fix\n')


def _preset_jsm_java_maven_shade_plugin_manifest(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/pom.xml')
    if d:
        state._mkdir(d)
    state._write_file('/app/pom.xml', '# broken configuration for java-maven-shade-plugin-manifest\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_scheduler_not_running(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/jobs/CleanupJob.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/jobs/CleanupJob.java', '# broken configuration for java-spring-scheduler-not-running\n# this file needs the documented fix\n')


def _preset_jsm_java_direct_buffer_oom(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/jvm.options')
    if d:
        state._mkdir(d)
    state._write_file('/app/jvm.options', '# broken configuration for java-direct-buffer-oom\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_actuator_exposed(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-spring-actuator-exposed\n# this file needs the documented fix\n')


def _preset_jsm_java_keystore_wrong_password(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-keystore-wrong-password\n# this file needs the documented fix\n')


def _preset_jsm_java_gradle_dependency_conflict(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/build.gradle')
    if d:
        state._mkdir(d)
    state._write_file('/app/build.gradle', '# broken configuration for java-gradle-dependency-conflict\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_transaction_rollback(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/service/PaymentService.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/service/PaymentService.java', '# broken configuration for java-spring-transaction-rollback\n# this file needs the documented fix\n')


def _preset_jsm_java_ssl_protocol_disabled(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-ssl-protocol-disabled\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_property_placeholder(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-spring-property-placeholder\n# this file needs the documented fix\n')


def _preset_jsm_java_stack_overflow_recursion(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/java/com/example/util/TreeWalker.java')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/java/com/example/util/TreeWalker.java', '# broken configuration for java-stack-overflow-recursion\n# this file needs the documented fix\n')


def _preset_jsm_java_spring_bean_override_conflict(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-spring-bean-override-conflict\n# this file needs the documented fix\n')


def _preset_jsm_java_truststore_expired_cert(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/application.yml')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/application.yml', '# broken configuration for java-truststore-expired-cert\n# this file needs the documented fix\n')


def _preset_jsm_java_gradle_test_task_skipped(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/build.gradle')
    if d:
        state._mkdir(d)
    state._write_file('/app/build.gradle', '# broken configuration for java-gradle-test-task-skipped\n# this file needs the documented fix\n')


def _preset_jsm_security_java_log4shell_jndi_lookup(state: RHELOSState) -> None:
    import os
    d = os.path.dirname('/app/src/main/resources/log4j2.component.properties')
    if d:
        state._mkdir(d)
    state._write_file('/app/src/main/resources/log4j2.component.properties', '# broken configuration for security-java-log4shell-jndi-lookup\n# this file needs the documented fix\n')


# ── P4: Cross-technology scenarios (two technologies, one broken handoff) ─────
# Each lab frames a real two-technology workflow (provision->configure,
# build->migrate, app<->network, db<->storage, security<->host). The broken
# state is a misconfigured handoff artifact (a config file the integration
# target owns) or a failed integration service. Validation reuses the existing
# fail-closed validators with NO new validator code:
#   • marker scenarios → check.sh runs `grep -q FIXED-OK <file>`; the preset
#     writes that file WITHOUT the sentinel, so a fresh lab is fail-closed and
#     only the genuine documented fix (e2e_simulation_fix `_RS_MARKER_FIX`)
#     rewrites it WITH `# FIXED-OK`.
#   • service scenarios → check.sh runs `systemctl is-active <unit>`; the preset
#     registers the integration unit as failed/disabled.
# These presets are registered in _PRESETS by EXACT slug so the generic
# substring fallbacks (gpu/ansible/docker/postgres/etc.) never shadow them.


def _preset_xtech_marker(state: RHELOSState, path: str, slug: str) -> None:
    """Write the cross-tech handoff artifact in a broken state (no FIXED-OK)."""
    import os

    d = os.path.dirname(path)
    if d:
        state._mkdir(d)
    state._write_file(
        path,
        f"# broken configuration for {slug}\n"
        "# the cross-technology handoff is misconfigured here\n"
        "# this file needs the documented fix\n",
    )


def _preset_xtech_terraform_to_ansible_inventory(state: RHELOSState) -> None:
    """Terraform->Ansible: the rendered inventory is stale/malformed."""
    state.hostname = "automation-01"
    _preset_xtech_marker(
        state,
        "/home/ansible/inventory/provisioned_hosts.ini",
        "linux-terraform-output-to-ansible-inventory",
    )


def _preset_xtech_docker_to_k8s_manifest(state: RHELOSState) -> None:
    """Docker->Kubernetes: the converted Deployment manifest is invalid."""
    # The original compose file is present for reference; the converted manifest
    # is broken (compose-only keys, bind mount, no requests) and is what's graded.
    state._mkdir("/opt/app")
    state._write_file(
        "/opt/app/docker-compose.yml",
        "services:\n  api:\n    image: registry.local/api:1.4.2\n"
        "    container_name: api\n    ports:\n      - \"8080:8080\"\n"
        "    volumes:\n      - ./config:/etc/api\n",
    )
    _preset_xtech_marker(
        state,
        "/opt/app/k8s/deployment.yaml",
        "docker-compose-to-k8s-manifest-migration",
    )


def _preset_xtech_network_bond_vlan(state: RHELOSState) -> None:
    """Networking<->Linux: bond uses the wrong mode and lacks the tagged VLAN."""
    _preset_xtech_marker(
        state,
        "/etc/sysconfig/network-scripts/ifcfg-bond0",
        "networking-linux-bond-vlan-trunk",
    )


def _preset_xtech_db_tablespace_new_disk(state: RHELOSState) -> None:
    """Database<->Linux storage: tablespace volume full; config not reconciled."""
    from .rhel_os import SimService

    state.services["postgresql"] = SimService(
        "postgresql", active="failed", enabled="enabled", description="PostgreSQL",
    )
    # A spare disk exists on the Linux side for the new tablespace location.
    state.add_block_device("/dev/sdc", "100G", "disk", present=True)
    _preset_xtech_marker(
        state,
        "/var/lib/pgsql/data/postgresql.conf",
        "db-postgres-tablespace-new-disk",
    )


def _preset_xtech_security_ssh_hardening(state: RHELOSState) -> None:
    """Security<->Linux: the CIS SSH drop-in still sets the insecure values."""
    import os

    state.hostname = "bastion-01"
    path = "/etc/ssh/sshd_config.d/50-cis.conf"
    d = os.path.dirname(path)
    if d:
        state._mkdir(d)
    state._write_file(
        path,
        f"# broken configuration for security-linux-ssh-cis-hardening\n"
        "PermitRootLogin yes\n"
        "PasswordAuthentication yes\n"
        "# weak crypto still negotiable; this file needs the documented fix\n",
    )


def _preset_xtech_ansible_to_k8s_kubeconfig(state: RHELOSState) -> None:
    """Ansible->Kubernetes: the deploy play points at a bad kubeconfig/ns/api."""
    state.hostname = "ansible-control"
    _preset_xtech_marker(
        state,
        "/home/ansible/k8s-deploy.yml",
        "ansible-deploy-to-k8s-kubeconfig",
    )


def _preset_xtech_terraform_to_vmware_clone(state: RHELOSState) -> None:
    """Terraform->VMware: the vSphere clone references non-existent inventory."""
    state.hostname = "terraform-ws"
    _preset_xtech_marker(
        state,
        "/root/iac/vsphere-vm.tf",
        "terraform-vmware-vm-clone-from-template",
    )


def _preset_xtech_docker_systemd_stack(state: RHELOSState) -> None:
    """Docker->Linux/systemd: the unit that manages the compose stack is failed."""
    from .rhel_os import SimService

    state._mkdir("/opt/app")
    if "docker" not in state.services:
        state.services["docker"] = SimService(
            "docker", active="active", enabled="enabled", description="Docker Application Container Engine")
    state.services["appstack"] = SimService(
        "appstack", active="failed", enabled="disabled",
        description="Containerized application stack (docker compose)")
    state._write_file(
        "/etc/systemd/system/appstack.service",
        "# broken configuration: wrong Type/ordering so the unit exits immediately\n"
        "[Unit]\nDescription=Containerized application stack (docker compose)\n\n"
        "[Service]\nExecStart=/usr/bin/docker compose -f /opt/app/docker-compose.yml up -d\n\n"
        "[Install]\nWantedBy=multi-user.target\n",
    )


def _preset_xtech_network_firewalld_app(state: RHELOSState) -> None:
    """Networking<->Security: the custom firewalld service XML is malformed."""
    import os

    state.hostname = "api-edge-01"
    path = "/etc/firewalld/services/app8443.xml"
    d = os.path.dirname(path)
    if d:
        state._mkdir(d)
    state._write_file(
        path,
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<!-- broken configuration for networking-firewalld-app-reachability -->\n"
        "<service>\n  <short>app8443</short>\n"
        "  <port protocol=\"udp\" port=\"443\"\n"  # wrong proto/port + unclosed tag
        "</service>\n",
    )


def _preset_xtech_gpu_k8s_device_plugin(state: RHELOSState) -> None:
    """GPU<->Kubernetes: the NVIDIA device-plugin DaemonSet manifest is broken."""
    _preset_xtech_marker(
        state,
        "/etc/nvidia-container-runtime/k8s-device-plugin.yaml",
        "gpu-k8s-device-plugin-daemonset",
    )


def _preset_xtech_db_replication_network(state: RHELOSState) -> None:
    """Database<->Networking: replica config clashes + path to primary is wrong."""
    import os

    state.hostname = "db-replica-02"
    path = "/etc/my.cnf.d/replication.cnf"
    d = os.path.dirname(path)
    if d:
        state._mkdir(d)
    state._write_file(
        path,
        "# broken configuration for db-mysql-replication-network-firewall\n"
        "[mysqld]\nserver-id=1\n"            # clashes with the primary's server-id
        "# master_host points at a stale primary; 3306 path not open\n"
        "# this file needs the documented fix\n",
    )


def _preset_xtech_devops_ci_to_ansible_cd(state: RHELOSState) -> None:
    """DevOps/CI->Ansible: the release play uses wrong var/URL/host group."""
    state.hostname = "ci-control"
    _preset_xtech_marker(
        state,
        "/home/ansible/cd-playbook.yml",
        "devops-ci-to-ansible-cd-handoff",
    )


_XTECH_PRESETS = {
    "linux-terraform-output-to-ansible-inventory": _preset_xtech_terraform_to_ansible_inventory,
    "docker-compose-to-k8s-manifest-migration": _preset_xtech_docker_to_k8s_manifest,
    "networking-linux-bond-vlan-trunk": _preset_xtech_network_bond_vlan,
    "db-postgres-tablespace-new-disk": _preset_xtech_db_tablespace_new_disk,
    "security-linux-ssh-cis-hardening": _preset_xtech_security_ssh_hardening,
    "ansible-deploy-to-k8s-kubeconfig": _preset_xtech_ansible_to_k8s_kubeconfig,
    "terraform-vmware-vm-clone-from-template": _preset_xtech_terraform_to_vmware_clone,
    "docker-handoff-systemd-managed-stack": _preset_xtech_docker_systemd_stack,
    "networking-firewalld-app-reachability": _preset_xtech_network_firewalld_app,
    "gpu-k8s-device-plugin-daemonset": _preset_xtech_gpu_k8s_device_plugin,
    "db-mysql-replication-network-firewall": _preset_xtech_db_replication_network,
    "devops-ci-to-ansible-cd-handoff": _preset_xtech_devops_ci_to_ansible_cd,
}

_JSM_PRESETS = {
    'actuator-health-failing': _preset_jsm_actuator_health_failing,
    'sim-java-classpath': _preset_jsm_sim_java_classpath,
    'sim-java-compile-error': _preset_jsm_sim_java_compile_error,
    'container-startup-probe': _preset_jsm_container_startup_probe,
    'sim-java-deadlock': _preset_jsm_sim_java_deadlock,
    'gc-pause-excessive': _preset_jsm_gc_pause_excessive,
    'gradle-build-cache-corrupt': _preset_jsm_gradle_build_cache_corrupt,
    'jacoco-coverage-missing': _preset_jsm_jacoco_coverage_missing,
    'jpa-n-plus-1': _preset_jsm_jpa_n_plus_1,
    'junit-flaky-test': _preset_jsm_junit_flaky_test,
    'jvm-heap-oom': _preset_jsm_jvm_heap_oom,
    'jvm-metaspace-oom': _preset_jsm_jvm_metaspace_oom,
    'jwt-token-expired': _preset_jsm_jwt_token_expired,
    'kafka-producer-timeout': _preset_jsm_kafka_producer_timeout,
    'log4j-config-missing': _preset_jsm_log4j_config_missing,
    'sim-java-maven-fail': _preset_jsm_sim_java_maven_fail,
    'maven-dependency-conflict': _preset_jsm_maven_dependency_conflict,
    'sim-java-oom': _preset_jsm_sim_java_oom,
    'rabbitmq-consumer-stuck': _preset_jsm_rabbitmq_consumer_stuck,
    'redis-jedis-connection': _preset_jsm_redis_jedis_connection,
    'spring-boot-startup-fail': _preset_jsm_spring_boot_startup_fail,
    'spring-db-connection-pool': _preset_jsm_spring_db_connection_pool,
    'sim-java-spring-fail': _preset_jsm_sim_java_spring_fail,
    'ssl-handshake-failed': _preset_jsm_ssl_handshake_failed,
    'thread-deadlock': _preset_jsm_thread_deadlock,
    'tomcat-max-threads': _preset_jsm_tomcat_max_threads,
    'java-gradle-wrapper-version-mismatch': _preset_jsm_java_gradle_wrapper_version_mismatch,
    'java-spring-circular-dependency': _preset_jsm_java_spring_circular_dependency,
    'java-logback-rolling-policy': _preset_jsm_java_logback_rolling_policy,
    'java-maven-surefire-no-tests': _preset_jsm_java_maven_surefire_no_tests,
    'java-jdbc-pool-leak': _preset_jsm_java_jdbc_pool_leak,
    'java-hibernate-lazy-init-exception': _preset_jsm_java_hibernate_lazy_init_exception,
    'java-spring-profile-not-active': _preset_jsm_java_spring_profile_not_active,
    'java-jackson-serialization-loop': _preset_jsm_java_jackson_serialization_loop,
    'java-runtime-version-mismatch': _preset_jsm_java_runtime_version_mismatch,
    'java-spring-cors-misconfigured': _preset_jsm_java_spring_cors_misconfigured,
    'java-maven-shade-plugin-manifest': _preset_jsm_java_maven_shade_plugin_manifest,
    'java-spring-scheduler-not-running': _preset_jsm_java_spring_scheduler_not_running,
    'java-direct-buffer-oom': _preset_jsm_java_direct_buffer_oom,
    'java-spring-actuator-exposed': _preset_jsm_java_spring_actuator_exposed,
    'java-keystore-wrong-password': _preset_jsm_java_keystore_wrong_password,
    'java-gradle-dependency-conflict': _preset_jsm_java_gradle_dependency_conflict,
    'java-spring-transaction-rollback': _preset_jsm_java_spring_transaction_rollback,
    'java-ssl-protocol-disabled': _preset_jsm_java_ssl_protocol_disabled,
    'java-spring-property-placeholder': _preset_jsm_java_spring_property_placeholder,
    'java-stack-overflow-recursion': _preset_jsm_java_stack_overflow_recursion,
    'java-spring-bean-override-conflict': _preset_jsm_java_spring_bean_override_conflict,
    'java-truststore-expired-cert': _preset_jsm_java_truststore_expired_cert,
    'java-gradle-test-task-skipped': _preset_jsm_java_gradle_test_task_skipped,
    'security-java-log4shell-jndi-lookup': _preset_jsm_security_java_log4shell_jndi_lookup,
}

_PRESETS.update(_JSM_PRESETS)
_PRESETS.update(_XTECH_PRESETS)

# ── Monitoring (Grafana + Prometheus) marker presets (generated) ──
# Each writes the scenario's config file in a BROKEN state (no FIXED-OK). The
# e2e fix rewrites it WITH the marker; validation.py's generic `grep -q FIXED-OK`
# branch reads the real file → fail-closed until the documented fix is applied.
try:
    from .monitoring_presets import MONITORING_PRESETS as _MONITORING_PRESETS
    _PRESETS.update(_MONITORING_PRESETS)
except Exception:  # pragma: no cover - defensive: never break preset loading
    pass

try:
    from .complete_tech_presets import COMPLETE_TECH_PRESETS as _COMPLETE_TECH_PRESETS
    _PRESETS.update(_COMPLETE_TECH_PRESETS)
except Exception:  # pragma: no cover
    pass

# ── Flagship real-simulation presets (override the marker preset by exact slug) ──
# These upgrade a curated set of academy labs from `grep FIXED-OK` markers to a
# genuinely broken OS state (failed service, missing user, closed firewall port,
# stopped compose stack) validated against the real state. Merged LAST so they
# win over the generated COMPLETE_TECH_PRESETS marker for the same slug.
try:
    from .flagship_presets import FLAGSHIP_PRESETS as _FLAGSHIP_PRESETS
    _PRESETS.update(_FLAGSHIP_PRESETS)
except Exception:  # pragma: no cover
    pass

# ── Academy real-state service presets (override COMPLETE_TECH markers) ──
try:
    from .academy_service_presets import ACADEMY_SERVICE_PRESETS as _ACADEMY_SERVICE_PRESETS
    _PRESETS.update(_ACADEMY_SERVICE_PRESETS)
except Exception:  # pragma: no cover
    pass


def _mtu_mismatch_marker(state) -> None:
    """networking-mtu-mismatch: the iptables/MTU fix can't be introspected, so
    seed a broken marker (no FIXED-OK) and grade on the learner attesting the fix."""
    state._mkdir("/opt/fixitlab/networking")
    state._write_file(
        "/opt/fixitlab/networking/mtu-mismatch.conf",
        "# broken configuration for networking-mtu-mismatch\n"
        "# tunnel MTU still 1500 and no TCP MSS clamping — large packets are dropped\n"
        "# this file needs the documented fix\n",
    )


_PRESETS["networking-mtu-mismatch"] = _mtu_mismatch_marker
