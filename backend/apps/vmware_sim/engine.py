"""
In-memory VMware vCenter simulator for training labs.
"""

from __future__ import annotations

import copy
import random
import time
from typing import Any

_SESSIONS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(message: str, severity: str = "info", entity: str = "") -> dict:
    return {"time": _now_iso(), "message": message, "severity": severity, "entity": entity}


def _base_inventory() -> dict:
    return {
        "datacenter": "DC-Prod",
        "cluster": "Cluster-01",
        "hosts": [
            {"id": "host-01", "name": "esxi-01.fixitlab.local", "status": "connected", "maintenance": False,
             "cpu_pct": 42, "mem_pct": 58, "network_mbps": 120, "storage_pct": 61},
            {"id": "host-02", "name": "esxi-02.fixitlab.local", "status": "connected", "maintenance": False,
             "cpu_pct": 35, "mem_pct": 49, "network_mbps": 88, "storage_pct": 54},
        ],
        "datastores": [
            {"id": "ds-01", "name": "datastore-ssd-01", "type": "VMFS", "capacity_gb": 2048, "free_gb": 412},
            {"id": "ds-02", "name": "datastore-nfs-01", "type": "NFS", "capacity_gb": 4096, "free_gb": 1900},
        ],
        "networks": [
            {"id": "net-01", "name": "VM Network", "vlan": 0, "type": "standard"},
            {"id": "net-02", "name": "Prod-VLAN-120", "vlan": 120, "type": "distributed"},
        ],
        "vms": [
            {"id": "vm-web", "name": "web-prod-01", "host_id": "host-01", "power": "poweredOff", "cpu": 4,
             "memory_mb": 8192, "guest_os": "Ubuntu Linux (64-bit)", "ip": "10.20.30.41", "tools": "notRunning"},
            {"id": "vm-api", "name": "api-prod-01", "host_id": "host-01", "power": "poweredOn", "cpu": 2,
             "memory_mb": 4096, "guest_os": "RHEL 8 (64-bit)", "ip": "10.20.30.42", "tools": "ok"},
            {"id": "vm-db", "name": "db-prod-01", "host_id": "host-02", "power": "poweredOn", "cpu": 8,
             "memory_mb": 16384, "guest_os": "RHEL 8 (64-bit)", "ip": "10.20.30.43", "tools": "ok"},
        ],
        "alarms": [],
        "events": [],
        "snapshots": {},
        "validation": {"target_vm": "web-prod-01", "require_power": "poweredOn"},
    }


def _apply_scenario_preset(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    events = state["events"]
    if "guest-powered-off" in slug:
        for vm in state["vms"]:
            if vm["name"] == "web-prod-01":
                vm["power"] = "poweredOff"
                vm["tools"] = "notRunning"
        events.append(_event("VM web-prod-01 powered off unexpectedly", "warning", "web-prod-01"))
        state["validation"] = {"target_vm": "web-prod-01", "require_power": "poweredOn"}
    elif "host-disconnected" in slug:
        state["hosts"][0]["status"] = "disconnected"
        events.append(_event("Host esxi-01.fixitlab.local disconnected", "critical", "esxi-01"))
        state["validation"] = {"require_host_connected": "esxi-01.fixitlab.local"}
    elif "ha-failure" in slug:
        state["cluster_ha"] = False
        state["hosts"][1]["status"] = "notResponding"
        for vm in state["vms"]:
            if vm["name"] == "web-prod-01":
                vm["power"] = "poweredOff"
        events.append(_event("HA cluster protection disabled on Cluster-01", "critical", "Cluster-01"))
        state["validation"] = {"cluster_ha": True, "target_vm": "web-prod-01", "require_power": "poweredOn"}
    elif "datastore-full" in slug:
        state["datastores"][0]["free_gb"] = 2
        state["alarms"].append({"id": "alm-ds-full", "name": "Datastore capacity alarm",
                                "entity": "datastore-ssd-01", "severity": "critical", "status": "active"})
        state["validation"] = {"datastore_min_free_gb": 100, "datastore": "datastore-ssd-01"}
    else:
        events.append(_event("vCenter inventory loaded", "info", "vCenter"))


def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    if key not in _SESSIONS:
        state = _base_inventory()
        state["events"] = []
        state["alarms"] = []
        state["snapshots"] = {}
        _apply_scenario_preset(state, scenario_slug)
        _SESSIONS[key] = {"session_id": key, "scenario_slug": scenario_slug, "state": state, "created_at": _now_iso()}
    return _SESSIONS[key]


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "inventory": state,
        "summary": {
            "hosts_connected": sum(1 for h in state["hosts"] if h["status"] == "connected"),
            "hosts_total": len(state["hosts"]),
            "vms_on": sum(1 for v in state["vms"] if v["power"] == "poweredOn"),
            "vms_total": len(state["vms"]),
            "active_alarms": len([a for a in state.get("alarms", []) if a.get("status") == "active"]),
        },
    }


