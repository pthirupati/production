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


def _hardware_inventory(hostname: str) -> dict:
    """Detailed server bill-of-materials for the Hardware drawer."""
    return {
        "motherboard": {
            "model": "ServerBoard X11DPi-N", "bios": "3.4", "uefi": True, "tpm": "2.0",
            "bmc": "iDRAC9 / Redfish", "secure_boot": True,
        },
        "cpus": [
            {"socket": 0, "model": "Intel Xeon Gold 6338", "cores": 32, "threads": 64, "numa_node": 0},
            {"socket": 1, "model": "Intel Xeon Gold 6338", "cores": 32, "threads": 64, "numa_node": 1},
        ],
        "dimms": [
            {"slot": f"A{i}", "size_gb": 32, "type": "DDR4-3200 ECC", "status": "healthy"}
            for i in range(1, 9)
        ],
        "pcie": [
            {"slot": "PCIe-1", "device": "NIC", "model": "Mellanox ConnectX-6 25GbE", "lanes": "x8"},
            {"slot": "PCIe-2", "device": "RAID", "model": "PERC H755", "lanes": "x8"},
            {"slot": "PCIe-3", "device": "HBA", "model": "Emulex LPe32002 FC32", "lanes": "x8"},
            {"slot": "PCIe-4", "device": "GPU", "model": "NVIDIA A40", "lanes": "x16"},
        ],
        "storage": [
            {"bay": 0, "model": "Samsung PM9A3", "size_gb": 1920, "bus": "NVMe", "status": "healthy"},
            {"bay": 1, "model": "Samsung PM9A3", "size_gb": 1920, "bus": "NVMe", "status": "healthy"},
            {"bay": 2, "model": "Seagate Exos", "size_gb": 4000, "bus": "SAS", "status": "healthy"},
        ],
        "psus": [
            {"id": "PSU1", "watts": 1400, "redundant": True, "status": "healthy"},
            {"id": "PSU2", "watts": 1400, "redundant": True, "status": "healthy"},
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
    }


def _session_key(session_id: str) -> str:
    return f"datacenter_session:{session_id}"


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


# ── Rooms / building layout ───────────────────────────────────────────────

def _rooms() -> list[dict]:
    return [
        {
            "id": "data-hall-a", "name": "Data Hall A", "type": "data_hall",
            "aisle": "hot_cold", "racks": list(_DATA_HALL_RACKS),
        },
        {
            "id": "mdf", "name": "Network / MDF", "type": "network",
            "racks": list(_MDF_RACKS),
        },
        {"id": "mechanical", "name": "Mechanical / Cooling", "type": "mechanical", "racks": []},
        {"id": "electrical", "name": "Electrical", "type": "electrical", "racks": []},
    ]


def _room_for_rack(rooms: list[dict], rack_id: str | None) -> str:
    for room in rooms:
        if rack_id and rack_id in (room.get("racks") or []):
            return room["id"]
    return "data-hall-a"


# ── BMC facade ─────────────────────────────────────────────────────────────

def _bmc(hostname: str, power_state: str, *, inlet_c: float = 22.1, exhaust_c: float = 34.0,
         fans_rpm: int = 4200, protocol: str = "redfish") -> dict:
    return {
        "endpoint": f"https://bmc-{hostname}.mgmt.corp.local",
        "protocol": protocol,
        "power": "on" if power_state == "on" else "off",
        "sensors": {"inlet_c": inlet_c, "exhaust_c": exhaust_c, "fans_rpm": fans_rpm},
        "sel": [{"time": _now_iso(), "message": "BMC self-test passed, sensors nominal"}],
    }


def _server(asset_id: str, rack: str, u_slot: int, hostname: str, **overrides) -> dict:
    components = {k: "healthy" for k in _COMPONENT_KEYS}
    components.update(overrides.pop("components", {}))
    power_state = overrides.get("power_state", "on")
    role = overrides.pop("role", None)
    bmc_override = overrides.pop("bmc", None)
    bmc = bmc_override or _bmc(hostname, power_state)
    # Alternate Dell / HPE fleets so FRU tickets go to the right OEM
    rack_num = int("".join(ch for ch in rack if ch.isdigit()) or "1")
    default_vendor = "HPE" if rack_num % 2 == 0 else "Dell"
    vendor = overrides.pop("vendor", default_vendor)
    service_tag = overrides.pop("service_tag", f"{'MX' if vendor == 'HPE' else 'DL'}{abs(hash(asset_id)) % 10_000_000:07d}")
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
        "model": "ProLiant DL380 Gen10" if vendor == "HPE" else "PowerEdge R750",
        "hardware": _hardware_inventory(hostname),
        "firmware_version": overrides.pop("firmware_version", "2.12.0"),
        **({"role": role} if role else {}),
        **{k: v for k, v in overrides.items() if k != "power_state"},
    }
    return server


