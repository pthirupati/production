"""In-memory SIEM / SOC console simulator for cybersecurity training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of a
Security Operations Center console: alerts, incidents, log search, response
playbooks, and monitored assets. Models the analyst triage workflow — an alert
is acknowledged, escalated into an incident, investigated (log search,
playbook run), remediated (quarantine host / block IP), then closed.
"""

from __future__ import annotations

import copy
import json
import time

from django.core.cache import cache

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"soc_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message, "severity": severity})


def _base_state() -> dict:
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"platform": "FixItLab SIEM", "version": "2.4"},
        "assets": [
            {"name": "web01", "ip": "10.0.0.11", "risk": "medium", "quarantined": False},
            {"name": "db01", "ip": "10.0.0.12", "risk": "high", "quarantined": False},
            {"name": "ws-finance-07", "ip": "10.0.5.42", "risk": "critical", "quarantined": False},
        ],
        "alerts": [
            {"id": "AL-1001", "title": "Suspicious PowerShell execution", "severity": "high",
             "asset": "ws-finance-07", "status": "new", "acknowledged": False, "source_ip": "203.0.113.55"},
            {"id": "AL-1002", "title": "Multiple failed SSH logins", "severity": "medium",
             "asset": "web01", "status": "new", "acknowledged": False, "source_ip": "198.51.100.23"},
            {"id": "AL-1003", "title": "Outbound connection to known C2 domain", "severity": "critical",
             "asset": "ws-finance-07", "status": "new", "acknowledged": False, "source_ip": "203.0.113.55"},
        ],
        "incidents": [],
        "playbooks": [
            {"id": "pb-malware-contain", "name": "Malware Containment", "steps": ["Isolate host", "Collect forensics", "Remove artifact"]},
            {"id": "pb-brute-force", "name": "Brute Force Response", "steps": ["Block source IP", "Force password reset", "Review auth logs"]},
        ],
        "blocked_ips": [],
        "log_index": [
            {"time": "2026-07-16T10:02:11Z", "host": "ws-finance-07", "message": "powershell.exe -enc <base64> spawned by winword.exe", "source": "EDR"},
            {"time": "2026-07-16T10:02:15Z", "host": "ws-finance-07", "message": "Outbound TCP 443 to 203.0.113.55 (known C2)", "source": "Firewall"},
            {"time": "2026-07-16T09:58:02Z", "host": "web01", "message": "Failed password for root from 198.51.100.23", "source": "sshd"},
            {"time": "2026-07-16T09:58:03Z", "host": "web01", "message": "Failed password for root from 198.51.100.23", "source": "sshd"},
            {"time": "2026-07-16T09:58:04Z", "host": "web01", "message": "Failed password for admin from 198.51.100.23", "source": "sshd"},
        ],
        "goal": {"title": "SOC triage lab", "objective": "Triage the critical C2 alert: acknowledge it, escalate to an incident, quarantine the host, and close it."},
        "broken": {"open_critical_alert": "AL-1003"},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "red-vs-blue" in slug or "red-blue" in slug or "dual-containment" in slug or "multi-vector" in slug:
        # Checked FIRST so a red-vs-blue slug never gets misrouted into the
        # single-fix quarantine/block branches below.
        state["goal"] = {
            "title": "Contain the multi-vector intrusion",
            "objective": "The attacker used two footholds at once: quarantine ws-finance-07 AND block "
                         "the brute-force source IP 198.51.100.23 — clearing only one leaves the other "
                         "vector open.",
        }
        state["broken"] = {"needs_quarantine": "ws-finance-07", "needs_block_ip": "198.51.100.23"}
    elif "quarantine" in slug or "malware" in slug or "c2" in slug:
        state["goal"] = {"title": "Contain malware", "objective": "Acknowledge AL-1003, run the containment playbook, and quarantine ws-finance-07."}
        state["broken"] = {"open_critical_alert": "AL-1003", "needs_quarantine": "ws-finance-07"}
    elif "brute" in slug or "ssh" in slug or "block" in slug:
        state["goal"] = {"title": "Stop brute force", "objective": "Acknowledge AL-1002 and block the attacking source IP."}
        state["broken"] = {"open_alert": "AL-1002", "needs_block_ip": "198.51.100.23"}
    elif "escalate" in slug or "incident" in slug:
        state["goal"] = {"title": "Escalate incident", "objective": "Escalate AL-1003 into a formal incident for tracking."}
        state["broken"] = {"needs_escalation": "AL-1003"}
    elif "playbook" in slug or "respond" in slug:
        state["goal"] = {"title": "Run response playbook", "objective": "Run the malware containment playbook against ws-finance-07."}
        state["broken"] = {"needs_playbook": "pb-malware-contain"}
    elif "search" in slug or "hunt" in slug or "log" in slug:
        state["goal"] = {"title": "Threat hunt", "objective": "Search the logs for the attacker source IP and confirm activity."}
        state["broken"] = {"needs_log_search": "203.0.113.55"}
    elif "close" in slug or "resolve" in slug:
        state["goal"] = {"title": "Close incident", "objective": "Close out the open incident after remediation."}
        state["broken"] = {"open_critical_alert": "AL-1003"}


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
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_soc_assets
        sync_soc_assets(session_id, state.get("assets") or [])
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


