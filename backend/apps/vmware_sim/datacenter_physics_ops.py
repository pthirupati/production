"""Phase 4–5: physics-lite, rack FRU, bus packet animation, ops tickets & metrics.

Formula-based facility physics (not Rapier). Rack bill-of-materials. Animated
bus util packets. Extended ticketing/RMA and Prometheus-style metric snapshots.
"""

from __future__ import annotations

import random
import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Physics-lite ───────────────────────────────────────────────────────────

SERVER_MASS_KG = {
    "esxi_host": 28.5,
    "db": 32.0,
    "gpu_node": 48.0,
    "storage": 38.0,
    None: 26.0,
}


def compute_rack_physics(rack: dict, servers: list[dict], cooling: list[dict], pdu: dict | None) -> dict:
    """Mass, CoG, tipping risk, heat, airflow, fan pressure for one rack."""
    rack_servers = [s for s in servers if s.get("rack") == rack.get("id")]
    empty_u = max(0, 42 - sum(1 if not s.get("u_height") else int(s.get("u_height") or 1) for s in rack_servers))
    # Rough: each occupied U ~ server mass; blanking adds little
    chassis_kg = 85.0  # empty APC-style frame
    server_kg = sum(SERVER_MASS_KG.get(s.get("role"), SERVER_MASS_KG[None]) for s in rack_servers)
    pdu_kg = 12.0
    total_kg = round(chassis_kg + server_kg + pdu_kg, 1)
    # Center of gravity height (mm from floor): heavier GPUs higher = risk
    cog_mm = 900
    if rack_servers:
        weighted = 0.0
        wsum = 0.0
        for s in rack_servers:
            m = SERVER_MASS_KG.get(s.get("role"), SERVER_MASS_KG[None])
            u = int(s.get("u_slot") or 1)
            height_mm = 100 + u * 44.45
            weighted += m * height_mm
            wsum += m
        cog_mm = int(weighted / wsum) if wsum else 900
    # Tip risk: CoG high + mass high + casters unlocked
    tip_score = min(100, int((cog_mm - 600) / 12 + (total_kg - 200) / 8))
    tip_risk = "low" if tip_score < 35 else ("medium" if tip_score < 65 else "high")

    # Heat: IT load from PDU + GPU penalty
    load_kw = float((pdu or {}).get("load_kw") or 4.0)
    gpu_extra = sum(1.2 for s in rack_servers if s.get("role") == "gpu_node")
    heat_kw = round(load_kw * 0.95 + gpu_extra, 2)
    inlet = 22.0
    for c in cooling or []:
        if c.get("status") == "running":
            inlet = min(inlet, float(c.get("temp_c") or 22))
        else:
            inlet = max(inlet, 28.0)
    delta_t = 8.0 + heat_kw * 0.7
    outlet_c = round(inlet + delta_t, 1)
    # Airflow CFM ≈ heat_kw * 200 / delta_t (rule of thumb)
    airflow_cfm = int(max(200, heat_kw * 180 / max(delta_t, 4)))
    # Fan pressure (mmH2O) scales with CFM and restriction from blanking
    blanking_u = empty_u
    restriction = 1.0 + max(0, (10 - blanking_u)) * 0.04  # missing blanking worsens
    fan_pressure = round(0.15 * (airflow_cfm / 100) * restriction, 2)
    vibration_mm_s = round(0.4 + (tip_score / 200) + (0.3 if any(s.get("role") == "gpu_node" for s in rack_servers) else 0), 2)
    thermal_expansion_um = round((outlet_c - 20) * 0.8, 1)  # stub µm on rail length

    return {
        "mass_kg": total_kg,
        "cog_height_mm": cog_mm,
        "tip_score": tip_score,
        "tip_risk": tip_risk,
        "heat_kw": heat_kw,
        "inlet_c": round(inlet, 1),
        "outlet_c": outlet_c,
        "airflow_cfm": airflow_cfm,
        "fan_pressure_mmH2O": fan_pressure,
        "vibration_mm_s": vibration_mm_s,
        "thermal_expansion_um": thermal_expansion_um,
        "casters_locked": True,
        "leveling_feet": True,
        "floor_loading_ok": total_kg < 900,
    }


