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

from .netapp_v2_facades import apply_v2_action, ensure_v2, seed_v2

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
        **seed_v2(),
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
    elif "svm" in slug or "vserver" in slug or "learn-svm" in slug:
        # Academy SVM labs grade on svm-prod running + NFS (state_assertions).
        state["goal"] = {
            "title": "Bring SVM online",
            "objective": "Start svm-prod and restore the NFS protocol.",
        }
        state["broken"] = {"svm_stopped": "svm-prod", "needs_nfs": "svm-prod"}
        for svm in state.get("svms") or []:
            if svm.get("name") == "svm-prod":
                svm["state"] = "stopped"
                svm["protocols"] = [p for p in (svm.get("protocols") or []) if p != "nfs"] or ["cifs"]


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
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    if set(entry["state"].keys()) != keys_before:
        _save(session_id, entry)
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


def _find_aggregate(state: dict, name: str) -> dict | None:
    return next((a for a in state.get("aggregates", []) if a.get("name") == name), None)


def _aggr_free_gb(aggr: dict) -> int:
    """Free space on an aggregate, floored at 0.

    used_gb is the aggregate's own allocated figure (aggr1 ships 1800GB used
    against 5000GB with only 300GB of that from the seeded volumes), not a
    derived sum — so provisioning has to add to it rather than recompute it.
    """
    return max(0, int(aggr.get("size_gb", 0)) - int(aggr.get("used_gb", 0)))


def _lun_volume(lun: dict) -> str:
    """Containing volume for a LUN.

    Seeded LUNs carry it only inside the path (`/vol/vol_db_data/lun0`); LUNs
    created through the engine record it explicitly.
    """
    if lun.get("volume"):
        return lun["volume"]
    parts = (lun.get("path") or "").split("/")
    return parts[2] if len(parts) > 3 and parts[1] == "vol" else ""


