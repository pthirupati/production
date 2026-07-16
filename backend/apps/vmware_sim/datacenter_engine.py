"""In-memory physical Data Center Infrastructure Management (DCIM) simulator.

Server-authoritative, session-cached (Django cache / Redis) mirror of a
physical datacenter floor: racks (R01-R12), servers in numbered U slots with
component-level health (power supply, NIC, disk, motherboard, CPU, GPU), PDUs,
and cooling units. A "field tech" lab walks the floor, selects a broken asset,
and physically replaces/reseats the failed component — mirroring hands-on
break/fix work instead of a software console.
"""

from __future__ import annotations

import copy
import json
import time

from django.core.cache import cache

SESSION_TTL = 7200

_RACKS = [f"R{i:02d}" for i in range(1, 13)]

# Component keys tracked per server; each has a status of "healthy" or "failed".
_COMPONENT_KEYS = ("power", "nic", "disk", "motherboard", "cpu", "gpu")


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


def _server(asset_id: str, rack: str, u_slot: int, hostname: str, **overrides) -> dict:
    components = {k: "healthy" for k in _COMPONENT_KEYS}
    components.update(overrides.pop("components", {}))
    return {
        "id": asset_id,
        "rack": rack,
        "u_slot": u_slot,
        "hostname": hostname,
        "power_state": overrides.get("power_state", "on"),
        "components": components,
        **{k: v for k, v in overrides.items() if k != "power_state"},
    }


def _base_state() -> dict:
    servers = [
        _server("srv-r01-u12", "R01", 12, "web-prod-01"),
        _server("srv-r01-u14", "R01", 14, "web-prod-02", power_state="off",
                components={"power": "failed", "nic": "healthy", "disk": "healthy",
                            "motherboard": "healthy", "cpu": "healthy", "gpu": "healthy"}),
        _server("srv-r02-u10", "R02", 10, "db-prod-01"),
        _server("srv-r03-u08", "R03", 8, "gpu-node-01",
                components={"power": "healthy", "nic": "healthy", "disk": "healthy",
                            "motherboard": "healthy", "cpu": "healthy", "gpu": "failed"}),
    ]
    racks = [{"id": r, "floor": "1", "pdu": f"PDU-{r}", "servers": [s["id"] for s in servers if s["rack"] == r]} for r in _RACKS]
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"site": "fixitlab-dc1", "floor_count": 1},
        "floors": [{"id": "1", "name": "Floor 1", "racks": _RACKS}],
        "racks": racks,
        "servers": servers,
        "pdus": [
            {"id": f"PDU-{r}", "rack": r, "status": "online", "load_pct": 45} for r in _RACKS[:4]
        ],
        "cooling": [
            {"id": "CRAC-1", "zone": "Floor 1 - North", "status": "running", "temp_c": 21.5},
            {"id": "CRAC-2", "zone": "Floor 1 - South", "status": "running", "temp_c": 22.0},
        ],
        "selected_asset": None,
        "goal": {"title": "Datacenter break/fix", "objective": "Replace the failed power supply in web-prod-02 (R01-U14)."},
        "broken": {"server": "srv-r01-u14", "component": "power"},
        "events": [],
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
    elif "gpu" in slug:
        state["goal"] = {"title": "Replace GPU", "objective": "Replace the failed GPU in gpu-node-01 (R03-U08)."}
        state["broken"] = {"server": "srv-r03-u08", "component": "gpu"}
    elif "power" in slug or "psu" in slug:
        state["goal"] = {"title": "Replace power supply", "objective": "Replace the failed power supply in web-prod-02 (R01-U14)."}
        state["broken"] = {"server": "srv-r01-u14", "component": "power"}
    elif "cable" in slug or "reseat" in slug:
        state["goal"] = {"title": "Reseat cable", "objective": "Reseat the loose network cable on db-prod-01 (R02-U10)."}
        state["broken"] = {"server": "srv-r02-u10", "component": "cable"}
    elif "firmware" in slug:
        state["goal"] = {"title": "Update firmware", "objective": "Update BIOS/firmware on gpu-node-01 (R03-U08)."}
        state["broken"] = {"server": "srv-r03-u08", "component": "firmware"}


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
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": state,
        "goal": state.get("goal", {}),
        "events": state.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


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

    if action == "select_asset":
        asset_id = payload.get("asset_id") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        state["selected_asset"] = srv["id"]
        _save(session_id, entry)
        return {"ok": True, "message": f"Selected {srv['id']}", "asset": srv}

    if action == "power_cycle":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        srv["power_state"] = "on" if all(v == "healthy" for v in srv["components"].values()) else "off"
        _event(state, f"Power cycled {srv['id']}", "info")
        _save(session_id, entry)
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
        if broken.get("server") == srv["id"] and broken.get("component") == component:
            broken.clear()
        _event(state, f"Replaced {component} in {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"{component} replaced"}

    if action == "reseat_cable":
        asset_id = payload.get("asset_id") or state.get("selected_asset") or broken.get("server") or ""
        srv = _find_server(state, asset_id)
        if not srv:
            return {"ok": False, "error": f"Asset {asset_id} not found"}
        srv["components"]["nic"] = "healthy"
        if broken.get("server") == srv["id"] and broken.get("component") == "cable":
            broken.clear()
        _event(state, f"Cable reseated on {srv['id']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Cable reseated"}

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
        return {"ok": True, "message": "Firmware updated"}

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
