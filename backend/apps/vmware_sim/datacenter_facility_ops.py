"""Facility ops: fire/safety, environmental sensors, optical plant, capacity & PdM.

Phase 10 Lab Environment facades for campus rooms (fire-suppression, FEF, MMR)
and NOC planning surfaces.
"""

from __future__ import annotations

import math
import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def tick_live(state: dict) -> dict:
    """Drift environmental + BMC sensors for live NOC scrape feel (no WS required)."""
    env = state.setdefault("environmental", build_environmental(state.get("servers") or []))
    t = time.time()
    phase = (t % 120) / 120.0 * 2 * math.pi
    for s in env.get("sensors") or []:
        if s.get("type") == "temp_humidity":
            base = 33.5 if "Hot" in (s.get("location") or "") else 21.2
            if s.get("status") == "alarm":
                continue
            s["temp_c"] = round(base + 0.6 * math.sin(phase + hash(s.get("id") or "") % 7), 1)
            s["humidity_pct"] = round(max(20, min(60, (s.get("humidity_pct") or 45) + 0.3 * math.cos(phase))), 1)
        elif s.get("type") == "differential_pressure" and s.get("status") == "ok":
            s["pa"] = round(12.0 + 1.5 * math.sin(phase * 1.7), 1)
    env["last_scan"] = _now()
    env["tick"] = env.get("tick", 0) + 1

    for srv in state.get("servers") or []:
        if srv.get("power_state") != "on":
            continue
        bmc = srv.setdefault("bmc", {})
        sensors = bmc.setdefault("sensors", {})
        inlet = float(sensors.get("inlet_c") or 22.0)
        sensors["inlet_c"] = round(inlet + 0.15 * math.sin(phase + hash(srv.get("id") or "") % 5), 1)
        sensors["exhaust_c"] = round(sensors["inlet_c"] + 11.5 + 0.4 * math.cos(phase), 1)
        sensors["fans_rpm"] = int(7200 + 80 * math.sin(phase * 2))
        if sensors.get("cpu1_c"):
            sensors["cpu1_c"] = round(sensors["inlet_c"] + 26 + 0.5 * math.sin(phase), 1)
        if sensors.get("cpu2_c"):
            sensors["cpu2_c"] = round(sensors["inlet_c"] + 28 + 0.5 * math.cos(phase), 1)

    # Progressive RAID rebuilds (degraded → rebuilding → optimal)
    advance_raid_rebuilds(state)
    return env


