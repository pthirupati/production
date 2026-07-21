"""Phase 11: disaster recovery, access control, automation runbooks, ops reports."""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Disaster recovery / power failover ─────────────────────────────────────

def build_dr_platform() -> dict:
    return {
        "mode": "normal",  # normal | utility_loss | on_generator | recovering
        "rto_min": 15,
        "rpo_min": 5,
        "sites": [
            {"id": "dc1-primary", "role": "active", "status": "online"},
            {"id": "dc2-dr", "role": "standby", "status": "warm"},
        ],
        "runbook_steps": [
            "Confirm utility loss / ATS transfer",
            "Verify generator start + fuel",
            "Confirm UPS on bypass/battery healthy",
            "Validate critical VLANs / BGP",
            "Declare incident + notify stakeholders",
            "Optional: failover workloads to dc2-dr",
        ],
        "completed_steps": [],
        "last_drill": None,
        "events": [{"time": _now(), "message": "DR platform ready · primary site active"}],
    }


def dr_op(dr: dict, power_chain: dict, campus: dict, op: str, **kwargs) -> tuple[bool, str, dict, dict]:
    """Mutate DR + power chain. Returns (ok, msg, dr, power_chain)."""
    ats = power_chain.setdefault("ats", {})
    gen = power_chain.setdefault("generator", {})
    utility = power_chain.setdefault("utility", {})
    ups_list = power_chain.get("ups") or []

    if op == "utility_fail":
        utility["status"] = "offline"
        ats["status"] = "transferring"
        for u in ups_list:
            if isinstance(u, dict):
                u["on_battery"] = True
                u["runtime_min"] = max(8, int(u.get("runtime_min") or 14) - 2)
        dr["mode"] = "utility_loss"
        dr.setdefault("events", []).insert(0, {"time": _now(), "message": "Utility feed lost · UPS on battery"})
        return True, "Utility failed", dr, power_chain

    if op == "start_generator":
        gen["status"] = "running"
        gen["runtime_hours"] = float(gen.get("runtime_hours") or 0) + 0.1
        gen["fuel_pct"] = max(5, float(gen.get("fuel_pct") or 90) - 0.5)
        # Sync campus generators
        for g in (campus or {}).get("generators") or []:
            g["status"] = "running"
            g["fuel_pct"] = gen["fuel_pct"]
        ats["status"] = "on_generator"
        utility["status"] = utility.get("status") or "offline"
        for u in ups_list:
            if isinstance(u, dict):
                u["on_battery"] = False
                u["status"] = "online"
        dr["mode"] = "on_generator"
        dr.setdefault("events", []).insert(0, {"time": _now(), "message": "Generator online · ATS on generator"})
        return True, "Generator started", dr, power_chain

    if op == "stop_generator":
        gen["status"] = "standby"
        for g in (campus or {}).get("generators") or []:
            g["status"] = "standby"
        if utility.get("status") == "online":
            ats["status"] = "on_utility"
            dr["mode"] = "normal"
        else:
            ats["status"] = "on_battery_only"
            dr["mode"] = "utility_loss"
        return True, "Generator stopped", dr, power_chain

    if op == "restore_utility":
        utility["status"] = "online"
        ats["status"] = "on_utility"
        gen["status"] = "cooldown" if gen.get("status") == "running" else "standby"
        if gen.get("status") == "cooldown":
            gen["status"] = "standby"
        for u in ups_list:
            if isinstance(u, dict):
                u["on_battery"] = False
                u["battery_pct"] = min(100, int(u.get("battery_pct") or 90) + 5)
        for g in (campus or {}).get("generators") or []:
            g["status"] = "standby"
        dr["mode"] = "recovering"
        dr.setdefault("events", []).insert(0, {"time": _now(), "message": "Utility restored · ATS back on utility"})
        return True, "Utility restored", dr, power_chain

    if op == "complete_step":
        step = kwargs.get("step") or ""
        steps = dr.get("runbook_steps") or []
        done = dr.setdefault("completed_steps", [])
        if step and step in steps and step not in done:
            done.append(step)
        if len(done) >= len(steps) and dr.get("mode") == "recovering":
            dr["mode"] = "normal"
        return True, f"Step done: {step}", dr, power_chain

    if op == "site_failover":
        for s in dr.get("sites") or []:
            if s.get("role") == "active":
                s["role"] = "failed"
                s["status"] = "offline"
            elif s.get("id") == "dc2-dr":
                s["role"] = "active"
                s["status"] = "online"
        dr["mode"] = "dr_active"
        dr.setdefault("events", []).insert(0, {"time": _now(), "message": "Workloads failed over to dc2-dr"})
        return True, "Site failover to DR", dr, power_chain

    if op == "site_failback":
        for s in dr.get("sites") or []:
            if s.get("id") == "dc1-primary":
                s["role"] = "active"
                s["status"] = "online"
            elif s.get("id") == "dc2-dr":
                s["role"] = "standby"
                s["status"] = "warm"
        dr["mode"] = "normal"
        dr["completed_steps"] = []
        dr.setdefault("events", []).insert(0, {"time": _now(), "message": "Failback to primary complete"})
        return True, "Failback complete", dr, power_chain

    if op == "run_drill":
        dr["last_drill"] = _now()
        dr["completed_steps"] = []
        dr.setdefault("events", []).insert(0, {"time": _now(), "message": "DR drill started (tabletop)"})
        return True, "DR drill started", dr, power_chain

    return False, f"Unknown DR op: {op}", dr, power_chain


