"""In-memory Ansible AWX / Ansible Tower simulator for training labs."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

from .awx_v2_facades import apply_v2_action, ensure_v2

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"awx_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now() -> float:
    return time.time()


def _activity(state: dict, action: str, obj: str) -> None:
    """Record a user-facing Activity Stream entry (newest first)."""
    user = (state.get("session") or {}).get("user") or "admin"
    activity = state.setdefault("activity", [])
    aid = f"a{len(activity) + 1}-{int(time.time() * 1000) % 100000}"
    activity.insert(0, {"id": aid, "time": _now_iso(), "user": user, "action": action, "object": obj})


# ---------------------------------------------------------------------------
# Job lifecycle model
#
# A launched/relaunched job is a real object with a wall-clock timeline. Its
# status advances pending -> waiting -> running -> successful/failed based on
# how many seconds have elapsed since it was launched (started_ts). Because the
# transition is derived purely from the launch timestamp, a fast poller that
# hits get_state several times per second never "skips" a state — every poll
# independently computes the correct status for the current instant, matching
# the time-based advance the monitoring / nmap engines use.
#
# Each job carries a full ansible stdout plan (play/task/recap lines). The
# number of lines revealed grows with elapsed time so the terminal log appears
# to stream as the job runs.
# ---------------------------------------------------------------------------

# Timeline thresholds (seconds since launch) for a live job.
_JOB_WAITING_AT = 1.5
_JOB_RUNNING_AT = 3.0
_JOB_FINISH_AT = 8.0


def _ansi(color: str, text: str) -> str:
    codes = {"green": "\x1b[32m", "red": "\x1b[31m", "amber": "\x1b[33m", "cyan": "\x1b[36m"}
    return f"{codes.get(color, '')}{text}\x1b[0m"


# ---------------------------------------------------------------------------
# Playbook content model
#
# A job template owns real playbook TEXT (state["playbooks"][<filename>]), not
# just a filename. Whether a launched job succeeds is DERIVED by evaluating
# that text against the live inventory — it is never a preset boolean. The
# defects below are the ones a learner can see in the editor and fix with the
# edit_playbook action; each maps to the ansible error a real run would emit.
# ---------------------------------------------------------------------------

# Modules the simulated execution environment ships. Anything else is a
# "couldn't resolve module/action" failure, which is the single most common
# real-world cause of a red PLAY RECAP in a training environment.
_KNOWN_MODULES = {
    "ansible.builtin.package", "ansible.builtin.apt", "ansible.builtin.yum",
    "ansible.builtin.dnf", "ansible.builtin.service", "ansible.builtin.systemd",
    "ansible.builtin.copy", "ansible.builtin.template", "ansible.builtin.file",
    "ansible.builtin.command", "ansible.builtin.shell", "ansible.builtin.assert",
    "ansible.builtin.debug", "ansible.builtin.setup", "ansible.builtin.stat",
    "ansible.builtin.lineinfile", "ansible.builtin.reboot", "ansible.builtin.wait_for",
    # Short (unqualified) names resolve to the builtin collection.
    "package", "apt", "yum", "dnf", "service", "systemd", "copy", "template",
    "file", "command", "shell", "assert", "debug", "setup", "stat",
    "lineinfile", "reboot", "wait_for",
}


def _parse_playbook(text: str) -> dict:
    """Minimal structural parse of a playbook's YAML text.

    Deliberately not a real YAML parser: the simulator only needs the handful
    of facts that decide whether a run goes green — the target host pattern,
    the module each task calls, and the variables the text interpolates. A
    hand-rolled scan keeps this dependency-free and tolerant of the partially
    broken text a learner is asked to repair.
    """
    hosts = ""
    modules: list[str] = []
    variables: set[str] = set()
    defined: set[str] = set()
    roles: list[str] = []
    tasks: list[dict] = []
    in_vars = False
    in_roles = False
    roles_indent = 0
    vars_indent = 0
    has_tasks = False
    pending_name = ""
    pending_role = False

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip().lstrip("- ").strip()

        # {{ var }} references anywhere in the file.
        rest = line
        while "{{" in rest and "}}" in rest:
            start = rest.index("{{") + 2
            end = rest.index("}}", start)
            # Strip filters/defaults: `pkg | default('x')` references `pkg`.
            token = rest[start:end].split("|")[0].strip()
            token = token.split(".")[0].split("[")[0].strip()
            if token and token.replace("_", "").isalnum() and not token.isdigit():
                variables.add(token)
            rest = rest[end + 2:]

        if body.startswith("hosts:"):
            hosts = body.split(":", 1)[1].strip()
            in_vars = in_roles = False
            continue
        if body.startswith("tasks:"):
            has_tasks = True
            in_vars = in_roles = False
            continue
        if body.startswith("vars:"):
            in_vars = True
            in_roles = False
            vars_indent = indent
            continue
        if body.startswith("roles:"):
            in_roles = True
            in_vars = False
            roles_indent = indent
            continue
        if in_vars:
            if indent <= vars_indent:
                in_vars = False
            elif ":" in body:
                defined.add(body.split(":", 1)[0].strip())
                continue
        if in_roles:
            if indent <= roles_indent:
                in_roles = False
            else:
                # `- role: geerlingguy.nginx` and bare `- geerlingguy.nginx` are
                # both valid entries in a play's roles: list.
                entry = body.split(":", 1)[1].strip() if body.startswith("role:") else body
                entry = entry.strip("'\"")
                if entry:
                    roles.append(entry)
                continue

        # A task's module is the first mapping key that is not a task keyword.
        if ":" in body:
            key = body.split(":", 1)[0].strip()
            if key == "name":
                value = body.split(":", 1)[1].strip().strip("'\"")
                if pending_role:
                    # The `name:` nested under include_role/import_role names a
                    # ROLE, not a task — it must resolve against galaxy.
                    if value:
                        roles.append(value)
                    pending_role = False
                else:
                    # Remember a task's name so the run log and the convergence
                    # ledger can refer to the task the learner actually wrote.
                    pending_name = value
                continue
            if key in ("include_role", "import_role"):
                in_roles = False
                pending_role = True
                continue
            if key in ("become", "when", "register", "loop", "with_items",
                       "notify", "tags", "vars", "hosts", "tasks", "handlers",
                       "gather_facts", "ignore_errors", "changed_when", "failed_when",
                       "delegate_to", "run_once", "state", "enabled", "msg", "that",
                       "src", "dest", "mode", "owner", "group", "line", "path"):
                continue
            if key and (key in _KNOWN_MODULES or "." in key or key.islower()):
                modules.append(key)
                tasks.append({"name": pending_name or key, "module": key})
                pending_name = ""

    return {
        "hosts": hosts,
        "modules": modules,
        "variables": variables,
        "defined_vars": defined,
        "roles": roles,
        "tasks": tasks,
        "has_tasks": has_tasks,
    }


def _inventory_targets(state: dict, pattern: str) -> list[dict] | None:
    """Hosts an ansible host pattern matches, or None if the pattern is unknown.

    Returning [] and None are different outcomes: [] means a real group that is
    currently empty/disabled, None means the pattern names nothing in AWX at
    all. Only the latter is a playbook defect — an inventory that simply has no
    host rows seeded is a fixture gap, not something the learner authored.
    """
    pattern = (pattern or "").strip().strip("'\"")
    hosts = state.get("hosts") or []
    if not pattern:
        return None
    if pattern in ("all", "*"):
        return list(hosts)
    matched = [h for h in hosts if (h.get("inventory") or "") == pattern]
    if matched:
        return matched
    by_name = [h for h in hosts if (h.get("name") or "") == pattern]
    if by_name:
        return by_name
    # A declared inventory with no host rows is still a valid target.
    if any((i.get("name") or "") == pattern for i in state.get("inventories") or []):
        return []
    return None


# ---------------------------------------------------------------------------
# Galaxy artifact model: roles/collections + requirements.yml pinning
#
# A project owns a real requirements.yml TEXT. Syncing the project runs the
# equivalent of `ansible-galaxy install -r requirements.yml`, which populates
# state["installed_roles"] / state["installed_collections"] with the exact
# name+version each entry pins. A playbook that uses a role is resolved against
# what is actually INSTALLED — not against the requirements text — so:
#   * a role referenced but absent from requirements.yml fails to resolve,
#   * a requirements.yml that was edited but never re-synced still fails,
#   * an unpinned entry ("version:" missing) fails the pin audit.
# That makes the artifact load-bearing instead of decorative.
# ---------------------------------------------------------------------------


def _parse_requirements(text: str) -> dict:
    """Parse a requirements.yml into its roles/collections entries.

    Recognises the two-section galaxy format (`roles:` / `collections:`) and the
    legacy bare list of roles. Each entry keeps whether it carried an explicit
    `version:` so the pin audit can flag floating dependencies.
    """
    roles: list[dict] = []
    collections: list[dict] = []
    section = "roles"  # a bare list (no header) is the legacy roles format
    current: dict | None = None

    def _flush() -> None:
        nonlocal current
        if current and current.get("name"):
            (collections if current.pop("_section") == "collections" else roles).append(current)
        current = None

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#") or line.strip() == "---":
            continue
        stripped = line.strip()
        if stripped in ("roles:", "collections:"):
            _flush()
            section = stripped[:-1]
            continue
        if stripped.startswith("- "):
            _flush()
            current = {"_section": section, "name": "", "version": ""}
            body = stripped[2:].strip()
            if body.startswith("name:"):
                current["name"] = body.split(":", 1)[1].strip().strip("'\"")
            elif ":" not in body:
                # `- geerlingguy.nginx` shorthand: named, but unpinned.
                current["name"] = body.strip("'\"")
            elif body.startswith("src:"):
                current["name"] = body.split(":", 1)[1].strip().strip("'\"")
            continue
        if current is not None and ":" in stripped:
            key, value = stripped.split(":", 1)
            key, value = key.strip(), value.strip().strip("'\"")
            if key in ("name", "src") and not current["name"]:
                current["name"] = value
            elif key == "version":
                current["version"] = value
    _flush()
    return {"roles": roles, "collections": collections}


def _project_for_playbook(state: dict, playbook: str) -> dict | None:
    """The project whose SCM checkout provides `playbook`.

    Templates do not carry a project id in this model, so fall back to the sole
    project when there is exactly one — the common lab shape.
    """
    projects = state.get("projects") or []
    for p in projects:
        if playbook in (p.get("playbooks") or []):
            return p
    return projects[0] if len(projects) == 1 else next(
        (p for p in projects if p.get("requirements")), None)


def _install_galaxy_requirements(state: dict, project: dict) -> dict:
    """Run `ansible-galaxy install -r requirements.yml` for a project.

    Returns a summary of what was installed and which entries float (carry no
    `version:`). Only pinned-or-not is recorded here; refusing to install an
    unpinned entry is the caller's policy decision.
    """
    parsed = _parse_requirements(project.get("requirements") or "")
    installed_roles = state.setdefault("installed_roles", {})
    installed_cols = state.setdefault("installed_collections", {})
    unpinned: list[str] = []
    for entry in parsed["roles"]:
        installed_roles[entry["name"]] = entry.get("version") or "unpinned"
        if not entry.get("version"):
            unpinned.append(entry["name"])
    for entry in parsed["collections"]:
        installed_cols[entry["name"]] = entry.get("version") or "unpinned"
        if not entry.get("version"):
            unpinned.append(entry["name"])
    return {
        "roles": [e["name"] for e in parsed["roles"]],
        "collections": [e["name"] for e in parsed["collections"]],
        "unpinned": unpinned,
    }


def _resolve_role(state: dict, role: str) -> str:
    """Return the ansible error for an unresolvable role, or "" if installed.

    A role is usable only if `ansible-galaxy install` actually put it on the
    control node (project synced), which is what makes requirements.yml
    load-bearing: editing the file is not enough, the project must be re-synced.
    """
    installed = state.get("installed_roles") or {}
    name = (role or "").strip().strip("'\"")
    if not name or name in installed:
        return ""
    # A role provided by an installed collection (namespace.collection.role).
    parts = name.split(".")
    if len(parts) >= 3:
        if ".".join(parts[:2]) in (state.get("installed_collections") or {}):
            return ""
    return (f"ERROR! the role '{name}' was not found in "
            "~/.ansible/roles:/usr/share/ansible/roles:/etc/ansible/roles. "
            "Add it to requirements.yml and re-sync the project.")


def _clear_resolved_role_blocker(state: dict, broken: dict) -> None:
    """Drop the role blocker only once the role is genuinely installed.

    Fail-closed: a sync of the WRONG project, or a requirements.yml edit that
    was never synced, leaves the role uninstalled and the blocker in place.
    """
    role = broken.get("role_not_installed")
    if role and not _resolve_role(state, str(role)):
        broken.pop("role_not_installed", None)


def _evaluate_playbook(state: dict, template_name: str, playbook: str) -> str:
    """Return the reason a run of `playbook` would fail, or "" if it will pass.

    This is the whole point of the content model: outcome comes from the text
    plus the live inventory, so a job cannot go green until the learner has
    actually corrected the playbook AND the hosts it targets are usable.
    """
    text = (state.get("playbooks") or {}).get(playbook)
    if text is None:
        # No content recorded (ad-hoc template created mid-lab): nothing to be
        # wrong with, so it runs clean. Fail-open only where there is no
        # authored defect to detect.
        return ""

    parsed = _parse_playbook(text)

    if not parsed["hosts"]:
        return "ERROR! the field 'hosts' is required but was not set"
    # A play made only of roles: is valid ansible even with no tasks: block.
    if not parsed["has_tasks"] and not parsed["roles"]:
        return f"ERROR! no tasks/entries found in {playbook}"

    for module in parsed["modules"]:
        if module not in _KNOWN_MODULES:
            return (f"ERROR! couldn't resolve module/action '{module}'. "
                    "This often indicates a misspelling, missing collection, "
                    "or incorrect module path.")

    for role in parsed["roles"]:
        unresolved = _resolve_role(state, role)
        if unresolved:
            return unresolved

    undefined = sorted(parsed["variables"] - parsed["defined_vars"] - _host_facts(state))
    if undefined:
        return (f"The task includes an option with an undefined variable. "
                f"The error was: '{undefined[0]}' is undefined")

    targets = _inventory_targets(state, parsed["hosts"])
    if targets is None:
        return (f"ERROR! Could not match supplied host pattern, "
                f"ignoring: {parsed['hosts']}")
    if targets and not any(h.get("enabled", True) for h in targets):
        return (f"ERROR! Could not match supplied host pattern, "
                f"ignoring: {parsed['hosts']} (all hosts disabled)")

    return ""


def _host_facts(state: dict) -> set[str]:
    """Variables ansible always provides, so referencing them is never undefined."""
    return {
        "inventory_hostname", "ansible_hostname", "ansible_fqdn", "ansible_host",
        "ansible_distribution", "ansible_os_family", "ansible_facts", "item",
        "groups", "hostvars", "playbook_dir", "ansible_user",
    }


# ---------------------------------------------------------------------------
# Convergence ledger: check mode, real changed-counts, and idempotency
#
# state["converged"] maps host -> {desired-state key: True} and is the ONLY
# source of a run's changed-count. A task is "changed" on a host when the host
# has not yet recorded that task's key; applying records it. Consequences that
# fall out for free, rather than being asserted by decorative text:
#   * run 1 (apply)  -> changed = number of state-changing tasks
#   * run 2 (apply)  -> changed = 0, because every key is already recorded
#   * check mode     -> reports the same diff but records NOTHING, so a check
#                       run never converges the fleet and is repeatable
# Editing the playbook mints new keys, so a genuinely different desired state
# correctly shows as changed again on the next run.
# ---------------------------------------------------------------------------

# Modules that only read/assert. They are always "ok", never "changed", so they
# do not participate in the convergence ledger.
_READ_ONLY_MODULES = {
    "ansible.builtin.assert", "ansible.builtin.debug", "ansible.builtin.setup",
    "ansible.builtin.stat", "ansible.builtin.wait_for", "ansible.builtin.command",
    "assert", "debug", "setup", "stat", "wait_for", "command",
}


def _task_key(playbook: str, task: dict) -> str:
    """Stable identity for a task's desired end state.

    Includes the task's name AND module so that editing either (a genuinely
    different intent) mints a new key and legitimately shows as changed again.
    """
    return f"{playbook}::{task.get('name', '')}::{task.get('module', '')}"


def _changing_tasks(playbook: str, parsed: dict) -> list[dict]:
    """The units of work in a play that can converge state (i.e. report changed).

    Applied roles count alongside inline tasks: a roles-only play does real work
    on the first run, so it must not report changed=0 and look idempotent before
    it has ever converged anything.
    """
    units = [t for t in parsed.get("tasks") or []
             if t.get("module") not in _READ_ONLY_MODULES]
    units += [{"name": f"{role} : converge", "module": "role"}
              for role in parsed.get("roles") or []]
    return units


def _plan_run(state: dict, playbook: str, targets: list[dict],
              *, check_mode: bool) -> dict:
    """Compute per-host changed/ok counts for a run, applying unless check_mode.

    This is what makes idempotency PROVABLE: the counts come from diffing the
    playbook's desired state against the ledger, and apply-mode writes the
    ledger back so an immediate second run legitimately reports changed=0.
    """
    text = (state.get("playbooks") or {}).get(playbook)
    parsed = _parse_playbook(text or "")
    tasks = _changing_tasks(playbook, parsed)
    read_only = len([t for t in parsed.get("tasks") or []
                     if t.get("module") in _READ_ONLY_MODULES])
    converged = state.setdefault("converged", {})

    per_host: list[dict] = []
    for host in targets:
        hostname = host.get("name") or "localhost"
        recorded = converged.setdefault(hostname, {}) if not check_mode else dict(
            converged.get(hostname) or {})
        pending = [t for t in tasks if _task_key(playbook, t) not in recorded]
        if not check_mode:
            for t in pending:
                recorded[_task_key(playbook, t)] = True
        per_host.append({
            "host": hostname,
            # +1 for Gathering Facts, which is always ok.
            "ok": 1 + read_only + len(tasks),
            "changed": len(pending),
            "pending": [t.get("name") or t.get("module") for t in pending],
        })
    return {
        "check_mode": check_mode,
        "hosts": per_host,
        "changed_total": sum(h["changed"] for h in per_host),
        "idempotent": all(h["changed"] == 0 for h in per_host) if per_host else False,
    }


def _build_diff_stdout(name: str, playbook: str, plan: dict) -> list[str]:
    """`--check --diff` style output: what WOULD change, changing nothing."""
    lines = [
        _ansi("cyan", f"PLAY [{name}] " + "*" * max(4, 52 - len(name))),
        "",
        _ansi("cyan", "TASK [Gathering Facts] " + "*" * 40),
    ]
    for entry in plan["hosts"]:
        lines.append(_ansi("green", f"ok: [{entry['host']}]"))
    lines.append("")
    for entry in plan["hosts"]:
        for task in entry["pending"]:
            lines += [
                _ansi("cyan", f"TASK [{task}] " + "*" * max(4, 48 - len(task))),
                _ansi("amber", f"--- before: {entry['host']} (current state)"),
                _ansi("green", f"+++ after:  {entry['host']} (desired state)"),
                _ansi("amber", f"changed: [{entry['host']}]"),
                "",
            ]
    recap_color = "green" if plan["idempotent"] else "amber"
    lines.append(_ansi(recap_color, "PLAY RECAP " + "*" * 58))
    for entry in plan["hosts"]:
        ok_txt = _ansi("green", "ok={}".format(entry["ok"]))
        ch_txt = _ansi("amber", "changed={}".format(entry["changed"]))
        lines.append(f"{entry['host']} : {ok_txt} {ch_txt} unreachable=0 failed=0")
    lines.append(_ansi("cyan", "check mode: no changes were actually made"))
    return lines


def _is_gpu_template(name: str, playbook: str = "") -> bool:
    blob = f"{name} {playbook}".lower()
    return any(
        k in blob
        for k in (
            "gpu", "nvidia", "dcgm", "driver", "repave", "persistenc",
            "h100", "h200", "b300", "rocm",
        )
    )


def _apply_plan_recap(lines: list[str], plan: dict | None) -> list[str]:
    """Replace a narrative's hardcoded PLAY RECAP with the ledger-derived one.

    The narrative task list stays (it is what makes the log readable), but the
    counts a learner and the grader read come from _plan_run, so a converged
    re-run genuinely reports changed=0 instead of reprinting a decorative
    changed=2.
    """
    if not plan or not plan.get("hosts"):
        return lines
    cut = next((i for i, ln in enumerate(lines) if "PLAY RECAP" in ln), None)
    if cut is None:
        return lines
    recap = [_ansi("green", "PLAY RECAP " + "*" * 58)]
    for entry in plan["hosts"]:
        ok_txt = _ansi("green", "ok={}".format(entry["ok"]))
        ch_txt = _ansi("amber", "changed={}".format(entry["changed"]))
        recap.append(f"{entry['host']} : {ok_txt} {ch_txt} unreachable=0 failed=0")
    if plan.get("idempotent"):
        recap.append(_ansi("green", "idempotent: no changes on this run"))
    return lines[:cut] + recap


def _build_job_stdout(name: str, playbook: str, host: str, will_fail: bool,
                      reason: str = "", plan: dict | None = None) -> list[str]:
    """A realistic ansible-playbook run log for a job template launch.

    Returned as an ordered list; get_state reveals a growing prefix as the job
    advances so the UI streams the output line by line. `reason` is the message
    _evaluate_playbook derived from the playbook text, so the fatal line names
    the actual defect instead of a generic "task failed". `plan` is the
    convergence diff from _plan_run; when present its counts replace the
    narrative's placeholder recap.
    """
    if _is_gpu_template(name, playbook):
        lines = _build_gpu_job_stdout(name, playbook, host, will_fail, reason)
        return _apply_plan_recap(lines, plan) if not will_fail else lines

    lines = [
        _ansi("cyan", f"PLAY [{name}] " + "*" * max(4, 52 - len(name))),
        "",
        _ansi("cyan", "TASK [Gathering Facts] " + "*" * 40),
        _ansi("green", f"ok: [{host}]"),
        "",
        _ansi("cyan", "TASK [Apply base configuration] " + "*" * 31),
        _ansi("amber", f"changed: [{host}]"),
        "",
        _ansi("cyan", f"TASK [Run {playbook}] " + "*" * max(4, 40 - len(playbook))),
    ]
    if will_fail:
        msg = reason or "task failed"
        lines += [
            _ansi("red", f"fatal: [{host}]: FAILED! => {{\"changed\": false, \"msg\": \"{msg}\"}}"),
            "",
            _ansi("red", "PLAY RECAP " + "*" * 58),
            f"{host} : {_ansi('green', 'ok=2')} {_ansi('amber', 'changed=1')} unreachable=0 {_ansi('red', 'failed=1')}",
        ]
    else:
        lines += [
            _ansi("amber", f"changed: [{host}]"),
            "",
            _ansi("cyan", "TASK [Verify service is active] " + "*" * 31),
            _ansi("green", f"ok: [{host}]"),
            "",
            _ansi("green", "PLAY RECAP " + "*" * 58),
            f"{host} : {_ansi('green', 'ok=4')} {_ansi('amber', 'changed=2')} unreachable=0 failed=0",
        ]
        return _apply_plan_recap(lines, plan)
    return lines


def _build_gpu_job_stdout(name: str, playbook: str, host: str, will_fail: bool,
                          reason: str = "") -> list[str]:
    """Stdout narrative for AI Infra GPU driver / DCGM / repave job templates."""
    low = f"{name} {playbook}".lower()
    if "dcgm" in low:
        tasks = [
            ("Install dcgm + datacenter-gpu-manager", "changed"),
            ("Deploy dcgm-exporter (port 9400)", "changed"),
            ("Assert DCGM_FI_DEV_GPU_UTIL scrapeable", "ok"),
        ]
        ok, changed = 5, 2
    elif "repave" in low or "image" in low:
        tasks = [
            ("Drain workloads / stop nvidia-persistenced", "changed"),
            ("Trigger MAAS deploy custom/h100-jammy", "changed"),
            ("Wait for cloud-init + nvidia-smi", "ok"),
        ]
        ok, changed = 5, 2
    elif "persistenc" in low:
        tasks = [
            ("Enable nvidia-persistenced", "changed"),
            ("Assert nvidia-smi -pm 1", "ok"),
        ]
        ok, changed = 4, 1
    else:
        tasks = [
            ("Install nvidia-driver-565 (H100)", "changed"),
            ("Enable nvidia-persistenced", "changed"),
            ("Assert nvidia-smi lists GPUs", "ok"),
        ]
        ok, changed = 6, 3

    lines = [
        _ansi("cyan", f"PLAY [{name}] " + "*" * max(4, 52 - len(name))),
        "",
        _ansi("cyan", "TASK [Gathering Facts] " + "*" * 40),
        _ansi("green", f"ok: [{host}]"),
        "",
    ]
    for title, result in tasks:
        lines.append(_ansi("cyan", f"TASK [{title}] " + "*" * max(4, 48 - len(title))))
        if will_fail and result == "changed":
            msg = reason or "driver install failed"
            lines += [
                _ansi("red", f"fatal: [{host}]: FAILED! => {{\"msg\": \"{msg}\"}}"),
                "",
            ]
            break
        color = "amber" if result == "changed" else "green"
        lines += [_ansi(color, f"{result}: [{host}]"), ""]

    if will_fail:
        lines += [
            _ansi("red", "PLAY RECAP " + "*" * 58),
            f"{host} : {_ansi('green', 'ok=2')} {_ansi('amber', 'changed=1')} unreachable=0 {_ansi('red', 'failed=1')}",
        ]
    else:
        # Fleet-shaped recap so learners see maas-gpu inventory, not a lone web host.
        peers = [host]
        if host.startswith("gpu-node"):
            peers = ["gpu-node-01", "gpu-node-02", "gpu-node-03"]
        lines.append(_ansi("green", "PLAY RECAP " + "*" * 58))
        for peer in peers:
            lines.append(
                f"{peer} : {_ansi('green', f'ok={ok}')} {_ansi('amber', f'changed={changed}')} "
                f"unreachable=0 failed=0"
            )
    return lines


def _job_host_for(state: dict, inventory: str) -> str:
    """Pick a representative host name for a job's play output."""
    for h in state.get("hosts", []):
        if h.get("inventory") == inventory and h.get("enabled", True):
            return h.get("name") or "localhost"
    for h in state.get("hosts", []):
        if h.get("name"):
            return h["name"]
    return "localhost"