def advance_raid_rebuilds(state: dict, only_server_id: str | None = None, step_pct: int = 18) -> list[dict]:
    """Advance any VD with status==rebuilding. Returns list of {server, vd, pct, status}."""
    advanced: list[dict] = []
    broken = state.get("broken") or {}
    for srv in state.get("servers") or []:
        if only_server_id and srv.get("id") != only_server_id:
            continue
        raid = srv.get("raid") or {}
        changed = False
        for vd in raid.get("virtual_disks") or []:
            if vd.get("status") != "rebuilding":
                continue
            pct = int(vd.get("rebuild_pct") or 0) + max(8, int(step_pct))
            if pct >= 100:
                pct = 100
                vd["rebuild_pct"] = 100
                vd["status"] = "optimal"
                # Retire failed disks (or resurrect if no spare — same-bay rebuild)
                target = vd.get("rebuild_target")
                for d in raid.get("physical_disks") or []:
                    if d.get("status") == "failed":
                        if target:
                            d["status"] = "offline"
                            d["smart"] = "Replaced"
                        else:
                            d["status"] = "online"
                            d["smart"] = "OK"
                    if d.get("status") == "rebuilding" or d.get("id") == target:
                        d["status"] = "online"
                        d["smart"] = "OK"
                comps = srv.setdefault("components", {})
                if comps.get("disk") == "failed":
                    comps["disk"] = "healthy"
                if comps.get("raid") == "failed":
                    comps["raid"] = "healthy"
                if broken.get("server") == srv.get("id") and broken.get("component") in ("disk", "raid"):
                    broken.clear()
                    state["broken"] = {}
                vd.pop("rebuild_source", None)
                vd.pop("rebuild_target", None)
                raid.setdefault("operations", []).insert(0, {
                    "time": _now(), "op": "rebuild_complete", "detail": vd.get("id"),
                })
                changed = True
                advanced.append({"server": srv.get("id"), "vd": vd.get("id"), "pct": 100, "status": "optimal"})
            else:
                vd["rebuild_pct"] = pct
                changed = True
                advanced.append({"server": srv.get("id"), "vd": vd.get("id"), "pct": pct, "status": "rebuilding"})
        if changed:
            raid.setdefault("operations", [])
    return advanced


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
        "idf": {
            "id": "IDF-1",
            "floor": "L2",
            "access_switch": {"id": "IDF-ASW-1", "model": "Catalyst 9300", "status": "up"},
            "patch_panels": [
                {"id": "IDF-PP-1", "ports": 24, "populated": 16, "media": "Cat6A"},
            ],
            "uplinks": [
                {"id": "UL-IDF-MDF", "from": "IDF-ASW-1", "to": "MDF-PP-1", "media": "SMF LC", "status": "up"},
            ],
        },
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

    # Ensure IDF closet exists on older sessions
    idf = opt.setdefault("idf", {
        "id": "IDF-1",
        "floor": "L2",
        "access_switch": {"id": "IDF-ASW-1", "model": "Catalyst 9300", "status": "up"},
        "patch_panels": [{"id": "IDF-PP-1", "ports": 24, "populated": 16, "media": "Cat6A"}],
        "uplinks": [{"id": "UL-IDF-MDF", "from": "IDF-ASW-1", "to": "MDF-PP-1", "media": "SMF LC", "status": "up"}],
    })

    if op == "idf_patch":
        delta = int(kwargs.get("delta") or 1)
        panels = idf.get("patch_panels") or []
        pp = next((p for p in panels if p.get("id") == kwargs.get("panel_id")), None) if kwargs.get("panel_id") else (panels[0] if panels else None)
        if not pp:
            return False, "IDF patch panel not found", opt
        ports = int(pp.get("ports") or 24)
        populated = max(0, min(ports, int(pp.get("populated") or 0) + delta))
        pp["populated"] = populated
        opt.setdefault("events", []).insert(0, {"time": _now(), "message": f"IDF patch {pp['id']} → {populated}/{ports}"})
        return True, f"{pp['id']} {populated}/{ports}", opt

    if op == "idf_uplink_toggle":
        uid = kwargs.get("uplink_id") or "UL-IDF-MDF"
        ul = next((u for u in (idf.get("uplinks") or []) if u.get("id") == uid), None)
        if not ul:
            return False, f"Uplink {uid} not found", opt
        ul["status"] = "down" if ul.get("status") == "up" else "up"
        sw = idf.get("access_switch") or {}
        if ul["status"] == "down":
            sw["status"] = "degraded"
        else:
            sw["status"] = "up"
        idf["access_switch"] = sw
        opt.setdefault("events", []).insert(0, {"time": _now(), "message": f"IDF uplink {uid} {ul['status']}"})
        return True, f"{uid} {ul['status']}", opt

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


# ── Campus exterior plant (dock / chillers / substation / battery / parking) ─