def _find_alert(state: dict, alert_id: str) -> dict | None:
    return next((a for a in state.get("alerts", []) if a.get("id") == alert_id), None)


def _find_incident(state: dict, incident_id: str) -> dict | None:
    return next((i for i in state.get("incidents", []) if i.get("id") == incident_id), None)


def _find_asset(state: dict, name: str) -> dict | None:
    return next((a for a in state.get("assets", []) if a.get("name") == name), None)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "SOC session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "analyst"}
        _event(state, "Signed in to SOC console", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to the SOC console first"}

    if action == "acknowledge_alert":
        alert_id = payload.get("alert_id") or broken.get("open_critical_alert") or broken.get("open_alert") or ""
        alert = _find_alert(state, alert_id)
        if not alert:
            return {"ok": False, "error": f"Alert {alert_id} not found"}
        alert["acknowledged"] = True
        alert["status"] = "acknowledged"
        _event(state, f"Alert {alert_id} acknowledged", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Alert acknowledged"}

    if action == "escalate_incident":
        alert_id = payload.get("alert_id") or broken.get("needs_escalation") or broken.get("open_critical_alert") or ""
        alert = _find_alert(state, alert_id)
        if not alert:
            return {"ok": False, "error": f"Alert {alert_id} not found"}
        inc_id = f"INC-{len(state.get('incidents', [])) + 1001}"
        state.setdefault("incidents", []).append({
            "id": inc_id, "title": alert.get("title"), "alert_id": alert_id,
            "asset": alert.get("asset"), "severity": alert.get("severity"), "status": "open",
        })
        alert["status"] = "escalated"
        broken.pop("needs_escalation", None)
        _event(state, f"Alert {alert_id} escalated to incident {inc_id}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Escalated to incident", "incident_id": inc_id}

    if action == "run_playbook":
        pb_id = payload.get("playbook_id") or broken.get("needs_playbook") or "pb-malware-contain"
        playbook = next((p for p in state.get("playbooks", []) if p.get("id") == pb_id), None)
        if not playbook:
            return {"ok": False, "error": f"Playbook {pb_id} not found"}
        broken.pop("needs_playbook", None)
        _event(state, f"Playbook {playbook['name']} executed", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Playbook {playbook['name']} executed", "steps": playbook.get("steps", [])}

    if action == "quarantine_host":
        name = payload.get("asset") or broken.get("needs_quarantine") or "ws-finance-07"
        asset = _find_asset(state, name)
        if not asset:
            return {"ok": False, "error": f"Asset {name} not found"}
        asset["quarantined"] = True
        broken.pop("needs_quarantine", None)
        _event(state, f"Host {name} quarantined from network", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.chaos_engine import inject as _chaos_inject
            _chaos_inject(session_id, "drop_nic", name, detail={"console": "soc", "reason": "quarantined"})
        except Exception:  # pragma: no cover
            pass
        return {"ok": True, "message": "Host quarantined"}

    if action == "block_ip":
        ip = payload.get("ip") or broken.get("needs_block_ip") or ""
        if not ip:
            return {"ok": False, "error": "IP address is required"}
        if ip not in state.setdefault("blocked_ips", []):
            state["blocked_ips"].append(ip)
        broken.pop("needs_block_ip", None)
        _event(state, f"IP {ip} blocked at the firewall", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"IP {ip} blocked"}

    if action == "search_logs":
        query = (payload.get("query") or "").strip()
        results = [e for e in state.get("log_index", []) if query.lower() in json.dumps(e).lower()] if query else []
        if query and query in ("203.0.113.55", "198.51.100.23") and broken.get("needs_log_search") == query:
            broken.pop("needs_log_search", None)
        _event(state, f"Log search: '{query}' ({len(results)} results)", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"{len(results)} log entries found", "results": results}

    if action == "close_incident":
        inc_id = payload.get("incident_id") or ""
        alert_id = payload.get("alert_id") or broken.get("open_critical_alert") or broken.get("open_alert") or ""
        incident = _find_incident(state, inc_id) if inc_id else next(
            (i for i in state.get("incidents", []) if i.get("alert_id") == alert_id), None
        )
        alert = _find_alert(state, alert_id) if alert_id else None
        if incident:
            incident["status"] = "closed"
        if alert:
            alert["status"] = "closed"
            if broken.get("open_critical_alert") == alert_id:
                broken.pop("open_critical_alert", None)
            if broken.get("open_alert") == alert_id:
                broken.pop("open_alert", None)
        if not incident and not alert:
            return {"ok": False, "error": "Incident or alert not found"}
        _event(state, f"Incident/alert {inc_id or alert_id} closed", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Closed"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_soc_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No SOC session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "SOC environment still has unresolved issues"
    return True, "SOC lab objectives met"
