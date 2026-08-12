"""Phase 12: CAB/change freeze, sustainability, containment, cable trays,
burn-in/load-bank, compliance evidence, SNMP/Redfish exporter depth.
"""

from __future__ import annotations

import hashlib
import json
import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Change CAB / freeze calendar ───────────────────────────────────────────

def build_change_calendar() -> dict:
    return {
        "freeze_active": False,
        "freeze_reason": None,
        "windows": [
            {"id": "MW-SUN", "label": "Sunday 02:00–06:00 UTC", "risk": "standard", "open": True},
            {"id": "MW-WED", "label": "Wednesday 01:00–03:00 UTC", "risk": "standard", "open": True},
        ],
        "changes": [],
        "events": [{"time": _now(), "message": "Change calendar loaded · no freeze"}],
    }


def change_op(cal: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    if op == "create":
        cid = f"CHG-{int(time.time()) % 100000:05d}"
        ch = {
            "id": cid,
            "title": kwargs.get("title") or "Scheduled maintenance",
            "risk": kwargs.get("risk") or "medium",
            "impact": kwargs.get("impact") or "Single rack / PDU",
            "rollback": kwargs.get("rollback") or "Revert FRU / restore prior config",
            "window_id": kwargs.get("window_id") or "MW-SUN",
            "status": "draft",  # draft → cab → approved|rejected → implementing → verified → closed
            "cab_notes": "",
            "created": _now(),
        }
        cal.setdefault("changes", []).insert(0, ch)
        return True, f"Created {cid}", cal

    if op == "submit_cab":
        ch = _find_change(cal, kwargs.get("change_id"))
        if not ch:
            return False, "Change not found", cal
        if ch["status"] != "draft":
            return False, f"Cannot submit from {ch['status']}", cal
        ch["status"] = "cab"
        return True, f"{ch['id']} in CAB", cal

    if op == "cab_approve":
        ch = _find_change(cal, kwargs.get("change_id"))
        if not ch:
            return False, "Change not found", cal
        ch["status"] = "approved"
        ch["cab_notes"] = kwargs.get("notes") or "CAB approved"
        return True, f"{ch['id']} approved", cal

    if op == "cab_reject":
        ch = _find_change(cal, kwargs.get("change_id"))
        if not ch:
            return False, "Change not found", cal
        ch["status"] = "rejected"
        ch["cab_notes"] = kwargs.get("notes") or "CAB rejected"
        return True, f"{ch['id']} rejected", cal

    if op == "implement":
        ch = _find_change(cal, kwargs.get("change_id"))
        if not ch:
            return False, "Change not found", cal
        if ch["status"] != "approved":
            return False, "Must be approved before implement", cal
        if cal.get("freeze_active"):
            return False, "Change freeze active — cannot implement", cal
        ch["status"] = "implementing"
        return True, f"{ch['id']} implementing", cal

    if op == "verify":
        ch = _find_change(cal, kwargs.get("change_id"))
        if not ch:
            return False, "Change not found", cal
        ch["status"] = "verified"
        return True, f"{ch['id']} verified", cal

    if op == "close":
        ch = _find_change(cal, kwargs.get("change_id"))
        if not ch:
            return False, "Change not found", cal
        ch["status"] = "closed"
        return True, f"{ch['id']} closed", cal

    if op == "enable_freeze":
        cal["freeze_active"] = True
        cal["freeze_reason"] = kwargs.get("reason") or "Holiday / critical event freeze"
        cal.setdefault("events", []).insert(0, {"time": _now(), "message": f"FREEZE ON: {cal['freeze_reason']}"})
        return True, "Freeze enabled", cal

    if op == "disable_freeze":
        cal["freeze_active"] = False
        cal["freeze_reason"] = None
        cal.setdefault("events", []).insert(0, {"time": _now(), "message": "Freeze lifted"})
        return True, "Freeze disabled", cal

    return False, f"Unknown change op: {op}", cal


def _find_change(cal: dict, change_id: str | None):
    return next((c for c in cal.get("changes") or [] if c.get("id") == change_id), None)


def window_load_advice(state: dict) -> list[dict]:
    """Per-rack headroom advice for planning a window against live load.

    Advisory only — deliberately not wired into change_freeze_blocks. Blocking
    ops on live load would make labs that never expected a load conflict report
    as broken instead of showing a policy message.
    """
    pdus = (state.get("power_chain") or {}).get("rack_pdus") or []
    by_rack: dict = {}
    for p in pdus:
        rack = p.get("rack")
        if not rack:
            continue
        pct = int(p.get("load_pct") or 0)
        kw = float(p.get("load_kw") or 0)
        prev = by_rack.get(rack)
        if prev is None or pct > prev["load_pct"] or kw > float(prev.get("load_kw") or 0):
            by_rack[rack] = {"rack": rack, "load_pct": pct, "load_kw": p.get("load_kw")}
    advice = []
    for row in by_rack.values():
        pct = int(row["load_pct"] or 0)
        if pct >= 85:
            verdict = "conflict"
        elif pct >= 70:
            verdict = "caution"
        else:
            verdict = "clear"
        advice.append({**row, "verdict": verdict})
    return advice


def change_freeze_blocks(state: dict, action: str) -> str | None:
    """Return error message if freeze blocks this action."""
    cal = state.get("change_calendar") or {}
    if not cal.get("freeze_active"):
        return None
    blocked = {
        "power_cycle", "service_mode_action", "motherboard_ops",
        "replace_power", "replace_cpu", "replace_motherboard", "replace_disk",
        "bmc_flash_target", "bios_flash", "raid_delete_vd",
    }
    if action in blocked:
        return f"Change freeze active ({cal.get('freeze_reason') or 'policy'}) — blocked: {action}"
    return None


# ── Sustainability ─────────────────────────────────────────────────────────

def build_sustainability(state: dict) -> dict:
    facility = state.get("facility") or {}
    campus = state.get("campus") or {}
    liquid = state.get("liquid_cooling") or {}
    it_kw = float(facility.get("it_kw") or 8.0)
    total_kw = float(facility.get("total_kw") or it_kw * 1.4)
    pue = float(facility.get("pue") or (total_kw / max(it_kw, 0.1)))
    # Water: cooling towers makeup ~ 1.8 L/kWh IT for hybrid; DLC reduces
    dlc_running = any(c.get("status") == "running" for c in (liquid.get("cdus") or []))
    liters_per_kwh = 0.4 if dlc_running else 1.8
    water_l_day = round(it_kw * 24 * liters_per_kwh, 1)
    wue = round(water_l_day / max(it_kw * 24, 1), 3)  # L/kWh
    carbon_kg_per_kwh = 0.24  # grid intensity stub
    carbon_kg_hr = round(total_kw * carbon_kg_per_kwh, 2)
    towers = campus.get("cooling_towers") or []
    return {
        "computed_at": _now(),
        "pue": round(pue, 3),
        "wue_l_per_kwh": wue,
        "water_l_day": water_l_day,
        "carbon_intensity_kg_per_kwh": carbon_kg_per_kwh,
        "carbon_kg_hr": carbon_kg_hr,
        "it_kw": round(it_kw, 2),
        "total_kw": round(total_kw, 2),
        "dlc_active": dlc_running,
        "cooling_towers_online": sum(1 for t in towers if t.get("status") == "running"),
        "targets": {"pue": 1.35, "wue": 1.2, "carbon_kg_hr": 200},
        "notes": "DLC active reduces WUE" if dlc_running else "Air-cooled path — higher WUE",
    }


# ── Containment / blanking coupling ────────────────────────────────────────

def build_containment() -> dict:
    return {
        "aisles": [
            {"id": "CA-A", "name": "Cold aisle A", "doors_closed": True, "curtains_ok": True, "dp_pa": 12.5},
            {"id": "HA-A", "name": "Hot aisle A", "doors_closed": True, "curtains_ok": True, "dp_pa": -2.0},
        ],
        "blanking_compliance_pct": 85,
        "events": [{"time": _now(), "message": "Containment nominal"}],
    }


def containment_op(ct: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    aid = kwargs.get("aisle_id") or "CA-A"
    aisle = next((a for a in ct.get("aisles") or [] if a.get("id") == aid), None)
    if op == "toggle_door":
        if not aisle:
            return False, "Aisle not found", ct
        aisle["doors_closed"] = not aisle.get("doors_closed", True)
        aisle["dp_pa"] = 12.5 if aisle["doors_closed"] else 2.0
        return True, f"{aid} doors {'closed' if aisle['doors_closed'] else 'OPEN'}", ct
    if op == "toggle_curtain":
        if not aisle:
            return False, "Aisle not found", ct
        aisle["curtains_ok"] = not aisle.get("curtains_ok", True)
        return True, f"{aid} curtains {'ok' if aisle['curtains_ok'] else 'gap'}", ct
    if op == "set_blanking_pct":
        ct["blanking_compliance_pct"] = int(kwargs.get("pct") or 85)
        return True, f"Blanking compliance {ct['blanking_compliance_pct']}%", ct
    return False, f"Unknown containment op: {op}", ct


def apply_blanking_to_physics(rack: dict, containment: dict | None) -> None:
    """Adjust inlet/ΔP based on installed blanking panels + containment doors."""
    phy = rack.get("physics") or {}
    fru = rack.get("fru") or {}
    panels = [p for p in (fru.get("blanking_panels") or []) if p.get("installed")]
    installed = len(panels)
    # More blanking → cooler inlet, higher ΔP
    bonus = min(4.0, installed * 0.25)
    phy["inlet_c"] = round(max(18.0, float(phy.get("inlet_c") or 22) - bonus + (2.5 if installed < 4 else 0)), 1)
    phy["outlet_c"] = round(float(phy.get("inlet_c") or 22) + float(phy.get("heat_kw") or 4) * 0.7 + 8, 1)
    phy["blanking_panels_installed"] = installed
    phy["fan_pressure_mmH2O"] = round(float(phy.get("fan_pressure_mmH2O") or 1) * (1.0 + installed * 0.02), 2)
    if containment:
        open_doors = any(not a.get("doors_closed", True) for a in containment.get("aisles") or [])
        if open_doors:
            phy["inlet_c"] = round(float(phy["inlet_c"]) + 1.5, 1)
            phy["containment_breach"] = True
        else:
            phy["containment_breach"] = False
    rack["physics"] = phy


# ── Cable tray plant ───────────────────────────────────────────────────────

def build_cable_plant() -> dict:
    return {
        "trays": [
            {"id": "TRAY-EW-1", "type": "ladder", "path": "East-West overhead row A", "fill_pct": 42, "capacity_mm2": 12000, "status": "ok"},
            {"id": "TRAY-EW-2", "type": "ladder", "path": "East-West overhead row B", "fill_pct": 61, "capacity_mm2": 12000, "status": "ok"},
            {"id": "TRAY-NS-1", "type": "basket", "path": "North-South to MDF", "fill_pct": 78, "capacity_mm2": 8000, "status": "warning"},
            {"id": "UF-A", "type": "underfloor", "path": "Cold aisle A underfloor", "fill_pct": 35, "capacity_mm2": 6000, "status": "ok"},
        ],
        "events": [{"time": _now(), "message": "Cable plant surveyed · TRAY-NS-1 near capacity"}],
    }


def cable_plant_op(plant: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    tid = kwargs.get("tray_id") or ""
    tray = next((t for t in plant.get("trays") or [] if t.get("id") == tid), None)
    if op == "add_fill":
        if not tray:
            return False, "Tray not found", plant
        tray["fill_pct"] = min(100, int(tray.get("fill_pct") or 0) + int(kwargs.get("delta") or 5))
        tray["status"] = "critical" if tray["fill_pct"] >= 90 else ("warning" if tray["fill_pct"] >= 70 else "ok")
        return True, f"{tid} fill {tray['fill_pct']}%", plant
    if op == "reduce_fill":
        if not tray:
            return False, "Tray not found", plant
        tray["fill_pct"] = max(0, int(tray.get("fill_pct") or 0) - int(kwargs.get("delta") or 5))
        tray["status"] = "critical" if tray["fill_pct"] >= 90 else ("warning" if tray["fill_pct"] >= 70 else "ok")
        return True, f"{tid} fill {tray['fill_pct']}%", plant
    if op == "reroute":
        if not tray:
            return False, "Tray not found", plant
        tray["path"] = kwargs.get("path") or tray.get("path")
        plant.setdefault("events", []).insert(0, {"time": _now(), "message": f"Rerouted {tid}"})
        return True, f"Rerouted {tid}", plant
    return False, f"Unknown cable plant op: {op}", plant


# ── Burn-in / load bank / guest OS ─────────────────────────────────────────

def build_burnin(servers: list[dict] | None = None) -> dict:
    machines = []
    for s in (servers or [])[:4]:
        machines.append({
            "id": s.get("id"),
            "hostname": s.get("hostname"),
            "load_bank": False,
            "soak_pct": 0,
            "result": None,
            "guest_install": "none",  # none | pxe | installer | cloud_init | ready
            "released": False,
        })
    return {
        "load_banks": [
            {"id": "LB-1", "kw": 20, "attached_to": None, "status": "idle"},
            {"id": "LB-2", "kw": 40, "attached_to": None, "status": "idle"},
        ],
        "machines": machines,
        "events": [{"time": _now(), "message": "Burn-in bay ready"}],
    }


def burnin_op(bi: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    mid = kwargs.get("machine_id") or ""
    m = next((x for x in bi.get("machines") or [] if x.get("id") == mid), None)

    if op == "attach_load_bank":
        lb_id = kwargs.get("load_bank_id") or "LB-1"
        lb = next((x for x in bi.get("load_banks") or [] if x.get("id") == lb_id), None)
        if not m or not lb:
            return False, "Machine or load bank not found", bi
        if lb.get("attached_to"):
            return False, f"{lb_id} already attached", bi
        lb["attached_to"] = mid
        lb["status"] = "loaded"
        m["load_bank"] = True
        return True, f"{lb_id} → {m['hostname']}", bi

    if op == "detach_load_bank":
        for lb in bi.get("load_banks") or []:
            if lb.get("attached_to") == mid:
                lb["attached_to"] = None
                lb["status"] = "idle"
        if m:
            m["load_bank"] = False
        return True, "Load bank detached", bi

    if op == "soak":
        if not m:
            return False, "Machine not found", bi
        if not m.get("load_bank"):
            return False, "Attach load bank first", bi
        m["soak_pct"] = min(100, int(m.get("soak_pct") or 0) + 34)
        if m["soak_pct"] >= 100:
            m["result"] = "pass"
        return True, f"Soak {m['soak_pct']}%", bi

    if op == "fail_soak":
        if not m:
            return False, "Machine not found", bi
        m["result"] = "fail"
        m["soak_pct"] = int(m.get("soak_pct") or 50)
        return True, "Soak failed", bi

    if op == "guest_advance":
        if not m:
            return False, "Machine not found", bi
        order = ["none", "pxe", "installer", "cloud_init", "ready"]
        cur = m.get("guest_install") or "none"
        idx = order.index(cur) if cur in order else 0
        m["guest_install"] = order[min(len(order) - 1, idx + 1)]
        return True, f"Guest → {m['guest_install']}", bi

    if op == "release":
        if not m:
            return False, "Machine not found", bi
        if m.get("result") != "pass" or m.get("guest_install") != "ready":
            return False, "Need soak pass + guest ready", bi
        m["released"] = True
        return True, f"Released {m['hostname']}", bi

    return False, f"Unknown burn-in op: {op}", bi


# ── Docs / evidence ────────────────────────────────────────────────────────

def build_doc_library() -> dict:
    return {
        "sops": [
            {"id": "SOP-PSU", "title": "Hot-swap PSU replacement", "role": "datacenter_tech"},
            {"id": "SOP-RAID", "title": "RAID rebuild with hot spare", "role": "platform"},
            {"id": "SOP-FIBER", "title": "MPO trunk cut response", "role": "network_eng"},
            {"id": "SOP-DR", "title": "Utility loss → generator", "role": "sre"},
            {"id": "SOP-ACCESS", "title": "Visitor escort & badge", "role": "security"},
        ],
        "events": [],
    }


def build_evidence_pack(state: dict) -> dict:
    payload = {
        "generated_at": _now(),
        "inventory": state.get("inventory") or [],
        "tickets": [
            {"id": t.get("id"), "status": t.get("status"), "type": t.get("type"), "vendor": t.get("vendor")}
            for t in (state.get("tickets") or [])
        ],
        "capacity": state.get("capacity") or {},
        "sustainability": state.get("sustainability") or {},
        "journal_len": len((state.get("digital_twin") or {}).get("persisted_changes") or []),
        "broken": state.get("broken") or {},
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return {
        "id": f"EVD-{digest}",
        "generated_at": payload["generated_at"],
        "sha256_16": digest,
        "sections": {
            "inventory_rows": len(payload["inventory"]),
            "tickets": len(payload["tickets"]),
            "journal_entries": payload["journal_len"],
        },
        "summary": payload,
    }


# ── Monitoring exporters depth ─────────────────────────────────────────────

def build_exporters(state: dict) -> dict:
    servers = state.get("servers") or []
    pdus = state.get("pdus") or []
    targets = []
    for s in servers:
        bmc = s.get("bmc") or {}
        targets.append({
            "id": f"redfish-{s.get('id')}",
            "type": "redfish",
            "endpoint": bmc.get("endpoint") or f"https://bmc-{s.get('hostname')}",
            "up": True,
            "paths": ["/redfish/v1/Systems/1", "/redfish/v1/Chassis/1", "/redfish/v1/Managers/1"],
        })
    for p in pdus[:6]:
        targets.append({
            "id": f"snmp-{p.get('id')}",
            "type": "snmp",
            "endpoint": f"udp://{p.get('id')}.mgmt.local:161",
            "up": p.get("status") == "online",
            "oids": ["1.3.6.1.2.1.1.1.0", "1.3.6.1.4.1.318.1.1.12.2.3.1.1.2"],
        })
    return {
        "targets": targets,
        "last_walk": None,
        "last_redfish": None,
        "events": [{"time": _now(), "message": f"{len(targets)} exporter targets registered"}],
    }


def exporter_op(ex: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    tid = kwargs.get("target_id") or ""
    t = next((x for x in ex.get("targets") or [] if x.get("id") == tid), None)

    if op == "toggle_target":
        if not t:
            return False, "Target not found", ex
        t["up"] = not t.get("up", True)
        return True, f"{tid} {'up' if t['up'] else 'down'}", ex

    if op == "snmp_walk":
        if not t or t.get("type") != "snmp":
            t = next((x for x in ex.get("targets") or [] if x.get("type") == "snmp"), None)
        if not t:
            return False, "No SNMP target", ex
        walk = [
            {"oid": "1.3.6.1.2.1.1.1.0", "value": "APC Rack PDU"},
            {"oid": "1.3.6.1.2.1.1.5.0", "value": t.get("id")},
            {"oid": "1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.1", "value": "12.4 A"},
            {"oid": "1.3.6.1.4.1.318.1.1.12.2.3.1.1.2.2", "value": "11.8 A"},
        ]
        ex["last_walk"] = {"target": t["id"], "time": _now(), "rows": walk}
        return True, f"SNMP walk {t['id']}", ex

    if op == "redfish_get":
        path = kwargs.get("path") or "/redfish/v1/Systems/1"
        if not t or t.get("type") != "redfish":
            t = next((x for x in ex.get("targets") or [] if x.get("type") == "redfish"), None)
        if not t:
            return False, "No Redfish target", ex
        body = {
            "@odata.id": path,
            "Id": "1",
            "PowerState": "On",
            "Status": {"Health": "OK", "State": "Enabled"},
            "ProcessorSummary": {"Count": 2},
            "MemorySummary": {"TotalSystemMemoryGiB": 512},
        }
        ex["last_redfish"] = {"target": t["id"], "path": path, "time": _now(), "body": body}
        return True, f"Redfish GET {path}", ex

    return False, f"Unknown exporter op: {op}", ex