def ensure_campus_plant(campus: dict, power_chain: dict | None = None) -> dict:
    """Backfill plant fields on older sessions without resetting live values."""
    c = campus if isinstance(campus, dict) else {}
    if not c.get("battery_strings"):
        ups_list = (power_chain or {}).get("ups") or []
        soc = 100
        if ups_list:
            soc = int(ups_list[0].get("battery_pct") or 100)
        c["battery_strings"] = [
            {"id": "STR-A", "chemistry": "VRLA", "cells": 40, "soc_pct": soc, "temp_c": 22.0, "status": "float"},
            {"id": "STR-B", "chemistry": "VRLA", "cells": 40, "soc_pct": soc, "temp_c": 21.8, "status": "float"},
        ]
    dock = c.setdefault("loading_dock", {})
    dock.setdefault("bays", 2)
    dock.setdefault("occupied_bays", 1)
    dock.setdefault("received_today", 0)
    dock.setdefault("queue", [
        {"id": "ASN-1042", "carrier": "Dell Logistics", "contents": "2× R760 PSU FRU", "status": "at_bay"},
        {"id": "ASN-1048", "carrier": "HPE", "contents": "DIMM kit 128GB", "status": "inbound"},
    ])
    c.setdefault("parking", {"spaces": 48, "occupied": 12})
    c.setdefault("events", [])
    if not c.get("spares"):
        c["spares"] = {
            "bins": [
                {"id": "BIN-PSU", "sku": "PSU-R760", "label": "R760 PSU FRU", "qty": 4, "min_qty": 2, "location": "A-1"},
                {"id": "BIN-DIMM", "sku": "DIMM-128GB", "label": "DIMM kit 128GB", "qty": 6, "min_qty": 2, "location": "A-2"},
                {"id": "BIN-SSD", "sku": "SSD-1.92TB", "label": "NVMe 1.92TB", "qty": 5, "min_qty": 2, "location": "B-1"},
                {"id": "BIN-DAC", "sku": "DAC-25G", "label": "25G DAC 3m", "qty": 12, "min_qty": 4, "location": "C-1"},
            ],
            "issued_today": 0,
            "quarantine": [],
            "kits_staged": [],
        }
    else:
        sp = c["spares"]
        sp.setdefault("bins", [])
        sp.setdefault("issued_today", 0)
        sp.setdefault("quarantine", [])
        sp.setdefault("kits_staged", [])
    return c


def _restock_from_contents(spares: dict, contents: str) -> str | None:
    """Match dock ASN contents to a spare bin sku/label; bump qty by 1."""
    hay = (contents or "").lower()
    if not hay:
        return None
    for bin_row in spares.get("bins") or []:
        keys = [bin_row.get("sku") or "", bin_row.get("label") or "", bin_row.get("id") or ""]
        if any(k and k.lower() in hay for k in keys):
            bin_row["qty"] = int(bin_row.get("qty") or 0) + 1
            return bin_row.get("id")
        # partial token match (e.g. "PSU" in "R760 PSU FRU")
        for token in ("psu", "dimm", "ssd", "nvme", "dac"):
            if token in hay and token in (bin_row.get("label") or "").lower():
                bin_row["qty"] = int(bin_row.get("qty") or 0) + 1
                return bin_row.get("id")
    return None


