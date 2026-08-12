"""In-memory physical Data Center Infrastructure Management (DCIM) facility.

Server-authoritative, session-cached (Django cache / Redis) mirror of a
multi-room physical datacenter floor: a Data Hall, a Network/MDF room, a
Mechanical (cooling) room and an Electrical room. Racks hold servers in
numbered U slots with component-level health (power supply, NIC, disk,
motherboard, CPU, GPU) and a per-server BMC (Redfish/IPMI) facade. Power flows
utility -> ATS -> generator -> UPS -> floor PDU -> rack PDU, and cooling is
modeled with CRAC units against an ASHRAE comfort envelope. A "field tech" lab
walks the floor, opens a server's BMC console, and physically replaces or
power-cycles failed hardware — mirroring hands-on break/fix work instead of a
software console. Everything below is 100% in-memory/computed state; there is
no real hardware behind it.
"""

from __future__ import annotations

import copy
import json
import time

from django.core.cache import cache

SESSION_TTL = 7200

# Data Hall A holds the general-purpose compute racks; the Network/MDF room
# hosts the core/aggregation switch racks.
_DATA_HALL_RACKS = [f"R{i:02d}" for i in range(1, 9)]
_MDF_RACKS = ["R09", "R10"]
_RACKS = _DATA_HALL_RACKS + _MDF_RACKS

# Component keys tracked per server; each has a status of "healthy" or "failed".
_COMPONENT_KEYS = (
    "power", "nic", "disk", "motherboard", "cpu", "gpu",
    "fan", "dimm", "pcie", "raid", "hba",
)


def _hardware_inventory(hostname: str, *, vendor: str = "Dell", role: str | None = None, model: str | None = None) -> dict:
    """Detailed server bill-of-materials for the Hardware drawer (vendor-aware)."""
    from apps.vmware_sim.datacenter_digital_twin import build_motherboard, build_raid

    v = (vendor or "Dell").upper()
    mb = build_motherboard(vendor or "Dell")
    raid = build_raid(vendor or "Dell")
    bmc_label = {
        "HPE": "iLO 5 / Redfish", "HP": "iLO 5 / Redfish",
        "LENOVO": "XClarity Controller / Redfish",
        "SUPERMICRO": "IPMI AST2600 / Redfish",
        "CISCO": "Cisco IMC / Redfish",
        "GIGABYTE": "AMI BMC / Redfish",
    }.get(v, "iDRAC9 / Redfish")
    board = mb.get("model") or "ServerBoard"
    raid_model = (raid.get("controller") or "PERC H755").split("/")[0].strip()
    cpu_die = ((mb.get("cpu_sockets") or [{}])[0].get("die")) or "Intel Xeon Gold 6338"
    gpu = "NVIDIA H100 80GB" if role == "gpu_node" else "NVIDIA A40"
    return {
        "motherboard": {
            "model": board, "bios": "3.4", "uefi": True, "tpm": "2.0",
            "bmc": bmc_label, "secure_boot": True, "chassis_model": model or board,
        },
        "cpus": [
            {"socket": 0, "model": cpu_die, "cores": 32, "threads": 64, "numa_node": 0},
            {"socket": 1, "model": cpu_die, "cores": 32, "threads": 64, "numa_node": 1},
        ],
        "dimms": [
            {"slot": f"A{i}", "size_gb": 32, "type": "DDR4-3200 ECC", "status": "healthy"}
            for i in range(1, 9)
        ],
        "pcie": [
            {"slot": "PCIe-1", "device": "NIC", "model": "Mellanox ConnectX-6 25GbE", "lanes": "x8"},
            {"slot": "PCIe-2", "device": "RAID", "model": raid_model, "lanes": "x8"},
            {"slot": "PCIe-3", "device": "HBA", "model": "Emulex LPe32002 FC32", "lanes": "x8"},
            {"slot": "PCIe-4", "device": "GPU", "model": gpu, "lanes": "x16"},
        ],
        "storage": [
            {"bay": 0, "model": "Samsung PM9A3", "size_gb": 1920, "bus": "NVMe", "status": "healthy"},
            {"bay": 1, "model": "Samsung PM9A3", "size_gb": 1920, "bus": "NVMe", "status": "healthy"},
            {"bay": 2, "model": "Seagate Exos", "size_gb": 4000, "bus": "SAS", "status": "healthy"},
        ],
        "psus": [
            {"id": "PSU1", "watts": 1400 if role != "gpu_node" else 2200, "redundant": True, "status": "healthy"},
            {"id": "PSU2", "watts": 1400 if role != "gpu_node" else 2200, "redundant": True, "status": "healthy"},
        ],
        "fans": [
            {"id": f"FAN{i}", "rpm": 7200 + i * 50, "status": "healthy"} for i in range(1, 7)
        ],
        "cables": [
            {"id": "NIC0-front", "type": "DAC", "port": "eth0", "status": "seated"},
            {"id": "NIC1-rear", "type": "fiber", "port": "eth1", "status": "seated"},
            {"id": "FC0", "type": "fiber", "port": "fc0", "status": "seated"},
        ],
        "hostname": hostname,
        "vendor": vendor or "Dell",
    }


def _normalize_support_vendor(vendor: str) -> str:
    from apps.vmware_sim.datacenter_physics_ops import SUPPORT_VENDORS
    raw = (vendor or "Dell").strip()
    low = raw.lower()
    aliases = {
        "hp": "HPE", "hewlett": "HPE", "hewlett-packard": "HPE",
        "dell emc": "Dell", "dellemc": "Dell",
        "super micro": "Supermicro", "smci": "Supermicro",
        "ocp": "Open Compute", "opencompute": "Open Compute",
    }
    if low in aliases:
        return aliases[low]
    for v in SUPPORT_VENDORS:
        if v.lower() == low:
            return v
    # Title-case unknown OEMs rather than forcing Dell
    return raw[:1].upper() + raw[1:] if raw else "Dell"


def _apply_thermal_to_zone(state: dict, *, inlet_c: float, exhaust_c: float, fans_rpm: int) -> None:
    """Push facility thermal stress into BMC sensors for all powered servers."""
    for srv in state.get("servers") or []:
        bmc = srv.setdefault("bmc", {})
        sensors = bmc.setdefault("sensors", {})
        if srv.get("power_state") != "on":
            continue
        sensors["inlet_c"] = round(inlet_c, 1)
        sensors["exhaust_c"] = round(exhaust_c, 1)
        sensors["fans_rpm"] = fans_rpm
        sensors["cpu1_c"] = round(inlet_c + 26, 1)
        sensors["cpu2_c"] = round(inlet_c + 28, 1)


def _sync_rack_pdus(state: dict) -> None:
    """Keep top-level pdus list aligned with power_chain.rack_pdus."""
    rack_pdus = (state.get("power_chain") or {}).get("rack_pdus") or []
    state["pdus"] = rack_pdus
    from apps.vmware_sim.datacenter_physics_ops import enrich_rack
    cooling = state.get("cooling") or []
    for rack in state.get("racks") or []:
        enrich_rack(rack, state.get("servers") or [], cooling, rack_pdus)


def _session_key(session_id: str) -> str:
    return f"datacenter_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is not None:
        return json.loads(data) if isinstance(data, str) else data
    # Cache-cold fallback: recover from LabSession.simulation_snapshot["datacenter"]
    return _load_from_snapshot(session_id)


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)
    _mirror_to_snapshot(session_id, entry)


def _load_from_snapshot(session_id: str) -> dict | None:
    try:
        from apps.labs.models import LabSession

        snap = (
            LabSession.objects.filter(pk=session_id)
            .values_list("simulation_snapshot", flat=True)
            .first()
        )
        if isinstance(snap, dict):
            entry = snap.get("datacenter")
            if isinstance(entry, dict) and entry.get("state"):
                return copy.deepcopy(entry)
    except Exception:  # pragma: no cover - defensive (no DB row / migration)
        return None
    return None


def _mirror_to_snapshot(session_id: str, entry: dict) -> None:
    """Persist datacenter twin state into LabSession.simulation_snapshot["datacenter"]."""
    try:
        from apps.labs.models import LabSession

        row = LabSession.objects.filter(pk=session_id).only("id", "simulation_snapshot").first()
        if not row:
            return
        snap = row.simulation_snapshot if isinstance(row.simulation_snapshot, dict) else {}
        snap = dict(snap)
        snap["datacenter"] = json.loads(json.dumps(entry, default=str))
        LabSession.objects.filter(pk=session_id).update(simulation_snapshot=snap)
    except Exception:  # pragma: no cover - defensive (unsaved session in tests)
        pass


JOURNAL_MAX = 200


def _twin_journal(state: dict, action: str, payload: dict | None = None) -> None:
    """Append a replayable action envelope to the digital-twin journal."""
    if (payload or {}).get("_replay"):
        return
    clean = {k: v for k, v in (payload or {}).items() if not str(k).startswith("_")}
    journal = state.setdefault("digital_twin", {}).setdefault("persisted_changes", [])
    journal.insert(0, {"time": _now_iso(), "action": action, "payload": clean})
    del journal[JOURNAL_MAX:]


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message, "severity": severity})


# ── Rooms / building layout ───────────────────────────────────────────────

def _rooms() -> list[dict]:
    from apps.vmware_sim.datacenter_digital_twin import campus_rooms
    hall = list(_DATA_HALL_RACKS)
    mdf = list(_MDF_RACKS)
    rooms = campus_rooms()
    for r in rooms:
        if r["id"] == "data-hall-a":
            r["racks"] = hall
            r["aisle"] = "hot_cold"
        elif r["id"] == "mdf":
            r["racks"] = mdf
        elif r.get("racks") is None:
            r["racks"] = []
    return rooms


def _campus() -> dict:
    from apps.vmware_sim.datacenter_digital_twin import campus_assets
    return campus_assets()


def _room_for_rack(rooms: list[dict], rack_id: str | None) -> str:
    for room in rooms:
        if rack_id and rack_id in (room.get("racks") or []):
            return room["id"]
    return "data-hall-a"


# ── BMC facade ─────────────────────────────────────────────────────────────

def _bmc(hostname: str, power_state: str, *, inlet_c: float = 22.1, exhaust_c: float = 34.0,
         fans_rpm: int = 4200, protocol: str = "redfish", vendor: str = "Dell") -> dict:
    from apps.vmware_sim.datacenter_digital_twin import build_bmc
    bmc = build_bmc(hostname, vendor, power_state)
    bmc["protocol"] = protocol
    bmc["sensors"]["inlet_c"] = inlet_c
    bmc["sensors"]["exhaust_c"] = exhaust_c
    bmc["sensors"]["fans_rpm"] = fans_rpm
    return bmc


def _server(asset_id: str, rack: str, u_slot: int, hostname: str, **overrides) -> dict:
    from apps.vmware_sim.datacenter_digital_twin import enrich_server
    from apps.vmware_sim.datacenter_hardware_catalog import fleet_profile_for
    components = {k: "healthy" for k in _COMPONENT_KEYS}
    components.update(overrides.pop("components", {}))
    power_state = overrides.get("power_state", "on")
    role = overrides.pop("role", None)
    bmc_override = overrides.pop("bmc", None)
    rack_num = int("".join(ch for ch in rack if ch.isdigit()) or "1")
    vendor_override = overrides.pop("vendor", None)
    profile = fleet_profile_for(vendor=vendor_override, rack_num=rack_num)
    vendor = profile["vendor"]
    model = overrides.pop("model", None) or profile["model"]
    prefix = profile["tag_prefix"]
    service_tag = overrides.pop("service_tag", f"{prefix}{abs(hash(asset_id)) % 10_000_000:07d}")
    bmc = bmc_override or _bmc(hostname, power_state, vendor=vendor)
    server = {
        "id": asset_id,
        "rack": rack,
        "u_slot": u_slot,
        "hostname": hostname,
        "power_state": power_state,
        "components": components,
        "bmc": bmc,
        "vendor": vendor,
        "service_tag": service_tag,
        "model": model,
        "hardware": _hardware_inventory(hostname, vendor=vendor, role=role, model=model),
        "firmware_version": overrides.pop("firmware_version", "2.12.0"),
        **({"role": role} if role else {}),
        **{k: v for k, v in overrides.items() if k != "power_state"},
    }
    return enrich_server(server)


# ── Power chain ────────────────────────────────────────────────────────────

# Steady-state draw per powered-on server, by role. Loosely tracks real 2U
# hardware: a GPU node with 2x2200W PSUs pulls multiples of an app node.
_ROLE_DRAW_KW = {
    "esxi_host": 1.45,
    "db": 1.7,
    "gpu_node": 4.6,
    "storage": 1.55,
    "app": 1.3,
    "cache": 1.1,
    None: 1.2,
}
# A powered-off server still draws BMC/standby power — the PSU is live.
_STANDBY_DRAW_KW = 0.35
# ToR switch + rack fans + PDU conversion loss on any populated rack.
_RACK_OVERHEAD_KW = 0.8
# MDF racks hold switching gear that is not modelled as a server object.
_MDF_GEAR_KW = 1.6
# Breaker trips above this; 208V/30A single-phase derated to 80% ≈ 5.0 kW.
RACK_BREAKER_KW = 5.8
# Continuous branch-circuit derate (NEC 80%) — used for cascade warnings only.
RACK_BREAKER_CONTINUOUS_KW = round(RACK_BREAKER_KW * 0.8, 2)


def rack_load_kw(rack_id: str, servers: list[dict]) -> float:
    """Actual draw for one rack, summed from the servers physically in it.

    Replaces a hardcoded 4.2 kW so that racking, powering off, or losing a
    server visibly moves power, heat and PUE instead of decorating the panel.
    """
    rack_servers = [s for s in servers or [] if s.get("rack") == rack_id]
    total = 0.0
    for s in rack_servers:
        if s.get("power_state") == "on":
            total += _ROLE_DRAW_KW.get(s.get("role"), _ROLE_DRAW_KW[None])
        else:
            total += _STANDBY_DRAW_KW
    if rack_servers:
        total += _RACK_OVERHEAD_KW
    elif rack_id in _MDF_RACKS:
        total += _MDF_GEAR_KW
    return round(total, 2)


def _rack_pdus(servers: list[dict] | None = None) -> list[dict]:
    """Build A/B dual-feed PDUs per rack (audit D14).

    Legacy id ``PDU-{rack}`` is feed A so existing trip/restore labs keep working.
    Feed B is ``PDU-{rack}-B``. Servers without ``power_feeds`` stay single-corded
    on A (trip A still kills them); dual-corded servers list ``["A","B"]``.
    """
    pdus = []
    for r in _RACKS:
        load_kw = rack_load_kw(r, servers or [])
        # Default single-corded world: all load on A.
        pdus.append({
            "id": f"PDU-{r}",
            "rack": r,
            "feed": "A",
            "status": "online",
            "breaker": "closed",
            "rating_kw": RACK_BREAKER_KW,
            "load_pct": int(min(100, round(load_kw / RACK_BREAKER_KW * 100))),
            "load_kw": load_kw,
        })
        pdus.append({
            "id": f"PDU-{r}-B",
            "rack": r,
            "feed": "B",
            "status": "online",
            "breaker": "closed",
            "rating_kw": RACK_BREAKER_KW,
            "load_pct": 0,
            "load_kw": 0.0,
        })
    return pdus


def _server_feeds(server: dict) -> list[str]:
    feeds = server.get("power_feeds")
    if isinstance(feeds, list) and feeds:
        return [str(f).upper() for f in feeds]
    # Legacy / default: single-corded on A.
    return ["A"]


def _redistribute_pdu_loads(state: dict) -> list[dict]:
    """Recompute per-feed load and auto-trip breakers that exceed rating.

    Returns list of PDUs that newly tripped (for events / cascade).
    """
    rack_pdus = state.get("power_chain", {}).get("rack_pdus", []) or []
    servers = state.get("servers") or []
    # Ensure every rack has a B feed (sessions seeded before dual-feed).
    by_rack: dict[str, dict[str, dict]] = {}
    for p in rack_pdus:
        rack = p.get("rack")
        feed = (p.get("feed") or ("B" if str(p.get("id", "")).endswith("-B") else "A")).upper()
        p["feed"] = feed
        p.setdefault("rating_kw", RACK_BREAKER_KW)
        by_rack.setdefault(rack, {})[feed] = p
    for rack in list({p.get("rack") for p in rack_pdus}):
        feeds = by_rack.setdefault(rack, {})
        if "B" not in feeds:
            b = {
                "id": f"PDU-{rack}-B", "rack": rack, "feed": "B",
                "status": "online", "breaker": "closed",
                "rating_kw": RACK_BREAKER_KW, "load_pct": 0, "load_kw": 0.0,
            }
            rack_pdus.append(b)
            feeds["B"] = b
        if "A" not in feeds:
            a = next((p for p in rack_pdus if p.get("rack") == rack and p.get("feed") == "A"), None)
            if a:
                feeds["A"] = a

    # Zero loads then accumulate from servers that can still draw from a closed feed.
    for p in rack_pdus:
        p["load_kw"] = 0.0

    for srv in servers:
        rack = srv.get("rack")
        feeds = by_rack.get(rack) or {}
        wanted = _server_feeds(srv)
        live = [
            f for f in wanted
            if feeds.get(f)
            and feeds[f].get("breaker") == "closed"
            and feeds[f].get("status") == "online"
        ]
        if not live:
            # No live feed → server is dark.
            if srv.get("power_state") == "on":
                srv["power_state"] = "off"
                if isinstance(srv.get("bmc"), dict):
                    srv["bmc"]["power"] = "off"
            continue
        draw = (
            _ROLE_DRAW_KW.get(srv.get("role"), _ROLE_DRAW_KW[None])
            if srv.get("power_state") == "on"
            else _STANDBY_DRAW_KW
        )
        share = draw / len(live)
        for f in live:
            feeds[f]["load_kw"] = round(feeds[f]["load_kw"] + share, 3)

    # Rack overhead / MDF gear on feed A when A is live, else B.
    for rack, feeds in by_rack.items():
        overhead = 0.0
        rack_servers = [s for s in servers if s.get("rack") == rack]
        if rack_servers:
            overhead = _RACK_OVERHEAD_KW
        elif rack in _MDF_RACKS:
            overhead = _MDF_GEAR_KW
        if overhead <= 0:
            continue
        target = feeds.get("A") if feeds.get("A", {}).get("breaker") == "closed" else feeds.get("B")
        if target and target.get("breaker") == "closed":
            target["load_kw"] = round(target["load_kw"] + overhead, 3)

    tripped: list[dict] = []
    for p in rack_pdus:
        rating = float(p.get("rating_kw") or RACK_BREAKER_KW)
        load_kw = float(p.get("load_kw") or 0)
        p["load_pct"] = int(min(999, round(load_kw / rating * 100))) if rating else 0
        p["continuous_derate_kw"] = RACK_BREAKER_CONTINUOUS_KW
        # Hard overcurrent: trip when load exceeds breaker rating.
        if (
            p.get("breaker") == "closed"
            and p.get("status") == "online"
            and load_kw > rating
        ):
            p["breaker"] = "open"
            p["status"] = "tripped"
            p["trip_reason"] = "overcurrent"
            tripped.append(p)

    return tripped