def tick_bus_packets(motherboard: dict) -> None:
    """Animate bus util + packet counters for PCIe/DDR/UPI/IF/NVLink."""
    if not motherboard:
        return
    for bus in motherboard.get("buses") or []:
        util = int(bus.get("util_pct") or 20)
        util = max(5, min(98, util + random.randint(-6, 8)))
        bus["util_pct"] = util
        bus["packets_per_s"] = int(util * random.randint(800, 2200))
        bus["latency_ns"] = max(20, int(bus.get("latency_ns") or 80) + random.randint(-5, 8))
        if random.random() < 0.04:
            bus["errors"] = (bus.get("errors") or 0) + 1
        # Moving packet positions 0–100 for CSS animation
        packets = bus.setdefault("packets", [])
        if len(packets) < 5:
            packets.append({"id": f"p{len(packets)}", "pos": random.randint(0, 90)})
        for pkt in packets:
            pkt["pos"] = (pkt.get("pos", 0) + random.randint(8, 22)) % 100


def ensure_extended_buses(motherboard: dict) -> None:
    """Ensure Infinity Fabric / NVLink appear alongside PCIe/DDR/UPI."""
    if not motherboard:
        return
    buses = motherboard.setdefault("buses", [])
    have = {b.get("id") for b in buses}
    extras = [
        {"id": "Infinity_Fabric", "util_pct": 18, "errors": 0, "color": "#A855F7", "latency_ns": 45, "packets": []},
        {"id": "NVLink", "util_pct": 35, "errors": 0, "color": "#76B900", "latency_ns": 25, "packets": []},
        {"id": "PCIe_Gen5", "util_pct": 40, "errors": 0, "color": "#00FF88", "latency_ns": 60, "packets": []},
    ]
    for e in extras:
        if e["id"] not in have:
            buses.append(e)


# ── Rack FRU ───────────────────────────────────────────────────────────────

def build_rack_fru(rack_id: str) -> dict:
    """Cage nuts, rails, blanking, PDU outlets, labels, QR/warranty."""
    outlets = []
    for i in range(1, 25):
        outlets.append({
            "id": f"{rack_id}-OUT-{i:02d}",
            "type": "C13" if i <= 18 else "C19",
            "energized": True,
            "breaker": "closed",
            "load_w": random.randint(40, 380) if i <= 12 else 0,
            "led": "green" if i <= 12 else "off",
        })
    cage_nuts = [
        {"u": u, "front_left": True, "front_right": True, "rear_left": True, "rear_right": True}
        for u in range(1, 43)
    ]
    return {
        "manufacturer": "APC NetShelter SX",
        "model": "AR3100",
        "serial": f"RK{abs(hash(rack_id)) % 10_000_000:07d}",
        "asset_tag": f"RACK-{rack_id}",
        "qr_code": f"QR://fixitlab/{rack_id}",
        "warranty_sticker": {"vendor": "Schneider", "expires": "2028-03-01", "visible": True},
        "u_height": 42,
        "width_mm": 600,
        "depth_mm": 1070,
        "max_weight_kg": 1360,
        "rails": {
            "front": {"installed": True, "type": "M6 square-hole", "screws": 84},
            "rear": {"installed": True, "type": "M6 square-hole", "screws": 84},
            "slide_kits": 4,
        },
        "cage_nuts_installed": sum(
            1 for cn in cage_nuts for k in ("front_left", "front_right", "rear_left", "rear_right") if cn[k]
        ),
        "cage_nuts": cage_nuts[:8],  # sample for UI; full count above
        "washers": 168,
        "grounding_strap": {"installed": True, "torque_nm": 5.0, "status": "ok"},
        "airflow_baffles": [{"id": "BAF-TOP", "status": "installed"}, {"id": "BAF-BOT", "status": "installed"}],
        "blanking_panels": [
            {"u": u, "size_u": 1, "installed": True} for u in (3, 5, 7, 15, 20, 25, 30, 35)
        ],
        "cable_ties": 24,
        "velcro_straps": 12,
        "port_labels": True,
        "pdu_outlets": outlets,
        "leveling_feet_mm": [12, 12, 11, 12],
        "casters": {"present": True, "locked": True},
    }


