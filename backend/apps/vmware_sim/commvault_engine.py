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
import hashlib
import json
import time
from typing import Any

from django.core.cache import cache

from .commvault_v2_facades import apply_v2_action, ensure_v2, seed_v2

SESSION_TTL = 7200

# Wall-clock thresholds (seconds since a job was kicked off) for the
# pending -> running -> completed/failed timeline.
_JOB_RUNNING_AT = 2.0
_JOB_FINISH_AT = 6.0

# A day in seconds — retention is expressed in days but recovery points carry a
# wall-clock timestamp, so aging a point past its policy's retention in a test
# (or a long-lived session) is a plain arithmetic comparison.
_DAY = 86400.0


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
    entry = {"time": _now_iso(), "message": message, "severity": severity}
    state.setdefault("events", []).insert(0, entry)
    state.setdefault("activity_log", []).insert(0, entry)
    state["activity_log"] = state["activity_log"][:200]


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
            # Provenance is settled at completion, not at launch: a backup only
            # yields a recovery point if it actually finished, and a restore is
            # only verified against the media once its job has run out.
            if job.get("status") == "completed":
                if job.get("kind") == "backup" and job.get("pending_point"):
                    _complete_backup_job(state, job)
                elif job.get("kind") == "restore":
                    _complete_restore_job(state, job)
    return changed


# ---------------------------------------------------------------------------
# Backup/restore provenance
#
# A completed backup writes a *recovery point*: a manifest of the subclient's
# content (path -> sha256 of the bytes that were protected) plus the job that
# produced it, the policy that governs its retention, and which copies hold it.
# A restore SELECTS a recovery point, materialises its files through the
# Linux-terminal bridge, then VERIFIES the materialised bytes against the
# manifest. Everything a restore can legitimately fail on — no point, expired
# by retention, copy unavailable, corrupt/incomplete backup — is decided from
# this data rather than hardcoded, so `will_fail` is a computed outcome.
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _synthetic_file_body(client: str, path: str, generation: int) -> str:
    """Deterministic stand-in for the bytes a real agent would have protected.

    Deterministic per (client, path, generation) so a restore of generation N
    reproduces exactly the content backup N recorded — that reproducibility is
    the whole point of the manifest check.
    """
    return f"{client}:{path}:gen{generation}\n"


def _subclient_content(state: dict, client_name: str) -> list[str]:
    sub = next((s for s in state.get("subclients", []) if s.get("client") == client_name), None)
    return list((sub or {}).get("content") or [])


def _manifest_for(state: dict, client_name: str, generation: int) -> list[dict]:
    """Expand a subclient's content roots into per-file manifest entries."""
    entries = []
    for root in _subclient_content(state, client_name) or [f"/data/{client_name}"]:
        for leaf in ("index.dat", "records.db"):
            path = f"{root.rstrip('/')}/{leaf}"
            body = _synthetic_file_body(client_name, path, generation)
            entries.append({"path": path, "sha256": _sha256(body), "size": len(body)})
    return entries


def _policy_for(state: dict, name: str) -> dict | None:
    return next((p for p in state.get("storage_policies", []) if p.get("name") == name), None)


def _record_recovery_point(state: dict, *, job: dict, client_name: str,
                           policy_name: str, corrupt: bool = False,
                           incomplete: bool = False) -> dict:
    """Register the recovery point a completed backup leaves behind."""
    points = state.setdefault("recovery_points", [])
    generation = len(points) + 1
    manifest = _manifest_for(state, client_name, generation)
    if incomplete and len(manifest) > 1:
        # An aborted backup protected only part of the content set; the manifest
        # still advertises the full set, which is exactly what makes the
        # shortfall detectable at restore time.
        stored = [e["path"] for e in manifest[:-1]]
    else:
        stored = [e["path"] for e in manifest]
    point = {
        "id": f"rp-{job['id']}",
        "job_id": job["id"],
        "client": client_name,
        "policy": policy_name,
        "type": job.get("type") or "Full",
        "generation": generation,
        "created": _now_iso(),
        "created_ts": _now(),
        "manifest": manifest,
        # Paths actually written to media. Divergence from the manifest is the
        # "incomplete backup" fault.
        "stored_paths": stored,
        # Media-side corruption: the bytes on media no longer hash to what the
        # manifest recorded, so restore verification must reject them.
        "corrupt": bool(corrupt),
        "copies": ["primary"],
    }
    points.insert(0, point)
    return point


