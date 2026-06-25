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
            {"id": 501, "name": "Patch Linux", "status": "successful", "started": _now_iso()},
            {"id": 502, "name": "Deploy App", "status": "failed", "started": _now_iso()},
        ],
        "credentials": [
            {"id": 1, "name": "Machine SSH", "kind": "Machine"},
            {"id": 2, "name": "Vault Password", "kind": "Vault"},
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
        _save(session_id, entry)
        return {"ok": True, "message": "Project sync completed"}

    if action == "launch_template":
        tid = int(payload.get("template_id") or broken.get("failed_template_id") or 11)
        for jt in state.get("job_templates", []):
            if jt["id"] == tid:
                jt["status"] = "successful"
        broken.pop("failed_template_id", None)
        state["jobs"].insert(0, {"id": 900 + tid, "name": jt.get("name", "Job"), "status": "successful", "started": _now_iso()})
        state["events"].insert(0, {"time": _now_iso(), "message": f"Template {tid} launched successfully", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Job completed successfully"}

    if action == "create_template":
        name = (payload.get("name") or "New Template").strip()
        tid = max((jt.get("id", 0) for jt in state.get("job_templates", [])), default=0) + 1
        state.setdefault("job_templates", []).append(
            {"id": tid, "name": name, "playbook": "site.yml", "inventory": "Production", "status": "never"}
        )
        broken.pop("missing_template", None)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Template {name} created", "severity": "success"})
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
        _save(session_id, entry)
        return {"ok": True, "message": "Credential created"}

    if action == "create_project":
        name = (payload.get("name") or "new-playbooks").strip()
        pid = max((p.get("id", 0) for p in state.get("projects", [])), default=0) + 1
        state.setdefault("projects", []).append(
            {"id": pid, "name": name, "scm_type": "git", "status": "successful"}
        )
        state["events"].insert(0, {"time": _now_iso(), "message": f"Project {name} created", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Project created"}

    if action == "create_inventory":
        name = (payload.get("name") or "New Inventory").strip()
        iid = max((i.get("id", 0) for i in state.get("inventories", [])), default=0) + 1
        state.setdefault("inventories", []).append({"id": iid, "name": name, "hosts": 0, "sources": 0})
        state["events"].insert(0, {"time": _now_iso(), "message": f"Inventory {name} created", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Inventory created"}

    if action == "create_schedule":
        name = (payload.get("name") or "Nightly patch").strip()
        template = payload.get("template") or "Patch Linux"
        state["events"].insert(0, {"time": _now_iso(), "message": f"Schedule {name} for {template}", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Schedule created"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_awx_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No AWX session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "AWX environment still has unresolved issues"
    return True, "AWX lab objectives met"