def _run_targets(state: dict, playbook: str, inventory: str) -> list[dict]:
    """Hosts a run converges: the playbook's own host pattern, else the JT's."""
    text = (state.get("playbooks") or {}).get(playbook)
    pattern = _parse_playbook(text or "").get("hosts") if text else ""
    targets = _inventory_targets(state, pattern or inventory)
    if not targets:
        targets = _inventory_targets(state, inventory) or []
    return [h for h in targets if h.get("enabled", True)]


def _make_job(state: dict, name: str, *, playbook: str = "site.yml",
              inventory: str = "Production",
              started_ts: float | None = None,
              check_mode: bool = False) -> dict:
    """Create a launched job object with a live wall-clock timeline.

    The end state is DERIVED from the playbook's text (see _evaluate_playbook),
    never passed in by the caller — a job goes red exactly when the playbook it
    runs is still broken, and the fatal line quotes the derived reason.

    A successful APPLY run also converges the ledger (see _plan_run), which is
    what makes the next identical run report changed=0. A check-mode run
    computes the same diff but converges nothing.
    """
    new_id = max((int(j.get("id", 0)) for j in state.get("jobs", [])), default=500) + 1
    host = _job_host_for(state, inventory)
    reason = _evaluate_playbook(state, name, playbook)
    will_fail = bool(reason)
    finish = "failed" if will_fail else "successful"

    plan = None
    if not will_fail:
        # Only a run that will actually converge may write the ledger — a failed
        # play must leave the fleet exactly as it found it.
        targets = _run_targets(state, playbook, inventory)
        plan = _plan_run(state, playbook, targets, check_mode=check_mode)

    stdout_plan = (_build_diff_stdout(name, playbook, plan) if (plan and check_mode)
                   else _build_job_stdout(name, playbook, host, will_fail, reason, plan))
    return {
        "id": new_id,
        "name": name,
        "playbook": playbook,
        "inventory": inventory,
        "status": "pending",
        "started": _now_iso(),
        "started_ts": started_ts if started_ts is not None else _now(),
        "finish_status": finish,
        "failure_reason": reason,
        "check_mode": check_mode,
        "changed_count": (plan or {}).get("changed_total", 0),
        "idempotent": bool((plan or {}).get("idempotent")),
        "stdout_plan": stdout_plan,
        "stdout": [_ansi("cyan", "Identifying playbook process...")],
    }


