#!/usr/bin/env python3
"""Upgrade flagship academy labs from marker checks to REAL simulation break/fix.

Many academy labs only validate `grep FIXED-OK <file>` — a learner can "pass" by
editing a sentinel file instead of doing real work. This script upgrades a
curated set of flagship labs per major technology so the lab:

  • boots into a genuinely broken OS state (a failed service, a missing user, a
    closed firewall port, a stopped container stack), and
  • is validated by reading that real state back (systemctl is-active, getent,
    firewall-cmd, docker ps) — NOT a marker.

It is the single source of truth for the flagship set. It:
  1. writes a real `check.sh` into each selected scenario directory,
  2. rewrites the scenario.yaml copy (description / objectives / initial_state /
     progressive hints) to describe the real task, and
  3. emits backend/.../simulation/flagship_presets.py with the slug→preset map
     plus the slug→fix maps consumed by scripts/e2e_simulation_fix.py.

Re-run after adding cycles or topics. Then re-seed scenarios so the new
check.sh content reaches the database (Scenario.validation_script).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios"
PRESET_OUT = ROOT / "backend/apps/labs/provisioner/simulation/flagship_presets.py"

# ── Per-kind real validation + learner-facing copy ───────────────────────────
# check: the real check.sh body (validated against live OS state, never a marker)
KINDS: dict[str, dict] = {
    "users": {
        "check": "getent passwd appuser",
        "description": (
            "Hands-on user administration. An application is meant to run under a "
            "dedicated, non-login service account named `appuser`, but that account "
            "does not exist on this host yet — so the service cannot own its files "
            "or run with least privilege. Create the `appuser` account (with a home "
            "directory) and verify it resolves with `getent passwd appuser`."
        ),
        "initial_state": (
            "The application service account `appuser` is missing on this host. The "
            "service that depends on it cannot start until the account exists."
        ),
        "objectives": [
            "The dedicated 'appuser' service account exists on the host",
            "The account is created cleanly (with a home directory)",
            "getent passwd appuser returns the account",
        ],
        "hints": [
            "Inspect first: `getent passwd appuser` (will be empty) and `cat /etc/passwd` to see existing accounts.",
            "Decide whether the account needs a login shell and home directory. A service account usually wants a home dir but no interactive login.",
            "Create it: `sudo useradd -m appuser`, confirm with `getent passwd appuser`, then run Check Solution.",
        ],
    },
    "systemd": {
        "check": "systemctl is-active nginx",
        "description": (
            "Day-2 systemd service operations. The `nginx` unit on this host has "
            "entered a failed state, so the web service it provides is down. "
            "Investigate it the way you would in production — `systemctl status "
            "nginx` and `journalctl -u nginx` — then bring the unit back to an "
            "active (running) state. Verify with `systemctl is-active nginx`."
        ),
        "initial_state": (
            "The `nginx` service is installed but currently failed/stopped, so the "
            "site it serves is unavailable."
        ),
        "objectives": [
            "The nginx service is active (running) again",
            "The unit is healthy and (ideally) enabled to survive reboot",
            "systemctl is-active nginx reports 'active'",
        ],
        "hints": [
            "Pre-check the unit: `systemctl status nginx` and `journalctl -u nginx` to see why it is not running.",
            "Bring it up with the smallest safe action rather than reinstalling — a stopped/failed unit usually just needs to be started.",
            "Run `sudo systemctl start nginx` (add `sudo systemctl enable nginx` for persistence), confirm `systemctl is-active nginx`, then Check Solution.",
        ],
    },
    "syslog": {
        "check": "systemctl is-active rsyslog",
        "description": (
            "Logging-pipeline troubleshooting. The `rsyslog` service that journald "
            "forwards system logs to is not running, so centralised/persistent "
            "logging has stopped and you are flying blind during incidents. "
            "Investigate and restore the service. Verify with "
            "`systemctl is-active rsyslog`."
        ),
        "initial_state": (
            "The `rsyslog` logging service is stopped, so log forwarding and "
            "persistence have halted on this host."
        ),
        "objectives": [
            "The rsyslog service is active (running) again",
            "The logging pipeline is restored",
            "systemctl is-active rsyslog reports 'active'",
        ],
        "hints": [
            "Check the service: `systemctl status rsyslog` and look for recent log entries with `journalctl -u rsyslog`.",
            "The configuration is intact — the daemon just needs to be running and enabled.",
            "Run `sudo systemctl enable --now rsyslog`, confirm with `systemctl is-active rsyslog`, then Check Solution.",
        ],
    },
    "crond": {
        "check": "systemctl is-active crond",
        "description": (
            "Scheduled-jobs operations. The `crond` scheduler is not running, so no "
            "cron jobs (backups, rotations, batch tasks) will fire. Restore the "
            "scheduler so scheduled work resumes. Verify with "
            "`systemctl is-active crond`."
        ),
        "initial_state": (
            "The cron scheduler (`crond`) is stopped, so no scheduled jobs will "
            "run until it is started."
        ),
        "objectives": [
            "The crond scheduler service is active (running)",
            "Scheduled jobs can fire again",
            "systemctl is-active crond reports 'active'",
        ],
        "hints": [
            "Check the scheduler: `systemctl status crond` and `systemctl list-timers` for context.",
            "No crontab edits are required — the scheduler daemon itself is down.",
            "Run `sudo systemctl enable --now crond`, confirm with `systemctl is-active crond`, then Check Solution.",
        ],
    },
    "ansible": {
        "check": "ansible webservers -m ping",
        "description": (
            "Ansible control-node troubleshooting. The managed hosts in the "
            "`webservers` group are unreachable over SSH from the control node, so "
            "every play fails at the connection stage. Establish key-based SSH "
            "access to the inventory hosts so Ansible can reach them. Verify with "
            "`ansible webservers -m ping` (every host should return SUCCESS / pong)."
        ),
        "initial_state": (
            "The Ansible control node cannot authenticate to the managed hosts in "
            "the `webservers` group — `ansible webservers -m ping` fails with "
            "unreachable/permission-denied errors."
        ),
        "objectives": [
            "All hosts in the webservers group are reachable from the control node",
            "Key-based SSH authentication works without a password prompt",
            "ansible webservers -m ping returns SUCCESS for every host",
        ],
        "hints": [
            "Confirm the failure: `ansible webservers -m ping` and check `ansible-inventory --list` to see the target hosts.",
            "The inventory is correct — the problem is SSH authentication to the managed nodes.",
            "Distribute your key with `ssh-copy-id` to each managed host (e.g. `ssh-copy-id root@web1`), then re-run `ansible webservers -m ping` and Check Solution.",
        ],
    },
    "chrony": {
        "check": "systemctl is-active chronyd",
        "description": (
            "RHEL time-service operations. `chronyd` (the NTP client) is not "
            "running on this host, so the system clock will drift — which breaks "
            "TLS validation, log correlation, and Kerberos. Restore the time "
            "service to an active state and confirm synchronisation. Verify with "
            "`systemctl is-active chronyd`."
        ),
        "initial_state": (
            "Time synchronisation is broken: the `chronyd` service is stopped, so "
            "the clock is free-running and will drift out of tolerance."
        ),
        "objectives": [
            "The chronyd service is active (running)",
            "Time synchronisation is restored on the host",
            "systemctl is-active chronyd reports 'active'",
        ],
        "hints": [
            "Check the service and sync state: `systemctl status chronyd` and `chronyc tracking`.",
            "The configuration is fine — the daemon simply is not running and enabled.",
            "Run `sudo systemctl enable --now chronyd`, confirm with `systemctl is-active chronyd`, then Check Solution.",
        ],
    },
    "firewall": {
        # NOTE: the leading token must NOT be `firewall...` — the validation loop
        # skips lines beginning with "fi" (shell `fi`). `sudo` prefix is both
        # realistic and keeps the firewalld port check from being silently dropped.
        "check": "sudo firewall-cmd --list-ports",
        "description": (
            "Firewall administration with firewalld. Clients cannot reach the HTTP "
            "service because the active firewalld zone does not permit web traffic "
            "on port 80. Open HTTP persistently and reload firewalld so the rule "
            "survives, then confirm the zone allows it. Verify with "
            "`firewall-cmd --list-all`."
        ),
        "initial_state": (
            "Port 80/tcp (HTTP) is not allowed through firewalld in the active "
            "zone, so the web service is unreachable from clients."
        ),
        "objectives": [
            "HTTP (port 80/tcp) is permitted in the active firewalld zone",
            "The rule is persistent across a firewalld reload",
            "firewall-cmd shows the HTTP port/service open",
        ],
        "hints": [
            "Inspect the active zone: `firewall-cmd --list-all` to see which services/ports are currently allowed.",
            "Make the change persistent (`--permanent`) and remember runtime rules need a `--reload` to take effect.",
            "Run `sudo firewall-cmd --permanent --add-service=http` (or `--add-port=80/tcp`) then `sudo firewall-cmd --reload`; verify with `firewall-cmd --list-all`, then Check Solution.",
        ],
    },
    "docker-compose": {
        "check": "docker ps | grep -q Up",
        "description": (
            "Container operations with Docker Compose. The application's services "
            "are defined in the compose file, but the stack is not running, so "
            "there are no live containers serving traffic. Bring the stack up and "
            "confirm the containers are healthy. Verify with `docker ps`."
        ),
        "initial_state": (
            "The Docker Compose stack is defined but not running — `docker ps` "
            "shows no application containers Up."
        ),
        "objectives": [
            "The Docker Compose stack is running",
            "docker ps shows the application containers in the Up state",
            "The containerised service is reachable again",
        ],
        "hints": [
            "Check what is running: `docker ps` (likely empty) and review the compose file in the app directory.",
            "You do not need to rebuild images — the stack simply needs to be started in the background.",
            "Run `docker compose up -d` from the app directory, confirm with `docker ps`, then Check Solution.",
        ],
    },
}

# Per-technology topic → kind selection. Matched as a suffix on the slug so each
# cycle (e.g. ...-systemd-services and ...-systemd-services-2) is included.
TECH_TOPICS: dict[str, list[tuple[str, str]]] = {
    "linux": [
        ("users-groups", "users"),
        ("systemd-services", "systemd"),
        ("journald-logs", "syslog"),
        ("networking-firewalld", "firewall"),
        ("cron-timers", "crond"),
    ],
    "rhel-linux": [
        ("firewalld", "firewall"),
        ("chrony", "chrony"),
    ],
    "docker": [
        ("compose", "docker-compose"),
    ],
    "ansible": [
        ("inventory", "ansible"),
        ("playbooks", "ansible"),
    ],
}


def _kind_for(tech: str, slug: str) -> str | None:
    for topic, kind in TECH_TOPICS.get(tech, []):
        if re.search(rf"-{re.escape(topic)}(-\d+)?$", slug):
            return kind
    return None


def _write_check(folder: Path, kind: str) -> None:
    body = KINDS[kind]["check"]
    (folder / "check.sh").write_text(
        f"#!/usr/bin/env bash\n{body}\nexit 0\n", encoding="utf-8"
    )


def _update_yaml(path: Path, kind: str) -> None:
    spec = KINDS[kind]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["description"] = spec["description"]
    data["initial_state"] = spec["initial_state"]
    data["objectives"] = list(spec["objectives"])
    data["hints"] = [
        {"order": i + 1, "cost": cost, "content": content}
        for i, (cost, content) in enumerate(
            zip((10, 15, 20), spec["hints"])
        )
    ]
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def main() -> None:
    slug_kind: dict[str, str] = {}
    for tech in TECH_TOPICS:
        tech_dir = SCEN / tech
        if not tech_dir.is_dir():
            continue
        for folder in sorted(tech_dir.glob(f"academy-{tech}-*")):
            if not (folder / "scenario.yaml").is_file():
                continue
            slug = folder.name
            kind = _kind_for(tech, slug)
            if not kind:
                continue
            _write_check(folder, kind)
            _update_yaml(folder / "scenario.yaml", kind)
            slug_kind[slug] = kind

    _emit_presets(slug_kind)
    by_kind: dict[str, int] = {}
    for k in slug_kind.values():
        by_kind[k] = by_kind.get(k, 0) + 1
    print(f"flagship labs upgraded: {len(slug_kind)}")
    for k, n in sorted(by_kind.items()):
        print(f"  {k:14s} {n}")
    print(f"presets: {PRESET_OUT}")


_MODULE_HEADER = '''"""GENERATED by scripts/upgrade_flagship_labs.py — do not edit by hand.

