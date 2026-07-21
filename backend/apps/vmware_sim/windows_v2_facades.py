"""Windows Server V2 facades — Hyper-V Manager VMs for lab grading.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "hyperv_vms": [
            {"name": "DC01", "state": "Running", "cpu": 12, "mem": 4096, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 1},
            {"name": "WEB01", "state": "Running", "cpu": 8, "mem": 2048, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 0},
            {"name": "WEB02", "state": "Running", "cpu": 6, "mem": 2048, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 0},
            {"name": "DB01", "state": "Running", "cpu": 24, "mem": 8192, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 2},
            {"name": "APP01", "state": "Running", "cpu": 15, "mem": 4096, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 0},
            {"name": "BACKUP01", "state": "Saved", "cpu": 0, "mem": 0, "uptime": "", "status": "Saved state", "generation": 1, "checkpoints": 1},
            {"name": "DEV-WIN", "state": "Off", "cpu": 0, "mem": 0, "uptime": "", "status": "Off", "generation": 2, "checkpoints": 0},
            {"name": "TEST-VM", "state": "Running", "cpu": 3, "mem": 1024, "uptime": "0.00:45:22", "status": "Operating normally", "generation": 2, "checkpoints": 0},
            {"name": "LEGACY-APP", "state": "Paused", "cpu": 0, "mem": 2048, "uptime": "", "status": "Paused", "generation": 1, "checkpoints": 0},
        ],
    }


def ensure_v2(world: dict) -> None:
    v2 = world.setdefault("v2", {})
    for key, value in seed_v2().items():
        if key not in v2 or v2.get(key) is None:
            v2[key] = value
    # Flat convenience mirror for get_state consumers.
    world["hyperv_vms"] = v2["hyperv_vms"]


def _find_vm(world: dict, name: str) -> dict | None:
    ensure_v2(world)
    return next((v for v in world.get("hyperv_vms") or [] if v.get("name") == name), None)


def apply_v2_action(world: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(world)

    if action == "hyperv_start":
        vm = _find_vm(world, payload.get("name") or "")
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        vm["state"] = "Running"
        vm["status"] = "Operating normally"
        vm["cpu"] = int(payload.get("cpu") or max(vm.get("cpu") or 0, 5))
        vm["mem"] = int(payload.get("mem") or max(vm.get("mem") or 0, 1024))
        vm["uptime"] = vm.get("uptime") or "0.00:00:01"
        return {"ok": True, "message": f"Started {vm['name']}", "vm": vm}

    if action == "hyperv_stop":
        vm = _find_vm(world, payload.get("name") or "")
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        vm["state"] = "Off"
        vm["status"] = "Off"
        vm["cpu"] = 0
        vm["mem"] = 0
        vm["uptime"] = ""
        return {"ok": True, "message": f"Turned off {vm['name']}", "vm": vm}

    if action == "hyperv_checkpoint":
        vm = _find_vm(world, payload.get("name") or "")
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        vm["checkpoints"] = int(vm.get("checkpoints") or 0) + 1
        vm["last_checkpoint"] = _now()
        return {"ok": True, "message": f"Checkpoint created for {vm['name']}", "vm": vm}

    if action == "hyperv_create":
        name = (payload.get("name") or f"NEW-VM-{len(world.get('hyperv_vms') or []) + 1}").strip()
        if _find_vm(world, name):
            return {"ok": False, "error": f"VM '{name}' already exists"}
        row = {
            "name": name,
            "state": "Off",
            "cpu": 0,
            "mem": 0,
            "uptime": "",
            "status": "Off",
            "generation": int(payload.get("generation") or 2),
            "checkpoints": 0,
            "memory_startup_mb": int(payload.get("memory_mb") or 2048),
        }
        world.setdefault("hyperv_vms", []).append(row)
        world["v2"]["hyperv_vms"] = world["hyperv_vms"]
        return {"ok": True, "message": f"Created VM {name}", "vm": row}

    return None