def _advance_job(job: dict) -> bool:
    """Advance a single job's status + streamed stdout based on wall-clock.

    Returns True if the job's status changed this call. Jobs already in a
    terminal state (or lacking a timeline) are left untouched.
    """
    status = job.get("status")
    if status in ("successful", "failed", "canceled", "error"):
        return False
    started = job.get("started_ts")
    if started is None:
        return False

    plan = job.get("stdout_plan") or []
    finish = job.get("finish_status") or "successful"
    elapsed = max(0.0, _now() - float(started))

    if elapsed >= _JOB_FINISH_AT:
        new_status = finish
        reveal = len(plan)
    elif elapsed >= _JOB_RUNNING_AT:
        new_status = "running"
        # Reveal all but the final recap block while running.
        span = _JOB_FINISH_AT - _JOB_RUNNING_AT
        frac = (elapsed - _JOB_RUNNING_AT) / span if span else 1.0
        body = max(1, len(plan) - 4)
        reveal = min(body, 1 + int(frac * body))
    elif elapsed >= _JOB_WAITING_AT:
        new_status = "waiting"
        reveal = 0
    else:
        new_status = "pending"
        reveal = 0

    changed = new_status != status
    job["status"] = new_status

    header = {
        "pending": [_ansi("cyan", "Identifying playbook process...")],
        "waiting": [_ansi("cyan", "Identifying playbook process..."),
                    _ansi("cyan", "Waiting for execution node capacity...")],
        "running": [_ansi("cyan", "Running ansible-playbook on execution node...")],
        "successful": [_ansi("cyan", "Running ansible-playbook on execution node...")],
        "failed": [_ansi("cyan", "Running ansible-playbook on execution node...")],
    }.get(new_status, [])

    job["stdout"] = header + (plan[:reveal] if reveal else [])
    return changed


