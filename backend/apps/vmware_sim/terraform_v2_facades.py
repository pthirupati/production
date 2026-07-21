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
            "agent_pools": [
                {"id": "ap1", "name": "default-pool", "agents": 3, "status": "healthy"},
                {"id": "ap2", "name": "prod-agents", "agents": 5, "status": "healthy"},
            ],
            "states": [
                {"id": "st-1", "workspace": "lab-workspace", "serial": 42, "createdAt": _now(), "createdBy": "lab-user", "resources": 18},
                {"id": "st-2", "workspace": "lab-workspace", "serial": 41, "createdAt": _now(), "createdBy": "ci-bot", "resources": 17},
            ],
            "locks": [],
            "ws_notifications": [
                {"id": "wn1", "workspace": "lab-workspace", "name": "Slack #infra", "triggers": "Errored runs", "status": "enabled"},
                {"id": "wn2", "workspace": "lab-workspace", "name": "Email platform", "triggers": "Needs attention", "status": "enabled"},
            ],
            "team_access": [
                {"team": "platform-admins", "permission": "Admin", "inherited": False, "workspace": "lab-workspace"},
                {"team": "developers", "permission": "Write", "inherited": True, "workspace": "lab-workspace"},
            ],
            "health": [
                {"check": "VCS connection", "status": "passing", "detail": "GitHub connected"},
                {"check": "Remote state", "status": "passing", "detail": "S3 backend reachable"},
                {"check": "Variables", "status": "warning", "detail": "1 sensitive var unused"},
                {"check": "Run queue", "status": "passing", "detail": "0 queued runs"},
            ],
            "org_settings": {
                "general": [
                    ["Organization name", "fixitlab-training"],
                    ["Default execution mode", "Remote"],
                    ["Terraform version", "1.7.5"],
                    ["Cost estimation", "Enabled"],
                ],
                "sso": [
                    ["SAML enabled", "Yes"],
                    ["IdP", "Okta"],
                    ["Enforce SSO", "Optional"],
                ],
                "vcs": [
                    {"provider": "GitHub", "org": "fixitlab", "status": "connected", "repos": 12},
                    {"provider": "GitLab", "org": "—", "status": "not connected", "repos": 0},
                ],
                "tokens": [
                    {"name": "ci-bot", "created": "2026-01-15", "lastUsed": "2026-06-24", "scopes": "plan, apply"},
                    {"name": "local-dev", "created": "2026-03-01", "lastUsed": "2026-06-20", "scopes": "read"},
                ],
                "audit": [
                    {"time": _now(), "user": "lab-user", "action": "run:plan", "target": "lab-workspace"},
                    {"time": _now(), "user": "ci-bot", "action": "run:apply", "target": "web-tier-asg"},
                ],
                "usage": [
                    {"metric": "Managed resources", "value": "186", "limit": "500"},
                    {"metric": "Runs this month", "value": "42", "limit": "Unlimited"},
                    {"metric": "Policy checks", "value": "12", "limit": "Unlimited"},
                ],
            },
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
        elif key == "org_settings" and isinstance(value, dict) and isinstance(tfc.get(key), dict):
            for section, rows in value.items():
                tfc["org_settings"].setdefault(section, rows)


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
        locks = tfc.setdefault("locks", [])
        if ws["locked"]:
            locks[:] = [lk for lk in locks if lk.get("workspace") != ws["name"]]
            locks.insert(0, {
                "id": f"lk-{len(locks) + 1}",
                "workspace": ws["name"],
                "operation": payload.get("operation") or "plan",
                "lockedBy": payload.get("lockedBy") or "lab-user",
                "lockedAt": _now(),
                "age": "0m",
            })
        else:
            locks[:] = [lk for lk in locks if lk.get("workspace") != ws["name"]]
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
            existing["hcl"] = bool(payload.get("hcl", existing.get("hcl")))
            row = existing
        else:
            row = {
                "id": f"v{len(vars_) + 1}",
                "workspace": ws_name,
                "key": key,
                "value": payload.get("value") or "",
                "category": payload.get("category") or "terraform",
                "sensitive": bool(payload.get("sensitive")),
                "hcl": bool(payload.get("hcl")),
            }
            vars_.append(row)
        return {"ok": True, "message": f"Set variable {key}", "variable": row}

    if action == "tfc_create_agent_pool":
        name = (payload.get("name") or f"pool-{len(tfc.get('agent_pools') or []) + 1}").strip()
        row = {
            "id": f"ap-{len(tfc.get('agent_pools') or []) + 1}",
            "name": name,
            "agents": int(payload.get("agents") or 1),
            "status": "healthy",
        }
        tfc.setdefault("agent_pools", []).append(row)
        return {"ok": True, "message": f"Agent pool {name} created", "pool": row}

    if action == "tfc_create_team":
        name = (payload.get("name") or f"team-{len(tfc.get('teams') or []) + 1}").strip()
        if any(t.get("name") == name for t in tfc.get("teams") or []):
            return {"ok": False, "error": f"Team '{name}' already exists"}
        row = {
            "id": f"t-{len(tfc.get('teams') or []) + 1}",
            "name": name,
            "access": payload.get("access") or "write",
            "members": int(payload.get("members") or 1),
        }
        tfc.setdefault("teams", []).append(row)
        return {"ok": True, "message": f"Team {name} created", "team": row}

    if action in ("tfc_set_team_access", "tfc_grant_team_access"):
        team = (payload.get("team") or "").strip()
        workspace = payload.get("workspace") or "lab-workspace"
        permission = payload.get("permission") or payload.get("access") or "Write"
        if not team:
            return {"ok": False, "error": "Team name required"}
        access = tfc.setdefault("team_access", [])
        existing = next((a for a in access if a.get("team") == team and a.get("workspace") == workspace), None)
        if existing:
            existing["permission"] = permission
            existing["inherited"] = bool(payload.get("inherited", False))
            row = existing
        else:
            row = {
                "team": team,
                "permission": permission,
                "inherited": bool(payload.get("inherited", False)),
                "workspace": workspace,
            }
            access.append(row)
        return {"ok": True, "message": f"Granted {permission} to {team} on {workspace}", "access": row}

    if action == "tfc_create_ws_notification":
        name = (payload.get("name") or f"Notify {len(tfc.get('ws_notifications') or []) + 1}").strip()
        workspace = payload.get("workspace") or "lab-workspace"
        row = {
            "id": f"wn-{len(tfc.get('ws_notifications') or []) + 1}",
            "workspace": workspace,
            "name": name,
            "triggers": payload.get("triggers") or "Errored runs",
            "status": payload.get("status") or "enabled",
        }
        tfc.setdefault("ws_notifications", []).append(row)
        return {"ok": True, "message": f"Notification {name} created", "notification": row}

    if action == "tfc_update_org_setting":
        section = payload.get("section") or "general"
        key = payload.get("key") or ""
        value = payload.get("value")
        org = tfc.setdefault("org_settings", {})
        rows = org.setdefault(section, [])
        if section in ("vcs", "tokens", "audit", "usage"):
            return {"ok": False, "error": f"Section {section} is not key/value editable"}
        # general/sso are list of [k,v]
        found = False
        for pair in rows:
            if isinstance(pair, (list, tuple)) and pair and pair[0] == key:
                pair[1] = value if value is not None else pair[1]
                found = True
                break
        if not found and key:
            rows.append([key, value or ""])
        return {"ok": True, "message": f"Updated {key}", "section": section}

    return None
