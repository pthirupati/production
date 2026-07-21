"""AWX / Ansible Tower V2 facades — workflows, approvals, notifications, EEs.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "workflow_templates": [
            {
                "id": 201,
                "name": "Deploy Web Stack",
                "organization": "Default",
                "inventory": "Production",
                "nodes": [
                    {"id": "n1", "type": "job", "name": "Deploy Web", "unified_job_template": 11},
                    {"id": "n2", "type": "approval", "name": "Change CAB"},
                    {"id": "n3", "type": "job", "name": "Smoke Tests", "unified_job_template": 12},
                ],
                "edges": [
                    {"from": "n1", "to": "n2", "on": "success"},
                    {"from": "n2", "to": "n3", "on": "success"},
                ],
            },
        ],
        "approvals": [
            {
                "id": "appr-1",
                "workflow": "Deploy Web Stack",
                "step": "Change CAB",
                "status": "pending",
                "requestedBy": "alice",
                "age": "12m",
                "created": _now(),
            },
        ],
        "notifications": [
            {
                "id": "nt-1",
                "name": "Slack Ops",
                "type": "Slack",
                "destinations": "#ops-alerts",
                "status": "ok",
            },
            {
                "id": "nt-2",
                "name": "Email On-Call",
                "type": "Email",
                "destinations": "oncall@fixitlab.io",
                "status": "ok",
            },
        ],
        "instance_groups": [
            {"id": "ig-1", "name": "default", "capacity": 100, "jobs_running": 1, "instances": 2},
            {"id": "ig-2", "name": "controlplane", "capacity": 50, "jobs_running": 0, "instances": 1},
        ],
        "execution_environments": [
            {
                "id": "ee-1",
                "name": "Default execution environment",
                "image": "quay.io/ansible/awx-ee:latest",
                "status": "ok",
            },
            {
                "id": "ee-2",
                "name": "Network EE",
                "image": "quay.io/ansible/network-ee:latest",
                "status": "ok",
            },
        ],
        "applications": [
            {
                "id": "app1",
                "name": "GitHub OAuth",
                "clientType": "Confidential",
                "redirect": "https://awx.fixitlab.local/sso/callback",
            },
        ],
        "management_jobs": [
            {"id": "mj1", "name": "Cleanup expired sessions", "schedule": "Daily 03:00", "lastRun": "Success", "enabled": True},
            {"id": "mj2", "name": "Remove old job artifacts", "schedule": "Weekly Sun", "lastRun": "Success", "enabled": True},
            {"id": "mj3", "name": "Cleanup orphaned partitions", "schedule": "Monthly 1st", "lastRun": "Success", "enabled": False},
        ],
        "settings": {
            "settings-auth": [
                {"key": "LDAP Server URI", "value": "ldap://dc.corp.fixitlab.local"},
                {"key": "Bind DN", "value": "CN=awx-bind,OU=Service,DC=corp,DC=fixitlab,DC=local"},
                {"key": "User Search", "value": "(&(objectClass=user)(sAMAccountName=%(user)s))"},
            ],
            "settings-jobs": [
                {"key": "Job timeout (seconds)", "value": "3600"},
                {"key": "Concurrent jobs", "value": "10"},
                {"key": "AWX task isolation", "value": "Enabled"},
            ],
            "settings-system": [
                {"key": "Base URL", "value": "https://awx.fixitlab.local"},
                {"key": "Timezone", "value": "UTC"},
                {"key": "Session timeout", "value": "1800"},
            ],
            "settings-ui": [
                {"key": "Custom login info", "value": "FixitLab AWX Training"},
                {"key": "Logo", "value": "Default"},
            ],
            "settings-subscription": [
                {"key": "Subscription type", "value": "Enterprise trial"},
                {"key": "Seats", "value": "50"},
                {"key": "Expires", "value": "2026-12-31"},
            ],
        },
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value
        elif key == "settings" and isinstance(value, dict) and isinstance(state.get(key), dict):
            for section, rows in value.items():
                state["settings"].setdefault(section, rows)


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "create_workflow_template":
        name = (payload.get("name") or f"Workflow {len(state.get('workflow_templates') or []) + 1}").strip()
        wid = max((int(w.get("id") or 0) for w in state.get("workflow_templates") or []), default=200) + 1
        row = {
            "id": wid,
            "name": name,
            "organization": payload.get("organization") or "Default",
            "inventory": payload.get("inventory") or "Production",
            "nodes": payload.get("nodes") or [
                {"id": "n1", "type": "job", "name": "Start Job", "unified_job_template": 11},
                {"id": "n2", "type": "approval", "name": "Approve"},
            ],
            "edges": payload.get("edges") or [{"from": "n1", "to": "n2", "on": "success"}],
        }
        state.setdefault("workflow_templates", []).append(row)
        return {"ok": True, "message": f"Workflow template {name} created", "workflow": row}

    if action == "launch_workflow":
        wid = int(payload.get("workflow_id") or payload.get("id") or 0)
        wf = next((w for w in state.get("workflow_templates") or [] if w.get("id") == wid), None)
        if not wf and (state.get("workflow_templates") or []):
            wf = state["workflow_templates"][0]
        if not wf:
            return {"ok": False, "error": "Workflow template not found"}
        approval = {
            "id": f"appr-{len(state.get('approvals') or []) + 1}",
            "workflow": wf["name"],
            "step": next((n["name"] for n in (wf.get("nodes") or []) if n.get("type") == "approval"), "Approval"),
            "status": "pending",
            "requestedBy": (state.get("session") or {}).get("user") or "admin",
            "age": "0m",
            "created": _now(),
        }
        state.setdefault("approvals", []).insert(0, approval)
        return {"ok": True, "message": f"Launched workflow {wf['name']}", "approval": approval}

    if action == "approve_workflow":
        aid = payload.get("id") or payload.get("approval_id")
        appr = next((a for a in state.get("approvals") or [] if a.get("id") == aid), None)
        if not appr and (state.get("approvals") or []):
            appr = next((a for a in state["approvals"] if a.get("status") == "pending"), None)
        if not appr:
            return {"ok": False, "error": "Approval not found"}
        appr["status"] = "approved" if payload.get("approve", True) else "denied"
        return {"ok": True, "message": f"Approval {appr['status']}", "approval": appr}

    if action == "create_notification":
        name = (payload.get("name") or f"Notify {len(state.get('notifications') or []) + 1}").strip()
        row = {
            "id": f"nt-{len(state.get('notifications') or []) + 1}",
            "name": name,
            "type": payload.get("type") or "Slack",
            "destinations": payload.get("destinations") or "#alerts",
            "status": "ok",
        }
        state.setdefault("notifications", []).append(row)
        return {"ok": True, "message": f"Notification {name} created", "notification": row}

    if action == "create_execution_environment":
        name = (payload.get("name") or f"EE {len(state.get('execution_environments') or []) + 1}").strip()
        row = {
            "id": f"ee-{len(state.get('execution_environments') or []) + 1}",
            "name": name,
            "image": payload.get("image") or "quay.io/ansible/awx-ee:latest",
            "status": "ok",
        }
        state.setdefault("execution_environments", []).append(row)
        return {"ok": True, "message": f"Execution environment {name} created", "execution_environment": row}

    if action == "create_application":
        name = (payload.get("name") or f"App {len(state.get('applications') or []) + 1}").strip()
        row = {
            "id": f"app-{len(state.get('applications') or []) + 1}",
            "name": name,
            "clientType": payload.get("clientType") or payload.get("client_type") or "Confidential",
            "redirect": payload.get("redirect") or "https://awx.fixitlab.local/api/o/authorize/",
        }
        state.setdefault("applications", []).append(row)
        return {"ok": True, "message": f"Application {name} created", "application": row}

    if action == "launch_mgmt_job":
        mid = payload.get("id") or payload.get("job_id")
        jobs = state.get("management_jobs") or []
        job = next((j for j in jobs if j.get("id") == mid), None)
        if not job and jobs:
            job = jobs[0]
        if not job:
            return {"ok": False, "error": "Management job not found"}
        job["lastRun"] = "Success"
        job["last_run_at"] = _now()
        return {"ok": True, "message": f"Launched management job {job['name']}", "job": job}

    if action == "toggle_mgmt_job":
        mid = payload.get("id") or payload.get("job_id")
        job = next((j for j in state.get("management_jobs") or [] if j.get("id") == mid), None)
        if not job:
            return {"ok": False, "error": "Management job not found"}
        job["enabled"] = not bool(job.get("enabled", True))
        return {"ok": True, "message": f"{'Enabled' if job['enabled'] else 'Disabled'} {job['name']}", "job": job}

    if action == "update_setting":
        section = payload.get("section") or "settings-system"
        key = payload.get("key") or ""
        value = payload.get("value")
        settings = state.setdefault("settings", {})
        rows = settings.setdefault(section, [])
        row = next((r for r in rows if r.get("key") == key), None)
        if row:
            row["value"] = value if value is not None else row.get("value")
        else:
            if not key:
                return {"ok": False, "error": "Setting key required"}
            row = {"key": key, "value": value or ""}
            rows.append(row)
        return {"ok": True, "message": f"Updated {key}", "setting": row, "section": section}

    return None