def _advance_jobs(state: dict) -> bool:
    """Advance every live job. Returns True if any status changed."""
    changed = False
    for job in state.get("jobs", []):
        if _advance_job(job):
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Cross-technology chain: ANSIBLE (AWX) → LINUX terminal.
#
# When a job template that "configures a service" runs to SUCCESS, we publish
# the intended end-state to the shared VMware/Linux bridge (record_ansible_result),
# keyed by the lab session id. The Linux terminal for the SAME session then
# reveals the service as installed + started when it inspects the unit
# (`systemctl is-active <svc>` → active, config file present) — see
# RHELOSState.reveal_ansible_services. Fail-closed: nothing is recorded until a
# service-configuring template actually launches successfully, so before the
# playbook runs the guest sees the service inactive/absent.
# ---------------------------------------------------------------------------

# Map a template name / playbook to the Linux service it configures + where its
# config lives. Keyed on tokens found in the template name or playbook filename;
# a scenario can also pass an explicit `service` in the launch payload.
_SERVICE_PLAYBOOKS: dict[str, dict] = {
    "nginx": {"service": "nginx", "package": "nginx", "config_path": "/etc/nginx/nginx.conf"},
    "httpd": {"service": "httpd", "package": "httpd", "config_path": "/etc/httpd/conf/httpd.conf"},
    "apache": {"service": "httpd", "package": "httpd", "config_path": "/etc/httpd/conf/httpd.conf"},
    "chrony": {"service": "chronyd", "package": "chrony", "config_path": "/etc/chrony.conf"},
    "postgres": {"service": "postgresql", "package": "postgresql-server", "config_path": "/var/lib/pgsql/data/postgresql.conf"},
    "postgresql": {"service": "postgresql", "package": "postgresql-server", "config_path": "/var/lib/pgsql/data/postgresql.conf"},
    "mariadb": {"service": "mariadb", "package": "mariadb-server", "config_path": "/etc/my.cnf"},
    "mysql": {"service": "mariadb", "package": "mariadb-server", "config_path": "/etc/my.cnf"},
    "redis": {"service": "redis", "package": "redis", "config_path": "/etc/redis/redis.conf"},
    "docker": {"service": "docker", "package": "docker-ce", "config_path": "/etc/docker/daemon.json"},
    "firewalld": {"service": "firewalld", "package": "firewalld", "config_path": "/etc/firewalld/firewalld.conf"},
}


def _service_config_for(template_name: str, playbook: str, payload: dict) -> dict | None:
    """Resolve which Linux service (if any) a launched template configures.

    An explicit `service` in the launch payload wins; otherwise match a known
    token in the template name or playbook filename. Returns a bridge-ready
    result dict, or None when the template does not configure a service (so we
    record nothing and the chain stays fail-closed)."""
    explicit = (payload.get("service") or "").strip()
    if explicit:
        spec = _SERVICE_PLAYBOOKS.get(explicit.lower(), {})
        return {
            "service": explicit,
            "installed": True,
            "started": bool(payload.get("started", True)),
            "enabled": bool(payload.get("enabled", True)),
            "config_path": payload.get("config_path") or spec.get("config_path") or "",
            "config_content": payload.get("config_content") or "",
            "package": payload.get("package") or spec.get("package") or explicit,
        }
    haystack = f"{template_name} {playbook}".lower()
    for token, spec in _SERVICE_PLAYBOOKS.items():
        if token in haystack:
            return {
                "service": spec["service"],
                "installed": True,
                "started": True,
                "enabled": True,
                "config_path": spec.get("config_path", ""),
                "config_content": "",
                "package": spec.get("package", spec["service"]),
            }
    return None


def _bridge_ansible_result(session_id: str, template_name: str, playbook: str,
                           payload: dict) -> None:
    """If a launched template configures a service, publish its intended end
    state to the Linux bridge. Best-effort: never let a bridge failure break the
    AWX action."""
    result = _service_config_for(template_name, playbook, payload)
    if not result:
        return
    try:
        from apps.labs.provisioner.simulation.vmware_bridge import record_ansible_result

        record_ansible_result(str(session_id), result)
    except Exception:
        pass


def _maybe_trigger_maas_deploy(session_id: str, job: dict, state: dict) -> None:
    """Cross-tech: launching a MAAS repave/deploy job template kicks off a real
    MAAS deploy on a Ready machine so the bare-metal Lab Environment advances
    in lockstep. Best-effort — a missing/uninitialized baremetal session must
    never fail the AWX job launch."""
    haystack = f"{job.get('name', '')} {job.get('playbook', '')}".lower()
    if not any(k in haystack for k in ("maas", "repave", "deploy")):
        return
    try:
        from apps.vmware_sim import baremetal_engine as be

        bm_state = (be.get_state(session_id, "") or {}).get("state") or {}
        machines = (bm_state.get("maas") or {}).get("machines") or []
        target = next((m for m in machines if m.get("status") == "Ready"), None)
        if not target:
            return
        boot_resources = (bm_state.get("maas") or {}).get("boot_resources") or []
        deploy_payload = {"machine_id": target.get("id")}
        if any(r.get("name") == "custom/h100-jammy" for r in boot_resources):
            deploy_payload["boot_resource"] = "custom/h100-jammy"
        res = be.apply_action(session_id, "maas_deploy", deploy_payload)
        if res.get("ok"):
            job["maas_deploy_triggered"] = True
            broken = state.get("broken")
            if isinstance(broken, dict):
                broken.pop("needs_maas_deploy", None)
    except Exception:
        pass


# --- Seeded playbook text -------------------------------------------------
# Authored so each defect is visible in the editor and repairable with
# edit_playbook. A healthy playbook must satisfy _evaluate_playbook: a host
# pattern that matches an enabled host, a tasks: block, only known modules,
# and no variable referenced without being defined.

_PATCH_PLAYBOOK = """---
- name: Patch Linux
  hosts: Production
  become: true
  tasks:
    - name: Apply all available security updates
      ansible.builtin.package:
        name: '*'
        state: latest
"""

_DEPLOY_PLAYBOOK = """---
- name: Deploy App
  hosts: Staging
  become: true
  tasks:
    - name: Ship the application bundle
      ansible.builtin.copy:
        src: app.tar.gz
        dest: /opt/app/app.tar.gz
    - name: Restart the application service
      ansible.builtin.service:
        name: app
        state: restarted
"""

# Defect: `servce` (missing 'i') does not resolve to a module, so every run
# fails with ansible's real resolve error until the learner fixes the spelling.
# Only seeded for slugs whose objective IS repairing the playbook — the
# launch-and-verify labs keep healthy text so their outcome is derived-green.
_BROKEN_DEPLOY_PLAYBOOK = _DEPLOY_PLAYBOOK.replace(
    "ansible.builtin.service:", "ansible.builtin.servce:"
)

_SSH_HARDENING_PLAYBOOK = """---
- name: Harden SSH
  hosts: Production
  become: true
  tasks:
    - name: Disable root login over SSH
      ansible.builtin.lineinfile:
        path: /etc/ssh/sshd_config
        line: PermitRootLogin no
    - name: Reload sshd
      ansible.builtin.service:
        name: sshd
        state: restarted
"""

_GPU_DRIVER_PLAYBOOK = """---
- name: GPU Driver Install (H100)
  hosts: maas-gpu-nodes
  become: true
  vars:
    nvidia_driver_version: 565
  tasks:
    - name: Install the pinned NVIDIA driver
      ansible.builtin.package:
        name: nvidia-driver-{{ nvidia_driver_version }}
        state: present
    - name: Enable persistence mode
      ansible.builtin.service:
        name: nvidia-persistenced
        state: started
"""

# Defect variant: the vars: block is gone, so `nvidia_driver_version` is
# interpolated while undefined. Seeded only for repair-objective slugs.
_BROKEN_GPU_DRIVER_PLAYBOOK = _GPU_DRIVER_PLAYBOOK.replace(
    "  vars:\n    nvidia_driver_version: 565\n", ""
)

_DCGM_PLAYBOOK = """---
- name: DCGM Exporter Deploy
  hosts: maas-gpu-nodes
  become: true
  tasks:
    - name: Install datacenter-gpu-manager
      ansible.builtin.package:
        name: datacenter-gpu-manager
        state: present
    - name: Start dcgm-exporter on :9400
      ansible.builtin.service:
        name: dcgm-exporter
        state: started
"""

