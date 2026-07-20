"""In-memory Dell EMC Unisphere / PowerMax simulator for storage training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of the
Unisphere console: arrays, storage groups, volumes/LUNs, masking views, hosts,
and front-end ports. Mirrors the real provisioning workflow — a volume must be
placed in a storage group, and a masking view binds a storage group + host +
port group together before a host can actually see the LUN.
"""

from __future__ import annotations

import copy
import json
import time

from django.core.cache import cache

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"dellemc_session:{session_id}"


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
    entry = {"time": _now_iso(), "message": message, "severity": severity}
    state.setdefault("events", []).insert(0, entry)
    state.setdefault("activity_log", []).insert(0, entry)
    state["activity_log"] = state["activity_log"][:200]


def _base_state() -> dict:
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"version": "Unisphere for PowerMax 10.2", "array": "000297900123"},
        "arrays": [
            {"id": "000297900123", "model": "PowerMax 2500", "capacity_tb": 500, "used_tb": 180, "health": "normal"},
        ],
        "storage_groups": [
            {"name": "SG_web_prod", "array": "000297900123", "volumes": ["0001", "0002"], "host_io_limit": None, "slo": "Diamond"},
            {"name": "SG_db_prod", "array": "000297900123", "volumes": ["0003"], "host_io_limit": None, "slo": "Platinum"},
        ],
        "volumes": [
            {"id": "0001", "size_gb": 100, "storage_group": "SG_web_prod", "status": "Ready", "emulation": "FBA"},
            {"id": "0002", "size_gb": 200, "storage_group": "SG_web_prod", "status": "Ready", "emulation": "FBA"},
            {"id": "0003", "size_gb": 500, "storage_group": "SG_db_prod", "status": "Ready", "emulation": "FBA"},
            {"id": "0004", "size_gb": 250, "storage_group": None, "status": "Unmapped", "emulation": "FBA"},
        ],
        "hosts": [
            {"name": "web01", "initiators": ["10:00:00:00:c9:aa:bb:01"], "host_type": "Linux"},
            {"name": "db01", "initiators": ["10:00:00:00:c9:aa:bb:02"], "host_type": "Linux"},
        ],
        "ports": [
            {"id": "FA-1D:4", "director": "FA-1D", "status": "online", "speed": "32Gb/s"},
            {"id": "FA-2D:4", "director": "FA-2D", "status": "online", "speed": "32Gb/s"},
        ],
        "masking_views": [
            {"name": "MV_web01", "storage_group": "SG_web_prod", "host": "web01", "port_group": "PG_web"},
        ],
        "port_groups": [
            {"name": "PG_web", "ports": ["FA-1D:4"]},
            {"name": "PG_db", "ports": ["FA-2D:4"]},
        ],
        "snapshots": [
            {"name": "snap-0003-daily", "volume_id": "0003", "size_gb": 12, "created": _now_iso()},
        ],
        "srdf": [
            {"name": "RDFG-1", "local_volume": "0003", "remote_volume": "9003", "mode": "Async", "state": "Consistent"},
        ],
        "activity_log": [],
        "goal": {"title": "Dell EMC provisioning lab", "objective": "Provision the unmapped volume 0004 to db01."},
        "broken": {"unmapped_volume": "0004"},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "masking" in slug or "view" in slug:
        state["goal"] = {"title": "Create masking view", "objective": "Create a masking view binding SG_db_prod, db01, and PG_db."}
        state["broken"] = {"needs_masking_view": "SG_db_prod"}
    elif "host" in slug and ("add" in slug or "register" in slug):
        state["goal"] = {"title": "Register host", "objective": "Register a new host with its FC initiator."}
        state["broken"] = {"needs_host": True}
    elif "storage-group" in slug or "storage_group" in slug or "sg" in slug:
        state["goal"] = {"title": "Create storage group", "objective": "Create a new storage group for the application team."}
        state["broken"] = {"needs_storage_group": True}
    elif "map" in slug or "provision" in slug or "volume" in slug:
        state["goal"] = {"title": "Provision volume", "objective": "Provision the unmapped volume 0004 to db01."}
        state["broken"] = {"unmapped_volume": "0004"}


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
        from apps.labs.provisioner.simulation.server_identity import sync_dellemc_storage
        sync_dellemc_storage(session_id, state)
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


