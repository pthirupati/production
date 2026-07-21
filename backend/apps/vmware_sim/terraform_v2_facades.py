"""Terraform Cloud V2 facades — workspaces, runs, locks, variables.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "tfc": {
            "org": {"name": "fixitlab-training", "id": "org-fixitlab"},
            "workspaces": [
                {"id": "ws-1", "name": "prod-vpc", "project": "Network", "status": "Applied", "runs": 42, "lastRun": "Plan applied", "updatedAt": _now(), "locked": False},
                {"id": "ws-2", "name": "web-tier-asg", "project": "Compute", "status": "Errored", "runs": 18, "lastRun": "Apply errored", "updatedAt": _now(), "locked": False},
                {"id": "ws-lab", "name": "lab-workspace", "project": "Training", "status": "Planned", "runs": 3, "lastRun": "Plan queued", "updatedAt": _now(), "locked": False},
            ],
            "runs": [
                {"id": "run-101", "workspace": "lab-workspace", "status": "Applied", "triggeredBy": "lab-user", "planCost": "$0.00", "time": "4m 12s", "createdAt": _now()},
                {"id": "run-100", "workspace": "web-tier-asg", "status": "Errored", "triggeredBy": "ci-bot", "planCost": "$12.40", "time": "2m 01s", "createdAt": _now()},
            ],
            "variables": [
                {"id": "v1", "workspace": "lab-workspace", "key": "aws_region", "value": "ap-south-1", "category": "terraform", "sensitive": False},
                {"id": "v2", "workspace": "lab-workspace", "key": "instance_type", "value": "t3.medium", "category": "terraform", "sensitive": False},
            ],
            "modules": [
                {"id": "m1", "name": "vpc", "provider": "hashicorp/aws", "version": "5.1.2"},
                {"id": "m2", "name": "eks", "provider": "hashicorp/aws", "version": "20.8.0"},
            ],
            "teams": [
                {"id": "t1", "name": "platform-admins", "access": "admin", "members": 4},
                {"id": "t2", "name": "developers", "access": "write", "members": 18},
            ],
        },
    }


def ensure_v2(state: dict) -> None:
    seed = seed_v2()
    if "tfc" not in state or state.get("tfc") is None:
        state["tfc"] = seed["tfc"]
        return
    tfc = state["tfc"]
    for key, value in seed["tfc"].items():
        if key not in tfc or tfc.get(key) is None:
            tfc[key] = value


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)
    tfc = state["tfc"]

    if action == "tfc_create_workspace":
        name = (payload.get("name") or f"ws-{len(tfc.get('workspaces') or []) + 1}").strip()
        if any(w.get("name") == name for w in tfc.get("workspaces") or []):
            return {"ok": False, "error": f"Workspace '{name}' already exists"}
        row = {
            "id": f"ws-{len(tfc.get('workspaces') or []) + 1}",
            "name": name,
            "project": payload.get("project") or "Training",
            "status": "No Changes",
            "runs": 0,
            "lastRun": "—",
            "updatedAt": _now(),
            "locked": False,
        }
        tfc.setdefault("workspaces", []).insert(0, row)
        return {"ok": True, "message": f"Workspace {name} created", "workspace": row}

    if action == "tfc_queue_run":
        ws_name = payload.get("workspace") or payload.get("name") or "lab-workspace"
        ws = next((w for w in tfc.get("workspaces") or [] if w.get("name") == ws_name or w.get("id") == ws_name), None)
        if not ws and (tfc.get("workspaces") or []):
            ws = tfc["workspaces"][0]
        if not ws:
            return {"ok": False, "error": "Workspace not found"}
        if ws.get("locked"):
            return {"ok": False, "error": "Workspace is locked"}
        run_id = f"run-{101 + len(tfc.get('runs') or [])}"
        status = "Planned" if not payload.get("apply") else "Applied"
        row = {
            "id": run_id,
            "workspace": ws["name"],
            "status": status,
            "triggeredBy": payload.get("triggeredBy") or "lab-user",
            "planCost": payload.get("planCost") or "$0.00",
            "time": "1m 20s",
            "createdAt": _now(),
        }
        tfc.setdefault("runs", []).insert(0, row)
        ws["runs"] = int(ws.get("runs") or 0) + 1
        ws["status"] = status
        ws["lastRun"] = f"Run {status.lower()}"
        ws["updatedAt"] = _now()
        return {"ok": True, "message": f"Queued run {run_id}", "run": row, "workspace": ws}

    if action == "tfc_apply_run":
        run_id = payload.get("run_id") or payload.get("id")
        run = next((r for r in tfc.get("runs") or [] if r.get("id") == run_id), None)
        if not run and (tfc.get("runs") or []):
            run = next((r for r in tfc["runs"] if r.get("status") == "Planned"), tfc["runs"][0])
        if not run:
            return {"ok": False, "error": "Run not found"}
        run["status"] = "Applied"
        ws = next((w for w in tfc.get("workspaces") or [] if w.get("name") == run.get("workspace")), None)
        if ws:
            ws["status"] = "Applied"
            ws["lastRun"] = "Applied successfully"
            ws["updatedAt"] = _now()
        return {"ok": True, "message": f"Applied {run['id']}", "run": run}

    if action == "tfc_lock_workspace":
        ws_name = payload.get("workspace") or payload.get("name") or ""
        ws = next((w for w in tfc.get("workspaces") or [] if w.get("name") == ws_name or w.get("id") == ws_name), None)
        if not ws:
            return {"ok": False, "error": "Workspace not found"}
        ws["locked"] = bool(payload.get("locked", True))
        return {"ok": True, "message": f"{'Locked' if ws['locked'] else 'Unlocked'} {ws['name']}", "workspace": ws}

    if action == "tfc_set_variable":
        ws_name = payload.get("workspace") or "lab-workspace"
        key = (payload.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "Variable key required"}
        vars_ = tfc.setdefault("variables", [])
        existing = next((v for v in vars_ if v.get("key") == key and v.get("workspace") == ws_name), None)
        if existing:
            existing["value"] = payload.get("value") or existing.get("value")
            existing["sensitive"] = bool(payload.get("sensitive", existing.get("sensitive")))
            row = existing
        else:
            row = {
                "id": f"v{len(vars_) + 1}",
                "workspace": ws_name,
                "key": key,
                "value": payload.get("value") or "",
                "category": payload.get("category") or "terraform",
                "sensitive": bool(payload.get("sensitive")),
            }
            vars_.append(row)
        return {"ok": True, "message": f"Set variable {key}", "variable": row}

    return None