def _apply_feed_loss(state: dict, pdu: dict) -> list[str]:
    """Power off servers that lost their last live feed after a PDU trip."""
    rack = pdu.get("rack")
    feed = (pdu.get("feed") or "A").upper()
    rack_pdus = state.get("power_chain", {}).get("rack_pdus", []) or []
    feeds = {
        (p.get("feed") or "A").upper(): p
        for p in rack_pdus
        if p.get("rack") == rack
    }
    affected = []
    for srv in state.get("servers") or []:
        if srv.get("rack") != rack:
            continue
        wanted = _server_feeds(srv)
        live = [
            f for f in wanted
            if feeds.get(f)
            and feeds[f].get("breaker") == "closed"
            and feeds[f].get("status") == "online"
        ]
        if not live:
            if srv.get("power_state") != "off":
                srv["power_state"] = "off"
                if isinstance(srv.get("bmc"), dict):
                    srv["bmc"]["power"] = "off"
                affected.append(srv["id"])
        elif feed in wanted and feed not in live:
            # Survived on the alternate feed — leave powered.
            pass
    return affected


def _power_chain(rack_pdus: list[dict]) -> dict:
    hall_pdus = [p for p in rack_pdus if p["rack"] in _DATA_HALL_RACKS]
    mdf_pdus = [p for p in rack_pdus if p["rack"] in _MDF_RACKS]
    return {
        "utility": {"id": "utility-feed-1", "status": "online", "voltage_v": 480, "source": "grid"},
        "ats": {"id": "ats-1", "status": "on_utility", "transfer_time_ms": 10},
        "generator": {"id": "gen-1", "status": "standby", "fuel_pct": 92, "runtime_hours": 0},
        "ups": [
            {"id": "ups-1", "status": "online", "load_pct": 52, "battery_pct": 100, "runtime_min": 14},
            {"id": "ups-2", "status": "online", "load_pct": 48, "battery_pct": 100, "runtime_min": 14},
        ],
        "floor_pdus": [
            {
                "id": "floor-pdu-a", "status": "online", "zone": "data-hall-a",
                "load_kw": round(sum(p["load_kw"] for p in hall_pdus), 1), "feeds": list(_DATA_HALL_RACKS),
            },
            {
                "id": "floor-pdu-mdf", "status": "online", "zone": "mdf",
                "load_kw": round(sum(p["load_kw"] for p in mdf_pdus), 1), "feeds": list(_MDF_RACKS),
            },
        ],
        "rack_pdus": rack_pdus,
    }


# Compressor work per kW of IT heat rejected (inverse of a ~1.8 CoP chiller).
_COOLING_KW_PER_IT_KW = 0.55


def _apply_cooling_load(it_kw: float, cooling: list[dict]) -> None:
    """Split the IT heat across running CRACs so cooling draw follows load.

    Previously each CRAC held a constant 9.0 kW, which made PUE a fixed number
    no matter what the racks were doing. Load is shared evenly; a unit that is
    over its capacity_kw is left at capacity so the overload stays visible.
    """
    running = [c for c in cooling or [] if c.get("status") == "running"]
    for c in cooling or []:
        if c.get("status") != "running":
            c["load_kw"] = 0.0
    if not running:
        return
    share = it_kw * _COOLING_KW_PER_IT_KW / len(running)
    for c in running:
        c["load_kw"] = round(min(share, float(c.get("capacity_kw") or share)), 2)


def _facility_summary(rack_pdus: list[dict], cooling: list[dict]) -> dict:
    it_kw = round(sum(p["load_kw"] for p in rack_pdus if p.get("status") == "online"), 2)
    _apply_cooling_load(it_kw, cooling)
    cooling_kw = round(sum(c["load_kw"] for c in cooling if c.get("status") == "running"), 2)
    overhead_kw = round(it_kw * 0.08, 2)
    total_kw = round(it_kw + cooling_kw + overhead_kw, 2)
    pue = round(total_kw / it_kw, 2) if it_kw else 1.0
    ashrae_ok = all(c.get("ashrae_ok", True) for c in cooling) if cooling else True
    return {
        "it_kw": it_kw,
        "cooling_kw": cooling_kw,
        "overhead_kw": overhead_kw,
        "total_kw": total_kw,
        "pue": pue,
        "ashrae_ok": ashrae_ok,
    }


def _recompute_facility(state: dict) -> None:
    cooling = state.get("cooling", [])
    # Dual-feed redistribution + overcurrent auto-trip (D14).
    # May cascade: A trip → load on B → B overcurrent → B trip.
    for _ in range(3):
        newly = _redistribute_pdu_loads(state)
        if not newly:
            break
        for pdu in newly:
            affected = _apply_feed_loss(state, pdu)
            _event(
                state,
                f"Breaker auto-tripped on {pdu['id']} (overcurrent "
                f"{pdu.get('load_kw')} kW > {pdu.get('rating_kw')} kW)"
                + (f" — lost power to {', '.join(affected)}" if affected else ""),
                "danger",
            )
    rack_pdus = state.get("power_chain", {}).get("rack_pdus", [])
    # Floor PDUs are the sum of the rack PDUs they feed.
    for floor_pdu in state.get("power_chain", {}).get("floor_pdus", []) or []:
        feeds = set(floor_pdu.get("feeds") or [])
        floor_pdu["load_kw"] = round(
            sum(p["load_kw"] for p in rack_pdus if p.get("rack") in feeds), 1
        )
    state["facility"] = {
        **state.get("facility", {}),
        **_facility_summary(rack_pdus, cooling),
    }


# ── Cooling ────────────────────────────────────────────────────────────────

def _cooling_units() -> list[dict]:
    units = [
        {
            "id": "CRAC-1", "zone": "Data Hall A - North", "room": "data-hall-a",
            "status": "running", "capacity_kw": 15.0, "load_kw": 9.0, "temp_c": 21.5, "humidity_pct": 45,
        },
        {
            "id": "CRAC-2", "zone": "Data Hall A - South", "room": "data-hall-a",
            "status": "running", "capacity_kw": 15.0, "load_kw": 9.0, "temp_c": 22.0, "humidity_pct": 46,
        },
    ]
    for u in units:
        u["ashrae_ok"] = u["status"] == "running" and 18.0 <= u["temp_c"] <= 27.0
    return units


# ── Network ────────────────────────────────────────────────────────────────

def _network() -> dict:
    from apps.vmware_sim.datacenter_network_storage import enrich_network
    switches = [
        {
            "id": "sw-core-01", "rack": "R09", "u_slot": 40, "hostname": "core-sw-01",
            "model": "Arista 7050CX3-32S", "ports": [
                {"port": 1, "status": "up", "speed": "10G", "vlan": 10, "connected_to": "srv-r01-u12"},
                {"port": 2, "status": "up", "speed": "10G", "vlan": 10, "connected_to": "srv-r01-u14"},
                {"port": 3, "status": "up", "speed": "10G", "vlan": 20, "connected_to": "srv-r02-u10"},
                {"port": 4, "status": "up", "speed": "25G", "vlan": 30, "connected_to": "srv-r03-u08"},
                {"port": 5, "status": "up", "speed": "10G", "vlan": 20, "connected_to": "srv-r04-u06"},
                {"port": 6, "status": "down", "speed": "10G", "vlan": None, "connected_to": None},
                {"port": 7, "status": "down", "speed": "10G", "vlan": None, "connected_to": None},
                {"port": 8, "status": "up", "speed": "40G", "vlan": 1, "connected_to": "sw-agg-01"},
            ],
        },
        {
            "id": "sw-agg-01", "rack": "R10", "u_slot": 38, "hostname": "agg-sw-01",
            "model": "Cisco Nexus 93180YC-FX", "ports": [
                {"port": 1, "status": "up", "speed": "40G", "vlan": 1, "connected_to": "sw-core-01"},
                {"port": 2, "status": "up", "speed": "10G", "vlan": 1, "connected_to": "internet-edge"},
                {"port": 3, "status": "down", "speed": "10G", "vlan": None, "connected_to": None},
            ],
        },
        {
            "id": "sw-ib-01", "rack": "R10", "u_slot": 36, "hostname": "ib-sw-01",
            "model": "NVIDIA Spectrum SN3700", "ports": [
                {"port": 1, "status": "up", "speed": "100G", "vlan": 30, "connected_to": "srv-r03-u08"},
                {"port": 2, "status": "up", "speed": "100G", "vlan": 1, "connected_to": "sw-agg-01"},
                {"port": 3, "status": "down", "speed": "100G", "vlan": None, "connected_to": None},
            ],
        },
        {
            "id": "sw-edge-01", "rack": "R09", "u_slot": 38, "hostname": "edge-sw-01",
            "model": "Juniper QFX5120-48Y", "ports": [
                {"port": 1, "status": "up", "speed": "25G", "vlan": 10, "connected_to": "sw-core-01"},
                {"port": 2, "status": "up", "speed": "10G", "vlan": 1, "connected_to": "internet-edge"},
                {"port": 3, "status": "down", "speed": "10G", "vlan": None, "connected_to": None},
            ],
        },
        {
            "id": "sw-tor-01", "rack": "R09", "u_slot": 34, "hostname": "tor-sw-01",
            "model": "Dell S5248F-ON", "ports": [
                {"port": 1, "status": "up", "speed": "25G", "vlan": 10, "connected_to": "sw-core-01"},
                {"port": 2, "status": "up", "speed": "25G", "vlan": 20, "connected_to": "srv-r02-u10"},
                {"port": 3, "status": "down", "speed": "25G", "vlan": None, "connected_to": None},
            ],
        },
        {
            "id": "sw-spine-01", "rack": "R10", "u_slot": 34, "hostname": "spine-sw-01",
            "model": "Extreme 9920", "ports": [
                {"port": 1, "status": "up", "speed": "100G", "vlan": 1, "connected_to": "sw-agg-01"},
                {"port": 2, "status": "up", "speed": "100G", "vlan": 1, "connected_to": "sw-core-01"},
                {"port": 3, "status": "down", "speed": "100G", "vlan": None, "connected_to": None},
            ],
        },
    ]
    topology = [
        {"from": "core-sw-01", "to": "agg-sw-01", "type": "uplink", "speed": "40G", "latency_us": 12, "util_pct": 34},
        {"from": "agg-sw-01", "to": "internet-edge", "type": "uplink", "speed": "10G", "latency_us": 80, "util_pct": 22},
        {"from": "ib-sw-01", "to": "agg-sw-01", "type": "uplink", "speed": "100G", "latency_us": 5, "util_pct": 41},
        {"from": "edge-sw-01", "to": "core-sw-01", "type": "uplink", "speed": "25G", "latency_us": 15, "util_pct": 18},
        {"from": "tor-sw-01", "to": "core-sw-01", "type": "uplink", "speed": "25G", "latency_us": 10, "util_pct": 27},
        {"from": "spine-sw-01", "to": "agg-sw-01", "type": "uplink", "speed": "100G", "latency_us": 6, "util_pct": 33},
    ]
    return enrich_network({"switches": switches, "topology": topology})


# ── Base state ─────────────────────────────────────────────────────────────

def _base_state() -> dict:
    servers = [
        # R01 stays Dell so power-failure / broken-asset scenarios stay stable
        _server("srv-r01-u12", "R01", 12, "web-prod-01", role="esxi_host", vendor="Dell"),
        _server("srv-r01-u14", "R01", 14, "web-prod-02", role="esxi_host", vendor="Dell", power_state="off",
                components={"power": "failed", "nic": "healthy", "disk": "healthy",
                            "motherboard": "healthy", "cpu": "healthy", "gpu": "healthy"}),
        _server("srv-r02-u10", "R02", 10, "db-prod-01", role="db", vendor="HPE"),
        _server("srv-r03-u08", "R03", 8, "gpu-node-01", role="gpu_node", vendor="Supermicro",
                components={"power": "healthy", "nic": "healthy", "disk": "healthy",
                            "motherboard": "healthy", "cpu": "healthy", "gpu": "failed"}),
        _server("srv-r04-u06", "R04", 6, "storage-01", role="storage", vendor="Lenovo"),
        _server("srv-r05-u10", "R05", 10, "app-prod-01", role="app", vendor="Cisco"),
        _server("srv-r06-u08", "R06", 8, "edge-cache-01", role="cache", vendor="Gigabyte"),
    ]
    rooms = _rooms()
    rack_pdus = _rack_pdus(servers)
    power_chain = _power_chain(rack_pdus)
    cooling = _cooling_units()
    network = _network()
    facility = {
        "site": "fixitlab-dc1",
        **_facility_summary(rack_pdus, cooling),
    }
    racks = [
        {
            "id": r, "floor": "1", "pdu": f"PDU-{r}", "room": _room_for_rack(rooms, r),
            "servers": [s["id"] for s in servers if s["rack"] == r],
        }
        for r in _RACKS
    ]
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"site": "fixitlab-dc1", "floor_count": 1},
        "floors": [{"id": "1", "name": "Floor 1", "racks": _RACKS}],
        "rooms": rooms,
        "current_room": "data-hall-a",
        "racks": racks,
        "servers": servers,
        "pdus": rack_pdus,
        "power_chain": power_chain,
        "cooling": cooling,
        "network": network,
        "facility": facility,
        "selected_asset": None,
        "goal": {"title": "Datacenter break/fix", "objective": "Replace the failed power supply in web-prod-02 (R01-U14)."},
        "broken": {"server": "srv-r01-u14", "component": "power"},
        "events": [],
        "tickets": [],
        "console": {"open": False, "asset_id": None, "lines": []},
        "campus": _campus(),
        "inventory": [],
        "digital_twin": {"version": 2, "persisted_changes": []},
        "liquid_cooling": None,  # built lazily in get_state
        "pxe_maas": None,
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    servers = state.get("servers", [])

    def _set_component(server_id: str, component: str, off: bool = False) -> None:
        srv = next((s for s in servers if s["id"] == server_id), None)
        if not srv:
            return
        srv["components"][component] = "failed"
        if off:
            srv["power_state"] = "off"
            srv["bmc"]["power"] = "off"

    if "nic" in slug:
        _set_component("srv-r02-u10", "nic")
        state["goal"] = {"title": "Replace NIC", "objective": "Replace the failed NIC in db-prod-01 (R02-U10)."}
        state["broken"] = {"server": "srv-r02-u10", "component": "nic"}
    elif "disk" in slug:
        _set_component("srv-r02-u10", "disk")
        state["goal"] = {"title": "Replace disk", "objective": "Replace the failed disk in db-prod-01 (R02-U10)."}
        state["broken"] = {"server": "srv-r02-u10", "component": "disk"}
    elif "motherboard" in slug:
        _set_component("srv-r01-u12", "motherboard", off=True)
        state["goal"] = {"title": "Replace motherboard", "objective": "Replace the failed motherboard in web-prod-01 (R01-U12)."}
        state["broken"] = {"server": "srv-r01-u12", "component": "motherboard"}
    elif "cpu" in slug:
        _set_component("srv-r01-u12", "cpu", off=True)
        state["goal"] = {"title": "Replace CPU", "objective": "Replace the failed CPU in web-prod-01 (R01-U12)."}
        state["broken"] = {"server": "srv-r01-u12", "component": "cpu"}
    elif "power" in slug or "psu" in slug:
        _set_component("srv-r01-u14", "power", off=True)
        state["goal"] = {"title": "Replace power supply", "objective": "Replace the failed power supply in web-prod-02 (R01-U14). Open a Dell/HPE FRU ticket if you need parts authorized."}
        state["broken"] = {"server": "srv-r01-u14", "component": "power"}
    elif "gpu" in slug:
        _set_component("srv-r03-u08", "gpu")
        state["goal"] = {"title": "Replace GPU", "objective": "Replace the failed GPU in gpu-node-01 (R03-U08)."}
        state["broken"] = {"server": "srv-r03-u08", "component": "gpu"}
    elif "cable" in slug or "reseat" in slug:
        srv = next((s for s in servers if s["id"] == "srv-r02-u10"), None)
        if srv:
            srv["components"]["nic"] = "failed"
            hw = srv.setdefault("hardware", {})
            for c in hw.get("cables") or []:
                if c.get("port") == "eth0":
                    c["status"] = "unseated"
                    break
        state["goal"] = {
            "title": "Reseat cable",
            "objective": "Plug / reseat the loose NIC0-front DAC cable on db-prod-01 (R02-U10), or open a Dell support ticket for FRU replacement.",
        }
        state["broken"] = {"server": "srv-r02-u10", "component": "cable", "cable_id": "NIC0-front"}
    elif "firmware" in slug:
        state["goal"] = {"title": "Update firmware", "objective": "Update BIOS/firmware on gpu-node-01 (R03-U08)."}
        state["broken"] = {"server": "srv-r03-u08", "component": "firmware"}
    elif "cooling" in slug or "crac" in slug or "overheat" in slug:
        crac = state["cooling"][0]
        crac["status"] = "failed"
        crac["temp_c"] = 31.5
        crac["ashrae_ok"] = False
        _recompute_facility(state)
        state["goal"] = {
            "title": "Restore cooling",
            "objective": f"Bring {crac['id']} back online in Data Hall A before the room exceeds ASHRAE limits.",
        }
        state["broken"] = {"server": None, "component": "cooling", "target": crac["id"]}
    elif "pdu" in slug or "breaker" in slug:
        pdu = state["power_chain"]["rack_pdus"][0]
        pdu["status"] = "tripped"
        pdu["breaker"] = "open"
        for srv in servers:
            if srv["rack"] == pdu["rack"]:
                srv["power_state"] = "off"
                srv["bmc"]["power"] = "off"
        _recompute_facility(state)
        state["goal"] = {
            "title": "Restore rack power",
            "objective": f"Close the breaker on {pdu['id']} and bring rack {pdu['rack']} back online.",
        }
        state["broken"] = {"server": None, "component": "pdu", "target": pdu["id"]}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


_ensure_session = _ensure


# ── ServerIdentity sync ────────────────────────────────────────────────────

def _sync_identity(session_id: str, state: dict) -> None:
    try:
        from apps.labs.provisioner.simulation.server_identity import upsert_server
    except Exception:  # pragma: no cover - identity module should always be importable
        return
    rooms = state.get("rooms", [])
    for srv in state.get("servers", []):
        inv = srv.get("inventory") if isinstance(srv.get("inventory"), dict) else {}
        patch = {
            "id": srv["id"],
            "hostname": srv.get("hostname"),
            "power": srv.get("power_state"),
            "physical_location": {
                "room": _room_for_rack(rooms, srv.get("rack")),
                "rack": srv.get("rack"),
                "u_position": srv.get("u_slot"),
            },
            "bmc": srv.get("bmc"),
            "tags": {"role": srv.get("role")} if srv.get("role") else {},
            "serial": inv.get("serial") or srv.get("service_tag") or srv.get("serial"),
            "asset_tag": inv.get("asset_tag") or srv.get("asset_tag"),
            "firmware": {
                "bios": inv.get("firmware") or srv.get("firmware_version"),
                "bmc": (srv.get("bmc") or {}).get("firmware") if isinstance(srv.get("bmc"), dict) else None,
            },
            "owner": inv.get("owner") or srv.get("owner") or "dcops",
            "install_state": srv.get("install_state") or inv.get("status") or "deployed",
        }
        if srv.get("raid") is not None:
            patch["raid"] = srv.get("raid")
        upsert_server(session_id, patch, source="datacenter")


