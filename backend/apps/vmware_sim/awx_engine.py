"""In-memory Ansible AWX / Ansible Tower simulator for training labs."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

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


def _build_job_stdout(name: str, playbook: str, host: str, will_fail: bool) -> list[str]:
    """A realistic ansible-playbook run log for a job template launch.

    Returned as an ordered list; get_state reveals a growing prefix as the job
    advances so the UI streams the output line by line.
    """
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
        lines += [
            _ansi("red", f"fatal: [{host}]: FAILED! => {{\"changed\": false, \"msg\": \"task failed\"}}"),
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


def _make_job(state: dict, name: str, *, playbook: str = "site.yml",
              inventory: str = "Production", will_fail: bool = False,
              started_ts: float | None = None) -> dict:
    """Create a launched job object with a live wall-clock timeline."""
    new_id = max((int(j.get("id", 0)) for j in state.get("jobs", [])), default=500) + 1
    host = _job_host_for(state, inventory)
    finish = "failed" if will_fail else "successful"
    return {
        "id": new_id,
        "name": name,
        "playbook": playbook,
        "inventory": inventory,
        "status": "pending",
        "started": _now_iso(),
        "started_ts": started_ts if started_ts is not None else _now(),
        "finish_status": finish,
        "stdout_plan": _build_job_stdout(name, playbook, host, will_fail),
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
        ],
        "projects": [
            {"id": 1, "name": "ansible-playbooks", "scm_type": "git", "status": "successful"},
            {"id": 2, "name": "tower-config", "scm_type": "git", "status": "error"},
        ],
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
                "stdout": _build_job_stdout("Deploy App", "deploy.yml", "web02.fixitlab.local", True),
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
        "goal": {"title": "Fix AWX", "objective": "Sync the failing project and re-run the failed job template."},
        "broken": {"project_sync_failed": True, "failed_template_id": 11},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
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


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    # Advance live jobs on wall-clock BEFORE snapshotting so transitions persist
    # (a terminal status sticks across polls, and grading sees the final state).
    if _advance_jobs(entry["state"]):
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    _merge_vmware_hosts(state, session_id)
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
        for p in state.get("projects", []):
            if p["id"] == pid:
                p["status"] = "successful"
        broken.pop("project_sync_failed", None)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Project {pid} synced", "severity": "success"})
        _activity(state, "Synced project", next((p["name"] for p in state.get("projects", []) if p["id"] == pid), str(pid)))
        _save(session_id, entry)
        return {"ok": True, "message": "Project sync completed"}

    if action == "launch_template":
        tid = int(payload.get("template_id") or broken.get("failed_template_id") or 11)
        jt = next((t for t in state.get("job_templates", []) if t["id"] == tid), None)
        jt = jt or {"name": "Job", "playbook": "site.yml", "inventory": "Production"}
        job = _make_job(
            state,
            jt.get("name", "Job"),
            playbook=jt.get("playbook", "site.yml"),
            inventory=jt.get("inventory", "Production"),
            will_fail=False,
        )
        # Launching resolves the failing template + clears the blocker so grading
        # (validate_awx_lab) still passes the moment the job is launched, while
        # the job's own status streams pending->...->successful on wall-clock.
        for t in state.get("job_templates", []):
            if t["id"] == tid:
                t["status"] = "successful"
        broken.pop("failed_template_id", None)
        state.setdefault("jobs", []).insert(0, job)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Job {job['name']} launched (#{job['id']})", "severity": "success"})
        _activity(state, f"Launched job template {job['name']}", f"Job #{job['id']}")
        _save(session_id, entry)
        # Cross-tech: a service-configuring template launched successfully →
        # publish its intended end state so the Linux terminal reveals it.
        _bridge_ansible_result(session_id, job.get("name", ""), job.get("playbook", ""), payload)
        return {"ok": True, "message": "Job launched", "job_id": job["id"]}

    if action == "create_template":
        name = (payload.get("name") or "New Template").strip()
        tid = max((jt.get("id", 0) for jt in state.get("job_templates", [])), default=0) + 1
        state.setdefault("job_templates", []).append(
            {"id": tid, "name": name, "playbook": "site.yml", "inventory": "Production", "status": "never"}
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
            will_fail=False,
        )
        state.setdefault("jobs", []).insert(0, job)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Job {job['name']} relaunched (#{job['id']})", "severity": "success"})
        _activity(state, "Relaunched job", f"Job #{job['id']}")
        _save(session_id, entry)
        # Cross-tech: a relaunched service-configuring template re-converges the box.
        _bridge_ansible_result(session_id, job.get("name", ""), job.get("playbook", ""), payload)
        return {"ok": True, "message": "Job relaunched", "job_id": job["id"]}

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
        for h in state.get("hosts", []):
            if str(h.get("id")) == hid:
                h["enabled"] = not h.get("enabled", True)
                state["events"].insert(0, {"time": _now_iso(), "message": f"Host {h.get('name')} {'enabled' if h['enabled'] else 'disabled'}", "severity": "info"})
        _save(session_id, entry)
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

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_awx_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No AWX session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "AWX environment still has unresolved issues"
    return True, "AWX lab objectives met"