_REPAVE_PLAYBOOK = """---
- name: Image Repave (jammy-h100)
  hosts: maas-gpu-nodes
  become: true
  tasks:
    - name: Drain workloads before repave
      ansible.builtin.service:
        name: nvidia-persistenced
        state: stopped
    - name: Trigger the MAAS deploy of custom/h100-jammy
      ansible.builtin.command: maas admin machine deploy custom/h100-jammy
"""

_PERSISTENCE_PLAYBOOK = """---
- name: NVIDIA Persistence Mode
  hosts: maas-gpu-nodes
  become: true
  tasks:
    - name: Enable nvidia-persistenced
      ansible.builtin.service:
        name: nvidia-persistenced
        state: started
        enabled: true
"""

# --- Galaxy artifacts -----------------------------------------------------
# A project's requirements.yml is the real dependency manifest: syncing the
# project installs exactly what it pins, and a role a playbook uses must appear
# here or the run cannot resolve it.

_REQUIREMENTS_YML = """---
roles:
  - name: fixitlab.baseline
    version: 1.4.2
  - name: fixitlab.webserver
    version: 2.0.1

collections:
  - name: ansible.posix
    version: 1.5.4
  - name: community.general
    version: 8.6.0
"""

# Defect variant: fixitlab.webserver floats (no version:), which the pin audit
# rejects — the artifact is present but not reproducible.
_UNPINNED_REQUIREMENTS_YML = """---
roles:
  - name: fixitlab.baseline
    version: 1.4.2
  - name: fixitlab.webserver

collections:
  - name: ansible.posix
    version: 1.5.4
"""

_GPU_REQUIREMENTS_YML = """---
roles:
  - name: nvidia.nvidia_driver
    version: 3.2.0
  - name: nvidia.dcgm
    version: 1.1.0

collections:
  - name: community.general
    version: 8.6.0
"""

# A play whose work lives in a galaxy role rather than inline tasks. Used by the
# roles labs: it cannot run until requirements.yml pins the role AND the project
# has been synced (which is what actually installs it).
_ROLE_PLAYBOOK = """---
- name: Converge Web Tier
  hosts: Production
  become: true
  roles:
    - role: fixitlab.baseline
    - role: fixitlab.webserver
"""

# Template created mid-lab with no authored text runs a trivially clean play.
_DEFAULT_NEW_PLAYBOOK = """---
- name: Site
  hosts: Production
  become: true
  tasks:
    - name: Converge the host to its desired state
      ansible.builtin.package:
        name: '*'
        state: present
"""


def _base_state() -> dict:
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"version": "AWX 24.6.1", "tower_mode": True},
        "inventories": [
            {"id": 1, "name": "Production", "hosts": 12, "sources": 1},
            {"id": 2, "name": "Staging", "hosts": 6, "sources": 1},
        ],
        "hosts": [
            {"id": "h1", "name": "web01.fixitlab.local", "inventory": "Production", "enabled": True, "status": "ok", "source": "Static"},
            {"id": "h2", "name": "web02.fixitlab.local", "inventory": "Production", "enabled": True, "status": "ok", "source": "Static"},
            {"id": "h3", "name": "db01.fixitlab.local", "inventory": "Production", "enabled": True, "status": "failed", "source": "Static"},
            {"id": "h4", "name": "lab-worker-01", "inventory": "Training", "enabled": True, "status": "ok", "source": "Static"},
            # Staging needs real host rows: a run against an empty inventory has
            # nothing to converge, which would make every recap fall back to a
            # decorative count instead of the ledger-derived one.
            {"id": "h5", "name": "stg01.fixitlab.local", "inventory": "Staging", "enabled": True, "status": "ok", "source": "Static"},
            {"id": "h6", "name": "stg02.fixitlab.local", "inventory": "Staging", "enabled": True, "status": "ok", "source": "Static"},
        ],
        "projects": [
            {"id": 1, "name": "ansible-playbooks", "scm_type": "git", "status": "successful",
             "requirements": _REQUIREMENTS_YML,
             "playbooks": ["patch.yml", "deploy.yml", "ssh_hardening.yml", "site_roles.yml"]},
            {"id": 2, "name": "tower-config", "scm_type": "git", "status": "error",
             "requirements": "", "playbooks": []},
        ],
        # Project 1 already synced at seed time, so its pinned galaxy content is
        # on the control node. Project 2 has never synced — nothing from it is
        # installed, which is what a re-sync must fix.
        "installed_roles": {"fixitlab.baseline": "1.4.2", "fixitlab.webserver": "2.0.1"},
        "installed_collections": {"ansible.posix": "1.5.4", "community.general": "8.6.0"},
        "converged": {},
        "job_templates": [
            {"id": 10, "name": "Patch Linux", "playbook": "patch.yml", "inventory": "Production", "status": "successful"},
            {"id": 11, "name": "Deploy App", "playbook": "deploy.yml", "inventory": "Staging", "status": "failed"},
            {"id": 12, "name": "Harden SSH", "playbook": "ssh_hardening.yml", "inventory": "Production", "status": "never"},
        ],
        "jobs": [
            {
                "id": 501, "name": "Patch Linux", "status": "successful", "started": _now_iso(),
                "playbook": "patch.yml", "inventory": "Production",
                "stdout": _build_job_stdout("Patch Linux", "patch.yml", "web01.fixitlab.local", False),
            },
            {
                "id": 502, "name": "Deploy App", "status": "failed", "started": _now_iso(),
                "playbook": "deploy.yml", "inventory": "Staging",
                # Historical failed run kept as backstory for the Jobs list.
                "stdout": _build_job_stdout(
                    "Deploy App", "deploy.yml", "web02.fixitlab.local", True,
                    "Timed out waiting for privilege escalation prompt",
                ),
            },
        ],
        "credentials": [
            {"id": 1, "name": "Machine SSH", "kind": "Machine"},
            {"id": 2, "name": "Vault Password", "kind": "Vault"},
        ],
        "schedules": [
            {"id": 1, "name": "Nightly patch", "template": "Patch Linux", "enabled": True, "next_run": _now_iso()},
            {"id": 2, "name": "Weekly config drift", "template": "Harden SSH", "enabled": False, "next_run": _now_iso()},
        ],
        "organizations": [
            {"id": "o1", "name": "Default", "description": "Training organization", "inventories": 4, "users": 12},
            {"id": "o2", "name": "Production Ops", "description": "Production automation", "inventories": 8, "users": 24},
        ],
        "teams": [
            {"id": "t1", "name": "Platform", "organization": "Default", "members": 6, "role": "Admin"},
            {"id": "t2", "name": "Developers", "organization": "Default", "members": 14, "role": "Execute"},
            {"id": "t3", "name": "Security", "organization": "Production Ops", "members": 4, "role": "Audit"},
        ],
        "users": [
            {"id": "u1", "username": "admin", "name": "Administrator", "role": "System Admin", "lastLogin": _now_iso()},
            {"id": "u2", "username": "awx-operator", "name": "AWX Operator", "role": "Org Admin", "lastLogin": _now_iso()},
            {"id": "u3", "username": "labuser", "name": "Lab User", "role": "Member", "lastLogin": _now_iso()},
        ],
        "activity": [
            {"id": "a1", "time": _now_iso(), "user": "admin", "action": "Launched job template Deploy Web", "object": "Job #4412"},
            {"id": "a2", "time": _now_iso(), "user": "awx-operator", "action": "Synced project", "object": "ansible-playbooks"},
            {"id": "a3", "time": _now_iso(), "user": "labuser", "action": "Created credential", "object": "prod-ssh-key"},
            {"id": "a4", "time": _now_iso(), "user": "ci-bot", "action": "Job failed", "object": "DB Backup #4408"},
        ],
        # Playbook TEXT backing each template. deploy.yml is the authored defect
        # for the "failed template" scenarios: `ansible.builtin.servce` is a
        # typo, so a launch fails with the same resolve error real ansible
        # emits until the learner corrects it via edit_playbook.
        "playbooks": {
            "patch.yml": _PATCH_PLAYBOOK,
            "deploy.yml": _DEPLOY_PLAYBOOK,
            "ssh_hardening.yml": _SSH_HARDENING_PLAYBOOK,
            "site_roles.yml": _ROLE_PLAYBOOK,
        },
        "goal": {"title": "Fix AWX", "objective": "Sync the failing project and re-run the failed job template."},
        "broken": {"project_sync_failed": True, "failed_template_id": 11},
        "events": [],
    }


def _is_ai_infra_awx_slug(slug: str) -> bool:
    s = (slug or "").lower()
    if "ai-infra" in s or s.startswith("academy-ai-infra"):
        return True
    return any(
        k in s
        for k in (
            "nvidia-driver", "dcgm-exporter", "gpu-driver", "maas-gpu",
            "image-repave", "packer-repave", "sxm-tray",
        )
    )