def drop_session(session_id: str) -> None:
    _SESSIONS.pop(str(session_id), None)


def _find_vm(state: dict, vm_id: str | None = None, vm_name: str | None = None) -> dict | None:
    for vm in state["vms"]:
        if vm_id and vm["id"] == vm_id:
            return vm
        if vm_name and vm["name"] == vm_name:
            return vm
    return None


def _find_host(state: dict, host_id: str | None = None, host_name: str | None = None) -> dict | None:
    for host in state["hosts"]:
        if host_id and host["id"] == host_id:
            return host
        if host_name and host["name"] == host_name:
            return host
    return None


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _SESSIONS.get(str(session_id))
    if not entry:
        return {"ok": False, "error": "Simulation session not found"}
    state = entry["state"]
    events = state.setdefault("events", [])

    if action == "power_on":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        host = _find_host(state, vm.get("host_id"))
        if host and host.get("status") != "connected":
            return {"ok": False, "error": f"Host {host['name']} is not connected"}
        if host and host.get("maintenance"):
            return {"ok": False, "error": f"Host {host['name']} is in maintenance mode"}
        vm["power"] = "poweredOn"
        vm["tools"] = "ok"
        events.append(_event(f"Powered on VM {vm['name']}", "info", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} powered on"}

    if action == "power_off":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["power"] = "poweredOff"
        vm["tools"] = "notRunning"
        events.append(_event(f"Powered off VM {vm['name']}", "info", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} powered off"}

    if action == "reconnect_host":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        host["status"] = "connected"
        events.append(_event(f"Host {host['name']} reconnected", "info", host["name"]))
        return {"ok": True, "message": f"{host['name']} reconnected"}

    if action == "enable_ha":
        state["cluster_ha"] = True
        for host in state["hosts"]:
            if host["status"] == "notResponding":
                host["status"] = "connected"
        events.append(_event("HA enabled on Cluster-01", "info", "Cluster-01"))
        return {"ok": True, "message": "HA enabled"}

    if action == "expand_datastore":
        ds_name = payload.get("datastore") or "datastore-ssd-01"
        add_gb = int(payload.get("gb") or 500)
        for ds in state["datastores"]:
            if ds["name"] == ds_name:
                ds["capacity_gb"] += add_gb
                ds["free_gb"] += add_gb
                state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != ds_name]
                events.append(_event(f"Expanded {ds_name} by {add_gb} GB", "info", ds_name))
                return {"ok": True, "message": f"{ds_name} expanded"}
        return {"ok": False, "error": "Datastore not found"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_vmware_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _SESSIONS.get(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    rules = state.get("validation") or {}

    if rules.get("require_host_connected"):
        name = rules["require_host_connected"]
        host = _find_host(state, host_name=name)
        if not host or host.get("status") != "connected":
            return False, f"Host {name} must be connected"
        return True, f"Host {name} is connected"

    if rules.get("cluster_ha"):
        if not state.get("cluster_ha", True):
            return False, "HA must be enabled on the cluster"
        host = _find_host(state, host_name="esxi-02.fixitlab.local")
        if host and host.get("status") != "connected":
            return False, "All cluster hosts must be connected"

    if rules.get("datastore_min_free_gb"):
        ds_name = rules.get("datastore", "datastore-ssd-01")
        for ds in state["datastores"]:
            if ds["name"] == ds_name:
                if ds["free_gb"] < rules["datastore_min_free_gb"]:
                    return False, f"{ds_name} needs more free space"
                return True, f"{ds_name} has sufficient capacity"

    target = rules.get("target_vm", "web-prod-01")
    required = rules.get("require_power", "poweredOn")
    vm = _find_vm(state, vm_name=target)
    if not vm:
        return False, f"VM {target} not found"
    if vm.get("power") != required:
        return False, f"{target} must be {required} (currently {vm.get('power')})"
    return True, f"{target} is {required} — validation passed"