def _volume_free_for_luns_gb(state: dict, vol: dict) -> int:
    """Space left in a volume once its existing LUNs are subtracted.

    LUNs are space-reserved against the volume they live in, so provisioning
    has to charge the full LUN size rather than its consumed bytes.
    """
    allocated = sum(
        int(l.get("size_gb", 0))
        for l in state.get("luns", [])
        if _lun_volume(l) == vol.get("name")
    )
    return max(0, int(vol.get("size_gb", 0)) - allocated)


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
        if size_gb <= 0:
            return {"ok": False, "error": "Volume size must be greater than 0GB"}
        aggr = _find_aggregate(state, aggregate)
        if not aggr:
            return {"ok": False, "error": f"Aggregate {aggregate} not found"}
        free_gb = _aggr_free_gb(aggr)
        if size_gb > free_gb:
            return {
                "ok": False,
                "error": (
                    f"Aggregate {aggregate} has only {free_gb}GB free — "
                    f"cannot provision a {size_gb}GB volume"
                ),
            }
        state.setdefault("volumes", []).append({
            "name": name, "svm": svm, "aggregate": aggregate, "size_gb": size_gb,
            "used_gb": 0, "state": "online", "type": "rw",
        })
        # Thick-provision accounting: charge the aggregate for the full size so
        # free space does not drift across a multi-step lab.
        aggr["used_gb"] = int(aggr.get("used_gb", 0)) + size_gb
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
        current_size = int(vol.get("size_gb", 0))
        if new_size <= current_size:
            return {"ok": False, "error": "New size must be larger than current size"}
        aggr = _find_aggregate(state, vol.get("aggregate"))
        if not aggr:
            return {"ok": False, "error": f"Aggregate {vol.get('aggregate')} not found"}
        delta_gb = new_size - current_size
        free_gb = _aggr_free_gb(aggr)
        if delta_gb > free_gb:
            return {
                "ok": False,
                "error": (
                    f"Aggregate {aggr['name']} has only {free_gb}GB free — "
                    f"cannot grow {name} by {delta_gb}GB"
                ),
            }
        vol["size_gb"] = new_size
        aggr["used_gb"] = int(aggr.get("used_gb", 0)) + delta_gb
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
        try:
            from apps.labs.provisioner.simulation import netapp_bridge
            netapp_bridge.record_lun_mapped(
                str(session_id),
                path,
                lun.get("size_gb") or 50,
                device="/dev/mapper/netapp0",
            )
        except Exception:
            pass
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
        # `or 50` would swallow an explicit 0, hiding it behind the default and
        # skipping the size guard below.
        raw_size = payload.get("size_gb")
        size_gb = int(raw_size) if raw_size not in (None, "") else 50
        if size_gb <= 0:
            return {"ok": False, "error": "LUN size must be greater than 0GB"}
        vol = _find_volume(state, volume)
        if not vol:
            return {"ok": False, "error": f"Volume {volume} not found"}
        free_gb = _volume_free_for_luns_gb(state, vol)
        if size_gb > free_gb:
            # ONTAP refuses a LUN that cannot fit in its containing volume.
            # Without this the lab would silently over-provision and the
            # capacity objectives below would be ungradeable.
            return {
                "ok": False,
                "error": (
                    f"Volume {volume} has only {free_gb}GB available for LUNs — "
                    f"cannot create a {size_gb}GB LUN. Grow the volume first."
                ),
            }
        path = payload.get("path") or f"/vol/{volume}/lun{len(state.get('luns', []))}"
        state.setdefault("luns", []).append({
            "path": path, "size_gb": size_gb, "svm": payload.get("svm") or "svm-prod",
            "mapped": False, "os_type": payload.get("os_type") or "linux",
            "volume": volume,
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

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or action, "success")
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# Per-key grader feedback. Unlike azure_engine, whose broken dict stores
# human-readable reasons, this engine stores bare targets (a volume name, a
# SnapMirror id) and sometimes just True — so the value cannot be echoed
# directly. Each template names the unmet objective and only interpolates the
# target when there is one worth showing.
_BROKEN_REASONS: dict[str, str] = {
    "volume_near_full": "volume {target} is still near full — grow it",
    "needs_volume": "the requested volume has not been created yet",
    "needs_snapmirror": "no SnapMirror relationship exists for {target} yet",
    "needs_break_mirror": "SnapMirror relationship {target} has not been broken off yet",
    "lun_unmapped": "LUN {target} is not mapped to an initiator yet",
    "needs_export": "volume {target} has no export policy rule yet",
}


def _describe_broken(broken: dict) -> str:
    kind = next(iter(broken.keys()))
    target = broken[kind]
    template = _BROKEN_REASONS.get(kind)
    if template is None:
        # Unknown key: still fail CLOSED, and name the key so a missing
        # template shows up as a reportable gap rather than a silent pass.
        return f"unresolved objective ({kind})"
    return template.format(target=target)


def validate_netapp_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No NetApp session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, f"NetApp lab not complete: {_describe_broken(broken)}"
    return True, "NetApp lab objectives met"


# ---------------------------------------------------------------------------
# ONTAP clustershell CLI surface
#
# `volume show`, `snapmirror show` and friends render from the same session
# state System Manager draws, and every write command routes back through
# apply_action so the `broken` flags, capacity arithmetic and the LUN bridge
# behave identically whether the learner clicked or typed. Unknown commands
# return rc!=0 — silently accepting one would leave a lab whose flag never
# cleared looking solved.
# ---------------------------------------------------------------------------

_ONTAP_HINT = "Enter 'help' for the supported command list."


def _ontap_error(message: str, *, rc: int = 1) -> dict:
    return {"ok": False, "rc": rc, "error": message, "stdout": "", "stderr": f"Error: {message}"}


def _ontap_ok(stdout: str, *, message: str = "") -> dict:
    return {"ok": True, "rc": 0, "stdout": stdout, "stderr": "", "message": message or stdout}


def _ontap_run(session_id: str, action: str, payload: dict) -> dict:
    """Delegate a write to apply_action and normalize it to shell shape.

    apply_action returns {ok, message|error} with no rc, but every CLI caller
    (and the grader-facing terminal) keys off rc, so a delegated failure has to
    surface as non-zero rather than a missing key.
    """
    result = apply_action(session_id, action, payload)
    if result.get("ok"):
        message = result.get("message") or ""
        return {**result, "rc": 0, "stdout": message, "stderr": ""}
    error = result.get("error") or "command failed"
    return {**result, "rc": 1, "stdout": "", "stderr": f"Error: {error}"}


def _ontap_parse(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split ONTAP `-field value` pairs from positional command words.

    ONTAP uses single-dash long options (`-vserver svm-prod -size 200GB`), so
    the parser keys off a leading '-' rather than '--'.
    """
    positionals: list[str] = []
    opts: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-") and len(tok) > 1 and not tok[1].isdigit():
            key = tok.lstrip("-").replace("-", "_")
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                opts[key] = tokens[i + 1]
                i += 1
            else:
                opts[key] = "true"
        else:
            positionals.append(tok)
        i += 1
    return positionals, opts


def _ontap_size_gb(raw: str) -> int | None:
    """Parse an ONTAP size literal (`200GB`, `1TB`, `500g`, bare `200`)."""
    if not raw:
        return None
    text = str(raw).strip().lower().rstrip("b")
    multiplier = 1
    if text.endswith("t"):
        multiplier, text = 1024, text[:-1]
    elif text.endswith("g"):
        multiplier, text = 1, text[:-1]
    elif text.endswith("m"):
        # Sub-GB requests round down to 0 and are rejected by the size guard.
        multiplier, text = 0, text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def _ontap_table(headers: list[str], rows: list[list[str]]) -> str:
    """ONTAP clustershell listing: header, dashed rule, space-padded columns."""
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))
    lines = [
        " ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip(),
        " ".join("-" * widths[i] for i in range(len(headers))).rstrip(),
    ]
    for row in rows:
        lines.append(" ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip())
    lines.append(f"{len(rows)} entries were displayed.")
    return "\n".join(lines)


_ONTAP_HELP = """Supported commands:
  volume show | volume create | volume size | volume offline | volume online
  lun show | lun create | lun map
  snapmirror show | snapmirror create | snapmirror break | snapmirror resync
  aggr show | storage aggregate show
  snapshot show | snapshot create
  vserver show | network interface show | qtree show | qtree create
  export-policy rule create
"""


def _ontap_volume(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else "show"
    name = opts.get("volume") or (args[1] if len(args) > 1 else "")

    if verb == "show":
        rows = []
        for v in state.get("volumes", []):
            if name and v.get("name") != name:
                continue
            size = int(v.get("size_gb", 0))
            used = int(v.get("used_gb", 0))
            pct = f"{round(used / size * 100)}%" if size else "-"
            rows.append([v.get("svm", ""), v.get("name", ""), v.get("aggregate", ""),
                         v.get("state", ""), v.get("type", ""), f"{size}GB", f"{size - used}GB", pct])
        return _ontap_ok(_ontap_table(
            ["Vserver", "Volume", "Aggregate", "State", "Type", "Size", "Available", "Used%"], rows))

    if verb == "create":
        if not name:
            return _ontap_error('Missing required parameter "-volume".')
        size = _ontap_size_gb(opts.get("size", ""))
        if size is None:
            return _ontap_error('Missing required parameter "-size".')
        payload = {"name": name, "size_gb": size}
        if opts.get("aggregate") or opts.get("aggr"):
            payload["aggregate"] = opts.get("aggregate") or opts["aggr"]
        if opts.get("vserver"):
            payload["svm"] = opts["vserver"]
        return _ontap_run(session_id, "create_volume", payload)

    if verb in ("size", "modify", "resize"):
        if not name:
            return _ontap_error('Missing required parameter "-volume".')
        size = _ontap_size_gb(opts.get("new_size") or opts.get("size", ""))
        if size is None:
            return _ontap_error('Missing required parameter "-new-size".')
        return _ontap_run(session_id, "resize_volume", {"name": name, "size_gb": size})

    if verb in ("offline", "online"):
        if not name:
            return _ontap_error('Missing required parameter "-volume".')
        return _ontap_run(session_id, f"{verb}_volume", {"name": name})

    return _ontap_error(f'"{verb}" is not a recognized volume command. {_ONTAP_HINT}')


def _ontap_lun(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else "show"
    path = opts.get("path") or (args[1] if len(args) > 1 else "")

    if verb == "show":
        rows = [[l.get("svm", ""), l.get("path", ""), f"{l.get('size_gb', 0)}GB",
                 "mapped" if l.get("mapped") else "unmapped", l.get("os_type", "")]
                for l in state.get("luns", [])]
        return _ontap_ok(_ontap_table(["Vserver", "Path", "Size", "State", "OS Type"], rows))

    if verb == "create":
        size = _ontap_size_gb(opts.get("size", ""))
        if size is None:
            return _ontap_error('Missing required parameter "-size".')
        payload = {"size_gb": size}
        if path:
            payload["path"] = path
            # `-path /vol/<volume>/<lun>` names the containing volume.
            parts = path.split("/")
            if len(parts) > 3 and parts[1] == "vol":
                payload["volume"] = parts[2]
        if opts.get("volume"):
            payload["volume"] = opts["volume"]
        if opts.get("ostype") or opts.get("os_type"):
            payload["os_type"] = opts.get("ostype") or opts["os_type"]
        return _ontap_run(session_id, "create_lun", payload)

    if verb in ("map", "mapping"):
        # `lun map -path X -igroup Y` and `lun mapping create -path X ...`.
        if not path:
            path = opts.get("path", "")
        if not path:
            return _ontap_error('Missing required parameter "-path".')
        payload = {"path": path}
        if opts.get("igroup") or opts.get("initiator"):
            payload["initiator"] = opts.get("igroup") or opts["initiator"]
        return _ontap_run(session_id, "mount_lun", payload)

    return _ontap_error(f'"{verb}" is not a recognized lun command. {_ONTAP_HINT}')


def _ontap_snapmirror(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else "show"

    if verb == "show":
        rows = [[s.get("id", ""), s.get("source", ""), s.get("destination", ""),
                 s.get("state", ""), s.get("lag", "")]
                for s in state.get("snapmirrors", [])]
        return _ontap_ok(_ontap_table(
            ["ID", "Source", "Destination", "Relationship Status", "Lag Time"], rows))

    if verb == "create":
        payload = {}
        if opts.get("source_path") or opts.get("source"):
            payload["source"] = opts.get("source_path") or opts["source"]
        if opts.get("destination_path") or opts.get("destination"):
            payload["destination"] = opts.get("destination_path") or opts["destination"]
        return _ontap_run(session_id, "create_snapmirror", payload)

    if verb in ("break", "break-quiesced"):
        sm_id = opts.get("id") or _sm_id_for(state, opts)
        if not sm_id:
            return _ontap_error('Missing required parameter "-destination-path".')
        return _ontap_run(session_id, "break_mirror", {"id": sm_id})

    if verb == "resync":
        sm_id = opts.get("id") or _sm_id_for(state, opts)
        if not sm_id:
            return _ontap_error('Missing required parameter "-destination-path".')
        return _ontap_run(session_id, "resync_mirror", {"id": sm_id})

    return _ontap_error(f'"{verb}" is not a recognized snapmirror command. {_ONTAP_HINT}')


def _sm_id_for(state: dict, opts: dict) -> str:
    """Resolve a SnapMirror id from a destination path, the way ONTAP does.

    Learners address relationships by `-destination-path svm-dr:vol_dr_copy`,
    never by the internal id the click actions use.
    """
    dest = opts.get("destination_path") or opts.get("destination") or ""
    if not dest:
        mirrors = state.get("snapmirrors", [])
        return mirrors[0].get("id", "") if len(mirrors) == 1 else ""
    match = next((s for s in state.get("snapmirrors", []) if s.get("destination") == dest), None)
    return match.get("id", "") if match else ""


def run_command(session_id: str, command: str) -> dict:
    """Execute one ONTAP clustershell line against the session state.

    Returns a shell-shaped dict ({ok, rc, stdout, stderr}). Unrecognized
    commands always come back rc!=0.
    """
    import shlex

    raw = (command or "").strip()
    if not raw:
        return _ontap_error("No command entered. " + _ONTAP_HINT)

    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return _ontap_error(f"Could not parse command ({exc})")

    if not tokens:
        return _ontap_error("No command entered. " + _ONTAP_HINT)

    if tokens[0] in ("help", "?"):
        return _ontap_ok(_ONTAP_HELP)

    entry = _ensure(session_id)
    state = entry["state"]

    if not state.get("session", {}).get("logged_in"):
        return _ontap_error("Access denied — log in to the cluster first.")

    positionals, opts = _ontap_parse(tokens)
    if not positionals:
        return _ontap_error("No command entered. " + _ONTAP_HINT)

    obj = positionals[0]
    args = positionals[1:]

    if obj == "volume" or obj == "vol":
        return _ontap_volume(state, session_id, args, opts)
    if obj == "lun":
        return _ontap_lun(state, session_id, args, opts)
    if obj == "snapmirror":
        return _ontap_snapmirror(state, session_id, args, opts)

    if obj in ("aggr", "aggregate") or (obj == "storage" and args and args[0] == "aggregate"):
        if obj == "storage":
            args = args[1:]
        verb = args[0] if args else "show"
        if verb != "show":
            return _ontap_error(f'"{verb}" is not a recognized aggregate command. {_ONTAP_HINT}')
        rows = []
        for a in state.get("aggregates", []):
            size = int(a.get("size_gb", 0))
            used = int(a.get("used_gb", 0))
            pct = f"{round(used / size * 100)}%" if size else "-"
            rows.append([a.get("name", ""), f"{size}GB", f"{_aggr_free_gb(a)}GB",
                         pct, a.get("state", ""), a.get("raid", "")])
        return _ontap_ok(_ontap_table(
            ["Aggregate", "Size", "Available", "Used%", "State", "RAID Type"], rows))

    if obj == "snapshot":
        verb = args[0] if args else "show"
        if verb == "show":
            rows = [[s.get("volume", ""), s.get("name", ""), f"{s.get('size_gb', 0)}GB", s.get("created", "")]
                    for s in state.get("snapshots", [])]
            return _ontap_ok(_ontap_table(["Volume", "Snapshot", "Size", "Created"], rows))
        if verb == "create":
            payload = {}
            if opts.get("volume"):
                payload["volume"] = opts["volume"]
            if opts.get("snapshot") or opts.get("name"):
                payload["name"] = opts.get("snapshot") or opts["name"]
            return _ontap_run(session_id, "take_snapshot", payload)
        return _ontap_error(f'"{verb}" is not a recognized snapshot command. {_ONTAP_HINT}')

    if obj == "qtree":
        verb = args[0] if args else "show"
        if verb == "show":
            rows = [[q.get("volume", ""), q.get("name", ""), q.get("security_style", ""), str(q.get("oplocks", ""))]
                    for q in state.get("qtrees", [])]
            return _ontap_ok(_ontap_table(["Volume", "Qtree", "Security Style", "Oplocks"], rows))
        if verb == "create":
            payload = {}
            for flag, key in (("volume", "volume"), ("qtree", "name"),
                              ("security_style", "security_style")):
                if opts.get(flag):
                    payload[key] = opts[flag]
            return _ontap_run(session_id, "create_qtree", payload)
        return _ontap_error(f'"{verb}" is not a recognized qtree command. {_ONTAP_HINT}')

    if obj == "vserver":
        verb = args[0] if args else "show"
        if verb != "show":
            return _ontap_error(f'"{verb}" is not a recognized vserver command. {_ONTAP_HINT}')
        rows = [[s.get("name", ""), s.get("state", ""), ",".join(s.get("protocols") or [])]
                for s in state.get("svms", [])]
        return _ontap_ok(_ontap_table(["Vserver", "State", "Allowed Protocols"], rows))

    if obj == "network" and args and args[0] == "interface":
        verb = args[1] if len(args) > 1 else "show"
        if verb != "show":
            return _ontap_error(f'"{verb}" is not a recognized interface command. {_ONTAP_HINT}')
        rows = [[n.get("svm", ""), n.get("name", ""), n.get("address", ""),
                 n.get("home_port", ""), n.get("status", "")]
                for n in state.get("network_interfaces", [])]
        return _ontap_ok(_ontap_table(
            ["Vserver", "Logical Interface", "Address", "Current Port", "Status"], rows))

    if obj in ("export-policy", "export"):
        # `export-policy rule create -vserver X -policyname Y -clientmatch Z`
        if args and args[0] == "rule" and len(args) > 1 and args[1] == "create":
            payload = {}
            if opts.get("volume"):
                payload["volume"] = opts["volume"]
            if opts.get("policyname") or opts.get("policy"):
                payload["policy"] = opts.get("policyname") or opts["policy"]
            if opts.get("clientmatch"):
                payload["clients"] = [c for c in opts["clientmatch"].split(",") if c]
            if opts.get("rorule") or opts.get("rwrule"):
                payload["rules"] = opts.get("rwrule") or opts["rorule"]
            return _ontap_run(session_id, "create_export", payload)
        if args and args[0] in ("show", "rule") :
            rows = [[e.get("volume", ""), e.get("policy", ""),
                     ",".join(e.get("clients") or []), e.get("rules", "")]
                    for e in state.get("exports", [])]
            return _ontap_ok(_ontap_table(["Volume", "Policy", "Client Match", "Access"], rows))
        return _ontap_error(f'"{" ".join(args)}" is not a recognized export-policy command. {_ONTAP_HINT}')

    return _ontap_error(f'"{obj}" is not a recognized command. {_ONTAP_HINT}')