def _sync_power(session_id: str, server_id: str, power_state: str) -> None:
    try:
        from apps.labs.provisioner.simulation.server_identity import set_power, get_primary
    except Exception:  # pragma: no cover
        return
    set_power(session_id, server_id, power_state, source="datacenter")
    # Also gate the lab terminal primary — BMC off on the working asset must
    # freeze SSH/shell just like a dead chassis.
    try:
        primary = get_primary(session_id)
        if primary and primary.get("id") != server_id:
            set_power(session_id, primary["id"], power_state, source="datacenter")
    except Exception:
        pass
    try:
        from apps.labs.provisioner.simulation.datacenter_bridge import record_power
        record_power(session_id, "off" if power_state == "off" else "on", asset_id=server_id)
    except Exception:
        pass


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    from apps.vmware_sim.datacenter_digital_twin import enrich_server, campus_rooms, campus_assets
    entry = _ensure(session_id, scenario_slug)
    state = entry["state"]
    # Migrate older sessions: campus rooms + twin hardware surfaces
    existing_ids = {r["id"] for r in state.get("rooms", [])}
    if "campus" not in existing_ids or len(state.get("rooms", [])) < 10:
        hall = list(_DATA_HALL_RACKS)
        mdf = list(_MDF_RACKS)
        rooms = campus_rooms()
        for r in rooms:
            if r["id"] == "data-hall-a":
                r["racks"] = hall
            elif r["id"] == "mdf":
                r["racks"] = mdf
            elif r.get("racks") is None:
                r["racks"] = []
        state["rooms"] = rooms
    else:
        # Merge newly added rooms (e.g. warehouse) and refresh exits metadata.
        by_id = {r["id"]: r for r in state.get("rooms", [])}
        for room in campus_rooms():
            rid = room["id"]
            if rid not in by_id:
                added = copy.deepcopy(room)
                if added.get("racks") is None:
                    added["racks"] = []
                state["rooms"].append(added)
                by_id[rid] = added
            elif "exits" in room:
                by_id[rid]["exits"] = list(room["exits"])
            if "name" in room and by_id[rid].get("name") != room["name"] and rid == "warehouse":
                by_id[rid]["name"] = room["name"]
    if not state.get("campus"):
        state["campus"] = campus_assets()
    else:
        from apps.vmware_sim.datacenter_facility_ops import ensure_campus_plant
        state["campus"] = ensure_campus_plant(state["campus"], state.get("power_chain"))
    for srv in state.get("servers", []):
        enrich_server(srv)
        mb = srv.get("motherboard")
        if mb:
            from apps.vmware_sim.datacenter_physics_ops import ensure_extended_buses, tick_bus_packets
            ensure_extended_buses(mb)
            tick_bus_packets(mb)
    # Enrich network (CLI/counters) for older sessions
    from apps.vmware_sim.datacenter_network_storage import enrich_network, tick_port_counters, CABLE_CATALOG
    if state.get("network"):
        enrich_network(state["network"])
        tick_port_counters(state["network"])
    # Phase 4: rack FRU + physics
    from apps.vmware_sim.datacenter_physics_ops import enrich_rack, build_monitoring_snapshot, build_training_scenarios
    pdus = state.get("pdus") or state.get("power_chain", {}).get("rack_pdus") or []
    for rack in state.get("racks") or []:
        enrich_rack(rack, state.get("servers") or [], state.get("cooling") or [], pdus)
    state["monitoring"] = build_monitoring_snapshot(state)
    if not state.get("training"):
        state["training"] = {"scenarios": build_training_scenarios(), "active": None, "progress": []}
    # Phase 6: hypervisors + AI/K8s
    from apps.vmware_sim.datacenter_compute_ai import build_hypervisor_platform, build_ai_platform
    if not state.get("hypervisors"):
        state["hypervisors"] = build_hypervisor_platform(state.get("servers") or [])
    if not state.get("ai_platform"):
        state["ai_platform"] = build_ai_platform(state.get("servers") or [])
    # Phase 9: liquid cooling + MAAS/PXE
    from apps.vmware_sim.datacenter_plant_provision import build_liquid_cooling, build_pxe_maas
    if not state.get("liquid_cooling"):
        state["liquid_cooling"] = build_liquid_cooling(state.get("servers") or [])
    if not state.get("pxe_maas"):
        state["pxe_maas"] = build_pxe_maas(state.get("servers") or [])
    # Phase 10: fire/env/optical/capacity/PdM
    from apps.vmware_sim.datacenter_facility_ops import (
        build_fire_safety, build_environmental, build_optical,
        build_capacity_snapshot, build_predictive_maintenance,
    )
    if not state.get("fire_safety"):
        state["fire_safety"] = build_fire_safety()
    if not state.get("environmental"):
        state["environmental"] = build_environmental(state.get("servers") or [])
    if not state.get("optical"):
        state["optical"] = build_optical()
    elif not (state.get("optical") or {}).get("idf"):
        state["optical"]["idf"] = build_optical()["idf"]
    state["capacity"] = build_capacity_snapshot(state)
    state["predictive"] = build_predictive_maintenance(state)
    # Phase 11: DR, access, automation, reports
    from apps.vmware_sim.datacenter_ops_platform import (
        build_dr_platform, build_access_control, build_automation, build_ops_report,
    )
    if not state.get("dr"):
        state["dr"] = build_dr_platform()
    if not state.get("access_control"):
        state["access_control"] = build_access_control()
    if not state.get("automation"):
        state["automation"] = build_automation()
    state["ops_report"] = build_ops_report(state)
    # Sync campus access from access_control
    campus = state.setdefault("campus", {})
    ac = state["access_control"]
    campus["access"] = {
        "gate": (ac.get("gate") or {}).get("status", "secured"),
        "biometrics": (ac.get("biometrics") or {}).get("status", "online"),
        "cameras": (ac.get("cameras") or {}).get("online", 24),
    }
    # Phase 12: CAB, sustainability, containment, cable plant, burn-in, exporters
    from apps.vmware_sim.datacenter_phase12 import (
        build_change_calendar, build_sustainability, build_containment,
        build_cable_plant, build_burnin, build_doc_library, build_exporters,
        apply_blanking_to_physics,
    )
    if not state.get("change_calendar"):
        state["change_calendar"] = build_change_calendar()
    if not state.get("containment"):
        state["containment"] = build_containment()
    if not state.get("cable_plant"):
        state["cable_plant"] = build_cable_plant()
    if not state.get("burnin"):
        state["burnin"] = build_burnin(state.get("servers") or [])
    if not state.get("doc_library"):
        state["doc_library"] = build_doc_library()
    if not state.get("exporters"):
        state["exporters"] = build_exporters(state)
    state["sustainability"] = build_sustainability(state)
    for rack in state.get("racks") or []:
        apply_blanking_to_physics(rack, state.get("containment"))
    # CMDB rollup + hardware catalog for UI
    state["inventory"] = [
        {**(s.get("inventory") or {}), "server_id": s["id"], "hostname": s.get("hostname")}
        for s in state.get("servers", [])
    ]
    if not state.get("hardware_catalog"):
        from apps.vmware_sim.datacenter_hardware_catalog import full_catalog
        state["hardware_catalog"] = full_catalog()
    state["hardware_catalog"]["cable_catalog"] = CABLE_CATALOG
    _save(session_id, entry)
    _sync_identity(session_id, state)
    state_copy = copy.deepcopy(state)
    rooms = state_copy.get("rooms", [])
    current_room = state_copy.get("current_room", "data-hall-a")
    facility = dict(state_copy.get("facility", {}))
    facility["rooms"] = rooms
    facility["current_room"] = current_room
    state_copy["facility"] = facility
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": state_copy,
        "goal": state_copy.get("goal", {}),
        "events": state_copy.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))
    try:
        from apps.labs.provisioner.simulation.chaos_engine import drop_session as chaos_drop
        chaos_drop(session_id)
    except Exception:  # pragma: no cover
        pass


def _find_server(state: dict, asset_id: str) -> dict | None:
    return next((s for s in state.get("servers", []) if s.get("id") == asset_id or s.get("hostname") == asset_id), None)


