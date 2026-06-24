"""In-memory Terraform + AWS CLI simulator for IaC training labs."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"terraform_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _base_state() -> dict:
    return {
        "terraform": {
            "initialized": False,
            "workspace": "default",
            "last_plan": None,
            "last_apply": None,
            "resources": [],
            "drift_detected": True,
        },
        "aws": {
            "profile": "training",
            "region": "ap-south-1",
            "caller_identity": "arn:aws:iam::123456789012:user/training",
            "resources": [
                {"type": "aws_s3_bucket", "id": "app-logs-prod", "status": "ok"},
                {"type": "aws_instance", "id": "i-0abc123", "status": "running"},
            ],
        },
        "goal": {"title": "Fix IaC", "objective": "Run terraform init, plan, and apply to reconcile drift."},
        "broken": {"drift": True, "plan_required": True},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "lock" in slug:
        state["goal"] = {"title": "Unlock state", "objective": "Force-unlock the stale DynamoDB state lock and re-run plan/apply."}
        state["broken"] = {"stale_lock": True, "plan_required": True}
        state["terraform"]["initialized"] = True
    elif "aws" in slug or "s3" in slug:
        state["goal"] = {"title": "AWS resource fix", "objective": "Use aws cli to verify and fix the S3 bucket policy."}
    if "vmware" in slug:
        state["goal"]["objective"] = "Apply Terraform to clone a VM from template in VMware."


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": copy.deepcopy(entry["state"]),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Terraform session not found"}
    state = entry["state"]
    tf = state["terraform"]
    broken = state.get("broken") or {}

    if action == "terraform_init":
        tf["initialized"] = True
        state["events"].insert(0, {"time": _now_iso(), "message": "Terraform initialized", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "output": "Terraform has been successfully initialized!"}

    if action == "terraform_plan":
        if not tf.get("initialized"):
            return {"ok": False, "error": "Run terraform init first"}
        plan = {
            "add": 1, "change": 2, "destroy": 0,
            "summary": "Plan: 1 to add, 2 to change, 0 to destroy.",
        }
        tf["last_plan"] = plan
        broken["plan_required"] = False
        state["events"].insert(0, {"time": _now_iso(), "message": plan["summary"], "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "plan": plan}

    if action == "terraform_apply":
        if not tf.get("last_plan"):
            return {"ok": False, "error": "Run terraform plan first"}
        tf["last_apply"] = _now_iso()
        tf["drift_detected"] = False
        broken.pop("drift", None)
        broken.pop("stale_lock", None)
        tf["resources"] = [
            {"type": "aws_instance", "name": "web", "status": "applied"},
            {"type": "aws_security_group", "name": "web-sg", "status": "applied"},
        ]
        state["events"].insert(0, {"time": _now_iso(), "message": "Apply complete! Resources: 3 added, 0 changed, 0 destroyed.", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Apply complete"}

    if action == "force_unlock":
        broken.pop("stale_lock", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "State lock force-unlocked", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Lock released"}

    if action == "aws_cli":
        cmd = (payload.get("command") or "").strip()
        if cmd.startswith("aws sts get-caller-identity"):
            return {"ok": True, "output": json.dumps({"Account": "123456789012", "Arn": state["aws"]["caller_identity"]})}
        if "s3 ls" in cmd:
            return {"ok": True, "output": "2024-01-15 10:00:00 app-logs-prod"}
        if "ec2 describe-instances" in cmd:
            return {"ok": True, "output": "i-0abc123  running  t3.medium"}
        return {"ok": True, "output": f"(simulated) {cmd}"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_terraform_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No Terraform session"
    broken = entry["state"].get("broken") or {}
    tf = entry["state"].get("terraform") or {}
    if broken:
        return False, "Terraform environment still has unresolved issues"
    if not tf.get("last_apply") and not broken:
        if tf.get("drift_detected"):
            return False, "Run terraform plan and apply to reconcile drift"
    return True, "Terraform lab objectives met"