# ── Access control / security ──────────────────────────────────────────────

def build_access_control() -> dict:
    return {
        "gate": {"status": "secured", "vehicle_barrier": "closed", "tailgate_alarm": False},
        "biometrics": {"status": "online", "readers": 6, "failed_scans_24h": 2},
        "badges": [
            {"id": "BADGE-1001", "holder": "tech.oncall", "role": "datacenter_tech", "zones": ["reception", "data-hall-a", "mdf"]},
            {"id": "BADGE-2002", "holder": "net.eng", "role": "network_eng", "zones": ["reception", "mdf", "mmr", "fef"]},
            {"id": "BADGE-3003", "holder": "visitor.acme", "role": "visitor", "zones": ["reception"], "escort_required": True},
        ],
        "cameras": {"online": 24, "total": 24, "recording": True},
        "events": [
            {"time": _now(), "type": "info", "message": "Gate secured · biometrics online"},
        ],
        "active_alarms": [],
        "mantrap": {"status": "ready", "occupied": False},
    }


def access_op(access: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    if op == "badge_in":
        badge_id = kwargs.get("badge_id") or "BADGE-1001"
        zone = kwargs.get("zone") or "data-hall-a"
        badge = next((b for b in access.get("badges") or [] if b.get("id") == badge_id), None)
        if not badge:
            return False, f"Unknown badge {badge_id}", access
        allowed = zone in (badge.get("zones") or []) or badge.get("role") == "datacenter_tech"
        if badge.get("escort_required") and zone != "reception":
            allowed = False
        if not allowed:
            access.setdefault("active_alarms", []).insert(0, {
                "time": _now(), "severity": "warning", "message": f"Access denied {badge_id} → {zone}",
            })
            access.setdefault("events", []).insert(0, {
                "time": _now(), "type": "deny", "message": f"DENY {badge['holder']} → {zone}",
            })
            return True, f"Denied {badge_id}", access
        access.setdefault("events", []).insert(0, {
            "time": _now(), "type": "allow", "message": f"ALLOW {badge['holder']} → {zone}",
        })
        if zone == "data-hall-a":
            access.setdefault("mantrap", {})["occupied"] = False
        return True, f"Badge-in {zone}", access

    if op == "open_gate":
        access.setdefault("gate", {})["status"] = "open"
        access["gate"]["vehicle_barrier"] = "open"
        access.setdefault("events", []).insert(0, {"time": _now(), "type": "warning", "message": "Vehicle gate opened"})
        return True, "Gate open", access

    if op == "secure_gate":
        access.setdefault("gate", {})["status"] = "secured"
        access["gate"]["vehicle_barrier"] = "closed"
        access["gate"]["tailgate_alarm"] = False
        return True, "Gate secured", access

    if op == "tailgate_alarm":
        access.setdefault("gate", {})["tailgate_alarm"] = True
        access.setdefault("active_alarms", []).insert(0, {
            "time": _now(), "severity": "critical", "message": "Tailgate detected at security gate",
        })
        return True, "Tailgate alarm", access

    if op == "clear_alarms":
        access["active_alarms"] = []
        access.setdefault("gate", {})["tailgate_alarm"] = False
        return True, "Alarms cleared", access

    if op == "biometric_fail":
        bio = access.setdefault("biometrics", {})
        bio["status"] = "degraded"
        bio["failed_scans_24h"] = int(bio.get("failed_scans_24h") or 0) + 5
        access.setdefault("active_alarms", []).insert(0, {
            "time": _now(), "severity": "warning", "message": "Biometric reader failure — lobby",
        })
        return True, "Biometric fault", access

    if op == "biometric_ok":
        bio = access.setdefault("biometrics", {})
        bio["status"] = "online"
        return True, "Biometrics online", access

    if op == "camera_offline":
        cam = access.setdefault("cameras", {})
        cam["online"] = max(0, int(cam.get("online") or 24) - 1)
        return True, "Camera offline", access

    return False, f"Unknown access op: {op}", access


# ── Automation runbooks ────────────────────────────────────────────────────

def build_automation() -> dict:
    return {
        "engine": "FixitLab Runbooks",
        "jobs": [],
        "catalog": [
            {
                "id": "rb-firmware-fleet",
                "name": "Fleet BIOS/BMC health check",
                "steps": ["Inventory firmware", "Compare baselines", "Open tickets for drift"],
            },
            {
                "id": "rb-pdu-balance",
                "name": "PDU A/B load balance audit",
                "steps": ["Read PDU outlets", "Flag imbalance >15%", "Suggest moves"],
            },
            {
                "id": "rb-raid-patrol",
                "name": "Nightly RAID patrol orchestration",
                "steps": ["Queue patrol_read", "Collect results", "Alert on media errors"],
            },
            {
                "id": "rb-dr-tabletop",
                "name": "DR tabletop automation",
                "steps": ["utility_fail", "start_generator", "Verify ATS", "restore_utility"],
            },
            {
                "id": "rb-compliance-export",
                "name": "Compliance evidence pack",
                "steps": ["Export inventory", "Export tickets", "Export capacity snapshot"],
            },
        ],
        "events": [{"time": _now(), "message": "Automation catalog loaded"}],
    }


def automation_op(auto: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    if op == "run":
        runbook_id = kwargs.get("runbook_id") or ""
        rb = next((r for r in auto.get("catalog") or [] if r.get("id") == runbook_id), None)
        if not rb:
            return False, f"Runbook {runbook_id} not found", auto
        job = {
            "id": f"JOB-{int(time.time()) % 100000:05d}",
            "runbook_id": runbook_id,
            "name": rb["name"],
            "status": "succeeded",
            "started": _now(),
            "finished": _now(),
            "steps_done": list(rb.get("steps") or []),
        }
        auto.setdefault("jobs", []).insert(0, job)
        auto.setdefault("events", []).insert(0, {"time": _now(), "message": f"Ran {rb['name']} → {job['id']}"})
        return True, f"Ran {rb['name']}", auto

    if op == "fail_job":
        jobs = auto.get("jobs") or []
        if not jobs:
            return False, "No jobs", auto
        jobs[0]["status"] = "failed"
        return True, "Latest job marked failed", auto

    return False, f"Unknown automation op: {op}", auto


# ── Ops reports ────────────────────────────────────────────────────────────

def build_ops_report(state: dict) -> dict:
    servers = state.get("servers") or []
    tickets = state.get("tickets") or []
    facility = state.get("facility") or {}
    capacity = state.get("capacity") or {}
    predictive = state.get("predictive") or {}
    broken = state.get("broken") or {}
    healthy = sum(
        1 for s in servers
        if all(v == "healthy" for v in (s.get("components") or {}).values())
    )
    open_tickets = [t for t in tickets if t.get("status") not in ("closed", "resolved")]
    return {
        "generated_at": _now(),
        "title": "FixitLab DCIM Ops Report",
        "summary": {
            "servers": len(servers),
            "healthy_servers": healthy,
            "open_tickets": len(open_tickets),
            "pue": facility.get("pue"),
            "it_kw": facility.get("it_kw") or capacity.get("power", {}).get("it_kw"),
            "active_incident": bool(broken.get("component")),
            "broken": broken or None,
        },
        "capacity": {
            "space_pct": (capacity.get("space") or {}).get("pct"),
            "power_pct": (capacity.get("power") or {}).get("pct"),
            "cooling_pct": (capacity.get("cooling") or {}).get("pct"),
            "bottlenecks": capacity.get("bottlenecks") or [],
        },
        "predictive_high_risk": (predictive.get("high_risk_count") or 0),
        "sections": [
            {"id": "inventory", "rows": len(state.get("inventory") or [])},
            {"id": "tickets", "rows": len(tickets)},
            {"id": "events", "rows": len(state.get("events") or [])},
            {"id": "twin_journal", "rows": len((state.get("digital_twin") or {}).get("persisted_changes") or [])},
        ],
        "recommendations": _report_recommendations(capacity, predictive, broken, open_tickets),
    }


def _report_recommendations(capacity, predictive, broken, open_tickets) -> list[str]:
    recs = []
    if broken.get("component"):
        recs.append(f"Resolve active fault: {broken.get('component')} ({broken.get('target') or broken.get('server') or 'facility'})")
    for b in (capacity.get("bottlenecks") or [])[:3]:
        recs.append(f"Capacity: {b.get('note')}")
    if (predictive.get("high_risk_count") or 0) > 0:
        recs.append(f"Schedule maintenance for {predictive['high_risk_count']} high-risk FRUs")
    if len(open_tickets) > 3:
        recs.append(f"Burn down {len(open_tickets)} open ops tickets")
    if not recs:
        recs.append("No critical recommendations — continue routine patrols")
    return recs