def _retention_days(state: dict, point: dict) -> int:
    policy = _policy_for(state, point.get("policy") or "")
    return int((policy or {}).get("retention_days") or 30)


def _is_expired(state: dict, point: dict) -> bool:
    """Aged past its policy's retention → pruned from what is restorable."""
    created = point.get("created_ts")
    if created is None:
        return False
    return (_now() - float(created)) > _retention_days(state, point) * _DAY


def _restorable_points(state: dict, client_name: str, *,
                       copy_name: str = "primary") -> list[dict]:
    """Recovery points for a client that retention and copy placement still allow.

    Newest first. Retention and aux-copy placement are enforced here, which is
    what makes those settings affect what is restorable instead of being inert
    seed fields.
    """
    out = []
    for point in state.get("recovery_points", []):
        if point.get("client") != client_name:
            continue
        if _is_expired(state, point):
            continue
        if copy_name not in (point.get("copies") or ["primary"]):
            continue
        out.append(point)
    return sorted(out, key=lambda p: float(p.get("created_ts") or 0), reverse=True)


def _select_recovery_point(state: dict, client_name: str, *,
                           point_id: str = "", job_id: Any = None,
                           before_ts: float | None = None,
                           copy_name: str = "primary") -> tuple[dict | None, str]:
    """Point-in-time selection. Returns (point, error-if-none)."""
    candidates = _restorable_points(state, client_name, copy_name=copy_name)
    if point_id:
        point = next((p for p in candidates if p.get("id") == point_id), None)
        return (point, "" if point else
                f"Recovery point {point_id} is not available on copy '{copy_name}'")
    if job_id is not None:
        point = next((p for p in candidates if str(p.get("job_id")) == str(job_id)), None)
        return (point, "" if point else
                f"No restorable recovery point from job {job_id} on copy '{copy_name}'")
    if before_ts is not None:
        # Point-in-time: newest recovery point at or before the requested instant.
        point = next((p for p in candidates
                      if float(p.get("created_ts") or 0) <= float(before_ts)), None)
        return (point, "" if point else
                "No recovery point exists at or before the requested point in time")
    point = candidates[0] if candidates else None
    if point:
        return point, ""
    if any(p.get("client") == client_name for p in state.get("recovery_points", [])):
        return None, (f"No restorable backup for {client_name} on copy '{copy_name}' — "
                      "every recovery point is expired or not on this copy")
    return None, f"No backup of {client_name} exists to restore from"


def _verify_restore(state: dict, point: dict, materialised: dict[str, str]) -> tuple[bool, str]:
    """Compare what the restore actually laid down against the manifest.

    Fails CLOSED: a missing path, a hash mismatch, or an empty materialisation
    all reject. This is the check whose absence let a restore that never wrote
    anything report success.
    """
    manifest = point.get("manifest") or []
    if not manifest:
        return False, "Recovery point has no manifest — nothing to verify against"
    missing, mismatched = [], []
    for entry in manifest:
        path = entry.get("path")
        if path not in materialised:
            missing.append(path)
            continue
        if _sha256(materialised[path]) != entry.get("sha256"):
            mismatched.append(path)
    if missing:
        return False, (f"Restore verification failed: {len(missing)} file(s) missing from the "
                       f"restored set (first: {missing[0]})")
    if mismatched:
        return False, (f"Restore verification failed: checksum mismatch on {len(mismatched)} "
                       f"file(s) (first: {mismatched[0]})")
    return True, f"Verified {len(manifest)} file(s) against the recovery point manifest"


def _materialise(state: dict, point: dict) -> dict[str, str]:
    """Produce the bytes a restore of this point puts back on the guest.

    Only `stored_paths` come back — a manifest entry that was never written to
    media cannot be materialised — and corrupt media yields bytes that will not
    hash to the manifest value.
    """
    stored = set(point.get("stored_paths") or [])
    out: dict[str, str] = {}
    for entry in point.get("manifest") or []:
        path = entry.get("path")
        if path not in stored:
            continue
        body = _synthetic_file_body(point.get("client") or "", path, point.get("generation") or 1)
        if point.get("corrupt"):
            body = body + "\x00CORRUPT"
        out[path] = body
    return out


