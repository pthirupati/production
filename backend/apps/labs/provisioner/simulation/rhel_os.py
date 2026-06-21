"""Virtual RHEL 9 OS state — filesystem, users, services, processes."""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field


@dataclass
class SimUser:
    username: str
    uid: int
    gid: int
    home: str
    shell: str = "/bin/bash"
    gecos: str = ""
    locked: bool = False


@dataclass
class SimService:
    name: str
    active: str = "inactive"  # active | inactive | failed
    enabled: str = "disabled"
    description: str = ""
    loaded: str = "loaded"
    sub_state: str = "dead"
    unit_file: str = ""


@dataclass
class SimProcess:
    pid: int
    user: str
    cpu: float
    mem: float
    command: str


@dataclass
class SimBlockDevice:
    """A whole disk, partition, or LV as seen by lsblk/blkid/mkfs/mount."""
    name: str                       # /dev/sdb, /dev/sdb1, /dev/mapper/rhel-data
    size: str = "50G"
    dev_type: str = "disk"          # disk | part | lvm
    parent: str = ""                # parent device name for partitions
    fstype: str = ""                # xfs | ext4 | swap | "" (unformatted)
    uuid: str = ""                  # populated when formatted
    mountpoint: str = ""            # current mount target ("" = unmounted)
    present: bool = True            # False until a SCSI rescan reveals it
    removable: bool = False
    needs_reboot: bool = False      # hidden disk a rescan won't reveal — needs reboot