Real-simulation presets for flagship academy labs. Each preset breaks a genuine
OS state (failed service, missing user, closed firewall port, stopped compose
stack). Validation reads that real state back via the scenario's check.sh, so a
fresh lab is fail-closed until the genuine fix is applied. The matching fix is
performed by scripts/e2e_simulation_fix.py using the *_FIX maps exported here.
"""
from __future__ import annotations

from .rhel_os import SimService


def _break_service(state, unit: str, desc: str) -> None:
    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled", description=desc,
        loaded="loaded", sub_state="failed", unit_file=f"[Unit]\\nDescription={desc}\\n",
    )


def _preset_users(state) -> None:
    # The dedicated service account must be created by the learner.
    state.users.pop("appuser", None)
    state.sync_passwd_files()


def _preset_systemd(state) -> None:
    _break_service(state, "nginx", "The nginx HTTP and reverse proxy server")


def _preset_chrony(state) -> None:
    _break_service(state, "chronyd", "NTP client/server (chrony)")


def _preset_syslog(state) -> None:
    _break_service(state, "rsyslog", "System Logging Service")


def _preset_crond(state) -> None:
    _break_service(state, "crond", "Command Scheduler (cron)")


def _preset_ansible(state) -> None:
    # No OS-level break: the managed hosts are unreachable until the learner
    # distributes SSH keys (engine._ssh_key_fixed stays False at boot). Nothing
    # to set on the state itself.
    return None


def _close_http(state) -> None:
    fw = state.firewall
    for scope in (fw.runtime, fw.permanent):
        zone = scope.get(fw.default_zone)
        if not zone:
            continue
        zone["services"] = [s for s in zone.get("services", []) if s != "http"]
        zone["ports"] = [p for p in zone.get("ports", []) if p != "80/tcp"]


def _preset_firewall(state) -> None:
    _close_http(state)


def _preset_docker_compose(state) -> None:
    # Daemon is up; the compose stack is simply not running yet.
    if "docker" not in state.services:
        state.services["docker"] = SimService(
            "docker", active="active", enabled="enabled",
            description="Docker Application Container Engine",
            loaded="loaded", sub_state="running",
        )


_BUILDERS = {
    "users": _preset_users,
    "systemd": _preset_systemd,
    "syslog": _preset_syslog,
    "crond": _preset_crond,
    "chrony": _preset_chrony,
    "firewall": _preset_firewall,
    "docker-compose": _preset_docker_compose,
    "ansible": _preset_ansible,
}

'''

_MODULE_FOOTER = '''
FLAGSHIP_PRESETS = {
    slug: (lambda state, _k=kind: _BUILDERS[_k](state))
    for slug, kind in FLAGSHIP_SLUG_KIND.items()
}

# Maps consumed by scripts/e2e_simulation_fix.py to apply the genuine fix.
_SERVICE_UNIT = {
    "systemd": "nginx",
    "chrony": "chronyd",
    "syslog": "rsyslog",
    "crond": "crond",
}
FLAGSHIP_SERVICE_FIX = {
    slug: _SERVICE_UNIT[kind]
    for slug, kind in FLAGSHIP_SLUG_KIND.items()
    if kind in _SERVICE_UNIT
}
FLAGSHIP_USER_FIX = {
    slug: "appuser" for slug, kind in FLAGSHIP_SLUG_KIND.items() if kind == "users"
}
FLAGSHIP_FIREWALL_SLUGS = {
    slug for slug, kind in FLAGSHIP_SLUG_KIND.items() if kind == "firewall"
}
FLAGSHIP_DOCKER_SLUGS = {
    slug for slug, kind in FLAGSHIP_SLUG_KIND.items() if kind == "docker-compose"
}
FLAGSHIP_ANSIBLE_SLUGS = {
    slug for slug, kind in FLAGSHIP_SLUG_KIND.items() if kind == "ansible"
}
FLAGSHIP_SLUGS = set(FLAGSHIP_SLUG_KIND)
'''


def _emit_presets(slug_kind: dict[str, str]) -> None:
    lines = [_MODULE_HEADER, "# slug -> preset kind (generated)", "FLAGSHIP_SLUG_KIND = {"]
    for slug in sorted(slug_kind):
        lines.append(f"    {slug!r}: {slug_kind[slug]!r},")
    lines.append("}")
    lines.append(_MODULE_FOOTER)
    PRESET_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