def _complete_backup_job(state: dict, job: dict) -> None:
    """A backup that reached `completed` leaves a recovery point behind."""
    spec = job.pop("pending_point", None) or {}
    point = _record_recovery_point(
        state, job=job,
        client_name=spec.get("client") or "",
        policy_name=spec.get("policy") or "",
        corrupt=bool(spec.get("corrupt")),
        incomplete=bool(spec.get("incomplete")),
    )
    job["recovery_point"] = point["id"]
    _event(state, f"Backup job {job['id']} completed — recovery point {point['id']} "
                  f"({len(point['stored_paths'])} file(s)) written to {point['policy']}", "success")


def _complete_restore_job(state: dict, job: dict) -> None:
    """A restore that reached `completed` must still pass verification.

    Verification runs against what the bridge recorded the restore as having
    materialised on the guest. It can flip the job to `failed`, which is the
    behaviour whose absence made every restore an automatic pass.
    """
    if job.get("verified") is not None:
        return
    point_id = job.get("recovery_point")
    point = next((p for p in state.get("recovery_points", []) if p.get("id") == point_id), None)
    if not point:
        job["status"] = "failed"
        job["finish_status"] = "failed"
        job["verified"] = False
        job["verify_message"] = "Recovery point no longer available at verification time"
        _event(state, f"Restore job {job['id']} failed: {job['verify_message']}", "error")
        return

    materialised = job.get("materialised") or {}
    ok, message = _verify_restore(state, point, materialised)
    job["verified"] = ok
    job["verify_message"] = message
    job["verified_files"] = len(materialised)
    if not ok:
        job["status"] = "failed"
        job["finish_status"] = "failed"
        _event(state, f"Restore job {job['id']} failed verification: {message}", "error")
        return
    _event(state, f"Restore job {job['id']} verified against {point['id']}: {message}", "success")
    # Only a VERIFIED restore clears the objective. Popping this at launch is
    # what previously let an unverified restore satisfy the grader.
    broken = state.get("broken") or {}
    if broken.get("needs_restore") == point.get("client"):
        broken.pop("needs_restore", None)


def _redact_internal(state: dict) -> None:
    """Drop verification bookkeeping from the client-facing state copy.

    The restored file bodies and the pending-point spec are how the server
    decides an outcome; shipping them to the browser on every poll would both
    bloat the payload and hand the learner the answer. The verdict
    (`verified` / `verify_message`) stays — that is console-visible detail.
    """
    for job in state.get("jobs", []):
        job.pop("materialised", None)
        job.pop("pending_point", None)
    for point in state.get("recovery_points", []):
        point.pop("corrupt", None)


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
            {"name": "MA-01", "status": "online", "os": "Linux", "streams": 10, "free_space_gb": 1200},
            {"name": "MA-02", "status": "online", "os": "Linux", "streams": 8, "free_space_gb": 800},
        ],
        "libraries": [
            {"name": "DiskLib-01", "type": "Disk", "capacity_gb": 2000, "used_gb": 640, "media_agent": "MA-01"},
            {"name": "CloudLib-S3", "type": "Cloud", "capacity_gb": 10000, "used_gb": 2100, "media_agent": "MA-02"},
        ],
        "schedules": [
            {"id": "sch1", "name": "Daily-Full-web01", "client": "web01", "policy": "Gold-Retention-30d",
             "type": "Full", "cron": "0 2 * * *", "enabled": True},
            {"id": "sch2", "name": "Incremental-db01", "client": "db01", "policy": "Gold-Retention-30d",
             "type": "Incremental", "cron": "0 */6 * * *", "enabled": False},
        ],
        "aux_copies": [
            {"id": "ac1", "name": "Gold-to-Cloud", "source_policy": "Gold-Retention-30d",
             "dest_library": "CloudLib-S3", "status": "idle"},
        ],
        # Populated by _seed_recovery_points once the subclient content exists.
        "recovery_points": [],
        "activity_log": [],
        "goal": {"title": "Commvault backup lab", "objective": "Run a backup job for the client with overdue protection."},
        "broken": {"overdue_client": "db01"},
        "events": [],
        **seed_v2(),
    }