def enrich_rack(rack: dict, servers: list[dict], cooling: list[dict], pdus: list[dict]) -> dict:
    pdu = next((p for p in (pdus or []) if p.get("rack") == rack.get("id") or p.get("id") == rack.get("pdu")), None)
    if not rack.get("fru"):
        rack["fru"] = build_rack_fru(rack["id"])
    from apps.vmware_sim.datacenter_plant_provision import densify_rack_fru
    rack["fru"] = densify_rack_fru(rack["fru"], rack["id"])
    rack["physics"] = compute_rack_physics(rack, servers, cooling, pdu)
    return rack


# ── Ops: tickets + monitoring (Phase 5 start) ──────────────────────────────

SUPPORT_VENDORS = (
    "Dell", "HPE", "Lenovo", "Supermicro", "Cisco", "NVIDIA",
    "Gigabyte", "ASUS", "Inspur", "Quanta", "Wiwynn", "Open Compute",
)

TICKET_TYPES = (
    "incident", "problem", "change", "rma", "field_visit",
    "maintenance_window", "warranty_lookup", "serial_lookup",
)


# Priority → response target (minutes). Mirrors ITSM SLA_MINUTES with string keys
# the twin UI already uses (medium/high/critical).
OPS_SLA_MINUTES = {
    "critical": 60,
    "high": 240,
    "medium": 480,
    "moderate": 480,
    "low": 1440,
    "planning": 2880,
}


def build_ops_ticket(
    *,
    vendor: str,
    ticket_type: str,
    asset_id: str | None,
    hostname: str | None,
    component: str,
    summary: str,
    service_tag: str | None = None,
    priority: str = "medium",
    now_ts: float | None = None,
) -> dict:
    vendor = vendor if vendor in SUPPORT_VENDORS else (vendor or "Dell")
    created_ts = float(now_ts if now_ts is not None else time.time())
    tid = f"{vendor[:4].upper()}-{ticket_type[:3].upper()}-{int(created_ts) % 100000:05d}"
    pri = (priority or "medium").lower()
    sla_minutes = int(OPS_SLA_MINUTES.get(pri, OPS_SLA_MINUTES["medium"]))
    due_ts = created_ts + sla_minutes * 60
    return {
        "id": tid,
        "type": ticket_type if ticket_type in TICKET_TYPES else "incident",
        "vendor": vendor,
        "asset_id": asset_id,
        "hostname": hostname,
        "component": component,
        "status": "open",
        "priority": pri,
        "summary": summary,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created_ts)),
        "created_ts": created_ts,
        "sla_minutes": sla_minutes,
        "sla_due": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(due_ts)),
        "sla_remaining_sec": sla_minutes * 60,
        "sla_breached": False,
        "service_tag": service_tag,
        "assignee": None,
        "escalation": 0,
        "rma": None,
        "rca": None,
        "maintenance_window": None,
        "history": [{"time": _now(), "event": "created"}],
    }


def refresh_ticket_sla(ticket: dict, now_ts: float | None = None) -> dict:
    """Recompute remaining/breach for an open ticket. Resolved/closed stay frozen."""
    now = float(now_ts if now_ts is not None else time.time())
    if ticket.get("status") in ("resolved", "closed"):
        ticket["sla_remaining_sec"] = 0
        return ticket
    pri = str(ticket.get("priority") or "medium").lower()
    sla_minutes = int(ticket.get("sla_minutes") or OPS_SLA_MINUTES.get(pri, 480))
    ticket["sla_minutes"] = sla_minutes
    created_ts = float(ticket.get("created_ts") or 0)
    if not created_ts:
        # Legacy tickets created before the SLA clock — treat as freshly opened.
        created_ts = now
        ticket["created_ts"] = created_ts
    due_ts = created_ts + sla_minutes * 60
    ticket["sla_due"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(due_ts))
    remaining = int(due_ts - now)
    ticket["sla_remaining_sec"] = max(0, remaining)
    was = bool(ticket.get("sla_breached"))
    ticket["sla_breached"] = remaining < 0
    if ticket["sla_breached"] and not was:
        hist = ticket.setdefault("history", [])
        hist.insert(0, {"time": _now(), "event": "sla_breached"})
    return ticket


