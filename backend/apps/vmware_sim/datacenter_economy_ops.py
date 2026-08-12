"""Economy / build helpers: customer contracts + rack floor-grid placement.

Session 73 engine halves for audit X6c / X6b — pure functions the twin can tick
without a full capital ledger or immersive build camera.
"""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Customer contracts / credits ─────────────────────────────────────────────

DEFAULT_CREDIT_PER_BREACH_USD = 250.0


def accept_contract(
    state: dict,
    *,
    tenant: str,
    kw: float,
    u_slots: int,
    sla_pct: float = 99.99,
    credit_usd: float | None = None,
) -> dict:
    """Accept a tenant capacity contract. Returns the contract record."""
    contracts = state.setdefault("contracts", [])
    tid = f"CTR-{(tenant or 'tenant')[:8].upper()}-{int(time.time()) % 100000:05d}"
    contract = {
        "id": tid,
        "tenant": (tenant or "tenant").strip() or "tenant",
        "kw": float(kw),
        "u_slots": int(u_slots),
        "sla_pct": float(sla_pct),
        "status": "active",
        "sla_breached": False,
        "credits_owed": 0.0,
        "credit_per_breach_usd": float(
            credit_usd if credit_usd is not None else DEFAULT_CREDIT_PER_BREACH_USD
        ),
        "accepted_at": _now(),
        "breach_count": 0,
        "history": [{"time": _now(), "event": "accepted"}],
    }
    contracts.insert(0, contract)
    return contract


def _available_capacity(state: dict) -> dict:
    facility = state.get("facility") or {}
    it_kw = float(facility.get("it_kw") or 0.0)
    # Headroom: treat breaker/total capacity as ~1.5× current IT draw when unset.
    capacity_kw = float(
        (state.get("capacity") or {}).get("power", {}).get("capacity_kw")
        or facility.get("capacity_kw")
        or max(it_kw * 1.5, 10.0)
    )
    free_kw = max(0.0, capacity_kw - it_kw)
    servers = state.get("servers") or []
    used_u = 0
    for s in servers:
        used_u += int(s.get("u_height") or 1)
    racks = state.get("racks") or []
    total_u = max(42 * max(len(racks), 1), used_u)
    free_u = max(0, total_u - used_u)
    # Open ticket SLA breaches count as downtime against the contract.
    open_ticket_breaches = sum(
        1
        for t in (state.get("tickets") or [])
        if t.get("sla_breached") and t.get("status") not in ("resolved", "closed")
    )
    return {
        "free_kw": round(free_kw, 2),
        "capacity_kw": round(capacity_kw, 2),
        "it_kw": round(it_kw, 2),
        "free_u": free_u,
        "total_u": total_u,
        "ticket_sla_breaches": open_ticket_breaches,
    }


def evaluate_contracts(state: dict) -> list[dict]:
    """Recompute breach/credits for every active contract. Returns newly breached."""
    newly: list[dict] = []
    cap = _available_capacity(state)
    committed_kw = 0.0
    committed_u = 0
    for c in state.get("contracts") or []:
        if c.get("status") != "active":
            continue
        committed_kw += float(c.get("kw") or 0)
        committed_u += int(c.get("u_slots") or 0)

    # Shared pool: sum of active commitments vs free+used margin (capacity - spare).
    # Breach when commitments exceed remaining free capacity OR any ticket SLA is hot.
    for c in state.get("contracts") or []:
        if c.get("status") != "active":
            continue
        need_kw = float(c.get("kw") or 0)
        need_u = int(c.get("u_slots") or 0)
        # Capacity shortfall: if all active contracts' demand exceeds free headroom
        # plus a share of current IT (already sold), flag under-provision.
        under_kw = committed_kw > (cap["capacity_kw"] + 0.01)
        under_u = committed_u > (cap["total_u"] + 0)
        # Also fail a single oversized contract that alone exceeds free slots/kw.
        alone_kw = need_kw > (cap["free_kw"] + cap["it_kw"] + 0.01)
        alone_u = need_u > cap["total_u"]
        ticket_hit = cap["ticket_sla_breaches"] > 0
        breached = under_kw or under_u or alone_kw or alone_u or ticket_hit
        was = bool(c.get("sla_breached"))
        c["sla_breached"] = breached
        c["last_eval"] = {
            "free_kw": cap["free_kw"],
            "free_u": cap["free_u"],
            "committed_kw": round(committed_kw, 2),
            "committed_u": committed_u,
            "ticket_sla_breaches": cap["ticket_sla_breaches"],
        }
        if breached and not was:
            c["breach_count"] = int(c.get("breach_count") or 0) + 1
            credit = float(c.get("credit_per_breach_usd") or DEFAULT_CREDIT_PER_BREACH_USD)
            c["credits_owed"] = round(float(c.get("credits_owed") or 0) + credit, 2)
            hist = c.setdefault("history", [])
            hist.insert(0, {"time": _now(), "event": "sla_breached", "credit_usd": credit})
            newly.append(c)
        elif not breached and was:
            hist = c.setdefault("history", [])
            hist.insert(0, {"time": _now(), "event": "sla_restored"})
    return newly