def _seed_recovery_points(state: dict) -> None:
    """Give the pre-seeded completed backup (job 1001) a real recovery point.

    Without this the console would open showing a successful historical backup
    that nothing could actually be restored from.
    """
    seed_job = next((j for j in state.get("jobs", []) if int(j.get("id", 0)) == 1001), None)
    if not seed_job or state.get("recovery_points"):
        return
    point = _record_recovery_point(
        state, job=seed_job, client_name="web01",
        policy_name=seed_job.get("policy") or "Gold-Retention-30d",
    )
    # Backdate to match the job it came from, so point-in-time selection has a
    # genuinely older point to choose between.
    point["created_ts"] = float(seed_job.get("started_ts") or _now()) - 100.0


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "restore" in slug:
        state["goal"] = {"title": "Restore data", "objective": "Restore web01 from a recovery point and pass restore verification."}
        state["broken"] = {"needs_restore": "web01"}
        if "corrupt" in slug or "verify" in slug:
            # The newest recovery point cannot be verified; the learner must
            # notice the failure and restore from the older good point instead.
            for point in state.get("recovery_points", []):
                if point.get("client") == "web01":
                    point["corrupt"] = True
                    break
            good = _record_recovery_point(
                state, job={"id": 1000, "type": "Full"}, client_name="web01",
                policy_name="Gold-Retention-30d",
            )
            # Older than the corrupt point, so "restore latest" hits the bad one
            # first and the learner has to select the earlier point explicitly.
            for point in state.get("recovery_points", []):
                if point.get("corrupt"):
                    good["created_ts"] = float(point.get("created_ts") or _now()) - 3600.0
                    break
            state["goal"]["objective"] = (
                "The latest backup of web01 fails restore verification. "
                "Restore from a recovery point that verifies clean."
            )
    elif "policy" in slug:
        state["goal"] = {"title": "Enable storage policy", "objective": "Enable the disabled Silver-Retention-7d storage policy."}
        state["broken"] = {"policy_disabled": "Silver-Retention-7d"}
    elif "subclient" in slug:
        state["goal"] = {"title": "Create subclient", "objective": "Create a subclient for app01 and assign it to a storage policy."}
        state["broken"] = {"missing_subclient": "app01"}
    elif "client" in slug and ("add" in slug or "register" in slug or "discover" in slug):
        state["goal"] = {"title": "Register client", "objective": "Add a new client to the CommCell and verify it comes online."}
        state["broken"] = {"missing_client": True}
    elif "schedule" in slug:
        state["goal"] = {"title": "Enable schedule", "objective": "Enable the disabled Incremental-db01 schedule."}
        state["broken"] = {"schedule_disabled": "Incremental-db01"}
    elif "aux" in slug or "copy" in slug:
        state["goal"] = {"title": "Run aux copy", "objective": "Start the Gold-to-Cloud auxiliary copy job."}
        state["broken"] = {"needs_aux_copy": "Gold-to-Cloud"}
    elif "backup" in slug or "job" in slug or "overdue" in slug:
        state["goal"] = {"title": "Fix overdue backup", "objective": "Run a backup job for db01 to clear its overdue protection status."}
        state["broken"] = {"overdue_client": "db01"}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _seed_recovery_points(state)
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


