"""In-memory Commvault CommCell console simulator for backup/restore training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of a CommCell
console: clients, storage policies, subclients, backup + restore jobs with a
wall-clock timeline (pending -> running -> completed), media agents, and disk
libraries. When a VMware simulator session exists for the same lab session id,
its powered-on VMs are pulled in as CommCell clients (cross-tech backup lab);
otherwise a static web/db/app client trio is seeded so the console is never
empty.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200

# Wall-clock thresholds (seconds since a job was kicked off) for the
# pending -> running -> completed/failed timeline.
_JOB_RUNNING_AT = 2.0
_JOB_FINISH_AT = 6.0


def _session_key(session_id: str) -> str:
    return f"commvault_session:{session_id}"


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


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message, "severity": severity})


# ---------------------------------------------------------------------------
# Job lifecycle (mirrors awx_engine's wall-clock job model): a launched backup
# or restore job carries `started_ts` and its status is derived purely from
# elapsed time, so every poll independently computes the correct status.
# ---------------------------------------------------------------------------

def _make_job(state: dict, *, kind: str, subclient: str, policy: str,
              job_type: str = "Full", will_fail: bool = False) -> dict:
    jobs = state.setdefault("jobs", [])
    new_id = max((int(j.get("id", 0)) for j in jobs), default=1000) + 1
    return {
        "id": new_id,
        "kind": kind,  # "backup" | "restore"
        "subclient": subclient,
        "policy": policy,
        "type": job_type,
        "status": "pending",
        "started": _now_iso(),
        "started_ts": _now(),
        "finish_status": "failed" if will_fail else "completed",
        "size_gb": round(1.5 + (new_id % 7) * 0.8, 1),
        "progress": 0,
    }


def _advance_job(job: dict) -> bool:
    status = job.get("status")
    if status in ("completed", "failed", "killed"):
        return False
    started = job.get("started_ts")
    if started is None:
        return False
    elapsed = max(0.0, _now() - float(started))
    finish = job.get("finish_status") or "completed"
    if elapsed >= _JOB_FINISH_AT:
        new_status, progress = finish, 100
    elif elapsed >= _JOB_RUNNING_AT:
        span = _JOB_FINISH_AT - _JOB_RUNNING_AT
        frac = (elapsed - _JOB_RUNNING_AT) / span if span else 1.0
        new_status, progress = "running", min(99, int(frac * 100))
    else:
        new_status, progress = "pending", 0
    changed = new_status != status
    job["status"] = new_status
    job["progress"] = progress
    return changed


def _advance_jobs(state: dict) -> bool:
    changed = False
    for job in state.get("jobs", []):
        if _advance_job(job):
            changed = True
    return changed


def _merge_vmware_clients(state: dict, session_id: str) -> None:
    """Expose powered-on VMware VMs as CommCell clients for cross-tech backup labs."""
    try:
        from apps.vmware_sim.engine import _load_session as vmware_load

        vm_entry = vmware_load(str(session_id))
        if not vm_entry or not vm_entry.get("state"):
            return
        clients = state.setdefault("clients", [])
        existing = {str(c.get("name") or "").lower() for c in clients}
        added = 0
        for vm in vm_entry["state"].get("vms", []):
            if vm.get("power") != "poweredOn":
                continue
            name = vm.get("hostname") or vm.get("name") or vm.get("id")
            if not name or str(name).lower() in existing:
                continue
            clients.append({
                "id": f"vmware-{vm.get('id') or name}",
                "name": name,
                "os": vm.get("guest_os_version") or vm.get("guest_os") or "Linux",
                "ip": vm.get("ip") or "",
                "status": "online",
                "backup_health": "protected" if vm.get("power") == "poweredOn" else "unprotected",
                "source": "VMware",
            })
            existing.add(str(name).lower())
            added += 1
        if added:
            _event(state, f"Discovered {added} VMware client(s) via VSA proxy", "info")
    except Exception:
        return


def _base_state() -> dict:
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"version": "Commvault Command Center 11.36", "commcell": "fixitlab-cc"},
        "clients": [
            {"id": "c1", "name": "web01", "os": "Linux", "ip": "10.0.0.11", "status": "online", "backup_health": "protected", "source": "Static"},
            {"id": "c2", "name": "db01", "os": "Linux", "ip": "10.0.0.12", "status": "online", "backup_health": "overdue", "source": "Static"},
            {"id": "c3", "name": "app01", "os": "Windows", "ip": "10.0.0.13", "status": "offline", "backup_health": "unprotected", "source": "Static"},
        ],
        "storage_policies": [
            {"id": "sp1", "name": "Gold-Retention-30d", "enabled": True, "retention_days": 30, "library": "DiskLib-01"},
            {"id": "sp2", "name": "Silver-Retention-7d", "enabled": False, "retention_days": 7, "library": "DiskLib-01"},
        ],
        "subclients": [
            {"id": "sc1", "name": "default", "client": "web01", "policy": "Gold-Retention-30d", "content": ["/var/www"]},
            {"id": "sc2", "name": "default", "client": "db01", "policy": "Gold-Retention-30d", "content": ["/var/lib/mysql"]},
        ],
        "jobs": [
            {"id": 1001, "kind": "backup", "subclient": "default (web01)", "policy": "Gold-Retention-30d",
             "type": "Full", "status": "completed", "started": _now_iso(), "started_ts": _now() - 100,
             "finish_status": "completed", "size_gb": 4.2, "progress": 100},
        ],
        "media_agents": [
            {"name": "MA-01", "status": "online", "os": "Linux"},
        ],
        "libraries": [
            {"name": "DiskLib-01", "type": "Disk", "capacity_gb": 2000, "used_gb": 640},
        ],
        "goal": {"title": "Commvault backup lab", "objective": "Run a backup job for the client with overdue protection."},
        "broken": {"overdue_client": "db01"},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "restore" in slug:
        state["goal"] = {"title": "Restore data", "objective": "Run a restore job from the latest successful backup of web01."}
        state["broken"] = {"needs_restore": "web01"}
    elif "policy" in slug:
        state["goal"] = {"title": "Enable storage policy", "objective": "Enable the disabled Silver-Retention-7d storage policy."}
        state["broken"] = {"policy_disabled": "Silver-Retention-7d"}
    elif "subclient" in slug:
        state["goal"] = {"title": "Create subclient", "objective": "Create a subclient for app01 and assign it to a storage policy."}
        state["broken"] = {"missing_subclient": "app01"}
    elif "client" in slug and ("add" in slug or "register" in slug or "discover" in slug):
        state["goal"] = {"title": "Register client", "objective": "Add a new client to the CommCell and verify it comes online."}
        state["broken"] = {"missing_client": True}
    elif "backup" in slug or "job" in slug or "overdue" in slug:
        state["goal"] = {"title": "Fix overdue backup", "objective": "Run a backup job for db01 to clear its overdue protection status."}
        state["broken"] = {"overdue_client": "db01"}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


_ensure_session = _ensure


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    if _advance_jobs(entry["state"]):
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    _merge_vmware_clients(state, session_id)
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": state,
        "goal": state.get("goal", {}),
        "events": state.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def _find_client(state: dict, ident: str) -> dict | None:
    return next((c for c in state.get("clients", []) if c.get("name") == ident or c.get("id") == ident), None)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Commvault session not found"}
    state = entry["state"]
    _advance_jobs(state)
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        _event(state, "Signed in to Command Center", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to the Command Center first"}

    if action == "run_backup":
        client_name = payload.get("client") or broken.get("overdue_client") or "db01"
        client = _find_client(state, client_name)
        subclient = next((s for s in state.get("subclients", []) if s.get("client") == client_name), None)
        policy_name = (subclient or {}).get("policy") or payload.get("policy") or "Gold-Retention-30d"
        job = _make_job(state, kind="backup", subclient=f"default ({client_name})", policy=policy_name,
                         job_type=payload.get("type") or "Full", will_fail=False)
        state.setdefault("jobs", []).insert(0, job)
        if client:
            client["backup_health"] = "protected"
            client["status"] = "online"
        if broken.get("overdue_client") == client_name:
            broken.pop("overdue_client", None)
        _event(state, f"Backup job {job['id']} started for {client_name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Backup job started", "job_id": job["id"]}

    if action == "run_restore":
        client_name = payload.get("client") or broken.get("needs_restore") or "web01"
        job = _make_job(state, kind="restore", subclient=f"default ({client_name})",
                         policy=payload.get("policy") or "Gold-Retention-30d",
                         job_type="Restore", will_fail=False)
        state.setdefault("jobs", []).insert(0, job)
        broken.pop("needs_restore", None)
        _event(state, f"Restore job {job['id']} started for {client_name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Restore job started", "job_id": job["id"]}

    if action == "create_subclient":
        client_name = payload.get("client") or broken.get("missing_subclient") or "app01"
        name = payload.get("name") or "default"
        policy = payload.get("policy") or "Gold-Retention-30d"
        content = payload.get("content") or ["/data"]
        sc_id = f"sc{len(state.get('subclients', [])) + 1}"
        state.setdefault("subclients", []).append(
            {"id": sc_id, "name": name, "client": client_name, "policy": policy, "content": content}
        )
        if broken.get("missing_subclient") == client_name:
            broken.pop("missing_subclient", None)
        _event(state, f"Subclient {name} created for {client_name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Subclient created", "subclient_id": sc_id}

    if action == "add_client":
        name = (payload.get("name") or "new-client").strip()
        cid = f"c{len(state.get('clients', [])) + 1}"
        state.setdefault("clients", []).append({
            "id": cid, "name": name, "os": payload.get("os") or "Linux",
            "ip": payload.get("ip") or "", "status": "online",
            "backup_health": "unprotected", "source": "Static",
        })
        broken.pop("missing_client", None)
        _event(state, f"Client {name} added to CommCell", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Client added", "client_id": cid}

    if action == "enable_policy":
        name = payload.get("name") or broken.get("policy_disabled") or ""
        policy = next((p for p in state.get("storage_policies", []) if p.get("name") == name or p.get("id") == name), None)
        if not policy:
            return {"ok": False, "error": f"Storage policy '{name}' not found"}
        policy["enabled"] = True
        if broken.get("policy_disabled") == policy["name"]:
            broken.pop("policy_disabled", None)
        _event(state, f"Storage policy {policy['name']} enabled", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Storage policy enabled"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_commvault_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No Commvault session"
    state = entry["state"]
    if _advance_jobs(state):
        _save(session_id, entry)
    broken = state.get("broken") or {}
    slug = (scenario_slug or entry.get("scenario_slug") or "").lower()

    if "restore" in slug:
        ok = any(j.get("kind") == "restore" and j.get("status") == "completed" for j in state.get("jobs", []))
        return (ok, "Restore job completed" if ok else "Run a restore job to completion")
    if "policy" in slug:
        name = broken.get("policy_disabled")
        if name:
            policy = next((p for p in state.get("storage_policies", []) if p.get("name") == name), None)
            if not policy or not policy.get("enabled"):
                return False, f"Enable storage policy {name}"
        return True, "Storage policy enabled"
    if "subclient" in slug:
        if broken.get("missing_subclient"):
            return False, "Create the missing subclient"
        return True, "Subclient created"
    if "client" in slug and ("add" in slug or "register" in slug or "discover" in slug):
        if broken.get("missing_client"):
            return False, "Register a new client"
        return True, "Client registered"

    if broken:
        return False, "Commvault environment still has unresolved issues"
    ok = any(j.get("kind") == "backup" and j.get("status") == "completed" for j in state.get("jobs", []))
    if not ok:
        return False, "Run a backup job to completion"
    return True, "Commvault lab objectives met"