def _seed_ai_infra_awx(state: dict, slug: str = "") -> None:
    """Seed GPU fleet inventory + job templates matching the Lab Terminal awx CLI.

    Hero labs (e.g. ai-infra-awx-nvidia-driver-rollout) open the AWX console —
    without this seed the UI only shows Patch Linux / Deploy App.
    """
    state["inventories"] = [
        {"id": 3, "name": "maas-gpu-nodes", "hosts": 3, "sources": 1},
        {"id": 4, "name": "lxd-burn-in", "hosts": 2, "sources": 0},
        {"id": 1, "name": "Production", "hosts": 12, "sources": 1},
    ]
    state["hosts"] = [
        {"id": "g1", "name": "gpu-node-01", "inventory": "maas-gpu-nodes", "enabled": True, "status": "ok", "source": "MAAS", "ip": "10.64.12.11"},
        {"id": "g2", "name": "gpu-node-02", "inventory": "maas-gpu-nodes", "enabled": True, "status": "ok", "source": "MAAS", "ip": "10.64.12.12"},
        {"id": "g3", "name": "gpu-node-03", "inventory": "maas-gpu-nodes", "enabled": True, "status": "failed", "source": "MAAS", "ip": "10.64.12.13"},
        {"id": "l1", "name": "gpu-worker-1", "inventory": "lxd-burn-in", "enabled": True, "status": "ok", "source": "LXD"},
        {"id": "l2", "name": "k8s-node-2", "inventory": "lxd-burn-in", "enabled": True, "status": "ok", "source": "LXD"},
    ]
    state["projects"] = [
        {"id": 1, "name": "ai-infra-playbooks", "scm_type": "git", "status": "successful",
         "requirements": _GPU_REQUIREMENTS_YML,
         "playbooks": ["nvidia_driver_h100.yml", "dcgm_exporter.yml",
                       "maas_repave_h100.yml", "nvidia_persistenced.yml"]},
        {"id": 2, "name": "gpu-image-factory", "scm_type": "git", "status": "successful",
         "requirements": "", "playbooks": []},
    ]
    state["installed_roles"] = {"nvidia.nvidia_driver": "3.2.0", "nvidia.dcgm": "1.1.0"}
    state["installed_collections"] = {"community.general": "8.6.0"}
    state["converged"] = {}
    state["job_templates"] = [
        {"id": 12, "name": "GPU Driver Install (H100)", "playbook": "nvidia_driver_h100.yml", "inventory": "maas-gpu-nodes", "status": "never"},
        {"id": 18, "name": "DCGM Exporter Deploy", "playbook": "dcgm_exporter.yml", "inventory": "maas-gpu-nodes", "status": "never"},
        {"id": 24, "name": "Image Repave (jammy-h100)", "playbook": "maas_repave_h100.yml", "inventory": "maas-gpu-nodes", "status": "never"},
        {"id": 31, "name": "NVIDIA Persistence Mode", "playbook": "nvidia_persistenced.yml", "inventory": "maas-gpu-nodes", "status": "never"},
    ]
    state["jobs"] = [
        {
            "id": 601,
            "name": "GPU Driver Install (H100)",
            "status": "failed",
            "started": _now_iso(),
            "playbook": "nvidia_driver_h100.yml",
            "inventory": "maas-gpu-nodes",
            "stdout": _build_job_stdout(
                "GPU Driver Install (H100)", "nvidia_driver_h100.yml", "gpu-node-03", True,
                "Unable to acquire the dpkg frontend lock",
            ),
        },
    ]
    state["playbooks"] = {
        "nvidia_driver_h100.yml": _GPU_DRIVER_PLAYBOOK,
        "dcgm_exporter.yml": _DCGM_PLAYBOOK,
        "maas_repave_h100.yml": _REPAVE_PLAYBOOK,
        "nvidia_persistenced.yml": _PERSISTENCE_PLAYBOOK,
    }
    state["credentials"] = [
        {"id": 1, "name": "MAAS GPU Machine SSH", "kind": "Machine"},
        {"id": 2, "name": "Vault Password", "kind": "Vault"},
    ]
    state["schedules"] = [
        {"id": 1, "name": "Nightly DCGM exporter", "template": "DCGM Exporter Deploy", "enabled": True, "next_run": _now_iso()},
    ]
    state["goal"] = {
        "title": "Roll NVIDIA drivers",
        "objective": (
            "Launch GPU Driver Install (H100) against maas-gpu-nodes, "
            "confirm PLAY RECAP success, then verify nvidia-smi on the canary."
        ),
    }
    # Canary node (gpu-node-03) still on the previous driver — launch JT 12 to fix.
    state["broken"] = {"failed_template_id": 12, "canary_driver_stale": True}
    s = (slug or "").lower()
    if "dcgm" in s:
        state["goal"] = {
            "title": "Deploy DCGM exporter",
            "objective": "Launch DCGM Exporter Deploy and confirm :9400 metrics.",
        }
        state["broken"] = {"failed_template_id": 18}
    elif "repave" in s or "packer" in s:
        state["goal"] = {
            "title": "Repave GPU nodes",
            "objective": "Launch Image Repave (jammy-h100) after the Packer image lands in MAAS.",
        }
        state["broken"] = {"failed_template_id": 24}
    elif any(k in s for k in ("playbook", "undefined-var", "broken-play")):
        # Repair objective: nvidia_driver_h100.yml interpolates an undefined
        # var, so relaunching keeps failing until the vars: block is restored.
        state["playbooks"]["nvidia_driver_h100.yml"] = _BROKEN_GPU_DRIVER_PLAYBOOK
        state["goal"] = {
            "title": "Fix the driver playbook",
            "objective": (
                "GPU Driver Install (H100) fails on every node. Correct "
                "nvidia_driver_h100.yml, then relaunch until PLAY RECAP is clean."
            ),
        }
        state["broken"] = {"failed_template_id": 12, "canary_driver_stale": True}


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    # AI Infra AWX labs get GPU inventory/templates first — avoid generic
    # "template"/"job" presets that strip JT lists down to Patch Linux.
    if _is_ai_infra_awx_slug(slug):
        _seed_ai_infra_awx(state, slug)
        return
    # Galaxy/role labs: the defect is a DEPENDENCY one — site_roles.yml uses a
    # role that requirements.yml no longer pins, so no amount of relaunching
    # helps. The learner must add the pin (edit_requirements) and re-sync the
    # project (which is what actually installs it). Checked before the playbook
    # branch because the playbook text itself is correct here.
    if any(k in slug for k in ("role", "galaxy", "collection", "requirements")):
        state["job_templates"].append(
            {"id": 13, "name": "Converge Web Tier", "playbook": "site_roles.yml",
             "inventory": "Production", "status": "failed"}
        )
        # The webserver role was dropped from requirements.yml and is therefore
        # not installed — the run cannot resolve it.
        state["projects"][0]["requirements"] = _REQUIREMENTS_YML.replace(
            "  - name: fixitlab.webserver\n    version: 2.0.1\n", ""
        )
        state["installed_roles"] = {"fixitlab.baseline": "1.4.2"}
        state["goal"] = {
            "title": "Restore the missing role",
            "objective": (
                "Converge Web Tier cannot resolve fixitlab.webserver. Pin the "
                "role in requirements.yml, re-sync ansible-playbooks so galaxy "
                "installs it, then launch the template until PLAY RECAP is clean."
            ),
        }
        state["broken"] = {"failed_template_id": 13, "role_not_installed": "fixitlab.webserver"}
        return
    # Playbook-repair labs: the defect lives in the playbook TEXT, so relaunching
    # is not a fix — the learner must correct the YAML (edit_playbook) before a
    # run can go green. Checked before the generic "launch"/"job" branch because
    # these slugs contain those words too.
    if any(k in slug for k in ("playbook", "syntax", "undefined-var", "broken-play")):
        state["playbooks"]["deploy.yml"] = _BROKEN_DEPLOY_PLAYBOOK
        state["goal"] = {
            "title": "Fix the failing playbook",
            "objective": (
                "Deploy App fails every run. Read the job output, correct "
                "deploy.yml, then relaunch the template until PLAY RECAP is clean."
            ),
        }
        state["broken"] = {"failed_template_id": 11}
        return
    if "install" in slug:
        state["goal"] = {"title": "Install AWX", "objective": "Complete AWX operator install and verify the web UI is reachable."}
        state["broken"] = {"awx_not_installed": True}
    elif "template" in slug:
        state["goal"] = {"title": "Create job template", "objective": "Create a job template from the synced project and launch it."}
        state["broken"] = {"missing_template": True}
        state["job_templates"] = state["job_templates"][:1]
    elif "launch" in slug or "job" in slug:
        state["goal"] = {"title": "Launch job", "objective": "Launch the failed job template and verify success."}
        state["broken"] = {"failed_template_id": 11}
    elif "sync" in slug or "project" in slug:
        state["goal"] = {"title": "Sync project", "objective": "Sync the failing SCM project before launching templates."}
        state["broken"] = {"project_sync_failed": True}
    elif "credential" in slug:
        state["goal"] = {"title": "Fix credentials", "objective": "Attach the Machine credential to the failing template."}
        state["broken"] = {"credential_missing": True}
    elif "ha" in slug or "tower" in slug:
        state["goal"] = {"title": "Tower HA", "objective": "Verify AWX/Tower HA endpoints and re-sync the config project."}
        state["broken"] = {"project_sync_failed": True}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


def _merge_vmware_hosts(state: dict, session_id: str) -> None:
    """Expose powered-on VMware VMs as AWX inventory hosts for cross-tool labs."""
    try:
        from apps.vmware_sim.engine import _load_session as vmware_load

        vm_entry = vmware_load(str(session_id))
        if not vm_entry or not vm_entry.get("state"):
            return

        hosts = state.setdefault("hosts", [])
        existing = {str(h.get("name") or "").lower() for h in hosts}
        production = next((i for i in state.setdefault("inventories", []) if i.get("name") == "Production"), None)
        if not production:
            production = {"id": 1, "name": "Production", "hosts": 0, "sources": 0}
            state["inventories"].append(production)

        added = 0
        for vm in vm_entry["state"].get("vms", []):
            if vm.get("power") != "poweredOn":
                continue
            name = vm.get("hostname") or vm.get("name") or vm.get("id")
            if not name or str(name).lower() in existing:
                continue
            hosts.append({
                "id": f"vmware-{vm.get('id') or name}",
                "name": name,
                "inventory": "Production",
                "enabled": True,
                "status": "ok",
                "source": "VMware",
                "ip": vm.get("ip") or "",
                "guest_os": vm.get("guest_os_version") or vm.get("guest_os") or "",
            })
            existing.add(str(name).lower())
            added += 1

        if added:
            production["hosts"] = max(int(production.get("hosts") or 0), len([h for h in hosts if h.get("inventory") == "Production"]))
            production["sources"] = max(int(production.get("sources") or 0), 2)
    except Exception:
        return


