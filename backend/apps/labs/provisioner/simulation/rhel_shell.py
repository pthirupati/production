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
        # Heredoc support: `cat > file <<EOF\n...body...\nEOF` (and `<<-`,
        # quoted delimiters). The terminal submits the whole block as one line
        # with embedded newlines, so handle it before the usual strip/parse.
        if "<<" in line and "\n" in line:
            hd = self._handle_heredoc(line)
            if hd is not None:
                return hd
        line = line.strip()

        # Interactive confirm continuation: a package manager that printed
        # "Is this ok [y/N]:" (or apt's "[Y/n]") stashed a callback in
        # state.pending_confirm; this input line (y / n / empty) resolves it.
        pending = getattr(self.state, "pending_confirm", None)
        if pending is not None:
            self.state.pending_confirm = None
            answer = line.strip().lower()
            default = pending.get("default", "n")
            if answer == "":
                answer = default
            proceed = answer in ("y", "yes")
            if proceed:
                self.state.last_exit_code = 0
                return pending["on_confirm"]()
            self.state.last_exit_code = pending.get("abort_code", 1)
            return pending.get("abort_message", "Operation aborted.")

        if not line:
            return ""
        if line.startswith("#"):
            return ""

        # Command-list operators. A real shell splits on `;` (run sequentially,
        # ignoring exit codes), `&&` (run next only on success) and `||` (run
        # next only on failure). We handle them here — before dispatch — so any
        # command can participate, honouring last_exit_code between segments.
        seq = self._split_operators(line)
        if seq is not None:
            chunks: list[str] = []
            for op, segment in seq:
                if op == "&&" and self.state.last_exit_code not in (0, None):
                    # Previous command failed — skip this &&-segment but keep the
                    # failing exit code so a later `||` still fires.
                    continue
                if op == "||" and self.state.last_exit_code in (0, None):
                    # Previous command succeeded — skip the ||-fallback.
                    continue
                out = self.run(segment.strip())
                if out:
                    chunks.append(out)
            return "\n".join(chunks)

        # A bare `VAR=value` (optionally several) assignment with no command sets
        # a shell/environment variable, like a real shell. `VAR=v cmd ...` runs
        # cmd with the var exported for that invocation.
        assign = self._parse_assignment(line)
        if assign is not None:
            names_values, remainder = assign
            for k, v in names_values:
                self.state.env[k] = self._expand(v)
            if not remainder.strip():
                self.state.last_exit_code = 0
                return ""
            line = remainder

        # Expand $VAR / ${VAR}, $(cmd) / `cmd` command substitution, ~ and globs
        # so downstream parsing sees the resolved words, as a real shell does.
        line = self._expand(line)

        # Pipelines: run each stage, feeding the previous stdout as stdin to the
        # next. Only a handful of stages consume stdin (grep, awk, wc, sort,
        # head, tail, sed); the rest ignore it as a real shell would.
        if "|" in line and not self._is_quoted_pipe(line):
            stages = [s.strip() for s in self._split_pipes(line)]
            if len(stages) > 1:
                data = ""
                for idx, stage in enumerate(stages):
                    data = self.run_with_stdin(stage, data if idx > 0 else None)
                return data

        # Pull trailing redirections (cmd > file, >> file, 2> file, 2>&1) off
        # the line so EVERY command — not just echo — can capture stdout/stderr
        # to the VFS. Returns the cleaned command plus redirect targets.
        line, redirect = self._extract_redirect(line)

        for handler in self._extra_handlers:
            try:
                parts = shlex.split(line)
            except ValueError:
                parts = line.split()
            result = handler(parts, line)
            if result is not None:
                self.state.last_exit_code = 0 if not result.startswith("bash:") else 127
                return self._apply_redirect(result, redirect)

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            return self._apply_redirect(f"bash: {exc}", redirect)

        if not parts:
            return ""

        cmd = parts[0]
        dispatch = {
            "pwd": self._cmd_pwd,
            "cd": self._cmd_cd,
            "ls": self._cmd_ls,
            "cat": self._cmd_cat,
            "echo": self._cmd_echo,
            "true": self._cmd_true,
            "false": self._cmd_false,
            "cut": self._cmd_cut,
            "tr": self._cmd_tr,
            "tee": self._cmd_tee,
            "xargs": self._cmd_xargs,
            "stat": self._cmd_stat,
            "du": self._cmd_du,
            "nproc": self._cmd_nproc,
            "basename": self._cmd_basename,
            "dirname": self._cmd_dirname,
            "readlink": self._cmd_readlink,
            "realpath": self._cmd_readlink,
            "seq": self._cmd_seq,
            "sleep": self._cmd_sleep,
            "sysctl": self._cmd_sysctl,
            "diff": self._cmd_diff,
            "md5sum": self._cmd_md5sum,
            "sha1sum": self._cmd_sha1sum,
            "sha256sum": self._cmd_sha256sum,
            "dig": self._cmd_dig,
            "nslookup": self._cmd_nslookup,
            "host": self._cmd_host,
            "nc": self._cmd_nc,
            "ncat": self._cmd_nc,
            "wget": self._cmd_wget,
            "openssl": self._cmd_openssl,
            "iptables": self._cmd_iptables,
            "ip6tables": self._cmd_iptables,
            "ufw": self._cmd_ufw,
            "watch": self._cmd_watch,
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
            "adduser": self._cmd_useradd,
            "userdel": self._cmd_userdel,
            "usermod": self._cmd_usermod,
            "groups": self._cmd_groups,
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
            "command": self._cmd_which,
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
            "microdnf": self._cmd_dnf,
            "apt": self._cmd_apt,
            "apt-get": self._cmd_apt,
            "rpm": self._cmd_rpm,
            "docker": self._cmd_docker,
            "kubectl": self._cmd_kubectl,
            "aws": self._cmd_aws,
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
            "umount": self._cmd_umount,
            "fdisk": self._cmd_fdisk,
            "parted": self._cmd_parted,
            "lvcreate": self._cmd_lvcreate,
            "mkfs": self._cmd_mkfs,
            "mkfs.xfs": self._cmd_mkfs,
            "mkfs.ext4": self._cmd_mkfs,
            "mkfs.ext3": self._cmd_mkfs,
            "blkid": self._cmd_blkid,
            "lsblk": self._cmd_lsblk,
            "mkswap": self._cmd_mkswap,
            "swapon": self._cmd_swapon,
            "swapoff": self._cmd_swapoff,
            "fsck": self._cmd_fsck,
            "fsck.xfs": self._cmd_fsck,
            "fsck.ext4": self._cmd_fsck,
            "xfs_repair": self._cmd_xfs_repair,
            "resize2fs": self._cmd_resize2fs,
            "xfs_growfs": self._cmd_xfs_growfs,
            "rescan-scsi-bus.sh": self._cmd_rescan_scsi,
            "partprobe": self._cmd_partprobe,
            "getenforce": self._cmd_getenforce,
            "setenforce": self._cmd_setenforce,
            "sestatus": self._cmd_sestatus,
            "semanage": self._cmd_semanage,
            "restorecon": self._cmd_restorecon,
            "chcon": self._cmd_chcon,
            "git": self._cmd_git,
            "virsh": self._cmd_virsh,
            "esxcli": self._cmd_esxcli,
            "vmware-toolbox-cmd": self._cmd_vmware,
            "reboot": self._cmd_reboot,
            "shutdown": self._cmd_shutdown,
        }

        fn = dispatch.get(cmd)
        if fn:
            # Default to success; commands that fail set their own non-zero code.
            # Resetting here stops a previous failure from leaking into `&&`/`||`.
            self.state.last_exit_code = 0
            out = fn(parts)
            if self._looks_like_stderr(out) and self.state.last_exit_code == 0:
                self.state.last_exit_code = 1
            return self._apply_redirect(out, redirect)

        self.state.last_exit_code = 127
        return self._apply_redirect(f"bash: {cmd}: command not found", redirect)

    @staticmethod
    def _split_pipes(line: str) -> list[str]:
        """Split on `|` that is not inside quotes."""
        parts: list[str] = []
        buf = ""
        quote = ""
        i = 0
        while i < len(line):
            ch = line[i]
            if quote:
                buf += ch
                if ch == quote:
                    quote = ""
            elif ch in ("'", '"'):
                quote = ch
                buf += ch
            elif ch == "|":
                # `||` is logical-or, not a pipe — bail out.
                if i + 1 < len(line) and line[i + 1] == "|":
                    return [line]
                parts.append(buf)
                buf = ""
            else:
                buf += ch
            i += 1
        parts.append(buf)
        return parts

    @staticmethod
    def _is_quoted_pipe(line: str) -> bool:
        """True when every `|` in the line sits inside quotes (nothing to split)."""
        return len(RHELShell._split_pipes(line)) == 1

    @staticmethod
    def _split_operators(line: str) -> list[tuple[str, str]] | None:
        """Split a command list on top-level ``;``, ``&&`` and ``||``.

        Returns a list of ``(operator, segment)`` pairs where operator is the
        connector that *precedes* the segment (``""`` for the first). Returns
        ``None`` when there is no top-level operator so the caller can take the
        single-command fast path. Operators inside quotes are ignored, and a
        bare ``|`` (pipe) is left untouched — pipelines are handled elsewhere.
        """
        segments: list[tuple[str, str]] = []
        buf = ""
        op = ""
        quote = ""
        i = 0
        n = len(line)
        found = False
        while i < n:
            ch = line[i]
            if quote:
                buf += ch
                if ch == quote:
                    quote = ""
                i += 1
                continue
            if ch in ("'", '"'):
                quote = ch
                buf += ch
                i += 1
                continue
            two = line[i:i + 2]
            if two == "&&" or two == "||":
                segments.append((op, buf))
                op = two
                buf = ""
                found = True
                i += 2
                continue
            if ch == ";" and not buf.endswith("\\"):
                segments.append((op, buf))
                op = ";"
                buf = ""
                found = True
                i += 1
                continue
            buf += ch
            i += 1
        segments.append((op, buf))
        if not found:
            return None
        # Drop empty segments produced by a trailing/leading separator.
        return [(o, s) for (o, s) in segments if s.strip()]

    # ── Expansion & assignment ───────────────────────────────────────

    _ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=")

    def _parse_assignment(self, line: str):
        """Peel leading ``VAR=value`` words off a command line.

        Returns ``(name_value_pairs, remainder)`` when the line begins with at
        least one assignment, else ``None``. Handles quoted values and the
        ``VAR=v cmd args`` prefix form. Only splits on unquoted whitespace.
        """
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            return None
        if not tokens or not self._ASSIGN_RE.match(tokens[0]):
            return None
        pairs: list[tuple[str, str]] = []
        idx = 0
        for tok in tokens:
            if self._ASSIGN_RE.match(tok):
                k, v = tok.split("=", 1)
                pairs.append((k, v))
                idx += 1
            else:
                break
        # Rebuild the remainder from the original (still-quoted) line so command
        # parsing downstream keeps quoting intact.
        remainder_tokens = tokens[idx:]
        remainder = " ".join(shlex.quote(t) for t in remainder_tokens)
        return pairs, remainder

    def _expand(self, line: str) -> str:
        """Perform the common word expansions on a command line.

        Order mirrors bash: command substitution (`$(...)` / backticks) first,
        then parameter expansion (`$VAR`, `${VAR}`), then tilde, then globbing.
        Expansions inside single quotes are left literal.
        """
        line = self._expand_command_subst(line)
        line = self._expand_vars(line)
        line = self._expand_tilde(line)
        line = self._expand_globs(line)
        return line

    def _expand_command_subst(self, line: str) -> str:
        """Resolve ``$(cmd)`` and ``` `cmd` ``` by running the inner command."""
        if "$(" not in line and "`" not in line:
            return line

        def run_inner(inner: str) -> str:
            out = self.run(inner.strip())
            # Command substitution collapses runs of whitespace/newlines.
            return " ".join(out.split())

        # $( ... ) — scan for balanced parentheses, skipping single-quoted spans.
        out = ""
        i = 0
        n = len(line)
        while i < n:
            if line[i] == "'":
                j = line.find("'", i + 1)
                if j == -1:
                    out += line[i:]
                    break
                out += line[i:j + 1]
                i = j + 1
                continue
            if line[i:i + 2] == "$(":
                depth = 1
                j = i + 2
                while j < n and depth:
                    if line[j] == "(":
                        depth += 1
                    elif line[j] == ")":
                        depth -= 1
                    if depth == 0:
                        break
                    j += 1
                inner = line[i + 2:j]
                out += run_inner(inner)
                i = j + 1
                continue
            out += line[i]
            i += 1
        line = out
        # Backtick form (no nesting).
        if "`" in line:
            line = re.sub(r"`([^`]*)`", lambda m: run_inner(m.group(1)), line)
        return line

    def _expand_vars(self, line: str) -> str:
        """Substitute ``$VAR`` / ``${VAR}`` from the environment.

        Single-quoted spans are preserved literally; everything else (including
        double-quoted spans, as in a real shell) is expanded. Unset variables
        expand to the empty string.
        """
        if "$" not in line:
            return line
        env = self.state.env
        # Provide a couple of dynamic specials the sim can answer.
        specials = {
            "HOME": self.state.users.get(self.state.current_user).home
            if self.state.current_user in self.state.users else "/root",
            "USER": self.state.current_user,
            "UID": str(self.state.users[self.state.current_user].uid)
            if self.state.current_user in self.state.users else "0",
            "PWD": self.state.cwd,
            "HOSTNAME": self.state.hostname,
            "?": str(self.state.last_exit_code or 0),
        }

        def lookup(name: str) -> str:
            if name in env:
                return env[name]
            return specials.get(name, "")

        out = ""
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if ch == "'":
                j = line.find("'", i + 1)
                if j == -1:
                    out += line[i:]
                    break
                out += line[i:j + 1]
                i = j + 1
                continue
            if ch == "$" and i + 1 < n:
                nxt = line[i + 1]
                if nxt == "{":
                    j = line.find("}", i + 2)
                    if j != -1:
                        out += lookup(line[i + 2:j])
                        i = j + 1
                        continue
                if nxt == "?":
                    out += lookup("?")
                    i += 2
                    continue
                m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", line[i + 1:])
                if m:
                    out += lookup(m.group(0))
                    i += 1 + m.end()
                    continue
            out += ch
            i += 1
        return out

    def _expand_tilde(self, line: str) -> str:
        """Expand a leading ``~`` in each unquoted word to the user's home."""
        home = (self.state.users.get(self.state.current_user).home
                if self.state.current_user in self.state.users else "/root")
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            return line
        changed = False
        for k, tok in enumerate(tokens):
            if tok == "~":
                tokens[k] = home
                changed = True
            elif tok.startswith("~/"):
                tokens[k] = home + tok[1:]
                changed = True
        if not changed:
            return line
        return " ".join(shlex.quote(t) for t in tokens)

    def _expand_globs(self, line: str) -> str:
        """Expand ``*`` / ``?`` / ``[...]`` patterns against the VFS.

        A word with no matches is left unchanged (bash's default nullglob-off
        behaviour). Quoted words are never expanded.
        """
        if not any(c in line for c in "*?["):
            return line
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            return line
        # shlex strips quotes, so we lose the "was this quoted" signal; re-scan
        # the raw line to know which tokens carried a quote and must stay literal.
        quoted = self._quoted_token_flags(line, tokens)
        out_tokens: list[str] = []
        for k, tok in enumerate(tokens):
            if quoted[k] or not any(c in tok for c in "*?["):
                out_tokens.append(tok)
                continue
            matches = self._glob_vfs(tok)
            if matches:
                out_tokens.extend(matches)
            else:
                out_tokens.append(tok)
        return " ".join(shlex.quote(t) for t in out_tokens)

    @staticmethod
    def _quoted_token_flags(line: str, tokens: list[str]) -> list[bool]:
        """Best-effort: mark tokens that appeared inside quotes in the raw line."""
        flags = [False] * len(tokens)
        # Find quoted spans and, for each, flag any token whose text sat inside.
        spans: list[tuple[int, int]] = []
        i = 0
        n = len(line)
        while i < n:
            if line[i] in ("'", '"'):
                q = line[i]
                j = line.find(q, i + 1)
                if j == -1:
                    break
                spans.append((i, j))
                i = j + 1
            else:
                i += 1
        for k, tok in enumerate(tokens):
            for s, e in spans:
                if line[s + 1:e] and tok in line[s + 1:e]:
                    flags[k] = True
                    break
        return flags

    def _glob_vfs(self, pattern: str) -> list[str]:
        """Return VFS paths matching a shell glob, preserving relative form."""
        import fnmatch

        base = self.state.resolve_path(pattern)
        # Split the pattern into a fixed directory prefix and a wildcard tail so
        # `/etc/*.conf` lists only /etc's direct children.
        ap_pattern = base
        parent = ap_pattern.rsplit("/", 1)[0] or "/"
        candidates: set[str] = set()
        # Direct children of the parent dir (files and dirs).
        entries = self.state.list_dir(parent) or []
        for name in entries:
            full = (parent.rstrip("/") + "/" + name) if parent != "/" else "/" + name
            if fnmatch.fnmatch(full, ap_pattern):
                candidates.add(full)
        # Also match any VFS path directly (covers implicit dirs).
        for path in self.state.vfs:
            if fnmatch.fnmatch(path, ap_pattern):
                candidates.add(path)
        if not candidates:
            return []
        results = sorted(candidates)
        # If the original pattern was relative, present matches relative to cwd.
        if not pattern.startswith("/") and not pattern.startswith("~"):
            cwd = self.state.cwd.rstrip("/") + "/"
            rel = [r[len(cwd):] if r.startswith(cwd) else r for r in results]
            return rel
        return results

    def _handle_heredoc(self, block: str) -> str | None:
        """Resolve a single-shot heredoc block submitted with embedded newlines.

        Supports ``cmd ... << DELIM`` / ``<<- DELIM`` / ``<< 'DELIM'``. The body
        is the lines between the opening line and the terminating delimiter. For
        ``cat > file`` / ``cat >> file`` / ``tee file`` the body is written to the
        VFS; otherwise the body is fed to the command as stdin.
        """
        lines = block.split("\n")
        header = lines[0]
        m = re.search(r"<<-?\s*[\"']?([A-Za-z_][A-Za-z0-9_]*)[\"']?", header)
        if not m:
            return None
        delim = m.group(1)
        body_lines: list[str] = []
        terminated = False
        for ln in lines[1:]:
            if ln.strip() == delim:
                terminated = True
                break
            body_lines.append(ln)
        if not terminated:
            return None
        body = "\n".join(body_lines)
        if body and not body.endswith("\n"):
            body += "\n"
        # Command portion is the header with the `<< DELIM` operator removed.
        cmd_part = header[: m.start()].strip()
        cmd, redirect = self._extract_redirect(cmd_part)
        try:
            tokens = shlex.split(cmd)
        except ValueError:
            tokens = cmd.split()
        base = tokens[0] if tokens else ""
        # `cat`/`tee` with a redirect (or `tee file`) writes the body to a file.
        target = redirect.get("stdout") if redirect else None
        append = bool(redirect and redirect.get("append"))
        if base == "tee" and len(tokens) > 1:
            target = tokens[1]
            append = "-a" in tokens
        if base in ("cat", "tee") and target:
            self.state.write_file(target, body, append=append)
            self.state.last_exit_code = 0
            return ""
        if base in ("cat", "tee", ""):
            # No file target: echo the body back (cat <<EOF without redirect).
            self.state.last_exit_code = 0
            return body.rstrip("\n")
        # Otherwise run the command with the heredoc body as stdin.
        return self.run_with_stdin(cmd_part, body)

    def run_with_stdin(self, line: str, stdin: str | None) -> str:
        """Run a single command stage with optional piped stdin."""
        prev = getattr(self, "_stdin", None)
        self._stdin = stdin
        try:
            return self.run(line)
        finally:
            self._stdin = prev

    def _stdin_lines(self) -> list[str] | None:
        data = getattr(self, "_stdin", None)
        if data is None:
            return None
        return data.splitlines()

    def _extract_redirect(self, line: str) -> tuple[str, dict | None]:
        """Split trailing redirection operators off a command line.

        Recognizes ``> f``, ``>> f``, ``2> f``, ``2>> f`` and ``2>&1``. Returns
        the command text with redirects removed and a dict describing where
        stdout/stderr should go (or None when there is no redirection).
        """
        if ">" not in line:
            return line, None
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError:
            return line, None
        cmd_tokens: list[str] = []
        redirect: dict = {"stdout": None, "stderr": None, "append": False,
                          "stderr_append": False, "merge": False, "raw": line}
        found = False
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in (">", ">>", "2>", "2>>") and i + 1 < len(tokens):
                target = tokens[i + 1]
                if tok == ">":
                    redirect["stdout"] = target
                elif tok == ">>":
                    redirect["stdout"] = target
                    redirect["append"] = True
                elif tok == "2>":
                    redirect["stderr"] = target
                elif tok == "2>>":
                    redirect["stderr"] = target
                    redirect["stderr_append"] = True
                found = True
                i += 2
                continue
            if tok == "2>&1":
                redirect["merge"] = True
                found = True
                i += 1
                continue
            # Glued forms like ">/tmp/f" or "2>/tmp/f".
            m = re.match(r"^(2?>>?)(\S+)$", tok)
            if m and not tok.startswith("/") and m.group(1):
                op, target = m.group(1), m.group(2)
                if op == ">":
                    redirect["stdout"] = target
                elif op == ">>":
                    redirect["stdout"] = target
                    redirect["append"] = True
                elif op == "2>":
                    redirect["stderr"] = target
                elif op == "2>>":
                    redirect["stderr"] = target
                    redirect["stderr_append"] = True
                found = True
                i += 1
                continue
            cmd_tokens.append(tok)
            i += 1
        if not found:
            return line, None
        # Re-quote tokens so the rebuilt line survives a second shlex.split.
        rebuilt = " ".join(shlex.quote(t) for t in cmd_tokens)
        return rebuilt, redirect

    @staticmethod
    def _looks_like_stderr(out: str) -> bool:
        """Heuristic: does this output represent an error (stderr)?

        Used so `2> file` captures error text while `> file` captures normal
        output. We can't truly split streams in the sim, so we match the common
        ``cmd: ... No such file`` / permission / invalid-argument shapes plus the
        bash-level prefixes.
        """
        if not out:
            return False
        first = out.splitlines()[0]
        if first.startswith("bash:") or first.startswith("-bash:"):
            return True
        markers = (
            "No such file or directory", "Permission denied", "command not found",
            "cannot stat", "cannot access", "cannot open", "cannot remove",
            "Invalid regular expression", "No such device", "not found",
            "is a directory", "missing operand", "Operation not permitted",
        )
        # A leading "<cmd>: <message>" line that carries one of these markers.
        if re.match(r"^[\w./-]+:\s", first) and any(m in out for m in markers):
            return True
        return False

    def _apply_redirect(self, out: str, redirect: dict | None) -> str:
        """Route command output to the VFS per the parsed redirection."""
        if not redirect:
            return out
        out = out or ""
        is_err = self._looks_like_stderr(out)
        payload = out if out.endswith("\n") or out == "" else out + "\n"

        # Writing to a SCSI host scan node triggers a bus rescan, revealing any
        # disk that was provisioned but not yet visible to the kernel.
        target = redirect.get("stdout") or redirect.get("stderr") or ""
        if "/sys/class/scsi_host/" in target and target.endswith("/scan"):
            self.state.reveal_hidden_disks()
            self.state.reveal_bridge_nic()
            return ""
        # A PCI rescan likewise surfaces a hot-added NIC for cross-tech scenarios.
        if "/sys/bus/pci/rescan" in target:
            self.state.reveal_bridge_nic()
            self.state.reveal_hidden_disks()
            return ""

        # 2>&1 with a stdout target sends everything to the stdout file.
        if redirect.get("merge") and redirect.get("stdout"):
            self.state.write_file(redirect["stdout"], payload,
                                  append=redirect.get("append", False))
            return ""

        if redirect.get("stderr") is not None and is_err:
            self.state.write_file(redirect["stderr"], payload,
                                  append=redirect.get("stderr_append", False))
            return ""

        if redirect.get("stdout") is not None:
            if is_err and not redirect.get("merge"):
                # stderr is not captured by `>`; surface it on the terminal.
                return out
            self.state.write_file(redirect["stdout"], payload,
                                  append=redirect.get("append", False))
            return ""

        if redirect.get("stderr") is not None:
            # `2> file` on a successful command: nothing to write, swallow stdout? No —
            # stdout still goes to the terminal.
            return out

        return out

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
        # Redirection (> >> 2>) is handled centrally in run()/_apply_redirect,
        # so by the time echo runs the line is already clean. We still guard the
        # legacy in-text form for any direct callers.
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
        recursive = any(a in ("-r", "-R", "-rf", "-fr", "-ra") or ("r" in a[1:] and a.startswith("-")) for a in p[1:] if a.startswith("-"))
        targets = [f for f in p[1:] if not f.startswith("-")]
        if not targets:
            return "rm: missing operand"
        for f in targets:
            ap = self.state.resolve_path(f)
            if self.state.is_dir(ap) and not recursive:
                return f"rm: cannot remove '{f}': Is a directory"
            self._remove_path(ap)
        return ""

    def _cmd_touch(self, p: list[str]) -> str:
        if len(p) < 2:
            return "touch: missing file operand"
        for f in p[1:]:
            if not self.state.read_file(f):
                self.state.write_file(f, "")
        return ""

    def _cmd_cp(self, p: list[str]) -> str:
        recursive = any(a in ("-r", "-R", "-a", "-rf", "-ra") for a in p[1:])
        args = [a for a in p[1:] if not a.startswith("-")]
        if len(args) < 2:
            return "cp: missing file operand"
        src, dst = args[0], args[-1]
        ok, err = self._copy_path(src, dst, recursive)
        return "" if ok else err

    def _copy_path(self, src: str, dst: str, recursive: bool) -> tuple[bool, str]:
        """Copy a file or (with recursive) a directory tree within the VFS."""
        src_ap = self.state.resolve_path(src)
        dst_ap = self.state.resolve_path(dst)
        if self.state.is_dir(src_ap):
            if not recursive:
                return False, f"cp: -r not specified; omitting directory '{src}'"
            # If dst is an existing directory, copy into it under the basename.
            if self.state.is_dir(dst_ap):
                dst_ap = dst_ap.rstrip("/") + "/" + src_ap.rstrip("/").split("/")[-1]
            self.state._mkdir(dst_ap)
            prefix = src_ap.rstrip("/") + "/"
            for path in sorted(self.state.vfs):
                if not path.startswith(prefix):
                    continue
                rel = path[len(prefix):]
                new_path = dst_ap.rstrip("/") + "/" + rel
                node = self.state.vfs.get(path)
                if isinstance(node, dict) and node.get("type") == "dir":
                    self.state._mkdir(new_path)
                else:
                    self.state.write_file(new_path, self.state.read_file(path) or "")
            return True, ""
        content = self.state.read_file(src_ap)
        if content is None:
            return False, f"cp: cannot stat '{src}': No such file or directory"
        # Copying a file onto a directory drops it inside the directory.
        if self.state.is_dir(dst_ap):
            dst_ap = dst_ap.rstrip("/") + "/" + src_ap.split("/")[-1]
        self.state.write_file(dst_ap, content)
        return True, ""

    def _cmd_mv(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if len(args) < 2:
            return "mv: missing file operand"
        src, dst = args[0], args[-1]
        # Atomic: only remove the source once the copy succeeds. A failed copy
        # must leave the source intact and surface the error (no concatenation).
        ok, err = self._copy_path(src, dst, recursive=True)
        if not ok:
            return err
        self._remove_path(self.state.resolve_path(src))
        return ""

    def _remove_path(self, ap: str) -> None:
        """Delete a VFS node and any descendants (for dirs)."""
        if ap in self.state.vfs:
            del self.state.vfs[ap]
        prefix = ap.rstrip("/") + "/"
        for path in [k for k in self.state.vfs if k.startswith(prefix)]:
            del self.state.vfs[path]

    def _cmd_whoami(self, p: list[str]) -> str:
        return self.state.current_user

    def _cmd_id(self, p: list[str]) -> str:
        # `id [OPTION]... [USER]` — operate on the named user if given, else the
        # current user. Look the user up in the real user table so a non-existent
        # name errors instead of silently falling back to the current user.
        args = [a for a in p[1:] if not a.startswith("-")]
        target = args[0] if args else self.state.current_user
        u = self.state.users.get(target)
        if not u:
            self.state.last_exit_code = 1
            return f"id: '{target}': no such user"
        # Supplementary groups: any group whose member list includes this uid.
        supp = []
        for gname, gids in self.state.groups.items():
            if gname == u.username:
                continue
            if u.uid in gids:
                supp.append(gname)
        groups_str = f"{u.gid}({u.username})"
        for gname in supp:
            gid = self.state.groups.get(gname, [u.uid])[0]
            groups_str += f",{gid}({gname})"
        opts = [a for a in p[1:] if a.startswith("-")]
        if "-u" in opts:
            return str(u.uid)
        if "-g" in opts:
            return str(u.gid)
        if "-un" in opts or ("-u" in opts and "-n" in opts):
            return u.username
        if "-gn" in opts:
            return u.username
        return f"uid={u.uid}({u.username}) gid={u.gid}({u.username}) groups={groups_str}"

    def _cmd_groups(self, p: list[str]) -> str:
        target = p[1] if len(p) > 1 else self.state.current_user
        u = self.state.users.get(target)
        if not u:
            self.state.last_exit_code = 1
            return f"groups: '{target}': no such user"
        names = [u.username]
        for gname, gids in self.state.groups.items():
            if gname != u.username and u.uid in gids:
                names.append(gname)
        return f"{u.username} : {' '.join(names)}"

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
            self.state.last_exit_code = 1
            return f"usermod: user '{name}' does not exist"
        u = self.state.users[name]
        if "-s" in p:
            idx = p.index("-s")
            if idx + 1 < len(p):
                u.shell = p[idx + 1]
        if "-d" in p:
            idx = p.index("-d")
            if idx + 1 < len(p):
                u.home = p[idx + 1]
        if "-L" in p:
            u.locked = True
        if "-U" in p:
            u.locked = False
        # -aG group[,group] — append the user to supplementary groups so `id`
        # and `groups` reflect the membership.
        for flag in ("-aG", "-G"):
            if flag in p:
                idx = p.index(flag)
                if idx + 1 < len(p):
                    for gname in p[idx + 1].split(","):
                        gname = gname.strip()
                        if not gname:
                            continue
                        gids = self.state.groups.setdefault(gname, [])
                        if u.uid not in gids:
                            gids.append(u.uid)
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
        # Parse flags: -i (ignore case), -v (invert), -c (count), -r/-R
        # (recursive), -q (quiet), -n (line numbers), -E (ERE — no-op here).
        flags = set()
        args: list[str] = []
        for tok in p[1:]:
            if tok.startswith("-") and len(tok) > 1 and not tok[1].isdigit():
                for ch in tok[1:]:
                    flags.add(ch)
            else:
                args.append(tok)
        if not args:
            return "Usage: grep [OPTION]... PATTERN [FILE]..."
        pattern = args[0]
        stdin_lines = self._stdin_lines()
        targets = args[1:]
        if not targets and stdin_lines is None:
            targets = [self.state.cwd]
        recursive = "r" in flags or "R" in flags
        ignore_case = "i" in flags
        invert = "v" in flags
        count_only = "c" in flags
        quiet = "q" in flags
        show_num = "n" in flags

        # Build the list of files to search, expanding directories under -r.
        files: list[str] = []
        for t in targets:
            ap = self.state.resolve_path(t)
            if self.state.is_dir(ap):
                if recursive:
                    prefix = ap.rstrip("/") + "/"
                    for fp in sorted(self.state.vfs):
                        node = self.state.vfs.get(fp)
                        if fp.startswith(prefix) and isinstance(node, dict) and node.get("type") == "file":
                            files.append(fp)
                # Non-recursive grep of a directory is an error in real grep, but
                # we silently skip to stay lenient for validators.
            else:
                files.append(t)

        try:
            rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error:
            # Match real grep's behaviour instead of bubbling up a Python error.
            self.state.last_exit_code = 2
            return f"grep: {pattern}: Invalid regular expression"

        multi = len(files) > 1 or recursive
        matches: list[str] = []
        per_file_count: dict[str, int] = {}
        # Pipe input: grep with no file operand filters stdin line-by-line.
        if not files and stdin_lines is not None:
            count = 0
            for line in stdin_lines:
                hit = bool(rx.search(line))
                if invert:
                    hit = not hit
                if hit:
                    count += 1
                    matches.append(line)
            self.state.last_exit_code = 0 if matches else 1
            if count_only:
                return str(count)
            if quiet:
                return ""
            return "\n".join(matches)
        for f in files:
            content = self.state.read_file(f)
            if content is None:
                continue
            per_file_count.setdefault(f, 0)
            for i, line in enumerate(content.splitlines(), 1):
                hit = bool(rx.search(line))
                if invert:
                    hit = not hit
                if hit:
                    per_file_count[f] += 1
                    prefix = ""
                    if multi:
                        prefix += f"{f}:"
                    if show_num:
                        prefix += f"{i}:"
                    matches.append(f"{prefix}{line}")
        if count_only:
            if multi:
                return "\n".join(f"{f}:{c}" for f, c in per_file_count.items())
            return str(sum(per_file_count.values()))
        self.state.last_exit_code = 0 if matches else 1
        if quiet:
            return ""
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
        if "-n" in p:
            n = int(p[p.index("-n") + 1])
        files = [a for a in p[1:] if not a.startswith("-") and not a.isdigit()]
        if not files and self._stdin_lines() is not None:
            return "\n".join(self._stdin_lines()[:n])
        f = files[-1] if files else p[-1]
        content = self.state.read_file(f)
        if content is None:
            return f"head: cannot open '{f}' for reading: No such file or directory"
        return "\n".join(content.splitlines()[:n])

    def _cmd_tail(self, p: list[str]) -> str:
        n = 10
        if "-n" in p:
            n = int(p[p.index("-n") + 1].lstrip("+"))
        files = [a for a in p[1:] if not a.startswith("-") and not a.isdigit()]
        if not files and self._stdin_lines() is not None:
            return "\n".join(self._stdin_lines()[-n:])
        f = files[-1] if files else p[-1]
        content = self.state.read_file(f)
        if content is None:
            return f"tail: cannot open '{f}' for reading: No such file or directory"
        return "\n".join(content.splitlines()[-n:])

    def _cmd_wc(self, p: list[str]) -> str:
        files = [a for a in p[1:] if not a.startswith("-")]
        if not files and self._stdin_lines() is not None:
            content = (getattr(self, "_stdin", "") or "")
            lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            if "-l" in p:
                return f"      {lines}"
            return f"  {lines}  {len(content.split())}  {len(content)}"
        f = files[-1] if files else p[-1]
        content = self.state.read_file(f) or ""
        lines = content.count("\n")
        words = len(content.split())
        if "-l" in p:
            return f"      {lines} {f}"
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
        base = self.state.lvm.format_df()
        # Append any extra filesystems mounted at runtime (mkfs + mount workflow).
        extra = []
        for mp, info in self.state.mounts.items():
            if mp in ("/", "/boot", "[SWAP]"):
                continue
            size_k = info.get("size_kb") or 0
            used = int(size_k * 0.03)
            avail = size_k - used
            extra.append(f"{info['device']:<32} {size_k:>10} {used:>8} {avail:>10}   3% {mp}")
        if extra:
            return base + "\n" + "\n".join(extra)
        return base

    def _cmd_free(self, p: list[str]) -> str:
        return "               total        used        free      shared  buff/cache   available\nMem:        16384000     2048000    12000000       64000     2336000    14000000\nSwap:        4194300           0     4194300"

    def _cmd_uptime(self, p: list[str]) -> str:
        now = time.time()
        up = max(0, int(now - self.state.boot_time))
        days, rem = divmod(up, 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        if days > 0:
            up_str = f"{days} day{'s' if days != 1 else ''}, {h:02d}:{m:02d}"
        elif h > 0:
            up_str = f"{h}:{m:02d}"
        else:
            up_str = f"{m} min"
        clock = time.strftime("%H:%M:%S", time.gmtime(now))
        if "-p" in p:
            parts = []
            if days:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if h:
                parts.append(f"{h} hour{'s' if h != 1 else ''}")
            parts.append(f"{m} minute{'s' if m != 1 else ''}")
            return "up " + ", ".join(parts)
        if "-s" in p:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.state.boot_time))
        return f" {clock} up {up_str},  1 user,  load average: 0.08, 0.04, 0.01"

    def _cmd_date(self, p: list[str]) -> str:
        return "Fri Jun 14 10:00:00 UTC 2026"

    def _cmd_which(self, p: list[str]) -> str:
        # Serves `which`, `command -v`, and `type`. Resolves ONLY commands that
        # are genuinely present — base coreutils/base-system binaries plus any a
        # package install (dnf/apt/rpm) recorded — so an un-installed tool is
        # honestly reported as not found. `command -v` prints the bare path and
        # `type` prints "name is /path"; plain `which` prints the path.
        prog = p[0]
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return ""
        # `command -v name` — args after stripping options start with "-v".
        if prog == "command":
            args = [a for a in p[2:] if not a.startswith("-")] or args
        results = []
        missing = False
        for name in args:
            path = self.state.resolve_binary(name)
            if path is None:
                missing = True
                if prog == "which":
                    results.append(f"which: no {name} in ({self.state.env['PATH']})")
                # command -v / type print nothing for a miss.
                continue
            if prog == "type":
                results.append(f"{name} is {path}")
            else:
                results.append(path)
        if missing:
            self.state.last_exit_code = 1
        return "\n".join(results)

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
                # Cross-tech: a NIC added in VMware appears only after the guest
                # discovers it (a rescan). Pull it from the bridge on demand so the
                # operator can configure the new link they just added in VMware.
                if dev not in self.state.network_ifs:
                    self.state.reveal_bridge_nic()
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
        # nginx is only a real command once its package (or an nginx scenario
        # preset) has put the binary on the box.
        if self.state.resolve_binary("nginx") is None:
            self.state.last_exit_code = 127
            return "bash: nginx: command not found"
        if len(p) > 1 and p[1] == "-t":
            cfg = self.state.read_file("/etc/nginx/nginx.conf")
            sites = self.state.read_file("/etc/nginx/sites-enabled/default") or ""
            if cfg is None:
                # Installed but no config yet — nginx bails opening the main conf.
                self.state.last_exit_code = 1
                return ("nginx: [emerg] open() \"/etc/nginx/nginx.conf\" failed "
                        "(2: No such file or directory)")
            if "listn" in sites or "listn" in cfg:
                self.state.last_exit_code = 1
                return ("nginx: [emerg] unknown directive \"listn\" in "
                        "/etc/nginx/sites-enabled/default:12\n"
                        "nginx: configuration file /etc/nginx/nginx.conf test failed")
            return ("nginx: the configuration file /etc/nginx/nginx.conf syntax is ok\n"
                    "nginx: configuration file /etc/nginx/nginx.conf test is successful")
        return "nginx: invalid option"

    def _cmd_pwck(self, p: list[str]) -> str:
        passwd = self.state.read_file("/etc/passwd") or ""
        for line in passwd.splitlines():
            if line and line.count(":") < 6:
                return f"pwck: line {line}: malformed entry"
        return "pwck: no errors"

    def _cmd_getent(self, p: list[str]) -> str:
        # getent <database> [key ...] — `database` is the FIRST argument. With no
        # key, dump the whole map; with keys, return only matching lines (and
        # exit 2 if none of the requested keys resolve, like real getent).
        if len(p) < 2:
            self.state.last_exit_code = 1
            return "Usage: getent [option]... database [key ...]"
        database = p[1]
        keys = p[2:]
        if database == "passwd":
            content = self.state.read_file("/etc/passwd") or ""
        elif database == "group":
            content = self.state.read_file("/etc/group") or ""
        elif database in ("hosts", "ahosts"):
            content = self.state.read_file("/etc/hosts") or ""
        else:
            self.state.last_exit_code = 1
            return f"Unknown database: {database}"
        lines = [ln for ln in content.splitlines() if ln.strip()]
        if not keys:
            return "\n".join(lines)
        matched = []
        for key in keys:
            for ln in lines:
                name = ln.split(":", 1)[0]
                # passwd/group: match by name or numeric uid/gid in field 3.
                fields = ln.split(":")
                uid = fields[2] if len(fields) > 2 else ""
                if name == key or uid == key:
                    matched.append(ln)
        if not matched:
            self.state.last_exit_code = 2
            return ""
        self.state.last_exit_code = 0
        return "\n".join(matched)

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

    @staticmethod
    def _assume_yes(p: list[str]) -> bool:
        """dnf/yum honour -y / --assumeyes / -q -y etc."""
        return any(a in ("-y", "--assumeyes") for a in p)

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
        if "list" in line and "installed" in line:
            return "Installed Packages\n" + "\n".join(
                f"{n}.x86_64    {self._pkg_ver(n)}    @System"
                for n in sorted(self.state.installed_packages))
        if "install" in p:
            names = [a for a in p[p.index("install") + 1:] if not a.startswith("-")]
            if not names:
                return "Error: Need to pass a list of pkgs to install"
            return self._dnf_install(names, assume_yes=self._assume_yes(p))
        if "remove" in line or "erase" in line:
            verb = "remove" if "remove" in p else "erase"
            names = [a for a in p[p.index(verb) + 1:] if not a.startswith("-")] if verb in p else []
            return self._dnf_remove(names)
        if "repolist" in line:
            return "repo id                    status\nrhel-9-base                enabled"
        return "dnf: command completed (simulation)"

    def _dnf_install(self, names: list[str], assume_yes: bool) -> str:
        """Render a realistic dnf transaction and (on confirm) really install."""
        from .rhel_os import PACKAGE_CATALOG, resolve_package_name
        state = self.state
        # Build the full install plan (deps first) across every requested pkg,
        # de-duplicated, skipping anything already installed.
        plan: list[str] = []
        seen: set[str] = set()
        for name in names:
            for step in state.resolve_install_plan(name):
                if step not in seen:
                    seen.add(step)
                    plan.append(step)
        header = "Updating Subscription Management repositories.\n" \
                 "Last metadata expiration check: 0:00:01 ago on Fri 14 Jun 2026 10:00:00 AM UTC."
        if not plan:
            already = [resolve_package_name(n) for n in names]
            msg = "\n".join(
                f"Package {state.installed_packages.get(n, self._pkg_nvra(n))} is already installed."
                for n in already)
            return f"{header}\n{msg}\nDependencies resolved.\nNothing to do.\nComplete!"

        def _size_kb(n: str) -> int:
            spec = PACKAGE_CATALOG.get(n)
            return spec.size_kb if spec else 512

        def _arch(n: str) -> str:
            spec = PACKAGE_CATALOG.get(n)
            return spec.arch if spec else "x86_64"

        # Dependency-resolution table.
        rows = [
            "================================================================================",
            f" {'Package':<26} {'Arch':<6} {'Version':<17} {'Repository':<19} Size",
            "================================================================================",
            "Installing:",
        ]
        repo = "rhel-9-appstream"
        for n in plan:
            rows.append(
                f" {n:<26} {_arch(n):<6} {self._pkg_ver(n):<17} {repo:<19} "
                f"{self._fmt_size(_size_kb(n))}"
            )
        total_kb = sum(_size_kb(n) for n in plan)
        installed_kb = int(total_kb * 3.4)  # unpacked footprint is larger
        rows += [
            "",
            "Transaction Summary",
            "================================================================================",
            f"Install  {len(plan)} Package{'s' if len(plan) != 1 else ''}",
            "",
            f"Total download size: {self._fmt_size(total_kb)}",
            f"Installed size: {self._fmt_size(installed_kb)}",
        ]
        table = "\n".join(header.split("\n")) + "\nDependencies resolved.\n" + "\n".join(rows)

        def _commit() -> str:
            newly = state.install_package(names[0])
            for extra in names[1:]:
                newly += [x for x in state.install_package(extra) if x not in newly]
            # newly may differ from plan if two names shared a dep; render `plan`.
            return self._render_transaction(plan)

        if not assume_yes:
            # The shell supports a follow-up input turn (see RHELShell.run's
            # pending_confirm handling), so pause for a genuine [y/N] answer.
            state.pending_confirm = {
                "on_confirm": _commit,
                "default": "n",
                "abort_code": 1,
                "abort_message": "Operation aborted.",
            }
            return table + "\n\nIs this ok [y/N]: "
        return table + "\n\n" + _commit()

    def _render_transaction(self, plan: list[str]) -> str:
        """Render the download/transaction-check/install/verify tail after the
        user confirmed (or passed -y). Assumes install_package already ran."""
        lines = ["Downloading Packages:"]
        n_total = len(plan)
        for idx, name in enumerate(plan, 1):
            nvra = self.state.installed_packages.get(name, self._pkg_nvra(name))
            lines.append(f"({idx}/{n_total}): {nvra}.rpm{'':<20} 100% |{'█' * 10}| ")
        lines += [
            "--------------------------------------------------------------------------------",
            "Running transaction check",
            "Transaction check succeeded.",
            "Running transaction test",
            "Transaction test succeeded.",
            "Running transaction",
        ]
        step = 1
        steps_total = n_total * 2
        for name in plan:
            nvra = self.state.installed_packages.get(name, self._pkg_nvra(name))
            body = nvra.rsplit(".", 1)[0] if "." in nvra else nvra  # strip .arch
            lines.append(f"  Installing : {body:<50} {step}/{steps_total}")
            step += 1
        for name in plan:
            nvra = self.state.installed_packages.get(name, self._pkg_nvra(name))
            body = nvra.rsplit(".", 1)[0] if "." in nvra else nvra
            lines.append(f"  Verifying  : {body:<50} {step}/{steps_total}")
            step += 1
        lines.append("")
        lines.append("Installed:")
        for name in plan:
            lines.append(f"  {self.state.installed_packages.get(name, self._pkg_nvra(name))}")
        lines.append("")
        lines.append("Complete!")
        return "\n".join(lines)

    def _dnf_remove(self, names: list[str]) -> str:
        from .rhel_os import resolve_package_name, PACKAGE_CATALOG
        db = self.state.installed_packages
        removed = []
        for n in names:
            canon = resolve_package_name(n)
            key = canon if canon in db else (n if n in db else None)
            if key is None:
                continue
            db.pop(key, None)
            # Drop binaries and unit(s) the package shipped.
            spec = PACKAGE_CATALOG.get(canon)
            if spec:
                for bname, _ in spec.binaries:
                    self.state.installed_binaries.pop(bname, None)
                for unit, _ in spec.units:
                    self.state.services.pop(unit, None)
            removed.append(key)
        if not removed:
            return "No match for argument: " + " ".join(names) + "\nNo packages marked for removal."
        return ("Dependencies resolved.\nRemoving:\n" + "\n".join(f" {n}" for n in removed)
                + f"\nRemove  {len(removed)} Package(s)\nRemoved:\n  "
                + "\n  ".join(removed) + "\nComplete!")

    @staticmethod
    def _fmt_size(kb: int) -> str:
        """Render a size the way dnf does: k for < 1 MB, M otherwise."""
        if kb < 1024:
            return f"{kb} k"
        return f"{kb / 1024:.1f} M"

    def _pkg_nvra(self, name: str) -> str:
        """Full NVRA for a package (catalog version if known, else a 1.0.0 stub)."""
        return self.state.catalog_nvra(name)

    def _pkg_ver(self, name: str) -> str:
        """version-release for a package (from the DB if installed, else catalog)."""
        nvra = self.state.installed_packages.get(name) or self._pkg_nvra(name)
        # strip leading "name-" and trailing ".arch"
        body = nvra[len(name) + 1:] if nvra.startswith(name + "-") else nvra
        return body.rsplit(".", 1)[0] if "." in body else body

    def _rpm_nvra(self, name: str) -> str:
        # Retained for compatibility; delegates to the catalog-aware version.
        return self._pkg_nvra(name)

    def _cmd_rpm(self, p: list[str]) -> str:
        db = self.state.installed_packages
        if "-i" in p or "--install" in p or "-U" in p or "--upgrade" in p:
            target = p[-1] if p[-1] not in ("-i", "-U", "--install", "--upgrade") else "package"
            name = target.split("/")[-1]
            if name.endswith(".rpm"):
                name = name[:-4]
            name = name.split("-")[0] or "package"
            # A real rpm -i installs just that package (no dep resolution), but
            # we route through install_package so its config/binaries/units are
            # materialised too — matching the honest post-state contract.
            self.state.install_package(name)
            db.setdefault(name, self._pkg_nvra(name))
            return f"Preparing...\n   1:{name}\nComplete!"
        if "-e" in p or "--erase" in p:
            names = [a for a in p[1:] if not a.startswith("-")]
            removed = [n for n in names if db.pop(n, None) is not None]
            if not removed and names:
                return f"error: package {names[0]} is not installed"
            return ""
        # -qa : list everything; -q <pkg> : query one (real wording on miss)
        if "-qa" in p or ("-q" in p and "-a" in p):
            return "\n".join(sorted(db.values()))
        if "-q" in p or "--query" in p:
            names = [a for a in p[1:] if not a.startswith("-")]
            if not names:
                return "no arguments given for query"
            return "\n".join(db.get(n, f"package {n} is not installed") for n in names)
        return "rpm: OK"

    # ── Debian/Ubuntu apt parity (shares the same package catalog) ──
    @staticmethod
    def _apt_assume_yes(p: list[str]) -> bool:
        return any(a in ("-y", "--yes", "--assume-yes") for a in p)

    def _cmd_apt(self, p: list[str]) -> str:
        # Subcommand is the first non-option arg after the program name.
        args = p[1:]
        sub = next((a for a in args if not a.startswith("-")), "")
        if sub in ("update",):
            return ("Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease\n"
                    "Reading package lists... Done")
        if sub in ("upgrade", "dist-upgrade", "full-upgrade"):
            return ("Reading package lists... Done\n"
                    "Building dependency tree... Done\n"
                    "Reading state information... Done\n"
                    "Calculating upgrade... Done\n"
                    "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.")
        if sub == "install":
            idx = args.index("install")
            names = [a for a in args[idx + 1:] if not a.startswith("-")]
            if not names:
                return "E: You must give at least one package to install"
            return self._apt_install(names, assume_yes=self._apt_assume_yes(p))
        if sub in ("remove", "purge", "autoremove"):
            idx = args.index(sub)
            names = [a for a in args[idx + 1:] if not a.startswith("-")]
            return self._apt_remove(names, verb=sub)
        return "Reading package lists... Done"

    def _apt_install(self, names: list[str], assume_yes: bool) -> str:
        from .rhel_os import PACKAGE_CATALOG, resolve_package_name
        state = self.state
        plan: list[str] = []
        requested_canon = [resolve_package_name(n) for n in names]
        seen: set[str] = set()
        for name in names:
            for step in state.resolve_install_plan(name):
                if step not in seen:
                    seen.add(step)
                    plan.append(step)
        head = ("Reading package lists... Done\n"
                "Building dependency tree... Done\n"
                "Reading state information... Done")
        if not plan:
            return f"{head}\n{names[-1]} is already the newest version.\n" \
                   "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded."
        # apt calls the deps (packages not explicitly requested) "additional".
        additional = [n for n in plan if n not in requested_canon]
        newpkgs = plan
        lines = [head]
        if additional:
            lines.append("The following additional packages will be installed:")
            lines.append("  " + " ".join(additional))
        lines.append("The following NEW packages will be installed:")
        lines.append("  " + " ".join(newpkgs))

        def _size_kb(n: str) -> int:
            spec = PACKAGE_CATALOG.get(n)
            return spec.size_kb if spec else 512

        total_kb = sum(_size_kb(n) for n in plan)
        disk_kb = int(total_kb * 3.4)
        lines.append(
            f"0 upgraded, {len(newpkgs)} newly installed, 0 to remove and 0 not upgraded."
        )
        lines.append(f"Need to get {self._apt_size(total_kb)} of archives.")
        lines.append(
            f"After this operation, {self._apt_size(disk_kb)} of additional disk space will be used."
        )
        body = "\n".join(lines)

        def _commit() -> str:
            for name in names:
                state.install_package(name)
            return self._render_apt_transaction(plan)

        if not assume_yes:
            state.pending_confirm = {
                "on_confirm": _commit,
                "default": "y",           # apt defaults to Yes ([Y/n])
                "abort_code": 1,
                "abort_message": "Abort.",
            }
            return body + "\nDo you want to continue? [Y/n] "
        return body + "\n" + _commit()

    def _render_apt_transaction(self, plan: list[str]) -> str:
        from .rhel_os import PACKAGE_CATALOG
        lines = []
        n_total = len(plan)
        for idx, name in enumerate(plan, 1):
            spec = PACKAGE_CATALOG.get(name)
            ver = spec.version if spec else "1.0.0"
            lines.append(
                f"Get:{idx} http://archive.ubuntu.com/ubuntu jammy/main amd64 "
                f"{name} amd64 {ver} [{self._apt_size((spec.size_kb if spec else 512))}]"
            )
        lines.append("Fetched archives in 1s")
        for name in plan:
            spec = PACKAGE_CATALOG.get(name)
            ver = spec.version if spec else "1.0.0"
            lines.append(f"Selecting previously unselected package {name}.")
            lines.append(f"Unpacking {name} ({ver}) ...")
        for name in plan:
            spec = PACKAGE_CATALOG.get(name)
            ver = spec.version if spec else "1.0.0"
            lines.append(f"Setting up {name} ({ver}) ...")
        lines.append("Processing triggers for man-db (2.10.2-1) ...")
        lines.append("Processing triggers for libc-bin (2.35-0ubuntu3) ...")
        return "\n".join(lines)

    def _apt_remove(self, names: list[str], verb: str) -> str:
        from .rhel_os import resolve_package_name, PACKAGE_CATALOG
        db = self.state.installed_packages
        removed = []
        for n in names:
            canon = resolve_package_name(n)
            key = canon if canon in db else (n if n in db else None)
            if key is None:
                continue
            db.pop(key, None)
            spec = PACKAGE_CATALOG.get(canon)
            if spec:
                for bname, _ in spec.binaries:
                    self.state.installed_binaries.pop(bname, None)
                for unit, _ in spec.units:
                    self.state.services.pop(unit, None)
            removed.append(key)
        head = ("Reading package lists... Done\n"
                "Building dependency tree... Done\n"
                "Reading state information... Done")
        if not removed:
            return f"{head}\nE: Unable to locate package {' '.join(names)}"
        word = "purged" if verb == "purge" else "removed"
        return (f"{head}\nThe following packages will be REMOVED:\n"
                f"  {' '.join(removed)}\n"
                f"0 upgraded, 0 newly installed, {len(removed)} to remove and 0 not upgraded.\n"
                + "\n".join(f"Removing {n} ...\n({word})" for n in removed))

    @staticmethod
    def _apt_size(kb: int) -> str:
        """apt reports sizes in kB / MB (decimal-ish, matching apt's wording)."""
        if kb < 1000:
            return f"{kb} kB"
        return f"{kb / 1024:.1f} MB"

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
        from .k8s_cluster import K8sCluster
        from .simulation_modules import _handle_kubectl

        if not hasattr(self, "_k8s_cluster"):
            slug = getattr(self.state, "scenario_slug", "") or ""
            sid = getattr(self.state, "session_id", "") or ""
            self._k8s_cluster = K8sCluster(slug, session_id=sid)
        cluster = self._k8s_cluster
        if sid := getattr(self.state, "session_id", "") or "":
            cluster.session_id = sid
            cluster.sync_from_vmware_bridge()
        line = " ".join(p)
        out = _handle_kubectl(cluster, p, line, self)
        return out if out is not None else f"kubectl {' '.join(p[1:])}: OK (simulation)"

    def _cmd_aws(self, p: list[str]) -> str:
        from .simulation_modules import _handle_aws_cli_local

        line = " ".join(p)
        sid = getattr(self.state, "session_id", "") or ""
        if sid:
            try:
                from apps.vmware_sim import terraform_engine as te

                slug = getattr(self.state, "scenario_slug", "") or ""
                te._ensure(sid, slug)
                res = te.apply_action(sid, "aws_cli", {"command": line.strip()})
                if res.get("ok"):
                    return res.get("output") or ""
                return res.get("error") or "Error"
            except Exception:  # noqa: BLE001
                pass
        return _handle_aws_cli_local(line.strip())

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
        """Support the common awk forms: `{print $N}`, `-F sep`, and `/pat/`.

        Reads from a file argument or piped stdin. Falls back to printing input
        lines untouched for unsupported programs rather than erroring.
        """
        field_sep = None
        args = p[1:]
        program = None
        file_arg = None
        i = 0
        while i < len(args):
            tok = args[i]
            if tok == "-F" and i + 1 < len(args):
                field_sep = args[i + 1]
                i += 2
                continue
            if tok.startswith("-F"):
                field_sep = tok[2:]
                i += 1
                continue
            if program is None:
                program = tok
            elif file_arg is None and not tok.startswith("-"):
                file_arg = tok
            i += 1

        if program is None:
            return ""
        program = program.strip()

        # Source lines: file arg wins, else piped stdin, else nothing.
        if file_arg is not None:
            content = self.state.read_file(file_arg)
            if content is None:
                return f"awk: can't open file {file_arg}"
            lines = content.splitlines()
        else:
            lines = self._stdin_lines() or []

        # Optional /pattern/ guard, optionally followed by an action block.
        pat = None
        m = re.match(r"^/(.*?)/\s*(\{.*\})?\s*$", program)
        if m:
            try:
                pat = re.compile(m.group(1))
            except re.error:
                pat = None
            action = m.group(2) or "{print $0}"
        else:
            action = program

        def split_fields(ln: str) -> list[str]:
            if field_sep:
                return ln.split(field_sep)
            return ln.split()

        out_lines: list[str] = []
        print_m = re.match(r"^\{\s*print\s*(.*?)\s*\}$", action)
        for ln in lines:
            if pat is not None and not pat.search(ln):
                continue
            if print_m is None:
                # Unsupported action — emulate the default {print $0}.
                out_lines.append(ln)
                continue
            spec = print_m.group(1).strip()
            fields = split_fields(ln)
            if spec in ("", "$0"):
                out_lines.append(ln)
                continue
            # Build the printed record from $N tokens and literal separators.
            rendered_parts: list[str] = []
            for piece in spec.split(","):
                piece = piece.strip()
                fm = re.match(r"^\$(\d+)$", piece)
                if fm:
                    n = int(fm.group(1))
                    if n == 0:
                        rendered_parts.append(ln)
                    elif 1 <= n <= len(fields):
                        rendered_parts.append(fields[n - 1])
                    else:
                        rendered_parts.append("")
                elif piece == "NF":
                    rendered_parts.append(str(len(fields)))
                else:
                    rendered_parts.append(piece.strip('"'))
            out_lines.append(" ".join(rendered_parts))
        return "\n".join(out_lines)

    def _cmd_sort(self, p: list[str]) -> str:
        reverse = "-r" in p
        numeric = "-n" in p
        files = [a for a in p[1:] if not a.startswith("-")]
        if files:
            lines = (self.state.read_file(files[-1]) or "").splitlines()
        elif self._stdin_lines() is not None:
            lines = self._stdin_lines()
        else:
            return ""
        key = (lambda s: (float(re.match(r"-?\d+(\.\d+)?", s.strip()).group()) if re.match(r"-?\d+", s.strip()) else 0)) if numeric else None
        return "\n".join(sorted(lines, key=key, reverse=reverse))

    def _cmd_tar(self, p: list[str]) -> str:
        """Create/extract tar archives inside the VFS.

        The archive payload is stored as a JSON manifest (path -> content) so
        extraction can faithfully rebuild the captured files/dirs. Supports
        -c/-x with optional -z and -v, -f <archive>, and -C <dir>.
        """
        import json
        flags = ""
        archive = None
        change_dir = None
        members: list[str] = []
        verbose = False
        i = 1
        while i < len(p):
            tok = p[i]
            if tok.startswith("-") and tok != "-":
                opt = tok.lstrip("-")
                # -f / -C may be glued to the flag cluster (e.g. -czf name).
                if "f" in opt:
                    flags += opt.replace("f", "")
                    if i + 1 < len(p):
                        archive = p[i + 1]
                        i += 2
                        continue
                elif "C" in opt:
                    flags += opt.replace("C", "")
                    if i + 1 < len(p):
                        change_dir = p[i + 1]
                        i += 2
                        continue
                else:
                    flags += opt
                if "v" in opt:
                    verbose = True
                i += 1
                continue
            if archive is None and ("f" in flags) and archive is None:
                archive = tok
            else:
                members.append(tok)
            i += 1

        create = "c" in flags
        extract = "x" in flags
        listing = "t" in flags
        if not archive:
            return "tar: refusing to read archive contents from terminal"

        if create:
            manifest: dict[str, str] = {}
            for member in members:
                ap = self.state.resolve_path(member)
                if self.state.is_dir(ap):
                    prefix = ap.rstrip("/") + "/"
                    manifest[ap] = "\0DIR\0"
                    for path in sorted(self.state.vfs):
                        if path.startswith(prefix):
                            node = self.state.vfs.get(path)
                            if isinstance(node, dict) and node.get("type") == "dir":
                                manifest[path] = "\0DIR\0"
                            else:
                                manifest[path] = self.state.read_file(path) or ""
                else:
                    content = self.state.read_file(ap)
                    if content is None:
                        return f"tar: {member}: Cannot stat: No such file or directory"
                    manifest[ap] = content
            self.state.write_file(archive, "TARSIM1\n" + json.dumps(manifest))
            return "\n".join(members) if verbose else ""

        if extract or listing:
            raw = self.state.read_file(archive)
            if raw is None:
                return f"tar: {archive}: Cannot open: No such file or directory"
            if not raw.startswith("TARSIM1\n"):
                return f"tar: {archive}: not a recognized archive (simulation)"
            try:
                manifest = json.loads(raw[len("TARSIM1\n"):])
            except json.JSONDecodeError:
                return f"tar: {archive}: corrupt archive"
            base = self.state.resolve_path(change_dir) if change_dir else None
            names = []
            for path, content in manifest.items():
                target = path
                if base:
                    target = base.rstrip("/") + "/" + path.lstrip("/")
                names.append(path)
                if listing:
                    continue
                if content == "\0DIR\0":
                    self.state._mkdir(target)
                else:
                    self.state.write_file(target, content)
            return "\n".join(names) if (verbose or listing) else ""

        return "tar: you must specify one of the -c, -x, or -t options"

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
            # Passing postcheck IS the documented completion of the patching
            # remediation; clear any preset-planted sentinel so the fail-closed
            # sweep in validation.py recognises the repaired engine state.
            from .ops_state import clear_broken_config_sentinel
            clear_broken_config_sentinel(self.state, slug)
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
            # Jira-gated LVM scenarios: the pending device stays unusable until the
            # storage team provisions it, even though it may exist as a block device.
            if not self.state.storage_disk_provisioned and dev == pending:
                return (
                    f"  Device {dev} not found.\n"
                    f"  Comment on Jira: @storage team please add a disk for LVM extension.\n"
                    f"  Wait ~30s, then run fdisk -l or echo 1 > /sys/class/scsi_host/host0/scan"
                )
            # Otherwise, if the kernel can see the block device (e.g. it was just
            # revealed by a SCSI rescan or reboot — including a disk hot-added in
            # VMware via the cross-tech bridge), pvcreate succeeds and registers it.
            if self.state.find_block_device(dev) is not None:
                from .lvm_state import SimPV
                self.state.lvm.pvs[dev] = SimPV(dev, "", "50.00g", "50.00g")
                return f'  Physical volume "{dev}" successfully created.'
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
        # Parse flags: -L/-l carry the new/added size, -r resizes the fs, and the
        # LV path is the first non-flag, non-size token (e.g. /dev/vgdata/lvdata).
        lv = ""
        size = ""
        i = 1
        while i < len(p):
            tok = p[i]
            if tok in ("-L", "--size", "-l", "--extents") and i + 1 < len(p):
                size = p[i + 1]
                i += 2
                continue
            if tok in ("-r", "--resizefs", "-n", "-y", "--yes"):
                i += 1
                continue
            if tok.startswith("/dev/") or "/" in tok:
                lv = tok
            elif not size and (tok.startswith("+") or tok.endswith("G") or "%" in tok):
                size = tok
            i += 1
        if not lv:
            lv = p[-1]
        # Normalise "+100%FREE"/"100%FREE" to "+100%FREE" so the LV genuinely grows
        # by the VG's free space (the freshly-added PV) rather than no-opping.
        if size and "%" in size and not size.startswith("+"):
            size = "+" + size
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
            # Mount every fstab entry that maps to a known formatted device.
            self._mount_from_fstab()
            return ""
        # `mount` with no args lists current mounts.
        args = [a for a in p[1:] if not a.startswith("-")]
        # Drop a `-t <type>` pair from the positional args.
        if "-t" in p:
            ti = p.index("-t")
            if ti + 1 < len(p) and p[ti + 1] in args:
                args.remove(p[ti + 1])
        if len(args) < 2:
            return self._format_mount_table()
        device, mountpoint = args[0], args[1]
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"mount: {device}: can't find in /etc/fstab or block devices"
        if not dev.fstype:
            return (f"mount: {mountpoint}: wrong fs type, bad option, bad superblock on {dev.name},\n"
                    f"       missing codepage or helper program, or other error.")
        if not self.state.is_dir(self.state.resolve_path(mountpoint)) and mountpoint not in ("[SWAP]",):
            self.state._mkdir(self.state.resolve_path(mountpoint))
        dev.mountpoint = mountpoint
        self.state.mounts[mountpoint] = {
            "device": dev.name, "fstype": dev.fstype,
            "size_kb": self.state.lvm._size_to_kb(dev.size),
        }
        return ""

    def _mount_from_fstab(self) -> None:
        fstab = self.state.read_file("/etc/fstab") or ""
        for raw in fstab.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            cols = line.split()
            if len(cols) < 2:
                continue
            dev = self.state.find_block_device(cols[0])
            if dev and dev.fstype and dev.fstype != "swap":
                dev.mountpoint = cols[1]
                self.state.mounts[cols[1]] = {
                    "device": dev.name, "fstype": dev.fstype,
                    "size_kb": self.state.lvm._size_to_kb(dev.size),
                }

    def _format_mount_table(self) -> str:
        lines = [self.state.lvm.format_mount()]
        for mp, info in self.state.mounts.items():
            if mp in ("/", "/boot", "[SWAP]"):
                continue
            lines.append(f"{info['device']} on {mp} type {info['fstype']} (rw,relatime)")
        return "\n".join(lines)

    def _cmd_umount(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return "umount: bad usage"
        target = args[0]
        for mp, info in list(self.state.mounts.items()):
            if mp == target or info["device"] == target:
                dev = self.state.find_block_device(info["device"])
                if dev:
                    dev.mountpoint = ""
                del self.state.mounts[mp]
                return ""
        dev = self.state.find_block_device(target)
        if dev and dev.mountpoint:
            dev.mountpoint = ""
            return ""
        return f"umount: {target}: not mounted"

    def _cmd_fdisk(self, p: list[str]) -> str:
        if len(p) > 1 and p[1] == "-l":
            return self._format_fdisk_list()
        dev = p[-1] if len(p) > 1 else "/dev/sda"
        if not dev.startswith("/dev/"):
            return f"fdisk: cannot open {dev}: No such file or directory"
        bdev = self.state.find_block_device(dev)
        if bdev is None:
            return f"fdisk: cannot open {dev}: No such file or directory"
        # Non-interactive create: add the next partition on this disk.
        part = self._create_partition(dev)
        if part:
            return (f"Welcome to fdisk.\nCreated a new partition {part.name.replace(dev, '').lstrip('p') or '1'} "
                    f"of type 'Linux'.\nThe partition table has been altered.\nSyncing disks.")
        return self._format_fdisk_list()

    def _format_fdisk_list(self) -> str:
        lines = []
        disks = [d for d in self.state.block_devices.values() if d.dev_type == "disk" and d.present]
        for disk in disks:
            lines.append(f"Disk {disk.name}: {disk.size}")
            for part in self.state.block_devices.values():
                if part.parent == disk.name and part.dev_type == "part":
                    lines.append(f"{part.name:<12} 2048 104857566 104855519 {part.size:>5} 83 Linux")
        return "\n".join(lines) if lines else self.state.lvm.format_fdisk()

    def _create_partition(self, disk: str):
        """Add the next sequential partition to a whole disk."""
        from .rhel_os import SimBlockDevice
        existing = [d for d in self.state.block_devices
                    if d.startswith(disk) and d != disk and d[len(disk):].lstrip("p").isdigit()]
        idx = len(existing) + 1
        # /dev/sdb -> /dev/sdb1 ; /dev/nvme0n1 -> /dev/nvme0n1p1
        sep = "p" if disk[-1].isdigit() else ""
        part_name = f"{disk}{sep}{idx}"
        if part_name in self.state.block_devices:
            return self.state.block_devices[part_name]
        part = SimBlockDevice(part_name, "50G", "part", parent=disk)
        self.state.block_devices[part_name] = part
        return part

    def _cmd_parted(self, p: list[str]) -> str:
        # parted /dev/sdb --script mkpart primary xfs 0% 100%  (or mklabel gpt)
        args = p[1:]
        device = next((a for a in args if a.startswith("/dev/")), None)
        line = " ".join(args)
        if not device:
            return "parted: no device specified"
        if self.state.find_block_device(device) is None:
            return f"Error: Could not stat device {device} - No such file or directory."
        if "mklabel" in line or "mktable" in line:
            return ""
        if "mkpart" in line:
            part = self._create_partition(device)
            return "" if part else "parted: failed to create partition"
        if "print" in line:
            return self._format_fdisk_list()
        return ""

    def _cmd_partprobe(self, p: list[str]) -> str:
        return ""

    def _cmd_rescan_scsi(self, p: list[str]) -> str:
        revealed = self.state.reveal_hidden_disks()
        # A bus rescan also surfaces a NIC hot-added in VMware for this session.
        self.state.reveal_bridge_nic()
        if revealed:
            return "\n".join(f"OLD: Host: scsi0 Channel: 00  ... new device {d}" for d in revealed) + \
                   f"\n{len(revealed)} new or changed device(s) found."
        return "0 new or changed device(s) found."

    def _cmd_lvcreate(self, p: list[str]) -> str:
        # lvcreate -L 10G -n data rhel   OR   lvcreate -l 100%FREE -n data rhel
        name = None
        size = "1G"
        vg = None
        i = 1
        while i < len(p):
            tok = p[i]
            if tok in ("-n", "--name") and i + 1 < len(p):
                name = p[i + 1]; i += 2; continue
            if tok in ("-L", "--size") and i + 1 < len(p):
                size = p[i + 1]; i += 2; continue
            if tok in ("-l", "--extents") and i + 1 < len(p):
                size = "10G"; i += 2; continue  # treat %FREE as a nominal size
            if not tok.startswith("-"):
                vg = tok
            i += 1
        if not name or not vg:
            return "  Please specify a logical volume name and volume group."
        ok, msg = self.state.lvm.lvcreate(name, vg, size)
        if ok:
            # Expose the new LV as a block device so mkfs/mount can target it.
            from .rhel_os import SimBlockDevice
            lv = self.state.lvm.lvs.get(f"{vg}/{name}")
            path = lv.lv_path if lv else f"/dev/mapper/{vg}-{name}"
            self.state.block_devices[path] = SimBlockDevice(
                path, lv.size if lv else size, "lvm", parent=vg)
            # Also expose the canonical /dev/<vg>/<name> alias.
            alias = f"/dev/{vg}/{name}"
            self.state.block_devices[alias] = self.state.block_devices[path]
        return msg

    def _cmd_mkfs(self, p: list[str]) -> str:
        # mkfs -t xfs /dev/sdb1   OR   mkfs.xfs /dev/sdb1   OR   mkfs.ext4 ...
        fstype = "ext4"
        if "." in p[0]:
            fstype = p[0].split(".", 1)[1]
        device = None
        i = 1
        while i < len(p):
            tok = p[i]
            if tok in ("-t", "--type") and i + 1 < len(p):
                fstype = p[i + 1]; i += 2; continue
            if tok.startswith("-"):
                i += 1; continue
            device = tok
            i += 1
        if not device:
            return f"mkfs.{fstype}: no device specified"
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"mkfs.{fstype}: cannot open {device}: No such file or directory"
        if dev.mountpoint:
            return f"mkfs.{fstype}: {device} is mounted; will not make a filesystem here!"
        dev.fstype = fstype
        dev.uuid = self.state.gen_uuid()
        return (f"meta-data=/dev/{device.split('/')[-1]}  isize=512\n"
                f"Creating filesystem with type {fstype} on {device}\n"
                f"Filesystem UUID: {dev.uuid}\ndone")

    def _cmd_blkid(self, p: list[str]) -> str:
        # Optionally query a single device.
        targets = [a for a in p[1:] if a.startswith("/dev/")]
        lines = []
        devs = (self.state.find_block_device(t) for t in targets) if targets else \
               (d for d in self.state.block_devices.values() if d.present)
        seen = set()
        for dev in devs:
            if dev is None or dev.name in seen or not dev.fstype:
                continue
            seen.add(dev.name)
            label = "LVM2_member" if dev.fstype == "LVM2_member" else dev.fstype
            lines.append(f'{dev.name}: UUID="{dev.uuid}" TYPE="{label}"')
        return "\n".join(lines)

    def _cmd_lsblk(self, p: list[str]) -> str:
        lines = ["NAME            MAJ:MIN RM  SIZE RO TYPE MOUNTPOINT"]
        disks = [d for d in self.state.block_devices.values() if d.dev_type == "disk" and d.present]
        for disk in sorted(disks, key=lambda d: d.name):
            short = disk.name.replace("/dev/", "")
            lines.append(f"{short:<15} 8:0    0 {disk.size:>5}  0 disk")
            children = [c for c in self.state.block_devices.values()
                        if c.parent == disk.name and c.present]
            for part in sorted(children, key=lambda d: d.name):
                pshort = part.name.replace("/dev/", "")
                mp = part.mountpoint or ""
                lines.append(f"`-{pshort:<13} 8:1    0 {part.size:>5}  0 {part.dev_type:<4} {mp}")
                # LVs carved from this partition.
                for lv in self.state.block_devices.values():
                    if lv.dev_type == "lvm" and lv.parent in (part.name, "rhel") and lv.name.startswith("/dev/mapper"):
                        lvshort = lv.name.replace("/dev/mapper/", "")
                        lines.append(f"  `-{lvshort:<11} 253:0  0 {lv.size:>5}  0 lvm  {lv.mountpoint or ''}")
        return "\n".join(lines)

    def _cmd_mkswap(self, p: list[str]) -> str:
        device = next((a for a in p[1:] if not a.startswith("-")), None)
        if not device:
            return "mkswap: no device specified"
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"mkswap: cannot open {device}: No such file or directory"
        dev.fstype = "swap"
        dev.uuid = self.state.gen_uuid()
        self.state.swaps[dev.name] = {"size": self.state.lvm._size_to_kb(dev.size), "used": 0}
        return f"Setting up swapspace version 1, size = {dev.size}\nno label, UUID={dev.uuid}"

    def _cmd_swapon(self, p: list[str]) -> str:
        if "-a" in p or "--all" in p:
            for dev in self.state.block_devices.values():
                if dev.fstype == "swap":
                    self.state.swaps.setdefault(
                        dev.name, {"size": self.state.lvm._size_to_kb(dev.size), "used": 0})
                    dev.mountpoint = "[SWAP]"
            return ""
        if "-s" in p or "--show" in p:
            lines = ["Filename                Type        Size    Used    Priority"]
            for name, info in self.state.swaps.items():
                lines.append(f"{name:<24}partition   {info['size']}    {info['used']}    -2")
            return "\n".join(lines)
        device = next((a for a in p[1:] if not a.startswith("-")), None)
        if not device:
            return "swapon: need a device"
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"swapon: cannot open {device}: No such file or directory"
        if dev.fstype != "swap":
            return f"swapon: {device}: read swap header failed (run mkswap first)"
        self.state.swaps[dev.name] = {"size": self.state.lvm._size_to_kb(dev.size), "used": 0}
        dev.mountpoint = "[SWAP]"
        return ""

    def _cmd_swapoff(self, p: list[str]) -> str:
        if "-a" in p:
            for dev in self.state.block_devices.values():
                if dev.fstype == "swap":
                    dev.mountpoint = ""
            self.state.swaps.clear()
            return ""
        device = next((a for a in p[1:] if not a.startswith("-")), None)
        if device:
            dev = self.state.find_block_device(device)
            if dev:
                dev.mountpoint = ""
            self.state.swaps.pop(dev.name if dev else device, None)
        return ""

    def _cmd_fsck(self, p: list[str]) -> str:
        device = next((a for a in p[1:] if a.startswith("/dev/")), None)
        if not device:
            return "fsck: no device specified"
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"fsck: cannot open {device}: No such file or directory"
        if dev.mountpoint:
            return f"fsck: {device} is mounted.\ne2fsck: Cannot continue, aborting."
        return f"fsck from util-linux\n{device}: clean, files/blocks"

    def _cmd_xfs_repair(self, p: list[str]) -> str:
        device = next((a for a in p[1:] if a.startswith("/dev/")), None)
        if not device:
            return "xfs_repair: no device specified"
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"xfs_repair: {device}: No such file or directory"
        if dev.mountpoint:
            return (f"xfs_repair: {device} contains a mounted filesystem\n"
                    f"xfs_repair: cannot repair a mounted filesystem")
        return ("Phase 1 - find and verify superblock...\n"
                "Phase 7 - verify and correct link counts...\ndone")

    def _cmd_resize2fs(self, p: list[str]) -> str:
        device = next((a for a in p[1:] if a.startswith("/dev/")), None)
        if not device:
            return "resize2fs: no device specified"
        dev = self.state.find_block_device(device)
        if dev is None:
            return f"resize2fs: cannot open {device}: No such file or directory"
        # Grow recorded size to track the underlying LV after lvextend.
        lv = next((l for l in self.state.lvm.lvs.values() if l.lv_path == device), None)
        if lv:
            dev.size = lv.size.replace(".00g", "G").replace("g", "G")
            mp = dev.mountpoint
            if mp in self.state.mounts:
                self.state.mounts[mp]["size_kb"] = self.state.lvm._size_to_kb(lv.size)
        return f"resize2fs: The filesystem on {device} is now resized."

    def _cmd_xfs_growfs(self, p: list[str]) -> str:
        target = next((a for a in p[1:] if not a.startswith("-")), None)
        if not target:
            return "xfs_growfs: no mountpoint specified"
        # xfs_growfs takes a mountpoint; map back to its LV to grow the size.
        lv = next((l for l in self.state.lvm.lvs.values() if l.mount == target), None)
        if lv:
            dev = self.state.find_block_device(lv.lv_path)
            if dev:
                dev.size = lv.size.replace(".00g", "G").replace("g", "G")
            if target in self.state.mounts:
                self.state.mounts[target]["size_kb"] = self.state.lvm._size_to_kb(lv.size)
        return "data blocks changed"

    # ── SELinux ──────────────────────────────────────────────────────

    def _cmd_getenforce(self, p: list[str]) -> str:
        return self.state.selinux_mode

    def _cmd_setenforce(self, p: list[str]) -> str:
        if len(p) < 2:
            return "usage: setenforce [ Enforcing | Permissive | 1 | 0 ]"
        arg = p[1]
        if arg in ("1", "Enforcing", "enforcing"):
            if self.state.selinux_mode == "Disabled":
                return "setenforce: SELinux is disabled"
            self.state.selinux_mode = "Enforcing"
        elif arg in ("0", "Permissive", "permissive"):
            if self.state.selinux_mode == "Disabled":
                return "setenforce: SELinux is disabled"
            self.state.selinux_mode = "Permissive"
        else:
            return f"setenforce: invalid argument '{arg}'"
        return ""

    def _cmd_sestatus(self, p: list[str]) -> str:
        mode = self.state.selinux_mode
        enabled = "enabled" if mode != "Disabled" else "disabled"
        current = mode if mode != "Disabled" else "disabled"
        return (
            f"SELinux status:                 {enabled}\n"
            f"SELinuxfs mount:                /sys/fs/selinux\n"
            f"SELinux root directory:         /etc/selinux\n"
            f"Loaded policy name:             targeted\n"
            f"Current mode:                   {current.lower()}\n"
            f"Mode from config file:          {('enforcing' if mode != 'Disabled' else 'disabled')}\n"
            f"Policy MLS status:              enabled\n"
            f"Policy deny_unknown status:     allowed\n"
            f"Max kernel policy version:      33"
        )

    def _cmd_semanage(self, p: list[str]) -> str:
        if len(p) < 2:
            return "semanage: missing subcommand"
        sub = p[1]
        if sub == "port":
            if "-a" in p or "--add" in p:
                # semanage port -a -t http_port_t -p tcp 8080
                sel_type = self._opt_value(p, "-t") or self._opt_value(p, "--type")
                port = next((a for a in p[2:] if a.isdigit()), None)
                if sel_type and port:
                    self.state.selinux_ports.setdefault(sel_type, [])
                    if int(port) not in self.state.selinux_ports[sel_type]:
                        self.state.selinux_ports[sel_type].append(int(port))
                return ""
            if "-l" in p or "--list" in p:
                lines = ["SELinux Port Type              Proto    Port Number"]
                for t, ports in self.state.selinux_ports.items():
                    lines.append(f"{t:<30} tcp      {', '.join(str(x) for x in ports)}")
                return "\n".join(lines)
            return ""
        if sub == "fcontext":
            if "-a" in p or "--add" in p:
                sel_type = self._opt_value(p, "-t") or self._opt_value(p, "--type")
                path = p[-1]
                if sel_type and path:
                    self.state.selinux_fcontexts.append({"path": path, "type": sel_type})
                return ""
            if "-l" in p or "--list" in p:
                return "\n".join(f"{e['path']}    {e['type']}" for e in self.state.selinux_fcontexts)
            return ""
        return f"semanage: unsupported object '{sub}' (simulation)"

    @staticmethod
    def _opt_value(p: list[str], flag: str) -> str | None:
        if flag in p:
            idx = p.index(flag)
            if idx + 1 < len(p):
                return p[idx + 1]
        return None

    def _cmd_restorecon(self, p: list[str]) -> str:
        # restorecon -Rv /path : apply the matching fcontext rule to the file.
        paths = [a for a in p[1:] if not a.startswith("-")]
        verbose = any("v" in a for a in p[1:] if a.startswith("-"))
        out = []
        for path in paths:
            ap = self.state.resolve_path(path)
            ctx = None
            for rule in self.state.selinux_fcontexts:
                if rule["path"].rstrip("(/.*)").rstrip("/") in ap or ap.startswith(rule["path"].split("(")[0].rstrip("/")):
                    ctx = rule["type"]
            if ctx is None:
                ctx = "default_t"
            self.state.file_contexts[ap] = f"system_u:object_r:{ctx}:s0"
            if verbose:
                out.append(f"Relabeled {ap} to {self.state.file_contexts[ap]}")
        return "\n".join(out)

    def _cmd_chcon(self, p: list[str]) -> str:
        # chcon -t httpd_sys_content_t /var/www/html/index.html
        sel_type = self._opt_value(p, "-t") or self._opt_value(p, "--type")
        full_ctx = self._opt_value(p, "--reference")
        paths = [a for a in p[1:] if not a.startswith("-") and a != sel_type]
        # A bare context string form: chcon system_u:object_r:httpd_sys_content_t:s0 file
        if not sel_type and not full_ctx and len(paths) >= 2 and ":" in paths[0]:
            ctx = paths[0]
            paths = paths[1:]
            for path in paths:
                self.state.file_contexts[self.state.resolve_path(path)] = ctx
            return ""
        for path in paths:
            ap = self.state.resolve_path(path)
            if self.state.find_block_device(ap) is None and self.state.read_file(ap) is None and not self.state.is_dir(ap):
                return f"chcon: cannot access '{path}': No such file or directory"
            if sel_type:
                self.state.file_contexts[ap] = f"unconfined_u:object_r:{sel_type}:s0"
        return ""

    def _cmd_git(self, p: list[str]) -> str:
        from .git_commands import run_git
        # Re-split from the raw line so quoted args (commit -m "msg") survive.
        return run_git(self.state, p, " ".join(p))

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

    # ── Core coreutils / text tools ──────────────────────────────────

    def _cmd_true(self, p: list[str]) -> str:
        self.state.last_exit_code = 0
        return ""

    def _cmd_false(self, p: list[str]) -> str:
        self.state.last_exit_code = 1
        return ""

    def _input_lines(self, files: list[str], err_prefix: str) -> tuple[list[str] | None, str]:
        """Read lines from file args, else piped stdin. Returns (lines, error)."""
        if files:
            content = self.state.read_file(files[-1])
            if content is None:
                return None, f"{err_prefix}: {files[-1]}: No such file or directory"
            return content.splitlines(), ""
        stdin = self._stdin_lines()
        return (stdin if stdin is not None else []), ""

    def _cmd_cut(self, p: list[str]) -> str:
        # cut -d: -f1  |  cut -f2  |  cut -c1-3  (field or char selection)
        delim = "\t"
        fields = None
        chars = None
        files: list[str] = []
        i = 1
        while i < len(p):
            tok = p[i]
            if tok == "-d" and i + 1 < len(p):
                delim = p[i + 1]; i += 2; continue
            if tok.startswith("-d"):
                delim = tok[2:] or "\t"; i += 1; continue
            if tok == "-f" and i + 1 < len(p):
                fields = p[i + 1]; i += 2; continue
            if tok.startswith("-f"):
                fields = tok[2:]; i += 1; continue
            if tok == "-c" and i + 1 < len(p):
                chars = p[i + 1]; i += 2; continue
            if tok.startswith("-c"):
                chars = tok[2:]; i += 1; continue
            if not tok.startswith("-"):
                files.append(tok)
            i += 1
        lines, err = self._input_lines(files, "cut")
        if lines is None:
            return err

        def indices(spec: str, upper: int) -> list[int]:
            out: list[int] = []
            for part in spec.split(","):
                if "-" in part:
                    a, b = part.split("-", 1)
                    lo = int(a) if a else 1
                    hi = int(b) if b else upper
                    out.extend(range(lo, hi + 1))
                elif part:
                    out.append(int(part))
            return out

        result = []
        for ln in lines:
            if chars is not None:
                idx = indices(chars, len(ln))
                result.append("".join(ln[j - 1] for j in idx if 1 <= j <= len(ln)))
            elif fields is not None:
                cols = ln.split(delim)
                # cut prints lines without the delimiter unchanged.
                if delim not in ln:
                    result.append(ln)
                    continue
                idx = indices(fields, len(cols))
                picked = [cols[j - 1] for j in idx if 1 <= j <= len(cols)]
                result.append(delim.join(picked))
            else:
                result.append(ln)
        return "\n".join(result)

    def _cmd_tr(self, p: list[str]) -> str:
        # tr SET1 SET2  |  tr -d SET  |  tr -s SET  (operates on stdin)
        delete = "-d" in p
        squeeze = "-s" in p
        args = [a for a in p[1:] if not a.startswith("-")]
        data = getattr(self, "_stdin", None) or ""

        def expand(s: str) -> str:
            out = ""
            i = 0
            while i < len(s):
                if i + 2 < len(s) and s[i + 1] == "-":
                    for c in range(ord(s[i]), ord(s[i + 2]) + 1):
                        out += chr(c)
                    i += 3
                else:
                    out += s[i]
                    i += 1
            # Common POSIX class shortcuts.
            return out

        set1 = expand(args[0]) if args else ""
        set1 = set1.replace("[:lower:]", "abcdefghijklmnopqrstuvwxyz").replace(
            "[:upper:]", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if delete:
            return "".join(c for c in data if c not in set1)
        if squeeze and len(args) == 1:
            out = ""
            prev = None
            for c in data:
                if c in set1 and c == prev:
                    continue
                out += c
                prev = c
            return out
        set2 = expand(args[1]) if len(args) > 1 else ""
        set2 = set2.replace("[:lower:]", "abcdefghijklmnopqrstuvwxyz").replace(
            "[:upper:]", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        if not set2:
            return data
        table = {}
        for k, c in enumerate(set1):
            table[c] = set2[k] if k < len(set2) else set2[-1]
        return "".join(table.get(c, c) for c in data)

    def _cmd_tee(self, p: list[str]) -> str:
        # tee [-a] FILE... — write stdin to files AND pass it through.
        append = "-a" in p
        files = [a for a in p[1:] if not a.startswith("-")]
        data = getattr(self, "_stdin", None) or ""
        payload = data if data.endswith("\n") or data == "" else data + "\n"
        for f in files:
            self.state.write_file(f, payload, append=append)
        # tee echoes stdin on to its own stdout.
        return data.rstrip("\n")

    def _cmd_xargs(self, p: list[str]) -> str:
        # xargs [-I{}] CMD ... — build a command from the leading command args
        # and the whitespace-split stdin words, then run it once.
        data = getattr(self, "_stdin", None) or ""
        words = data.split()
        args = p[1:]
        replace = None
        if args and args[0] == "-I" and len(args) > 1:
            replace = args[1]
            args = args[2:]
        elif args and args[0].startswith("-I"):
            replace = args[0][2:]
            args = args[1:]
        if not args:
            # Default command is echo.
            return " ".join(words)
        if replace:
            outputs = []
            for w in (words or [""]):
                cmd = " ".join(a.replace(replace, w) for a in args)
                out = self.run(cmd)
                if out:
                    outputs.append(out)
            return "\n".join(outputs)
        cmd = " ".join(args) + (" " + " ".join(words) if words else "")
        return self.run(cmd)

    def _cmd_stat(self, p: list[str]) -> str:
        fmt = None
        files: list[str] = []
        i = 1
        while i < len(p):
            tok = p[i]
            if tok in ("-c", "--format") and i + 1 < len(p):
                fmt = p[i + 1]; i += 2; continue
            if tok.startswith("-c"):
                fmt = tok[2:]; i += 1; continue
            if not tok.startswith("-"):
                files.append(tok)
            i += 1
        if not files:
            return "stat: missing operand"
        out = []
        for f in files:
            ap = self.state.resolve_path(f)
            node = self.state.vfs.get(ap)
            is_dir = self.state.is_dir(ap)
            if node is None and not is_dir:
                out.append(f"stat: cannot statx '{f}': No such file or directory")
                self.state.last_exit_code = 1
                continue
            mode = node.get("mode", "755" if is_dir else "644") if isinstance(node, dict) else "644"
            owner = node.get("owner", "root") if isinstance(node, dict) else "root"
            group = node.get("group", owner) if isinstance(node, dict) else "root"
            content = node.get("content", "") if isinstance(node, dict) else ""
            size = 4096 if is_dir else len(content)
            ftype = "directory" if is_dir else "regular file"
            if fmt:
                mapping = {
                    "%n": f, "%s": str(size), "%a": mode, "%U": owner, "%G": group,
                    "%F": ftype, "%i": "131074", "%h": "1",
                }
                rendered = fmt
                for k, v in mapping.items():
                    rendered = rendered.replace(k, v)
                out.append(rendered)
            else:
                out.append(
                    f"  File: {f}\n"
                    f"  Size: {size:<15} Blocks: 8          IO Block: 4096   {ftype}\n"
                    f"Access: (0{mode}/{'d' if is_dir else '-'}rwxr-xr-x)  Uid: (    0/{owner:>6})   Gid: (    0/{group:>6})\n"
                    f"Access: 2026-06-14 10:00:00.000000000 +0000\n"
                    f"Modify: 2026-06-14 10:00:00.000000000 +0000\n"
                    f"Change: 2026-06-14 10:00:00.000000000 +0000"
                )
        return "\n".join(out)

    def _cmd_du(self, p: list[str]) -> str:
        summarize = "-s" in "".join(a for a in p[1:] if a.startswith("-"))
        human = "h" in "".join(a for a in p[1:] if a.startswith("-"))
        targets = [a for a in p[1:] if not a.startswith("-")] or [self.state.cwd]

        def size_of(ap: str) -> int:
            total = 0
            if self.state.is_dir(ap):
                prefix = ap.rstrip("/") + "/"
                for path, node in self.state.vfs.items():
                    if (path == ap or path.startswith(prefix)) and isinstance(node, dict) \
                            and node.get("type") == "file":
                        total += len(node.get("content", ""))
                return total or 4096
            content = self.state.read_file(ap)
            return len(content) if content is not None else 0

        def human_kb(nbytes: int) -> str:
            kb = max(1, (nbytes + 1023) // 1024)
            if not human:
                return str(kb)
            if kb < 1024:
                return f"{kb}K"
            return f"{kb / 1024:.1f}M"

        out = []
        for t in targets:
            ap = self.state.resolve_path(t)
            if self.state.read_file(ap) is None and not self.state.is_dir(ap):
                out.append(f"du: cannot access '{t}': No such file or directory")
                self.state.last_exit_code = 1
                continue
            out.append(f"{human_kb(size_of(ap))}\t{t}")
        return "\n".join(out)

    def _cmd_nproc(self, p: list[str]) -> str:
        return str(getattr(self.state, "cpu_count", 4))

    def _cmd_basename(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return "basename: missing operand"
        name = args[0].rstrip("/").split("/")[-1] or "/"
        if len(args) > 1 and name.endswith(args[1]):
            name = name[: -len(args[1])] or name
        return name

    def _cmd_dirname(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return "dirname: missing operand"
        path = args[0].rstrip("/")
        if "/" not in path:
            return "."
        head = path.rsplit("/", 1)[0]
        return head or "/"

    def _cmd_readlink(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return ""
        # No symlink graph in the VFS — resolve to the canonical absolute path.
        return self.state.resolve_path(args[0])

    def _cmd_seq(self, p: list[str]) -> str:
        nums = [a for a in p[1:] if not a.startswith("-") or a.lstrip("-").isdigit()]
        try:
            vals = [int(x) for x in nums]
        except ValueError:
            return "seq: invalid floating point argument"
        if len(vals) == 1:
            start, step, end = 1, 1, vals[0]
        elif len(vals) == 2:
            start, step, end = vals[0], 1, vals[1]
        elif len(vals) >= 3:
            start, step, end = vals[0], vals[1], vals[2]
        else:
            return "seq: missing operand"
        if step == 0:
            return ""
        out = []
        v = start
        if step > 0:
            while v <= end:
                out.append(str(v)); v += step
        else:
            while v >= end:
                out.append(str(v)); v += step
        return "\n".join(out)

    def _cmd_sleep(self, p: list[str]) -> str:
        # Do NOT actually block the terminal in the sim — just succeed.
        self.state.last_exit_code = 0
        return ""

    def _cmd_sysctl(self, p: list[str]) -> str:
        store = getattr(self.state, "sysctl", None)
        if store is None:
            store = {
                "vm.swappiness": "30",
                "net.ipv4.ip_forward": "0",
                "kernel.hostname": self.state.hostname,
                "fs.file-max": "9223372036854775807",
                "net.ipv4.tcp_syncookies": "1",
                "vm.max_map_count": "65530",
            }
            self.state.sysctl = store
        args = [a for a in p[1:] if not a.startswith("-")]
        if "-a" in p or "--all" in p:
            return "\n".join(f"{k} = {v}" for k, v in store.items())
        if "-w" in p or (args and "=" in args[0]):
            for a in args:
                if "=" in a:
                    k, v = a.split("=", 1)
                    store[k.strip()] = v.strip()
                    return f"{k.strip()} = {v.strip()}"
            return ""
        if not args:
            return "\n".join(f"{k} = {v}" for k, v in store.items())
        out = []
        for key in args:
            if key in store:
                out.append(f"{key} = {store[key]}")
            else:
                out.append(f"sysctl: cannot stat /proc/sys/{key.replace('.', '/')}: No such file or directory")
                self.state.last_exit_code = 255
        return "\n".join(out)

    def _cmd_diff(self, p: list[str]) -> str:
        files = [a for a in p[1:] if not a.startswith("-")]
        if len(files) < 2:
            return "diff: missing operand"
        a = self.state.read_file(files[0])
        b = self.state.read_file(files[1])
        if a is None:
            self.state.last_exit_code = 2
            return f"diff: {files[0]}: No such file or directory"
        if b is None:
            self.state.last_exit_code = 2
            return f"diff: {files[1]}: No such file or directory"
        if a == b:
            self.state.last_exit_code = 0
            return ""
        import difflib
        self.state.last_exit_code = 1
        if "-u" in p or "--unified" in p:
            ud = difflib.unified_diff(
                a.splitlines(), b.splitlines(),
                fromfile=files[0], tofile=files[1], lineterm="")
            return "\n".join(ud)
        # Default (normal) diff: emit a compact ed-style summary.
        alines, blines = a.splitlines(), b.splitlines()
        out = []
        for k, (x, y) in enumerate(zip(alines, blines), 1):
            if x != y:
                out.append(f"{k}c{k}\n< {x}\n---\n> {y}")
        if len(alines) != len(blines):
            out.append(f"{min(len(alines), len(blines)) + 1}c: files differ in length")
        return "\n".join(out)

    def _hash_targets(self, p: list[str], algo, label: str) -> str:
        import hashlib
        files = [a for a in p[1:] if not a.startswith("-")]
        if not files and self._stdin_lines() is not None:
            data = (getattr(self, "_stdin", "") or "").encode()
            return f"{algo(data).hexdigest()}  -"
        out = []
        for f in files:
            content = self.state.read_file(f)
            if content is None:
                out.append(f"{label}: {f}: No such file or directory")
                self.state.last_exit_code = 1
                continue
            out.append(f"{algo(content.encode()).hexdigest()}  {f}")
        return "\n".join(out)

    def _cmd_md5sum(self, p: list[str]) -> str:
        import hashlib
        return self._hash_targets(p, hashlib.md5, "md5sum")

    def _cmd_sha1sum(self, p: list[str]) -> str:
        import hashlib
        return self._hash_targets(p, hashlib.sha1, "sha1sum")

    def _cmd_sha256sum(self, p: list[str]) -> str:
        import hashlib
        return self._hash_targets(p, hashlib.sha256, "sha256sum")

    # ── Networking / TLS tools ───────────────────────────────────────

    def _resolve_dns(self, name: str) -> str | None:
        """Resolve a hostname the way the sim's /etc/hosts + known IPs would."""
        if name in ("localhost", "127.0.0.1", "::1"):
            return "127.0.0.1"
        hosts = self.state.read_file("/etc/hosts") or ""
        for raw in hosts.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            cols = line.split()
            if name in cols[1:]:
                return cols[0]
        host_ips = getattr(self, "_host_ips", {})
        if name in host_ips:
            return host_ips[name]
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", name):
            return name
        # A handful of well-known public names resolve deterministically so DNS
        # lookups in labs succeed offline.
        known = {
            "example.com": "93.184.216.34",
            "google.com": "142.250.72.14",
            "github.com": "140.82.121.4",
        }
        return known.get(name)

    def _cmd_dig(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-") and not a.startswith("@")]
        short = "+short" in p
        args = [a for a in args if not a.startswith("+")]
        rtype = "A"
        name = ""
        for a in args:
            if a.upper() in ("A", "AAAA", "MX", "TXT", "NS", "CNAME", "PTR", "SOA"):
                rtype = a.upper()
            else:
                name = a
        if not name:
            return "; <<>> DiG 9.16 <<>> \n;; global options: +cmd"
        ip = self._resolve_dns(name)
        if short:
            return ip or ""
        if ip is None:
            return (f"; <<>> DiG 9.16.23 <<>> {name}\n;; ->>HEADER<<- opcode: QUERY, status: NXDOMAIN\n"
                    f";; QUESTION SECTION:\n;{name}.\t\tIN\t{rtype}")
        return (f"; <<>> DiG 9.16.23 <<>> {name}\n"
                f";; ->>HEADER<<- opcode: QUERY, status: NOERROR\n\n"
                f";; QUESTION SECTION:\n;{name}.\t\tIN\t{rtype}\n\n"
                f";; ANSWER SECTION:\n{name}.\t300\tIN\t{rtype}\t{ip}\n\n"
                f";; Query time: 1 msec\n;; SERVER: 127.0.0.53#53(127.0.0.53)")

    def _cmd_nslookup(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return "> "
        name = args[0]
        ip = self._resolve_dns(name)
        if ip is None:
            return (f"Server:\t\t127.0.0.53\nAddress:\t127.0.0.53#53\n\n"
                    f"** server can't find {name}: NXDOMAIN")
        return (f"Server:\t\t127.0.0.53\nAddress:\t127.0.0.53#53\n\n"
                f"Non-authoritative answer:\nName:\t{name}\nAddress: {ip}")

    def _cmd_host(self, p: list[str]) -> str:
        args = [a for a in p[1:] if not a.startswith("-")]
        if not args:
            return "Usage: host [options] name"
        name = args[0]
        ip = self._resolve_dns(name)
        if ip is None:
            return f"Host {name} not found: 3(NXDOMAIN)"
        return f"{name} has address {ip}"

    def _cmd_nc(self, p: list[str]) -> str:
        # nc -zv HOST PORT — connectivity probe. Succeeds when the port maps to a
        # running service and (for the local host) the firewall allows it.
        args = [a for a in p[1:] if not a.startswith("-")]
        if len(args) < 2:
            return "nc: missing host/port"
        hostarg, portarg = args[0], args[1]
        try:
            port = int(portarg)
        except ValueError:
            return f"nc: port number invalid: {portarg}"
        ip = self._resolve_dns(hostarg)
        if ip is None:
            return f"nc: getaddrinfo for host \"{hostarg}\" port {port}: Name or service not known"
        local = ip in ("127.0.0.1",) or hostarg in ("localhost", self.state.hostname)
        st = self.state if local else self._server_state()
        port_to_svc = {22: "sshd", 80: "nginx", 443: "nginx", 3306: "mysqld",
                       5432: "postgresql", 6379: "redis", 8080: "nginx"}
        svc_name = port_to_svc.get(port)
        svc = st.services.get(svc_name) if svc_name else None
        listening = bool(svc and svc.active == "active") or port == 22
        if local and listening and not st.firewall.is_port_open(port) and port != 22:
            listening = False
        if listening:
            return (f"Ncat: Version 7.92\n"
                    f"Connection to {ip} {port} port [tcp/*] succeeded!")
        self.state.last_exit_code = 1
        return f"Ncat: Connection refused."

    def _cmd_wget(self, p: list[str]) -> str:
        url = next((a for a in p[1:] if a.startswith("http") or "://" in a
                    or "." in a), "")
        if not url:
            return "wget: missing URL"
        # Reuse the curl body plumbing for the actual fetch semantics.
        body = self._cmd_curl(["curl", url])
        if body.startswith("curl:"):
            reason = body.split(")", 1)[-1].strip() or "failed"
            self.state.last_exit_code = 4
            return (f"--2026-06-14 10:00:00--  {url}\n"
                    f"Resolving host... failed: {reason}.")
        host = url.split("://", 1)[-1].split("/", 1)[0]
        return (f"--2026-06-14 10:00:00--  {url}\n"
                f"Resolving {host}... 127.0.0.1\nConnecting to {host}|127.0.0.1|:80... connected.\n"
                f"HTTP request sent, awaiting response... 200 OK\n"
                f"Length: {len(body)} [text/html]\nSaving to: 'index.html'\n\n"
                f"'index.html' saved [{len(body)}/{len(body)}]")

    def _cmd_openssl(self, p: list[str]) -> str:
        if len(p) < 2:
            return "usage: openssl command [ options ]"
        sub = p[1]
        if sub == "version":
            return "OpenSSL 3.0.7 1 Nov 2022 (Library: OpenSSL 3.0.7 1 Nov 2022)"
        if sub == "rand":
            n = 16
            for tok in p[2:]:
                if tok.isdigit():
                    n = int(tok)
            import hashlib
            digest = hashlib.sha256(f"{self.state.hostname}:{n}".encode()).hexdigest()
            if "-hex" in p:
                return digest[: n * 2]
            return digest[: n * 2]
        if sub == "x509":
            return ("subject=CN = sim.fixitlab.local\n"
                    "issuer=CN = FixitLab Root CA\n"
                    "notBefore=Jun 14 10:00:00 2026 GMT\n"
                    "notAfter=Jun 14 10:00:00 2027 GMT")
        if sub in ("genrsa", "genpkey"):
            return "..+++++\nGenerating RSA private key (simulation)"
        if sub == "s_client":
            return ("CONNECTED(00000003)\n"
                    "depth=0 CN = sim.fixitlab.local\n"
                    "Verify return code: 0 (ok)")
        if sub in ("dgst", "sha256"):
            files = [a for a in p[2:] if not a.startswith("-")]
            if files:
                import hashlib
                content = self.state.read_file(files[0]) or ""
                return f"SHA256({files[0]})= {hashlib.sha256(content.encode()).hexdigest()}"
        return f"openssl {sub}: OK (simulation)"

    def _cmd_iptables(self, p: list[str]) -> str:
        # A thin veneer over the firewalld state so port-open checks stay
        # consistent. Supports -L/-S listing and -A ... --dport N -j ACCEPT.
        fw = self.state.firewall
        line = " ".join(p)
        if "-L" in p or "--list" in p:
            open_ports = []
            z = fw.runtime.get(fw.default_zone, {})
            for ptok in z.get("ports", []):
                open_ports.append(ptok.split("/")[0])
            if "http" in z.get("services", []):
                open_ports.append("80")
            rules = "\n".join(
                f"ACCEPT     tcp  --  anywhere    anywhere    tcp dpt:{pt}"
                for pt in sorted(set(open_ports), key=lambda x: int(x) if x.isdigit() else 0))
            return ("Chain INPUT (policy ACCEPT)\n"
                    "target     prot opt source      destination\n"
                    f"{rules}" if rules else
                    "Chain INPUT (policy ACCEPT)\ntarget     prot opt source      destination")
        if "-S" in p:
            return "-P INPUT ACCEPT\n-P FORWARD ACCEPT\n-P OUTPUT ACCEPT"
        if "-A" in p or "-I" in p:
            m = re.search(r"--dport\s+(\d+)", line)
            if m and "ACCEPT" in line:
                fw.add_port(f"{m.group(1)}/tcp", permanent=True)
                fw.add_port(f"{m.group(1)}/tcp", permanent=False)
            return ""
        if "-D" in p or "-F" in p:
            return ""
        return ""

    def _cmd_ufw(self, p: list[str]) -> str:
        fw = self.state.firewall
        if len(p) < 2:
            return "ERROR: not enough args"
        sub = p[1]
        if sub == "status":
            z = fw.runtime.get(fw.default_zone, {})
            rows = []
            for ptok in z.get("ports", []):
                port = ptok.split("/")[0]
                rows.append(f"{port + '/tcp':<26}ALLOW       Anywhere")
            body = "\n".join(rows) if rows else ""
            return ("Status: active\n\n"
                    "To                         Action      From\n"
                    "--                         ------      ----\n" + body)
        if sub == "allow":
            target = p[2] if len(p) > 2 else ""
            port = re.sub(r"[^0-9]", "", target.split("/")[0])
            if port:
                fw.add_port(f"{port}/tcp", permanent=True)
                fw.add_port(f"{port}/tcp", permanent=False)
                return f"Rule added"
            return "Rule added"
        if sub in ("enable", "disable", "reload", "deny", "delete"):
            return f"Firewall {sub}d"
        return "ufw: ok"

    def _cmd_watch(self, p: list[str]) -> str:
        # Non-interactive: run the wrapped command once and show a header, as a
        # single-shot `watch -n1 CMD` snapshot would.
        args = list(p[1:])
        while args and args[0].startswith("-"):
            if args[0] in ("-n", "--interval") and len(args) > 1:
                args = args[2:]
            else:
                args = args[1:]
        if not args:
            return "Usage: watch [options] command"
        cmd = " ".join(args)
        header = f"Every 2.0s: {cmd}"
        body = self.run(cmd)
        return f"{header}\n\n{body}" if body else header

    def _cmd_reboot(self, p: list[str]) -> str:
        # Restart the uptime clock. The unified engine resets boot_time again in
        # _reboot_from_shell after running the boot sequence; doing it here too
        # keeps the bare-shell (no-engine) path correct and is idempotent.
        self.state.boot_time = time.time()
        return "__REBOOT__"

    def _cmd_shutdown(self, p: list[str]) -> str:
        return "System shutdown simulated."

    def _cmd_exit(self, p: list[str]) -> str:
        return "logout"
