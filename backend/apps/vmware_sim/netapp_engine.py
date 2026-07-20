"""In-memory NetApp ONTAP System Manager simulator for storage training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of ONTAP
System Manager: clusters, SVMs (storage virtual machines), aggregates, volumes,
LUNs, SnapMirror relationships, and NFS/CIFS exports.
"""

from __future__ import annotations

import copy
import json
import time

from django.core.cache import cache

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"netapp_session:{session_id}"


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
        "summary": {"version": "ONTAP 9.14.1", "cluster": "fixitlab-cluster"},
        "clusters": [
            {"name": "fixitlab-cluster", "nodes": 2, "health": "ok", "ha_partner": "node-02"},
        ],
        "nodes": [
            {"name": "node-01", "model": "AFF-A400", "uptime": "42d", "state": "up"},
            {"name": "node-02", "model": "AFF-A400", "uptime": "42d", "state": "up"},
        ],
        "svms": [
            {"name": "svm-prod", "state": "running", "protocols": ["nfs", "cifs", "iscsi"]},
            {"name": "svm-dr", "state": "running", "protocols": ["nfs"]},
        ],
        "aggregates": [
            {"name": "aggr1", "size_gb": 5000, "used_gb": 1800, "state": "online", "svm": "svm-prod", "raid": "raid_dp"},
            {"name": "aggr2", "size_gb": 5000, "used_gb": 500, "state": "online", "svm": "svm-dr", "raid": "raid_dp"},
        ],
        "volumes": [
            {"name": "vol_web_data", "svm": "svm-prod", "aggregate": "aggr1", "size_gb": 100, "used_gb": 95, "state": "online", "type": "rw"},
            {"name": "vol_db_data", "svm": "svm-prod", "aggregate": "aggr1", "size_gb": 200, "used_gb": 120, "state": "online", "type": "rw"},
            {"name": "vol_dr_copy", "svm": "svm-dr", "aggregate": "aggr2", "size_gb": 100, "used_gb": 40, "state": "online", "type": "dp"},
        ],
        "luns": [
            {"path": "/vol/vol_db_data/lun0", "size_gb": 150, "svm": "svm-prod", "mapped": False, "os_type": "linux"},
        ],
        "snapshots": [
            {"name": "vol_web_data.daily.20260719", "volume": "vol_web_data", "size_gb": 2.1, "created": _now_iso()},
        ],
        "qtrees": [
            {"name": "qt_users", "volume": "vol_web_data", "security_style": "unix", "oplocks": True},
        ],
        "network_interfaces": [
            {"name": "svm-prod-data", "svm": "svm-prod", "address": "10.0.10.50", "home_port": "e0a", "status": "up"},
            {"name": "svm-dr-data", "svm": "svm-dr", "address": "10.0.20.50", "home_port": "e0a", "status": "up"},
        ],
        "snapmirrors": [
            {"id": "sm1", "source": "svm-prod:vol_web_data", "destination": "svm-dr:vol_dr_copy", "state": "snapmirrored", "lag": "00:05:00"},
        ],
        "exports": [
            {"volume": "vol_web_data", "policy": "default", "clients": ["10.0.0.0/24"], "rules": "rw"},
        ],
        "activity_log": [],
        "goal": {"title": "NetApp storage lab", "objective": "Grow vol_web_data before it runs out of space."},
        "broken": {"volume_near_full": "vol_web_data"},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "snapmirror" in slug and ("break" in slug or "failover" in slug):
        state["goal"] = {"title": "Break SnapMirror", "objective": "Break the SnapMirror relationship to promote the DR copy."}
        state["broken"] = {"needs_break_mirror": "sm1"}
    elif "snapmirror" in slug or "replicat" in slug:
        state["goal"] = {"title": "Create SnapMirror", "objective": "Create a SnapMirror relationship from vol_db_data to the DR SVM."}
        state["broken"] = {"needs_snapmirror": "vol_db_data"}
    elif "lun" in slug or "iscsi" in slug:
        state["goal"] = {"title": "Mount LUN", "objective": "Map the unmapped LUN to an initiator host."}
        state["broken"] = {"lun_unmapped": "/vol/vol_db_data/lun0"}
    elif "export" in slug or "nfs" in slug:
        state["goal"] = {"title": "Create NFS export", "objective": "Create an export policy rule so vol_db_data is reachable via NFS."}
        state["broken"] = {"needs_export": "vol_db_data"}
    elif "resize" in slug or "grow" in slug or "expand" in slug:
        state["goal"] = {"title": "Resize volume", "objective": "Grow vol_web_data before it runs out of space."}
        state["broken"] = {"volume_near_full": "vol_web_data"}
    elif "volume" in slug and "create" in slug:
        state["goal"] = {"title": "Create volume", "objective": "Create a new volume on aggr1 for the application team."}
        state["broken"] = {"needs_volume": True}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
        near_full = state.get("broken", {}).get("volume_near_full")
        if near_full:
            try:
                from apps.labs.provisioner.simulation.chaos_engine import inject as _chaos_inject
                _chaos_inject(session_id, "fill_disk", near_full, detail={"console": "netapp"})
            except Exception:  # pragma: no cover
                pass
    return entry