def _merge_maas_identity_hosts(state: dict, session_id: str) -> None:
    """S1: pull Ready/Deployed MAAS assets from the unified registry into AWX."""
    try:
        from apps.labs.provisioner.simulation.server_identity import list_servers
    except Exception:
        return
    try:
        servers = list_servers(str(session_id))
    except Exception:
        return
    hosts = state.setdefault("hosts", [])
    existing = {str(h.get("name") or "").lower() for h in hosts}
    inventory_name = "maas-gpu-nodes"
    inv = next((i for i in state.setdefault("inventories", []) if i.get("name") == inventory_name), None)
    if not inv:
        inv = {"id": 3, "name": inventory_name, "hosts": 0, "sources": 1}
        state["inventories"].append(inv)

    added = 0
    for s in servers:
        sources = {str(x).lower() for x in (s.get("sources") or [])}
        status = (s.get("install_state") or "").strip()
        if not (sources & {"maas", "baremetal", "gpu"}):
            continue
        if status not in ("Ready", "Deployed", "deployed", "Failed testing", "Broken"):
            continue
        name = s.get("hostname") or ""
        if not name:
            continue
        row = {
            "id": f"id-{s.get('id') or name}",
            "name": name,
            "inventory": inventory_name,
            "enabled": (s.get("power") or "on") == "on",
            "status": "ok" if status in ("Deployed", "deployed", "Ready") else "failed",
            "source": "MAAS",
            "ip": s.get("primary_ip") or "",
            "serial": s.get("serial") or "",
            "asset_tag": s.get("asset_tag") or "",
        }
        if name.lower() in existing:
            for h in hosts:
                if str(h.get("name") or "").lower() == name.lower() and h.get("source") == "MAAS":
                    h["enabled"] = row["enabled"]
                    h["status"] = row["status"]
                    if row["ip"]:
                        h["ip"] = row["ip"]
                    break
            continue
        hosts.append(row)
        existing.add(name.lower())
        added += 1

    if added:
        inv["hosts"] = max(
            int(inv.get("hosts") or 0),
            len([h for h in hosts if h.get("inventory") == inventory_name]),
        )
        inv["sources"] = max(int(inv.get("sources") or 0), 1)


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    ensure_v2(entry["state"])
    # Advance live jobs on wall-clock BEFORE snapshotting so transitions persist
    # (a terminal status sticks across polls, and grading sees the final state).
    _advance_jobs(entry["state"])
    _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    _merge_vmware_hosts(state, session_id)
    _merge_maas_identity_hosts(state, session_id)
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_awx_inventory
        sync_awx_inventory(session_id, state.get("hosts") or [])
    except Exception:
        pass
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "inventory": state,
        "summary": state.get("summary", {}),
        "goal": state.get("goal", {}),
        "events": state.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "AWX session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": "Signed in to AWX", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to AWX first"}

    if action == "sync_project":
        pid = int(payload.get("project_id") or 2)
        installed = {"roles": [], "collections": [], "unpinned": []}
        for p in state.get("projects", []):
            if p["id"] == pid:
                p["status"] = "successful"
                # An SCM sync is also a galaxy install: this is the ONLY thing
                # that puts a pinned role on the control node, so editing
                # requirements.yml without re-syncing legitimately changes nothing.
                installed = _install_galaxy_requirements(state, p)
        broken.pop("project_sync_failed", None)
        _clear_resolved_role_blocker(state, broken)
        detail = (f" — installed {len(installed['roles'])} role(s), "
                  f"{len(installed['collections'])} collection(s)"
                  if (installed["roles"] or installed["collections"]) else "")
        state["events"].insert(0, {"time": _now_iso(), "message": f"Project {pid} synced{detail}", "severity": "success"})
        _activity(state, "Synced project", next((p["name"] for p in state.get("projects", []) if p["id"] == pid), str(pid)))
        _save(session_id, entry)
        return {"ok": True, "message": "Project sync completed",
                "installed_roles": installed["roles"],
                "installed_collections": installed["collections"],
                "unpinned": installed["unpinned"]}

    if action == "edit_requirements":
        # The repair surface for the dependency model. Saving alone installs
        # nothing — the learner must re-sync the project afterwards, exactly as
        # on a real control node.
        pid = int(payload.get("project_id") or 1)
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            return {"ok": False, "error": "requirements.yml content required"}
        project = next((p for p in state.get("projects", []) if p["id"] == pid), None)
        if not project:
            return {"ok": False, "error": f"No project with id {pid}"}
        project["requirements"] = content
        parsed = _parse_requirements(content)
        unpinned = [e["name"] for e in parsed["roles"] + parsed["collections"]
                    if not e.get("version")]
        project["status"] = "pending_sync"
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": (f"requirements.yml saved for {project['name']} — "
                        "re-sync the project to install"),
            "severity": "info",
        })
        _activity(state, "Edited requirements.yml", project["name"])
        _save(session_id, entry)
        return {"ok": True, "message": "requirements.yml saved (project needs a re-sync)",
                "unpinned": unpinned, "needs_sync": True}

    if action == "audit_requirements":
        # Reproducibility gate: every dependency must carry an explicit version.
        findings = []
        for p in state.get("projects", []):
            parsed = _parse_requirements(p.get("requirements") or "")
            for entry_ in parsed["roles"] + parsed["collections"]:
                if not entry_.get("version"):
                    findings.append({"project": p.get("name"), "name": entry_["name"]})
        _save(session_id, entry)
        return {
            "ok": True,
            "pinned": not findings,
            "unpinned": findings,
            "message": ("All galaxy dependencies are pinned" if not findings
                        else f"{len(findings)} dependency/dependencies are not pinned"),
        }

    if action == "launch_template":
        tid = int(payload.get("template_id") or broken.get("failed_template_id") or 11)
        jt = next((t for t in state.get("job_templates", []) if t["id"] == tid), None)
        jt = jt or {"name": "Job", "playbook": "site.yml", "inventory": "Production"}
        check_mode = bool(payload.get("check_mode"))
        job = _make_job(
            state,
            jt.get("name", "Job"),
            playbook=jt.get("playbook", "site.yml"),
            inventory=jt.get("inventory", "Production"),
            check_mode=check_mode,
        )
        will_succeed = job["finish_status"] == "successful"
        # Grading follows the DERIVED outcome, not the act of launching. A job
        # whose playbook is still broken leaves the template failed and the
        # blocker in place, so validate_awx_lab keeps failing until the learner
        # actually repairs the playbook and relaunches.
        #
        # A check-mode run is a DRY RUN: it converges nothing, so it must not
        # clear any blocker or mark the template successful. Otherwise
        # `--check` would become a free pass for every AWX lab.
        if not check_mode:
            for t in state.get("job_templates", []):
                if t["id"] == tid:
                    t["status"] = "successful" if will_succeed else "failed"
            if will_succeed:
                broken.pop("failed_template_id", None)
                broken.pop("canary_driver_stale", None)
        state.setdefault("jobs", []).insert(0, job)
        if check_mode:
            message = (f"Job {job['name']} ran in CHECK MODE (#{job['id']}) — "
                       f"{job['changed_count']} change(s) would be made")
        elif will_succeed:
            message = f"Job {job['name']} launched (#{job['id']})"
        else:
            message = (f"Job {job['name']} launched (#{job['id']}) — "
                       f"playbook error: {job['failure_reason']}")
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": message,
            "severity": "info" if check_mode else ("success" if will_succeed else "error"),
        })
        _activity(state, f"Launched job template {job['name']}", f"Job #{job['id']}")
        _save(session_id, entry)
        if will_succeed and not check_mode:
            # Cross-tech: only a run that actually converges may publish its end
            # state downstream — a failed play (or a dry run) must not reveal the
            # service on the Linux guest or kick a MAAS deploy.
            _bridge_ansible_result(session_id, job.get("name", ""), job.get("playbook", ""), payload)
            _maybe_trigger_maas_deploy(session_id, job, state)
        return {
            "ok": True,
            "message": message,
            "job_id": job["id"],
            "will_fail": not will_succeed,
            "failure_reason": job["failure_reason"],
            "check_mode": check_mode,
            "changed_count": job["changed_count"],
            "idempotent": job["idempotent"],
        }

    if action == "edit_playbook":
        # The repair surface for the content model: a learner rewrites the
        # playbook text, then relaunches. Nothing here decides pass/fail — the
        # next launch re-derives the outcome from whatever was saved.
        name = (payload.get("playbook") or "").strip()
        content = payload.get("content")
        if not name:
            return {"ok": False, "error": "playbook filename required"}
        if not isinstance(content, str) or not content.strip():
            return {"ok": False, "error": "playbook content required"}
        state.setdefault("playbooks", {})[name] = content
        reason = _evaluate_playbook(state, "", name)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": f"Playbook {name} saved" + (f" (still failing: {reason})" if reason else ""),
            "severity": "info" if reason else "success",
        })
        _activity(state, "Edited playbook", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Playbook saved", "will_fail": bool(reason),
                "failure_reason": reason}

    if action == "create_template":
        name = (payload.get("name") or "New Template").strip()
        tid = max((jt.get("id", 0) for jt in state.get("job_templates", [])), default=0) + 1
        playbook = (payload.get("playbook") or "site.yml").strip()
        state.setdefault("job_templates", []).append(
            {"id": tid, "name": name, "playbook": playbook, "inventory": "Production", "status": "never"}
        )
        # A template the learner authors gets real (healthy) text, so its runs
        # go through the same content evaluation as the seeded ones.
        state.setdefault("playbooks", {}).setdefault(
            playbook, payload.get("content") or _DEFAULT_NEW_PLAYBOOK
        )
        broken.pop("missing_template", None)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Template {name} created", "severity": "success"})
        _activity(state, "Created job template", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Job template created"}

    if action == "attach_credential":
        broken.pop("credential_missing", None)
        _save(session_id, entry)
        return {"ok": True, "message": "Credential attached to template"}

    if action == "install_awx":
        broken.pop("awx_not_installed", None)
        state["summary"]["installed"] = True
        _save(session_id, entry)
        return {"ok": True, "message": "AWX operator installed"}

    if action == "create_credential":
        name = (payload.get("name") or "Machine SSH").strip()
        kind = (payload.get("kind") or "Machine").strip()
        cred_id = max((c.get("id", 0) for c in state.get("credentials", [])), default=0) + 1
        state.setdefault("credentials", []).append({"id": cred_id, "name": name, "kind": kind})
        broken.pop("credential_missing", None)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Credential {name} created", "severity": "success"})
        _activity(state, "Created credential", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Credential created"}

    if action == "create_project":
        name = (payload.get("name") or "new-playbooks").strip()
        pid = max((p.get("id", 0) for p in state.get("projects", [])), default=0) + 1
        state.setdefault("projects", []).append(
            {"id": pid, "name": name, "scm_type": "git", "status": "successful"}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"Project {name} created", "severity": "success"})
        _activity(state, "Created project", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Project created"}

    if action == "create_inventory":
        name = (payload.get("name") or "New Inventory").strip()
        iid = max((i.get("id", 0) for i in state.get("inventories", [])), default=0) + 1
        state.setdefault("inventories", []).append({"id": iid, "name": name, "hosts": 0, "sources": 0})
        state["events"].insert(0, {"time": _now_iso(), "message": f"Inventory {name} created", "severity": "success"})
        _activity(state, "Created inventory", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Inventory created"}

    if action == "create_schedule":
        name = (payload.get("name") or "Nightly patch").strip()
        template = payload.get("template") or "Patch Linux"
        sid = max((s.get("id", 0) for s in state.get("schedules", [])), default=0) + 1
        state.setdefault("schedules", []).append(
            {"id": sid, "name": name, "template": template, "enabled": True, "next_run": _now_iso()}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"Schedule {name} for {template}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Schedule created"}

    if action == "toggle_schedule":
        sid = int(payload.get("schedule_id") or 0)
        for s in state.get("schedules", []):
            if s["id"] == sid:
                s["enabled"] = not s.get("enabled", True)
                state["events"].insert(0, {"time": _now_iso(), "message": f"Schedule {s['name']} {'enabled' if s['enabled'] else 'disabled'}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Schedule updated"}

    if action == "delete_schedule":
        sid = int(payload.get("schedule_id") or 0)
        state["schedules"] = [s for s in state.get("schedules", []) if s["id"] != sid]
        state["events"].insert(0, {"time": _now_iso(), "message": f"Schedule {sid} deleted", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Schedule deleted"}

    if action == "relaunch_job":
        jid = int(payload.get("job_id") or 0)
        src = next((j for j in state.get("jobs", []) if j["id"] == jid), None)
        src = src or {}
        job = _make_job(
            state,
            src.get("name", "Job"),
            playbook=src.get("playbook", "site.yml"),
            inventory=src.get("inventory", "Production"),
        )
        will_succeed = job["finish_status"] == "successful"
        # A relaunch of a still-broken playbook fails again — retrying is not a
        # fix, so it must not clear the template's failed status or the blocker.
        if will_succeed:
            for t in state.get("job_templates", []):
                if t.get("name") == job["name"]:
                    t["status"] = "successful"
            if broken.get("failed_template_id") is not None:
                failed_jt = next((t for t in state.get("job_templates", [])
                                  if t["id"] == broken.get("failed_template_id")), None)
                if failed_jt and failed_jt.get("name") == job["name"]:
                    broken.pop("failed_template_id", None)
                    broken.pop("canary_driver_stale", None)
        state.setdefault("jobs", []).insert(0, job)
        state["events"].insert(0, {
            "time": _now_iso(),
            "message": (f"Job {job['name']} relaunched (#{job['id']})" if will_succeed
                        else f"Job {job['name']} relaunched (#{job['id']}) — playbook error: {job['failure_reason']}"),
            "severity": "success" if will_succeed else "error",
        })
        _activity(state, "Relaunched job", f"Job #{job['id']}")
        _save(session_id, entry)
        if will_succeed:
            # Cross-tech: a relaunched service-configuring template re-converges the box.
            _bridge_ansible_result(session_id, job.get("name", ""), job.get("playbook", ""), payload)
        return {"ok": True, "message": "Job relaunched", "job_id": job["id"],
                "will_fail": not will_succeed, "failure_reason": job["failure_reason"],
                "changed_count": job["changed_count"], "idempotent": job["idempotent"]}

    if action == "cancel_job":
        jid = int(payload.get("job_id") or 0)
        for j in state.get("jobs", []):
            if j["id"] == jid and j.get("status") in ("running", "pending", "waiting"):
                j["status"] = "canceled"
                state["events"].insert(0, {"time": _now_iso(), "message": f"Job {j.get('name')} canceled", "severity": "warning"})
        _save(session_id, entry)
        return {"ok": True, "message": "Job canceled"}

    if action == "toggle_host":
        hid = str(payload.get("host_id") or "")
        toggled = None
        for h in state.get("hosts", []):
            if str(h.get("id")) == hid:
                h["enabled"] = not h.get("enabled", True)
                state["events"].insert(0, {"time": _now_iso(), "message": f"Host {h.get('name')} {'enabled' if h['enabled'] else 'disabled'}", "severity": "info"})
                toggled = h
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.server_identity import sync_awx_inventory
            sync_awx_inventory(session_id, state.get("hosts") or [])
        except Exception:
            pass
        if toggled is not None:
            try:
                from apps.labs.provisioner.simulation.chaos_engine import inject as _chaos_inject
                from apps.labs.provisioner.simulation.chaos_engine import clear_faults as _chaos_clear
                if toggled.get("enabled"):
                    _chaos_clear(session_id, fault_type="drop_nic", target=toggled.get("name") or "")
                else:
                    _chaos_inject(session_id, "drop_nic", toggled.get("name") or "", detail={"console": "awx", "host_id": hid})
            except Exception:  # pragma: no cover
                pass
        return {"ok": True, "message": "Host updated"}

    if action == "create_host":
        name = (payload.get("name") or "new-host.fixitlab.local").strip()
        inventory = (payload.get("inventory") or "Production").strip()
        hid = f"h{len(state.get('hosts', [])) + 1}-{int(time.time() * 1000) % 100000}"
        state.setdefault("hosts", []).append(
            {"id": hid, "name": name, "inventory": inventory, "enabled": True, "status": "ok", "source": "Static", "ip": ""}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"Host {name} added to {inventory}", "severity": "success"})
        _activity(state, "Created host", name)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.server_identity import sync_awx_inventory
            sync_awx_inventory(session_id, state.get("hosts") or [])
        except Exception:
            pass
        return {"ok": True, "message": "Host created"}

    if action == "create_organization":
        name = (payload.get("name") or "New Organization").strip()
        description = (payload.get("description") or "").strip()
        oid = f"o{len(state.get('organizations', [])) + 1}-{int(time.time() * 1000) % 100000}"
        state.setdefault("organizations", []).append(
            {"id": oid, "name": name, "description": description, "inventories": 0, "users": 0}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"Organization {name} created", "severity": "success"})
        _activity(state, "Created organization", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Organization created"}

    if action == "create_team":
        name = (payload.get("name") or "New Team").strip()
        org = (payload.get("organization") or "Default").strip()
        tid = f"t{len(state.get('teams', [])) + 1}-{int(time.time() * 1000) % 100000}"
        state.setdefault("teams", []).append(
            {"id": tid, "name": name, "organization": org, "members": 0, "role": "Member"}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"Team {name} created", "severity": "success"})
        _activity(state, "Created team", name)
        _save(session_id, entry)
        return {"ok": True, "message": "Team created"}

    if action == "create_user":
        username = (payload.get("username") or "new-user").strip()
        display = (payload.get("name") or username).strip()
        role = (payload.get("role") or "Member").strip()
        uid = f"u{len(state.get('users', [])) + 1}-{int(time.time() * 1000) % 100000}"
        state.setdefault("users", []).append(
            {"id": uid, "username": username, "name": display, "role": role, "lastLogin": _now_iso()}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"User {username} created", "severity": "success"})
        _activity(state, "Created user", username)
        _save(session_id, entry)
        return {"ok": True, "message": "User created"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            state.setdefault("events", []).insert(0, {
                "time": _now_iso(), "message": v2.get("message") or action, "severity": "success",
            })
            _activity(state, v2.get("message") or action, action)
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# Per-key grader feedback. The broken dict stores bare targets (a job template
# id) and often just True, so the value cannot be echoed the way azure_engine
# echoes its human-readable reasons.
_BROKEN_REASONS: dict[str, str] = {
    "project_sync_failed": "the project has not synced successfully yet — fix the SCM settings and re-sync",
    "failed_template_id": "job template {target} has not completed a successful run yet",
    "canary_driver_stale": "the canary host is still on the stale driver — update it",
    "awx_not_installed": "AWX has not been installed yet",
    "missing_template": "the required job template has not been created yet",
    "credential_missing": "the required credential has not been created yet",
    "needs_maas_deploy": "the MAAS deployment job has not been run yet",
    "role_not_installed": ("the galaxy role {target} is not installed — pin it in "
                           "requirements.yml and re-sync the project"),
}


def _describe_broken(broken: dict) -> str:
    """Name every outstanding objective, not just the first.

    Several AWX presets seed two keys at once (a failed template plus a stale
    canary driver, a sync failure plus a failed template), so reporting only
    next(iter(...)) would hide half the work still remaining.
    """
    parts = []
    for kind, target in broken.items():
        template = _BROKEN_REASONS.get(kind)
        if template is None:
            # Unknown key: still fail CLOSED, and name the key so a missing
            # template surfaces as a reportable gap rather than a silent pass.
            parts.append(f"unresolved objective ({kind})")
        else:
            parts.append(template.format(target=target))
    return "; ".join(parts)


def validate_awx_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No AWX session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, f"AWX lab not complete: {_describe_broken(broken)}"
    return True, "AWX lab objectives met"
