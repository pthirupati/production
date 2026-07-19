"""In-memory CI/CD pipeline simulator + server-side grader for training labs.

The DevOps / CI-CD track ships a rich *client-side* pipeline player
(frontend/src/components/devops/*) that streams a GitLab/GitHub-Actions-style
run in the browser. Because that player lives entirely in the browser, the
audit found the CI/CD track could not be graded server-side: there was no
engine holding authoritative pipeline state and no validator. A learner could
"fix" the pipeline visually and the backend had nothing to check.

This module closes that gap. It mirrors the same fault domain the frontend
models (bad image tag, missing `needs`/dependency edge, an unapproved manual
gate, a failing job/step) as authoritative, cache-persisted state and derives
the pipeline outcome from that state. Grading is fail-CLOSED: a freshly seeded
scenario always has an unresolved fault, so `validate_cicd_lab` returns
`(False, reason)` until the learner applies the specific fix, after which the
pipeline goes green and it returns `(True, ...)`.

State lives in the Django cache (Redis in production) for multi-worker safety,
exactly like the AWX / Terraform / monitoring engines. It is additionally
mirrored into `LabSession.simulation_snapshot["cicd"]` so grading survives a
worker restart even if the cache is cold — the mirror is namespaced so it never
collides with the RHEL engine's `version==1` restore payload.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL matching the sibling simulators


def _session_key(session_id: str) -> str:
    return f"cicd_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is not None:
        return json.loads(data) if isinstance(data, str) else data
    # Cache-cold fallback: recover the graded state from the DB mirror so a
    # worker restart never silently loses a learner's fix (which would flip a
    # passing lab back to failing — a fail-closed regression in the wrong
    # direction, but still a bad experience).
    return _load_from_snapshot(session_id)


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)
    _mirror_to_snapshot(session_id, entry)


def _load_from_snapshot(session_id: str) -> dict | None:
    try:
        from apps.labs.models import LabSession

        snap = (
            LabSession.objects.filter(pk=session_id)
            .values_list("simulation_snapshot", flat=True)
            .first()
        )
        if isinstance(snap, dict):
            entry = snap.get("cicd")
            if isinstance(entry, dict) and entry.get("state"):
                return copy.deepcopy(entry)
    except Exception:  # pragma: no cover - defensive (no DB row / migration)
        return None
    return None


def _mirror_to_snapshot(session_id: str, entry: dict) -> None:
    """Persist a copy of the graded pipeline state into the LabSession row.

    Namespaced under the ``cicd`` key so it coexists with the RHEL engine's
    ``version==1`` snapshot without either clobbering the other.
    """
    try:
        from apps.labs.models import LabSession

        row = LabSession.objects.filter(pk=session_id).only("id", "simulation_snapshot").first()
        if not row:
            return
        snap = row.simulation_snapshot if isinstance(row.simulation_snapshot, dict) else {}
        snap = dict(snap)
        snap["cicd"] = json.loads(json.dumps(entry, default=str))
        LabSession.objects.filter(pk=session_id).update(simulation_snapshot=snap)
    except Exception:  # pragma: no cover - defensive (unsaved session in tests)
        pass


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Pipeline model
#
# A pipeline is an ordered list of stages, each with jobs. A job carries:
#   id, name, stage, image, needs[] (upstream job ids it depends on),
#   manual (bool → requires approval before it can run), approved (bool),
#   script[] (steps), and a `_fault` marker describing what the scenario broke.
# The *outcome* of a job/pipeline is DERIVED from that state (never stored as a
# free-standing "green/red" the learner can flip directly), so grading reflects
# the real configuration, not a UI toggle.
# ---------------------------------------------------------------------------

_VALID_IMAGES = {
    "node:20", "node:18", "python:3.12", "python:3.11", "golang:1.22",
    "docker:24", "docker:25", "alpine:3.19", "ubuntu:22.04", "maven:3.9-eclipse-temurin-21",
    "registry.fixitlab.local/ci/base:1.4.0",
}


def _base_state() -> dict:
    """A healthy 3-stage pipeline: build → test → deploy."""
    return {
        "provider": "gitlab",
        "project": "fixitlab/app",
        "branch": "main",
        "commit": {"sha": "a1b2c3d", "message": "chore: pipeline tune-up", "author": "labuser"},
        "stages": ["build", "test", "deploy"],
        "jobs": [
            {
                "id": "build",
                "name": "build",
                "stage": "build",
                "image": "node:20",
                "needs": [],
                "manual": False,
                "approved": True,
                "script": ["npm ci", "npm run build"],
                "_fault": None,
            },
            {
                "id": "unit-test",
                "name": "unit-test",
                "stage": "test",
                "image": "node:20",
                "needs": ["build"],
                "manual": False,
                "approved": True,
                "script": ["npm test"],
                "_fault": None,
            },
            {
                "id": "deploy-prod",
                "name": "deploy-prod",
                "stage": "deploy",
                "image": "docker:24",
                "needs": ["unit-test"],
                "manual": True,
                "approved": True,
                "environment": "production",
                "script": ["docker build -t app .", "kubectl rollout restart deploy/app"],
                "_fault": None,
            },
        ],
        "goal": {
            "title": "Get the pipeline green",
            "objective": "Diagnose and fix the broken CI/CD pipeline so every stage passes.",
        },
        "fault": {"kind": None, "job": None, "summary": ""},
        "last_run": None,
        "events": [],
    }


# ---------------------------------------------------------------------------
# Scenario presets — each plants exactly one fault the learner must fix.
# ---------------------------------------------------------------------------

def _job(state: dict, job_id: str) -> dict | None:
    return next((j for j in state.get("jobs", []) if j.get("id") == job_id), None)


def _apply_preset(state: dict, slug: str) -> None:
    s = (slug or "").lower()
    fault = state["fault"]

    if "image" in s or "bad-image" in s or "registry" in s or "tag" in s:
        # Bad container image / tag → the job can never pull its runner image.
        job = _job(state, "build")
        if job:
            job["image"] = "node:18-broken"  # non-existent tag
            job["_fault"] = "bad_image"
        fault.update({
            "kind": "bad_image", "job": "build",
            "summary": "The build job references an image tag that does not exist in the registry "
                       "(ErrImagePull). Point it at a valid image tag.",
        })
        state["goal"] = {"title": "Fix the image tag",
                         "objective": "The build job pulls a non-existent image. Set a valid image tag."}
    elif "needs" in s or "dependency" in s or "dag" in s or "edge" in s or "order" in s:
        # Missing `needs` edge → deploy runs before test, races, and fails.
        job = _job(state, "deploy-prod")
        if job:
            job["needs"] = []  # dropped the dependency on unit-test
            job["_fault"] = "missing_needs"
        fault.update({
            "kind": "missing_needs", "job": "deploy-prod",
            "summary": "deploy-prod has no `needs`/dependency on unit-test, so it can run before "
                       "tests pass. Restore the dependency edge.",
        })
        state["goal"] = {"title": "Fix the pipeline DAG",
                         "objective": "deploy-prod is missing its dependency on unit-test. Add the needs edge."}
    elif "gate" in s or "approval" in s or "approve" in s or "manual" in s:
        # Unapproved manual gate → deploy is stuck awaiting approval.
        job = _job(state, "deploy-prod")
        if job:
            job["manual"] = True
            job["approved"] = False
            job["_fault"] = "unapproved_gate"
        fault.update({
            "kind": "unapproved_gate", "job": "deploy-prod",
            "summary": "deploy-prod is a manual gate that has not been approved, so the pipeline "
                       "is blocked awaiting approval. Approve the deploy.",
        })
        state["goal"] = {"title": "Approve the deploy gate",
                         "objective": "The deploy job is a manual gate awaiting approval. Approve it to release."}
    else:
        # Default / "failing-job" / "test-fail" — a job's script fails.
        job = _job(state, "unit-test")
        if job:
            job["_fault"] = "failing_job"
            job["script"] = ["npm test  # exits 1: 2 tests failing"]
        fault.update({
            "kind": "failing_job", "job": "unit-test",
            "summary": "The unit-test job is failing (exit code 1). Fix the job so its script passes.",
        })
        state["goal"] = {"title": "Fix the failing job",
                         "objective": "The unit-test job fails. Repair the job so the pipeline goes green."}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


# Public alias matching the sibling engines' `_ensure` dispatch convention.
_ensure_session = _ensure


# ---------------------------------------------------------------------------
# Outcome derivation — the single source of truth for grading and the UI.
# ---------------------------------------------------------------------------

def _job_outcome(state: dict, job: dict) -> tuple[str, str]:
    """Return (status, detail) for one job derived purely from its state.

    status ∈ {success, failed, blocked, skipped}. A job is `skipped` when any
    upstream `needs` job did not succeed.
    """
    fault = job.get("_fault")
    if fault == "bad_image" and job.get("image") not in _VALID_IMAGES:
        return "failed", f"ErrImagePull: image '{job.get('image')}' not found"
    if fault == "failing_job":
        return "failed", "job script exited 1"
    if job.get("manual") and not job.get("approved"):
        return "blocked", "awaiting manual approval"
    # An upstream that never ran (missing needs edge) is a config fault caught
    # separately; here we only skip when a declared need did not succeed.
    for dep_id in job.get("needs") or []:
        dep = _job(state, dep_id)
        if not dep:
            continue
        dep_status, _ = _job_outcome(state, dep)
        if dep_status != "success":
            return "skipped", f"upstream {dep_id} is {dep_status}"
    return "success", "passed"


def _pipeline_outcome(state: dict) -> dict:
    """Compute the whole-pipeline result. Green only when every job succeeds
    AND no structural fault (e.g. a missing dependency edge) remains."""
    jobs_out = []
    all_green = True
    for job in state.get("jobs", []):
        status, detail = _job_outcome(state, job)
        if status != "success":
            all_green = False
        jobs_out.append({
            "id": job.get("id"), "name": job.get("name"), "stage": job.get("stage"),
            "status": status, "detail": detail, "image": job.get("image"),
            "needs": job.get("needs") or [], "manual": bool(job.get("manual")),
            "approved": bool(job.get("approved")),
        })

    # Structural fault: the deploy job must depend (directly or transitively) on
    # the test job. If the scenario dropped that edge, the pipeline is unsafe
    # even if every job happens to be individually green.
    structural_ok, structural_reason = _dag_is_safe(state)
    if not structural_ok:
        all_green = False

    return {
        "status": "success" if all_green else "failed",
        "jobs": jobs_out,
        "structural_ok": structural_ok,
        "structural_reason": structural_reason,
    }


def _dag_is_safe(state: dict) -> tuple[bool, str]:
    """A deploy job must transitively depend on the test job(s)."""
    deploy_jobs = [j for j in state.get("jobs", []) if (j.get("stage") == "deploy")]
    test_ids = {j.get("id") for j in state.get("jobs", []) if j.get("stage") == "test"}
    if not deploy_jobs or not test_ids:
        return True, "no deploy/test coupling required"

    def reaches_test(job_id: str, seen: set) -> bool:
        if job_id in seen:
            return False
        seen.add(job_id)
        job = _job(state, job_id)
        if not job:
            return False
        for dep in job.get("needs") or []:
            if dep in test_ids or reaches_test(dep, seen):
                return True
        return False

    for dj in deploy_jobs:
        if not reaches_test(dj.get("id"), set()):
            return False, f"{dj.get('id')} does not depend on the test stage"
    return True, "deploy depends on tests"


# ---------------------------------------------------------------------------
# Engine contract
# ---------------------------------------------------------------------------

def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    outcome = _pipeline_outcome(state)
    summary = {
        "pipeline_status": outcome["status"],
        "jobs_total": len(outcome["jobs"]),
        "jobs_failed": sum(1 for j in outcome["jobs"] if j["status"] in ("failed", "blocked", "skipped")),
        "fault_kind": state.get("fault", {}).get("kind"),
        "fault_summary": state.get("fault", {}).get("summary", ""),
        "structural_ok": outcome["structural_ok"],
    }
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "pipeline": {
            "provider": state.get("provider"),
            "project": state.get("project"),
            "branch": state.get("branch"),
            "commit": state.get("commit"),
            "stages": state.get("stages"),
        },
        "jobs": state.get("jobs"),
        "outcome": outcome,
        "goal": state.get("goal", {}),
        "fault": state.get("fault", {}),
        "last_run": state.get("last_run"),
        "events": state.get("events", []),
        "summary": summary,
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# Alias matching the terminate_lab convention used by some sibling engines.
clear_session = drop_session


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "CI/CD session not found"}
    state = entry["state"]
    fault = state.setdefault("fault", {"kind": None, "job": None, "summary": ""})

    def _clear_fault_if(job_id: str, kinds: tuple) -> None:
        job = _job(state, job_id)
        if job and job.get("_fault") in kinds:
            job["_fault"] = None
        if fault.get("job") == job_id and fault.get("kind") in kinds:
            fault["kind"] = None
            fault["summary"] = ""

    if action == "set_image":
        job_id = (payload.get("job") or payload.get("job_id") or "").strip()
        image = (payload.get("image") or "").strip()
        job = _job(state, job_id)
        if not job:
            return {"ok": False, "error": f"job '{job_id}' not found"}
        if not image:
            return {"ok": False, "error": "image is required"}
        job["image"] = image
        if image in _VALID_IMAGES and job.get("_fault") == "bad_image":
            job["_fault"] = None
            _clear_fault_if(job_id, ("bad_image",))
        state["events"].insert(0, {"time": _now_iso(), "message": f"Set {job_id} image to {image}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Image for {job_id} set to {image}"}

    if action == "add_needs" or action == "set_needs":
        job_id = (payload.get("job") or payload.get("job_id") or "").strip()
        job = _job(state, job_id)
        if not job:
            return {"ok": False, "error": f"job '{job_id}' not found"}
        if action == "set_needs":
            needs = payload.get("needs") or []
            if not isinstance(needs, list):
                return {"ok": False, "error": "needs must be a list of job ids"}
            job["needs"] = [str(n) for n in needs]
        else:
            dep = (payload.get("depends_on") or payload.get("needs") or "").strip()
            if not dep:
                return {"ok": False, "error": "depends_on (upstream job id) is required"}
            if not _job(state, dep):
                return {"ok": False, "error": f"upstream job '{dep}' not found"}
            if dep not in (job.get("needs") or []):
                job.setdefault("needs", []).append(dep)
        if job.get("_fault") == "missing_needs":
            job["_fault"] = None
        _clear_fault_if(job_id, ("missing_needs",))
        state["events"].insert(0, {"time": _now_iso(), "message": f"Updated needs for {job_id}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Dependencies for {job_id} updated", "needs": job.get("needs")}

    if action == "approve_job" or action == "approve":
        job_id = (payload.get("job") or payload.get("job_id") or "").strip()
        job = _job(state, job_id)
        if not job:
            return {"ok": False, "error": f"job '{job_id}' not found"}
        if not job.get("manual"):
            return {"ok": False, "error": f"job '{job_id}' is not a manual gate"}
        job["approved"] = True
        if job.get("_fault") == "unapproved_gate":
            job["_fault"] = None
        _clear_fault_if(job_id, ("unapproved_gate",))
        state["events"].insert(0, {"time": _now_iso(), "message": f"Approved manual gate {job_id}", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Approved {job_id}"}

    if action == "fix_job":
        # Repair a failing job's script so it passes.
        job_id = (payload.get("job") or payload.get("job_id") or "").strip()
        job = _job(state, job_id)
        if not job:
            return {"ok": False, "error": f"job '{job_id}' not found"}
        if "script" in payload and isinstance(payload["script"], list):
            job["script"] = [str(x) for x in payload["script"]]
        if job.get("_fault") == "failing_job":
            job["_fault"] = None
        _clear_fault_if(job_id, ("failing_job",))
        state["events"].insert(0, {"time": _now_iso(), "message": f"Repaired job {job_id}", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Job {job_id} repaired"}

    if action == "run_pipeline" or action == "run":
        outcome = _pipeline_outcome(state)
        state["last_run"] = {
            "time": _now_iso(),
            "status": outcome["status"],
            "jobs": outcome["jobs"],
        }
        sev = "success" if outcome["status"] == "success" else "error"
        state["events"].insert(0, {"time": _now_iso(),
                                   "message": f"Pipeline run finished: {outcome['status']}",
                                   "severity": sev})
        _save(session_id, entry)
        return {"ok": True, "message": f"Pipeline {outcome['status']}", "outcome": outcome}

    if action == "update_job":
        # Generic editor: apply any of image/needs/approved/script in one call.
        job_id = (payload.get("job") or payload.get("job_id") or "").strip()
        job = _job(state, job_id)
        if not job:
            return {"ok": False, "error": f"job '{job_id}' not found"}
        if "image" in payload and payload["image"]:
            job["image"] = str(payload["image"]).strip()
        if "needs" in payload and isinstance(payload["needs"], list):
            job["needs"] = [str(n) for n in payload["needs"]]
        if "approved" in payload:
            job["approved"] = bool(payload["approved"])
        if "script" in payload and isinstance(payload["script"], list):
            job["script"] = [str(x) for x in payload["script"]]
        # Auto-clear any fault that the edit resolves.
        status, _ = _job_outcome(state, job)
        if job.get("_fault") and status == "success" and _dag_is_safe(state)[0]:
            resolved_kind = job.get("_fault")
            job["_fault"] = None
            if fault.get("job") == job_id and fault.get("kind") == resolved_kind:
                fault["kind"] = None
                fault["summary"] = ""
        state["events"].insert(0, {"time": _now_iso(), "message": f"Updated job {job_id}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Job {job_id} updated"}

    return {"ok": False, "error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Grader — fail-CLOSED. Fails on a freshly-seeded (broken) scenario; passes only
# once the planted fault is fixed AND the pipeline derives green.
# ---------------------------------------------------------------------------

def validate_cicd_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        # No session state at all → cannot confirm a fix. Fail closed.
        return False, "No CI/CD pipeline session"
    state = entry.get("state") or {}
    fault = state.get("fault") or {}

    # 1) The specific planted fault must be cleared.
    if fault.get("kind"):
        return False, fault.get("summary") or f"Unresolved pipeline fault: {fault.get('kind')}"

    # 2) No job may still carry a fault marker (defensive against partial fixes).
    for job in state.get("jobs", []):
        if job.get("_fault"):
            return False, f"Job {job.get('id')} still broken ({job.get('_fault')})"

    # 3) The derived pipeline outcome must be green.
    outcome = _pipeline_outcome(state)
    if not outcome.get("structural_ok", True):
        return False, outcome.get("structural_reason") or "Pipeline DAG is unsafe"
    if outcome.get("status") != "success":
        stuck = next((j for j in outcome["jobs"] if j["status"] != "success"), None)
        if stuck:
            return False, f"Job {stuck['id']} is {stuck['status']}: {stuck['detail']}"
        return False, "Pipeline is not green"

    return True, "CI/CD pipeline is green — validation passed"
