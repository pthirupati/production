"""In-memory OpenStack Horizon console for cloud training labs.

Server-authoritative session state: Keystone project, Nova instances,
Neutron networks, Cinder volumes, Glance images. Zero real OpenStack APIs.
"""

from __future__ import annotations

import copy
import json
import random
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200
PENDING_SECONDS = 3

FLAVORS: dict[str, dict[str, Any]] = {
    "m1.tiny": {"vcpus": 1, "ram_gb": 1, "disk_gb": 10},
    "m1.small": {"vcpus": 1, "ram_gb": 2, "disk_gb": 20},
    "m1.medium": {"vcpus": 2, "ram_gb": 4, "disk_gb": 40},
    "m1.large": {"vcpus": 4, "ram_gb": 8, "disk_gb": 80},
    "m1.xlarge": {"vcpus": 8, "ram_gb": 16, "disk_gb": 160},
}

_HEX = "0123456789abcdef"


def _hex(n: int) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _uuid() -> str:
    return f"{_hex(8)}-{_hex(4)}-{_hex(4)}-{_hex(4)}-{_hex(12)}"


def _session_key(session_id: str) -> str:
    return f"openstack_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now() -> float:
    return time.time()


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {
        "time": _now_iso(), "message": message, "severity": severity,
    })


def _find_instance(state: dict, ident: str) -> dict | None:
    for inst in state.get("instances", []):
        if inst.get("id") == ident or inst.get("name") == ident:
            return inst
    return None


def _find_volume(state: dict, ident: str) -> dict | None:
    return next((v for v in state.get("volumes", []) if v.get("id") == ident or v.get("name") == ident), None)


def _base_state() -> dict:
    project = "fixitlab-prod"
    net_id = _uuid()
    vol_id = _uuid()
    inst_id = _uuid()
    return {
        "session": {"logged_in": False, "user": ""},
        "project": {"id": _uuid(), "name": project, "domain": "Default"},
        "flavors": [{"name": k, **v} for k, v in FLAVORS.items()],
        "images": [
            {"id": _uuid(), "name": "cirros-0.6.2", "status": "active", "size_gb": 1},
            {"id": _uuid(), "name": "ubuntu-22.04", "status": "active", "size_gb": 8},
            {"id": _uuid(), "name": "rhel-9", "status": "active", "size_gb": 10},
        ],
        "networks": [
            {
                "id": net_id, "name": "private", "project": project,
                "subnets": [{"name": "private-subnet", "cidr": "10.0.0.0/24", "gateway": "10.0.0.1"}],
                "status": "ACTIVE",
            },
            {
                "id": _uuid(), "name": "public", "project": project,
                "subnets": [{"name": "public-subnet", "cidr": "172.24.4.0/24", "gateway": "172.24.4.1"}],
                "status": "ACTIVE",
            },
        ],
        "volumes": [
            {
                "id": vol_id, "name": "vol-web-data", "size_gb": 50, "status": "available",
                "attached_to": None, "device": None, "bootable": False,
            },
        ],
        "instances": [
            {
                "id": inst_id, "name": "web-01", "status": "ACTIVE",
                "flavor": "m1.medium", "image": "ubuntu-22.04",
                "network": "private", "private_ip": "10.0.0.15",
                "power_state": "Running", "created": _now_iso(),
                "lab_managed": False,
            },
        ],
        "events": [
            {"time": _now_iso(), "message": "Horizon dashboard ready", "severity": "info"},
        ],
        "goal": {
            "title": "OpenStack operations",
            "summary": "Manage Nova instances, Neutron networks, and Cinder volumes from Horizon.",
        },
        "broken": {},
    }