def _find_volume(state: dict, vol_id: str) -> dict | None:
    return next((v for v in state.get("volumes", []) if v.get("id") == vol_id), None)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Dell EMC session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        _event(state, "Signed in to Unisphere", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to Unisphere first"}

    if action == "create_storage_group":
        name = (payload.get("name") or "SG_new").strip()
        if any(sg.get("name") == name for sg in state.get("storage_groups", [])):
            return {"ok": False, "error": f"Storage group {name} already exists"}
        state.setdefault("storage_groups", []).append({
            "name": name, "array": state["arrays"][0]["id"], "volumes": [], "host_io_limit": None,
        })
        broken.pop("needs_storage_group", None)
        _event(state, f"Storage group {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Storage group created"}

    if action == "create_volume":
        size_gb = int(payload.get("size_gb") or 100)
        vol_id = f"{int(max((int(v['id']) for v in state.get('volumes', [])), default=0)) + 1:04d}"
        sg_name = payload.get("storage_group")
        state.setdefault("volumes", []).append({
            "id": vol_id, "size_gb": size_gb, "storage_group": sg_name,
            "status": "Ready" if sg_name else "Unmapped", "emulation": "FBA",
        })
        if sg_name:
            sg = next((s for s in state.get("storage_groups", []) if s.get("name") == sg_name), None)
            if sg:
                sg.setdefault("volumes", []).append(vol_id)
        _event(state, f"Volume {vol_id} created ({size_gb}GB)", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Volume created", "volume_id": vol_id}

    if action == "map_volume":
        vol_id = payload.get("volume_id") or broken.get("unmapped_volume") or ""
        sg_name = payload.get("storage_group") or "SG_db_prod"
        vol = _find_volume(state, vol_id)
        if not vol:
            return {"ok": False, "error": f"Volume {vol_id} not found"}
        sg = next((s for s in state.get("storage_groups", []) if s.get("name") == sg_name), None)
        if not sg:
            return {"ok": False, "error": f"Storage group {sg_name} not found"}
        vol["storage_group"] = sg_name
        vol["status"] = "Ready"
        if vol_id not in sg.setdefault("volumes", []):
            sg["volumes"].append(vol_id)
        if broken.get("unmapped_volume") == vol_id:
            broken.pop("unmapped_volume", None)
        _event(state, f"Volume {vol_id} mapped into {sg_name}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import dellemc_bridge
            dellemc_bridge.record_volume_mapped(
                str(session_id),
                vol_id,
                vol.get("size_gb") or 100,
                device="/dev/sdx",
            )
        except Exception:
            pass
        return {"ok": True, "message": "Volume mapped to storage group"}

    if action == "add_host":
        name = (payload.get("name") or "new-host").strip()
        initiators = payload.get("initiators") or ["10:00:00:00:c9:aa:bb:99"]
        if any(h.get("name") == name for h in state.get("hosts", [])):
            return {"ok": False, "error": f"Host {name} already exists"}
        state.setdefault("hosts", []).append({
            "name": name, "initiators": initiators, "host_type": payload.get("host_type") or "Linux",
        })
        broken.pop("needs_host", None)
        _event(state, f"Host {name} registered", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Host registered"}

    if action == "create_masking_view":
        name = payload.get("name") or "MV_new"
        sg_name = payload.get("storage_group") or broken.get("needs_masking_view") or "SG_db_prod"
        host = payload.get("host") or "db01"
        port_group = payload.get("port_group") or "PG_db"
        sg = next((s for s in state.get("storage_groups", []) if s.get("name") == sg_name), None)
        host_obj = next((h for h in state.get("hosts", []) if h.get("name") == host), None)
        if not sg:
            return {"ok": False, "error": f"Storage group {sg_name} not found"}
        if not host_obj:
            return {"ok": False, "error": f"Host {host} not found"}
        state.setdefault("masking_views", []).append({
            "name": name, "storage_group": sg_name, "host": host, "port_group": port_group,
        })
        if broken.get("needs_masking_view") == sg_name:
            broken.pop("needs_masking_view", None)
        _event(state, f"Masking view {name} created for {host}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Masking view created"}

    if action == "expand_volume":
        vol_id = payload.get("volume_id") or ""
        vol = _find_volume(state, vol_id)
        if not vol:
            return {"ok": False, "error": f"Volume {vol_id} not found"}
        new_size = int(payload.get("size_gb") or (vol.get("size_gb", 100) + 100))
        if new_size <= vol.get("size_gb", 0):
            return {"ok": False, "error": "New size must be larger"}
        vol["size_gb"] = new_size
        _event(state, f"Volume {vol_id} expanded to {new_size}GB", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Volume expanded"}

    if action == "create_snapshot":
        vol_id = payload.get("volume_id") or "0003"
        vol = _find_volume(state, vol_id)
        if not vol:
            return {"ok": False, "error": f"Volume {vol_id} not found"}
        name = payload.get("name") or f"snap-{vol_id}-{int(time.time()) % 10000}"
        state.setdefault("snapshots", []).insert(0, {
            "name": name, "volume_id": vol_id, "size_gb": round(float(vol.get("size_gb", 10)) * 0.05, 1),
            "created": _now_iso(),
        })
        _event(state, f"Snapshot {name} created for volume {vol_id}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Snapshot created"}

    if action == "set_host_io_limit":
        sg_name = payload.get("storage_group") or "SG_web_prod"
        sg = next((s for s in state.get("storage_groups", []) if s.get("name") == sg_name), None)
        if not sg:
            return {"ok": False, "error": f"Storage group {sg_name} not found"}
        iops = int(payload.get("iops") or 10000)
        sg["host_io_limit"] = iops
        _event(state, f"Host I/O limit for {sg_name} set to {iops} IOPS", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Host I/O limit set"}

    if action == "create_port_group":
        name = (payload.get("name") or "PG_new").strip()
        ports = payload.get("ports") or ["FA-1D:4"]
        state.setdefault("port_groups", []).append({"name": name, "ports": ports})
        _event(state, f"Port group {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Port group created"}

    if action == "failover_srdf":
        name = payload.get("name") or "RDFG-1"
        pair = next((s for s in state.get("srdf", []) if s.get("name") == name), None)
        if not pair:
            return {"ok": False, "error": f"SRDF group {name} not found"}
        pair["state"] = "FailedOver"
        pair["mode"] = "Async"
        _event(state, f"SRDF {name} failed over to remote", "warning")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import dellemc_bridge
            dellemc_bridge.record_srdf_failover(str(session_id), name)
        except Exception:
            pass
        return {"ok": True, "message": "SRDF failover complete"}

    if action == "delete_masking_view":
        name = payload.get("name") or ""
        before = len(state.get("masking_views", []))
        state["masking_views"] = [m for m in state.get("masking_views", []) if m.get("name") != name]
        if len(state["masking_views"]) == before:
            return {"ok": False, "error": f"Masking view {name} not found"}
        _event(state, f"Masking view {name} deleted", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Masking view deleted"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_dellemc_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No Dell EMC session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "Dell EMC environment still has unresolved issues"
    return True, "Dell EMC lab objectives met"