_ensure_session = _ensure


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    if set(entry["state"].keys()) != keys_before:
        _save(session_id, entry)
    if _advance_jobs(entry["state"]):
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    _redact_internal(state)
    _merge_vmware_clients(state, session_id)
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_commvault_clients
        sync_commvault_clients(session_id, state.get("clients") or [])
    except Exception:
        pass
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
        # Carried until the job completes, then turned into a recovery point.
        # `corrupt`/`incomplete` let a scenario seed a backup that will not
        # survive restore verification.
        job["pending_point"] = {
            "client": client_name,
            "policy": policy_name,
            "corrupt": bool(payload.get("corrupt")),
            "incomplete": bool(payload.get("incomplete")),
        }
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
        copy_name = payload.get("copy") or "primary"
        before_ts = payload.get("before_ts")
        if before_ts is not None:
            try:
                before_ts = float(before_ts)
            except (TypeError, ValueError):
                return {"ok": False, "error": "before_ts must be a unix timestamp"}
        point, err = _select_recovery_point(
            state, client_name,
            point_id=payload.get("recovery_point") or "",
            job_id=payload.get("from_job_id"),
            before_ts=before_ts,
            copy_name=copy_name,
        )
        if not point:
            # Refusing to launch is itself a real outcome: there is nothing on
            # media to restore from, so no job may claim success.
            _event(state, f"Restore for {client_name} rejected: {err}", "error")
            _save(session_id, entry)
            return {"ok": False, "error": err}

        job = _make_job(state, kind="restore", subclient=f"default ({client_name})",
                         policy=point.get("policy") or payload.get("policy") or "Gold-Retention-30d",
                         job_type="Restore", will_fail=False)
        job["recovery_point"] = point["id"]
        job["point_in_time"] = point.get("created")
        job["copy"] = copy_name
        materialised = _materialise(state, point)
        job["materialised"] = materialised
        state.setdefault("jobs", []).insert(0, job)
        _event(state, f"Restore job {job['id']} started for {client_name} from "
                      f"{point['id']} ({point.get('created')}, copy {copy_name})", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import commvault_bridge
            commvault_bridge.record_restore_files(
                str(session_id), sorted(materialised), client=client_name,
                job_id=job["id"], contents=materialised,
            )
        except Exception:
            # A bridge that did not accept the write means the guest never got
            # the files; leave a breadcrumb rather than swallowing it silently.
            _event(state, f"Restore job {job['id']} could not stage files to the guest", "warning")
        return {"ok": True, "message": f"Restore job started from {point['id']}",
                "job_id": job["id"], "recovery_point": point["id"],
                "point_in_time": point.get("created")}

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

    if action == "set_retention":
        name = payload.get("name") or ""
        policy = next((p for p in state.get("storage_policies", []) if p.get("name") == name or p.get("id") == name), None)
        if not policy:
            return {"ok": False, "error": f"Storage policy '{name}' not found"}
        days = int(payload.get("retention_days") or policy.get("retention_days") or 30)
        policy["retention_days"] = days
        _event(state, f"Retention for {policy['name']} set to {days} days", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Retention updated"}

    if action == "kill_job":
        job_id = int(payload.get("job_id") or 0)
        job = next((j for j in state.get("jobs", []) if int(j.get("id", 0)) == job_id), None)
        if not job:
            return {"ok": False, "error": f"Job {job_id} not found"}
        if job.get("status") in ("completed", "failed", "killed"):
            return {"ok": False, "error": "Job already finished"}
        job["status"] = "killed"
        job["progress"] = job.get("progress") or 0
        _event(state, f"Job {job_id} killed by operator", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Job killed"}

    if action == "enable_schedule":
        name = payload.get("name") or broken.get("schedule_disabled") or ""
        sch = next((s for s in state.get("schedules", []) if s.get("name") == name or s.get("id") == name), None)
        if not sch:
            return {"ok": False, "error": f"Schedule '{name}' not found"}
        sch["enabled"] = True
        if broken.get("schedule_disabled") == sch["name"]:
            broken.pop("schedule_disabled", None)
        _event(state, f"Schedule {sch['name']} enabled", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Schedule enabled"}

    if action == "create_schedule":
        name = (payload.get("name") or "New-Schedule").strip()
        sch_id = f"sch{len(state.get('schedules', [])) + 1}"
        state.setdefault("schedules", []).append({
            "id": sch_id, "name": name,
            "client": payload.get("client") or "web01",
            "policy": payload.get("policy") or "Gold-Retention-30d",
            "type": payload.get("type") or "Incremental",
            "cron": payload.get("cron") or "0 1 * * *",
            "enabled": True,
        })
        _event(state, f"Schedule {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Schedule created", "id": sch_id}

    if action == "run_aux_copy":
        name = payload.get("name") or broken.get("needs_aux_copy") or "Gold-to-Cloud"
        aux = next((a for a in state.get("aux_copies", []) if a.get("name") == name or a.get("id") == name), None)
        if not aux:
            return {"ok": False, "error": f"Aux copy '{name}' not found"}
        aux["status"] = "running"
        job = _make_job(state, kind="aux_copy", subclient=aux["name"], policy=aux.get("source_policy") or "",
                         job_type="AuxCopy", will_fail=False)
        state.setdefault("jobs", []).insert(0, job)
        # An aux copy is what puts recovery points on the secondary copy, so it
        # is the reason a restore from that copy can succeed at all.
        copy_label = aux.get("dest_library") or aux["name"]
        copied = 0
        for point in state.get("recovery_points", []):
            if point.get("policy") != aux.get("source_policy"):
                continue
            copies = point.setdefault("copies", ["primary"])
            if copy_label not in copies:
                copies.append(copy_label)
                copied += 1
        aux["copied_points"] = copied
        _event(state, f"Aux copy {aux['name']} placed {copied} recovery point(s) on {copy_label}", "info")
        if broken.get("needs_aux_copy") == aux["name"]:
            broken.pop("needs_aux_copy", None)
        _event(state, f"Auxiliary copy {aux['name']} started (job {job['id']})", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Aux copy started", "job_id": job["id"]}

    if action == "add_media_agent":
        name = (payload.get("name") or "MA-new").strip()
        state.setdefault("media_agents", []).append({
            "name": name, "status": "online", "os": payload.get("os") or "Linux",
            "streams": int(payload.get("streams") or 8), "free_space_gb": int(payload.get("free_space_gb") or 500),
        })
        _event(state, f"Media agent {name} registered", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Media agent added"}

    if action == "create_library":
        name = (payload.get("name") or "DiskLib-new").strip()
        state.setdefault("libraries", []).append({
            "name": name, "type": payload.get("type") or "Disk",
            "capacity_gb": int(payload.get("capacity_gb") or 1000), "used_gb": 0,
            "media_agent": payload.get("media_agent") or "MA-01",
        })
        _event(state, f"Library {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Library created"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or action, "success")
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# Per-key grader feedback. The broken dict stores bare targets (a client name,
# a policy name) and sometimes just True, so the value cannot be echoed the way
# azure_engine echoes its human-readable reasons.
_BROKEN_REASONS: dict[str, str] = {
    "overdue_client": "client {target} is still overdue for a backup — run one to completion",
    "needs_restore": "a restore for {target} has not been run to completion yet",
    "policy_disabled": "storage policy {target} is still disabled — enable it",
    "missing_subclient": "the subclient for {target} has not been created yet",
    "missing_client": "the new client has not been registered yet",
    "schedule_disabled": "schedule {target} is still disabled — enable it",
    "needs_aux_copy": "aux copy {target} has not been run yet",
}


def _describe_broken(broken: dict) -> str:
    """Name every outstanding objective, not just the first.

    Presets currently seed a single key each, but joining rather than taking
    next(iter(...)) means a future multi-key preset cannot silently hide half
    the remaining work.
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
        restores = [j for j in state.get("jobs", []) if j.get("kind") == "restore"]
        verified = next((j for j in restores
                         if j.get("status") == "completed" and j.get("verified") is True), None)
        if verified:
            return True, (f"Restore job {verified['id']} verified against "
                          f"{verified.get('recovery_point')}: {verified.get('verify_message')}")
        # Fail CLOSED, and say WHY: a restore that ran but did not verify is the
        # exact silent pass this grader used to accept.
        failed = next((j for j in restores if j.get("verified") is False), None)
        if failed:
            return False, (f"Restore job {failed['id']} did not verify: "
                           f"{failed.get('verify_message') or 'verification failed'}")
        if restores:
            return False, "Restore job has not finished verifying yet"
        return False, "Run a restore job to completion"
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
        return False, f"Commvault lab not complete: {_describe_broken(broken)}"
    ok = any(j.get("kind") == "backup" and j.get("status") == "completed" for j in state.get("jobs", []))
    if not ok:
        return False, "Run a backup job to completion"
    return True, "Commvault lab objectives met"
