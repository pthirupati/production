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
            {"name": "DC01", "state": "Running", "cpu": 12, "mem": 4096, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 1, "vswitch": "External Switch", "vhd_path": "C:\\Hyper-V\\DC01.vhdx", "memory_startup_mb": 4096, "processors": 2},
            {"name": "WEB01", "state": "Running", "cpu": 8, "mem": 2048, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 0, "vswitch": "External Switch", "vhd_path": "C:\\Hyper-V\\WEB01.vhdx", "memory_startup_mb": 2048, "processors": 2},
            {"name": "WEB02", "state": "Running", "cpu": 6, "mem": 2048, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 0, "vswitch": "External Switch", "vhd_path": "C:\\Hyper-V\\WEB02.vhdx", "memory_startup_mb": 2048, "processors": 2},
            {"name": "DB01", "state": "Running", "cpu": 24, "mem": 8192, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 2, "vswitch": "Internal Switch", "vhd_path": "C:\\Hyper-V\\DB01.vhdx", "memory_startup_mb": 8192, "processors": 4},
            {"name": "APP01", "state": "Running", "cpu": 15, "mem": 4096, "uptime": "2.14:23:11", "status": "Operating normally", "generation": 2, "checkpoints": 0, "vswitch": "External Switch", "vhd_path": "C:\\Hyper-V\\APP01.vhdx", "memory_startup_mb": 4096, "processors": 2},
            {"name": "BACKUP01", "state": "Saved", "cpu": 0, "mem": 0, "uptime": "", "status": "Saved state", "generation": 1, "checkpoints": 1, "vswitch": "Private Switch", "vhd_path": "C:\\Hyper-V\\BACKUP01.vhdx", "memory_startup_mb": 2048, "processors": 1},
            {"name": "DEV-WIN", "state": "Off", "cpu": 0, "mem": 0, "uptime": "", "status": "Off", "generation": 2, "checkpoints": 0, "vswitch": "Default Switch", "vhd_path": "C:\\Hyper-V\\DEV-WIN.vhdx", "memory_startup_mb": 2048, "processors": 2},
            {"name": "TEST-VM", "state": "Running", "cpu": 3, "mem": 1024, "uptime": "0.00:45:22", "status": "Operating normally", "generation": 2, "checkpoints": 0, "vswitch": "Default Switch", "vhd_path": "C:\\Hyper-V\\TEST-VM.vhdx", "memory_startup_mb": 1024, "processors": 1},
            {"name": "LEGACY-APP", "state": "Paused", "cpu": 0, "mem": 2048, "uptime": "", "status": "Paused", "generation": 1, "checkpoints": 0, "vswitch": "Internal Switch", "vhd_path": "C:\\Hyper-V\\LEGACY-APP.vhdx", "memory_startup_mb": 2048, "processors": 1},
        ],
        "vswitches": [
            {"name": "External Switch", "type": "External", "adapter": "Ethernet", "notes": "Bound to physical NIC"},
            {"name": "Internal Switch", "type": "Internal", "adapter": "", "notes": "Host + VMs"},
            {"name": "Private Switch", "type": "Private", "adapter": "", "notes": "VMs only"},
            {"name": "Default Switch", "type": "Internal", "adapter": "", "notes": "NAT for lab VMs"},
        ],
        "vhdx_disks": [
            {"path": "C:\\Hyper-V\\DC01.vhdx", "size_gb": 80, "type": "Dynamic", "attached_to": "DC01"},
            {"path": "C:\\Hyper-V\\WEB01.vhdx", "size_gb": 60, "type": "Dynamic", "attached_to": "WEB01"},
        ],
        "console_sessions": [],
    }


