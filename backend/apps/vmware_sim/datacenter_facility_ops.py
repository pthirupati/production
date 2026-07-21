"""Facility ops: fire/safety, environmental sensors, optical plant, capacity & PdM.

Phase 10 Lab Environment facades for campus rooms (fire-suppression, FEF, MMR)
and NOC planning surfaces.
"""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Fire & safety ──────────────────────────────────────────────────────────

def build_fire_safety() -> dict:
    return {
        "system": "VESDA + Novec 1230",
        "status": "armed",
        "zones": [
            {"id": "FZ-A", "name": "Data Hall A", "status": "normal", "smoke_pct": 0.2},
            {"id": "FZ-B", "name": "MDF / Network", "status": "normal", "smoke_pct": 0.1},
            {"id": "FZ-C", "name": "Battery / Electrical", "status": "normal", "smoke_pct": 0.0},
        ],
        "detectors": [
            {"id": "VESDA-1", "type": "aspirating", "zone": "FZ-A", "status": "ok", "obscuration": 0.02},
            {"id": "SMK-12", "type": "photoelectric", "zone": "FZ-A", "status": "ok"},
            {"id": "SMK-18", "type": "photoelectric", "zone": "FZ-B", "status": "ok"},
            {"id": "HEAT-03", "type": "rate-of-rise", "zone": "FZ-C", "status": "ok"},
        ],
        "cylinders": [
            {"id": "NOV-1", "agent": "Novec 1230", "pressure_bar": 25.0, "weight_kg": 180, "status": "ready"},
            {"id": "NOV-2", "agent": "Novec 1230", "pressure_bar": 25.1, "weight_kg": 178, "status": "ready"},
        ],
        "nozzles_armed": 24,
        "manual_release": False,
        "pre_alarm": False,
        "discharge_active": False,
        "events": [{"time": _now(), "message": "Fire system armed · weekly test passed"}],
    }