def refresh_all_ticket_slas(state: dict, now_ts: float | None = None) -> list[dict]:
    """Tick every open ops ticket's SLA clock. Returns newly breached tickets."""
    newly: list[dict] = []
    for ticket in state.get("tickets") or []:
        before = bool(ticket.get("sla_breached"))
        refresh_ticket_sla(ticket, now_ts=now_ts)
        if ticket.get("sla_breached") and not before:
            newly.append(ticket)
    return newly


# Above this share of the rack breaker, pulling a redundant feed during a visit
# risks tripping the remaining one — the classic "maintenance caused the outage".
_WINDOW_LOAD_WARN_PCT = 70
_WINDOW_LOAD_BLOCK_PCT = 85


def assess_window_load(facility: dict | None, asset_id: str | None = None, rack: str | None = None) -> dict:
    """Judge a maintenance window against what the floor is actually carrying.

    Deliberately advisory: it returns a verdict and a reason, and never vetoes
    an action. Hard-blocking ops on live load would make labs that never
    expected a load conflict look broken rather than show a policy message.
    """
    facility = facility or {}
    it_kw = float(facility.get("it_kw") or 0.0)
    racks = facility.get("rack_loads") or {}
    target = rack
    if not target and asset_id:
        # Asset ids look like srv-r03-u08 → rack R03.
        parts = str(asset_id).split("-")
        if len(parts) >= 2 and parts[1][:1].lower() == "r":
            target = parts[1].upper()
    rack_pct = int(racks.get(target) or 0) if target else 0
    if rack_pct >= _WINDOW_LOAD_BLOCK_PCT:
        verdict, reason = "conflict", (
            f"{target} is at {rack_pct}% of breaker — shed load or schedule off-peak "
            "before pulling a feed"
        )
    elif rack_pct >= _WINDOW_LOAD_WARN_PCT:
        verdict, reason = "caution", f"{target} at {rack_pct}% of breaker — no headroom for a feed loss"
    else:
        verdict, reason = "clear", "Load within safe margin for the window"
    return {
        "rack": target,
        "rack_load_pct": rack_pct,
        "it_kw_at_schedule": round(it_kw, 2),
        "load_verdict": verdict,
        "load_reason": reason,
    }


