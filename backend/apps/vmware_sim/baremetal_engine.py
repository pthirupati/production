"""In-memory MAAS / LXD / KVM bare-metal simulator for training labs."""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"baremetal_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _base_state() -> dict:
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"site": "fixitlab", "version": "MAAS 3.4 / LXD 5.x / KVM 8.x"},
        "maas": {
            "machines": [
                {"id": 1, "hostname": "gpu-node-01", "status": "Ready", "power": "on", "ip": "10.10.1.11"},
                {"id": 2, "hostname": "gpu-node-02", "status": "Failed commissioning", "power": "off", "ip": ""},
                {"id": 3, "hostname": "storage-01", "status": "Deployed", "power": "on", "ip": "10.10.1.20"},
            ],
            "fabrics": [{"name": "default", "vlans": ["pxe", "mgmt"]}],
        },
        "lxd": {
            "containers": [
                {"name": "infer-svc", "status": "Running", "ipv4": "10.10.2.5", "image": "ubuntu:22.04"},
                {"name": "batch-job", "status": "Stopped", "ipv4": "", "image": "ubuntu:22.04"},
            ],
            "profiles": ["default", "gpu-passthrough"],
        },
        "kvm": {
            "vms": [
                {"name": "train-vm-1", "state": "running", "vcpu": 8, "ram_gb": 32, "ip": "192.168.122.10"},
                {"name": "train-vm-2", "state": "shut off", "vcpu": 4, "ram_gb": 16, "ip": ""},
            ],
            "networks": ["default", "br-ai"],
            "pools": ["default"],
        },
        "ipmi": {"bmc_hosts": [{"name": "gpu-node-02", "reachable": False, "power": "unknown"}]},
        "goal": {"title": "Fix bare metal", "objective": "Commission the failed MAAS machine and deploy it."},
        "broken": {"machine_needs_commission": 2, "bmc_unreachable": True},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "lxd" in slug or "lxc" in slug:
        state["goal"] = {"title": "LXD container", "objective": "Start the stopped container and verify it has an IP."}
        state["broken"] = {"container_stopped": "batch-job"}
    elif "kvm" in slug or "virsh" in slug:
        state["goal"] = {"title": "KVM VM", "objective": "Start the shut-off VM and confirm it is running."}
        state["broken"] = {"vm_stopped": "train-vm-2"}
    elif "maas" in slug:
        state["goal"] = {"title": "MAAS commission", "objective": "Commission gpu-node-02 and deploy Ubuntu."}
        state["broken"] = {"machine_needs_commission": 2, "bmc_unreachable": True}
    elif "pxe" in slug:
        state["goal"] = {"title": "PXE boot", "objective": "Fix VLAN tagging so PXE discovery succeeds."}
        state["broken"] = {"pxe_vlan_wrong": True}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": copy.deepcopy(entry["state"]),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Bare metal session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": "Signed in to bare metal console", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in first"}

    if action == "maas_commission":
        mid = int(payload.get("machine_id") or broken.get("machine_needs_commission") or 2)
        for m in state["maas"]["machines"]:
            if m["id"] == mid:
                m["status"] = "Ready"
                m["power"] = "on"
                m["ip"] = m.get("ip") or f"10.10.1.{10 + mid}"
        broken.pop("machine_needs_commission", None)
        broken.pop("bmc_unreachable", None)
        for b in state["ipmi"]["bmc_hosts"]:
            b["reachable"] = True
            b["power"] = "on"
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} commissioned", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Commissioning complete"}

    if action == "maas_deploy":
        mid = int(payload.get("machine_id") or 2)
        for m in state["maas"]["machines"]:
            if m["id"] == mid:
                m["status"] = "Deployed"
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} deployed", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Deploy complete"}

    if action == "lxd_start":
        name = payload.get("name") or broken.get("container_stopped") or "batch-job"
        for c in state["lxd"]["containers"]:
            if c["name"] == name:
                c["status"] = "Running"
                c["ipv4"] = c.get("ipv4") or "10.10.2.6"
        broken.pop("container_stopped", None)
        _save(session_id, entry)
        return {"ok": True, "message": f"Container {name} started"}

    if action == "kvm_start":
        name = payload.get("name") or broken.get("vm_stopped") or "train-vm-2"
        for v in state["kvm"]["vms"]:
            if v["name"] == name:
                v["state"] = "running"
                v["ip"] = v.get("ip") or "192.168.122.11"
        broken.pop("vm_stopped", None)
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} started"}

    if action == "fix_pxe_vlan":
        broken.pop("pxe_vlan_wrong", None)
        _save(session_id, entry)
        return {"ok": True, "message": "PXE VLAN corrected"}

    if action == "create_lxd":
        name = payload.get("name") or "new-svc"
        state["lxd"]["containers"].append(
            {"name": name, "status": "Running", "ipv4": "10.10.2.7", "image": payload.get("image") or "ubuntu:22.04"}
        )
        _save(session_id, entry)
        return {"ok": True, "message": f"Container {name} created"}

    if action == "create_kvm":
        name = payload.get("name") or "new-vm"
        state["kvm"]["vms"].append(
            {"name": name, "state": "running", "vcpu": 4, "ram_gb": 8, "ip": "192.168.122.12"}
        )
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} created"}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_baremetal_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No bare metal session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "Bare metal environment still has unresolved issues"
    return True, "Bare metal lab objectives met"