def _scenario_overlay(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    if "attach" in slug or "volume" in slug:
        state["goal"] = {
            "title": "Attach Cinder volume",
            "summary": "Attach vol-web-data to web-01, then confirm the disk in the lab terminal with lsblk.",
        }
        state["broken"] = {"volume_unattached": True}
    elif "stop" in slug or "power" in slug:
        inst = state["instances"][0]
        inst["status"] = "SHUTOFF"
        inst["power_state"] = "Shutdown"
        state["goal"] = {
            "title": "Restore instance power",
            "summary": "web-01 is SHUTOFF after a maintenance window. Start it from Horizon.",
        }
        state["broken"] = {"instance_stopped": True}
    elif "create" in slug or "launch" in slug:
        state["goal"] = {
            "title": "Launch a Nova instance",
            "summary": "Launch app-02 from ubuntu-22.04 on the private network using m1.small.",
        }
        state["broken"] = {"needs_instance": True}


def _ensure(session_id: str, scenario_slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _scenario_overlay(state, scenario_slug)
        entry = {"scenario_slug": scenario_slug or "", "state": state}
        _save(session_id, entry)
    elif scenario_slug and not entry.get("scenario_slug"):
        entry["scenario_slug"] = scenario_slug
        _save(session_id, entry)
    return entry


def _advance_lifecycle(state: dict) -> bool:
    changed = False
    for inst in state.get("instances", []):
        transition = inst.get("_transition")
        if not transition:
            continue
        if _now() - transition.get("started_ts", 0) >= PENDING_SECONDS:
            inst["status"] = transition["status"]
            inst["power_state"] = transition["power_state"]
            inst.pop("_transition", None)
            changed = True
    return changed


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    if _advance_lifecycle(entry["state"]):
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
        primary = state["instances"][0] if state.get("instances") else None
        if primary:
            sync_openstack_instance(session_id, primary, flavors=FLAVORS)
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


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if entry is None and action in ("create_instance", "login"):
        entry = _ensure(session_id, payload.get("scenario_slug") or "")
    if not entry:
        return {"ok": False, "error": "Session not found"}
    state = entry["state"]
    _advance_lifecycle(state)

    if action == "login":
        state["session"]["logged_in"] = True
        state["session"]["user"] = payload.get("user") or "admin"
        _event(state, f"Signed in as {state['session']['user']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Authenticated"}

    if action == "logout":
        state["session"]["logged_in"] = False
        state["session"]["user"] = ""
        _save(session_id, entry)
        return {"ok": True}

    if not state.get("session", {}).get("logged_in") and action != "login":
        return {"ok": False, "error": "Not authenticated"}

    if action == "create_instance":
        name = (payload.get("name") or "instance-new").strip()
        flavor = payload.get("flavor") or "m1.small"
        if flavor not in FLAVORS:
            return {"ok": False, "error": f"Unknown flavor '{flavor}'"}
        image = payload.get("image") or "ubuntu-22.04"
        network = payload.get("network") or "private"
        last_octet = 20 + len(state.get("instances", []))
        inst = {
            "id": _uuid(),
            "name": name,
            "status": "BUILD",
            "flavor": flavor,
            "image": image,
            "network": network,
            "private_ip": f"10.0.0.{last_octet}",
            "power_state": "No State",
            "created": _now_iso(),
            "lab_managed": True,
            "_transition": {
                "started_ts": _now(),
                "status": "ACTIVE",
                "power_state": "Running",
            },
        }
        state.setdefault("instances", []).append(inst)
        _event(state, f"Launching instance {name} ({flavor})", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
            sync_openstack_instance(session_id, {**inst, "status": "ACTIVE", "power_state": "Running"}, flavors=FLAVORS)
        except Exception:
            pass
        return {"ok": True, "message": "Instance create started", "instance": inst}

    if action in ("start_instance", "stop_instance", "reboot_instance"):
        inst = _find_instance(state, payload.get("instance_id") or payload.get("name") or "")
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if action == "start_instance":
            inst["status"] = "ACTIVE"
            inst["power_state"] = "Running"
            op = "start"
        elif action == "stop_instance":
            inst["status"] = "SHUTOFF"
            inst["power_state"] = "Shutdown"
            op = "stop"
        else:
            inst["status"] = "REBOOT"
            inst["power_state"] = "Running"
            inst["_transition"] = {
                "started_ts": _now(), "status": "ACTIVE", "power_state": "Running",
            }
            op = "restart"
        _event(state, f"{op.title()} instance {inst['name']}", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            openstack_bridge.record_instance_power(str(session_id), op)
            from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
            sync_openstack_instance(session_id, inst, flavors=FLAVORS)
        except Exception:
            pass
        return {"ok": True, "message": f"Instance {op} requested"}

    if action == "delete_instance":
        ident = payload.get("instance_id") or payload.get("name") or ""
        before = len(state.get("instances", []))
        state["instances"] = [i for i in state.get("instances", []) if i.get("id") != ident and i.get("name") != ident]
        if len(state["instances"]) == before:
            return {"ok": False, "error": "Instance not found"}
        _event(state, f"Deleted instance {ident}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Instance deleted"}

    if action == "attach_volume":
        vol = _find_volume(state, payload.get("volume_id") or payload.get("name") or "")
        inst = _find_instance(state, payload.get("instance_id") or payload.get("instance") or "")
        if not vol:
            return {"ok": False, "error": "Volume not found"}
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if vol.get("status") == "in-use":
            return {"ok": False, "error": "Volume already attached"}
        device = payload.get("device") or "/dev/vdb"
        vol["status"] = "in-use"
        vol["attached_to"] = inst["id"]
        vol["device"] = device
        _event(state, f"Attached {vol['name']} to {inst['name']} at {device}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            openstack_bridge.record_disk_attach(
                str(session_id), vol["name"], size_gb=int(vol.get("size_gb") or 50), device=device,
            )
        except Exception:
            pass
        return {"ok": True, "message": "Volume attached", "device": device}

    if action == "detach_volume":
        vol = _find_volume(state, payload.get("volume_id") or payload.get("name") or "")
        if not vol:
            return {"ok": False, "error": "Volume not found"}
        device = vol.get("device")
        vol["status"] = "available"
        vol["attached_to"] = None
        vol["device"] = None
        _event(state, f"Detached volume {vol['name']}", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            if device:
                openstack_bridge.record_disk_detach(str(session_id), device)
        except Exception:
            pass
        return {"ok": True, "message": "Volume detached"}

    if action == "resize_instance":
        inst = _find_instance(state, payload.get("instance_id") or payload.get("name") or "")
        flavor = payload.get("flavor") or ""
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if flavor not in FLAVORS:
            return {"ok": False, "error": f"Unknown flavor '{flavor}'"}
        inst["flavor"] = flavor
        _event(state, f"Resized {inst['name']} to {flavor}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            openstack_bridge.record_instance_resize(str(session_id), FLAVORS[flavor])
            from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
            sync_openstack_instance(session_id, inst, flavors=FLAVORS)
        except Exception:
            pass
        return {"ok": True, "message": "Resize complete"}

    return {"ok": False, "error": f"Unknown action '{action}'"}