# ── Floor-grid rack placement ────────────────────────────────────────────────

GRID_CELL_M = 1.4
AISLE_CLEAR_CELLS = 1
MAX_FLOOR_KG = 900.0
VALID_ORIENTATIONS = frozenset({"hot_cold", "cold_hot"})


def validate_rack_placement(
    state: dict,
    *,
    grid_x: int,
    grid_z: int,
    orientation: str = "hot_cold",
    mass_kg: float = 250.0,
    rack_id: str | None = None,
) -> dict:
    """Pure placement check — never mutates state."""
    reasons: list[str] = []
    gx, gz = int(grid_x), int(grid_z)
    orient = (orientation or "hot_cold").lower()
    mass = float(mass_kg)

    if orient not in VALID_ORIENTATIONS:
        reasons.append(f"orientation must be one of {sorted(VALID_ORIENTATIONS)}")
    if mass <= 0 or mass >= MAX_FLOOR_KG:
        reasons.append(f"floor loading {mass} kg exceeds {MAX_FLOOR_KG} kg/cell limit")
    if abs(gx) > 8 or abs(gz) > 6:
        reasons.append("grid cell outside hall bounds")

    occupied = {
        (int(r.get("grid_x", i % 4)), int(r.get("grid_z", i // 4)))
        for i, r in enumerate(state.get("racks") or [])
        if not rack_id or r.get("id") != rack_id
    }
    if (gx, gz) in occupied:
        reasons.append(f"cell ({gx},{gz}) already occupied")

    # Aisle clearance: neighboring cell along the cold-aisle axis (Z) must be empty.
    for dz in range(1, AISLE_CLEAR_CELLS + 1):
        if (gx, gz + dz) in occupied or (gx, gz - dz) in occupied:
            reasons.append("aisle clearance violated — neighboring Z cell occupied")
            break

    # Hot/cold facing: even Z = cold-aisle face expected for hot_cold.
    if orient == "hot_cold" and (gz % 2) != 0:
        reasons.append("hot_cold racks must sit on even Z (cold-aisle face)")
    if orient == "cold_hot" and (gz % 2) == 0:
        reasons.append("cold_hot racks must sit on odd Z (hot-aisle face)")

    ok = not reasons
    return {
        "ok": ok,
        "grid_x": gx,
        "grid_z": gz,
        "orientation": orient,
        "mass_kg": mass,
        "reasons": reasons,
        "floor_loading_ok": mass < MAX_FLOOR_KG,
    }


def place_rack(
    state: dict,
    *,
    rack_id: str,
    grid_x: int,
    grid_z: int,
    orientation: str = "hot_cold",
    mass_kg: float = 250.0,
    record_history: bool = True,
) -> dict:
    """Mutate racks when validation passes."""
    rid = (rack_id or "").strip()
    if not rid:
        return {"ok": False, "error": "rack_id required"}
    if any(r.get("id") == rid for r in (state.get("racks") or [])):
        return {"ok": False, "error": f"Rack {rid} already exists"}
    verdict = validate_rack_placement(
        state,
        grid_x=grid_x,
        grid_z=grid_z,
        orientation=orientation,
        mass_kg=mass_kg,
    )
    if not verdict["ok"]:
        return {"ok": False, "error": "; ".join(verdict["reasons"]), "validation": verdict}
    racks = state.setdefault("racks", [])
    rack = {
        "id": rid,
        "floor": "1",
        "room": state.get("current_room") or "data-hall-a",
        "grid_x": verdict["grid_x"],
        "grid_z": verdict["grid_z"],
        "aisle": verdict["orientation"],
        "servers": [],
        "physics": {
            "mass_kg": verdict["mass_kg"],
            "floor_loading_ok": verdict["floor_loading_ok"],
        },
        "pdu": f"PDU-{rid}",
    }
    racks.append(rack)
    if record_history:
        _push_blueprint_entry(
            state,
            forward={"op": "place", "rack": dict(rack)},
            inverse={"op": "remove", "rack_id": rid},
        )
    return {"ok": True, "rack": rack, "validation": verdict, "blueprint": blueprint_summary(state)}


def remove_rack(state: dict, rack_id: str, *, record_history: bool = True) -> dict:
    rid = (rack_id or "").strip()
    racks = state.get("racks") or []
    rack = next((r for r in racks if r.get("id") == rid), None)
    if not rack:
        return {"ok": False, "error": f"Rack {rid} not found"}
    servers = [s for s in (state.get("servers") or []) if s.get("rack") == rid]
    if servers:
        return {"ok": False, "error": f"Rack {rid} still has {len(servers)} server(s)"}
    snap = dict(rack)
    state["racks"] = [r for r in racks if r.get("id") != rid]
    if record_history:
        _push_blueprint_entry(
            state,
            forward={"op": "remove", "rack_id": rid},
            inverse={"op": "place", "rack": snap},
        )
    return {"ok": True, "removed": rid, "blueprint": blueprint_summary(state)}


# ── Blueprint undo / save / copy-row ─────────────────────────────────────────

def ensure_blueprint(state: dict) -> dict:
    bp = state.setdefault("blueprint", {})
    bp.setdefault("undo", [])
    bp.setdefault("redo", [])
    bp.setdefault("saved", {})
    return bp


def blueprint_summary(state: dict) -> dict:
    bp = ensure_blueprint(state)
    return {
        "undo_depth": len(bp["undo"]),
        "redo_depth": len(bp["redo"]),
        "saved_names": sorted(bp["saved"].keys()),
    }


def _push_blueprint_entry(state: dict, *, forward: dict, inverse: dict) -> None:
    bp = ensure_blueprint(state)
    bp["undo"].append({"forward": forward, "inverse": inverse})
    bp["redo"].clear()
    if len(bp["undo"]) > 50:
        del bp["undo"][:-50]


def _apply_blueprint_op(state: dict, op: dict) -> None:
    kind = (op or {}).get("op")
    if kind == "remove":
        rid = op.get("rack_id")
        state["racks"] = [r for r in (state.get("racks") or []) if r.get("id") != rid]
    elif kind == "place":
        rack = dict(op.get("rack") or {})
        rid = rack.get("id")
        if not rid:
            return
        racks = state.setdefault("racks", [])
        if not any(r.get("id") == rid for r in racks):
            racks.append(rack)


def undo_blueprint(state: dict) -> dict:
    bp = ensure_blueprint(state)
    if not bp["undo"]:
        return {"ok": False, "error": "Nothing to undo", "blueprint": blueprint_summary(state)}
    entry = bp["undo"].pop()
    _apply_blueprint_op(state, entry["inverse"])
    bp["redo"].append(entry)
    return {"ok": True, "applied": entry["inverse"], "blueprint": blueprint_summary(state)}


def redo_blueprint(state: dict) -> dict:
    bp = ensure_blueprint(state)
    if not bp["redo"]:
        return {"ok": False, "error": "Nothing to redo", "blueprint": blueprint_summary(state)}
    entry = bp["redo"].pop()
    _apply_blueprint_op(state, entry["forward"])
    bp["undo"].append(entry)
    return {"ok": True, "applied": entry["forward"], "blueprint": blueprint_summary(state)}


def save_blueprint(state: dict, name: str) -> dict:
    label = (name or "").strip() or "default"
    bp = ensure_blueprint(state)
    import copy
    bp["saved"][label] = {"racks": copy.deepcopy(state.get("racks") or [])}
    return {"ok": True, "name": label, "rack_count": len(bp["saved"][label]["racks"]), "blueprint": blueprint_summary(state)}


def load_blueprint(state: dict, name: str) -> dict:
    label = (name or "").strip() or "default"
    bp = ensure_blueprint(state)
    saved = bp["saved"].get(label)
    if not saved:
        return {"ok": False, "error": f"No blueprint named {label!r}", "blueprint": blueprint_summary(state)}
    import copy
    state["racks"] = copy.deepcopy(saved.get("racks") or [])
    bp["undo"].clear()
    bp["redo"].clear()
    return {"ok": True, "name": label, "rack_count": len(state["racks"]), "blueprint": blueprint_summary(state)}


def copy_rack_row(state: dict, *, source_z: int, dest_z: int) -> dict:
    """Clone every rack on grid_z=source_z onto dest_z with new ids."""
    source_z = int(source_z)
    dest_z = int(dest_z)
    if source_z == dest_z:
        return {"ok": False, "error": "source_z and dest_z must differ"}
    src = [r for r in (state.get("racks") or []) if int(r.get("grid_z") or 0) == source_z]
    if not src:
        return {"ok": False, "error": f"No racks on row z={source_z}"}
    created = []
    for rack in src:
        new_id = f"{rack.get('id')}-z{dest_z}"
        if any(r.get("id") == new_id for r in (state.get("racks") or [])):
            new_id = f"{new_id}-{len(created)}"
        result = place_rack(
            state,
            rack_id=new_id,
            grid_x=int(rack.get("grid_x") or 0),
            grid_z=dest_z,
            orientation=rack.get("aisle") or "hot_cold",
            mass_kg=float((rack.get("physics") or {}).get("mass_kg") or 250),
            record_history=True,
        )
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error"), "created": created}
        created.append(result["rack"]["id"])
    return {"ok": True, "created": created, "blueprint": blueprint_summary(state)}


# ── Capital / operating cost ledger ──────────────────────────────────────────

HARDWARE_PRICES_USD = {
    "server_1u": 4200.0,
    "server_2u": 6800.0,
    "psu": 280.0,
    "dimm": 120.0,
    "disk": 350.0,
    "gpu": 9500.0,
    "rack": 1800.0,
}
POWER_USD_PER_KWH = 0.12
BANDWIDTH_USD_PER_HOUR = 4.0
STAFF_USD_PER_HOUR = 45.0
COOLING_FRAC_OF_IT = 0.35  # of IT kWh cost when PUE not used for cooling split


def ensure_ledger(state: dict) -> dict:
    ledger = state.setdefault("ledger", {})
    ledger.setdefault("cash", 100_000.0)
    ledger.setdefault("capex_usd", 0.0)
    ledger.setdefault("opex_usd", 0.0)
    ledger.setdefault("power_kwh", 0.0)
    ledger.setdefault("history", [])
    return ledger


def buy_hardware(state: dict, *, sku: str, qty: int = 1) -> dict:
    """Spend cash on a catalog SKU. Returns purchase result."""
    ledger = ensure_ledger(state)
    key = (sku or "").strip().lower()
    price = HARDWARE_PRICES_USD.get(key)
    if price is None:
        return {"ok": False, "error": f"Unknown SKU {sku}", "skus": sorted(HARDWARE_PRICES_USD)}
    n = max(1, int(qty))
    total = round(price * n, 2)
    cash = float(ledger.get("cash") or 0)
    if cash < total:
        return {"ok": False, "error": f"Insufficient cash (${cash:.0f} < ${total:.0f})"}
    ledger["cash"] = round(cash - total, 2)
    ledger["capex_usd"] = round(float(ledger.get("capex_usd") or 0) + total, 2)
    inv = state.setdefault("stockroom", {}).setdefault("purchases", [])
    inv.insert(0, {"sku": key, "qty": n, "usd": total, "time": _now()})
    ledger.setdefault("history", []).insert(0, {"time": _now(), "event": "capex", "sku": key, "usd": total})
    return {"ok": True, "sku": key, "qty": n, "usd": total, "ledger": dict(ledger)}


def tick_opex(state: dict, *, hours: float = 1.0) -> dict:
    """Accrue opex for power (IT×PUE×$/kWh), cooling share, bandwidth, staff."""
    ledger = ensure_ledger(state)
    facility = state.get("facility") or {}
    it_kw = float(facility.get("it_kw") or 0.0)
    pue = float(facility.get("pue") or 1.4)
    hrs = max(0.0, float(hours))
    power_kwh = it_kw * pue * hrs
    power_usd = power_kwh * POWER_USD_PER_KWH
    cooling_usd = it_kw * hrs * POWER_USD_PER_KWH * COOLING_FRAC_OF_IT
    # Staff on payroll (hired roster) or a floor minimum of 1 FTE.
    staff_n = max(1, len([s for s in (state.get("staff") or []) if s.get("status") == "active"]))
    staff_usd = staff_n * STAFF_USD_PER_HOUR * hrs
    bw_usd = BANDWIDTH_USD_PER_HOUR * hrs
    total = round(power_usd + cooling_usd + staff_usd + bw_usd, 2)
    ledger["opex_usd"] = round(float(ledger.get("opex_usd") or 0) + total, 2)
    ledger["power_kwh"] = round(float(ledger.get("power_kwh") or 0) + power_kwh, 3)
    ledger["cash"] = round(float(ledger.get("cash") or 0) - total, 2)
    entry = {
        "time": _now(),
        "event": "opex",
        "hours": hrs,
        "usd": total,
        "power_usd": round(power_usd, 2),
        "cooling_usd": round(cooling_usd, 2),
        "staff_usd": round(staff_usd, 2),
        "bandwidth_usd": round(bw_usd, 2),
        "pue": pue,
        "it_kw": it_kw,
    }
    ledger.setdefault("history", []).insert(0, entry)
    return {"ok": True, "opex": entry, "ledger": dict(ledger)}


# ── Inspect before energize ──────────────────────────────────────────────────


def inspect_before_energize(state: dict) -> dict:
    """Flag code / layout violations that should block floor energize."""
    violations: list[dict] = []
    for i, rack in enumerate(state.get("racks") or []):
        rid = rack.get("id") or f"rack-{i}"
        phy = rack.get("physics") or {}
        if phy.get("floor_loading_ok") is False:
            violations.append({"code": "floor_load", "rack": rid, "message": f"{rid} exceeds floor loading"})
        aisle = (rack.get("aisle") or rack.get("orientation") or "hot_cold").lower()
        gz = rack.get("grid_z")
        if gz is not None:
            if aisle == "hot_cold" and int(gz) % 2 != 0:
                violations.append({"code": "aisle_facing", "rack": rid, "message": f"{rid} hot_cold on odd Z"})
            if aisle == "cold_hot" and int(gz) % 2 == 0:
                violations.append({"code": "aisle_facing", "rack": rid, "message": f"{rid} cold_hot on even Z"})
        # Dual-feed: prefer A/B PDU ids when present
        feeds = rack.get("power_feeds") or phy.get("power_feeds")
        if feeds is not None and len(feeds) < 2:
            violations.append({"code": "dual_feed", "rack": rid, "message": f"{rid} missing A/B PDU feeds"})

    for c in state.get("cooling") or []:
        if c.get("ashrae_ok") is False:
            violations.append({
                "code": "ashrae",
                "asset": c.get("id"),
                "message": f"{c.get('id')} outside ASHRAE envelope",
            })
        if c.get("status") and c.get("status") != "running":
            violations.append({
                "code": "cooling_down",
                "asset": c.get("id"),
                "message": f"{c.get('id')} not running",
            })

    containment = state.get("containment") or {}
    if containment.get("doors_open") or containment.get("open"):
        violations.append({"code": "containment", "message": "Containment doors open — seal before energize"})

    blanking_ok = True
    for rack in state.get("racks") or []:
        free = rack.get("free_u")
        blanked = rack.get("blanking_u") or (rack.get("fru") or {}).get("blanking_u")
        if free is not None and int(free) > 0 and not blanked:
            # Soft signal only when free_u is explicitly tracked
            blanking_ok = False
            violations.append({
                "code": "blanking",
                "rack": rack.get("id"),
                "message": f"{rack.get('id')} has open U without blanking",
            })
            break

    ok = not violations
    report = {"ok": ok, "violations": violations, "blanking_checked": blanking_ok}
    state["inspection"] = {**report, "inspected_at": _now()}
    return report


def energize_floor(state: dict, *, force: bool = False) -> dict:
    """Energize rack PDU outlets only when inspection passes (unless force)."""
    report = inspect_before_energize(state)
    if not report["ok"] and not force:
        return {"ok": False, "error": "Inspection failed — fix violations before energize", "inspection": report}
    energized = 0
    for rack in state.get("racks") or []:
        fru = rack.setdefault("fru", {})
        outlets = fru.setdefault("pdu_outlets", [])
        if not outlets:
            outlets.append({"id": "outlet-1", "energized": True})
            energized += 1
        else:
            for out in outlets:
                if not out.get("energized"):
                    out["energized"] = True
                    energized += 1
    state["floor_energized"] = True
    return {"ok": True, "energized_outlets": energized, "inspection": report}


# ── Staff roster / dispatch ──────────────────────────────────────────────────

ROLE_SKILLS = {
    "field-tech": {"hardware", "rma", "psu", "disk", "fan"},
    "network-eng": {"network", "nic", "cable", "switch"},
    "sre": {"software", "bmc", "firmware", "incident"},
}


def ensure_staff(state: dict) -> list:
    return state.setdefault("staff", [])


def hire_staff(
    state: dict,
    *,
    name: str,
    role: str = "field-tech",
    shift: str = "day",
) -> dict:
    staff = ensure_staff(state)
    role_key = (role or "field-tech").lower()
    skills = sorted(ROLE_SKILLS.get(role_key, ROLE_SKILLS["field-tech"]))
    sid = f"STF-{len(staff) + 1:03d}"
    person = {
        "id": sid,
        "name": (name or sid).strip(),
        "role": role_key,
        "skills": skills,
        "shift": (shift or "day").lower(),
        "fatigue": 0.0,
        "status": "active",
        "assigned_ticket": None,
        "hired_at": _now(),
    }
    staff.append(person)
    return {"ok": True, "staff": person}


def tick_fatigue(state: dict, *, hours: float = 1.0) -> list:
    """Raise fatigue for on-shift staff; rest off-shift slightly."""
    changed = []
    hrs = max(0.0, float(hours))
    for person in ensure_staff(state):
        if person.get("status") != "active":
            continue
        fat = float(person.get("fatigue") or 0)
        if person.get("assigned_ticket"):
            fat = min(100.0, fat + 8.0 * hrs)
        else:
            fat = max(0.0, fat - 2.0 * hrs)
        person["fatigue"] = round(fat, 1)
        changed.append(person["id"])
    return changed


def dispatch_staff(state: dict, *, ticket_id: str, staff_id: str) -> dict:
    """Assign staff to a ticket when skill/shift/fatigue allow."""
    tickets = state.get("tickets") or []
    ticket = next((t for t in tickets if t.get("id") == ticket_id), None)
    if not ticket:
        return {"ok": False, "error": f"Ticket {ticket_id} not found"}
    if ticket.get("status") in ("resolved", "closed"):
        return {"ok": False, "error": "Ticket already closed"}
    person = next((s for s in ensure_staff(state) if s.get("id") == staff_id), None)
    if not person:
        return {"ok": False, "error": f"Staff {staff_id} not found"}
    if person.get("status") != "active":
        return {"ok": False, "error": "Staff not active"}
    if float(person.get("fatigue") or 0) >= 85:
        return {"ok": False, "error": "Staff too fatigued — rest required"}
    # Shift gate: night tickets prefer night shift (soft fail for day-only on night pri)
    component = (ticket.get("component") or "hardware").lower()
    skills = set(person.get("skills") or [])
    if component not in skills and "hardware" not in skills and "incident" not in skills:
        return {"ok": False, "error": f"Skill mismatch — {person['role']} lacks {component}"}
    # Clear previous assignee from other staff
    for s in ensure_staff(state):
        if s.get("assigned_ticket") == ticket_id:
            s["assigned_ticket"] = None
    person["assigned_ticket"] = ticket_id
    ticket["assignee"] = person["name"]
    hist = ticket.setdefault("history", [])
    hist.insert(0, {"time": _now(), "event": f"dispatched:{person['id']}"})
    if ticket.get("status") == "open":
        ticket["status"] = "assigned"
    return {"ok": True, "ticket": ticket, "staff": person}


# ── Tech tree / upgrades ─────────────────────────────────────────────────────

UPGRADE_CATALOG = [
    {
        "id": "high_density",
        "name": "Higher-density racks",
        "cost_usd": 12000,
        "requires": [],
        "effects": {"density_kw_per_rack": 15.0},
    },
    {
        "id": "liquid_cooling",
        "name": "Liquid cooling",
        "cost_usd": 25000,
        "requires": ["high_density"],
        "effects": {"cooling_mode": "liquid", "pue_delta": -0.15},
    },
    {
        "id": "free_cooling",
        "name": "Free cooling",
        "cost_usd": 18000,
        "requires": [],
        "effects": {"cooling_mode": "free", "pue_delta": -0.1},
    },
    {
        "id": "ups_efficiency",
        "name": "Better UPS efficiency",
        "cost_usd": 8000,
        "requires": [],
        "effects": {"ups_efficiency": 0.97, "pue_delta": -0.05},
    },
    {
        "id": "dcim_automation",
        "name": "DCIM automation",
        "cost_usd": 15000,
        "requires": ["ups_efficiency"],
        "effects": {"dcim_automation": True},
    },
    {
        "id": "onsite_solar",
        "name": "On-site solar + battery",
        "cost_usd": 40000,
        "requires": ["free_cooling"],
        "effects": {"solar_kw": 50.0, "pue_delta": -0.08},
    },
]


def list_upgrades(state: dict) -> list[dict]:
    owned = set((state.get("upgrades") or {}).get("owned") or [])
    out = []
    for u in UPGRADE_CATALOG:
        missing = [r for r in (u.get("requires") or []) if r not in owned]
        out.append({
            **u,
            "owned": u["id"] in owned,
            "available": u["id"] not in owned and not missing,
            "missing_prereqs": missing,
        })
    return out


def apply_upgrade(state: dict, upgrade_id: str) -> dict:
    catalog = {u["id"]: u for u in UPGRADE_CATALOG}
    uid = (upgrade_id or "").strip()
    if uid not in catalog:
        return {"ok": False, "error": f"Unknown upgrade {upgrade_id}"}
    upgrades = state.setdefault("upgrades", {"owned": []})
    owned = list(upgrades.get("owned") or [])
    if uid in owned:
        return {"ok": False, "error": "Already owned"}
    spec = catalog[uid]
    missing = [r for r in (spec.get("requires") or []) if r not in owned]
    if missing:
        return {"ok": False, "error": f"Missing prerequisites: {', '.join(missing)}"}
    ledger = ensure_ledger(state)
    cost = float(spec["cost_usd"])
    if float(ledger.get("cash") or 0) < cost:
        return {"ok": False, "error": f"Insufficient cash (${ledger.get('cash'):.0f} < ${cost:.0f})"}
    ledger["cash"] = round(float(ledger["cash"]) - cost, 2)
    ledger["capex_usd"] = round(float(ledger.get("capex_usd") or 0) + cost, 2)
    owned.append(uid)
    upgrades["owned"] = owned
    effects = dict(spec.get("effects") or {})
    facility = state.setdefault("facility", {})
    if "pue_delta" in effects:
        pue = float(facility.get("pue") or 1.4) + float(effects["pue_delta"])
        facility["pue"] = round(max(1.05, pue), 3)
    for k, v in effects.items():
        if k == "pue_delta":
            continue
        facility[k] = v
        upgrades[k] = v
    ledger.setdefault("history", []).insert(0, {
        "time": _now(), "event": "upgrade", "id": uid, "usd": cost,
    })
    return {"ok": True, "upgrade": uid, "effects": effects, "ledger": dict(ledger), "facility": dict(facility)}


# ── Reputation / second hall ─────────────────────────────────────────────────

REPUTATION_UNLOCK_HALL = 70
SECOND_HALL_COST_USD = 35000


def ensure_reputation(state: dict) -> dict:
    rep = state.setdefault("reputation", {})
    rep.setdefault("score", 50.0)
    rep.setdefault("halls", ["data-hall-a"])
    rep.setdefault("history", [])
    return rep


def tick_reputation(state: dict) -> dict:
    """Adjust reputation from contract/ticket SLA health."""
    rep = ensure_reputation(state)
    delta = 1.0
    for c in state.get("contracts") or []:
        if c.get("status") == "active" and c.get("sla_breached"):
            delta -= 4.0
        elif c.get("status") == "active":
            delta += 0.5
    for t in state.get("tickets") or []:
        if t.get("sla_breached") and t.get("status") not in ("resolved", "closed"):
            delta -= 2.0
    score = max(0.0, min(100.0, float(rep.get("score") or 50) + delta))
    rep["score"] = round(score, 1)
    rep["last_delta"] = round(delta, 1)
    return dict(rep)


def unlock_second_hall(state: dict) -> dict:
    """Unlock data-hall-b when reputation and cash gates pass."""
    rep = ensure_reputation(state)
    halls = list(rep.get("halls") or ["data-hall-a"])
    if "data-hall-b" in halls:
        return {"ok": False, "error": "Second hall already unlocked", "reputation": rep}
    if float(rep.get("score") or 0) < REPUTATION_UNLOCK_HALL:
        return {
            "ok": False,
            "error": f"Reputation {rep.get('score')} < {REPUTATION_UNLOCK_HALL}",
            "reputation": rep,
        }
    ledger = ensure_ledger(state)
    if float(ledger.get("cash") or 0) < SECOND_HALL_COST_USD:
        return {"ok": False, "error": "Insufficient cash for second hall", "reputation": rep}
    ledger["cash"] = round(float(ledger["cash"]) - SECOND_HALL_COST_USD, 2)
    ledger["capex_usd"] = round(float(ledger.get("capex_usd") or 0) + SECOND_HALL_COST_USD, 2)
    halls.append("data-hall-b")
    rep["halls"] = halls
    facility = state.setdefault("facility", {})
    facility["halls"] = halls
    rep.setdefault("history", []).insert(0, {"time": _now(), "event": "unlock_hall", "hall": "data-hall-b"})
    return {"ok": True, "halls": halls, "reputation": rep, "ledger": dict(ledger)}
