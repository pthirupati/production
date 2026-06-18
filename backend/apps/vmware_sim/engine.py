"""
Complete in-memory VMware vCenter/ESXi simulator for training labs.
Replicates the full vSphere 6.x/7.x inventory, actions, and validation logic.
"""

from __future__ import annotations

import copy
import random
import time
from typing import Any

_SESSIONS: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(message: str, severity: str = "info", entity: str = "", user: str = "root") -> dict:
    return {"time": _now_iso(), "message": message, "severity": severity, "entity": entity, "user": user}


def _task(name: str, target: str, result: str = "Completed successfully") -> dict:
    t = _now_iso()
    return {
        "id": f"task-{int(time.time())}-{random.randint(1000, 9999)}",
        "name": name,
        "target": target,
        "initiator": "root",
        "queued": t,
        "started": t,
        "result": result,
        "completed": t,
        "status": "success" if result == "Completed successfully" else "error",
    }


def _base_inventory() -> dict:
    return {
        "datacenter": "DC-Prod",
        "cluster": "Cluster-01",
        "cluster_ha": True,
        "cluster_drs": True,
        "cluster_vsan": False,
        "vcenter_version": "7.0.3",
        "vcenter_build": "20328353",

        "hosts": [
            {
                "id": "host-01",
                "name": "esxi-01.fixitlab.local",
                "ip": "192.168.10.11",
                "status": "connected",
                "connection_state": "connected",
                "maintenance": False,
                "version": "7.0.3",
                "build": "20328353",
                "vendor": "VMware, Inc.",
                "model": "VMware Virtual Platform",
                "cpu_model": "Intel(R) Core(TM) i7-10700 CPU @ 2.90GHz",
                "cpu_sockets": 2,
                "cpu_cores_per_socket": 8,
                "cpu_threads": 32,
                "cpu_mhz": 2900,
                "cpu_pct": 42,
                "memory_gb": 64,
                "mem_pct": 58,
                "network_mbps": 120,
                "network_adapters": 4,
                "storage_pct": 61,
                "uptime_seconds": 864000,
                "vms": ["vm-web", "vm-api"],
                "ssh_enabled": True,
                "power_policy": "High Performance",
                "ntp_server": "pool.ntp.org",
                "dns_servers": ["8.8.8.8", "8.8.4.4"],
            },
            {
                "id": "host-02",
                "name": "esxi-02.fixitlab.local",
                "ip": "192.168.10.12",
                "status": "connected",
                "connection_state": "connected",
                "maintenance": False,
                "version": "7.0.3",
                "build": "20328353",
                "vendor": "VMware, Inc.",
                "model": "VMware Virtual Platform",
                "cpu_model": "Intel(R) Xeon(R) E5-2680 v4 @ 2.40GHz",
                "cpu_sockets": 2,
                "cpu_cores_per_socket": 14,
                "cpu_threads": 56,
                "cpu_mhz": 2400,
                "cpu_pct": 35,
                "memory_gb": 128,
                "mem_pct": 49,
                "network_mbps": 88,
                "network_adapters": 4,
                "storage_pct": 54,
                "uptime_seconds": 1728000,
                "vms": ["vm-db", "vm-mon"],
                "ssh_enabled": False,
                "power_policy": "Balanced",
                "ntp_server": "pool.ntp.org",
                "dns_servers": ["8.8.8.8", "8.8.4.4"],
            },
        ],

        "datastores": [
            {
                "id": "ds-01",
                "name": "datastore-ssd-01",
                "type": "VMFS",
                "version": "VMFS 6.82",
                "capacity_gb": 2048,
                "free_gb": 412,
                "accessible": True,
                "hosts": ["host-01", "host-02"],
                "vms": ["vm-web", "vm-api"],
            },
            {
                "id": "ds-02",
                "name": "datastore-nfs-01",
                "type": "NFS",
                "version": "NFS 4.1",
                "capacity_gb": 4096,
                "free_gb": 1900,
                "accessible": True,
                "hosts": ["host-01", "host-02"],
                "vms": ["vm-db", "vm-mon"],
            },
            {
                "id": "ds-03",
                "name": "datastore-local-esxi01",
                "type": "VMFS",
                "version": "VMFS 6.82",
                "capacity_gb": 480,
                "free_gb": 320,
                "accessible": True,
                "hosts": ["host-01"],
                "vms": [],
            },
        ],

        "networks": [
            {
                "id": "net-01",
                "name": "VM Network",
                "vlan": 0,
                "type": "standard",
                "switch": "vSwitch0",
                "hosts": ["host-01", "host-02"],
            },
            {
                "id": "net-02",
                "name": "Prod-VLAN-120",
                "vlan": 120,
                "type": "distributed",
                "switch": "dvSwitch-Prod",
                "hosts": ["host-01", "host-02"],
            },
            {
                "id": "net-03",
                "name": "Mgmt-VLAN-10",
                "vlan": 10,
                "type": "standard",
                "switch": "vSwitch0",
                "hosts": ["host-01", "host-02"],
            },
            {
                "id": "net-04",
                "name": "Storage-VLAN-200",
                "vlan": 200,
                "type": "distributed",
                "switch": "dvSwitch-Storage",
                "hosts": ["host-01", "host-02"],
            },
        ],

        "vswitches": [
            {
                "id": "vsw-01",
                "name": "vSwitch0",
                "type": "standard",
                "ports": 120,
                "mtu": 1500,
                "host": "host-01",
                "uplinks": ["vmnic0", "vmnic1"],
                "portgroups": ["VM Network", "Mgmt-VLAN-10"],
            },
            {
                "id": "vsw-02",
                "name": "dvSwitch-Prod",
                "type": "distributed",
                "version": "7.0.0",
                "ports": 256,
                "mtu": 9000,
                "hosts": ["host-01", "host-02"],
                "uplinks": ["vmnic2", "vmnic3"],
                "portgroups": ["Prod-VLAN-120"],
            },
        ],

        "resource_pools": [
            {
                "id": "rp-prod",
                "name": "Production",
                "parent": "Cluster-01",
                "cpu_shares": "high",
                "mem_shares": "high",
                "cpu_limit_mhz": -1,
                "mem_limit_mb": -1,
            },
            {
                "id": "rp-dev",
                "name": "Development",
                "parent": "Cluster-01",
                "cpu_shares": "normal",
                "mem_shares": "normal",
                "cpu_limit_mhz": 8000,
                "mem_limit_mb": 16384,
            },
        ],

        "vms": [
            {
                "id": "vm-web",
                "name": "web-prod-01",
                "host_id": "host-01",
                "datastore_id": "ds-01",
                "network_id": "net-02",
                "resource_pool_id": "rp-prod",
                "power": "poweredOff",
                "cpu": 4,
                "memory_mb": 8192,
                "disk_gb": 80,
                "guest_os": "Ubuntu Linux (64-bit)",
                "guest_os_version": "Ubuntu 22.04 LTS",
                "ip": "10.20.30.41",
                "hostname": "web-prod-01.fixitlab.local",
                "tools": "notRunning",
                "tools_version": "11333",
                "hardware_version": "vmx-19",
                "annotation": "Production web server",
                "snapshots": [],
                "cpu_pct": 0,
                "mem_pct": 0,
                "disk_io_mbps": 0,
                "net_mbps": 0,
            },
            {
                "id": "vm-api",
                "name": "api-prod-01",
                "host_id": "host-01",
                "datastore_id": "ds-01",
                "network_id": "net-02",
                "resource_pool_id": "rp-prod",
                "power": "poweredOn",
                "cpu": 2,
                "memory_mb": 4096,
                "disk_gb": 40,
                "guest_os": "Red Hat Enterprise Linux 8 (64-bit)",
                "guest_os_version": "RHEL 8.6",
                "ip": "10.20.30.42",
                "hostname": "api-prod-01.fixitlab.local",
                "tools": "ok",
                "tools_version": "11333",
                "hardware_version": "vmx-19",
                "annotation": "REST API service",
                "snapshots": [],
                "cpu_pct": 18,
                "mem_pct": 62,
                "disk_io_mbps": 5,
                "net_mbps": 12,
            },
            {
                "id": "vm-db",
                "name": "db-prod-01",
                "host_id": "host-02",
                "datastore_id": "ds-02",
                "network_id": "net-02",
                "resource_pool_id": "rp-prod",
                "power": "poweredOn",
                "cpu": 8,
                "memory_mb": 16384,
                "disk_gb": 500,
                "guest_os": "Red Hat Enterprise Linux 8 (64-bit)",
                "guest_os_version": "RHEL 8.6",
                "ip": "10.20.30.43",
                "hostname": "db-prod-01.fixitlab.local",
                "tools": "ok",
                "tools_version": "11333",
                "hardware_version": "vmx-19",
                "annotation": "Primary database server",
                "snapshots": [
                    {"id": "snap-001", "name": "pre-upgrade-2024-01", "description": "Before DB upgrade", "created": "2024-01-15T08:00:00Z"},
                ],
                "cpu_pct": 45,
                "mem_pct": 78,
                "disk_io_mbps": 120,
                "net_mbps": 45,
            },
            {
                "id": "vm-mon",
                "name": "monitor-prod-01",
                "host_id": "host-02",
                "datastore_id": "ds-02",
                "network_id": "net-01",
                "resource_pool_id": "rp-prod",
                "power": "poweredOn",
                "cpu": 2,
                "memory_mb": 4096,
                "disk_gb": 100,
                "guest_os": "Ubuntu Linux (64-bit)",
                "guest_os_version": "Ubuntu 22.04 LTS",
                "ip": "10.20.30.44",
                "hostname": "monitor-prod-01.fixitlab.local",
                "tools": "ok",
                "tools_version": "11333",
                "hardware_version": "vmx-19",
                "annotation": "Monitoring and logging",
                "snapshots": [],
                "cpu_pct": 12,
                "mem_pct": 44,
                "disk_io_mbps": 8,
                "net_mbps": 20,
            },
        ],

        "alarms": [],
        "events": [],
        "recent_tasks": [],
        "validation": {"target_vm": "web-prod-01", "require_power": "poweredOn"},
    }