_ensure_session = _ensure


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_netapp_storage
        sync_netapp_storage(session_id, state)
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


def _find_volume(state: dict, name: str) -> dict | None:
    return next((v for v in state.get("volumes", []) if v.get("name") == name), None)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "NetApp session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        _event(state, "Signed in to System Manager", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to System Manager first"}

    if action == "create_volume":
        name = (payload.get("name") or "new_vol").strip()
        svm = payload.get("svm") or "svm-prod"
        aggregate = payload.get("aggregate") or "aggr1"
        size_gb = int(payload.get("size_gb") or 50)
        if _find_volume(state, name):
            return {"ok": False, "error": f"Volume {name} already exists"}
        state.setdefault("volumes", []).append({
            "name": name, "svm": svm, "aggregate": aggregate, "size_gb": size_gb,
            "used_gb": 0, "state": "online", "type": "rw",
        })
        broken.pop("needs_volume", None)
        _event(state, f"Volume {name} created ({size_gb}GB) on {aggregate}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Volume created"}

    if action == "resize_volume":
        name = payload.get("name") or broken.get("volume_near_full") or ""
        vol = _find_volume(state, name)
        if not vol:
            return {"ok": False, "error": f"Volume {name} not found"}
        new_size = int(payload.get("size_gb") or (vol.get("size_gb", 100) * 2))
        if new_size <= vol.get("size_gb", 0):
            return {"ok": False, "error": "New size must be larger than current size"}
        vol["size_gb"] = new_size
        if broken.get("volume_near_full") == name:
            broken.pop("volume_near_full", None)
        _event(state, f"Volume {name} resized to {new_size}GB", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.chaos_engine import clear_faults as _chaos_clear
            _chaos_clear(session_id, fault_type="fill_disk", target=name)
        except Exception:  # pragma: no cover
            pass
        return {"ok": True, "message": "Volume resized"}

    if action == "create_snapmirror":
        source = payload.get("source") or "svm-prod:vol_db_data"
        destination = payload.get("destination") or "svm-dr:vol_dr_copy"
        sm_id = f"sm{len(state.get('snapmirrors', [])) + 1}"
        state.setdefault("snapmirrors", []).append({
            "id": sm_id, "source": source, "destination": destination,
            "state": "snapmirrored", "lag": "00:00:00",
        })
        vol_name = source.split(":")[-1]
        if broken.get("needs_snapmirror") == vol_name:
            broken.pop("needs_snapmirror", None)
        _event(state, f"SnapMirror {source} -> {destination} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "SnapMirror relationship created", "id": sm_id}

    if action == "break_mirror":
        sm_id = payload.get("id") or broken.get("needs_break_mirror") or ""
        sm = next((s for s in state.get("snapmirrors", []) if s.get("id") == sm_id), None)
        if not sm:
            return {"ok": False, "error": f"SnapMirror relationship {sm_id} not found"}
        sm["state"] = "broken-off"
        if broken.get("needs_break_mirror") == sm_id:
            broken.pop("needs_break_mirror", None)
        _event(state, f"SnapMirror {sm_id} broken — destination promoted read-write", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "SnapMirror relationship broken"}

    if action == "create_export":
        volume = payload.get("volume") or broken.get("needs_export") or "vol_web_data"
        clients = payload.get("clients") or ["0.0.0.0/0"]
        state.setdefault("exports", []).append({
            "volume": volume, "policy": payload.get("policy") or "default",
            "clients": clients, "rules": payload.get("rules") or "rw",
        })
        if broken.get("needs_export") == volume:
            broken.pop("needs_export", None)
        _event(state, f"Export policy rule added for {volume}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Export created"}

    if action == "mount_lun":
        path = payload.get("path") or broken.get("lun_unmapped") or ""
        lun = next((l for l in state.get("luns", []) if l.get("path") == path), None)
        if not lun:
            return {"ok": False, "error": f"LUN {path} not found"}
        lun["mapped"] = True
        lun["initiator"] = payload.get("initiator") or "iqn.1994-05.com.redhat:client1"
        if broken.get("lun_unmapped") == path:
            broken.pop("lun_unmapped", None)
        _event(state, f"LUN {path} mapped to {lun['initiator']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "LUN mapped"}

    if action == "take_snapshot":
        volume = payload.get("volume") or "vol_web_data"
        vol = _find_volume(state, volume)
        if not vol:
            return {"ok": False, "error": f"Volume {volume} not found"}
        name = payload.get("name") or f"{volume}.manual.{int(time.time()) % 100000}"
        state.setdefault("snapshots", []).insert(0, {
            "name": name, "volume": volume, "size_gb": round(float(vol.get("used_gb", 1)) * 0.02, 2),
            "created": _now_iso(),
        })
        _event(state, f"Snapshot {name} created on {volume}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Snapshot created", "name": name}

    if action == "create_qtree":
        volume = payload.get("volume") or "vol_web_data"
        name = (payload.get("name") or "qt_new").strip()
        if not _find_volume(state, volume):
            return {"ok": False, "error": f"Volume {volume} not found"}
        state.setdefault("qtrees", []).append({
            "name": name, "volume": volume,
            "security_style": payload.get("security_style") or "unix", "oplocks": True,
        })
        _event(state, f"Qtree {name} created on {volume}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Qtree created"}

    if action == "offline_volume":
        name = payload.get("name") or ""
        vol = _find_volume(state, name)
        if not vol:
            return {"ok": False, "error": f"Volume {name} not found"}
        vol["state"] = "offline"
        _event(state, f"Volume {name} taken offline", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Volume offline"}

    if action == "online_volume":
        name = payload.get("name") or ""
        vol = _find_volume(state, name)
        if not vol:
            return {"ok": False, "error": f"Volume {name} not found"}
        vol["state"] = "online"
        _event(state, f"Volume {name} brought online", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Volume online"}

    if action == "create_lun":
        volume = payload.get("volume") or "vol_db_data"
        size_gb = int(payload.get("size_gb") or 50)
        path = payload.get("path") or f"/vol/{volume}/lun{len(state.get('luns', []))}"
        state.setdefault("luns", []).append({
            "path": path, "size_gb": size_gb, "svm": payload.get("svm") or "svm-prod",
            "mapped": False, "os_type": payload.get("os_type") or "linux",
        })
        _event(state, f"LUN {path} created ({size_gb}GB)", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "LUN created"}

    if action == "resync_mirror":
        sm_id = payload.get("id") or ""
        sm = next((s for s in state.get("snapmirrors", []) if s.get("id") == sm_id), None)
        if not sm:
            return {"ok": False, "error": f"SnapMirror {sm_id} not found"}
        sm["state"] = "snapmirrored"
        sm["lag"] = "00:00:00"
        _event(state, f"SnapMirror {sm_id} resynchronized", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "SnapMirror resynced"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_netapp_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No NetApp session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "NetApp environment still has unresolved issues"
    return True, "NetApp lab objectives met"