def fire_safety_op(fs: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    if op == "smoke_alarm":
        zone = kwargs.get("zone_id") or "FZ-A"
        z = next((x for x in fs.get("zones") or [] if x.get("id") == zone), None)
        if z:
            z["status"] = "alarm"
            z["smoke_pct"] = 8.5
        for d in fs.get("detectors") or []:
            if d.get("zone") == zone:
                d["status"] = "alarm"
        fs["pre_alarm"] = True
        fs["status"] = "pre-alarm"
        fs.setdefault("events", []).insert(0, {"time": _now(), "message": f"Smoke alarm {zone}"})
        return True, f"Smoke alarm {zone}", fs

    if op == "silence":
        fs["pre_alarm"] = False
        fs["status"] = "armed"
        for z in fs.get("zones") or []:
            z["status"] = "normal"
            z["smoke_pct"] = 0.2
        for d in fs.get("detectors") or []:
            d["status"] = "ok"
        fs.setdefault("events", []).insert(0, {"time": _now(), "message": "Alarms silenced / reset"})
        return True, "Silenced", fs

    if op == "discharge":
        if not fs.get("pre_alarm") and not kwargs.get("force"):
            return False, "Discharge requires pre-alarm or force=true", fs
        fs["discharge_active"] = True
        fs["status"] = "discharging"
        for c in fs.get("cylinders") or []:
            c["status"] = "discharged"
            c["pressure_bar"] = 2.0
            c["weight_kg"] = max(5, float(c.get("weight_kg") or 10) - 150)
        fs.setdefault("events", []).insert(0, {"time": _now(), "message": "Novec discharge initiated"})
        return True, "Discharge started", fs

    if op == "rearm":
        fs["discharge_active"] = False
        fs["pre_alarm"] = False
        fs["manual_release"] = False
        fs["status"] = "armed"
        for c in fs.get("cylinders") or []:
            c["status"] = "ready"
            c["pressure_bar"] = 25.0
            c["weight_kg"] = 180
        for z in fs.get("zones") or []:
            z["status"] = "normal"
            z["smoke_pct"] = 0.1
        for d in fs.get("detectors") or []:
            d["status"] = "ok"
        fs.setdefault("events", []).insert(0, {"time": _now(), "message": "System rearmed · cylinders refilled"})
        return True, "Rearmed", fs

    if op == "manual_release":
        fs["manual_release"] = True
        fs["pre_alarm"] = True
        fs["status"] = "pre-alarm"
        return True, "Manual release armed", fs

    return False, f"Unknown fire op: {op}", fs


# ── Environmental monitoring ───────────────────────────────────────────────

def build_environmental(servers: list[dict] | None = None) -> dict:
    servers = servers or []
    sensors = [
        {"id": "ENV-IN-A", "type": "temp_humidity", "location": "Cold aisle A", "temp_c": 21.2, "humidity_pct": 45, "status": "ok"},
        {"id": "ENV-OUT-A", "type": "temp_humidity", "location": "Hot aisle A", "temp_c": 33.8, "humidity_pct": 28, "status": "ok"},
        {"id": "ENV-IN-B", "type": "temp_humidity", "location": "Cold aisle B", "temp_c": 21.5, "humidity_pct": 46, "status": "ok"},
        {"id": "LEAK-01", "type": "water_leak", "location": "Underfloor R01-R03", "wet": False, "status": "ok"},
        {"id": "LEAK-02", "type": "water_leak", "location": "Underfloor CDU row", "wet": False, "status": "ok"},
        {"id": "DOOR-DH", "type": "door", "location": "Data hall mantrap", "open": False, "status": "ok"},
        {"id": "DOOR-MDF", "type": "door", "location": "MDF", "open": False, "status": "ok"},
        {"id": "DIFF-01", "type": "differential_pressure", "location": "Containment A", "pa": 12.5, "status": "ok"},
    ]
    # Reflect BMC inlets roughly
    if servers:
        inlets = [
            (s.get("bmc") or {}).get("sensors", {}).get("inlet_c")
            for s in servers if (s.get("bmc") or {}).get("sensors", {}).get("inlet_c")
        ]
        if inlets:
            avg = sum(inlets) / len(inlets)
            sensors[0]["temp_c"] = round(avg, 1)
    return {
        "sensors": sensors,
        "ashrae_class": "A1",
        "alerts": [],
        "last_scan": _now(),
    }


def environmental_op(env: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    sid = kwargs.get("sensor_id") or ""
    sensor = next((s for s in env.get("sensors") or [] if s.get("id") == sid), None)

    if op == "trip_leak":
        sensor = sensor or next((s for s in env.get("sensors") or [] if s.get("type") == "water_leak"), None)
        if not sensor:
            return False, "No leak sensor", env
        sensor["wet"] = True
        sensor["status"] = "alarm"
        env.setdefault("alerts", []).insert(0, {"time": _now(), "severity": "critical", "message": f"Water leak {sensor['id']}"})
        return True, f"Leak {sensor['id']}", env

    if op == "clear_leak":
        for s in env.get("sensors") or []:
            if s.get("type") == "water_leak":
                s["wet"] = False
                s["status"] = "ok"
        env["alerts"] = [a for a in env.get("alerts") or [] if "leak" not in (a.get("message") or "").lower()]
        return True, "Leak sensors cleared", env

    if op == "open_door":
        if not sensor or sensor.get("type") != "door":
            return False, "Door sensor required", env
        sensor["open"] = True
        sensor["status"] = "warning"
        env.setdefault("alerts", []).insert(0, {"time": _now(), "severity": "warning", "message": f"Door open {sensor['id']}"})
        return True, f"Door open {sid}", env

    if op == "close_door":
        if not sensor or sensor.get("type") != "door":
            return False, "Door sensor required", env
        sensor["open"] = False
        sensor["status"] = "ok"
        return True, f"Door closed {sid}", env

    if op == "hotspot":
        sensor = sensor or next((s for s in env.get("sensors") or [] if "Hot" in (s.get("location") or "")), None)
        if not sensor:
            return False, "No hot-aisle sensor", env
        sensor["temp_c"] = 42.0
        sensor["status"] = "alarm"
        env.setdefault("alerts", []).insert(0, {"time": _now(), "severity": "warning", "message": f"Hotspot {sensor['id']} {sensor['temp_c']}°C"})
        return True, "Hotspot injected", env

    if op == "normalize":
        for s in env.get("sensors") or []:
            s["status"] = "ok"
            if s.get("type") == "temp_humidity" and "Hot" in (s.get("location") or ""):
                s["temp_c"] = 33.5
            if s.get("type") == "water_leak":
                s["wet"] = False
            if s.get("type") == "door":
                s["open"] = False
        env["alerts"] = []
        env["last_scan"] = _now()
        return True, "Environment normalized", env

    return False, f"Unknown env op: {op}", env


# ── Optical infrastructure ─────────────────────────────────────────────────

def build_optical() -> dict:
    return {
        "fef": {
            "id": "FEF-1",
            "carriers": [
                {"id": "CARRIER-A", "circuit": "DWDM-100G-01", "status": "up", "lambda_nm": 1550},
                {"id": "CARRIER-B", "circuit": "DWDM-100G-02", "status": "up", "lambda_nm": 1550},
            ],
            "splice_trays": 8,
            "status": "online",
        },
        "mmr": {
            "id": "MMR-1",
            "cross_connects": [
                {"id": "XC-01", "a": "CARRIER-A", "z": "cust-spine", "media": "SMF LC", "status": "active"},
                {"id": "XC-02", "a": "CARRIER-B", "z": "cust-spine", "media": "SMF LC", "status": "active"},
                {"id": "XC-03", "a": "FEF-spare", "z": "none", "media": "SMF LC", "status": "dark"},
            ],
            "status": "online",
        },
        "trunks": [
            {"id": "TRK-MPO-01", "type": "MPO-24", "from": "MMR-1", "to": "MDF-PP-1", "length_m": 45, "status": "ok", "loss_db": 0.8},
            {"id": "TRK-MPO-02", "type": "MPO-24", "from": "MDF-PP-1", "to": "R09-TOR", "length_m": 28, "status": "ok", "loss_db": 0.6},
            {"id": "TRK-MPO-03", "type": "MPO-12", "from": "MDF-PP-1", "to": "R10-IB", "length_m": 32, "status": "ok", "loss_db": 0.5},
        ],
        "patch_panels": [
            {"id": "MDF-PP-1", "ports": 48, "media": "LC duplex", "populated": 36},
            {"id": "DH-PP-A", "ports": 24, "media": "MPO-LC harness", "populated": 18},
        ],
        "events": [{"time": _now(), "message": "Optical plant OTDR baseline within budget"}],
    }


def optical_op(opt: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    if op == "cut_fiber":
        tid = kwargs.get("trunk_id") or "TRK-MPO-01"
        tr = next((t for t in opt.get("trunks") or [] if t.get("id") == tid), None)
        if not tr:
            return False, f"Trunk {tid} not found", opt
        tr["status"] = "cut"
        tr["loss_db"] = 99.0
        opt.setdefault("events", []).insert(0, {"time": _now(), "message": f"Fiber cut {tid}"})
        return True, f"Cut {tid}", opt

    if op == "repair_fiber":
        tid = kwargs.get("trunk_id") or ""
        tr = next((t for t in opt.get("trunks") or [] if t.get("id") == tid), None)
        if not tr:
            return False, f"Trunk {tid} not found", opt
        tr["status"] = "ok"
        tr["loss_db"] = 0.7
        opt.setdefault("events", []).insert(0, {"time": _now(), "message": f"Fiber repaired {tid}"})
        return True, f"Repaired {tid}", opt

    if op == "activate_xc":
        xid = kwargs.get("xc_id") or "XC-03"
        xc = next((x for x in (opt.get("mmr") or {}).get("cross_connects") or [] if x.get("id") == xid), None)
        if not xc:
            return False, f"XC {xid} not found", opt
        xc["status"] = "active"
        xc["z"] = kwargs.get("z_end") or "cust-spine"
        return True, f"Activated {xid}", opt

    if op == "deactivate_xc":
        xid = kwargs.get("xc_id") or ""
        xc = next((x for x in (opt.get("mmr") or {}).get("cross_connects") or [] if x.get("id") == xid), None)
        if not xc:
            return False, f"XC {xid} not found", opt
        xc["status"] = "dark"
        return True, f"Darkened {xid}", opt

    if op == "carrier_down":
        cid = kwargs.get("carrier_id") or "CARRIER-A"
        for c in (opt.get("fef") or {}).get("carriers") or []:
            if c.get("id") == cid:
                c["status"] = "down"
                opt.setdefault("events", []).insert(0, {"time": _now(), "message": f"Carrier down {cid}"})
                return True, f"{cid} down", opt
        return False, f"Carrier {cid} not found", opt

    if op == "carrier_up":
        cid = kwargs.get("carrier_id") or "CARRIER-A"
        for c in (opt.get("fef") or {}).get("carriers") or []:
            if c.get("id") == cid:
                c["status"] = "up"
                return True, f"{cid} up", opt
        return False, f"Carrier {cid} not found", opt

    return False, f"Unknown optical op: {op}", opt


# ── Capacity planning + predictive maintenance ─────────────────────────────

def build_capacity_snapshot(state: dict) -> dict:
    servers = state.get("servers") or []
    racks = state.get("racks") or []
    facility = state.get("facility") or {}
    cooling = state.get("cooling") or []
    pdus = state.get("pdus") or state.get("power_chain", {}).get("rack_pdus") or []

    u_used = len(servers)
    u_total = max(1, len(racks) * 42)
    it_kw = float(facility.get("it_kw") or sum(
        ((s.get("bmc") or {}).get("sensors") or {}).get("psu1_w", 0)
        + ((s.get("bmc") or {}).get("sensors") or {}).get("psu2_w", 0)
        for s in servers
    ) / 1000)
    cooling_cap = sum(float(c.get("capacity_kw") or 0) for c in cooling) or 30.0
    cooling_load = sum(float(c.get("load_kw") or 0) for c in cooling if c.get("status") == "running")
    pdu_kw = sum(float(p.get("load_kw") or 0) for p in pdus)
    power_cap_kw = max(pdu_kw * 1.4, it_kw * 1.5, 50.0)

    space_pct = round(100.0 * u_used / u_total, 1)
    power_pct = round(100.0 * it_kw / power_cap_kw, 1)
    cool_pct = round(100.0 * cooling_load / cooling_cap, 1)

    # Simple growth projection (linear 2% / month)
    forecast = []
    for m in range(1, 7):
        forecast.append({
            "month": m,
            "space_pct": min(99, round(space_pct + m * 2.0, 1)),
            "power_pct": min(99, round(power_pct + m * 1.5, 1)),
            "cooling_pct": min(99, round(cool_pct + m * 1.2, 1)),
        })

    bottlenecks = []
    if power_pct >= 75:
        bottlenecks.append({"resource": "power", "pct": power_pct, "note": "Plan PDU / UPS upgrade"})
    if cool_pct >= 70:
        bottlenecks.append({"resource": "cooling", "pct": cool_pct, "note": "Add CRAC or raise setpoint carefully"})
    if space_pct >= 80:
        bottlenecks.append({"resource": "space", "pct": space_pct, "note": "Free U or add racks"})

    return {
        "computed_at": _now(),
        "space": {"used_u": u_used, "total_u": u_total, "pct": space_pct},
        "power": {"it_kw": round(it_kw, 2), "capacity_kw": round(power_cap_kw, 2), "pct": power_pct},
        "cooling": {"load_kw": round(cooling_load, 2), "capacity_kw": round(cooling_cap, 2), "pct": cool_pct},
        "weight": {
            "avg_kg_per_rack": round(
                sum(float((r.get("physics") or {}).get("mass_kg") or 300) for r in racks) / max(1, len(racks)),
                0,
            ),
            "floor_ok": all((r.get("physics") or {}).get("floor_loading_ok", True) for r in racks),
        },
        "forecast_6m": forecast,
        "bottlenecks": bottlenecks,
        "pue": facility.get("pue"),
    }


def build_predictive_maintenance(state: dict) -> dict:
    items = []
    for s in state.get("servers") or []:
        hw = s.get("hardware") or {}
        host = s.get("hostname") or s.get("id")
        for f in hw.get("fans") or []:
            hours = int(f.get("bearing_hours") or 18000)
            items.append({
                "asset": host,
                "part": f.get("id") or "FAN",
                "metric": "bearing_hours",
                "value": hours,
                "threshold": 25000,
                "risk": "high" if hours > 22000 else ("medium" if hours > 18000 else "low"),
                "recommendation": "Replace fan module at next window" if hours > 18000 else "Monitor",
            })
        for p in hw.get("psus") or []:
            items.append({
                "asset": host,
                "part": p.get("id") or "PSU",
                "metric": "efficiency_drift",
                "value": 2.1 if p.get("status") != "healthy" else 0.4,
                "threshold": 3.0,
                "risk": "high" if p.get("status") != "healthy" else "low",
                "recommendation": "RMA PSU" if p.get("status") != "healthy" else "OK",
            })
        raid = s.get("raid") or {}
        for d in raid.get("physical_disks") or []:
            wear = int(d.get("wear_pct") or 0)
            items.append({
                "asset": host,
                "part": d.get("id"),
                "metric": "ssd_wear_pct",
                "value": wear,
                "threshold": 80,
                "risk": "high" if wear >= 70 or d.get("status") == "failed" else ("medium" if wear >= 40 else "low"),
                "recommendation": "Stage spare / rebuild" if wear >= 40 or d.get("status") == "failed" else "OK",
            })
    # Sort high risk first
    order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: order.get(x.get("risk"), 9))
    return {
        "computed_at": _now(),
        "items": items[:40],
        "high_risk_count": sum(1 for i in items if i.get("risk") == "high"),
        "medium_risk_count": sum(1 for i in items if i.get("risk") == "medium"),
    }