def campus_plant_op(campus: dict, power_chain: dict | None, op: str, **kwargs) -> tuple[bool, str, dict]:
    """Mutate exterior plant rooms: dock receive, chiller start/stop, XFMR note, battery sync, parking, spares."""
    c = ensure_campus_plant(campus or {}, power_chain)
    pc = power_chain or {}
    op = (op or "").strip()

    def _log(msg: str) -> None:
        c.setdefault("events", []).insert(0, {"time": _now(), "message": msg})
        c["events"] = c["events"][:40]

    if op == "receive_dock":
        asn = kwargs.get("asn_id") or kwargs.get("id")
        dock = c["loading_dock"]
        queue = dock.get("queue") or []
        item = next((q for q in queue if q.get("id") == asn), None) if asn else next(
            (q for q in queue if q.get("status") in ("at_bay", "inbound")), None
        )
        if not item:
            return False, "No inbound shipment to receive", c
        item["status"] = "received"
        dock["received_today"] = int(dock.get("received_today") or 0) + 1
        dock["occupied_bays"] = max(0, int(dock.get("occupied_bays") or 1) - 1)
        restocked = _restock_from_contents(c["spares"], item.get("contents") or "")
        # RMA ASNs stage a kit for the ticket asset so repair bay can consume it.
        asset = item.get("asset_id")
        sku = item.get("sku") or (item.get("contents") or "FRU").split("·")[0].strip()
        if asset:
            spares = c["spares"]
            spares.setdefault("kits_staged", []).insert(0, {
                "id": f"KIT-{item.get('rma_number') or item.get('id')}",
                "sku": sku,
                "bin_id": restocked or "dock",
                "for_asset": asset,
                "ticket_id": item.get("ticket_id"),
                "rma_number": item.get("rma_number"),
                "status": "staged",
            })
            spares["kits_staged"] = spares["kits_staged"][:20]
        extra = f" · restocked {restocked}" if restocked else ""
        if asset:
            extra += f" · kit staged for {asset}"
        _log(f"Dock received {item['id']} · {item.get('contents')}{extra}")
        return True, f"Received {item['id']}{extra}", c

    if op == "arrive_dock":
        dock = c["loading_dock"]
        queue = dock.setdefault("queue", [])
        inbound = next((q for q in queue if q.get("status") == "inbound"), None)
        if not inbound:
            nid = f"ASN-{1040 + len(queue) + 1}"
            inbound = {
                "id": nid,
                "carrier": kwargs.get("carrier") or "Freight",
                "contents": kwargs.get("contents") or "Misc FRU",
                "status": "inbound",
            }
            queue.append(inbound)
        inbound["status"] = "at_bay"
        dock["occupied_bays"] = min(int(dock.get("bays") or 2), int(dock.get("occupied_bays") or 0) + 1)
        _log(f"Truck at bay · {inbound['id']}")
        return True, f"{inbound['id']} at bay", c

    if op == "issue_spare":
        spares = c["spares"]
        bid = kwargs.get("bin_id") or kwargs.get("id")
        bin_row = next((b for b in (spares.get("bins") or []) if b.get("id") == bid), None)
        if not bin_row:
            return False, "Spare bin not found", c
        if int(bin_row.get("qty") or 0) <= 0:
            return False, f"{bid} empty", c
        bin_row["qty"] = int(bin_row["qty"]) - 1
        spares["issued_today"] = int(spares.get("issued_today") or 0) + 1
        asset = kwargs.get("asset_id")
        if asset:
            spares.setdefault("kits_staged", []).insert(0, {
                "id": f"KIT-{spares['issued_today']}",
                "sku": bin_row.get("sku"),
                "bin_id": bid,
                "for_asset": asset,
                "status": "staged",
            })
            spares["kits_staged"] = spares["kits_staged"][:20]
        _log(f"Issued {bin_row.get('sku')} from {bid} · qty {bin_row['qty']}")
        return True, f"Issued {bin_row.get('sku')}", c

    if op == "restock_spare":
        spares = c["spares"]
        bid = kwargs.get("bin_id") or kwargs.get("id")
        bin_row = next((b for b in (spares.get("bins") or []) if b.get("id") == bid), None)
        if not bin_row:
            return False, "Spare bin not found", c
        delta = max(1, int(kwargs.get("qty") or 1))
        bin_row["qty"] = int(bin_row.get("qty") or 0) + delta
        _log(f"Restocked {bid} +{delta} → {bin_row['qty']}")
        return True, f"{bid} qty {bin_row['qty']}", c

    if op == "quarantine_spare":
        spares = c["spares"]
        bid = kwargs.get("bin_id") or kwargs.get("id")
        bin_row = next((b for b in (spares.get("bins") or []) if b.get("id") == bid), None)
        if not bin_row:
            return False, "Spare bin not found", c
        if int(bin_row.get("qty") or 0) <= 0:
            return False, f"{bid} empty", c
        bin_row["qty"] = int(bin_row["qty"]) - 1
        spares.setdefault("quarantine", []).insert(0, {
            "id": f"Q-{bid}-{int(bin_row['qty'])}",
            "bin_id": bid,
            "sku": bin_row.get("sku"),
            "reason": kwargs.get("reason") or "failed_burnin",
            "time": _now(),
        })
        spares["quarantine"] = spares["quarantine"][:30]
        _log(f"Quarantined 1× {bin_row.get('sku')} from {bid}")
        return True, f"Quarantined {bin_row.get('sku')}", c

    if op == "repair_bay_swap":
        spares = c["spares"]
        kits = spares.get("kits_staged") or []
        kit_id = kwargs.get("kit_id") or kwargs.get("id")
        asset = kwargs.get("asset_id")
        kit = next((k for k in kits if k.get("id") == kit_id), None) if kit_id else None
        if kit is None and asset:
            kit = next((k for k in kits if k.get("for_asset") == asset and k.get("status") == "staged"), None)
        if kit is None and kits:
            kit = next((k for k in kits if k.get("status") == "staged"), kits[0])
        if not kit:
            return False, "No staged kit — issue from stockroom or receive RMA at dock first", c
        kit["status"] = "installed"
        kit["installed_at"] = _now()
        # Quarantine the failed part for RMA return.
        spares.setdefault("quarantine", []).insert(0, {
            "id": f"Q-SWAP-{kit.get('id')}",
            "sku": kwargs.get("failed_sku") or "failed-FRU",
            "reason": "replaced_at_repair_bay",
            "for_asset": kit.get("for_asset"),
            "ticket_id": kit.get("ticket_id"),
            "time": _now(),
        })
        spares["quarantine"] = spares["quarantine"][:30]
        _log(f"Repair bay installed {kit.get('sku')} on {kit.get('for_asset')} · kit {kit.get('id')}")
        return True, f"Installed {kit.get('sku')} on {kit.get('for_asset')}", c

    if op in ("start_chiller", "stop_chiller"):
        cid = kwargs.get("chiller_id") or kwargs.get("id")
        chillers = c.get("chillers") or []
        ch = next((x for x in chillers if x.get("id") == cid), None) if cid else None
        if not ch and chillers:
            # Prefer flipping a standby for start, a running for stop
            if op == "start_chiller":
                ch = next((x for x in chillers if x.get("status") == "standby"), chillers[0])
            else:
                running = [x for x in chillers if x.get("status") == "running"]
                ch = running[-1] if running else chillers[0]
        if not ch:
            return False, "No chiller found", c
        if op == "start_chiller":
            ch["status"] = "running"
            ch["cop"] = ch.get("cop") or 5.6
            _log(f"Chiller {ch['id']} started")
            return True, f"{ch['id']} running", c
        running = [x for x in chillers if x.get("status") == "running"]
        if len(running) <= 1 and ch.get("status") == "running":
            return False, "Keep at least one chiller online", c
        ch["status"] = "standby"
        ch["cop"] = None
        _log(f"Chiller {ch['id']} stopped → standby")
        return True, f"{ch['id']} standby", c

    if op == "note_xfmr_load":
        xid = kwargs.get("transformer_id") or kwargs.get("id")
        load = kwargs.get("load_pct")
        xfmr = next((x for x in (c.get("transformers") or []) if x.get("id") == xid), None) if xid else None
        if not xfmr:
            xfmr = (c.get("transformers") or [None])[0]
        if not xfmr:
            return False, "No transformer found", c
        if load is None:
            # Nudge ±2 for a live feel when operator "takes a reading"
            cur = int(xfmr.get("load_pct") or 50)
            load = max(5, min(95, cur + (3 if cur < 60 else -2)))
        xfmr["load_pct"] = int(load)
        xfmr["status"] = "online"
        _log(f"XFMR {xfmr['id']} load reading {xfmr['load_pct']}%")
        return True, f"{xfmr['id']} load {xfmr['load_pct']}%", c

    if op == "sync_battery":
        ups_list = pc.get("ups") or []
        soc = int(ups_list[0].get("battery_pct") or 100) if ups_list else 100
        on_batt = any(u.get("on_battery") for u in ups_list)
        for s in c.get("battery_strings") or []:
            s["soc_pct"] = soc
            s["status"] = "discharge" if on_batt else "float"
            s["temp_c"] = round(float(s.get("temp_c") or 22) + (0.4 if on_batt else -0.1), 1)
        _log(f"Battery strings synced · SoC {soc}% · {'discharge' if on_batt else 'float'}")
        return True, f"Battery SoC {soc}%", c

    if op == "parking_in":
        p = c.setdefault("parking", {"spaces": 48, "occupied": 0})
        if int(p.get("occupied") or 0) >= int(p.get("spaces") or 48):
            return False, "Parking full", c
        p["occupied"] = int(p.get("occupied") or 0) + 1
        _log(f"Vehicle badge-in · {p['occupied']}/{p['spaces']}")
        return True, f"Parking {p['occupied']}/{p['spaces']}", c

    if op == "parking_out":
        p = c.setdefault("parking", {"spaces": 48, "occupied": 0})
        if int(p.get("occupied") or 0) <= 0:
            return False, "Lot empty", c
        p["occupied"] = int(p.get("occupied") or 0) - 1
        _log(f"Vehicle exit · {p['occupied']}/{p['spaces']}")
        return True, f"Parking {p['occupied']}/{p['spaces']}", c

    return False, f"Unknown campus plant op: {op}", c