_REPLACE_ACTIONS = {
    "replace_nic": "nic",
    "replace_disk": "disk",
    "replace_motherboard": "motherboard",
    "replace_cpu": "cpu",
    "replace_gpu": "gpu",
    "replace_power": "power",
    "replace_psu": "power",
    "replace_fan": "fan",
    "replace_dimm": "dimm",
    "replace_pcie": "pcie",
    "replace_raid": "raid",
    "replace_hba": "hba",
}


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Datacenter session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    # Phase 12: change freeze gate
    from apps.vmware_sim.datacenter_phase12 import change_freeze_blocks
    freeze_err = change_freeze_blocks(state, action)
    if freeze_err:
        return {"ok": False, "error": freeze_err}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "tech"}
        _event(state, "Signed in to DCIM console", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if action == "enter_room":
        room_id = payload.get("room_id") or ""
        room_ids = {r["id"] for r in state.get("rooms", [])}
        if room_id not in room_ids:
            return {"ok": False, "error": f"Unknown room: {room_id}"}
        state["current_room"] = room_id
        _save(session_id, entry)
        return {"ok": True, "message": f"Entered {room_id}", "current_room": room_id}

    if action == "select_asset":
        asset_id = payload.get("asset_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        state["selected_asset"] = srv["id"]
        _save(session_id, entry)
        return {"ok": True, "message": f"Selected {srv['id']}", "asset": srv}

    if action == "open_bmc":
        asset_id = payload.get("asset_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        state["selected_asset"] = srv["id"]
        _save(session_id, entry)
        return {"ok": True, "message": f"Opened BMC console for {srv['id']}", "bmc": srv.get("bmc"), "asset": srv}

    if action == "bmc_login":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        user = (payload.get("username") or payload.get("user") or "").strip()
        password = (payload.get("password") or "").strip()
        bmc = srv.setdefault("bmc", {})
        allowed = {u.get("name") for u in (bmc.get("users") or []) if u.get("enabled")}
        # Factory defaults: root/calvin (Dell) or Administrator/password (iLO-style)
        ok_cred = (
            (user in allowed or user in ("root", "Administrator", "admin"))
            and password in ("calvin", "password", "admin", "changeme")
        )
        if not ok_cred:
            bmc.setdefault("sel", []).insert(0, {
                "time": _now_iso(), "severity": "warning",
                "message": f"Failed login attempt for user '{user or '?'}'",
            })
            _save(session_id, entry)
            return {"ok": False, "error": "Invalid BMC credentials"}
        bmc["session"] = {"authenticated": True, "user": user}
        bmc.setdefault("sel", []).insert(0, {
            "time": _now_iso(), "severity": "info",
            "message": f"User {user} authenticated to {bmc.get('product', 'BMC')} web UI",
        })
        _save(session_id, entry)
        return {"ok": True, "message": f"Logged into {bmc.get('product')}", "bmc": bmc}

    if action == "bmc_logout":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        bmc["session"] = {"authenticated": False, "user": None}
        _save(session_id, entry)
        return {"ok": True, "message": "BMC session ended", "bmc": bmc}

    if action == "bmc_power":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        mode = (payload.get("mode") or "on").lower()
        if mode not in ("on", "off", "reset", "cycle"):
            return {"ok": False, "error": f"Unknown BMC power mode: {mode}"}
        if mode == "off":
            srv["power_state"] = "off"
        elif mode == "on":
            srv["power_state"] = "on"
        else:  # reset / cycle
            srv["power_state"] = "on" if all(v == "healthy" for v in srv["components"].values()) else "off"
        srv["bmc"]["power"] = "on" if srv["power_state"] == "on" else "off"
        srv["bmc"].setdefault("sel", []).insert(0, {"time": _now_iso(), "message": f"Power {mode} issued via Redfish"})
        # Rack draw is derived from powered-on servers, so power ops move kW.
        _recompute_facility(state)
        _event(state, f"BMC {mode} issued for {srv['id']}", "info")
        _save(session_id, entry)
        _sync_identity(session_id, state)
        _sync_power(session_id, srv["id"], srv["power_state"])
        return {"ok": True, "message": f"BMC {mode} issued", "power_state": srv["power_state"], "bmc": srv["bmc"]}

    if action == "power_cycle":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        srv["power_state"] = "on" if all(v == "healthy" for v in srv["components"].values()) else "off"
        srv["bmc"]["power"] = "on" if srv["power_state"] == "on" else "off"
        _recompute_facility(state)
        _event(state, f"Power cycled {srv['id']}", "info")
        _save(session_id, entry)
        _sync_identity(session_id, state)
        _sync_power(session_id, srv["id"], srv["power_state"])
        return {"ok": True, "message": "Power cycle issued", "power_state": srv["power_state"]}

    if action in _REPLACE_ACTIONS:
        component = _REPLACE_ACTIONS[action]
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        srv["components"][component] = "healthy"
        if all(v == "healthy" for v in srv["components"].values()):
            srv["power_state"] = "on"
            srv["bmc"]["power"] = "on"
        if broken.get("server") == srv["id"] and broken.get("component") == component:
            broken.clear()
        # Keep detailed hardware inventory in sync with component health.
        hw = srv.setdefault("hardware", _hardware_inventory(
            srv.get("hostname") or srv["id"],
            vendor=srv.get("vendor") or "Dell",
            role=srv.get("role"),
            model=srv.get("model"),
        ))
        if component == "disk":
            for d in hw.get("storage") or []:
                d["status"] = "healthy"
        if component == "dimm":
            for d in hw.get("dimms") or []:
                d["status"] = "healthy"
        if component == "power":
            for p in hw.get("psus") or []:
                p["status"] = "healthy"
        if component == "fan":
            for f in hw.get("fans") or []:
                f["status"] = "healthy"
        _event(state, f"Replaced {component} in {srv['id']}", "success")
        _save(session_id, entry)
        _sync_identity(session_id, state)
        try:
            from apps.labs.provisioner.simulation import datacenter_bridge
            if component == "disk":
                datacenter_bridge.record_disk_replaced(str(session_id), srv["id"])
            elif component == "nic":
                datacenter_bridge.record_nic_reseated(str(session_id), srv["id"])
        except Exception:
            pass
        return {"ok": True, "message": f"{component} replaced"}

    if action in ("reseat_cable", "plug_cable", "unplug_cable"):
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        cable_id = payload.get("cable_id") or broken.get("cable_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        hw = srv.setdefault("hardware", _hardware_inventory(
            srv.get("hostname") or srv["id"],
            vendor=srv.get("vendor") or "Dell",
            role=srv.get("role"),
            model=srv.get("model"),
        ))
        cables = hw.setdefault("cables", [])
        target = None
        if cable_id:
            target = next((c for c in cables if c.get("id") == cable_id), None)
        if target is None and cables:
            target = next((c for c in cables if c.get("status") != "seated"), cables[0])
        if action == "unplug_cable":
            if not target:
                return {"ok": False, "error": "No cable found"}
            target["status"] = "unseated"
            srv["components"]["nic"] = "failed"
            _event(state, f"Unplugged {target['id']} on {srv['id']}", "warning")
            _save(session_id, entry)
            _sync_identity(session_id, state)
            return {"ok": True, "message": f"Cable {target['id']} unplugged"}
        # plug / reseat
        if target:
            target["status"] = "seated"
        if cables and all(c.get("status") == "seated" for c in cables):
            srv["components"]["nic"] = "healthy"
        if broken.get("server") == srv["id"] and broken.get("component") == "cable":
            if not cable_id or broken.get("cable_id") in (None, "", cable_id) or (target and target.get("id") == broken.get("cable_id")):
                if all(c.get("status") == "seated" for c in cables):
                    broken.clear()
        label = target["id"] if target else "cable"
        _event(state, f"Cable {label} reseated on {srv['id']}", "success")
        _save(session_id, entry)
        _sync_identity(session_id, state)
        try:
            from apps.labs.provisioner.simulation import datacenter_bridge
            datacenter_bridge.record_nic_reseated(str(session_id), srv["id"])
        except Exception:
            pass
        return {"ok": True, "message": f"Cable {label} plugged / reseated"}

    if action == "open_vendor_ticket":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        component = payload.get("component") or broken.get("component") or "hardware"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        vendor = _normalize_support_vendor(payload.get("vendor") or srv.get("vendor") or "Dell")
        ticket_id = f"{vendor.upper()[:4]}-{int(time.time()) % 100000:05d}"
        tickets = state.setdefault("tickets", [])
        ticket = {
            "id": ticket_id,
            "vendor": vendor,
            "asset_id": srv["id"],
            "hostname": srv.get("hostname"),
            "component": component,
            "status": "open",
            "priority": "high" if component in ("power", "motherboard", "cpu", "disk") else "medium",
            "summary": f"{component} failure on {srv.get('hostname')}",
            "created": _now_iso(),
            "service_tag": srv.get("service_tag") or f"ST{srv['id'][-6:].upper()}",
        }
        tickets.insert(0, ticket)
        # Part replacement ticket fulfills FRU scenarios when tech replaces after RMA approval simulation
        if broken.get("server") == srv["id"] and broken.get("component") == component:
            # Opening ticket alone does not clear broken — tech still must replace/reseat
            pass
        _event(state, f"Opened {vendor} ticket {ticket_id} for {srv['id']} ({component})", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"{vendor} ticket {ticket_id} opened", "ticket": ticket}

    if action == "resolve_vendor_ticket":
        ticket_id = payload.get("ticket_id") or ""
        tickets = state.setdefault("tickets", [])
        ticket = next((t for t in tickets if t.get("id") == ticket_id), None)
        if not ticket:
            return {"ok": False, "error": f"Ticket {ticket_id} not found"}
        ticket["status"] = "parts_shipped"
        ticket["resolved"] = _now_iso()
        _event(state, f"Ticket {ticket_id}: FRU authorized / parts shipped", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Ticket {ticket_id} advanced to parts_shipped"}

    if action == "update_firmware":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        srv["firmware_version"] = payload.get("version") or "2.14.0"
        if broken.get("server") == srv["id"] and broken.get("component") == "firmware":
            broken.clear()
        _event(state, f"Firmware updated on {srv['id']} to {srv['firmware_version']}", "success")
        _save(session_id, entry)
        _sync_identity(session_id, state)
        return {"ok": True, "message": "Firmware updated"}

    if action == "trip_pdu_breaker":
        pdu_id = payload.get("pdu_id") or payload.get("asset_id") or ""
        rack_pdus = state.get("power_chain", {}).get("rack_pdus", [])
        pdu = next((p for p in rack_pdus if p["id"] == pdu_id), None)
        if not pdu:
            return {"ok": False, "error": f"PDU {pdu_id} not found"}
        pdu["status"] = "tripped"
        pdu["breaker"] = "open"
        pdu["trip_reason"] = payload.get("reason") or "manual"
        affected = _apply_feed_loss(state, pdu)
        # Failover may overload the surviving feed → cascade overcurrent trip.
        _recompute_facility(state)
        _sync_rack_pdus(state)
        feed = pdu.get("feed") or "A"
        _event(
            state,
            f"Breaker tripped on {pdu['id']} (feed {feed}) — rack {pdu['rack']}"
            + (f" lost power to {len(affected)} server(s)" if affected else " (dual-corded load failed over)"),
            "danger",
        )
        try:
            from apps.labs.provisioner.simulation.chaos_engine import inject as chaos_inject
            chaos_inject(session_id, "trip_pdu", pdu["id"], detail={"rack": pdu["rack"], "affected_servers": affected})
        except Exception:  # pragma: no cover
            pass
        _save(session_id, entry)
        _sync_identity(session_id, state)
        return {"ok": True, "message": f"Breaker tripped on {pdu['id']}", "affected_servers": affected}

    if action == "set_server_power_feeds":
        asset_id = payload.get("asset_id") or payload.get("server_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        feeds = payload.get("power_feeds") or payload.get("feeds") or ["A", "B"]
        if not isinstance(feeds, list) or not feeds:
            return {"ok": False, "error": "power_feeds must be a non-empty list"}
        srv["power_feeds"] = [str(f).upper() for f in feeds]
        _recompute_facility(state)
        _sync_rack_pdus(state)
        _event(state, f"{srv['id']} cording set to {srv['power_feeds']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"{srv['id']} power_feeds={srv['power_feeds']}", "server": srv}

    if action == "restore_pdu":
        pdu_id = payload.get("pdu_id") or payload.get("asset_id") or ""
        rack_pdus = state.get("power_chain", {}).get("rack_pdus", [])
        pdu = next((p for p in rack_pdus if p["id"] == pdu_id), None)
        if not pdu:
            return {"ok": False, "error": f"PDU {pdu_id} not found"}
        pdu["status"] = "online"
        pdu["breaker"] = "closed"
        if broken.get("component") == "pdu" and broken.get("target") == pdu["id"]:
            broken.clear()
        _recompute_facility(state)
        _sync_rack_pdus(state)
        _event(state, f"Breaker restored on {pdu['id']}", "success")
        try:
            from apps.labs.provisioner.simulation.chaos_engine import clear_faults
            clear_faults(session_id, fault_type="trip_pdu", target=pdu["id"])
        except Exception:  # pragma: no cover
            pass
        _save(session_id, entry)
        return {"ok": True, "message": f"Breaker restored on {pdu['id']}"}

    if action == "restore_crac":
        crac_id = payload.get("crac_id") or payload.get("asset_id") or ""
        crac = next((c for c in state.get("cooling", []) if c["id"] == crac_id), None)
        if not crac:
            return {"ok": False, "error": f"CRAC {crac_id} not found"}
        crac["status"] = "running"
        crac["temp_c"] = 21.5
        crac["ashrae_ok"] = True
        if broken.get("component") == "cooling" and broken.get("target") == crac["id"]:
            broken.clear()
        _apply_thermal_to_zone(state, inlet_c=22.1, exhaust_c=34.0, fans_rpm=4200)
        _recompute_facility(state)
        _event(state, f"{crac['id']} restored to normal operation", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"{crac_id} restored"}

    if action == "open_serial_console":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        power = srv.get("power_state") == "on"
        lines = [
            f"Connected to {srv.get('hostname')} serial console (COM1 @ 115200)",
            f"BMC: {srv.get('bmc', {}).get('endpoint')}",
            f"Vendor: {srv.get('vendor')}  Model: {srv.get('model')}  Service Tag: {srv.get('service_tag')}",
            "---",
        ]
        if power:
            lines += [
                f"{srv.get('hostname')} login: (session attached)",
                f"[  OK  ] Reached target Multi-User System.",
                f"kernel: eth0 link {'UP' if srv['components'].get('nic') == 'healthy' else 'DOWN'}",
            ]
        else:
            lines += [
                "No carrier — host powered off. Use BMC Power On or rack PDU.",
                "POST halted. Chassis LED: amber.",
            ]
        state["console"] = {"open": True, "asset_id": srv["id"], "lines": lines}
        state["selected_asset"] = srv["id"]
        _event(state, f"Opened serial console on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Serial console attached", "console": state["console"]}

    if action == "close_serial_console":
        state["console"] = {"open": False, "asset_id": None, "lines": []}
        _save(session_id, entry)
        return {"ok": True, "message": "Serial console closed"}

    if action == "open_motherboard":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        from apps.vmware_sim.datacenter_digital_twin import enrich_server
        enrich_server(srv)
        state["selected_asset"] = srv["id"]
        _save(session_id, entry)
        return {"ok": True, "message": "Motherboard map open", "motherboard": srv.get("motherboard")}

    if action == "toggle_chassis_cover":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        mb = srv.setdefault("motherboard", {})
        mb["cover_open"] = not mb.get("cover_open", False)
        if mb["cover_open"]:
            mb["maintenance_mode"] = True
        _event(state, f"Chassis cover {'opened' if mb['cover_open'] else 'closed'} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Chassis cover toggled", "motherboard": mb}

    if action == "replace_dimm_slot":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        slot_id = payload.get("slot_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        mb = srv.setdefault("motherboard", {})
        slot = next((d for d in mb.get("dimm_slots", []) if d.get("id") == slot_id), None)
        if not slot:
            return {"ok": False, "error": f"DIMM slot {slot_id} not found"}
        slot["status"] = "healthy"
        slot["ecc_corrections_24h"] = 0
        srv["components"]["dimm"] = "healthy"
        if broken.get("server") == srv["id"] and broken.get("component") == "dimm":
            broken.clear()
        _event(state, f"Replaced DIMM in slot {slot_id} on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"DIMM {slot_id} replaced"}

    if action == "apply_thermal_paste":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        socket_id = payload.get("socket_id") or "CPU1"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        mb = srv.setdefault("motherboard", {})
        sock = next((c for c in mb.get("cpu_sockets", []) if c.get("id") == socket_id), None)
        if not sock:
            return {"ok": False, "error": f"Socket {socket_id} not found"}
        sock["paste_applied"] = True
        sock["temp_c"] = max(35.0, (sock.get("temp_c") or 55) - 6)
        _event(state, f"Thermal paste reapplied on {socket_id} ({srv['id']})", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Thermal paste applied to {socket_id}"}

    if action == "motherboard_ops":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        op = payload.get("op") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        mb = srv.setdefault("motherboard", {})
        sm = srv.setdefault("service_mode", {})
        inv = srv.setdefault("inventory", {})
        hist = inv.setdefault("replacement_history", [])
        if not mb.get("cover_open") and op not in ("pulse_buses",):
            return {"ok": False, "error": "Open chassis cover before motherboard FRU ops"}

        if op == "remove_cpu":
            sock = payload.get("socket_id") or "CPU1"
            for c in mb.get("cpu_sockets") or []:
                if c.get("id") == sock:
                    c["populated"] = False
                    c["status"] = "empty"
                    c["paste_applied"] = False
            if sock not in sm.setdefault("cpu_removed", []):
                sm["cpu_removed"].append(sock)
            hist.insert(0, {"time": _now_iso(), "part": sock, "action": "cpu_remove"})
        elif op == "install_cpu":
            sock = payload.get("socket_id") or "CPU1"
            for c in mb.get("cpu_sockets") or []:
                if c.get("id") == sock:
                    c["populated"] = True
                    c["status"] = "healthy"
                    c["paste_applied"] = False
            sm["cpu_removed"] = [x for x in sm.get("cpu_removed", []) if x != sock]
            hist.insert(0, {"time": _now_iso(), "part": sock, "action": "cpu_install"})
            if broken.get("server") == srv["id"] and broken.get("component") == "cpu":
                srv["components"]["cpu"] = "healthy"
                broken.clear()
        elif op == "remove_heatsink":
            sock = payload.get("socket_id") or "CPU1"
            if sock not in sm.setdefault("heatsink_removed", []):
                sm["heatsink_removed"].append(sock)
            for c in mb.get("cpu_sockets") or []:
                if c.get("id") == sock:
                    c["heatsink"] = None
        elif op == "install_heatsink":
            sock = payload.get("socket_id") or "CPU1"
            sm["heatsink_removed"] = [x for x in sm.get("heatsink_removed", []) if x != sock]
            for c in mb.get("cpu_sockets") or []:
                if c.get("id") == sock:
                    c["heatsink"] = "aluminum finstack + heatpipes"
        elif op == "reseat_dimm":
            slot_id = payload.get("slot_id") or ""
            slot = next((d for d in mb.get("dimm_slots", []) if d.get("id") == slot_id), None)
            if not slot:
                return {"ok": False, "error": f"DIMM slot {slot_id} not found"}
            slot["clips_locked"] = not slot.get("clips_locked", True)
            if slot.get("clips_locked"):
                slot["populated"] = True
                slot["status"] = "healthy"
                slot["ecc_corrections_24h"] = 0
            else:
                slot["status"] = "unseated"
            hist.insert(0, {"time": _now_iso(), "part": slot_id, "action": "dimm_reseat"})
        elif op == "remove_pcie":
            slot_id = payload.get("slot_id") or ""
            slot = next((p for p in mb.get("pcie_slots", []) if p.get("id") == slot_id), None)
            if not slot:
                return {"ok": False, "error": f"PCIe slot {slot_id} not found"}
            removed = slot.get("device")
            slot["device"] = None
            slot["status"] = "empty"
            slot["bw_gbs"] = 0
            hist.insert(0, {"time": _now_iso(), "part": slot_id, "action": f"pcie_remove:{removed}"})
        elif op == "install_pcie":
            slot_id = payload.get("slot_id") or ""
            device = payload.get("device") or "ConnectX-7 100GbE"
            slot = next((p for p in mb.get("pcie_slots", []) if p.get("id") == slot_id), None)
            if not slot:
                return {"ok": False, "error": f"PCIe slot {slot_id} not found"}
            slot["device"] = device
            slot["status"] = "healthy"
            slot["bw_gbs"] = 4.0
            hist.insert(0, {"time": _now_iso(), "part": slot_id, "action": f"pcie_install:{device}"})
            if broken.get("server") == srv["id"] and broken.get("component") in ("nic", "pcie", "gpu"):
                srv["components"][broken.get("component")] = "healthy"
                broken.clear()
        elif op == "pulse_buses":
            for bus in mb.get("buses") or []:
                util = int(bus.get("util_pct") or 0)
                bus["util_pct"] = min(95, max(1, util + (7 if util < 50 else -5)))
        else:
            return {"ok": False, "error": f"Unknown motherboard op: {op}"}
        _twin_journal(state, "motherboard_ops", {"asset_id": srv["id"], "op": op})
        _event(state, f"Motherboard {op} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Motherboard: {op}", "motherboard": mb, "service_mode": sm}

    if action == "raid_create_vd":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        level = payload.get("raid_level") or "RAID1"
        name = payload.get("name") or f"VD{len(raid.get('virtual_disks') or [])}"
        members = payload.get("members") or []
        vd = {
            "id": f"VD{len(raid.get('virtual_disks') or [])}",
            "name": name,
            "raid_level": level,
            "size_gb": int(payload.get("size_gb") or 1920),
            "members": members,
            "status": "optimal",
            "read_policy": "ReadAhead",
            "write_policy": payload.get("write_policy") or "WriteBack",
            "stripe_kb": int(payload.get("stripe_kb") or 64),
            "rebuild_pct": None,
        }
        raid.setdefault("virtual_disks", []).append(vd)
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "create_vd", "detail": vd["id"]})
        _event(state, f"Created {level} volume {name} on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Virtual disk {name} created", "raid": raid}

    if action == "raid_fail_disk":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        disk_id = payload.get("disk_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        disk = next((d for d in raid.get("physical_disks", []) if d.get("id") == disk_id), None)
        if not disk:
            return {"ok": False, "error": f"Disk {disk_id} not found"}
        disk["status"] = "failed"
        disk["smart"] = "Predictive Failure"
        srv["components"]["disk"] = "failed"
        for vd in raid.get("virtual_disks", []):
            if disk_id in (vd.get("members") or []):
                vd["status"] = "degraded"
                vd["rebuild_pct"] = 0
        _event(state, f"Disk {disk_id} failed on {srv['id']}", "danger")
        _save(session_id, entry)
        return {"ok": True, "message": f"{disk_id} marked failed", "raid": raid}

    if action == "raid_rebuild":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        vd_id = payload.get("vd_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        vd = next((v for v in raid.get("virtual_disks", []) if v.get("id") == vd_id), None)
        if not vd:
            return {"ok": False, "error": f"VD {vd_id} not found"}
        if vd.get("status") == "rebuilding":
            return {"ok": True, "message": f"{vd_id} already rebuilding ({vd.get('rebuild_pct') or 0}%)", "raid": raid}
        if vd.get("status") not in ("degraded", "rebuilding"):
            return {"ok": False, "error": f"{vd_id} is {vd.get('status')} — only degraded volumes can rebuild"}
        # Promote hotspare into the array if available (failed member stays failed until complete)
        spare = next((d for d in raid.get("physical_disks", []) if d.get("status") == "hotspare"), None)
        failed = next((d for d in raid.get("physical_disks", []) if d.get("status") == "failed"), None)
        if spare:
            spare["status"] = "rebuilding"
            if failed and failed["id"] in (vd.get("members") or []):
                vd["members"] = [spare["id"] if m == failed["id"] else m for m in vd["members"]]
                vd["rebuild_source"] = failed["id"]
                vd["rebuild_target"] = spare["id"]
        vd["status"] = "rebuilding"
        vd["rebuild_pct"] = max(5, int(vd.get("rebuild_pct") or 0) or 8)
        raid.setdefault("operations", []).insert(0, {
            "time": _now_iso(), "op": "rebuild_start", "detail": f"{vd_id} @ {vd['rebuild_pct']}%",
        })
        _event(state, f"RAID rebuild started for {vd_id} on {srv['id']} ({vd['rebuild_pct']}%)", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": f"{vd_id} rebuilding ({vd['rebuild_pct']}%)", "raid": raid}

    if action == "raid_advance_rebuild":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id) if asset_id else None
        from apps.vmware_sim.datacenter_facility_ops import advance_raid_rebuilds
        advanced = advance_raid_rebuilds(state, only_server_id=(srv or {}).get("id"))
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Advanced {len(advanced)} rebuild(s)",
            "advanced": advanced,
            "raid": (srv or {}).get("raid") if srv else None,
        }

    if action == "raid_set_cache":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        cache = raid.setdefault("cache", {})
        if payload.get("mode"):
            cache["mode"] = payload["mode"]
        _event(state, f"RAID cache set to {cache.get('mode')} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Cache policy updated", "raid": raid}

    if action == "bios_enter_setup":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bios = srv.setdefault("bios", {})
        bios["setup_open"] = True
        bios["post_state"] = "setup"
        _event(state, f"Entered BIOS/UEFI setup on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "BIOS setup open", "bios": bios}

    if action == "bios_exit_setup":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bios = srv.setdefault("bios", {})
        bios["setup_open"] = False
        bios["post_state"] = "idle"
        _save(session_id, entry)
        return {"ok": True, "message": "Exited BIOS setup", "bios": bios}

    if action == "bios_set":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        key = payload.get("key") or ""
        value = payload.get("value")
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bios = srv.setdefault("bios", {})
        if key == "boot_order" and isinstance(value, list):
            bios["boot_order"] = value
        elif key in bios.get("settings", {}):
            bios["settings"][key] = value
        elif key in ("secure_boot", "mode"):
            bios[key] = value
        else:
            return {"ok": False, "error": f"Unknown BIOS setting: {key}"}
        _event(state, f"BIOS {key}={value} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"BIOS {key} updated", "bios": bios}

    if action == "bios_cmos_reset":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        from apps.vmware_sim.datacenter_digital_twin import build_bios
        srv["bios"] = build_bios(srv.get("vendor") or "Dell")
        srv["bios"]["cmos_cleared"] = True
        _event(state, f"CMOS cleared on {srv['id']}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "CMOS reset complete", "bios": srv["bios"]}

    if action == "bmc_mount_virtual_media":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        image = payload.get("image") or "rhel-9.4-x86_64-dvd.iso"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        bmc.setdefault("virtual_media", {})["mounted"] = True
        bmc["virtual_media"]["image"] = image
        bmc.setdefault("sel", []).insert(0, {"time": _now_iso(), "severity": "info", "message": f"Virtual media mounted: {image}"})
        _event(state, f"Virtual media {image} mounted on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Mounted {image}", "bmc": bmc}

    if action == "bmc_run_diagnostics":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        suite = payload.get("suite") or "Memory"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        diag = bmc.setdefault("diagnostics", {})
        failed = any(v != "healthy" for v in srv.get("components", {}).values())
        diag["last_run"] = _now_iso()
        diag["result"] = "FAIL" if failed and suite in ("Memory", "Storage", "CPU") else "PASS"
        diag["suite"] = suite
        bmc.setdefault("sel", []).insert(0, {
            "time": _now_iso(), "severity": "warning" if diag["result"] == "FAIL" else "info",
            "message": f"ePSA/Insight Diagnostics {suite}: {diag['result']}",
        })
        _event(state, f"Diagnostics {suite}={diag['result']} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"{suite} diagnostics {diag['result']}", "bmc": bmc}

    if action == "bmc_update_network":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        net = bmc.setdefault("network", {})
        for k in ("ipv4", "gateway", "vlan", "mode"):
            if k in payload and payload[k] is not None:
                net[k] = payload[k]
        _event(state, f"BMC network updated on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "BMC network updated", "bmc": bmc}

    # ── Phase 2: catalog, inventory, failure inject, service, RAID/BIOS/BMC depth ──

    if action == "get_hardware_catalog":
        from apps.vmware_sim.datacenter_hardware_catalog import full_catalog
        return {"ok": True, "catalog": full_catalog()}

    if action == "inject_failure":
        from apps.vmware_sim.datacenter_hardware_catalog import FAILURE_PRESETS
        preset_id = payload.get("preset") or payload.get("failure") or ""
        preset = next((p for p in FAILURE_PRESETS if p["id"] == preset_id), None)
        if not preset:
            return {"ok": False, "error": f"Unknown failure preset: {preset_id}"}
        target_type = preset.get("target") or "server"
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        if target_type == "server":
            srv = _find_server(state, asset_id) or next((s for s in state.get("servers", [])), None)
            if not srv:
                return {"ok": False, "error": "No server for failure injection"}
            comp = preset["component"]
            if comp == "firmware":
                state["broken"] = {"server": srv["id"], "component": "firmware"}
                srv["firmware_version"] = "CORRUPT"
                _event(state, f"Injected firmware corruption on {srv['id']}", "danger")
            elif comp == "cable":
                hw = srv.setdefault("hardware", _hardware_inventory(
            srv.get("hostname") or srv["id"],
            vendor=srv.get("vendor") or "Dell",
            role=srv.get("role"),
            model=srv.get("model"),
        ))
                cables = hw.setdefault("cables", [])
                if cables:
                    cables[0]["status"] = "damaged" if preset.get("detail") == "fiber" else "loose"
                    state["broken"] = {"server": srv["id"], "component": "cable", "cable_id": cables[0]["id"]}
                if preset.get("detail") == "fiber":
                    from apps.vmware_sim.datacenter_facility_ops import build_optical, optical_op
                    opt = state.get("optical") or build_optical()
                    _, _, opt = optical_op(opt, "cut_fiber", trunk_id="TRK-MPO-02")
                    state["optical"] = opt
                _event(state, f"Injected cable/fiber fault on {srv['id']}", "danger")
            elif comp == "pxe":
                bios = srv.setdefault("bios", {})
                bios.setdefault("settings", {})["PXEBoot"] = "Disabled"
                state["broken"] = {"server": srv["id"], "component": "pxe"}
                from apps.vmware_sim.datacenter_plant_provision import build_pxe_maas, pxe_maas_op
                platform = state.get("pxe_maas") or build_pxe_maas(state.get("servers") or [])
                _, _, platform = pxe_maas_op(platform, "break_dhcp")
                state["pxe_maas"] = platform
                _event(state, f"Injected PXE failure on {srv['id']}", "danger")
            elif comp in srv.get("components", {}):
                srv["components"][comp] = "failed"
                if comp == "dimm":
                    mb = srv.setdefault("motherboard", {})
                    slots = mb.get("dimm_slots") or []
                    if slots:
                        slots[0]["status"] = "failed"
                        slots[0]["ecc_corrections_24h"] = 128
                if comp == "raid":
                    raid = srv.setdefault("raid", {})
                    disks = raid.get("physical_disks") or []
                    if disks:
                        disks[0]["status"] = "failed"
                        disks[0]["smart"] = "Predictive Failure"
                    for vd in raid.get("virtual_disks") or []:
                        vd["status"] = "degraded"
                if comp == "fan":
                    hw = srv.setdefault("hardware", _hardware_inventory(
            srv.get("hostname") or srv["id"],
            vendor=srv.get("vendor") or "Dell",
            role=srv.get("role"),
            model=srv.get("model"),
        ))
                    fans = hw.get("fans") or []
                    if fans:
                        fans[0]["status"] = "failed"
                        fans[0]["rpm"] = 0
                if comp in ("cpu", "motherboard", "power") and payload.get("power_off"):
                    srv["power_state"] = "off"
                    if srv.get("bmc"):
                        srv["bmc"]["power"] = "off"
                detail = preset.get("detail")
                state["broken"] = {"server": srv["id"], "component": comp, **({"detail": detail} if detail else {})}
                state["goal"] = {"title": preset["label"], "objective": f"Troubleshoot and remediate {preset['label']} on {srv.get('hostname')}."}
                _event(state, f"Injected {preset['label']} on {srv['id']}", "danger")
            else:
                state["broken"] = {"server": srv["id"], "component": comp}
                _event(state, f"Injected {preset['label']} on {srv['id']}", "danger")
            # twin journal
            _twin_journal(state, "inject_failure", {"preset": preset_id, "asset_id": srv["id"]})
        elif target_type == "facility":
            if preset["component"] == "cooling":
                cooling = state.get("cooling") or []
                if cooling:
                    cooling[0]["status"] = "failed"
                    cooling[0]["ashrae_ok"] = False
                    inlet = 36.0 if preset.get("detail") == "thermal" else 31.0
                    if preset.get("detail") == "thermal":
                        cooling[0]["temp_c"] = 42.0
                    else:
                        cooling[0]["temp_c"] = max(float(cooling[0].get("temp_c") or 22), 28.0)
                    state["broken"] = {"server": None, "component": "cooling", "target": cooling[0]["id"]}
                    _apply_thermal_to_zone(state, inlet_c=inlet, exhaust_c=inlet + 14, fans_rpm=9800)
                    _recompute_facility(state)
            elif preset["component"] == "ups":
                ups = (state.get("power_chain") or {}).get("ups") or {}
                if isinstance(ups, dict):
                    ups["status"] = "failed"
                    ups["on_battery"] = True
                state["broken"] = {"server": None, "component": "ups", "target": "UPS-A"}
            elif preset["component"] in ("leak", "fire"):
                fac = state.setdefault("facility", {})
                fac["alarm"] = preset["component"]
                state["broken"] = {"server": None, "component": preset["component"], "target": "facility"}
                if preset["component"] == "leak":
                    from apps.vmware_sim.datacenter_plant_provision import build_liquid_cooling, liquid_cooling_op
                    loop = state.get("liquid_cooling") or build_liquid_cooling(state.get("servers") or [])
                    _, _, loop = liquid_cooling_op(loop, "inject_leak")
                    state["liquid_cooling"] = loop
                    state["broken"]["detail"] = "water_leak"
                    state["broken"]["target"] = "liquid-leak"
                    from apps.vmware_sim.datacenter_facility_ops import build_environmental, environmental_op
                    env = state.get("environmental") or build_environmental(state.get("servers") or [])
                    _, _, env = environmental_op(env, "trip_leak")
                    state["environmental"] = env
                if preset["component"] == "fire":
                    from apps.vmware_sim.datacenter_facility_ops import build_fire_safety, fire_safety_op
                    fs = state.get("fire_safety") or build_fire_safety()
                    _, _, fs = fire_safety_op(fs, "smoke_alarm", zone_id="FZ-A")
                    state["fire_safety"] = fs
                    state["broken"]["target"] = "FZ-A"
            state["goal"] = {"title": preset["label"], "objective": f"Respond to {preset['label']}."}
            _event(state, f"Injected facility fault: {preset['label']}", "danger")
            _twin_journal(state, "inject_failure", {"preset": preset_id})
        elif target_type == "network":
            net = state.setdefault("network", {})
            net.setdefault("faults", []).insert(0, {"time": _now_iso(), "type": preset["component"], "label": preset["label"]})
            if preset["component"] == "switch":
                switches = net.get("switches") or []
                if switches:
                    for p in switches[0].get("ports") or []:
                        p["status"] = "down"
                    state["broken"] = {"server": None, "component": "switch", "target": switches[0]["id"]}
            else:
                state["broken"] = {"server": None, "component": preset["component"], "target": "network"}
            state["goal"] = {"title": preset["label"], "objective": f"Remediate {preset['label']}."}
            _event(state, f"Injected network fault: {preset['label']}", "danger")
        _save(session_id, entry)
        return {"ok": True, "message": f"Failure injected: {preset['label']}", "broken": state.get("broken")}

    if action == "clear_failure":
        broken = state.get("broken") or {}
        if not broken:
            return {"ok": True, "message": "No open fault", "broken": {}}
        # Light remediations so Clear fault is usable after inject without a full FRU path
        comp = broken.get("component")
        srv = _find_server(state, broken.get("server") or "") if broken.get("server") else None
        if srv and comp in (srv.get("components") or {}):
            srv["components"][comp] = "ok"
        if srv and comp == "fan":
            for f in (srv.get("hardware") or {}).get("fans") or []:
                if f.get("status") == "failed":
                    f["status"] = "healthy"
                    f["rpm"] = f.get("rpm") or 7200
        if srv and comp == "dimm":
            for slot in (srv.get("motherboard") or {}).get("dimm_slots") or []:
                if slot.get("status") == "failed":
                    slot["status"] = "ok"
                    slot["ecc_corrections_24h"] = 0
        if srv and comp == "raid":
            raid = srv.get("raid") or {}
            for d in raid.get("physical_disks") or []:
                if d.get("status") == "failed":
                    d["status"] = "online"
                    d["smart"] = "OK"
            for vd in raid.get("virtual_disks") or []:
                if vd.get("status") == "degraded":
                    vd["status"] = "optimal"
        if srv and comp == "cable":
            for c in (srv.get("hardware") or {}).get("cables") or []:
                if c.get("status") in ("damaged", "loose"):
                    c["status"] = "ok"
        if srv and comp == "firmware":
            if srv.get("firmware_version") == "CORRUPT":
                srv["firmware_version"] = "2.0.0"
        if srv and comp == "pxe":
            bios = srv.setdefault("bios", {})
            bios.setdefault("settings", {})["PXEBoot"] = "Enabled"
        if comp == "cooling":
            for u in state.get("cooling") or []:
                if u.get("status") == "failed":
                    u["status"] = "running"
                    u["ashrae_ok"] = True
                    u["temp_c"] = 22.0
            _recompute_facility(state)
        if comp == "ups":
            ups = (state.get("power_chain") or {}).get("ups")
            if isinstance(ups, dict):
                ups["status"] = "online"
                ups["on_battery"] = False
            elif isinstance(ups, list):
                for u in ups:
                    u["status"] = "online"
                    u["on_battery"] = False
        if comp == "cable" or (broken.get("detail") == "fiber"):
            from apps.vmware_sim.datacenter_facility_ops import build_optical, optical_op
            opt = state.get("optical") or build_optical()
            for tr in opt.get("trunks") or []:
                if tr.get("status") == "cut":
                    _, _, opt = optical_op(opt, "repair_fiber", trunk_id=tr["id"])
            state["optical"] = opt
        if comp in ("leak", "fire"):
            fac = state.setdefault("facility", {})
            if fac.get("alarm") in ("leak", "fire"):
                fac["alarm"] = None
        broken.clear()
        state["broken"] = {}
        state["goal"] = {"title": "Facility clear", "objective": "No open injected faults."}
        training = state.get("training") or {}
        if training.get("active"):
            prog = training.setdefault("progress", [])
            if "Clear fault" not in prog:
                prog.append("Clear fault")
            training["feedback"] = "Fault cleared. Training step recorded."
        _twin_journal(state, "clear_failure", {"component": comp})
        _event(state, f"Cleared fault ({comp or 'unknown'})", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Fault cleared", "broken": {}, "training": training}

    if action == "service_mode_action":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        op = payload.get("op") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        sm = srv.setdefault("service_mode", {})
        mb = srv.setdefault("motherboard", {})
        inv = srv.setdefault("inventory", {})
        hist = inv.setdefault("replacement_history", [])

        if op == "extend_rails":
            sm["rails_extended"] = True
        elif op == "retract_rails":
            sm["rails_extended"] = False
        elif op == "open_cover":
            sm["cover_open"] = True
            mb["cover_open"] = True
            mb["maintenance_mode"] = True
        elif op == "close_cover":
            sm["cover_open"] = False
            mb["cover_open"] = False
            mb["maintenance_mode"] = False
        elif op == "remove_air_shroud":
            sm["air_shroud_removed"] = True
        elif op == "install_air_shroud":
            sm["air_shroud_removed"] = False
        elif op == "disconnect_power":
            sm["power_cables_disconnected"] = True
            srv["power_state"] = "off"
            if srv.get("bmc"):
                srv["bmc"]["power"] = "off"
        elif op == "reconnect_power":
            sm["power_cables_disconnected"] = False
        elif op == "disconnect_network":
            sm["network_cables_disconnected"] = True
        elif op == "reconnect_network":
            sm["network_cables_disconnected"] = False
        elif op == "remove_cpu":
            sock = payload.get("socket_id") or "CPU1"
            if sock not in sm.setdefault("cpu_removed", []):
                sm["cpu_removed"].append(sock)
            for c in mb.get("cpu_sockets") or []:
                if c.get("id") == sock:
                    c["populated"] = False
                    c["status"] = "empty"
        elif op == "install_cpu":
            sock = payload.get("socket_id") or "CPU1"
            sm["cpu_removed"] = [x for x in sm.get("cpu_removed", []) if x != sock]
            for c in mb.get("cpu_sockets") or []:
                if c.get("id") == sock:
                    c["populated"] = True
                    c["status"] = "healthy"
                    c["paste_applied"] = False
            hist.insert(0, {"time": _now_iso(), "part": sock, "action": "cpu_install"})
            if broken.get("server") == srv["id"] and broken.get("component") == "cpu":
                srv["components"]["cpu"] = "healthy"
                broken.clear()
        elif op == "remove_heatsink":
            sock = payload.get("socket_id") or "CPU1"
            if sock not in sm.setdefault("heatsink_removed", []):
                sm["heatsink_removed"].append(sock)
        elif op == "install_heatsink":
            sock = payload.get("socket_id") or "CPU1"
            sm["heatsink_removed"] = [x for x in sm.get("heatsink_removed", []) if x != sock]
        elif op == "replace_cmos":
            sm["cmos_battery_ok"] = True
            for chip in mb.get("chips") or []:
                if chip.get("id") == "CMOS":
                    chip["status"] = "healthy"
                    chip["voltage_v"] = 3.2
            hist.insert(0, {"time": _now_iso(), "part": "CMOS", "action": "replace"})
        elif op == "replace_tpm":
            sm["tpm_present"] = True
            for chip in mb.get("chips") or []:
                if chip.get("id") == "TPM":
                    chip["status"] = "healthy"
            hist.insert(0, {"time": _now_iso(), "part": "TPM", "action": "replace"})
        elif op == "hotswap_psu":
            slot = payload.get("psu_id") or "PSU1"
            hw = srv.setdefault("hardware", _hardware_inventory(
            srv.get("hostname") or srv["id"],
            vendor=srv.get("vendor") or "Dell",
            role=srv.get("role"),
            model=srv.get("model"),
        ))
            for p in hw.get("psus") or []:
                if p.get("id") == slot:
                    p["status"] = "healthy"
            srv["components"]["power"] = "healthy"
            hist.insert(0, {"time": _now_iso(), "part": slot, "action": "hotswap_psu"})
            if broken.get("server") == srv["id"] and broken.get("component") == "power":
                broken.clear()
        else:
            return {"ok": False, "error": f"Unknown service op: {op}"}
        _twin_journal(state, "service_mode_action", {
            "asset_id": srv["id"], "op": op, "slot": payload.get("slot"),
        })
        _event(state, f"Service mode {op} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Service: {op}", "service_mode": sm, "motherboard": mb, "inventory": inv}

    if action == "raid_delete_vd":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        vd_id = payload.get("vd_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        before = len(raid.get("virtual_disks") or [])
        raid["virtual_disks"] = [v for v in raid.get("virtual_disks") or [] if v.get("id") != vd_id]
        if len(raid["virtual_disks"]) == before:
            return {"ok": False, "error": f"VD {vd_id} not found"}
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "delete_vd", "detail": vd_id})
        _event(state, f"Deleted {vd_id} on {srv['id']}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": f"Deleted {vd_id}", "raid": raid}

    if action == "raid_patrol_read":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        pr = raid.setdefault("patrol_read", {})
        pr["status"] = "completed"
        pr["last_run"] = _now_iso()
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "patrol_read", "detail": "ok"})
        _event(state, f"Patrol read completed on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Patrol read complete", "raid": raid}

    if action == "raid_consistency_check":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        cc = raid.setdefault("consistency_check", {})
        cc["status"] = "completed"
        cc["last_run"] = _now_iso()
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "consistency_check", "detail": "ok"})
        _event(state, f"Consistency check completed on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Consistency check complete", "raid": raid}

    if action == "raid_import_foreign":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        raid["foreign_config"] = False
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "import_foreign", "detail": "cleared"})
        _event(state, f"Foreign configuration imported on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Foreign config imported", "raid": raid}

    if action == "raid_assign_hotspare":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        disk_id = payload.get("disk_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        disk = next((d for d in raid.get("physical_disks", []) if d.get("id") == disk_id), None)
        if not disk:
            return {"ok": False, "error": f"Disk {disk_id} not found"}
        # Only unassigned online disks (not VD members) become hot spares
        members = {m for vd in raid.get("virtual_disks") or [] for m in (vd.get("members") or [])}
        if disk_id in members:
            return {"ok": False, "error": f"{disk_id} is a VD member"}
        disk["status"] = "hotspare"
        spares = raid.setdefault("hot_spares", [])
        if disk_id not in spares:
            spares.append(disk_id)
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "assign_hotspare", "detail": disk_id})
        _event(state, f"Assigned hot spare {disk_id} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"{disk_id} → hot spare", "raid": raid}

    if action == "raid_expand_vd":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        vd_id = payload.get("vd_id") or ""
        add_gb = int(payload.get("add_gb") or 500)
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        vd = next((v for v in raid.get("virtual_disks", []) if v.get("id") == vd_id), None)
        if not vd:
            return {"ok": False, "error": f"VD {vd_id} not found"}
        if vd.get("status") not in ("optimal", "degraded"):
            return {"ok": False, "error": f"{vd_id} cannot expand in state {vd.get('status')}"}
        vd["size_gb"] = int(vd.get("size_gb") or 0) + add_gb
        vd["status"] = "optimal"
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "expand_vd", "detail": f"{vd_id}+{add_gb}G"})
        _event(state, f"Expanded {vd_id} by {add_gb}G on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"{vd_id} expanded +{add_gb}G", "raid": raid}

    if action == "raid_initialize_vd":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        vd_id = payload.get("vd_id") or ""
        mode = payload.get("mode") or "fast"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        raid = srv.setdefault("raid", {})
        vd = next((v for v in raid.get("virtual_disks", []) if v.get("id") == vd_id), None)
        if not vd:
            return {"ok": False, "error": f"VD {vd_id} not found"}
        vd["init_mode"] = mode
        vd["init_pct"] = 100
        vd["status"] = "optimal"
        raid.setdefault("operations", []).insert(0, {"time": _now_iso(), "op": "initialize", "detail": f"{vd_id}:{mode}"})
        _event(state, f"Initialized {vd_id} ({mode}) on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"{vd_id} initialized ({mode})", "raid": raid}

    if action == "bios_run_post":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bios = srv.setdefault("bios", {})
        bios["post_state"] = "posting"
        bios["post_log"] = [
            "POST: CPU OK", "POST: Memory OK", "POST: PCI devices enumerated",
            "POST: Storage controllers OK", "POST: Booting UEFI...",
        ]
        failed = [k for k, v in (srv.get("components") or {}).items() if v != "healthy"]
        if failed:
            bios["post_log"].append(f"POST WARNING: degraded components: {', '.join(failed)}")
            bios["post_state"] = "setup"
        else:
            bios["post_state"] = "os"
        _event(state, f"POST completed on {srv['id']} → {bios['post_state']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "POST complete", "bios": bios}

    if action == "bios_set_password":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bios = srv.setdefault("bios", {})
        pwd = payload.get("password") or ""
        bios["password_set"] = bool(pwd)
        bios["password"] = "***" if pwd else None
        _event(state, f"BIOS password {'set' if pwd else 'cleared'} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "BIOS password updated", "bios": bios}

    if action == "bios_flash":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        version = payload.get("version") or "2.14.0"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bios = srv.setdefault("bios", {})
        bios["flash_in_progress"] = False
        bios["version"] = version
        srv["firmware_version"] = version
        if srv.get("inventory"):
            srv["inventory"].setdefault("firmware", {})["bios"] = version
        if broken.get("server") == srv["id"] and broken.get("component") == "firmware":
            broken.clear()
        _event(state, f"BIOS flashed to {version} on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"BIOS {version}", "bios": bios}

    if action == "bmc_nmi":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        bmc.setdefault("sel", []).insert(0, {"time": _now_iso(), "severity": "warning", "message": "NMI generated via BMC"})
        _event(state, f"NMI issued on {srv['id']}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "NMI issued", "bmc": bmc}

    if action == "bmc_flash_target":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        target = payload.get("target") or "BMC"
        version = payload.get("version") or "next"
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        if target == "BMC":
            bmc["firmware"] = version if version != "next" else bmc.get("firmware", "6.10.30.00")
        bmc.setdefault("lifecycle_log", []).insert(0, {"time": _now_iso(), "message": f"Flashed {target} → {version}"})
        bmc.setdefault("sel", []).insert(0, {"time": _now_iso(), "severity": "info", "message": f"Firmware update {target} complete"})
        if srv.get("inventory"):
            srv["inventory"].setdefault("firmware", {})[target.lower()] = version
        _event(state, f"BMC flashed {target} on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"{target} firmware updated", "bmc": bmc}

    if action == "bmc_open_kvm":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        bmc = srv.setdefault("bmc", {})
        bmc.setdefault("console", {})["kvm_active"] = True
        state["console"] = {
            "open": True,
            "asset_id": srv["id"],
            "lines": [
                f"=== {bmc.get('product')} HTML5 KVM — {srv.get('hostname')} ===",
                "Remote console session established.",
                "Press F2 for Setup | F12 for PXE | Esc for Boot Menu",
            ],
        }
        _event(state, f"HTML5 KVM opened on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "KVM open", "console": state["console"], "bmc": bmc}

    if action == "bmc_set_generation":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        generation = payload.get("generation") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        from apps.vmware_sim.datacenter_digital_twin import build_bmc
        vendor = srv.get("vendor") or "Dell"
        hostname = srv.get("hostname") or srv["id"]
        power = srv.get("power_state") or "on"
        prev = srv.get("bmc") or {}
        gens = prev.get("generations_available") or []
        if generation and gens and generation not in gens:
            return {"ok": False, "error": f"{generation} not available for {vendor}"}
        rich = build_bmc(hostname, vendor, power, generation=generation or None)
        rich["endpoint"] = prev.get("endpoint") or rich["endpoint"]
        rich["network"] = prev.get("network") or rich["network"]
        rich["users"] = prev.get("users") or rich["users"]
        if prev.get("sel"):
            rich["sel"] = prev["sel"]
        rich.setdefault("sel", []).insert(0, {
            "time": _now_iso(), "severity": "info",
            "message": f"BMC product switched to {rich.get('product')}",
        })
        srv["bmc"] = rich
        if srv.get("inventory"):
            srv["inventory"].setdefault("firmware", {})["bmc"] = rich.get("firmware")
        _twin_journal(state, "bmc_set_generation", {"asset_id": srv["id"], "generation": rich.get("product")})
        _event(state, f"BMC generation → {rich.get('product')} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"BMC → {rich.get('product')}", "bmc": rich}

    # ── Phase 3: switch CLI, net tools, cables, storage ─────────────────────

    if action == "switch_cli":
        from apps.vmware_sim.datacenter_network_storage import run_switch_cli, enrich_network
        switch_id = payload.get("switch_id") or ""
        command = payload.get("command") or ""
        net = state.setdefault("network", {})
        enrich_network(net)
        sw = next((s for s in net.get("switches") or [] if s.get("id") == switch_id or s.get("hostname") == switch_id), None)
        if not sw and net.get("switches"):
            sw = net["switches"][0]
        if not sw:
            return {"ok": False, "error": "No switch found"}
        lines = run_switch_cli(sw, command)
        # Clear switch failure if admin no shutdown restored ports
        if broken.get("component") == "switch" and broken.get("target") == sw.get("id"):
            if any(p.get("status") == "up" for p in sw.get("ports") or []):
                broken.clear()
        # Journal config-mutating CLI (skip pure show/help/ping)
        cl = (command or "").strip().lower()
        if cl and not cl.startswith("show") and cl not in ("?", "help") and not cl.startswith("ping"):
            _twin_journal(state, "switch_cli", {"switch_id": sw["id"], "command": command})
            # Clear MPLS/EVPN faults when CLI re-enables them
            if broken.get("component") in ("mpls", "evpn", "vxlan"):
                proto = sw.get("protocols") or {}
                if broken["component"] == "mpls" and (proto.get("mpls") or {}).get("enabled"):
                    broken.clear()
                if broken["component"] in ("evpn", "vxlan") and (proto.get("evpn") or {}).get("enabled"):
                    broken.clear()
        _event(state, f"CLI on {sw.get('hostname')}: {command}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "CLI ok", "switch_id": sw["id"], "output": lines, "switch": sw}

    if action == "net_ping":
        from apps.vmware_sim.datacenter_network_storage import run_switch_cli
        host = payload.get("host") or "10.0.0.1"
        # Reuse ping formatter
        lines = run_switch_cli({"ports": [], "cli_style": "cisco", "hostname": "tools"}, f"ping {host}")
        tools = state.setdefault("network", {}).setdefault("tools", {})
        tools["last_ping"] = {"host": host, "lines": lines, "time": _now_iso()}
        if broken.get("component") in ("dns", "dhcp") and "0%" in "\n".join(lines):
            pass  # ping alone doesn't clear DNS
        _event(state, f"ping {host}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"ping {host}", "output": lines, "tools": tools}

    if action == "net_traceroute":
        from apps.vmware_sim.datacenter_network_storage import run_traceroute
        dest = payload.get("dest") or payload.get("host") or "10.99.0.10"
        result = run_traceroute(dest)
        tools = state.setdefault("network", {}).setdefault("tools", {})
        tools["last_traceroute"] = result
        lines = [f"{h['hop']}  {h['host']} ({h['ip']})  {h['rtt_ms']} ms" for h in result["hops"]]
        _event(state, f"traceroute {dest}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"traceroute {dest}", "output": lines, "result": result}

    if action == "net_iperf":
        from apps.vmware_sim.datacenter_network_storage import run_iperf
        src = payload.get("src") or "srv-r01-u12"
        dst = payload.get("dst") or "srv-r04-u06"
        result = run_iperf(src, dst, int(payload.get("seconds") or 5))
        tools = state.setdefault("network", {}).setdefault("tools", {})
        tools["last_iperf"] = result
        lines = [
            f"iperf3: {src} → {dst}",
            f"Interval 0.0-{result['seconds']}.0 sec  Transfer  Bandwidth {result['throughput_gbps']} Gbits/sec",
            f"Retransmits: {result['retransmits']}",
        ]
        _event(state, f"iperf {src}→{dst} {result['throughput_gbps']}Gbps", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "iperf complete", "output": lines, "result": result}

    if action == "net_fix_protocol":
        from apps.vmware_sim.datacenter_network_storage import enrich_network
        proto = payload.get("protocol") or "bgp"
        net = state.setdefault("network", {})
        enrich_network(net)
        for sw in net.get("switches") or []:
            p = sw.setdefault("protocols", {})
            if proto == "bgp":
                p.setdefault("bgp", {})["status"] = "up"
                p["bgp"]["established"] = p["bgp"].get("peers", 2)
            elif proto == "vlan":
                # restore VLANs on downed access ports
                for port in sw.get("ports") or []:
                    if port.get("connected_to") and not port.get("vlan"):
                        port["vlan"] = 10
                        port["status"] = "up"
            elif proto == "ospf":
                p.setdefault("ospf", {})["status"] = "full"
            elif proto == "mpls":
                m = p.setdefault("mpls", {})
                m["enabled"] = True
                m["status"] = "established"
                m.setdefault("ldp_neighbors", ["10.0.0.1", "10.0.0.2"])
                m.setdefault("labels", [
                    {"in": 16001, "out": 3, "fec": "10.10.0.0/16"},
                ])
            elif proto in ("evpn", "vxlan"):
                ev = p.setdefault("evpn", {})
                vx = p.setdefault("vxlan", {})
                ev["enabled"] = True
                ev["status"] = "established"
                vx["enabled"] = True
                if not vx.get("vnis"):
                    vx["vnis"] = [10010, 10020]
                if not ev.get("neighbors"):
                    ev["neighbors"] = ["10.0.0.1"]
        if broken.get("component") in ("bgp", "vlan", "ospf", "mpls", "evpn", "vxlan", proto):
            broken.clear()
        _twin_journal(state, "net_fix_protocol", {"protocol": proto})
        _event(state, f"Restored network protocol {proto}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"{proto} restored", "network": net}

    if action == "cable_ops":
        from apps.vmware_sim.datacenter_network_storage import cable_action, enrich_cables
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        hw = srv.setdefault("hardware", _hardware_inventory(
            srv.get("hostname") or srv["id"],
            vendor=srv.get("vendor") or "Dell",
            role=srv.get("role"),
            model=srv.get("model"),
        ))
        hw["cables"] = enrich_cables(hw.get("cables") or [])
        ok, msg, cable = cable_action(
            hw["cables"],
            payload.get("cable_id") or "",
            payload.get("op") or "label",
            label=payload.get("label"),
            route=payload.get("route"),
            cable_type=payload.get("cable_type"),
            bend_radius_mm=payload.get("bend_radius_mm"),
            tension_n=payload.get("tension_n"),
        )
        if not ok:
            return {"ok": False, "error": msg}
        if cable and cable.get("status") == "seated" and broken.get("server") == srv["id"] and broken.get("component") == "cable":
            if all(c.get("status") == "seated" for c in hw["cables"]):
                broken.clear()
        _event(state, f"Cable {msg} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "cables": hw["cables"], "cable": cable}

    if action == "storage_ops":
        from apps.vmware_sim.datacenter_network_storage import storage_action, build_storage_stack
        asset_id = payload.get("asset_id") or state.get("selected_asset") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        stack = srv.setdefault("storage_stack", build_storage_stack(srv.get("role")))
        ok, msg = storage_action(
            stack,
            payload.get("op") or "ceph_status",
            bay_id=payload.get("bay_id"),
            lun_id=payload.get("lun_id"),
            path=payload.get("path"),
            clients=payload.get("clients"),
            mode=payload.get("mode"),
        )
        if not ok:
            return {"ok": False, "error": msg}
        if payload.get("op") == "replace_bay" and broken.get("server") == srv["id"] and broken.get("component") == "disk":
            srv["components"]["disk"] = "healthy"
            broken.clear()
        _event(state, f"Storage {msg} on {srv['id']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "storage_stack": stack}

    # ── Phase 4–5: physics, rack FRU, ops tickets, monitoring, training ─────

    if action == "toggle_rack_casters":
        rack_id = payload.get("rack_id") or ""
        rack = next((r for r in state.get("racks") or [] if r.get("id") == rack_id), None)
        if not rack:
            return {"ok": False, "error": f"Rack {rack_id} not found"}
        phy = rack.setdefault("physics", {})
        phy["casters_locked"] = not phy.get("casters_locked", True)
        fru = rack.setdefault("fru", {})
        fru.setdefault("casters", {})["locked"] = phy["casters_locked"]
        # Unlocking casters raises tip risk
        if not phy["casters_locked"]:
            phy["tip_score"] = min(100, int(phy.get("tip_score") or 40) + 25)
            phy["tip_risk"] = "high" if phy["tip_score"] >= 65 else phy.get("tip_risk")
        _event(state, f"Rack {rack_id} casters {'locked' if phy['casters_locked'] else 'unlocked'}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Casters toggled", "rack": rack}

    if action == "install_blanking":
        rack_id = payload.get("rack_id") or ""
        u = int(payload.get("u") or 1)
        rack = next((r for r in state.get("racks") or [] if r.get("id") == rack_id), None)
        if not rack:
            return {"ok": False, "error": f"Rack {rack_id} not found"}
        fru = rack.setdefault("fru", {})
        panels = fru.setdefault("blanking_panels", [])
        existing = next((p for p in panels if p.get("u") == u), None)
        if existing:
            existing["installed"] = True
        else:
            panels.append({"u": u, "size_u": 1, "installed": True})
        from apps.vmware_sim.datacenter_phase12 import apply_blanking_to_physics
        apply_blanking_to_physics(rack, state.get("containment"))
        ct = state.get("containment")
        if ct is not None:
            total_panels = sum(
                len([p for p in ((r.get("fru") or {}).get("blanking_panels") or []) if p.get("installed")])
                for r in (state.get("racks") or [])
            )
            ct["blanking_compliance_pct"] = min(100, 40 + total_panels * 3)
        _event(state, f"Blanking panel installed at {rack_id} U{u}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Blanking U{u}", "fru": fru}

    if action == "pdu_outlet_toggle":
        rack_id = payload.get("rack_id") or ""
        outlet_id = payload.get("outlet_id") or ""
        rack = next((r for r in state.get("racks") or [] if r.get("id") == rack_id), None)
        if not rack:
            return {"ok": False, "error": f"Rack {rack_id} not found"}
        outlets = (rack.get("fru") or {}).get("pdu_outlets") or []
        out = next((o for o in outlets if o.get("id") == outlet_id), None)
        if not out:
            return {"ok": False, "error": f"Outlet {outlet_id} not found"}
        if out.get("breaker") == "closed":
            out["breaker"] = "open"
            out["energized"] = False
            out["led"] = "off"
            out["load_w"] = 0
        else:
            out["breaker"] = "closed"
            out["energized"] = True
            out["led"] = "green"
            out["load_w"] = 120
        _event(state, f"PDU outlet {outlet_id} breaker {out['breaker']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Outlet {outlet_id}", "outlet": out}

    if action == "liquid_cooling_ops":
        from apps.vmware_sim.datacenter_plant_provision import build_liquid_cooling, liquid_cooling_op
        loop = state.get("liquid_cooling") or build_liquid_cooling(state.get("servers") or [])
        op = payload.get("op") or ""
        ok, msg, loop = liquid_cooling_op(loop, op, **{k: v for k, v in payload.items() if k != "op"})
        state["liquid_cooling"] = loop
        if not ok:
            return {"ok": False, "error": msg}
        if op == "inject_leak":
            state["broken"] = {"server": None, "component": "cooling", "target": "liquid-leak", "detail": "water_leak"}
        if op == "clear_leak" and broken.get("detail") == "water_leak":
            broken.clear()
        _twin_journal(state, "liquid_cooling_ops", {"op": op})
        _event(state, f"Liquid cooling: {msg}", "warning" if "leak" in op else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "liquid_cooling": loop}

    if action == "pxe_maas_ops":
        from apps.vmware_sim.datacenter_plant_provision import build_pxe_maas, pxe_maas_op
        platform = state.get("pxe_maas") or build_pxe_maas(state.get("servers") or [])
        op = payload.get("op") or ""
        ok, msg, platform = pxe_maas_op(platform, op, **{k: v for k, v in payload.items() if k != "op"})
        state["pxe_maas"] = platform
        if not ok:
            return {"ok": False, "error": msg}
        # Sync BIOS PXE + clear pxe failure on successful pxe_boot / fix_dhcp
        asset_id = payload.get("machine_id") or payload.get("asset_id") or state.get("selected_asset")
        srv = _find_server(state, asset_id) if asset_id else None
        if op == "pxe_boot" and srv:
            bios = srv.setdefault("bios", {})
            bios.setdefault("settings", {})["PXEBoot"] = "Enabled"
            if (platform.get("region") or {}).get("dhcp"):
                if broken.get("server") == srv["id"] and broken.get("component") == "pxe":
                    broken.clear()
                console_lines = [
                    f"=== PXE → MAAS ({(platform.get('region') or {}).get('url')}) ===",
                    "1/6 DHCP discover → offer → request → ack",
                    "2/6 TFTP: bootx64.efi → grubx64.efi → vmlinuz + initrd",
                    "3/6 Kernel + initramfs · iPXE chain pxelinux.0",
                    "4/6 Curtin: partition + install rootfs",
                    "5/6 cloud-init: DataSourceMAAS · netplan · users · runcmd",
                    "6/6 Reboot → sshd listening · node Ready/Deployed path",
                    f"Host {srv.get('hostname')} · PXE stages complete",
                ]
                srv["pxe_boot_stages"] = [
                    {"id": "dhcp", "label": "DHCP", "done": True},
                    {"id": "tftp", "label": "TFTP", "done": True},
                    {"id": "kernel", "label": "Kernel", "done": True},
                    {"id": "curtin", "label": "Curtin", "done": True},
                    {"id": "cloud_init", "label": "cloud-init", "done": True},
                    {"id": "sshd", "label": "sshd", "done": True},
                ]
                srv["pxe_anim"] = {"active": True, "stage": 5, "started_at": _now_iso()}
                state["console"] = {"open": True, "asset_id": srv["id"], "lines": console_lines}
            else:
                return {"ok": False, "error": "PXE failed — DHCP down. Run fix_dhcp."}
        if op == "deploy" and srv:
            srv["power_state"] = "on"
            if srv.get("bmc"):
                srv["bmc"]["power"] = "on"
        if op == "fix_dhcp" and broken.get("component") == "pxe":
            broken.clear()
        if op == "break_dhcp":
            state["broken"] = {"server": None, "component": "pxe", "target": "maas-dhcp"}
        _twin_journal(state, "pxe_maas_ops", {"op": op, "machine_id": asset_id})
        _event(state, f"MAAS/PXE: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "pxe_maas": platform, "console": state.get("console")}

    if action == "rack_fru_ops":
        from apps.vmware_sim.datacenter_plant_provision import rack_fru_op, densify_rack_fru
        rack_id = payload.get("rack_id") or ""
        rack = next((r for r in state.get("racks") or [] if r.get("id") == rack_id), None)
        if not rack:
            return {"ok": False, "error": f"Rack {rack_id} not found"}
        fru = densify_rack_fru(rack.setdefault("fru", {}), rack_id)
        op = payload.get("op") or ""
        ok, msg, fru = rack_fru_op(fru, op, **{k: v for k, v in payload.items() if k not in ("op", "rack_id")})
        rack["fru"] = fru
        if not ok:
            return {"ok": False, "error": msg}
        _twin_journal(state, "rack_fru_ops", {"rack_id": rack_id, "op": op})
        _event(state, f"Rack FRU {rack_id}: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "fru": fru}

    if action == "fire_safety_ops":
        from apps.vmware_sim.datacenter_facility_ops import build_fire_safety, fire_safety_op
        fs = state.get("fire_safety") or build_fire_safety()
        op = payload.get("op") or ""
        ok, msg, fs = fire_safety_op(fs, op, **{k: v for k, v in payload.items() if k != "op"})
        state["fire_safety"] = fs
        if not ok:
            return {"ok": False, "error": msg}
        if op == "smoke_alarm":
            state["broken"] = {"server": None, "component": "fire", "target": payload.get("zone_id") or "FZ-A"}
            state.setdefault("facility", {})["alarm"] = "fire"
        if op in ("silence", "rearm") and broken.get("component") == "fire":
            broken.clear()
            state.setdefault("facility", {}).pop("alarm", None)
        _twin_journal(state, "fire_safety_ops", {"op": op})
        _event(state, f"Fire: {msg}", "danger" if "alarm" in op or op == "discharge" else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "fire_safety": fs}

    if action == "environmental_ops":
        from apps.vmware_sim.datacenter_facility_ops import build_environmental, environmental_op
        env = state.get("environmental") or build_environmental(state.get("servers") or [])
        op = payload.get("op") or ""
        ok, msg, env = environmental_op(env, op, **{k: v for k, v in payload.items() if k != "op"})
        state["environmental"] = env
        if not ok:
            return {"ok": False, "error": msg}
        if op == "trip_leak":
            state["broken"] = {"server": None, "component": "leak", "target": "facility", "detail": "water_leak"}
        if op in ("clear_leak", "normalize") and broken.get("component") in ("leak",):
            broken.clear()
        _twin_journal(state, "environmental_ops", {"op": op})
        _event(state, f"Env: {msg}", "warning" if op in ("trip_leak", "hotspot", "open_door") else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "environmental": env}

    if action == "optical_ops":
        from apps.vmware_sim.datacenter_facility_ops import build_optical, optical_op
        opt = state.get("optical") or build_optical()
        op = payload.get("op") or ""
        ok, msg, opt = optical_op(opt, op, **{k: v for k, v in payload.items() if k != "op"})
        state["optical"] = opt
        if not ok:
            return {"ok": False, "error": msg}
        if op == "cut_fiber":
            state["broken"] = {"server": None, "component": "cable", "target": payload.get("trunk_id") or "TRK-MPO-01", "detail": "fiber"}
        if op == "repair_fiber" and broken.get("detail") == "fiber":
            broken.clear()
        if op == "carrier_up" and broken.get("component") in ("cable",):
            pass
        _twin_journal(state, "optical_ops", {"op": op})
        _event(state, f"Optical: {msg}", "danger" if "cut" in op or "down" in op else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "optical": opt}

    if action == "refresh_capacity":
        from apps.vmware_sim.datacenter_facility_ops import build_capacity_snapshot, build_predictive_maintenance
        state["capacity"] = build_capacity_snapshot(state)
        state["predictive"] = build_predictive_maintenance(state)
        _event(state, "Capacity / PdM refreshed", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Capacity refreshed", "capacity": state["capacity"], "predictive": state["predictive"]}

    if action == "dr_ops":
        from apps.vmware_sim.datacenter_ops_platform import build_dr_platform, dr_op
        dr = state.get("dr") or build_dr_platform()
        pc = state.setdefault("power_chain", {})
        campus = state.setdefault("campus", {})
        op = payload.get("op") or ""
        ok, msg, dr, pc = dr_op(dr, pc, campus, op, **{k: v for k, v in payload.items() if k != "op"})
        state["dr"] = dr
        state["power_chain"] = pc
        if not ok:
            return {"ok": False, "error": msg}
        if op == "utility_fail":
            state["broken"] = {"server": None, "component": "ups", "target": "utility", "detail": "utility_loss"}
        if op in ("restore_utility", "site_failback") and broken.get("detail") == "utility_loss":
            broken.clear()
        if op == "site_failover":
            state["broken"] = {"server": None, "component": "dr", "target": "dc1-primary"}
        _recompute_facility(state)
        _twin_journal(state, "dr_ops", {"op": op})
        _event(state, f"DR: {msg}", "danger" if op in ("utility_fail", "site_failover") else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "dr": dr, "power_chain": pc}

    if action == "campus_plant_ops":
        from apps.vmware_sim.datacenter_facility_ops import campus_plant_op, ensure_campus_plant
        campus = ensure_campus_plant(state.setdefault("campus", {}), state.get("power_chain"))
        pc = state.get("power_chain") or {}
        op = payload.get("op") or ""
        ok, msg, campus = campus_plant_op(
            campus, pc, op, **{k: v for k, v in payload.items() if k != "op"}
        )
        state["campus"] = campus
        if not ok:
            return {"ok": False, "error": msg}
        _twin_journal(state, "campus_plant_ops", {"op": op})
        _event(state, f"Campus plant: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "campus": campus}

    if action == "access_ops":
        from apps.vmware_sim.datacenter_ops_platform import build_access_control, access_op
        ac = state.get("access_control") or build_access_control()
        op = payload.get("op") or ""
        ok, msg, ac = access_op(ac, op, **{k: v for k, v in payload.items() if k != "op"})
        state["access_control"] = ac
        if not ok:
            return {"ok": False, "error": msg}
        campus = state.setdefault("campus", {})
        campus["access"] = {
            "gate": (ac.get("gate") or {}).get("status", "secured"),
            "biometrics": (ac.get("biometrics") or {}).get("status", "online"),
            "cameras": (ac.get("cameras") or {}).get("online", 24),
        }
        # `broken` is a single-fault slot shared with hardware chaos injection,
        # so a security event must not evict an in-flight hardware fault a lab
        # is grading on. Only claim the slot when it is free, and restore what
        # was there on clear.
        if op == "tailgate_alarm":
            if not broken:
                state["broken"] = {"server": None, "component": "security", "target": "gate"}
            else:
                ac.setdefault("events", []).insert(0, {
                    "time": _now_iso(), "type": "warning",
                    "message": "Tailgate alarm raised while a hardware fault is open",
                })
        if op == "clear_alarms" and broken.get("component") == "security":
            broken.clear()
            state["broken"] = {}
        _twin_journal(state, "access_ops", {"op": op})
        _event(state, f"Access: {msg}", "warning" if "alarm" in op or "deny" in msg.lower() or "Denied" in msg else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "access_control": ac}

    if action == "automation_ops":
        from apps.vmware_sim.datacenter_ops_platform import build_automation, automation_op, build_dr_platform, dr_op
        auto = state.get("automation") or build_automation()
        op = payload.get("op") or "run"
        ok, msg, auto = automation_op(auto, op, **{k: v for k, v in payload.items() if k != "op"})
        state["automation"] = auto
        if not ok:
            return {"ok": False, "error": msg}
        # DR tabletop runbook also drives power chain when selected
        if op == "run" and payload.get("runbook_id") == "rb-dr-tabletop":
            dr = state.get("dr") or build_dr_platform()
            pc = state.setdefault("power_chain", {})
            campus = state.setdefault("campus", {})
            for step_op in ("utility_fail", "start_generator", "restore_utility"):
                _, _, dr, pc = dr_op(dr, pc, campus, step_op)
            state["dr"] = dr
            state["power_chain"] = pc
            _recompute_facility(state)
        if op == "run" and payload.get("runbook_id") == "rb-compliance-export":
            from apps.vmware_sim.datacenter_phase12 import build_evidence_pack, build_sustainability
            from apps.vmware_sim.datacenter_facility_ops import build_capacity_snapshot, build_predictive_maintenance
            state["capacity"] = build_capacity_snapshot(state)
            state["predictive"] = build_predictive_maintenance(state)
            state["sustainability"] = build_sustainability(state)
            state["evidence_pack"] = build_evidence_pack(state)
            msg = f"{msg} · evidence {state['evidence_pack']['id']}"
        _twin_journal(state, "automation_ops", {"op": op, "runbook_id": payload.get("runbook_id")})
        _event(state, f"Automation: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "automation": auto, "dr": state.get("dr"), "evidence_pack": state.get("evidence_pack")}

    if action == "generate_ops_report":
        from apps.vmware_sim.datacenter_ops_platform import build_ops_report
        from apps.vmware_sim.datacenter_facility_ops import build_capacity_snapshot, build_predictive_maintenance
        state["capacity"] = build_capacity_snapshot(state)
        state["predictive"] = build_predictive_maintenance(state)
        report = build_ops_report(state)
        state["ops_report"] = report
        _event(state, "Ops report generated", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Report generated", "ops_report": report}

    if action == "change_ops":
        from apps.vmware_sim.datacenter_phase12 import build_change_calendar, change_op
        cal = state.get("change_calendar") or build_change_calendar()
        op = payload.get("op") or ""
        ok, msg, cal = change_op(cal, op, **{k: v for k, v in payload.items() if k != "op"})
        state["change_calendar"] = cal
        if not ok:
            return {"ok": False, "error": msg}
        _twin_journal(state, "change_ops", {"op": op, "change_id": payload.get("change_id")})
        _event(state, f"Change: {msg}", "warning" if "freeze" in op else "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "change_calendar": cal}

    if action == "containment_ops":
        from apps.vmware_sim.datacenter_phase12 import build_containment, containment_op, apply_blanking_to_physics
        ct = state.get("containment") or build_containment()
        op = payload.get("op") or ""
        ok, msg, ct = containment_op(ct, op, **{k: v for k, v in payload.items() if k != "op"})
        state["containment"] = ct
        if not ok:
            return {"ok": False, "error": msg}
        for rack in state.get("racks") or []:
            apply_blanking_to_physics(rack, ct)
        _event(state, f"Containment: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "containment": ct}

    if action == "cable_plant_ops":
        from apps.vmware_sim.datacenter_phase12 import build_cable_plant, cable_plant_op
        plant = state.get("cable_plant") or build_cable_plant()
        op = payload.get("op") or ""
        ok, msg, plant = cable_plant_op(plant, op, **{k: v for k, v in payload.items() if k != "op"})
        state["cable_plant"] = plant
        if not ok:
            return {"ok": False, "error": msg}
        _event(state, f"Cable plant: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "cable_plant": plant}

    if action == "burnin_ops":
        from apps.vmware_sim.datacenter_phase12 import build_burnin, burnin_op
        bi = state.get("burnin") or build_burnin(state.get("servers") or [])
        op = payload.get("op") or ""
        ok, msg, bi = burnin_op(bi, op, **{k: v for k, v in payload.items() if k != "op"})
        state["burnin"] = bi
        if not ok:
            return {"ok": False, "error": msg}
        mid = payload.get("machine_id")
        if op == "guest_advance" and mid:
            srv = _find_server(state, mid)
            if srv:
                stage = next((m.get("guest_install") for m in bi.get("machines") or [] if m.get("id") == mid), "")
                state["console"] = {
                    "open": True, "asset_id": mid,
                    "lines": [f"=== Guest install stage: {stage} ===", f"Host {srv.get('hostname')}", "cloud-init / first-boot progressing..."],
                }
        _twin_journal(state, "burnin_ops", {"op": op, "machine_id": mid})
        _event(state, f"Burn-in: {msg}", "info")
        # FRU RMA close: soak pass or release auto-resolves awaiting_parts / assigned
        # tickets for that asset (Steam-class locate → dock → repair → burn-in → close).
        closed = []
        if op in ("soak", "release") and mid:
            mrow = next((x for x in (bi.get("machines") or []) if x.get("id") == mid), None)
            if mrow and (mrow.get("result") == "pass" or mrow.get("released")):
                from apps.vmware_sim.datacenter_physics_ops import advance_ticket
                for t in state.get("tickets") or []:
                    if t.get("asset_id") != mid:
                        continue
                    if (t.get("status") or "") in ("closed", "resolved"):
                        continue
                    if (t.get("status") or "") in ("awaiting_parts", "assigned", "open", "scheduled") or t.get("type") == "rma":
                        try:
                            if t.get("status") != "resolved":
                                advance_ticket(t, "resolve")
                            advance_ticket(t, "close")
                            closed.append(t.get("id"))
                        except ValueError:
                            pass
                if closed:
                    _event(state, f"Burn-in closed ticket(s) {', '.join(closed)}", "success")
        _save(session_id, entry)
        out = {"ok": True, "message": msg, "burnin": bi, "console": state.get("console")}
        if closed:
            out["tickets_closed"] = closed
        return out

    if action == "exporter_ops":
        from apps.vmware_sim.datacenter_phase12 import build_exporters, exporter_op
        ex = state.get("exporters") or build_exporters(state)
        op = payload.get("op") or ""
        ok, msg, ex = exporter_op(ex, op, **{k: v for k, v in payload.items() if k != "op"})
        state["exporters"] = ex
        if not ok:
            return {"ok": False, "error": msg}
        _event(state, f"Exporter: {msg}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "exporters": ex}

    if action == "generate_evidence":
        from apps.vmware_sim.datacenter_phase12 import build_evidence_pack, build_sustainability
        from apps.vmware_sim.datacenter_facility_ops import build_capacity_snapshot, build_predictive_maintenance
        state["capacity"] = build_capacity_snapshot(state)
        state["predictive"] = build_predictive_maintenance(state)
        state["sustainability"] = build_sustainability(state)
        pack = build_evidence_pack(state)
        state["evidence_pack"] = pack
        # Mark compliance runbook as having artifact
        auto = state.get("automation") or {}
        auto.setdefault("events", []).insert(0, {"time": _now_iso(), "message": f"Evidence pack {pack['id']} generated"})
        state["automation"] = auto
        _event(state, f"Evidence {pack['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Evidence {pack['id']}", "evidence_pack": pack}

    if action == "ops_ticket":
        from apps.vmware_sim.datacenter_physics_ops import build_ops_ticket, advance_ticket, SUPPORT_VENDORS
        op = payload.get("op") or "create"
        tickets = state.setdefault("tickets", [])
        if op == "create":
            asset_id = payload.get("asset_id") or state.get("selected_asset")
            srv = _find_server(state, asset_id) if asset_id else None
            vendor = payload.get("vendor") or (srv.get("vendor") if srv else "Dell")
            if vendor not in SUPPORT_VENDORS and vendor not in ("HP",):
                # allow Cisco/NVIDIA even without matching server OEM
                pass
            ticket = build_ops_ticket(
                vendor=vendor if vendor != "HP" else "HPE",
                ticket_type=payload.get("ticket_type") or "incident",
                asset_id=srv["id"] if srv else asset_id,
                hostname=srv.get("hostname") if srv else None,
                component=payload.get("component") or (broken.get("component") if broken else "hardware") or "hardware",
                summary=payload.get("summary") or f"Ops ticket for {asset_id or 'facility'}",
                service_tag=srv.get("service_tag") if srv else payload.get("service_tag"),
                priority=payload.get("priority") or "medium",
            )
            tickets.insert(0, ticket)
            _twin_journal(state, "ops_ticket", {
                "op": "create",
                "vendor": ticket["vendor"],
                "ticket_type": ticket["type"],
                "asset_id": asset_id,
                "component": ticket["component"],
                "summary": ticket["summary"],
            })
            _event(state, f"Opened {ticket['type']} {ticket['id']} ({ticket['vendor']})", "info")
            _save(session_id, entry)
            return {"ok": True, "message": f"Ticket {ticket['id']}", "ticket": ticket}
        ticket_id = payload.get("ticket_id") or ""
        ticket = next((t for t in tickets if t.get("id") == ticket_id), None)
        if not ticket:
            return {"ok": False, "error": f"Ticket {ticket_id} not found"}
        try:
            advance_ticket(
                ticket,
                payload.get("advance") or "assign",
                engineer=payload.get("engineer"),
                part=payload.get("part"),
                root_cause=payload.get("root_cause"),
                corrective=payload.get("corrective"),
                duration_min=payload.get("duration_min"),
                sku=payload.get("sku"),
                carrier=payload.get("carrier"),
                eta_days=payload.get("eta_days"),
                rack=payload.get("rack"),
                # Live floor state so a window can be judged against real load
                # rather than being a free-text note (audit L2267).
                facility={
                    **(state.get("facility") or {}),
                    "rack_loads": {
                        p.get("rack"): p.get("load_pct")
                        for p in (state.get("power_chain") or {}).get("rack_pdus") or []
                    },
                },
            )
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        # Close FRU loop: ship_rma enqueues a loading-dock ASN tied to ticket+asset.
        pending = ticket.pop("_pending_dock_asn", None)
        if pending:
            from apps.vmware_sim.datacenter_facility_ops import (
                TICKS_PER_TRANSIT_DAY,
                ensure_campus_plant,
                eta_summary,
            )
            campus = ensure_campus_plant(state.get("campus") or {}, state.get("power_chain"))
            dock = campus.setdefault("loading_dock", {})
            queue = dock.setdefault("queue", [])
            asn_id = f"ASN-RMA-{pending.get('rma_number') or len(queue) + 1}"
            # The RMA already carried eta_days but nothing enforced it; convert
            # it to sim ticks so the part is genuinely unavailable until then.
            eta_days = int((ticket.get("rma") or {}).get("eta_days") or 2)
            asn = {
                "id": asn_id,
                "carrier": pending.get("carrier") or "FedEx",
                "contents": pending.get("contents") or "FRU",
                "status": "inbound",
                "ticket_id": pending.get("ticket_id"),
                "asset_id": pending.get("asset_id"),
                "rma_number": pending.get("rma_number"),
                "sku": pending.get("sku"),
                "eta_days": eta_days,
                "ticks_remaining": max(1, eta_days * TICKS_PER_TRANSIT_DAY),
            }
            queue.insert(0, asn)
            state["campus"] = campus
            _event(state, f"Dock ASN {asn_id} queued for {pending.get('rma_number')} · {eta_summary(asn)}", "info")
        _event(state, f"Ticket {ticket_id} → {ticket.get('status')}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Ticket {ticket_id} updated", "ticket": ticket}

    if action == "training_start":
        from apps.vmware_sim.datacenter_physics_ops import build_training_scenarios
        training = state.setdefault("training", {"scenarios": build_training_scenarios(), "active": None, "progress": []})
        # Refresh scenario list so new troubleshoot drills appear on older sessions
        training["scenarios"] = build_training_scenarios()
        sid = payload.get("scenario_id") or "dc-tech"
        scen = next((s for s in training["scenarios"] if s["id"] == sid), training["scenarios"][0])
        training["active"] = scen["id"]
        training["progress"] = []
        training["feedback"] = f"Started: {scen['role']}. Complete steps in order."
        inject = scen.get("inject")
        injected = None
        if inject:
            # Auto-inject linked failure so the drill starts with a live fault
            inj = apply_action(session_id, "inject_failure", {
                "preset": inject,
                "asset_id": payload.get("asset_id") or state.get("selected_asset") or "",
            })
            # Reload entry after nested apply_action persisted
            entry = _ensure(session_id)
            state = entry["state"]
            training = state.setdefault("training", training)
            training["active"] = scen["id"]
            training["progress"] = []
            if inj.get("ok"):
                training["feedback"] = f"Started: {scen['role']}. Fault injected ({inject}). Remediate, then Clear fault."
                injected = inject
            else:
                training["feedback"] = f"Started: {scen['role']}. Inject failed: {inj.get('error')}"
        _event(state, f"Training started: {scen['role']}", "info")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Training {scen['id']}",
            "training": training,
            "injected": injected,
            "broken": state.get("broken"),
        }

    if action == "training_complete_step":
        training = state.setdefault("training", {})
        step = payload.get("step") or ""
        if not training.get("active"):
            return {"ok": False, "error": "No active training"}
        prog = training.setdefault("progress", [])
        if step and step not in prog:
            prog.append(step)
        scen = next((s for s in training.get("scenarios") or [] if s["id"] == training["active"]), None)
        done = len(prog)
        total = len((scen or {}).get("steps") or [])
        training["feedback"] = f"Progress {done}/{total}. " + (
            "Scenario complete — great work." if done >= total else f"Next: {(scen or {}).get('steps', [''])[min(done, total-1)]}"
        )
        _save(session_id, entry)
        return {"ok": True, "message": training["feedback"], "training": training}

    if action == "refresh_monitoring":
        from apps.vmware_sim.datacenter_physics_ops import build_monitoring_snapshot
        state["monitoring"] = build_monitoring_snapshot(state)
        _save(session_id, entry)
        return {"ok": True, "message": "Metrics refreshed", "monitoring": state["monitoring"]}

    if action == "accept_contract":
        from apps.vmware_sim.datacenter_economy_ops import accept_contract, evaluate_contracts
        contract = accept_contract(
            state,
            tenant=payload.get("tenant") or "acme",
            kw=float(payload.get("kw") or 10),
            u_slots=int(payload.get("u_slots") or 20),
            sla_pct=float(payload.get("sla_pct") or 99.99),
            credit_usd=payload.get("credit_usd"),
        )
        evaluate_contracts(state)
        _twin_journal(state, "accept_contract", {"id": contract["id"], "tenant": contract["tenant"]})
        _event(state, f"Accepted contract {contract['id']} for {contract['tenant']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": f"Contract {contract['id']}", "contract": contract, "contracts": state.get("contracts")}

    if action == "economy_buy":
        from apps.vmware_sim.datacenter_economy_ops import buy_hardware
        result = buy_hardware(state, sku=payload.get("sku") or "", qty=int(payload.get("qty") or 1))
        if not result.get("ok"):
            return result
        _event(state, f"Purchased {result['qty']}× {result['sku']} (${result['usd']})", "info")
        _save(session_id, entry)
        return result

    if action == "economy_tick":
        from apps.vmware_sim.datacenter_economy_ops import tick_opex, tick_fatigue, tick_reputation
        result = tick_opex(state, hours=float(payload.get("hours") or 1))
        tick_fatigue(state, hours=float(payload.get("hours") or 1))
        tick_reputation(state)
        _save(session_id, entry)
        return {**result, "reputation": state.get("reputation")}

    if action == "apply_upgrade":
        from apps.vmware_sim.datacenter_economy_ops import apply_upgrade, list_upgrades
        result = apply_upgrade(state, payload.get("upgrade_id") or "")
        if result.get("ok"):
            _event(state, f"Unlocked upgrade {result['upgrade']}", "success")
            _save(session_id, entry)
        result["upgrades"] = list_upgrades(state)
        return result

    if action == "list_upgrades":
        from apps.vmware_sim.datacenter_economy_ops import list_upgrades
        return {"ok": True, "upgrades": list_upgrades(state)}

    if action == "unlock_second_hall":
        from apps.vmware_sim.datacenter_economy_ops import unlock_second_hall
        result = unlock_second_hall(state)
        if result.get("ok"):
            _event(state, "Unlocked data-hall-b", "success")
            _save(session_id, entry)
        return result

    if action == "inspect_floor":
        from apps.vmware_sim.datacenter_economy_ops import inspect_before_energize
        report = inspect_before_energize(state)
        _save(session_id, entry)
        return {"ok": report["ok"], "inspection": report}

    if action == "energize_floor":
        from apps.vmware_sim.datacenter_economy_ops import energize_floor
        result = energize_floor(state, force=bool(payload.get("force")))
        if result.get("ok"):
            _event(state, f"Floor energized ({result.get('energized_outlets')} outlets)", "success")
            _save(session_id, entry)
        return result

    if action == "hire_staff":
        from apps.vmware_sim.datacenter_economy_ops import hire_staff
        result = hire_staff(
            state,
            name=payload.get("name") or "tech",
            role=payload.get("role") or "field-tech",
            shift=payload.get("shift") or "day",
        )
        _event(state, f"Hired {result['staff']['name']} ({result['staff']['role']})", "info")
        _save(session_id, entry)
        return result

    if action == "dispatch_staff":
        from apps.vmware_sim.datacenter_economy_ops import dispatch_staff
        result = dispatch_staff(
            state,
            ticket_id=payload.get("ticket_id") or "",
            staff_id=payload.get("staff_id") or "",
        )
        if result.get("ok"):
            _event(state, f"Dispatched {result['staff']['name']} → {result['ticket']['id']}", "info")
            _save(session_id, entry)
        return result

    if action == "place_rack":
        from apps.vmware_sim.datacenter_economy_ops import place_rack
        result = place_rack(
            state,
            rack_id=payload.get("rack_id") or "",
            grid_x=int(payload.get("grid_x") or 0),
            grid_z=int(payload.get("grid_z") or 0),
            orientation=payload.get("orientation") or "hot_cold",
            mass_kg=float(payload.get("mass_kg") or 250),
        )
        if not result.get("ok"):
            return result
        _twin_journal(state, "place_rack", {"rack_id": result["rack"]["id"], "grid": [result["rack"]["grid_x"], result["rack"]["grid_z"]]})
        _event(state, f"Placed rack {result['rack']['id']} at ({result['rack']['grid_x']},{result['rack']['grid_z']})", "success")
        _save(session_id, entry)
        return result

    if action == "remove_rack":
        from apps.vmware_sim.datacenter_economy_ops import remove_rack
        result = remove_rack(state, payload.get("rack_id") or "")
        if not result.get("ok"):
            return result
        _twin_journal(state, "remove_rack", {"rack_id": result["removed"]})
        _event(state, f"Removed rack {result['removed']}", "info")
        _save(session_id, entry)
        return result

    if action == "blueprint_undo":
        from apps.vmware_sim.datacenter_economy_ops import undo_blueprint
        result = undo_blueprint(state)
        if result.get("ok"):
            _event(state, "Blueprint undo", "info")
            _save(session_id, entry)
        return result

    if action == "blueprint_redo":
        from apps.vmware_sim.datacenter_economy_ops import redo_blueprint
        result = redo_blueprint(state)
        if result.get("ok"):
            _event(state, "Blueprint redo", "info")
            _save(session_id, entry)
        return result

    if action == "blueprint_save":
        from apps.vmware_sim.datacenter_economy_ops import save_blueprint
        result = save_blueprint(state, payload.get("name") or "default")
        if result.get("ok"):
            _event(state, f"Blueprint saved: {result['name']}", "success")
            _save(session_id, entry)
        return result

    if action == "blueprint_load":
        from apps.vmware_sim.datacenter_economy_ops import load_blueprint
        result = load_blueprint(state, payload.get("name") or "default")
        if result.get("ok"):
            _event(state, f"Blueprint loaded: {result['name']}", "success")
            _save(session_id, entry)
        return result

    if action == "blueprint_copy_row":
        from apps.vmware_sim.datacenter_economy_ops import copy_rack_row
        result = copy_rack_row(
            state,
            source_z=int(payload.get("source_z") or 0),
            dest_z=int(payload.get("dest_z") or 1),
        )
        if result.get("ok"):
            _event(state, f"Copied row → {len(result.get('created') or [])} racks", "success")
            _save(session_id, entry)
        return result

    if action == "vendor_inject":
        from apps.labs.vendor_dependency_ops import inject_vendor_event
        result = inject_vendor_event(
            state,
            kind=payload.get("kind") or "",
            detail=payload.get("detail"),
        )
        if result.get("ok"):
            _event(state, f"Vendor event: {result['event']['kind']}", "danger")
            _save(session_id, entry)
        return result

    if action == "vendor_remediate":
        from apps.labs.vendor_dependency_ops import remediate_vendor_event
        result = remediate_vendor_event(
            state,
            event_id=payload.get("event_id") or "",
            action=payload.get("remediation") or payload.get("action") or "",
        )
        if result.get("ok"):
            _event(state, f"Vendor remediated via {result['event'].get('resolved_by')}", "success")
            _save(session_id, entry)
        return result

    if action == "vault_status":
        from apps.labs.vault_lab_ops import vault_status
        return vault_status(state)

    if action == "vault_seal":
        from apps.labs.vault_lab_ops import seal_vault
        result = seal_vault(state)
        _event(state, "Vault sealed", "danger")
        _save(session_id, entry)
        return result

    if action == "vault_unseal_key":
        from apps.labs.vault_lab_ops import present_unseal_key
        result = present_unseal_key(state, payload.get("key") or "")
        if result.get("unsealed"):
            _event(state, "Vault unsealed — service restored", "success")
        elif result.get("ok"):
            _event(state, result.get("message") or "Unseal progress", "info")
        if result.get("ok"):
            _save(session_id, entry)
        return result

    if action == "vault_auth":
        from apps.labs.vault_lab_ops import auth_vault
        result = auth_vault(
            state,
            method=payload.get("method") or "token",
            token=payload.get("token"),
            role_id=payload.get("role_id"),
            secret_id=payload.get("secret_id"),
        )
        if result.get("ok"):
            _event(state, f"Vault auth via {result.get('auth_method')}", "success")
            _save(session_id, entry)
        return result

    if action == "vault_issue_db":
        from apps.labs.vault_lab_ops import issue_db_credentials
        result = issue_db_credentials(state, ttl_seconds=int(payload.get("ttl_seconds") or 60))
        if result.get("ok"):
            _event(state, f"Dynamic DB lease {result['lease']['id']}", "success")
            _save(session_id, entry)
        return result

    if action == "vault_renew_lease":
        from apps.labs.vault_lab_ops import renew_lease
        result = renew_lease(state, payload.get("lease_id") or "", extend_seconds=int(payload.get("extend_seconds") or 60))
        if result.get("ok"):
            _save(session_id, entry)
        return result

    if action == "vault_revoke_lease":
        from apps.labs.vault_lab_ops import revoke_lease
        result = revoke_lease(state, payload.get("lease_id") or "")
        if result.get("ok"):
            _event(state, f"Revoked lease {result['lease_id']}", "info")
            _save(session_id, entry)
        return result

    if action == "live_tick":
        # Live scrape without flooding the twin journal (not replayed).
        from apps.vmware_sim.datacenter_facility_ops import advance_shipments, tick_live
        from apps.vmware_sim.datacenter_physics_ops import build_monitoring_snapshot, refresh_all_ticket_slas
        env = tick_live(state)
        state["environmental"] = env
        state["monitoring"] = build_monitoring_snapshot(state)
        breached = refresh_all_ticket_slas(state)
        for t in breached:
            _event(state, f"SLA breached: {t.get('id')} ({t.get('summary')})", "danger")
        from apps.vmware_sim.datacenter_economy_ops import evaluate_contracts
        for c in evaluate_contracts(state):
            _event(
                state,
                f"Contract SLA: {c.get('id')} credits ${c.get('credits_owed')} ({c.get('tenant')})",
                "danger",
            )
        # Inbound RMA parts close distance on the sim clock, not wall-clock, so
        # an idle session never conjures a part and a busy one still finishes.
        arrived = advance_shipments(state.get("campus") or {})
        for item in arrived:
            _event(state, f"Dock: {item['id']} arrived at bay ({item.get('contents')})", "info")
        # Propped doors and unescorted visitors escalate on the same clock.
        from apps.vmware_sim.datacenter_facility_ops import advance_physical_security
        violations = advance_physical_security(state)
        for viol in violations:
            _event(state, f"Security: {viol['message']}", "danger")
        from apps.vmware_sim.datacenter_facility_ops import build_capacity_snapshot
        state["capacity"] = build_capacity_snapshot(state)
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Live tick #{env.get('tick', 0)}",
            "environmental": env,
            "monitoring": state["monitoring"],
            "capacity": state["capacity"],
            "shipments_arrived": [i["id"] for i in arrived],
        }

    if action == "hypervisor_ops":
        from apps.vmware_sim.datacenter_compute_ai import build_hypervisor_platform, hv_action
        plat = state.setdefault("hypervisors", build_hypervisor_platform(state.get("servers") or []))
        ok, msg = hv_action(
            plat,
            payload.get("op") or "create_vm",
            host_id=payload.get("host_id"),
            vm_id=payload.get("vm_id"),
            dest_host=payload.get("dest_host"),
            name=payload.get("name"),
            cpus=payload.get("cpus"),
            mem_gb=payload.get("mem_gb"),
            disk_gb=payload.get("disk_gb"),
            mode=payload.get("mode"),
        )
        if not ok:
            return {"ok": False, "error": msg}
        _twin_journal(state, "hypervisor_ops", {
            "op": payload.get("op"),
            "host_id": payload.get("host_id"),
            "vm_id": payload.get("vm_id"),
            "dest_host": payload.get("dest_host"),
            "name": payload.get("name"),
            "cpus": payload.get("cpus"),
            "mem_gb": payload.get("mem_gb"),
            "disk_gb": payload.get("disk_gb"),
            "mode": payload.get("mode"),
        })
        _event(state, msg, "success")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "hypervisors": plat}

    if action == "ai_ops":
        from apps.vmware_sim.datacenter_compute_ai import build_ai_platform, ai_action
        ai = state.setdefault("ai_platform", build_ai_platform(state.get("servers") or []))
        ok, msg = ai_action(
            ai,
            payload.get("op") or "deploy_pod",
            name=payload.get("name"),
            ns=payload.get("ns"),
            node=payload.get("node"),
            gpus=payload.get("gpus"),
            chart=payload.get("chart"),
            profile=payload.get("profile"),
            replicas=payload.get("replicas"),
        )
        if not ok:
            return {"ok": False, "error": msg}
        _twin_journal(state, "ai_ops", {
            "op": payload.get("op"),
            "name": payload.get("name"),
            "ns": payload.get("ns"),
            "node": payload.get("node"),
            "gpus": payload.get("gpus"),
            "chart": payload.get("chart"),
            "profile": payload.get("profile"),
            "replicas": payload.get("replicas"),
        })
        _event(state, msg, "success")
        _save(session_id, entry)
        return {"ok": True, "message": msg, "ai_platform": ai}

    if action == "replay_twin_journal":
        twin = state.get("digital_twin") or {}
        journal = list(reversed(twin.get("persisted_changes") or []))
        scenario = entry.get("scenario_slug") or payload.get("scenario_slug") or ""
        entry["state"] = _base_state()
        _apply_preset(entry["state"], scenario)
        entry["state"]["digital_twin"] = {"version": 2, "persisted_changes": []}
        entry["scenario_slug"] = scenario
        _save(session_id, entry)
        replayed = 0
        skipped = 0
        for item in journal:
            act = item.get("action")
            if not act or act in ("replay_twin_journal", "live_tick", "refresh_monitoring"):
                skipped += 1
                continue
            pl = dict(item.get("payload") or {})
            pl["_replay"] = True
            res = apply_action(session_id, act, pl)
            if res.get("ok"):
                replayed += 1
            else:
                skipped += 1
        entry = _load(session_id) or entry
        state = entry["state"]
        state.setdefault("digital_twin", {})["persisted_changes"] = list(reversed(journal))
        state["digital_twin"]["last_replay"] = {
            "time": _now_iso(), "replayed": replayed, "skipped": skipped,
        }
        _event(state, f"Replayed twin journal ({replayed} actions, {skipped} skipped)", "success")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"Replayed {replayed} journal actions",
            "replayed": replayed,
            "skipped": skipped,
            "digital_twin": state.get("digital_twin"),
        }

    return {"ok": False, "error": f"Unknown action: {action}"}


# Per-component grader feedback. Unlike the other console engines, this one's
# broken dict is a single fault RECORD -- {"server": ..., "component": ...,
# "target": ..., "cable_id": ...} -- not a bag of independent objective keys.
# So the reason is keyed on the component, and the target is resolved from
# whichever of server/cable_id/target the injector filled in.
_BROKEN_REASONS: dict[str, str] = {
    # Field-replaceable server hardware.
    "power": "the power supply in {target} is still failed — replace the PSU",
    "nic": "the NIC in {target} is still failed — replace it",
    "disk": "the disk in {target} is still failed — replace it",
    "motherboard": "the motherboard in {target} is still failed — replace it",
    "cpu": "the CPU in {target} is still failed — replace it",
    "gpu": "the GPU in {target} is still failed — replace it",
    "fan": "the fan in {target} is still failed — replace it",
    "dimm": "the DIMM in {target} is still failed — replace it",
    "pcie": "the PCIe/NVLink device in {target} is still failed — replace it",
    "raid": "the RAID controller in {target} is still failed — replace it",
    "hba": "the HBA in {target} is still failed — replace it",
    # Server-scoped, but fixed by something other than a part swap.
    "firmware": "the firmware on {target} is still corrupt — reflash it",
    "cable": "cable {target} is still faulted — reseat or replace it",
    "pxe": "PXE boot for {target} is still broken — re-enable PXE and DHCP",
    # Facility.
    "cooling": "cooling unit {target} is still failed — restore cooling",
    "pdu": "PDU {target} is still failed — restore the power feed",
    "ups": "UPS {target} is still on fault — restore utility power",
    "leak": "the water leak at {target} has not been contained yet",
    "fire": "the fire/smoke alarm in zone {target} has not been cleared yet",
    "security": "the security breach at {target} has not been resolved yet",
    # Network fabric.
    "switch": "switch {target} is still down — bring it back up",
    "bgp": "BGP on {target} has not been restored yet",
    "ospf": "OSPF on {target} has not been restored yet",
    "mpls": "MPLS on {target} has not been re-enabled yet",
    "evpn": "EVPN on {target} has not been re-enabled yet",
    "vxlan": "the VXLAN overlay on {target} has not been restored yet",
    "vlan": "the VLAN misconfiguration on {target} has not been corrected yet",
    "dns": "DNS resolution for {target} has not been restored yet",
    "dhcp": "DHCP for {target} has not been restored yet",
    # Site-level.
    "dr": "the DR failover for {target} has not completed yet",
}


def _broken_target(broken: dict) -> str:
    """Best available name for the faulted asset.

    Server faults carry "server"; facility/network faults set server to None
    and carry "target" instead; cable faults carry both plus "cable_id".
    """
    server = broken.get("server")
    cable_id = broken.get("cable_id")
    if cable_id and server:
        return f"{cable_id} on {server}"
    return str(cable_id or server or broken.get("target") or "this environment")


def _describe_broken(broken: dict) -> str:
    component = broken.get("component")
    if not component:
        # A fault record with no component at all: fail CLOSED and name the
        # keys present so the gap is reportable rather than silently generic.
        return f"unresolved objective ({', '.join(sorted(broken))})"
    template = _BROKEN_REASONS.get(component)
    if template is None:
        # Unknown component: still fail CLOSED, and name it so a missing
        # template surfaces as a reportable gap rather than a silent pass.
        return f"unresolved objective ({component})"
    return template.format(target=_broken_target(broken))


def validate_datacenter_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No datacenter session"
    state = entry["state"]
    broken = state.get("broken") or {}
    if broken:
        return False, f"Datacenter lab not complete: {_describe_broken(broken)}"
    return True, "Datacenter lab objectives met"
