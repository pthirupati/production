"""Interactive shell for simulated RHEL — dispatches common Linux commands."""

from __future__ import annotations

import re
import shlex
import time
from typing import Callable

from .rhel_os import RHELOSState
from .scenario_presets import apply_scenario_preset


class RHELShell:
    """Full RHEL-like shell backed by RHELOSState."""

    def __init__(self, state: RHELOSState | None = None, scenario_slug: str = "", hostname: str = "rhel-sim"):
        self.state = state or RHELOSState(hostname=hostname, scenario_slug=scenario_slug)
        slug = scenario_slug or getattr(self.state, "scenario_slug", "") or ""
        if slug and not getattr(self.state, "_scenario_preset_applied", False):
            apply_scenario_preset(slug, self.state)
            self.state._scenario_preset_applied = True
            self.state.scenario_slug = slug
        self._extra_handlers: list[Callable[[list[str], str], str | None]] = []

    def register_handler(self, handler: Callable[[list[str], str], str | None]) -> None:
        self._extra_handlers.append(handler)

    @property
    def prompt(self) -> str:
        u = self.state.current_user
        h = self.state.hostname
        cwd = self.state.cwd
        if cwd.startswith("/home/" + u):
            disp = "~" + cwd[len("/home/" + u):]
        elif cwd == f"/home/{u}":
            disp = "~"
        else:
            disp = cwd
        sym = "#" if u == "root" else "$"
        return f"[{u}@{h} {disp}]{sym} "

    def run(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""
        if line.startswith("#"):
            return ""
        if " && " in line:
            chunks: list[str] = []
            for segment in line.split(" && "):
                out = self.run(segment.strip())
                if out:
                    chunks.append(out)
                if self.state.last_exit_code not in (0, None):
                    break
            return "\n".join(chunks)

        for handler in self._extra_handlers:
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = line.split()
            result = handler(parts, line)
            if result is not None:
                self.state.last_exit_code = 0 if not result.startswith("bash:") else 127
                return result

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            return f"bash: {exc}"

        if not parts:
            return ""

        cmd = parts[0]
        dispatch = {
            "pwd": self._cmd_pwd,
            "cd": self._cmd_cd,
            "ls": self._cmd_ls,
            "cat": self._cmd_cat,
            "echo": self._cmd_echo,
            "mkdir": self._cmd_mkdir,
            "rm": self._cmd_rm,
            "touch": self._cmd_touch,
            "cp": self._cmd_cp,
            "mv": self._cmd_mv,
            "whoami": self._cmd_whoami,
            "id": self._cmd_id,
            "hostname": self._cmd_hostname,
            "uname": self._cmd_uname,
            "useradd": self._cmd_useradd,
            "userdel": self._cmd_userdel,
            "usermod": self._cmd_usermod,
            "passwd": self._cmd_passwd,
            "groupadd": self._cmd_groupadd,
            "systemctl": self._cmd_systemctl,
            "service": self._cmd_service,
            "ps": self._cmd_ps,
            "pgrep": self._cmd_pgrep,
            "kill": self._cmd_kill,
            "killall": self._cmd_killall,
            "grep": self._cmd_grep,
            "sed": self._cmd_sed,
            "head": self._cmd_head,
            "tail": self._cmd_tail,
            "wc": self._cmd_wc,
            "chmod": self._cmd_chmod,
            "chown": self._cmd_chown,
            "chattr": self._cmd_chattr,
            "lsattr": self._cmd_lsattr,
            "df": self._cmd_df,
            "free": self._cmd_free,
            "uptime": self._cmd_uptime,
            "date": self._cmd_date,
            "which": self._cmd_which,
            "type": self._cmd_which,
            "env": self._cmd_env,
            "export": self._cmd_export,
            "su": self._cmd_su,
            "sudo": self._cmd_sudo,
            "journalctl": self._cmd_journalctl,
            "dmesg": self._cmd_dmesg,
            "ip": self._cmd_ip,
            "ss": self._cmd_ss,
            "curl": self._cmd_curl,
            "nginx": self._cmd_nginx,
            "pwck": self._cmd_pwck,
            "getent": self._cmd_getent,
            "clear": self._cmd_clear,
            "history": self._cmd_history,
            "help": self._cmd_help,
            "ssh": self._cmd_ssh,
            "scp": self._cmd_scp,
            "ping": self._cmd_ping,
            "shutdown": self._cmd_shutdown,
            "exit": self._cmd_exit,
            "logout": self._cmd_exit,
            "dnf": self._cmd_dnf,
            "yum": self._cmd_dnf,
            "rpm": self._cmd_rpm,
            "docker": self._cmd_docker,
            "kubectl": self._cmd_kubectl,
            "mysql": self._cmd_mysql,
            "psql": self._cmd_psql,
            "python3": self._cmd_python3,
            "python": self._cmd_python3,
            "pip3": self._cmd_pip3,
            "find": self._cmd_find,
            "awk": self._cmd_awk,
            "sort": self._cmd_sort,
            "tar": self._cmd_tar,
            "ln": self._cmd_ln,
            "crontab": self._cmd_crontab,
            "firewall-cmd": self._cmd_firewall,
            "nmcli": self._cmd_nmcli,
            "dracut": self._cmd_dracut,
            "grub2-mkconfig": self._cmd_grub2_mkconfig,
            "grub2-install": self._cmd_grub2_install,
            "grub-install": self._cmd_grub2_install,
            "bash": self._cmd_bash,
            "sh": self._cmd_bash,
            "vi": self._cmd_nano,
            "vim": self._cmd_nano,
            "nano": self._cmd_nano,
            "pvs": self._cmd_pvs,
            "vgs": self._cmd_vgs,
            "lvs": self._cmd_lvs,
            "pvcreate": self._cmd_pvcreate,
            "vgcreate": self._cmd_vgcreate,
            "vgextend": self._cmd_vgextend,
            "lvextend": self._cmd_lvextend,
            "lvdisplay": self._cmd_lvdisplay,
            "pvdisplay": self._cmd_pvdisplay,
            "vgdisplay": self._cmd_vgdisplay,
            "lvresize": self._cmd_lvextend,
            "less": self._cmd_cat,
            "more": self._cmd_cat,
            "netstat": self._cmd_netstat,
            "lsof": self._cmd_lsof,
            "mount": self._cmd_mount,
            "fdisk": self._cmd_fdisk,
            "virsh": self._cmd_virsh,
            "esxcli": self._cmd_esxcli,
            "vmware-toolbox-cmd": self._cmd_vmware,
            "reboot": self._cmd_reboot,
            "shutdown": self._cmd_shutdown,
        }

        fn = dispatch.get(cmd)
        if fn:
            out = fn(parts)
            return out

        return f"bash: {cmd}: command not found"

    def create_stream_handler(self):
        shell = self
        return lambda line: shell.run(line)

    # ── Commands ─────────────────────────────────────────────────────

    def _cmd_pwd(self, p: list[str]) -> str:
        return self.state.cwd

    def _cmd_cd(self, p: list[str]) -> str:
        target = p[1] if len(p) > 1 else "/root"
        if target == "~":
            target = self.state.users[self.state.current_user].home
        ap = self.state.resolve_path(target)
        if ap == "/root" and self.state.current_user != "root":
            return f"bash: cd: {target}: Permission denied"
        if self.state.read_file(ap) and not self.state.is_dir(ap):
            return f"bash: cd: {target}: Not a directory"
        self.state.cwd = ap
        return ""

    def _cmd_ls(self, p: list[str]) -> str:
        long_fmt = "-l" in "".join(p[1:])
        path = p[-1] if len(p) > 1 and not p[-1].startswith("-") else self.state.cwd
        entries = self.state.list_dir(path)
        if entries is None:
            content = self.state.read_file(self.state.resolve_path(path))
            if content is not None:
                return self.state.resolve_path(path)
            return f"ls: cannot access '{path}': No such file or directory"
        if not long_fmt:
            return "  ".join(entries) if entries else ""
        lines = []
        for name in entries:
            fp = self.state.resolve_path(path.rstrip("/") + "/" + name)
            node = self.state.vfs.get(fp, {})
            mode = node.get("mode", "755") if isinstance(node, dict) else "755"
            owner = node.get("owner", "root") if isinstance(node, dict) else "root"
            ftype = "d" if self.state.is_dir(fp) else "-"
            lines.append(f"{ftype}rwxr-xr-x 1 {owner} {owner} 4096 Jun 14 10:00 {name}")
        return "\n".join(lines)

    def _cmd_cat(self, p: list[str]) -> str:
        if len(p) < 2:
            return "cat: missing file operand"
        out = []
        for f in p[1:]:
            if f.startswith("-"):
                continue
            content = self.state.read_file(f)
            if content is None:
                return f"cat: {f}: No such file or directory"
            out.append(content.rstrip("\n"))
        return "\n".join(out)

    def _cmd_echo(self, p: list[str]) -> str:
        text = " ".join(p[1:])
        if ">>" in text:
            left, right = text.split(">>", 1)
            self.state.write_file(right.strip(), left.strip().strip('"').strip("'") + "\n", append=True)
            return ""
        if ">" in text:
            left, right = text.split(">", 1)
            self.state.write_file(right.strip(), left.strip().strip('"').strip("'") + "\n")
            return ""
        return text.strip('"').strip("'")

    def _cmd_mkdir(self, p: list[str]) -> str:
        if len(p) < 2:
            return "mkdir: missing operand"
        for d in p[1:]:
            if d.startswith("-"):
                continue
            self.state._mkdir(self.state.resolve_path(d))
        return ""

    def _cmd_rm(self, p: list[str]) -> str:
        if len(p) < 2:
            return "rm: missing operand"
        for f in p[1:]:
            if f.startswith("-"):
                continue
            ap = self.state.resolve_path(f)
            if ap in self.state.vfs:
                del self.state.vfs[ap]
        return ""

    def _cmd_touch(self, p: list[str]) -> str:
        if len(p) < 2:
            return "touch: missing file operand"
        for f in p[1:]:
            if not self.state.read_file(f):
                self.state.write_file(f, "")
        return ""

    def _cmd_cp(self, p: list[str]) -> str:
        if len(p) < 3:
            return "cp: missing file operand"
        src = self.state.read_file(p[1])
        if src is None:
            return f"cp: cannot stat '{p[1]}': No such file or directory"
        self.state.write_file(p[2], src)
        return ""

    def _cmd_mv(self, p: list[str]) -> str:
        return self._cmd_cp(p) + (self._cmd_rm(["rm", p[1]]) if len(p) >= 3 else "")

    def _cmd_whoami(self, p: list[str]) -> str:
        return self.state.current_user

    def _cmd_id(self, p: list[str]) -> str:
        u = self.state.users.get(self.state.current_user)
        if not u:
            return f"id: '{self.state.current_user}': no such user"
        return f"uid={u.uid}({u.username}) gid={u.gid}({u.username}) groups={u.gid}({u.username})"

    def _cmd_hostname(self, p: list[str]) -> str:
        if len(p) > 1 and p[1] in ("-f", "--fqdn"):
            return self.state.hostname + ".fixitlab.local"
        if len(p) > 1 and not p[1].startswith("-"):
            self.state.hostname = p[1]
            self.state.env["HOSTNAME"] = p[1]
            return ""
        return self.state.hostname

    def _cmd_uname(self, p: list[str]) -> str:
        flags = "".join(p[1:])
        if "-a" in flags:
            return f"Linux {self.state.hostname} {self.state.kernel} #1 SMP x86_64 x86_64 x86_64 GNU/Linux"
        if "-r" in flags:
            return self.state.kernel
        return "Linux"

    def _cmd_useradd(self, p: list[str]) -> str:
        home = None
        shell = "/bin/bash"
        name = p[-1]
        if name.startswith("-"):
            return "useradd: invalid user name"
        i = 1
        while i < len(p) - 1:
            if p[i] == "-m":
                home = f"/home/{name}"
            elif p[i] == "-s" and i + 1 < len(p):
                shell = p[i + 1]
                i += 1
            elif p[i] == "-d" and i + 1 < len(p):
                home = p[i + 1]
                i += 1
            i += 1
        ok, err = self.state.add_user(name, home=home, shell=shell)
        if not ok:
            self.state.last_exit_code = 1
            return err
        return ""

    def _cmd_userdel(self, p: list[str]) -> str:
        if len(p) < 2:
            return "userdel: user '' does not exist"
        name = p[-1]
        if name not in self.state.users or name == "root":
            return f"userdel: user '{name}' does not exist"
        del self.state.users[name]
        self.state.sync_passwd_files()
        return ""

    def _cmd_usermod(self, p: list[str]) -> str:
        if len(p) < 2:
            return "usermod: missing user"
        name = p[-1]
        if name not in self.state.users:
            return f"usermod: user '{name}' does not exist"
        if "-s" in p:
            idx = p.index("-s")
            if idx + 1 < len(p):
                self.state.users[name].shell = p[idx + 1]
        if "-aG" in p:
            return ""
        self.state.sync_passwd_files()
        return ""

    def _cmd_passwd(self, p: list[str]) -> str:
        user = p[1] if len(p) > 1 else self.state.current_user
        if user not in self.state.users:
            return f"passwd: user '{user}' does not exist"
        self.state.users[user].locked = False
        return f"Changing password for user {user}.\nNew password: \nRetype new password: \npasswd: all authentication tokens updated successfully."

    def _cmd_groupadd(self, p: list[str]) -> str:
        if len(p) < 2:
            return "groupadd: missing group name"
        self.state.groups[p[-1]] = [self.state.uid_counter]
        return ""

    def _cmd_systemctl(self, p: list[str]) -> str:
        if len(p) < 2:
            return "Unknown operation systemctl."
        action = p[1]
        unit = p[2] if len(p) > 2 else ""
        unit = unit.replace(".service", "")

        if action in ("emergency", "rescue"):
            self.state.emergency_mode = True
            engine = getattr(self, "_engine", None)
            if engine and engine.boot:
                engine.boot.phase = "emergency"
                engine.boot.logged_in = True
                engine.boot.username = "root"
            return (
                "You are in emergency mode. After logging in, type \"journalctl -xb\" to view\n"
                "system logs, \"systemctl reboot\" to reboot, or \"exit\" to continue bootup.\n"
                "Give root password for maintenance (or type Control-D to continue): "
            )

        svc = self.state.services.get(unit)
        if not svc and action not in ("daemon-reload", "list-units"):
            return f"Unit {unit}.service could not be found."

        if action == "status" and svc:
            active = "active (running)" if svc.active == "active" else svc.active
            return (
                f"● {unit}.service - {svc.description}\n"
                f"   Loaded: {svc.loaded} (/usr/lib/systemd/system/{unit}.service; {svc.enabled})\n"
                f"   Active: {active} since Fri 2026-06-14 10:00:00 UTC; 1h ago\n"
                f"   Main PID: 891 ({unit})\n"
            )
        if action == "start" and svc:
            svc.active = "active"
            svc.sub_state = "running"
            return ""
        if action == "stop" and svc:
            svc.active = "inactive"
            svc.sub_state = "dead"
            return ""
        if action == "restart" and svc:
            svc.active = "active"
            svc.sub_state = "running"
            return ""
        if action == "enable" and svc:
            svc.enabled = "enabled"
            return f"Created symlink /etc/systemd/system/multi-user.target.wants/{unit}.service"
        if action == "disable" and svc:
            svc.enabled = "disabled"
            return ""
        if action == "is-active" and svc:
            return svc.active if svc.active == "active" else "inactive"
        if action == "daemon-reload":
            return ""
        if action == "reboot":
            return self._cmd_reboot(p)
        if action == "list-units":
            lines = [f"  {n}.service  {s.active}  {s.description}" for n, s in self.state.services.items()]
            return "\n".join(lines)
        return f"Unknown operation '{action}'."

    def _cmd_service(self, p: list[str]) -> str:
        if len(p) >= 3:
            return self._cmd_systemctl(["systemctl", p[1], p[2]])
        return "Usage: service name action"

    def _cmd_ps(self, p: list[str]) -> str:
        header = "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"
        lines = [header]
        for proc in self.state.processes:
            lines.append(
                f"{proc.user:<10}{proc.pid:>5} {proc.cpu:4.1f} {proc.mem:4.1f}  12345  6789 ?        Ss   10:00   0:00 {proc.command}"
            )
        return "\n".join(lines)

    def _cmd_pgrep(self, p: list[str]) -> str:
        name = p[-1]
        return "\n".join(str(pr.pid) for pr in self.state.processes if name in pr.command)

    def _cmd_kill(self, p: list[str]) -> str:
        if len(p) < 2:
            return "kill: usage: kill [-s sigspec] pid"
        try:
            pid = int(p[-1])
        except ValueError:
            return f"kill: {p[-1]}: arguments must be process or job IDs"
        self.state.processes = [pr for pr in self.state.processes if pr.pid != pid]
        return ""

    def _cmd_killall(self, p: list[str]) -> str:
        if len(p) < 2:
            return "killall: missing process name"
        name = p[1]
        self.state.processes = [pr for pr in self.state.processes if name not in pr.command]
        return ""

    def _cmd_grep(self, p: list[str]) -> str:
        if len(p) < 2:
            return "Usage: grep pattern [file...]"
        pattern = p[1].lstrip("-").replace("'", "")
        files = [x for x in p[2:] if not x.startswith("-")] or [self.state.cwd]
        matches = []
        for f in files:
            content = self.state.read_file(f)
            if content:
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern in line or (pattern and re.search(pattern, line)):
                        matches.append(f"{f}:{line}" if len(files) > 1 or f != self.state.cwd else line)
        return "\n".join(matches) if matches else ""

    def _cmd_sed(self, p: list[str]) -> str:
        if len(p) < 2:
            return "sed: missing script"
        line = " ".join(p)
        # sed -i 's/listn/listen/' file
        m = re.search(r"s/([^/]+)/([^/]+)/", line)
        fmatch = re.search(r"s/[^/]+/[^/]+/\s*(\S+)", line)
        if m and fmatch:
            old, new = m.group(1), m.group(2)
            path = fmatch.group(1)
            content = self.state.read_file(path)
            if content is None:
                return f"sed: can't read {path}: No such file or directory"
            self.state.write_file(path, content.replace(old, new))
            return ""
        return "sed: unsupported expression (use s/old/new/ file)"

    def _cmd_head(self, p: list[str]) -> str:
        n = 10
        f = p[-1]
        if "-n" in p:
            n = int(p[p.index("-n") + 1])
        content = self.state.read_file(f)
        if content is None:
            return f"head: cannot open '{f}' for reading: No such file or directory"
        return "\n".join(content.splitlines()[:n])

    def _cmd_tail(self, p: list[str]) -> str:
        n = 10
        f = p[-1]
        if "-n" in p:
            n = int(p[p.index("-n") + 1])
        content = self.state.read_file(f)
        if content is None:
            return f"tail: cannot open '{f}' for reading: No such file or directory"
        return "\n".join(content.splitlines()[-n:])

    def _cmd_wc(self, p: list[str]) -> str:
        f = p[-1]
        content = self.state.read_file(f) or ""
        lines = content.count("\n")
        words = len(content.split())
        return f"  {lines}  {words}  {len(content)} {f}"

    def _cmd_chmod(self, p: list[str]) -> str:
        if len(p) < 3:
            return "chmod: missing operand"
        mode, path = p[1], p[2]
        ap = self.state.resolve_path(path)
        node = self.state.vfs.get(ap)
        if isinstance(node, dict) and node.get("type") == "file":
            node["mode"] = mode
        return ""

    def _cmd_chown(self, p: list[str]) -> str:
        if len(p) < 3:
            return "chown: missing operand"
        owner, path = p[1], p[2]
        ap = self.state.resolve_path(path)
        node = self.state.vfs.get(ap)
        if isinstance(node, dict):
            node["owner"] = owner.split(":")[0]
            if ":" in owner:
                node["group"] = owner.split(":")[1]
        return ""

    def _cmd_chattr(self, p: list[str]) -> str:
        return ""

    def _cmd_lsattr(self, p: list[str]) -> str:
        f = p[-1] if len(p) > 1 else "."
        return f"--------------e------- {f}"

    def _cmd_df(self, p: list[str]) -> str:
        return self.state.lvm.format_df()

    def _cmd_free(self, p: list[str]) -> str:
        return "               total        used        free      shared  buff/cache   available\nMem:        16384000     2048000    12000000       64000     2336000    14000000\nSwap:        4194300           0     4194300"

    def _cmd_uptime(self, p: list[str]) -> str:
        up = int(time.time() - self.state.boot_time)
        h, rem = divmod(up, 3600)
        m, _ = divmod(rem, 60)
        return f" 10:00:00 up {h}:{m:02d},  1 user,  load average: 0.08, 0.04, 0.01"

    def _cmd_date(self, p: list[str]) -> str:
        return "Fri Jun 14 10:00:00 UTC 2026"

    def _cmd_which(self, p: list[str]) -> str:
        if len(p) < 2:
            return ""
        binaries = {
            "bash": "/usr/bin/bash", "systemctl": "/usr/bin/systemctl", "nginx": "/usr/sbin/nginx",
            "useradd": "/usr/sbin/useradd", "passwd": "/usr/bin/passwd", "python3": "/usr/bin/python3",
        }
        return binaries.get(p[1], f"which: no {p[1]} in ({self.state.env['PATH']})")

    def _cmd_env(self, p: list[str]) -> str:
        return "\n".join(f"{k}={v}" for k, v in self.state.env.items())

    def _cmd_export(self, p: list[str]) -> str:
        if len(p) > 1 and "=" in p[1]:
            k, v = p[1].split("=", 1)
            self.state.env[k] = v.strip('"')
        return ""

    def _cmd_su(self, p: list[str]) -> str:
        user = p[-1].lstrip("-") if len(p) > 1 else "root"
        if not self.state.set_prompt_user(user):
            return f"su: user {user} does not exist"
        return f"Password: \n[switched to {user}]"

    def _cmd_sudo(self, p: list[str]) -> str:
        if len(p) < 2:
            return "usage: sudo command"
        return self.run(" ".join(p[1:]))

    def _cmd_journalctl(self, p: list[str]) -> str:
        unit = ""
        if "-u" in p:
            unit = p[p.index("-u") + 1].replace(".service", "")
        lines = [f"Jun 14 10:00:00 {self.state.hostname} systemd[1]: Started {unit or 'system'}"]
        svc = self.state.services.get(unit)
        if svc and svc.active == "failed":
            lines.append(f"Jun 14 10:00:01 {self.state.hostname} {unit}[891]: Failed to start")
        return "\n".join(lines)

    def _cmd_dmesg(self, p: list[str]) -> str:
        extra = getattr(self.state, "dmesg_extra", [])
        base = [
            f"[    0.000000] Linux version {self.state.kernel}",
            "[    1.234567] systemd[1]: Reached target Multi-User System.",
        ]
        return "\n".join(base + extra)

    def _cmd_ip(self, p: list[str]) -> str:
        if len(p) > 1 and p[1] == "addr":
            if len(p) > 2 and p[2] == "add" and len(p) > 3:
                addr = p[3]
                dev = "eth0"
                if "dev" in p:
                    dev = p[p.index("dev") + 1]
                if dev not in self.state.network_ifs:
                    self.state.network_ifs[dev] = {"up": True, "addrs": []}
                if addr not in self.state.network_ifs[dev]["addrs"]:
                    self.state.network_ifs[dev]["addrs"].append(addr)
                return ""
            return self.state.format_ip_addr()
        if len(p) > 1 and p[1] == "link" and len(p) > 2:
            if p[2] == "set" and len(p) > 3:
                dev = p[3]
                if dev not in self.state.network_ifs:
                    self.state.network_ifs[dev] = {"up": True, "addrs": []}
                if "up" in p:
                    self.state.network_ifs[dev]["up"] = True
                if "down" in p:
                    self.state.network_ifs[dev]["up"] = False
                return ""
        if len(p) > 1 and p[1] == "route" and (len(p) < 3 or p[2] == "show"):
            return "default via 10.0.0.1 dev eth0 proto static\n10.0.0.0/24 dev eth0 proto kernel scope link src 10.0.0.10"
        return "Usage: ip addr | ip link set dev eth0 up | ip route show"

    def _cmd_ss(self, p: list[str]) -> str:
        return "Netid State  Recv-Q Send-Q Local Address:Port Peer Address:Port\nu_str ESTAB  0      0      * 22                * *\n"

    def _server_state(self):
        """Canonical primary/server state for remote checks from client terminals."""
        engine = getattr(self, "_engine", None)
        if engine:
            return engine.shell.state
        return self.state

    def _cmd_curl(self, p: list[str]) -> str:
        url = p[-1]
        st = self.state
        if any(x in url for x in ("10.0.0.10", "primary")):
            st = self._server_state()
        elif "localhost" in url or "127.0.0.1" in url:
            st = self.state
        else:
            return f"curl: (6) Could not resolve host: {url}"

        if "localhost" in url or "127.0.0.1" in url or "10.0.0.10" in url or "://" in url:
            nginx = st.services.get("nginx")
            if nginx and nginx.active == "active":
                if not st.firewall.is_port_open(80):
                    return "curl: (7) Failed to connect to host port 80: Connection refused"
                sites = st.read_file("/etc/nginx/sites-enabled/default") or ""
                if "listn" in sites:
                    return "curl: (52) Empty reply from server"
                if "root /var/www/wrong" in sites:
                    html = st.read_file("/var/www/wrong/index.html") or ""
                    if "Wrong Site" in html:
                        return "<html><body><h1>Wrong Site</h1></body></html>"
                if "root /var/www/html" in sites:
                    html = st.read_file("/var/www/html/index.html") or ""
                    if html.strip():
                        return html.strip() if html.startswith("<") else f"<html><body>{html}</body></html>"
                return "<html><body><h1>Welcome to nginx!</h1></body></html>"
            return "curl: (7) Failed to connect to localhost port 80: Connection refused"
        return f"curl: (6) Could not resolve host: {url}"

    def _cmd_nginx(self, p: list[str]) -> str:
        if len(p) > 1 and p[1] == "-t":
            cfg = self.state.read_file("/etc/nginx/nginx.conf") or ""
            sites = self.state.read_file("/etc/nginx/sites-enabled/default") or ""
            if "listn" in sites or "listn" in cfg:
                return "nginx: [emerg] unknown directive \"listn\" in /etc/nginx/sites-enabled/default:12\nnginx: configuration file /etc/nginx/nginx.conf test failed"
            return "nginx: the configuration file /etc/nginx/nginx.conf syntax is ok\nnginx: configuration file /etc/nginx/nginx.conf test is successful"
        return "nginx: invalid option"

    def _cmd_pwck(self, p: list[str]) -> str:
        passwd = self.state.read_file("/etc/passwd") or ""
        for line in passwd.splitlines():
            if line and line.count(":") < 6:
                return f"pwck: line {line}: malformed entry"
        return "pwck: no errors"

    def _cmd_getent(self, p: list[str]) -> str:
        if len(p) < 2:
            return ""
        if p[1] == "passwd":
            return self.state.read_file("/etc/passwd") or ""
        if p[1] == "group":
            return self.state.read_file("/etc/group") or ""
        return ""

    def _cmd_clear(self, p: list[str]) -> str:
        return "\x1b[2J\x1b[H"

    def _cmd_history(self, p: list[str]) -> str:
        return "  1  systemctl status nginx\n  2  journalctl -u nginx"

    def _cmd_help(self, p: list[str]) -> str:
        return (
            "FixitLab RHEL 9 Simulation — full Linux command set:\n"
            "  files: ls cd cat cp mv rm mkdir touch sed grep find tar chmod chown\n"
            "  users: useradd passwd pwck getent su sudo\n"
            "  services: systemctl service journalctl nginx curl\n"
            "  packages: dnf yum rpm dracut (patching)\n"
            "  boot: grub2-mkconfig grub2-install reboot\n"
            "  docker kubectl mysql psql python3 firewall-cmd nmcli virsh\n"
            "  Arrow keys, Home/End, and command history supported in terminal."
        )

    def _cmd_dnf(self, p: list[str]) -> str:
        line = " ".join(p)
        if any(x in line for x in ("update", "upgrade")):
            if getattr(self.state, "patching_done", False):
                return "Nothing to do. Complete!"
            self.state.patching_done = True
            engine = getattr(self, "_engine", None)
            if engine and engine.boot:
                engine.boot.patching_done = True
            from .boot_sequence import PATCHING_OUTPUT, NEW_KERNEL, OLD_KERNEL
            return PATCHING_OUTPUT.format(old_kernel=OLD_KERNEL, new_kernel=NEW_KERNEL)
        if "install" in line:
            pkg = p[-1] if len(p) > 2 else "package"
            return f"Last metadata expiration check: 0:00:01 ago\nInstalling:\n {pkg}    x86_64    simulated    rhel-9-base\nComplete!"
        if "remove" in line:
            return "Removed (simulated)."
        if "repolist" in line:
            return "repo id                    status\nrhel-9-base                enabled"
        return "dnf: command completed (simulation)"

    def _cmd_rpm(self, p: list[str]) -> str:
        line = " ".join(p)
        if "-i" in p or "--install" in p or "-U" in p or "--upgrade" in p:
            pkg = p[-1] if p[-1] not in ("-i", "-U", "--install", "--upgrade") else "package"
            return f"Preparing...\n   1:{pkg}\n   2:Complete!"
        if "-e" in p or "--erase" in p:
            return "Removed (simulated)."
        if "-qa" in p or "-q" in p:
            k = self.state.kernel
            if "kernel" in line:
                return f"kernel-{k}"
            return f"kernel-{k}\nglibc-2.34-100.el9.x86_64\nsystemd-252-13.el9.x86_64"
        return "rpm: OK"

    def _cmd_docker(self, p: list[str]) -> str:
        if len(p) < 2:
            return "docker: missing command"
        sub = p[1]
        if sub == "ps":
            return "CONTAINER ID   IMAGE          STATUS         NAMES\nabc123         nginx:latest   Up 2 hours     web"
        if sub == "images":
            return "REPOSITORY   TAG       IMAGE ID       CREATED        SIZE\nnginx        latest    abcdef123456   2 weeks ago    142MB"
        if sub == "run":
            return "abc123def456789"
        if sub == "logs":
            return "2026-06-14T10:00:00 nginx started"
        if sub == "inspect":
            return '{"State":{"Status":"running"},"Config":{"Image":"nginx:latest"}}'
        if sub == "exec":
            return "OCI runtime exec failed: container not running (simulation — start container first)"
        return f"docker {sub}: OK (simulation)"

    def _cmd_kubectl(self, p: list[str]) -> str:
        if len(p) < 2:
            return "kubectl: missing command"
        sub = p[1]
        if sub == "get" and "pods" in p:
            return "NAME                     READY   STATUS             RESTARTS   AGE\nnginx-7d4b8c9f-xk2m1      0/1     CrashLoopBackOff   5          10m\napi-5f8c7d6b-abc12        1/1     Running            0          1h"
        if sub == "get" and "nodes" in p:
            return "NAME       STATUS   ROLES           AGE   VERSION\nmaster-1   Ready    control-plane   30d   v1.28.2\nworker-1   Ready    <none>          30d   v1.28.2"
        if sub == "describe" and "pod" in p:
            return "Events:\n  Warning  Failed     kubelet  Error: ImagePullBackOff"
        if sub == "logs":
            return "Error from server: container not found (CrashLoopBackOff)"
        if sub == "apply":
            return "deployment.apps/api configured"
        return f"kubectl {' '.join(p[1:])}: OK (simulation)"

    def _cmd_mysql(self, p: list[str]) -> str:
        if "-e" in p:
            idx = p.index("-e")
            query = p[idx + 1] if idx + 1 < len(p) else "SELECT 1"
            if "ERROR" in query.upper():
                return "ERROR 2002 (HY000): Can't connect to local MySQL server"
            return "1\n1"
        svc = self.state.services.get("mysqld") or self.state.services.get("mysql")
        if svc and svc.active != "active":
            return "ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/lib/mysql/mysql.sock'"
        return "Welcome to the MySQL monitor. Type 'help;' for help.\nmysql>"

    def _cmd_psql(self, p: list[str]) -> str:
        svc = self.state.services.get("postgresql")
        if svc and svc.active != "active":
            return "psql: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" failed"
        return "psql (15.3)\nType \"help\" for help.\n\npostgres=#"

    def _cmd_python3(self, p: list[str]) -> str:
        if "-c" in p:
            idx = p.index("-c")
            code = p[idx + 1] if idx + 1 < len(p) else "print(1)"
            if "SyntaxError" in code or "syntax" in code.lower():
                return '  File "<string>", line 1\n    print("hello"\n               ^\nSyntaxError: unexpected EOF while parsing'
            if "print" in code:
                m = re.search(r"print\(['\"](.+?)['\"]\)", code)
                return m.group(1) if m else "None"
            return ""
        if len(p) > 1 and not p[1].startswith("-"):
            content = self.state.read_file(p[1])
            if content and "SyntaxError" in content:
                return content
            return f"python3: running {p[1]} (simulation OK)"
        return "Python 3.11.6 (main, Oct 2023) [GCC 11.4.1] on linux"

    def _cmd_pip3(self, p: list[str]) -> str:
        if "install" in p:
            return "Successfully installed package (simulation)"
        return "pip 23.2.1 from /usr/lib/python3.11/site-packages/pip"

    def _cmd_find(self, p: list[str]) -> str:
        path = p[-1] if len(p) > 1 else "."
        ap = self.state.resolve_path(path)
        results = []
        for fp in sorted(self.state.vfs):
            if fp.startswith(ap.rstrip("/")) or ap == "/":
                results.append(fp)
        return "\n".join(results[:50])

    def _cmd_awk(self, p: list[str]) -> str:
        return "awk: processed (simulation)"

    def _cmd_sort(self, p: list[str]) -> str:
        f = p[-1] if len(p) > 1 and not p[-1].startswith("-") else None
        if f:
            content = self.state.read_file(f) or ""
            return "\n".join(sorted(content.splitlines()))
        return ""

    def _cmd_tar(self, p: list[str]) -> str:
        return "tar: archive operation complete (simulation)"

    def _cmd_ln(self, p: list[str]) -> str:
        if len(p) >= 3:
            self.state.write_file(p[-1], self.state.read_file(p[-2]) or "")
        return ""

    def _cmd_crontab(self, p: list[str]) -> str:
        if "-l" in p:
            return self.state.read_file(f"/var/spool/cron/{self.state.current_user}") or "no crontab for user"
        return "crontab: installing new crontab"

    def _cmd_firewall(self, p: list[str]) -> str:
        line = " ".join(p)
        fw = self.state.firewall
        permanent = "--permanent" in line
        if "--list-all" in line:
            return fw.list_all(permanent=permanent)
        if "--reload" in line:
            return fw.reload()
        if "--add-port" in line:
            port_tok = None
            for tok in p:
                if tok.startswith("--add-port="):
                    port_tok = tok.split("=", 1)[1]
                elif "/" in tok and tok[0].isdigit():
                    port_tok = tok
            if port_tok:
                fw.add_port(port_tok, permanent=permanent)
                if not permanent:
                    return "success"
                return "success"
        if "--add-service" in line:
            svc_tok = None
            for tok in p:
                if tok.startswith("--add-service="):
                    svc_tok = tok.split("=", 1)[1]
                elif tok not in ("firewall-cmd", "--add-service", "--permanent", "--zone=public") and not tok.startswith("-"):
                    svc_tok = tok
            if svc_tok:
                fw.add_service(svc_tok, permanent=permanent)
                return "success"
        if "--get-active-zones" in line:
            return f"public\n  interfaces: eth0"
        return "success"

    def _cmd_nmcli(self, p: list[str]) -> str:
        if "connection" in p and "show" in p:
            return "NAME    UUID                                  TYPE      DEVICE\neth0    abc-123                               ethernet  eth0"
        return "nmcli: OK"

    def _cmd_dracut(self, p: list[str]) -> str:
        self.state.initramfs_fixed = True
        return "dracut: Generating initramfs for kernel 5.14.0-362.el9.x86_64...\ndracut: initramfs generation complete"

    def _cmd_grub2_mkconfig(self, p: list[str]) -> str:
        self.state.grub_fixed = True
        return "Generating grub configuration file ... done"

    def _cmd_grub2_install(self, p: list[str]) -> str:
        self.state.mbr_fixed = True
        self.state.grub_fixed = True
        return "Installation finished. No error reported."

    def _cmd_bash(self, p: list[str]) -> str:
        if len(p) <= 1 or p[1].startswith("-"):
            return ""
        path = self.state.resolve_path(p[1])
        if "precheck" in path:
            slug = (self.state.scenario_slug or "").lower()
            if "patch" in slug:
                from .ops_state import ops_ready_for_patching
                if not ops_ready_for_patching(self.state):
                    return (
                        "PRECHECK FAILED: change window not ready.\n"
                        "In Jira, comment:\n"
                        "  @backup team @database team @application team — stop DB/app and take backup.\n"
                        "Wait ~30 seconds for team confirmations, then re-run precheck."
                    )
            self.state.precheck_ran = True
            baseline = self.state.read_file("/opt/fixitlab/PRECHECK_BASELINE") or ""
            return (
                "=== FixitLab pre-patch baseline ===\n"
                f"{baseline.strip()}\n"
                "Precheck recorded. Apply dnf update -y then reboot."
            )
        if "postcheck" in path:
            self.state.postcheck_ran = True
            if not self.state.precheck_ran:
                return "POSTCHECK FAILED: run /opt/fixitlab/precheck.sh first"
            if not self.state.patching_done:
                return "POSTCHECK FAILED: apply dnf update -y first"
            if not self.state.rebooted_after_patch:
                return "POSTCHECK FAILED: reboot required after patching"
            from .boot_sequence import NEW_KERNEL
            if self.state.kernel != NEW_KERNEL:
                return f"POSTCHECK FAILED: expected kernel {NEW_KERNEL}, got {self.state.kernel}"
            slug = (self.state.scenario_slug or "").lower()
            if "patch" in slug and not self.state.ops_services_restarted:
                return (
                    "POSTCHECK FAILED: services not restored.\n"
                    "In Jira, ask @database team and @application team to start services after patching."
                )
            return "POSTCHECK PASSED: kernel and package state match baseline"
        script = self.state.read_file(p[1])
        if script:
            outputs = []
            for line in script.splitlines():
                if line.strip() and not line.strip().startswith("#"):
                    out = self.run(line.strip())
                    if out:
                        outputs.append(out)
            return "\n".join(outputs)
        return f"bash: {p[1]}: No such file or directory"

    def _cmd_nano(self, p: list[str]) -> str:
        if len(p) < 2:
            return "nano: missing filename"
        path = p[1]
        editor_type = "vi" if p[0] in ("vi", "vim") else "nano"
        content = self.state.read_file(path) or ""
        from .editor_mode import EditorSession
        self.state.editor = EditorSession(path, content, editor_type)
        return "__EDITOR__"

    def _cmd_pvs(self, p: list[str]) -> str:
        return self.state.lvm.format_pvs()

    def _cmd_vgs(self, p: list[str]) -> str:
        return self.state.lvm.format_vgs()

    def _cmd_lvs(self, p: list[str]) -> str:
        return self.state.lvm.format_lvs()

    def _cmd_pvcreate(self, p: list[str]) -> str:
        dev = p[-1] if len(p) > 1 else ""
        if dev not in self.state.lvm.pvs:
            pending = getattr(self.state, "pending_storage_device", "/dev/sdb")
            if not self.state.storage_disk_provisioned and dev == pending:
                return (
                    f"  Device {dev} not found.\n"
                    f"  Comment on Jira: @storage team please add a disk for LVM extension.\n"
                    f"  Wait ~30s, then run fdisk -l or echo 1 > /sys/class/scsi_host/host0/scan"
                )
            return f"  Device {dev} not found"
        ok, msg = self.state.lvm.pvcreate(dev)
        return msg if ok else f"  {msg}"

    def _cmd_vgcreate(self, p: list[str]) -> str:
        if len(p) < 3:
            return "vgcreate: missing argument"
        from .lvm_state import SimVG
        vg, pv = p[1], p[2]
        self.state.lvm.vgs[vg] = SimVG(vg, "50.00g", "50.00g", [pv])
        if pv in self.state.lvm.pvs:
            self.state.lvm.pvs[pv].vg = vg
        return f'  Volume group "{vg}" successfully created'

    def _cmd_vgextend(self, p: list[str]) -> str:
        if len(p) < 3:
            return "vgextend: missing argument"
        ok, msg = self.state.lvm.vgextend(p[1], p[2])
        return msg

    def _cmd_lvextend(self, p: list[str]) -> str:
        if len(p) < 2:
            return "lvextend: missing argument"
        lv = p[1]
        size = p[-1] if p[-1].startswith("+") or p[-1].endswith("G") else ""
        ok, msg = self.state.lvm.lvextend(lv, size)
        return msg

    def _cmd_lvdisplay(self, p: list[str]) -> str:
        lines = []
        for lv in self.state.lvm.lvs.values():
            lines.append(f"  --- Logical volume ---\n  LV Path                {lv.lv_path}\n  LV Size                {lv.size}")
        return "\n".join(lines)

    def _cmd_pvdisplay(self, p: list[str]) -> str:
        lines = []
        for pv in self.state.lvm.pvs.values():
            lines.append(f"  --- Physical volume ---\n  PV Name               {pv.device}\n  VG Name               {pv.vg or ''}\n  PV Size               {pv.size}")
        return "\n".join(lines)

    def _cmd_vgdisplay(self, p: list[str]) -> str:
        lines = []
        for vg in self.state.lvm.vgs.values():
            lines.append(f"  --- Volume group ---\n  VG Name               {vg.name}\n  VG Size               {vg.size}\n  Free  PE / Size       {vg.free}")
        return "\n".join(lines)

    def _cmd_netstat(self, p: list[str]) -> str:
        return "Active Internet connections\nProto Recv-Q Send-Q Local Address           Foreign Address         State\ntcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN\ntcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN"

    def _cmd_lsof(self, p: list[str]) -> str:
        return "COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\nsshd      412 root    3u  IPv4  12345      0t0  TCP *:22 (LISTEN)"

    def _cmd_mount(self, p: list[str]) -> str:
        if "-a" in p:
            if self.state.mount_issue_after_reboot and not self.state.mount_filesystems_fixed:
                self.state.mount_filesystems_fixed = True
                self.state.fstab_valid = True
                return "mount: mounting all filesystems in /etc/fstab"
        return self.state.lvm.format_mount()

    def _cmd_fdisk(self, p: list[str]) -> str:
        if len(p) > 1 and p[1] == "-l":
            return self.state.lvm.format_fdisk()
        dev = p[-1] if len(p) > 1 else "/dev/sda"
        return self.state.lvm.format_fdisk() if dev.startswith("/dev/sd") else f"fdisk: cannot open {dev}"

    def _cmd_virsh(self, p: list[str]) -> str:
        if len(p) > 1 and p[1] == "list":
            return " Id   Name       State\n-------------------------\n 1    rhel-guest running\n 2    win-guest  shut off"
        if "console" in p:
            return "Connected to domain rhel-guest\nEscape character is ^]\nrhel-guest login:"
        return "virsh: OK (simulation)"

    def _cmd_esxcli(self, p: list[str]) -> str:
        return "Host CPU: Intel Xeon Gold 6248R\n  32 logical CPUs\nMemory: 256 GB"

    def _cmd_vmware(self, p: list[str]) -> str:
        return "VMware Tools version: 12.3.5"

    def _cmd_ssh(self, p: list[str]) -> str:
        if len(p) < 2:
            return "usage: ssh [-l user] user@host [command]"
        target = p[-1] if len(p) > 2 and not p[1].startswith("-") else p[1]
        user = self.state.current_user
        host = target
        if "@" in target:
            user, host = target.split("@", 1)
        host_key = getattr(self, "_host_ips", {}).get(host)
        if not host_key and host in getattr(self, "_host_names", {}):
            host_key = host
        if not host_key:
            return f"ssh: connect to host {host} port 22: Connection refused"
        engine = getattr(self, "_engine", None)
        remote = engine.state.clone_for_host(host_key) if engine else self.state.clone_for_host(host_key)
        meta = getattr(self, "_host_names", {}).get(host) or getattr(self, "_host_names", {}).get(host_key) or {}
        if isinstance(meta, dict) and meta.get("ip"):
            remote.set_host_ip(meta["ip"])
        sshd = remote.services.get("sshd")
        if sshd and sshd.active != "active":
            return f"ssh: connect to host {host} port 22: Connection refused"
        remote.set_prompt_user(user if user in remote.users else "root")
        self.state = remote
        self.state.hostname = host_key
        return (
            f"Warning: Permanently added '{host}' (ED25519) to the list of known hosts.\r\n"
            f"Last login: {time.strftime('%a %b %d %H:%M:%S %Y')} from 10.0.0.5"
        )

    def _cmd_scp(self, p: list[str]) -> str:
        if len(p) < 3:
            return "usage: scp source dest"
        return f"{p[-1]}: simulated copy complete"

    def _cmd_ping(self, p: list[str]) -> str:
        host = p[1] if len(p) > 1 else "localhost"
        if host in ("localhost", "127.0.0.1") or host in getattr(self, "_host_ips", {}):
            return (
                f"PING {host} ({host if host != 'localhost' else '127.0.0.1'}) 56(84) bytes of data.\n"
                f"64 bytes from {host}: icmp_seq=1 ttl=64 time=0.3 ms\n"
                f"--- {host} ping statistics ---\n1 packets transmitted, 1 received, 0% packet loss"
            )
        return f"ping: {host}: Name or service not known"

    def _cmd_reboot(self, p: list[str]) -> str:
        return "__REBOOT__"

    def _cmd_shutdown(self, p: list[str]) -> str:
        return "System shutdown simulated."

    def _cmd_exit(self, p: list[str]) -> str:
        return "logout"