class RHELOSState:
    """Mutable in-memory RHEL-like system state."""

    def __init__(self, hostname: str = "rhel-sim", scenario_slug: str = ""):
        self.hostname = hostname
        self.scenario_slug = scenario_slug
        self.kernel = "5.14.0-362.el9.x86_64"
        self.os_release = "Red Hat Enterprise Linux 9.3 (Plow)"
        self.current_user = "root"
        self.cwd = "/root"
        self.uid_counter = 1000
        self.pid_counter = 2000
        self.last_exit_code = 0
        self.boot_time = time.time() - 3600
        self.vfs: dict[str, str | dict] = {}
        self.users: dict[str, SimUser] = {}
        self.groups: dict[str, list[int]] = {"root": [0]}
        self.services: dict[str, SimService] = {}
        self.processes: list[SimProcess] = []
        self.env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "HOME": "/root",
            "SHELL": "/bin/bash",
            "USER": "root",
            "HOSTNAME": hostname,
        }
        self.dmesg_extra: list[str] = []
        self.gpu_healthy: bool = True
        self.initramfs_fixed: bool = False
        self.grub_fixed: bool = False
        self.mbr_fixed: bool = False
        self.kernel_fixed: bool = False
        self.patching_done: bool = False
        self.precheck_ran: bool = False
        self.postcheck_ran: bool = False
        self.rebooted_after_patch: bool = False
        self.emergency_mode: bool = False
        self.fstab_valid: bool = True
        # Jira-coordinated change management
        self.ops_backup_taken: bool = False
        self.ops_db_stopped: bool = False
        self.ops_app_stopped: bool = False
        self.ops_db_started: bool = True
        self.ops_app_started: bool = True
        self.ops_services_restarted: bool = False
        self.mount_issue_after_reboot: bool = False
        self.mount_filesystems_fixed: bool = False
        self.pending_storage_device: str = "/dev/sdb"
        self.storage_disk_provisioned: bool = True
        self.pending_nic_config: str = "10.0.0.20/24"
        self.network_nic_provisioned: bool = True
        # SELinux: mode round-trips via getenforce/setenforce; ports/fcontexts
        # are state that semanage mutates and restorecon/chcon read.
        self.selinux_mode: str = "Enforcing"  # Enforcing | Permissive | Disabled
        self.selinux_ports: dict[str, list[int]] = {}   # type -> [ports]
        self.selinux_fcontexts: list[dict] = []          # {path, type}
        self.file_contexts: dict[str, str] = {}          # path -> selinux context
        # Block-device model for storage/filesystem scenarios.
        self.block_devices: dict[str, SimBlockDevice] = {}
        self.hidden_block_devices: dict[str, SimBlockDevice] = {}  # revealed by SCSI rescan
        self.swaps: dict[str, dict] = {}  # device -> {"size": kb, "used": kb}
        self.mounts: dict[str, dict] = {}  # mountpoint -> {"device", "fstype", "size_kb"}
        self.disk_rescanned: bool = False
        # Cross-technology bridge (VMware ⇄ this terminal). session_id keys the
        # shared cache; server_hung models a guest hung until reset from VMware.
        self.session_id: str = ""
        self.server_hung: bool = False
        self.editor = None  # EditorSession when nano/vi active
        self.network_ifs: dict[str, dict] = {
            "lo": {"up": True, "addrs": ["127.0.0.1/8"]},
            "eth0": {"up": True, "addrs": ["10.0.0.10/24"]},
        }
        from .lvm_state import LVMState
        from .firewall_state import FirewallState
        self.lvm = LVMState()
        self.firewall = FirewallState()
        # Stateful rpm DB: name -> "name-version-release.arch". `dnf/yum install`
        # adds, remove deletes, and `rpm -q`/`rpm -qa` read from it so an install
        # is reflected in subsequent queries.
        self.installed_packages: dict[str, str] = {
            "kernel": f"kernel-{self.kernel}",
            "glibc": "glibc-2.34-100.el9.x86_64",
            "bash": "bash-5.1.8-9.el9.x86_64",
            "systemd": "systemd-252-13.el9.x86_64",
            "openssh-server": "openssh-server-8.7p1-34.el9.x86_64",
            "openssh-clients": "openssh-clients-8.7p1-34.el9.x86_64",
            "sudo": "sudo-1.9.5p2-9.el9.x86_64",
            "python3": "python3-3.9.18-1.el9.x86_64",
            "dnf": "dnf-4.14.0-8.el9.noarch",
            "rpm": "rpm-4.16.1.3-22.el9.x86_64",
            "firewalld": "firewalld-1.2.5-1.el9.noarch",
            "chrony": "chrony-4.3-1.el9.x86_64",
            "coreutils": "coreutils-8.32-34.el9.x86_64",
        }
        self._init_base_system()
        self._init_block_devices()

    def _init_base_system(self) -> None:
        self.users["root"] = SimUser("root", 0, 0, "/root", "/bin/bash", "root")
        self._write_file("/etc/hostname", self.hostname + "\n")
        self._write_file("/etc/os-release", f'NAME="{self.os_release}"\nVERSION_ID="9.3"\n')
        self._write_file("/etc/passwd", "root:x:0:0:root:/root:/bin/bash\n")
        self._write_file("/etc/group", "root:x:0:\n")
        self._write_file("/etc/shadow", "root:*:19000:0:99999:7:::\n")
        self._write_file("/etc/shells", "/bin/sh\n/bin/bash\n")
        self._write_file("/etc/resolv.conf", "nameserver 8.8.8.8\n")
        self._write_file("/etc/hosts", f"127.0.0.1 localhost\n127.0.1.1 {self.hostname}\n")
        self._mkdir("/root")
        self._mkdir("/home")
        self._mkdir("/etc/systemd/system")
        self._mkdir("/var/log")
        self._mkdir("/var/log/journal")
        self._mkdir("/opt/fixitlab")
        self._write_file("/opt/fixitlab/check.sh", "#!/bin/bash\nexit 0\n")

        for svc, desc in (
            ("sshd", "OpenSSH server daemon"),
            ("nginx", "The nginx HTTP and reverse proxy server"),
            ("crond", "Command Scheduler"),
            ("chronyd", "NTP client/server"),
            ("rsyslog", "System Logging Service"),
        ):
            self.services[svc] = SimService(
                svc, active="active", enabled="enabled", description=desc,
                sub_state="running",
                unit_file=f"[Unit]\nDescription={desc}\n",
            )

        self.processes = [
            SimProcess(1, "root", 0.0, 0.1, "systemd"),
            SimProcess(412, "root", 0.1, 0.5, "/usr/sbin/sshd -D"),
            SimProcess(891, "nginx", 0.0, 0.3, "nginx: master process /usr/sbin/nginx"),
            SimProcess(892, "nginx", 0.0, 0.2, "nginx: worker process"),
        ]
        self.pid_counter = 900

    def _init_block_devices(self) -> None:
        """Seed the default disk layout: sda (boot + LVM PV) plus a spare sdb."""
        self.block_devices = {
            "/dev/sda": SimBlockDevice("/dev/sda", "50G", "disk"),
            "/dev/sda1": SimBlockDevice("/dev/sda1", "1G", "part", parent="/dev/sda",
                                        fstype="xfs", uuid="aaaa1111-boot", mountpoint="/boot"),
            "/dev/sda2": SimBlockDevice("/dev/sda2", "49G", "part", parent="/dev/sda",
                                        fstype="LVM2_member", uuid="bbbb2222-pv"),
            "/dev/sdb": SimBlockDevice("/dev/sdb", "50G", "disk"),
        }
        # Root + swap LVs exposed as device-mapper block devices.
        self.block_devices["/dev/mapper/rhel-root"] = SimBlockDevice(
            "/dev/mapper/rhel-root", "40G", "lvm", parent="/dev/sda2",
            fstype="xfs", uuid="cccc3333-root", mountpoint="/")
        self.block_devices["/dev/mapper/rhel-swap"] = SimBlockDevice(
            "/dev/mapper/rhel-swap", "8G", "lvm", parent="/dev/sda2",
            fstype="swap", uuid="dddd4444-swap", mountpoint="[SWAP]")
        self.swaps["/dev/mapper/rhel-swap"] = {"size": 8 * 1024 * 1024, "used": 0}

    def gen_uuid(self) -> str:
        import uuid as _uuid
        return str(_uuid.uuid4())

    def add_block_device(self, name: str, size: str = "50G", dev_type: str = "disk",
                         present: bool = True, **kw) -> "SimBlockDevice":
        """Register a disk/partition; when present=False it is hidden until a
        SCSI rescan reveals it (the classic disk-missing workflow)."""
        dev = SimBlockDevice(name, size, dev_type, present=present, **kw)
        if present:
            self.block_devices[name] = dev
        else:
            dev.present = False
            self.hidden_block_devices[name] = dev
        return dev

    def reveal_hidden_disks(self, after_reboot: bool = False) -> list[str]:
        """A SCSI rescan / rescan-scsi-bus.sh makes pending disks appear.

        Two sources are drained: (1) locally pre-seeded hidden_block_devices (the
        classic single-engine disk-missing flow), and (2) the cross-technology
        VMware bridge — disks hot-added in the VMware simulator for THIS lab
        session. Bridge disks flagged requires_reboot stay invisible to a plain
        rescan and only appear once `after_reboot` is True (Scenario B)."""
        revealed = []
        self.disk_rescanned = True
        for name, dev in list(self.hidden_block_devices.items()):
            if getattr(dev, "needs_reboot", False) and not after_reboot:
                continue
            dev.present = True
            self.block_devices[name] = dev
            del self.hidden_block_devices[name]
            revealed.append(name)
        revealed.extend(self._reveal_bridge_disks(after_reboot=after_reboot))
        return revealed

    def _reveal_bridge_disks(self, after_reboot: bool = False) -> list[str]:
        """Pull disks hot-added in the VMware simulator for this lab session."""
        if not self.session_id:
            return []
        try:
            from .vmware_bridge import consume_revealed_disks
        except Exception:
            return []
        revealed = []
        for disk in consume_revealed_disks(self.session_id, after_reboot=after_reboot):
            dev = disk.get("dev") or "/dev/sdc"
            size = f"{int(disk.get('size_gb', 50))}G"
            # The disk arrives bare (no partition table / no LVM metadata) — the
            # operator must pvcreate/vgextend/lvextend to actually use it.
            self.block_devices[dev] = SimBlockDevice(dev, size, "disk", present=True)
            self.hidden_block_devices.pop(dev, None)
            revealed.append(dev)
        return revealed

    def reveal_bridge_nic(self) -> bool:
        """A rescan / ifup surfaces a NIC hot-added in VMware for this session."""
        if not self.session_id:
            return False
        try:
            from .vmware_bridge import consume_pending_nic
        except Exception:
            return False
        nic = consume_pending_nic(self.session_id)
        if not nic:
            return False
        ip = nic.get("ip", "10.0.0.30/24")
        name = f"eth{len(self.network_ifs) - 1}"  # lo + eth0 already present → eth1
        self.network_ifs[name] = {"up": True, "addrs": [ip]}
        return True

    def recover_from_vmware_reset(self) -> bool:
        """If the guest was hung and VMware reset it for this session, recover."""
        if not self.server_hung or not self.session_id:
            return False
        try:
            from .vmware_bridge import was_vm_reset
        except Exception:
            return False
        if was_vm_reset(self.session_id):
            self.server_hung = False
            return True
        return False

    def find_block_device(self, ref: str) -> "SimBlockDevice | None":
        """Resolve a device by /dev path, UUID=, or bare UUID."""
        if not ref:
            return None
        if ref.startswith("UUID="):
            ref = ref.split("=", 1)[1].strip('"')
        if ref in self.block_devices:
            return self.block_devices[ref]
        for dev in self.block_devices.values():
            if dev.uuid and dev.uuid == ref:
                return dev
        return None

    def _mkdir(self, path: str) -> None:
        self.vfs[path] = {"type": "dir", "entries": {}}

    def _write_file(self, path: str, content: str, mode: str = "644") -> None:
        self.vfs[path] = {"type": "file", "content": content, "mode": mode, "owner": "root", "group": "root"}

    def resolve_path(self, path: str) -> str:
        if not path:
            return self.cwd
        if path.startswith("/"):
            base = path
        else:
            base = self.cwd.rstrip("/") + "/" + path if self.cwd != "/" else "/" + path
        parts = []
        for p in base.split("/"):
            if p == "" or p == ".":
                continue
            if p == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(p)
        return "/" + "/".join(parts) if parts else "/"

    def read_file(self, path: str) -> str | None:
        ap = self.resolve_path(path)
        node = self.vfs.get(ap)
        if isinstance(node, dict) and node.get("type") == "file":
            return node.get("content", "")
        return None

    def write_file(self, path: str, content: str, append: bool = False) -> None:
        ap = self.resolve_path(path)
        parent = "/".join(ap.split("/")[:-1]) or "/"
        name = ap.split("/")[-1]
        if parent not in self.vfs:
            self._mkdir(parent)
        parent_node = self.vfs.get(parent)
        if isinstance(parent_node, dict) and parent_node.get("type") == "dir":
            parent_node.setdefault("entries", {})[name] = ap
        existing = self.vfs.get(ap)
        if append and isinstance(existing, dict) and existing.get("type") == "file":
            content = existing.get("content", "") + content
        self._write_file(ap, content)

    def list_dir(self, path: str) -> list[str] | None:
        ap = self.resolve_path(path)
        node = self.vfs.get(ap)
        if isinstance(node, dict) and node.get("type") == "dir":
            entries = list(node.get("entries", {}).keys())
            if ap == "/":
                return sorted(set(entries + [k.split("/")[-1] for k in self.vfs if k.count("/") == 1 and k != "/"]))
            return sorted(entries)
        if isinstance(node, dict) and node.get("type") == "file":
            return None
        # implicit dirs from file paths
        prefix = ap.rstrip("/") + "/"
        found = set()
        for p in self.vfs:
            if p.startswith(prefix):
                rest = p[len(prefix):]
                found.add(rest.split("/")[0])
        return sorted(found) if found else None

    def file_exists(self, path: str) -> bool:
        ap = self.resolve_path(path)
        return ap in self.vfs

    def is_dir(self, path: str) -> bool:
        ap = self.resolve_path(path)
        node = self.vfs.get(ap)
        if isinstance(node, dict):
            return node.get("type") == "dir"
        return self.list_dir(ap) is not None and not self.read_file(ap)

    def sync_passwd_files(self) -> None:
        lines_p = []
        lines_g = ["root:x:0:"]
        for u in sorted(self.users.values(), key=lambda x: x.uid):
            lines_p.append(f"{u.username}:x:{u.uid}:{u.gid}:{u.gecos}:{u.home}:{u.shell}")
            gname = u.username if u.uid >= 1000 else None
            if gname and gname not in self.groups:
                self.groups[gname] = [u.gid]
            if gname:
                lines_g.append(f"{gname}:x:{u.gid}:")
        self._write_file("/etc/passwd", "\n".join(lines_p) + "\n")
        self._write_file("/etc/group", "\n".join(lines_g) + "\n")

    def add_user(self, username: str, home: str | None = None, shell: str = "/bin/bash") -> tuple[bool, str]:
        if username in self.users:
            return False, f"useradd: user '{username}' already exists"
        uid = self.uid_counter
        self.uid_counter += 1
        home = home or f"/home/{username}"
        self.users[username] = SimUser(username, uid, uid, home, shell, username)
        self._mkdir(home)
        self.sync_passwd_files()
        return True, ""

    def set_prompt_user(self, username: str) -> bool:
        if username not in self.users:
            return False
        self.current_user = username
        u = self.users[username]
        self.cwd = u.home
        self.env["USER"] = username
        self.env["HOME"] = u.home
        return True

    def clone_for_host(self, hostname: str) -> RHELOSState:
        """Companion host shares scenario preset but different hostname."""
        other = RHELOSState(hostname=hostname, scenario_slug=self.scenario_slug)
        other.vfs = copy.deepcopy(self.vfs)
        other.users = copy.deepcopy(self.users)
        other.groups = copy.deepcopy(self.groups)
        other.services = copy.deepcopy(self.services)
        other.processes = copy.deepcopy(self.processes)
        other.dmesg_extra = list(self.dmesg_extra)
        other.uid_counter = self.uid_counter
        other.pid_counter = self.pid_counter
        other.lvm = copy.deepcopy(self.lvm)
        other.firewall = copy.deepcopy(self.firewall)
        other.network_ifs = copy.deepcopy(self.network_ifs)
        other.block_devices = copy.deepcopy(self.block_devices)
        other.hidden_block_devices = copy.deepcopy(self.hidden_block_devices)
        other.swaps = copy.deepcopy(self.swaps)
        other.mounts = copy.deepcopy(self.mounts)
        other.selinux_mode = self.selinux_mode
        other.selinux_ports = copy.deepcopy(self.selinux_ports)
        other.selinux_fcontexts = copy.deepcopy(self.selinux_fcontexts)
        other.file_contexts = copy.deepcopy(self.file_contexts)
        other.emergency_mode = self.emergency_mode
        other.fstab_valid = self.fstab_valid
        other.editor = None
        other._write_file("/etc/hostname", hostname + "\n")
        other.env["HOSTNAME"] = hostname
        return other

    def set_host_ip(self, ip: str, iface: str = "eth0") -> None:
        if iface not in self.network_ifs:
            self.network_ifs[iface] = {"up": True, "addrs": []}
        self.network_ifs[iface]["addrs"] = [f"{ip}/24" if "/" not in ip else ip]

    def append_host_ip(self, ip: str, iface: str = "eth0") -> None:
        if iface not in self.network_ifs:
            self.network_ifs[iface] = {"up": True, "addrs": []}
        addr = f"{ip}/24" if "/" not in ip else ip
        if addr not in self.network_ifs[iface]["addrs"]:
            self.network_ifs[iface]["addrs"].append(addr)

    def format_ip_addr(self) -> str:
        lines = []
        for idx, (name, data) in enumerate(self.network_ifs.items(), 1):
            flags = "LOOPBACK,UP" if name == "lo" else "BROADCAST,UP"
            if not data.get("up", True):
                flags = "BROADCAST"
            mtu = 65536 if name == "lo" else 1500
            lines.append(f"{idx}: {name}: <{flags}> mtu {mtu}")
            for addr in data.get("addrs", []):
                if name == "lo":
                    lines.append(f"    inet {addr.split('/')[0]}/8 scope host {name}")
                else:
                    ip, _, prefix = addr.partition("/")
                    lines.append(f"    inet {ip}/{prefix or '24'} brd {ip.rsplit('.', 1)[0]}.255 scope global {name}")
        return "\n".join(lines)