def _apply_scenario_preset(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    events = state["events"]
    tasks = state["recent_tasks"]

    if "guest-powered-off" in slug:
        for vm in state["vms"]:
            if vm["name"] == "web-prod-01":
                vm["power"] = "poweredOff"
                vm["tools"] = "notRunning"
                vm["cpu_pct"] = 0
                vm["mem_pct"] = 0
        events.append(_event("VM web-prod-01 powered off unexpectedly", "warning", "web-prod-01"))
        events.append(_event("Guest heartbeat lost on web-prod-01", "critical", "web-prod-01"))
        state["alarms"].append({"id": "alm-vm-off", "name": "VM powered off", "entity": "web-prod-01",
                                 "severity": "critical", "status": "active", "time": _now_iso()})
        state["validation"] = {"target_vm": "web-prod-01", "require_power": "poweredOn"}

    elif "host-disconnected" in slug:
        state["hosts"][0]["status"] = "disconnected"
        state["hosts"][0]["connection_state"] = "disconnected"
        for vm in state["vms"]:
            if vm["host_id"] == "host-01":
                vm["power"] = "poweredOff"
                vm["tools"] = "notRunning"
        events.append(_event("Host esxi-01.fixitlab.local disconnected from vCenter", "critical", "esxi-01.fixitlab.local"))
        events.append(_event("2 VMs on esxi-01 are inaccessible", "critical", "DC-Prod"))
        state["alarms"].append({"id": "alm-host-dc", "name": "Host disconnected", "entity": "esxi-01.fixitlab.local",
                                 "severity": "critical", "status": "active", "time": _now_iso()})
        state["validation"] = {"require_host_connected": "esxi-01.fixitlab.local"}

    elif "ha-failure" in slug:
        state["cluster_ha"] = False
        state["hosts"][1]["status"] = "notResponding"
        state["hosts"][1]["connection_state"] = "notResponding"
        for vm in state["vms"]:
            if vm["name"] == "web-prod-01":
                vm["power"] = "poweredOff"
        events.append(_event("HA protection disabled on Cluster-01", "critical", "Cluster-01"))
        events.append(_event("Host esxi-02.fixitlab.local not responding", "critical", "esxi-02.fixitlab.local"))
        state["alarms"].append({"id": "alm-ha", "name": "vSphere HA protection disabled", "entity": "Cluster-01",
                                 "severity": "critical", "status": "active", "time": _now_iso()})
        state["validation"] = {"cluster_ha": True, "target_vm": "web-prod-01", "require_power": "poweredOn"}

    elif "datastore-full" in slug:
        state["datastores"][0]["free_gb"] = 2
        state["alarms"].append({"id": "alm-ds-full", "name": "Datastore usage exceeded threshold",
                                 "entity": "datastore-ssd-01", "severity": "critical", "status": "active", "time": _now_iso()})
        events.append(_event("Datastore datastore-ssd-01 at 99.9% capacity", "critical", "datastore-ssd-01"))
        state["validation"] = {"datastore_min_free_gb": 100, "datastore": "datastore-ssd-01"}

    else:
        events.append(_event("vCenter inventory loaded successfully", "info", "vCenter"))
        events.append(_event("All hosts connected and responding", "info", "Cluster-01"))
        tasks.extend([
            _task("Power On Virtual Machine", "api-prod-01"),
            _task("Power On Virtual Machine", "db-prod-01"),
            _task("Power On Virtual Machine", "monitor-prod-01"),
            _task("VMotion", "api-prod-01"),
        ])


def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    if key not in _SESSIONS:
        state = _base_inventory()
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
            "cluster_ha": state.get("cluster_ha", True),
            "cluster_drs": state.get("cluster_drs", True),
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


def _find_ds(state: dict, ds_id: str | None = None, ds_name: str | None = None) -> dict | None:
    for ds in state["datastores"]:
        if ds_id and ds["id"] == ds_id:
            return ds
        if ds_name and ds["name"] == ds_name:
            return ds
    return None


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _SESSIONS.get(str(session_id))
    if not entry:
        return {"ok": False, "error": "Simulation session not found"}
    state = entry["state"]
    events = state.setdefault("events", [])
    tasks = state.setdefault("recent_tasks", [])

    if action == "power_on":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        host = _find_host(state, vm.get("host_id"))
        if host and host.get("status") != "connected":
            return {"ok": False, "error": f"Host {host['name']} is not connected"}
        if host and host.get("maintenance"):
            return {"ok": False, "error": f"Host {host['name']} is in maintenance mode"}
        if vm["power"] == "poweredOn":
            return {"ok": False, "error": f"{vm['name']} is already powered on"}
        vm["power"] = "poweredOn"
        vm["tools"] = "ok"
        vm["cpu_pct"] = random.randint(10, 30)
        vm["mem_pct"] = random.randint(40, 70)
        vm["net_mbps"] = random.randint(5, 30)
        vm["disk_io_mbps"] = random.randint(2, 20)
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != vm["name"]]
        events.append(_event(f"VM {vm['name']} powered on", "info", vm["name"]))
        tasks.insert(0, _task("Power On Virtual Machine", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} powered on successfully"}

    if action == "power_off":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] == "poweredOff":
            return {"ok": False, "error": f"{vm['name']} is already powered off"}
        vm["power"] = "poweredOff"
        vm["tools"] = "notRunning"
        vm["cpu_pct"] = 0
        vm["mem_pct"] = 0
        vm["net_mbps"] = 0
        vm["disk_io_mbps"] = 0
        events.append(_event(f"VM {vm['name']} powered off", "info", vm["name"]))
        tasks.insert(0, _task("Power Off Virtual Machine", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} powered off"}

    if action == "power_off_guest":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] != "poweredOn":
            return {"ok": False, "error": "VM is not running"}
        if vm["tools"] != "ok":
            return {"ok": False, "error": "VMware Tools not running — use Power Off instead"}
        vm["power"] = "poweredOff"
        vm["tools"] = "notRunning"
        vm["cpu_pct"] = 0
        vm["mem_pct"] = 0
        events.append(_event(f"Shut down guest OS on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Shut Down Guest", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} shut down gracefully"}

    if action == "reboot":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] != "poweredOn":
            return {"ok": False, "error": "VM must be powered on to reboot"}
        vm["cpu_pct"] = random.randint(20, 50)
        events.append(_event(f"VM {vm['name']} rebooted", "info", vm["name"]))
        tasks.insert(0, _task("Restart Virtual Machine", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} restarted"}

    if action == "reboot_guest":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] != "poweredOn":
            return {"ok": False, "error": "VM is not running"}
        if vm["tools"] != "ok":
            return {"ok": False, "error": "VMware Tools not running"}
        events.append(_event(f"Restart guest OS on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Restart Guest", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} guest OS restarted"}

    if action == "suspend":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] != "poweredOn":
            return {"ok": False, "error": "VM must be powered on to suspend"}
        vm["power"] = "suspended"
        vm["cpu_pct"] = 0
        vm["net_mbps"] = 0
        events.append(_event(f"VM {vm['name']} suspended", "info", vm["name"]))
        tasks.insert(0, _task("Suspend Virtual Machine", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} suspended"}

    if action == "resume":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] != "suspended":
            return {"ok": False, "error": "VM is not suspended"}
        vm["power"] = "poweredOn"
        vm["cpu_pct"] = random.randint(10, 25)
        events.append(_event(f"VM {vm['name']} resumed", "info", vm["name"]))
        tasks.insert(0, _task("Resume Virtual Machine", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} resumed"}

    if action == "take_snapshot":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        snap_name = payload.get("snapshot_name") or f"snapshot-{int(time.time())}"
        snap = {
            "id": f"snap-{int(time.time())}-{random.randint(100, 999)}",
            "name": snap_name,
            "description": payload.get("description") or "",
            "created": _now_iso(),
        }
        vm.setdefault("snapshots", []).append(snap)
        events.append(_event(f"Snapshot '{snap_name}' created on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Create Snapshot", vm["name"]))
        return {"ok": True, "message": f"Snapshot '{snap_name}' created", "snapshot": snap}

    if action == "delete_snapshot":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        snap_id = payload.get("snapshot_id")
        before = len(vm.get("snapshots", []))
        vm["snapshots"] = [s for s in vm.get("snapshots", []) if s["id"] != snap_id]
        if len(vm["snapshots"]) == before:
            return {"ok": False, "error": "Snapshot not found"}
        events.append(_event(f"Snapshot deleted on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Remove Snapshot", vm["name"]))
        return {"ok": True, "message": "Snapshot deleted"}

    if action == "revert_snapshot":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        snap_id = payload.get("snapshot_id")
        snap = next((s for s in vm.get("snapshots", []) if s["id"] == snap_id), None)
        if not snap:
            return {"ok": False, "error": "Snapshot not found"}
        events.append(_event(f"Reverted {vm['name']} to snapshot '{snap['name']}'", "info", vm["name"]))
        tasks.insert(0, _task("Revert to Snapshot", vm["name"]))
        return {"ok": True, "message": f"Reverted to '{snap['name']}'"}

    if action == "reconnect_host":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        host["status"] = "connected"
        host["connection_state"] = "connected"
        # Restore tools status on VMs but do NOT auto-power-on — ESXi reconnect
        # does not restart VMs; HA or the admin must do that explicitly.
        for vm in state["vms"]:
            if vm["host_id"] == host["id"] and vm.get("tools") == "notRunning":
                vm["tools"] = "guestToolsNotInstalled"
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != host["name"]]
        events.append(_event(f"Host {host['name']} reconnected", "info", host["name"]))
        tasks.insert(0, _task("Reconnect Host", host["name"]))
        return {"ok": True, "message": f"{host['name']} reconnected"}

    if action == "enter_maintenance":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        if host.get("maintenance"):
            return {"ok": False, "error": "Host is already in maintenance mode"}
        host["maintenance"] = True
        events.append(_event(f"Host {host['name']} entered maintenance mode", "warning", host["name"]))
        tasks.insert(0, _task("Enter Maintenance Mode", host["name"]))
        return {"ok": True, "message": f"{host['name']} entered maintenance mode"}

    if action == "exit_maintenance":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        if not host.get("maintenance"):
            return {"ok": False, "error": "Host is not in maintenance mode"}
        host["maintenance"] = False
        events.append(_event(f"Host {host['name']} exited maintenance mode", "info", host["name"]))
        tasks.insert(0, _task("Exit Maintenance Mode", host["name"]))
        return {"ok": True, "message": f"{host['name']} exited maintenance mode"}

    if action == "enable_ha":
        state["cluster_ha"] = True
        for host in state["hosts"]:
            if host["status"] == "notResponding":
                host["status"] = "connected"
                host["connection_state"] = "connected"
        state["alarms"] = [a for a in state.get("alarms", []) if "ha" not in a.get("id", "").lower()]
        events.append(_event("vSphere HA enabled on Cluster-01", "info", "Cluster-01"))
        tasks.insert(0, _task("Enable vSphere HA", "Cluster-01"))
        return {"ok": True, "message": "HA enabled on cluster"}

    if action == "disable_ha":
        state["cluster_ha"] = False
        events.append(_event("vSphere HA disabled on Cluster-01", "warning", "Cluster-01"))
        tasks.insert(0, _task("Disable vSphere HA", "Cluster-01"))
        return {"ok": True, "message": "HA disabled"}

    if action == "enable_drs":
        state["cluster_drs"] = True
        events.append(_event("vSphere DRS enabled on Cluster-01", "info", "Cluster-01"))
        tasks.insert(0, _task("Enable vSphere DRS", "Cluster-01"))
        return {"ok": True, "message": "DRS enabled"}

    if action == "expand_datastore":
        ds_name = payload.get("datastore") or "datastore-ssd-01"
        add_gb = int(payload.get("gb") or 500)
        if add_gb <= 0:
            return {"ok": False, "error": "Expansion size must be a positive number of GB"}
        ds = _find_ds(state, ds_name=ds_name)
        if not ds:
            return {"ok": False, "error": "Datastore not found"}
        ds["capacity_gb"] += add_gb
        ds["free_gb"] += add_gb
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != ds_name]
        events.append(_event(f"Expanded {ds_name} by {add_gb} GB", "info", ds_name))
        tasks.insert(0, _task("Expand Datastore", ds_name))
        return {"ok": True, "message": f"{ds_name} expanded by {add_gb} GB"}

    if action == "migrate_vm":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        target_host = _find_host(state, host_name=payload.get("target_host"))
        if not target_host:
            return {"ok": False, "error": "Target host not found"}
        if target_host.get("status") != "connected":
            return {"ok": False, "error": f"Target host {target_host['name']} is not connected"}
        vm["host_id"] = target_host["id"]
        events.append(_event(f"vMotion: migrated {vm['name']} to {target_host['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Migrate Virtual Machine (VMotion)", vm["name"]))
        return {"ok": True, "message": f"{vm['name']} migrated to {target_host['name']}"}

    if action == "acknowledge_alarm":
        alarm_id = payload.get("alarm_id")
        for alarm in state.get("alarms", []):
            if alarm["id"] == alarm_id:
                alarm["status"] = "acknowledged"
                events.append(_event(f"Alarm '{alarm['name']}' acknowledged", "info", alarm["entity"]))
                return {"ok": True, "message": "Alarm acknowledged"}
        return {"ok": False, "error": "Alarm not found"}

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
        return True, f"Host {name} is connected — validation passed"

    if rules.get("cluster_ha"):
        if not state.get("cluster_ha", True):
            return False, "HA must be enabled on Cluster-01"
        for host in state["hosts"]:
            if host.get("status") not in ("connected",):
                return False, f"Host {host['name']} must be connected for HA"
        return True, "HA is enabled and all hosts connected — validation passed"

    if rules.get("datastore_min_free_gb"):
        ds_name = rules.get("datastore", "datastore-ssd-01")
        ds = _find_ds(state, ds_name=ds_name)
        if not ds:
            return False, f"Datastore {ds_name} not found"
        if ds["free_gb"] < rules["datastore_min_free_gb"]:
            return False, f"{ds_name} needs at least {rules['datastore_min_free_gb']} GB free (currently {ds['free_gb']} GB)"
        return True, f"{ds_name} has {ds['free_gb']} GB free — validation passed"

    target = rules.get("target_vm", "web-prod-01")
    required = rules.get("require_power", "poweredOn")
    vm = _find_vm(state, vm_name=target)
    if not vm:
        return False, f"VM {target} not found"
    if vm.get("power") != required:
        return False, f"{target} must be {required} (currently {vm.get('power')})"
    return True, f"{target} is {required} — validation passed"
