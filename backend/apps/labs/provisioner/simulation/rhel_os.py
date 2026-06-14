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
        self._init_base_system()

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
        other._write_file("/etc/hostname", hostname + "\n")
        other.env["HOSTNAME"] = hostname
        return other