def advance_ticket(ticket: dict, action: str, **kwargs) -> dict:
    """assign | escalate | ship_rma | schedule_visit | add_rca | resolve | close."""
    hist = ticket.setdefault("history", [])
    if action == "assign":
        ticket["assignee"] = kwargs.get("engineer") or "field-eng-01"
        ticket["status"] = "assigned"
        hist.insert(0, {"time": _now(), "event": f"assigned:{ticket['assignee']}"})
    elif action == "escalate":
        ticket["escalation"] = int(ticket.get("escalation") or 0) + 1
        ticket["priority"] = "critical" if ticket["escalation"] >= 2 else "high"
        ticket["sla_minutes"] = OPS_SLA_MINUTES.get(ticket["priority"], 60)
        # Escalate tightens the remaining window from *now*, not the original open.
        ticket["created_ts"] = time.time()
        refresh_ticket_sla(ticket)
        hist.insert(0, {"time": _now(), "event": f"escalated L{ticket['escalation']}"})
    elif action == "ship_rma":
        ticket["type"] = "rma"
        rma_number = f"RMA-{int(time.time()) % 1000000:06d}"
        part = kwargs.get("part") or ticket.get("component") or "FRU"
        ticket["rma"] = {
            "rma_number": rma_number,
            "part": part,
            "carrier": kwargs.get("carrier") or "FedEx",
            "eta_days": int(kwargs.get("eta_days") or 2),
            "status": "parts_shipped",
            "asset_id": ticket.get("asset_id"),
            "ticket_id": ticket.get("id"),
        }
        ticket["status"] = "awaiting_parts"
        # Hint for facility dock enqueue (engine wires ASN onto campus).
        ticket["_pending_dock_asn"] = {
            "carrier": ticket["rma"]["carrier"],
            "contents": f"{part} · {rma_number}",
            "ticket_id": ticket.get("id"),
            "asset_id": ticket.get("asset_id"),
            "rma_number": rma_number,
            "sku": kwargs.get("sku") or part,
        }
        hist.insert(0, {"time": _now(), "event": f"rma:{rma_number}"})
    elif action == "schedule_visit":
        ticket["type"] = "field_visit"
        window = {
            "start": kwargs.get("start") or _now(),
            "duration_min": int(kwargs.get("duration_min") or 120),
            "engineer": kwargs.get("engineer") or "field-eng-01",
        }
        # The window is only meaningful if it knows what the floor is doing.
        window.update(assess_window_load(kwargs.get("facility"), ticket.get("asset_id"), kwargs.get("rack")))
        ticket["maintenance_window"] = window
        ticket["status"] = "scheduled"
        hist.insert(0, {
            "time": _now(),
            "event": f"field_visit_scheduled:{window['load_verdict']}",
        })
    elif action == "add_rca":
        ticket["rca"] = {
            "root_cause": kwargs.get("root_cause") or "Component wear-out",
            "corrective_action": kwargs.get("corrective") or "Replace FRU and update firmware",
            "author": kwargs.get("author") or "sre-01",
            "time": _now(),
        }
        ticket["type"] = "problem"
        hist.insert(0, {"time": _now(), "event": "rca_attached"})
    elif action == "resolve":
        ticket["status"] = "resolved"
        hist.insert(0, {"time": _now(), "event": "resolved"})
    elif action == "close":
        ticket["status"] = "closed"
        hist.insert(0, {"time": _now(), "event": "closed"})
    else:
        raise ValueError(f"Unknown ticket action: {action}")
    return ticket


def build_monitoring_snapshot(state: dict) -> dict:
    """Prometheus / DCGM / SNMP / Redfish style metric facade."""
    servers = state.get("servers") or []
    cooling = state.get("cooling") or []
    pdus = state.get("pdus") or state.get("power_chain", {}).get("rack_pdus") or []
    facility = state.get("facility") or {}
    alerts = []
    series = {
        "node_cpu_celsius": [],
        "node_power_watts": [],
        "dcgm_gpu_utilization": [],
        "snmp_pdu_amps": [],
        "redfish_inlet_c": [],
        "crac_supply_c": [],
    }
    for s in servers:
        bmc = s.get("bmc") or {}
        sensors = bmc.get("sensors") or {}
        inlet = sensors.get("inlet_c") or 22
        series["redfish_inlet_c"].append({"instance": s.get("hostname"), "value": inlet})
        series["node_cpu_celsius"].append({"instance": s.get("hostname"), "value": sensors.get("cpu1_c") or 45})
        series["node_power_watts"].append({
            "instance": s.get("hostname"),
            "value": (sensors.get("psu1_w") or 0) + (sensors.get("psu2_w") or 0),
        })
        if s.get("role") == "gpu_node":
            util = 72 if s.get("components", {}).get("gpu") == "healthy" else 0
            series["dcgm_gpu_utilization"].append({"instance": s.get("hostname"), "value": util})
            if s.get("components", {}).get("gpu") != "healthy":
                alerts.append({
                    "severity": "critical",
                    "alertname": "GPUFault",
                    "instance": s.get("hostname"),
                    "summary": "GPU component failed",
                })
        for k, v in (s.get("components") or {}).items():
            if v != "healthy":
                alerts.append({
                    "severity": "warning",
                    "alertname": f"Component{k.title()}Failed",
                    "instance": s.get("hostname"),
                    "summary": f"{k} is {v}",
                })
    for p in pdus:
        series["snmp_pdu_amps"].append({
            "instance": p.get("id"),
            "value": round(float(p.get("load_kw") or 0) * 1000 / 208 / 1.732, 1),
        })
        if p.get("status") != "online":
            alerts.append({"severity": "critical", "alertname": "PDUOffline", "instance": p.get("id"), "summary": "PDU breaker open"})
    for c in cooling:
        series["crac_supply_c"].append({"instance": c.get("id"), "value": c.get("temp_c")})
        if not c.get("ashrae_ok", True):
            alerts.append({"severity": "warning", "alertname": "ASHRAEBreach", "instance": c.get("id"), "summary": "Out of ASHRAE range"})

    return {
        "scraped_at": _now(),
        "exporters": ["node_exporter", "dcgm-exporter", "snmp_exporter", "redfish_exporter", "alertmanager"],
        "series": series,
        "alerts": alerts[:40],
        "pue": facility.get("pue"),
        "it_kw": facility.get("it_kw"),
        "targets_up": 12 - min(5, len([a for a in alerts if a["severity"] == "critical"])),
        "targets_total": 12,
    }