def ensure_v2(world: dict) -> None:
    v2 = world.setdefault("v2", {})
    for key, value in seed_v2().items():
        if key not in v2 or v2.get(key) is None:
            v2[key] = value
    # Flat convenience mirror for get_state consumers.
    world["hyperv_vms"] = v2["hyperv_vms"]
    world["vswitches"] = v2.get("vswitches") or []
    world["vhdx_disks"] = v2.get("vhdx_disks") or []
    world["console_sessions"] = v2.get("console_sessions") or []


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
        mem = int(payload.get("memory_mb") or 2048)
        vhd = payload.get("vhd_path") or f"C:\\Hyper-V\\{name}.vhdx"
        row = {
            "name": name,
            "state": "Off",
            "cpu": 0,
            "mem": 0,
            "uptime": "",
            "status": "Off",
            "generation": int(payload.get("generation") or 2),
            "checkpoints": 0,
            "memory_startup_mb": mem,
            "processors": int(payload.get("processors") or 2),
            "vswitch": payload.get("vswitch") or "Default Switch",
            "vhd_path": vhd,
        }
        world.setdefault("hyperv_vms", []).append(row)
        world["v2"]["hyperv_vms"] = world["hyperv_vms"]
        disk = {"path": vhd, "size_gb": int(payload.get("disk_gb") or 40), "type": "Dynamic", "attached_to": name}
        world.setdefault("vhdx_disks", []).append(disk)
        world["v2"]["vhdx_disks"] = world["vhdx_disks"]
        return {"ok": True, "message": f"Created VM {name}", "vm": row}

    if action == "hyperv_apply_settings":
        vm = _find_vm(world, payload.get("name") or "")
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        if payload.get("memory_mb") is not None:
            vm["memory_startup_mb"] = int(payload["memory_mb"])
            if vm.get("state") == "Running":
                vm["mem"] = int(payload["memory_mb"])
        if payload.get("processors") is not None:
            vm["processors"] = max(1, int(payload["processors"]))
        if payload.get("vswitch"):
            vm["vswitch"] = payload["vswitch"]
        if payload.get("notes") is not None:
            vm["notes"] = payload["notes"]
        if payload.get("new_name"):
            new_name = str(payload["new_name"]).strip()
            if new_name and new_name != vm["name"] and not _find_vm(world, new_name):
                old = vm["name"]
                vm["name"] = new_name
                for d in world.get("vhdx_disks") or []:
                    if d.get("attached_to") == old:
                        d["attached_to"] = new_name
        vm["settings_applied_at"] = _now()
        return {"ok": True, "message": f"Settings applied for {vm['name']}", "vm": vm}

    if action == "hyperv_connect":
        vm = _find_vm(world, payload.get("name") or "")
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        session = {
            "id": f"console-{vm['name']}-{_now()}",
            "vm": vm["name"],
            "state": vm.get("state"),
            "opened_at": _now(),
            "message": f"Virtual Machine Connection — {vm['name']} ({vm.get('state')})",
        }
        world.setdefault("console_sessions", []).append(session)
        world["v2"]["console_sessions"] = world["console_sessions"][-20:]
        world["console_sessions"] = world["v2"]["console_sessions"]
        return {"ok": True, "message": session["message"], "session": session}

    if action == "hyperv_create_vswitch":
        name = (payload.get("name") or f"vSwitch-{len(world.get('vswitches') or []) + 1}").strip()
        switches = world.setdefault("vswitches", [])
        if any(s.get("name") == name for s in switches):
            return {"ok": False, "error": f"Virtual switch '{name}' already exists"}
        row = {
            "name": name,
            "type": payload.get("type") or "Internal",
            "adapter": payload.get("adapter") or "",
            "notes": payload.get("notes") or "",
        }
        switches.append(row)
        world["v2"]["vswitches"] = switches
        return {"ok": True, "message": f"Created virtual switch {name}", "vswitch": row}

    if action == "hyperv_create_vhdx":
        path = (payload.get("path") or f"C:\\Hyper-V\\disk-{len(world.get('vhdx_disks') or []) + 1}.vhdx").strip()
        disks = world.setdefault("vhdx_disks", [])
        if any(d.get("path") == path for d in disks):
            return {"ok": False, "error": "VHDX already exists"}
        row = {
            "path": path,
            "size_gb": int(payload.get("size_gb") or 40),
            "type": payload.get("type") or "Dynamic",
            "attached_to": payload.get("attached_to") or "",
        }
        disks.append(row)
        world["v2"]["vhdx_disks"] = disks
        vm_name = payload.get("attached_to")
        if vm_name:
            vm = _find_vm(world, vm_name)
            if vm:
                vm["vhd_path"] = path
        return {"ok": True, "message": f"Created VHDX {path}", "disk": row}

    return None