# ── Power chain ────────────────────────────────────────────────────────────

def _rack_pdus() -> list[dict]:
    pdus = []
    for r in _RACKS:
        pdus.append({
            "id": f"PDU-{r}",
            "rack": r,
            "status": "online",
            "breaker": "closed",
            "load_pct": 45,
            "load_kw": 4.2,
        })
    return pdus


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


def _facility_summary(rack_pdus: list[dict], cooling: list[dict]) -> dict:
    it_kw = round(sum(p["load_kw"] for p in rack_pdus if p.get("status") == "online"), 2)
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
    rack_pdus = state.get("power_chain", {}).get("rack_pdus", [])
    cooling = state.get("cooling", [])
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
    switches = [
        {
            "id": "sw-core-01", "rack": "R09", "u_slot": 40, "hostname": "core-sw-01",
            "model": "48-port 10G ToR", "ports": [
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
            "model": "24-port 40G aggregation", "ports": [
                {"port": 1, "status": "up", "speed": "40G", "vlan": 1, "connected_to": "sw-core-01"},
                {"port": 2, "status": "up", "speed": "10G", "vlan": 1, "connected_to": "internet-edge"},
                {"port": 3, "status": "down", "speed": "10G", "vlan": None, "connected_to": None},
            ],
        },
    ]
    topology = [
        {"from": "core-sw-01", "to": "agg-sw-01", "type": "uplink", "speed": "40G"},
        {"from": "agg-sw-01", "to": "internet-edge", "type": "uplink", "speed": "10G"},
    ]
    return {"switches": switches, "topology": topology}


# ── Base state ─────────────────────────────────────────────────────────────

def _base_state() -> dict:
    servers = [
        _server("srv-r01-u12", "R01", 12, "web-prod-01", role="esxi_host"),
        _server("srv-r01-u14", "R01", 14, "web-prod-02", role="esxi_host", power_state="off",
                components={"power": "failed", "nic": "healthy", "disk": "healthy",
                            "motherboard": "healthy", "cpu": "healthy", "gpu": "healthy"}),
        _server("srv-r02-u10", "R02", 10, "db-prod-01", role="db"),
        _server("srv-r03-u08", "R03", 8, "gpu-node-01", role="gpu_node",
                components={"power": "healthy", "nic": "healthy", "disk": "healthy",
                            "motherboard": "healthy", "cpu": "healthy", "gpu": "failed"}),
        _server("srv-r04-u06", "R04", 6, "storage-01", role="storage"),
    ]
    rooms = _rooms()
    rack_pdus = _rack_pdus()
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
        upsert_server(
            session_id,
            {
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
            },
            source="datacenter",
        )


def _sync_power(session_id: str, server_id: str, power_state: str) -> None:
    try:
        from apps.labs.provisioner.simulation.server_identity import set_power
    except Exception:  # pragma: no cover
        return
    set_power(session_id, server_id, power_state, source="datacenter")


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    state = entry["state"]
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
        hw = srv.setdefault("hardware", _hardware_inventory(srv.get("hostname") or srv["id"]))
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
        hw = srv.setdefault("hardware", _hardware_inventory(srv.get("hostname") or srv["id"]))
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
        vendor = (payload.get("vendor") or srv.get("vendor") or "Dell").strip()
        if vendor.lower() in ("hpe", "hp", "hewlett"):
            vendor = "HPE"
        elif vendor.lower() in ("dell", "dell emc", "dellemc"):
            vendor = "Dell"
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
        affected = []
        for srv in state.get("servers", []):
            if srv["rack"] == pdu["rack"]:
                srv["power_state"] = "off"
                srv["bmc"]["power"] = "off"
                affected.append(srv["id"])
        _recompute_facility(state)
        _event(state, f"Breaker tripped on {pdu['id']} — rack {pdu['rack']} lost power", "danger")
        try:
            from apps.labs.provisioner.simulation.chaos_engine import inject as chaos_inject
            chaos_inject(session_id, "trip_pdu", pdu["id"], detail={"rack": pdu["rack"], "affected_servers": affected})
        except Exception:  # pragma: no cover
            pass
        _save(session_id, entry)
        _sync_identity(session_id, state)
        return {"ok": True, "message": f"Breaker tripped on {pdu['id']}", "affected_servers": affected}

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

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_datacenter_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No datacenter session"
    state = entry["state"]
    broken = state.get("broken") or {}
    if broken:
        return False, "Datacenter environment still has unresolved issues"
    return True, "Datacenter lab objectives met"