def build_training_scenarios() -> list[dict]:
    return [
        {"id": "dc-tech", "role": "New datacenter technician", "steps": ["Badge in", "Enter data hall", "Open rack", "Replace PSU", "Clear ticket"]},
        {"id": "linux-eng", "role": "Linux engineer", "steps": ["Attach serial", "BIOS POST", "Boot OS", "Check dmesg via console"]},
        {"id": "net-eng", "role": "Network engineer", "steps": ["Enter MDF", "show interfaces", "Fix VLAN", "ping/traceroute"]},
        {"id": "platform", "role": "Platform engineer", "steps": ["Inventory CMDB", "Firmware flash", "Validate BMC"]},
        {"id": "sre", "role": "SRE", "steps": ["Review alerts", "Open incident", "RCA", "Close change"]},
        {"id": "devops", "role": "DevOps engineer", "steps": ["PXE boot", "Virtual media ISO", "Verify storage"]},
        {"id": "gpu-eng", "role": "GPU infrastructure engineer", "steps": ["Check DCGM", "NVLink bus", "Replace GPU FRU"]},
        {"id": "bare-metal", "role": "Bare-metal engineer", "steps": ["Service mode", "CPU paste", "Rails extend", "POST"]},
        {"id": "cloud-support", "role": "Cloud support engineer", "steps": ["Vendor ticket", "Serial lookup", "RMA ship"]},
        # Troubleshooting drills — training_start auto-injects `inject` preset
        {
            "id": "ts-psu",
            "role": "Troubleshoot — Failed PSU",
            "inject": "psu",
            "steps": ["Confirm power alert", "Open RMA / ticket", "Replace PSU FRU", "Verify redundant power", "Clear fault"],
        },
        {
            "id": "ts-dimm",
            "role": "Troubleshoot — DIMM / ECC",
            "inject": "dimm",
            "steps": ["Review BMC SEL / ECC", "Identify failed slot", "Replace DIMM", "Clear fault"],
        },
        {
            "id": "ts-raid",
            "role": "Troubleshoot — RAID degraded",
            "inject": "raid",
            "steps": ["Confirm predictive failure", "Fail / rebuild disk", "Validate VD optimal", "Clear fault"],
        },
        {
            "id": "ts-cooling",
            "role": "Troubleshoot — Cooling failure",
            "inject": "cooling",
            "steps": ["Check ASHRAE / CRAC", "Restore cooling unit", "Confirm inlet temps", "Clear fault"],
        },
        {
            "id": "ts-fiber",
            "role": "Troubleshoot — Fiber cut",
            "inject": "fiber",
            "steps": ["Locate trunk fault", "Splice / repair fiber", "Verify link up", "Clear fault"],
        },
        {
            "id": "ts-ups",
            "role": "Troubleshoot — UPS failure",
            "inject": "ups",
            "steps": ["Confirm on-battery", "Start generator / restore utility", "Sync battery strings", "Clear fault"],
        },
    ]
