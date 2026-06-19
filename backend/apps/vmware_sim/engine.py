"""
Complete in-memory VMware vCenter/ESXi simulator for training labs.
Replicates the full vSphere 6.x/7.x inventory, actions, and validation logic.
"""

from __future__ import annotations

import copy
import json
import random
import time
from typing import Any

import django
from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL for VMware lab sessions

# Sessions stored in Django cache (Redis in production) for multi-worker safety
# Key: "vmware_session:{session_id}"  Value: JSON-serialized session dict


def _session_key(session_id: str) -> str:
    return f"vmware_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


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


def _vmware_mac(seed: str) -> str:
    """VMware-assigned OUI 00:50:56."""
    h = abs(hash(seed)) & 0xFFFFFF
    return f"00:50:56:{(h >> 16) & 0xFF:02x}:{(h >> 8) & 0xFF:02x}:{h & 0xFF:02x}"


def _scsi_label(controller: int, unit: int) -> str:
    return f"Hard disk {unit + 1}"


def _make_disk(
    disk_id: str,
    capacity_gb: int,
    datastore_id: str,
    controller: int = 0,
    unit: int = 0,
    thin: bool = True,
) -> dict:
    return {
        "id": disk_id,
        "label": _scsi_label(controller, unit),
        "scsi_controller": controller,
        "scsi_unit": unit,
        "scsi_id": f"{controller}:{unit}",
        "controller_type": "LSI Logic SAS",
        "capacity_gb": capacity_gb,
        "datastore_id": datastore_id,
        "thin_provisioned": thin,
        "disk_mode": "independent_persistent",
        "sharing": "sharingNone",
        "uuid": f"6000C29{abs(hash(disk_id)) & 0xFFFFFFFF:08x}",
    }


def _make_nic(
    nic_id: str,
    network_id: str,
    network_name: str,
    mac: str,
    vlan_id: int | None = None,
    connected: bool = True,
    adapter_type: str = "Vmxnet3",
    portgroup_key: str = "",
) -> dict:
    return {
        "id": nic_id,
        "label": f"Network adapter {nic_id.split('-')[-1].replace('nic', '') or '1'}",
        "network_id": network_id,
        "network_name": network_name,
        "mac_address": mac,
        "mac": mac,
        "adapter_type": adapter_type,
        "connected": connected,
        "vlan_id": vlan_id,
        "portgroup_key": portgroup_key or f"dvportgroup-{vlan_id or 0}",
        "direct_path_io": False,
        "wake_on_lan": True,
    }


def _enrich_inventory(state: dict) -> None:
    """Add vSphere-realistic SCSI, MAC, and portgroup metadata."""
    net_by_id = {n["id"]: n for n in state.get("networks", [])}

    for net in state.get("networks", []):
        net.setdefault("vlan_id", net.get("vlan", 0))
        net.setdefault("portgroup_key", f"dvportgroup-{100 + int(net.get('vlan', 0))}")
        net.setdefault("num_ports", 128 if net.get("type") == "distributed" else 64)
        net.setdefault("active_ports", random.randint(4, 24))
        if net.get("type") == "distributed":
            net.setdefault("uplink_teaming", "loadbalance_srcmac")
            net.setdefault("security_promiscuous", False)
            net.setdefault("security_forged_transmits", True)
            net.setdefault("security_mac_changes", True)

    for ds in state.get("datastores", []):
        used_pct = round(((ds["capacity_gb"] - ds["free_gb"]) / ds["capacity_gb"]) * 100, 1) if ds.get("capacity_gb") else 0
        ds.setdefault("used_pct", used_pct)
        ds.setdefault("vmfs_uuid", f"5f8{abs(hash(ds['id'])) & 0xFFFFFFFFFFF:011x}")
        ds.setdefault("extent_name", f"naa.6000C29{abs(hash(ds['id'])) & 0xFFFFFFFF:08x}")
        if used_pct >= 90:
            ds.setdefault("warning", "critical")
        elif used_pct >= 80:
            ds.setdefault("warning", "warning")

    for host in state.get("hosts", []):
        if not host.get("vmnics"):
            host["vmnics"] = [
                {
                    "id": f"{host['id']}-vmnic0",
                    "name": "vmnic0",
                    "mac_address": _vmware_mac(f"{host['id']}-vmnic0"),
                    "pci_id": "0000:04:00.0",
                    "driver": "bnxtnet",
                    "speed_mbps": 10000,
                    "status": "up",
                    "switch": "vSwitch0",
                    "duplex": "full",
                },
                {
                    "id": f"{host['id']}-vmnic1",
                    "name": "vmnic1",
                    "mac_address": _vmware_mac(f"{host['id']}-vmnic1"),
                    "pci_id": "0000:04:00.1",
                    "driver": "bnxtnet",
                    "speed_mbps": 10000,
                    "status": "up",
                    "switch": "vSwitch0",
                    "duplex": "full",
                },
                {
                    "id": f"{host['id']}-vmnic2",
                    "name": "vmnic2",
                    "mac_address": _vmware_mac(f"{host['id']}-vmnic2"),
                    "pci_id": "0000:05:00.0",
                    "driver": "bnxtnet",
                    "speed_mbps": 25000,
                    "status": "up",
                    "switch": "dvSwitch-Prod",
                    "duplex": "full",
                },
                {
                    "id": f"{host['id']}-vmnic3",
                    "name": "vmnic3",
                    "mac_address": _vmware_mac(f"{host['id']}-vmnic3"),
                    "pci_id": "0000:05:00.1",
                    "driver": "bnxtnet",
                    "speed_mbps": 25000,
                    "status": "up",
                    "switch": "dvSwitch-Prod",
                    "duplex": "full",
                },
            ]

    for vm in state.get("vms", []):
        vm.setdefault("scsi_controllers", [
            {"id": "scsi0", "type": "LSI Logic SAS", "shared_bus": "none", "slot": 16},
        ])
        ds_id = vm.get("datastore_id") or "ds-01"
        net_id = vm.get("network_id") or "net-01"
        net = net_by_id.get(net_id, {})
        net_name = net.get("name", "VM Network")
        vlan = net.get("vlan_id", net.get("vlan"))

        if not vm.get("disks"):
            total_gb = int(vm.get("disk_gb") or 40)
            if total_gb > 200:
                boot_gb = min(80, total_gb // 4)
                data_gb = total_gb - boot_gb
                vm["disks"] = [
                    _make_disk(f"{vm['id']}-disk0", boot_gb, ds_id, 0, 0),
                    _make_disk(f"{vm['id']}-disk1", data_gb, ds_id, 0, 1),
                ]
            else:
                vm["disks"] = [_make_disk(f"{vm['id']}-disk0", total_gb, ds_id, 0, 0)]
        else:
            for d in vm["disks"]:
                d.setdefault("scsi_id", f"{d.get('scsi_controller', 0)}:{d.get('scsi_unit', 0)}")
                d.setdefault("uuid", f"6000C29{abs(hash(d['id'])) & 0xFFFFFFFF:08x}")

        vm["disk_gb"] = sum(d.get("capacity_gb", 0) for d in vm["disks"])

        mac = vm.get("mac") or _vmware_mac(vm["id"])
        vm["mac"] = mac
        if not vm.get("nics"):
            vm["nics"] = [
                _make_nic(
                    f"{vm['id']}-nic0",
                    net_id,
                    net_name,
                    mac,
                    vlan_id=vlan,
                    connected=not vm.get("network_disconnected"),
                    portgroup_key=net.get("portgroup_key", ""),
                ),
            ]
        else:
            for nic in vm["nics"]:
                nic.setdefault("mac_address", nic.get("mac") or _vmware_mac(nic["id"]))
                nic.setdefault("mac", nic["mac_address"])
                if nic.get("network_id") and not nic.get("vlan_id"):
                    n = net_by_id.get(nic["network_id"], {})
                    nic["vlan_id"] = n.get("vlan_id", n.get("vlan"))
                    nic.setdefault("network_name", n.get("name", ""))

        if vm.get("nics"):
            primary = vm["nics"][0]
            vm["network_id"] = primary.get("network_id", net_id)
            vm["mac"] = primary.get("mac_address", mac)


def _tick_performance(state: dict) -> None:
    """Advance live-ish performance samples for charts."""
    for host in state.get("hosts", []):
        if host.get("status") == "connected" and not host.get("maintenance"):
            host["cpu_pct"] = max(5, min(95, int((host.get("cpu_pct") or 35) + (random.random() - 0.5) * 5)))
            host["mem_pct"] = max(10, min(95, int((host.get("mem_pct") or 50) + (random.random() - 0.5) * 4)))
            host["storage_pct"] = max(10, min(95, int((host.get("storage_pct") or 40) + (random.random() - 0.5) * 3)))
        hist = host.setdefault("perf_history", {"cpu": [], "mem": []})
        hist["cpu"] = (hist.get("cpu") or [])[-19:] + [host.get("cpu_pct", 0)]
        hist["mem"] = (hist.get("mem") or [])[-19:] + [host.get("mem_pct", 0)]
    for vm in state.get("vms", []):
        if vm.get("power") == "poweredOn":
            vm["cpu_pct"] = max(1, min(99, int((vm.get("cpu_pct") or 20) + (random.random() - 0.5) * 6)))
            vm["mem_pct"] = max(1, min(99, int((vm.get("mem_pct") or 50) + (random.random() - 0.5) * 4)))
            vm["disk_io_mbps"] = max(0, int((vm.get("disk_io_mbps") or 5) + (random.random() - 0.5) * 8))
            vm["net_mbps"] = max(0, int((vm.get("net_mbps") or 10) + (random.random() - 0.5) * 10))
            hist = vm.setdefault("perf_history", {"cpu": [], "mem": [], "disk": [], "net": []})
            hist["cpu"] = (hist.get("cpu") or [])[-19:] + [vm.get("cpu_pct", 0)]
            hist["mem"] = (hist.get("mem") or [])[-19:] + [vm.get("mem_pct", 0)]
            hist["disk"] = (hist.get("disk") or [])[-19:] + [vm.get("disk_io_mbps", 0)]
            hist["net"] = (hist.get("net") or [])[-19:] + [vm.get("net_mbps", 0)]


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
                "datacenter_id": "dc-prod",
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
                "datacenter_id": "dc-prod",
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

        "templates": [
            {
                "id": "tpl-rhel8",
                "name": "rhel8-template",
                "guest_os": "Red Hat Enterprise Linux 8 (64-bit)",
                "guest_os_version": "RHEL 8.6",
                "cpu": 2,
                "memory_mb": 4096,
                "disk_gb": 40,
                "datastore_id": "ds-01",
                "network_id": "net-02",
                "hardware_version": "vmx-19",
            },
            {
                "id": "tpl-ubuntu",
                "name": "ubuntu-2204-template",
                "guest_os": "Ubuntu Linux (64-bit)",
                "guest_os_version": "Ubuntu 22.04 LTS",
                "cpu": 2,
                "memory_mb": 4096,
                "disk_gb": 40,
                "datastore_id": "ds-01",
                "network_id": "net-02",
                "hardware_version": "vmx-19",
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

        "permissions": [
            {"id": "perm-root", "entity": "vCenter", "entity_id": "vcenter", "entity_type": "vcenter",
             "principal": "VSPHERE.LOCAL\\Administrators", "role": "Administrator", "propagate": True},
            {"id": "perm-lab", "entity": "DC-Prod", "entity_id": "dc-prod", "entity_type": "datacenter",
             "principal": "lab_vmware", "role": "Virtual Machine User", "propagate": True},
        ],
        "roles_catalog": [
            "Administrator", "Read Only", "Virtual Machine User", "Virtual Machine Power User",
            "Virtual Machine Administrator", "Network Administrator", "Storage Administrator",
            "No Access",
        ],
        "vsan": {
            "enabled": True,
            "health": "healthy",
            "cluster_status": "online",
            "disk_groups": [
                {
                    "host": "esxi-01.fixitlab.local",
                    "disks": [
                        {"id": "naa.6000C29a1", "tier": "cache", "status": "in_use", "size_tb": 0.4},
                        {"id": "naa.6000C29a2", "tier": "capacity", "status": "in_use", "size_tb": 1.8},
                    ],
                },
            ],
            "unclaimed_disks": [],
            "resync_percent": 100,
            "components_healthy": True,
        },
        "content_library": [
            {
                "id": "cl-fixitlab",
                "name": "FixitLab Content Library",
                "type": "local",
                "items": [
                    {"id": "ovf-tiny-linux", "name": "tiny-linux.ova", "size_mb": 256,
                     "os": "Linux", "description": "Minimal Ubuntu OVA for lab deploy"},
                    {"id": "ovf-win2019", "name": "win2019-template.ova", "size_mb": 4096,
                     "os": "Windows", "description": "Windows Server 2019 template OVA"},
                    {"id": "ovf-rhel8", "name": "rhel8-minimal.ova", "size_mb": 512,
                     "os": "Linux", "description": "RHEL 8 minimal OVA"},
                ],
            },
        ],
        "updates": {
            "vcenter": {"available": False, "current": "7.0.3", "latest": "7.0.3"},
            "hosts": {},
            "vms_tools_pending": [],
        },
        "storage_vmotion_jobs": [],

        "linked_mode": False,
        "datacenters": [
            {
                "id": "dc-prod",
                "name": "DC-Prod",
                "site": "primary",
                "clusters": [{"id": "cluster-01", "name": "Cluster-01", "hosts": ["host-01", "host-02"]}],
            },
            {
                "id": "dc-dr",
                "name": "DC-DR",
                "site": "recovery",
                "linked": False,
                "clusters": [{"id": "cluster-dr", "name": "Cluster-DR", "hosts": ["host-dr-01"]}],
            },
        ],
        "nsx": {
            "enabled": False,
            "manager": "nsx-mgr.fixitlab.local",
            "version": "4.1.0",
            "segments": [
                {"id": "seg-prod", "name": "Prod-Segment", "vlan": 120, "subnets": ["10.20.30.0/24"]},
            ],
            "firewall_rules": [
                {"id": "rule-1", "name": "Allow-SSH", "action": "ALLOW", "source": "any", "dest": "any", "service": "SSH"},
            ],
            "dfw_enabled": True,
            "microseg_missing": False,
        },
        "srm": {
            "enabled": False,
            "site_a": "DC-Prod",
            "site_b": "DC-DR",
            "protection_groups": [],
            "recovery_plans": [],
            "replication_ok": False,
            "last_test": None,
            "failover_ready": False,
        },
        "vami": {
            "appliance": "vCenter Server Appliance",
            "version": "7.0.3",
            "build": "20328353",
            "pending_patches": 0,
            "stage": "idle",
            "stage_progress": 0,
            "last_backup": "2026-06-01T00:00:00Z",
        },
    }


def _apply_scenario_preset(state: dict, scenario_slug: str) -> None:
    from .scenario_presets import apply_vmware_scenario_preset
    apply_vmware_scenario_preset(state, scenario_slug)


def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = _base_inventory()
        _apply_scenario_preset(state, scenario_slug)
        _enrich_inventory(state)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state, "created_at": _now_iso()}
        _save_session(key, entry)
    else:
        _enrich_inventory(entry["state"])
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    _enrich_inventory(state)
    _tick_performance(state)
    vsan = state.get("vsan") or {}
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
            "cluster_vsan": state.get("cluster_vsan", vsan.get("enabled", False)),
            "vsan_health": vsan.get("health", "healthy"),
            "linux_ssh_ok": state.get("linux_ssh_ok", True),
            "jira_incident_updated": state.get("jira_incident_updated", False),
            "customer_reboot_approved": state.get("customer_reboot_approved", False),
            "storage_vmotion_stuck": state.get("storage_vmotion_stuck", False),
            "vcenter_role": state.get("vcenter_role", "Administrator"),
            "linked_mode": state.get("linked_mode", False),
            "nsx_enabled": state.get("nsx", {}).get("enabled", False),
            "srm_enabled": state.get("srm", {}).get("enabled", False),
            "vami_pending": state.get("vami", {}).get("pending_patches", 0),
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


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
    entry = _load_session(str(session_id))
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
        vm.pop("guest_hung", None)
        vm.pop("question_pending", None)
        vm.pop("network_disconnected", None)
        if state.get("linux_ssh_ok") is False:
            state["linux_ssh_ok"] = True
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != vm["name"]]
        events.append(_event(f"VM {vm['name']} powered on", "info", vm["name"]))
        tasks.insert(0, _task("Power On Virtual Machine", vm["name"]))
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{vm['name']} shut down gracefully"}

    if action == "reboot":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] != "poweredOn":
            return {"ok": False, "error": "VM must be powered on to reboot"}
        if state.get("validation", {}).get("require_customer_approval") and not state.get("customer_reboot_approved"):
            return {"ok": False, "error": "Customer must approve reboot before resetting the VM"}
        vm.pop("guest_hung", None)
        vm["tools"] = "ok"
        vm["cpu_pct"] = random.randint(20, 50)
        vm.pop("network_disconnected", None)
        if state.get("linux_ssh_ok") is False:
            state["linux_ssh_ok"] = True
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != vm["name"]]
        events.append(_event(f"VM {vm['name']} rebooted", "info", vm["name"]))
        tasks.insert(0, _task("Restart Virtual Machine", vm["name"]))
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Reverted to '{snap['name']}'"}

    if action == "reconnect_host":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        host["status"] = "connected"
        host["connection_state"] = "connected"
        host.pop("management_network", None)
        # Restore tools status on VMs but do NOT auto-power-on — ESXi reconnect
        # does not restart VMs; HA or the admin must do that explicitly.
        for vm in state["vms"]:
            if vm["host_id"] == host["id"] and vm.get("tools") == "notRunning":
                vm["tools"] = "guestToolsNotInstalled"
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != host["name"]]
        events.append(_event(f"Host {host['name']} reconnected", "info", host["name"]))
        tasks.insert(0, _task("Reconnect Host", host["name"]))
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "HA enabled on cluster"}

    if action == "disable_ha":
        state["cluster_ha"] = False
        events.append(_event("vSphere HA disabled on Cluster-01", "warning", "Cluster-01"))
        tasks.insert(0, _task("Disable vSphere HA", "Cluster-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "HA disabled"}

    if action == "enable_drs":
        state["cluster_drs"] = True
        state["drs_balanced"] = True
        for host in state["hosts"]:
            host["cpu_pct"] = random.randint(28, 45)
        events.append(_event("vSphere DRS enabled on Cluster-01", "info", "Cluster-01"))
        tasks.insert(0, _task("Enable vSphere DRS", "Cluster-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "DRS enabled"}

    if action == "run_drs":
        if not state.get("cluster_drs"):
            return {"ok": False, "error": "DRS must be enabled before running balance"}
        state["drs_balanced"] = True
        for host in state["hosts"]:
            host["cpu_pct"] = random.randint(28, 42)
        events.append(_event("DRS balance completed on Cluster-01", "info", "Cluster-01"))
        tasks.insert(0, _task("Run DRS", "Cluster-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "DRS recommendations applied"}

    if action == "disable_drs":
        state["cluster_drs"] = False
        state["drs_balanced"] = False
        events.append(_event("vSphere DRS disabled on Cluster-01", "info", "Cluster-01"))
        tasks.insert(0, _task("Disable vSphere DRS", "Cluster-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "DRS disabled"}

    if action == "toggle_ssh":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            host = state["hosts"][0]
        host["ssh_enabled"] = not host.get("ssh_enabled", False)
        label = "enabled" if host["ssh_enabled"] else "disabled"
        events.append(_event(f"SSH {label} on {host['name']}", "info", host["name"]))
        tasks.insert(0, _task(f"{'Enable' if host['ssh_enabled'] else 'Disable'} SSH", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"SSH {label} on {host['name']}"}

    if action == "deploy_from_template":
        tpl_name = (payload.get("template_name") or payload.get("name") or "").strip()
        tpl = next((t for t in state.get("templates", []) if t["name"] == tpl_name), None)
        if not tpl:
            return {"ok": False, "error": f"Template '{tpl_name}' not found"}
        vm_name = (payload.get("vm_name") or f"{tpl_name}-deploy-{int(time.time()) % 1000}").strip()
        if any(v["name"] == vm_name for v in state["vms"]):
            return {"ok": False, "error": f"VM '{vm_name}' already exists"}
        host_id = payload.get("host_id") or (state["hosts"][0]["id"] if state["hosts"] else None)
        vm_id = f"vm-{vm_name.lower().replace(' ', '-')}-{int(time.time()) % 100000}"
        vm = {
            "id": vm_id,
            "name": vm_name,
            "host_id": host_id,
            "datastore_id": tpl.get("datastore_id"),
            "network_id": tpl.get("network_id"),
            "resource_pool_id": "rp-prod",
            "power": "poweredOff",
            "cpu": tpl.get("cpu", 2),
            "memory_mb": tpl.get("memory_mb", 4096),
            "disk_gb": tpl.get("disk_gb", 40),
            "guest_os": tpl.get("guest_os"),
            "guest_os_version": tpl.get("guest_os_version", tpl.get("guest_os")),
            "ip": "—",
            "hostname": f"{vm_name}.fixitlab.local",
            "tools": "notRunning",
            "tools_version": "11333",
            "hardware_version": tpl.get("hardware_version", "vmx-19"),
            "annotation": f"Deployed from template {tpl_name}",
            "snapshots": [],
            "cpu_pct": 0,
            "mem_pct": 0,
            "disk_io_mbps": 0,
            "net_mbps": 0,
            "from_template": tpl_name,
        }
        state["vms"].append(vm)
        _enrich_inventory(state)
        events.append(_event(f"Deployed VM {vm_name} from template {tpl_name}", "info", vm_name))
        tasks.insert(0, _task("Deploy Virtual Machine from Template", vm_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Deployed {vm_name} from {tpl_name}", "vm_id": vm_id}

    if action == "convert_to_template":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm.get("power") != "poweredOff":
            return {"ok": False, "error": "VM must be powered off to convert to template"}
        tpl_name = (payload.get("template_name") or f"{vm['name']}-template").strip()
        if any(t["name"] == tpl_name for t in state.get("templates", [])):
            return {"ok": False, "error": f"Template '{tpl_name}' already exists"}
        tpl = {
            "id": f"tpl-{int(time.time()) % 100000}",
            "name": tpl_name,
            "guest_os": vm.get("guest_os"),
            "guest_os_version": vm.get("guest_os_version"),
            "cpu": vm.get("cpu", 2),
            "memory_mb": vm.get("memory_mb", 4096),
            "disk_gb": vm.get("disk_gb", 40),
            "datastore_id": vm.get("datastore_id"),
            "network_id": vm.get("network_id"),
            "hardware_version": vm.get("hardware_version", "vmx-19"),
        }
        state.setdefault("templates", []).append(tpl)
        state["vms"] = [v for v in state["vms"] if v["id"] != vm["id"]]
        events.append(_event(f"Converted {vm['name']} to template {tpl_name}", "info", tpl_name))
        tasks.insert(0, _task("Convert to Template", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Template '{tpl_name}' created"}

    if action == "sync_ntp":
        for host in state["hosts"]:
            host["ntp_synced"] = True
        events.append(_event("NTP synchronized on all ESXi hosts", "info", "Cluster-01"))
        tasks.insert(0, _task("Sync NTP", "Cluster-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "NTP synchronized"}

    if action == "clear_coredump":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            host = state["hosts"][0]
        host["coredump_full"] = False
        events.append(_event(f"Core dump partition cleared on {host['name']}", "info", host["name"]))
        tasks.insert(0, _task("Clear Core Dump", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Core dump partition cleared"}

    if action == "fix_admission_control":
        state["admission_control_failed"] = False
        events.append(_event("HA admission control policy adjusted", "info", "Cluster-01"))
        tasks.insert(0, _task("Configure HA Admission Control", "Cluster-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Admission control resolved"}

    if action == "complete_storage_vmotion":
        state["storage_vmotion_stuck"] = False
        events.append(_event("Storage vMotion completed", "info", "web-prod-01"))
        tasks.insert(0, _task("Storage vMotion", "web-prod-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Storage vMotion completed"}

    if action == "fix_dv_switch_mtu":
        state["dv_switch_mtu_mismatch"] = False
        events.append(_event("Distributed switch MTU corrected", "info", "dvSwitch-Prod"))
        tasks.insert(0, _task("Fix MTU", "dvSwitch-Prod"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "MTU mismatch fixed"}

    if action == "create_portgroup":
        pg_name = (payload.get("name") or state.get("portgroup_missing") or "Prod-VLAN-200").strip()
        if not pg_name:
            return {"ok": False, "error": "Port group name required"}
        if any(n.get("name") == pg_name for n in state.get("networks", [])):
            return {"ok": False, "error": f"Port group '{pg_name}' already exists"}
        net_id = f"net-{pg_name.lower().replace(' ', '-')}"
        state.setdefault("networks", []).append({
            "id": net_id, "name": pg_name, "type": "portgroup",
            "vlan": payload.get("vlan") or 200, "switch": "dvSwitch-Prod",
        })
        state.pop("portgroup_missing", None)
        events.append(_event(f"Created port group {pg_name}", "info", "dvSwitch-Prod"))
        tasks.insert(0, _task("Create Port Group", pg_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Port group '{pg_name}' created"}

    if action == "resolve_vmotion":
        state["vmotion_failed"] = False
        events.append(_event("vMotion issue resolved for api-prod-01", "info", "api-prod-01"))
        tasks.insert(0, _task("Migrate Virtual Machine (VMotion)", "api-prod-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "vMotion resolved"}

    if action == "convert_template":
        state["template_convert_failed"] = False
        events.append(_event("Template converted to VM successfully", "info", "web-template"))
        tasks.insert(0, _task("Convert Template", "web-template"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Template converted"}

    if action == "renew_vcenter_cert":
        state["vcenter_cert_expired"] = False
        events.append(_event("vCenter certificate renewed", "info", "vCenter"))
        tasks.insert(0, _task("Renew Certificate", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Certificate renewed"}

    if action == "expand_vcenter_db":
        state["vcenter_db_full"] = False
        events.append(_event("vCenter database partition expanded", "info", "vCenter"))
        tasks.insert(0, _task("Expand Database", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Database expanded"}

    if action == "unlock_sso":
        state["vcenter_sso_locked"] = False
        events.append(_event("SSO administrator account unlocked", "info", "vCenter"))
        tasks.insert(0, _task("Unlock SSO Account", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "SSO account unlocked"}

    if action == "upgrade_tools":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["tools"] = "ok"
        vm["tools_version"] = "12389"
        events.append(_event(f"VMware Tools upgraded on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Upgrade VMware Tools", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Tools upgraded on {vm['name']}"}

    if action == "answer_question":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm.pop("question_pending", None)
        events.append(_event(f"Pending question answered on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Answer VM Question", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Question cleared"}

    if action == "connect_network":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm.pop("network_disconnected", None)
        vm["net_mbps"] = random.randint(5, 30)
        events.append(_event(f"Network adapter connected on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Connect Network", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Network connected on {vm['name']}"}

    if action == "reduce_cpu_contention":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["cpu_ready_pct"] = random.randint(2, 8)
        events.append(_event(f"CPU contention reduced on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Migrate Virtual Machine (VMotion)", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "CPU ready time improved"}

    if action == "mark_jira_updated":
        state["jira_incident_updated"] = True
        events.append(_event("Incident ticket updated with console findings", "info", "Jira"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Jira incident updated"}

    if action == "confirm_customer_reboot":
        if state.get("validation", {}).get("require_jira_updated") and not state.get("jira_incident_updated"):
            return {"ok": False, "error": "Update Jira with findings before requesting customer reboot"}
        state["customer_reboot_approved"] = True
        events.append(_event("Customer approved server reboot", "info", "web-prod-01"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Customer reboot approved"}

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
        _save_session(str(session_id), entry)
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
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{vm['name']} migrated to {target_host['name']}"}

    if action == "acknowledge_alarm":
        alarm_id = payload.get("alarm_id")
        for alarm in state.get("alarms", []):
            if alarm["id"] == alarm_id:
                alarm["status"] = "acknowledged"
                events.append(_event(f"Alarm '{alarm['name']}' acknowledged", "info", alarm["entity"]))
                _save_session(str(session_id), entry)
                return {"ok": True, "message": "Alarm acknowledged"}
        return {"ok": False, "error": "Alarm not found"}

    if action == "create_vm":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "VM name is required"}
        if any(v["name"] == name for v in state["vms"]):
            return {"ok": False, "error": f"A VM named '{name}' already exists"}
        host_id = payload.get("host_id") or (state["hosts"][0]["id"] if state["hosts"] else None)
        ds_id = payload.get("datastore_id") or (state["datastores"][0]["id"] if state["datastores"] else None)
        net_id = payload.get("network_id") or (state["networks"][0]["id"] if state["networks"] else None)
        guest_os = payload.get("guest_os") or "Ubuntu Linux (64-bit)"
        cpu = max(1, int(payload.get("cpu") or 2))
        mem_mb = max(512, int(payload.get("memory_mb") or 4096))
        disk_gb = max(10, int(payload.get("disk_gb") or 40))
        vm_id = f"vm-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}"
        vm = {
            "id": vm_id,
            "name": name,
            "host_id": host_id,
            "datastore_id": ds_id,
            "network_id": net_id,
            "resource_pool_id": "rp-prod",
            "power": "poweredOff",
            "cpu": cpu,
            "memory_mb": mem_mb,
            "disk_gb": disk_gb,
            "guest_os": guest_os,
            "guest_os_version": guest_os,
            "ip": "—",
            "hostname": f"{name}.fixitlab.local",
            "tools": "notRunning",
            "tools_version": "11333",
            "hardware_version": "vmx-19",
            "annotation": payload.get("annotation") or "",
            "snapshots": [],
            "cpu_pct": 0,
            "mem_pct": 0,
            "disk_io_mbps": 0,
            "net_mbps": 0,
        }
        state["vms"].append(vm)
        _enrich_inventory(state)
        host = _find_host(state, host_id=host_id)
        if host:
            host.setdefault("vms", []).append(vm_id)
        ds = _find_ds(state, ds_id=ds_id)
        if ds:
            ds.setdefault("vms", []).append(vm_id)
            disk_used = disk_gb
            if ds["free_gb"] >= disk_used:
                ds["free_gb"] -= disk_used
        events.append(_event(f"Created VM {name}", "info", name))
        tasks.insert(0, _task("Create Virtual Machine", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"VM '{name}' created", "vm_id": vm_id}

    if action == "delete_vm":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] == "poweredOn":
            return {"ok": False, "error": f"Cannot delete a powered-on VM — shut it down first"}
        vm_id = vm["id"]
        vm_name = vm["name"]
        disk_gb = vm.get("disk_gb", 0)
        ds = _find_ds(state, ds_id=vm.get("datastore_id"))
        if ds:
            ds["free_gb"] = min(ds["capacity_gb"], ds["free_gb"] + disk_gb)
            ds["vms"] = [v for v in ds.get("vms", []) if v != vm_id]
        host = _find_host(state, host_id=vm.get("host_id"))
        if host:
            host["vms"] = [v for v in host.get("vms", []) if v != vm_id]
        state["vms"] = [v for v in state["vms"] if v["id"] != vm_id]
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != vm_name]
        events.append(_event(f"VM {vm_name} deleted from inventory", "warning", vm_name))
        tasks.insert(0, _task("Delete Virtual Machine", vm_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"VM '{vm_name}' deleted"}

    if action == "edit_vm":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm["power"] == "poweredOn" and (payload.get("cpu") or payload.get("memory_mb")):
            return {"ok": False, "error": "Power off the VM before editing CPU or memory"}
        changed = []
        if payload.get("cpu"):
            vm["cpu"] = max(1, int(payload["cpu"]))
            changed.append("CPU")
        if payload.get("memory_mb"):
            vm["memory_mb"] = max(512, int(payload["memory_mb"]))
            changed.append("Memory")
        if payload.get("annotation") is not None:
            vm["annotation"] = payload["annotation"]
            changed.append("Annotation")
        if payload.get("name"):
            new_name = payload["name"].strip()
            if new_name and new_name != vm["name"]:
                if any(v["name"] == new_name for v in state["vms"]):
                    return {"ok": False, "error": f"A VM named '{new_name}' already exists"}
                old_name = vm["name"]
                vm["name"] = new_name
                events.append(_event(f"VM renamed from {old_name} to {new_name}", "info", new_name))
                changed.append("Name")
        if not changed:
            return {"ok": False, "error": "No changes specified"}
        events.append(_event(f"VM {vm['name']} configuration updated: {', '.join(changed)}", "info", vm["name"]))
        tasks.insert(0, _task("Edit Virtual Machine Settings", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{vm['name']} updated: {', '.join(changed)}"}

    if action == "clone_vm":
        src = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not src:
            return {"ok": False, "error": "Source VM not found"}
        clone_name = (payload.get("clone_name") or f"{src['name']}-clone").strip()
        if any(v["name"] == clone_name for v in state["vms"]):
            return {"ok": False, "error": f"VM named '{clone_name}' already exists"}
        import copy as _copy
        clone = _copy.deepcopy(src)
        clone["id"] = f"vm-clone-{int(time.time()) % 100000}"
        clone["name"] = clone_name
        clone["power"] = "poweredOff"
        clone["cpu_pct"] = 0
        clone["mem_pct"] = 0
        clone["net_mbps"] = 0
        clone["disk_io_mbps"] = 0
        clone["snapshots"] = []
        clone["ip"] = "—"
        clone["tools"] = "notRunning"
        for field in ("disks", "nics", "scsi_controllers", "snapshots"):
            clone.pop(field, None)
        state["vms"].append(clone)
        _enrich_inventory(state)
        ds = _find_ds(state, ds_id=src.get("datastore_id"))
        if ds and ds["free_gb"] >= src.get("disk_gb", 40):
            ds["free_gb"] -= src.get("disk_gb", 40)
            ds.setdefault("vms", []).append(clone["id"])
        events.append(_event(f"Cloned {src['name']} → {clone_name}", "info", clone_name))
        tasks.insert(0, _task("Clone Virtual Machine", clone_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"VM cloned as '{clone_name}'", "vm_id": clone["id"]}

    if action == "add_disk":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        add_gb = max(10, int(payload.get("size_gb") or 100))
        _enrich_inventory(state)
        disks = vm.setdefault("disks", [])
        next_unit = max((d.get("scsi_unit", 0) for d in disks), default=-1) + 1
        disk_id = f"{vm['id']}-disk{next_unit}"
        ds_id = vm.get("datastore_id") or (state["datastores"][0]["id"] if state["datastores"] else "")
        new_disk = _make_disk(disk_id, add_gb, ds_id, 0, next_unit)
        disks.append(new_disk)
        vm["disk_gb"] = sum(d.get("capacity_gb", 0) for d in disks)
        ds = _find_ds(state, ds_id=ds_id)
        if ds and ds["free_gb"] >= add_gb:
            ds["free_gb"] -= add_gb
        events.append(_event(f"Added {add_gb} GB disk ({new_disk['scsi_id']}) to {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Add Hard Disk", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Added {add_gb} GB disk at SCSI 0:{next_unit}"}

    if action == "change_network":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        net_id = payload.get("network_id")
        net = next((n for n in state["networks"] if n["id"] == net_id), None)
        if not net:
            return {"ok": False, "error": "Network not found"}
        vm["network_id"] = net_id
        vm.pop("network_disconnected", None)
        vm["net_mbps"] = random.randint(5, 30)
        if vm.get("nics"):
            vm["nics"][0]["network_id"] = net_id
            vm["nics"][0]["network_name"] = net["name"]
            vm["nics"][0]["vlan_id"] = net.get("vlan_id", net.get("vlan"))
            vm["nics"][0]["portgroup_key"] = net.get("portgroup_key", "")
            vm["nics"][0]["connected"] = True
        events.append(_event(f"Changed {vm['name']} network to {net['name']} (VLAN {net.get('vlan_id', net.get('vlan', 0))})", "info", vm["name"]))
        tasks.insert(0, _task("Change Network Adapter", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{vm['name']} moved to network '{net['name']}'"}

    if action == "vmotion_precheck":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        target = _find_host(state, host_name=payload.get("target_host"))
        if not vm or not target:
            return {"ok": False, "error": "VM or target host not found"}
        checks = [
            {"name": "Compatibility", "passed": target.get("status") == "connected", "detail": "CPU compatibility OK"},
            {"name": "Network", "passed": True, "detail": "All port groups available on destination"},
            {"name": "Storage", "passed": True, "detail": "Shared datastore accessible"},
            {"name": "Resources", "passed": not target.get("maintenance"), "detail": "Host not in maintenance"},
        ]
        return {"ok": True, "checks": checks, "ready": all(c["passed"] for c in checks)}

    if action == "start_storage_vmotion":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        target_ds = _find_ds(state, ds_id=payload.get("target_datastore_id"), ds_name=payload.get("target_datastore"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if not target_ds:
            return {"ok": False, "error": "Target datastore not found"}
        if vm.get("power") != "poweredOff" and vm.get("power") != "poweredOn":
            return {"ok": False, "error": "VM must be powered on or off for storage vMotion"}
        job_id = f"svm-{int(time.time()) % 100000}"
        job = {
            "id": job_id, "vm_id": vm["id"], "vm_name": vm["name"],
            "source_datastore_id": vm.get("datastore_id"),
            "target_datastore_id": target_ds["id"],
            "progress": 0, "status": "running",
        }
        state.setdefault("storage_vmotion_jobs", []).insert(0, job)
        state["storage_vmotion_stuck"] = False
        events.append(_event(f"Storage vMotion started for {vm['name']} → {target_ds['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Relocate Virtual Machine", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Storage vMotion started", "job_id": job_id, "progress": 0}

    if action == "advance_storage_vmotion":
        job_id = payload.get("job_id")
        jobs = state.get("storage_vmotion_jobs") or []
        job = next((j for j in jobs if j["id"] == job_id), jobs[0] if jobs else None)
        if not job:
            return {"ok": False, "error": "No storage vMotion job in progress"}
        job["progress"] = min(100, job.get("progress", 0) + int(payload.get("step", 25)))
        if job["progress"] >= 100:
            job["status"] = "completed"
            vm = _find_vm(state, job.get("vm_id"))
            if vm:
                vm["datastore_id"] = job["target_datastore_id"]
            state["storage_vmotion_stuck"] = False
            events.append(_event(f"Storage vMotion completed for {job['vm_name']}", "info", job["vm_name"]))
            tasks.insert(0, _task("Storage vMotion completed", job["vm_name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "progress": job["progress"], "status": job["status"]}

    if action == "deploy_ovf":
        item_name = (payload.get("ovf_name") or payload.get("name") or "").strip()
        lib = state.get("content_library") or []
        item = None
        for cl in lib:
            item = next((i for i in cl.get("items", []) if i["name"] == item_name), None)
            if item:
                break
        if not item:
            return {"ok": False, "error": f"OVF/OVA '{item_name}' not found in content library"}
        vm_name = (payload.get("vm_name") or item["name"].replace(".ova", "").replace(".ovf", "")).strip()
        if any(v["name"] == vm_name for v in state["vms"]):
            return {"ok": False, "error": f"VM '{vm_name}' already exists"}
        host_id = payload.get("host_id") or state["hosts"][0]["id"]
        is_windows = "windows" in item.get("os", "").lower() or "win" in item_name.lower()
        vm_id = f"vm-{vm_name.lower().replace(' ', '-')}-{int(time.time()) % 100000}"
        vm = {
            "id": vm_id, "name": vm_name, "host_id": host_id,
            "datastore_id": payload.get("datastore_id") or "ds-01",
            "network_id": payload.get("network_id") or "net-02",
            "resource_pool_id": "rp-prod", "power": "poweredOff",
            "cpu": 2, "memory_mb": 4096, "disk_gb": 40,
            "guest_os": "Microsoft Windows Server 2019 (64-bit)" if is_windows else "Ubuntu Linux (64-bit)",
            "guest_os_version": "Windows Server 2019" if is_windows else "Ubuntu 22.04 LTS",
            "ip": "—", "hostname": f"{vm_name}.fixitlab.local",
            "tools": "notRunning", "tools_version": "11333", "hardware_version": "vmx-19",
            "annotation": f"Deployed from OVF {item_name}", "snapshots": [],
            "cpu_pct": 0, "mem_pct": 0, "disk_io_mbps": 0, "net_mbps": 0,
            "from_ovf": item_name,
        }
        state["vms"].append(vm)
        _enrich_inventory(state)
        events.append(_event(f"Deployed {vm_name} from OVF {item_name}", "info", vm_name))
        tasks.insert(0, _task("Deploy OVF Template", vm_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Deployed {vm_name} from {item_name}", "vm_id": vm_id}

    if action == "assign_permission":
        entity = payload.get("entity") or payload.get("entity_name") or "DC-Prod"
        principal = (payload.get("principal") or payload.get("user") or "").strip()
        role = (payload.get("role") or "Read Only").strip()
        if not principal:
            return {"ok": False, "error": "User or group name required"}
        perm = {
            "id": f"perm-{int(time.time()) % 100000}",
            "entity": entity, "entity_id": payload.get("entity_id", entity.lower()),
            "entity_type": payload.get("entity_type", "inventory"),
            "principal": principal, "role": role,
            "propagate": bool(payload.get("propagate", True)),
        }
        state.setdefault("permissions", []).append(perm)
        if state.get("permission_missing") and principal == "lab_vmware":
            state["permission_missing"] = False
        events.append(_event(f"Assigned {role} to {principal} on {entity}", "info", entity))
        tasks.insert(0, _task("Assign Role", entity))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{role} assigned to {principal}"}

    if action == "revoke_permission":
        perm_id = payload.get("permission_id")
        perms = state.get("permissions") or []
        before = len(perms)
        state["permissions"] = [p for p in perms if p.get("id") != perm_id]
        if len(state["permissions"]) == before:
            return {"ok": False, "error": "Permission not found"}
        events.append(_event("Permission revoked", "info", payload.get("entity", "inventory")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Permission revoked"}

    if action == "set_vcenter_role":
        role = (payload.get("role") or "Administrator").strip()
        if role not in state.get("roles_catalog", []):
            return {"ok": False, "error": f"Unknown role: {role}"}
        state["vcenter_role"] = role
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Session role set to {role}"}

    if action == "update_dvs":
        dvs_name = (payload.get("dvs_name") or payload.get("name") or "dvSwitch-Prod").strip()
        dvs = next((v for v in state.get("vswitches", []) if v["name"] == dvs_name), None)
        if not dvs:
            return {"ok": False, "error": f"Distributed switch '{dvs_name}' not found"}
        if "mtu" in payload:
            dvs["mtu"] = int(payload["mtu"])
            if int(payload["mtu"]) == 9000:
                state["dv_switch_mtu_mismatch"] = False
        if payload.get("uplinks"):
            dvs["uplinks"] = payload["uplinks"]
        if payload.get("teaming"):
            dvs["teaming"] = payload["teaming"]
        if payload.get("portgroups"):
            dvs["portgroups"] = payload["portgroups"]
        events.append(_event(f"Updated distributed switch {dvs_name}", "info", dvs_name))
        tasks.insert(0, _task("Reconfigure Distributed Switch", dvs_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{dvs_name} updated"}

    if action == "claim_vsan_disk":
        disk_id = payload.get("disk_id")
        vsan = state.setdefault("vsan", {})
        unclaimed = vsan.get("unclaimed_disks") or []
        if disk_id:
            disk = next((d for d in unclaimed if d["id"] == disk_id), None)
            if not disk:
                return {"ok": False, "error": f"Disk {disk_id} not found or already claimed"}
            unclaimed.remove(disk)
            vsan.setdefault("disk_groups", []).append({
                "host": disk.get("host", "esxi-02.fixitlab.local"),
                "disks": [{**disk, "tier": "capacity", "status": "in_use"}],
            })
        state["vsan_disk_unclaimed"] = len(unclaimed) > 0
        vsan["unclaimed_disks"] = unclaimed
        vsan["health"] = "healthy" if not unclaimed else "warning"
        vsan["components_healthy"] = not unclaimed
        events.append(_event("vSAN disk claimed", "info", disk_id or "esxi-02"))
        tasks.insert(0, _task("Claim vSAN Disk", disk_id or "disk"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "vSAN disk claimed"}

    if action == "rescan_hba":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            host = state["hosts"][0]
        host["hba_rescan_done"] = True
        events.append(_event(f"Rescan all HBAs on {host['name']}", "info", host["name"]))
        tasks.insert(0, _task("Rescan Storage", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "HBA rescan completed"}

    if action == "guest_rescan_scsi":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["guest_disk_rescanned"] = True
        vm["guest_disk_visible"] = True
        events.append(_event(f"SCSI rescan completed in guest {vm['name']}", "info", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Guest disk visible after SCSI rescan"}

    if action == "guest_format_disk":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if not vm.get("guest_disk_visible") and vm.get("guest_disk_hidden"):
            return {"ok": False, "error": "Disk not visible — rescan SCSI bus first"}
        vm["guest_disk_formatted"] = True
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Filesystem created on new disk"}

    if action == "guest_mount_disk":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if not vm.get("guest_disk_formatted"):
            return {"ok": False, "error": "Create a filesystem before mounting"}
        vm["guest_disk_mounted"] = True
        vm.pop("guest_disk_hidden", None)
        events.append(_event(f"Data disk mounted in {vm['name']}", "info", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Disk mounted successfully"}

    if action == "guest_load_module":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["kernel_module_missing"] = False
        events.append(_event(f"Kernel module loaded in {vm['name']}", "info", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Kernel module loaded"}

    if action == "guest_fix_boot":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["boot_failure"] = False
        events.append(_event(f"Guest boot issue resolved on {vm['name']}", "info", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Boot failure resolved"}

    if action == "check_updates":
        target = payload.get("target") or "all"
        pending = []
        if target in ("host", "all"):
            for host in state["hosts"]:
                cnt = host.get("pending_patches", 0)
                if cnt:
                    pending.append(f"{host['name']}: {cnt} ESXi patches")
        if target in ("vm", "all"):
            for vm in state["vms"]:
                if vm.get("tools") == "old":
                    pending.append(f"{vm['name']}: VMware Tools update")
        state.setdefault("updates", {})["last_check"] = _now_iso()
        _save_session(str(session_id), entry)
        return {"ok": True, "pending": pending, "message": "No updates" if not pending else f"{len(pending)} update(s) available"}

    if action == "install_updates":
        target_type = payload.get("target_type") or "host"
        if target_type == "host":
            host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
            if host:
                host["pending_patches"] = 0
                host.pop("patch_reboot_required", None)
        elif target_type == "vm":
            vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
            if vm:
                vm["tools"] = "ok"
                vm.pop("tools_outdated", None)
        events.append(_event("Updates installed", "info", target_type))
        tasks.insert(0, _task("Install Updates", target_type))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Updates installed successfully"}

    if action == "install_tools_update":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        if vm.get("power") != "poweredOn":
            return {"ok": False, "error": "VM must be powered on to upgrade tools"}
        vm["tools"] = "ok"
        vm["tools_version"] = "12389"
        events.append(_event(f"VMware Tools upgraded on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Upgrade VMware Tools", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"VMware Tools upgraded on {vm['name']}"}

    if action == "enable_linked_mode":
        state["linked_mode"] = True
        for dc in state.get("datacenters", []):
            if dc.get("site") == "recovery":
                dc["linked"] = True
        if not any(h["id"] == "host-dr-01" for h in state["hosts"]):
            state["hosts"].append({
                "id": "host-dr-01", "name": "esxi-dr-01.fixitlab.local", "ip": "192.168.20.11",
                "status": "connected", "connection_state": "connected", "maintenance": False,
                "version": "7.0.3", "build": "20328353", "vendor": "VMware, Inc.",
                "model": "VMware Virtual Platform", "cpu_model": "Intel(R) Xeon", "cpu_sockets": 2,
                "cpu_cores_per_socket": 8, "cpu_mhz": 2900, "memory_gb": 128, "cpu_pct": 22,
                "mem_pct": 38, "storage_pct": 45, "ssh_enabled": False, "ntp_synced": True,
                "dns_servers": ["8.8.8.8"], "ntp_server": "pool.ntp.org", "power_policy": "balanced",
                "network_adapters": 4, "datacenter_id": "dc-dr",
            })
        events.append(_event("Enhanced linked mode enabled — DC-DR linked to vCenter", "info", "vCenter"))
        tasks.insert(0, _task("Enable Linked Mode", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Linked mode enabled — DC-DR visible"}

    if action == "enable_nsx":
        nsx = state.setdefault("nsx", {})
        nsx["enabled"] = True
        nsx["microseg_missing"] = False
        events.append(_event("NSX-T manager connected", "info", nsx.get("manager", "NSX")))
        tasks.insert(0, _task("Configure NSX-T", "NSX"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "NSX-T enabled"}

    if action == "create_nsx_firewall_rule":
        nsx = state.setdefault("nsx", {})
        rule = {
            "id": f"rule-{int(time.time()) % 100000}",
            "name": payload.get("name", "Lab-Rule"),
            "action": payload.get("action", "ALLOW"),
            "source": payload.get("source", "any"),
            "dest": payload.get("dest", "any"),
            "service": payload.get("service", "ANY"),
        }
        nsx.setdefault("firewall_rules", []).append(rule)
        nsx["microseg_missing"] = False
        events.append(_event(f"NSX DFW rule '{rule['name']}' created", "info", "NSX"))
        tasks.insert(0, _task("Create DFW Rule", rule["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Firewall rule {rule['name']} created"}

    if action == "configure_srm":
        srm = state.setdefault("srm", {})
        srm["enabled"] = True
        srm["replication_ok"] = True
        srm["protection_groups"] = [{"name": "PG-Prod", "vms": ["web-prod-01", "api-prod-01"]}]
        srm["recovery_plans"] = [{"name": "RP-Prod-DR", "status": "ready"}]
        events.append(_event("SRM site pairing configured", "info", "SRM"))
        tasks.insert(0, _task("Configure SRM", "SRM"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "SRM replication configured"}

    if action == "srm_test_recovery":
        srm = state.setdefault("srm", {})
        if not srm.get("enabled"):
            return {"ok": False, "error": "SRM must be configured first"}
        srm["last_test"] = _now_iso()
        srm["failover_ready"] = True
        events.append(_event("SRM recovery plan test completed successfully", "info", "SRM"))
        tasks.insert(0, _task("Test Recovery Plan", "RP-Prod-DR"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Recovery plan test passed"}

    if action == "srm_failover":
        srm = state.setdefault("srm", {})
        if not srm.get("failover_ready") and not srm.get("replication_ok"):
            return {"ok": False, "error": "Run recovery plan test before failover"}
        srm["failover_executed"] = True
        for vm in state["vms"]:
            if vm["name"] in ("web-prod-01", "api-prod-01"):
                vm["host_id"] = "host-dr-01"
                vm["datacenter_id"] = "dc-dr"
        events.append(_event("SRM planned migration executed to DC-DR", "critical", "SRM"))
        tasks.insert(0, _task("Execute Failover", "RP-Prod-DR"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Failover to DC-DR completed"}

    if action == "vami_check_patches":
        vami = state.setdefault("vami", {})
        pending = vami.get("pending_patches", 0)
        patches = []
        if pending:
            patches = [f"VCenter patch {vami.get('version')} build+1"] * pending
        _save_session(str(session_id), entry)
        return {"ok": True, "pending": patches, "count": pending}

    if action == "vami_stage_patches":
        vami = state.setdefault("vami", {})
        vami["stage"] = "staging"
        vami["stage_progress"] = 0
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Patches staging started", "progress": 0}

    if action == "vami_advance_stage":
        vami = state.setdefault("vami", {})
        if vami.get("stage") not in ("staging", "installing"):
            return {"ok": False, "error": "No VAMI operation in progress"}
        vami["stage_progress"] = min(100, vami.get("stage_progress", 0) + int(payload.get("step", 25)))
        if vami["stage_progress"] >= 100:
            vami["stage"] = "installing"
            vami["stage_progress"] = 0
        _save_session(str(session_id), entry)
        return {"ok": True, "stage": vami["stage"], "progress": vami["stage_progress"]}

    if action == "vami_install_patches":
        vami = state.setdefault("vami", {})
        vami["pending_patches"] = 0
        vami["stage"] = "idle"
        vami["stage_progress"] = 100
        state["vcenter_cert_expired"] = False
        events.append(_event("vCenter VAMI patches installed — appliance reboot may be required", "info", "VAMI"))
        tasks.insert(0, _task("Install VAMI Patches", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "VAMI patches installed successfully"}

    if action == "create_vm_wizard":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "VM name required"}
        if any(v["name"] == name for v in state["vms"]):
            return {"ok": False, "error": f"VM '{name}' already exists"}
        vm_id = f"vm-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}"
        vm = {
            "id": vm_id, "name": name,
            "host_id": payload.get("host_id") or state["hosts"][0]["id"],
            "datastore_id": payload.get("datastore_id") or "ds-01",
            "network_id": payload.get("network_id") or "net-02",
            "resource_pool_id": payload.get("resource_pool_id") or "rp-prod",
            "power": payload.get("power", "poweredOff"),
            "cpu": int(payload.get("cpu", 2)),
            "memory_mb": int(payload.get("memory_mb", 4096)),
            "disk_gb": int(payload.get("disk_gb", 40)),
            "guest_os": payload.get("guest_os", "Ubuntu Linux (64-bit)"),
            "guest_os_version": payload.get("guest_os_version", payload.get("guest_os", "Linux")),
            "ip": "—", "hostname": f"{name}.fixitlab.local",
            "tools": "notRunning", "tools_version": "11333", "hardware_version": "vmx-19",
            "annotation": payload.get("annotation", "Created via New VM wizard"),
            "snapshots": [], "cpu_pct": 0, "mem_pct": 0, "disk_io_mbps": 0, "net_mbps": 0,
            "wizard_created": True,
            "cd_dvd": payload.get("cd_dvd", "Client Device"),
            "firmware": payload.get("firmware", "BIOS"),
        }
        state["vms"].append(vm)
        _enrich_inventory(state)
        events.append(_event(f"Created VM {name} via New Virtual Machine wizard", "info", name))
        tasks.insert(0, _task("Create Virtual Machine", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"VM '{name}' created", "vm_id": vm_id}

    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_vmware_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    rules = state.get("validation") or {}

    if rules.get("require_host_connected"):
        name = rules["require_host_connected"]
        host = _find_host(state, host_name=name)
        if not host or host.get("status") != "connected" or host.get("connection_state") != "connected":
            return False, f"Host {name} must be connected"
        if host.get("management_network") == "down":
            return False, f"Management network on {name} is down"

    if rules.get("require_ntp_synced"):
        for host in state["hosts"]:
            if not host.get("ntp_synced", True):
                return False, f"NTP not synced on {host['name']}"

    if rules.get("require_coredump_cleared"):
        for host in state["hosts"]:
            if host.get("coredump_full"):
                return False, f"Core dump partition full on {host['name']}"

    if rules.get("cluster_ha") is True:
        if not state.get("cluster_ha", False):
            return False, "HA must be enabled on Cluster-01"
        for host in state["hosts"]:
            if host.get("status") not in ("connected",):
                return False, f"Host {host['name']} must be connected for HA"

    if rules.get("admission_control_ok"):
        if state.get("admission_control_failed"):
            return False, "HA admission control is blocking VM power-on"

    if rules.get("cluster_drs") is True:
        if not state.get("cluster_drs", False):
            return False, "DRS must be enabled on Cluster-01"

    if rules.get("drs_balanced") is True:
        if not state.get("drs_balanced", False):
            return False, "Cluster hosts are not balanced — enable or run DRS"

    if rules.get("datastore_min_free_gb"):
        ds_name = rules.get("datastore", "datastore-ssd-01")
        ds = _find_ds(state, ds_name=ds_name)
        if not ds:
            return False, f"Datastore {ds_name} not found"
        if ds["free_gb"] < rules["datastore_min_free_gb"]:
            return False, (
                f"{ds_name} needs at least {rules['datastore_min_free_gb']} GB free "
                f"(currently {ds['free_gb']} GB)"
            )

    if rules.get("vsan_disks_claimed"):
        if state.get("vsan_disk_unclaimed"):
            return False, "vSAN disks must be claimed on all hosts"

    if rules.get("storage_vmotion_complete"):
        if state.get("storage_vmotion_stuck"):
            return False, "Storage vMotion is still stuck — cancel or complete it"

    if rules.get("dv_switch_mtu_fixed"):
        if state.get("dv_switch_mtu_mismatch"):
            return False, "Distributed switch MTU mismatch not fixed"

    if rules.get("portgroup_created"):
        pg = rules["portgroup_created"]
        if not any(n.get("name") == pg for n in state.get("networks", [])):
            return False, f"Port group {pg} must be created"

    if rules.get("vmotion_resolved"):
        if state.get("vmotion_failed"):
            return False, "vMotion failure not resolved"

    if rules.get("template_converted"):
        if state.get("template_convert_failed"):
            return False, "Template conversion not completed"

    if rules.get("vcenter_cert_renewed"):
        if state.get("vcenter_cert_expired"):
            return False, "vCenter certificate must be renewed"

    if rules.get("vcenter_db_expanded"):
        if state.get("vcenter_db_full"):
            return False, "vCenter database partition must be expanded"

    if rules.get("vcenter_sso_unlocked"):
        if state.get("vcenter_sso_locked"):
            return False, "SSO administrator account is locked"

    if rules.get("require_jira_updated"):
        if not state.get("jira_incident_updated"):
            return False, "Update the Jira incident with console findings before rebooting"

    if rules.get("require_customer_approval"):
        if not state.get("customer_reboot_approved"):
            return False, "Customer must approve reboot before proceeding"

    if rules.get("require_ssh_ok"):
        if not state.get("linux_ssh_ok", True):
            return False, "Linux server SSH is not reachable — fix the guest VM first"

    target = rules.get("target_vm")
    if target:
        vm = _find_vm(state, vm_name=target)
        if not vm:
            return False, f"VM {target} not found"

        if rules.get("require_power"):
            if vm.get("power") != rules["require_power"]:
                return False, f"{target} must be {rules['require_power']} (currently {vm.get('power')})"

        if rules.get("require_guest_responsive"):
            if vm.get("guest_hung"):
                return False, f"{target} guest OS is hung — verify in console and reboot"

        if rules.get("require_question_cleared"):
            if vm.get("question_pending"):
                return False, f"{target} has a pending question that must be answered"

        if rules.get("require_network_connected"):
            if vm.get("network_disconnected"):
                return False, f"{target} network adapter is disconnected"

        if rules.get("require_tools"):
            if vm.get("tools") != rules["require_tools"]:
                return False, f"{target} VMware Tools must be {rules['require_tools']}"

        if rules.get("min_disk_gb"):
            if vm.get("disk_gb", 0) < rules["min_disk_gb"]:
                return False, f"{target} disk must be at least {rules['min_disk_gb']} GB"

        if rules.get("max_snapshots") is not None:
            if len(vm.get("snapshots", [])) > rules["max_snapshots"]:
                return False, f"{target} has too many snapshots — consolidate or delete"

        if rules.get("max_cpu_ready_pct") is not None:
            if vm.get("cpu_ready_pct", 0) > rules["max_cpu_ready_pct"]:
                return False, f"{target} CPU ready time is too high — migrate or reduce load"

        if rules.get("guest_disk_mounted"):
            if not vm.get("guest_disk_mounted"):
                return False, f"{target} data disk not mounted — rescan SCSI, create filesystem, and mount"

        if rules.get("boot_resolved"):
            if vm.get("boot_failure"):
                return False, f"{target} guest OS boot failure not resolved"

        if rules.get("kernel_module_loaded"):
            if vm.get("kernel_module_missing"):
                return False, f"{target} required kernel module not loaded"

    if rules.get("host_patches_installed"):
        for host in state["hosts"]:
            if host.get("pending_patches", 0) > 0:
                return False, f"Install pending patches on {host['name']}"

    if rules.get("permission_assigned"):
        if state.get("permission_missing") and len(state.get("permissions", [])) < 3:
            return False, "Assign required vCenter permission to lab operator"

    if rules.get("ovf_deployed"):
        if not any(v.get("from_ovf") for v in state.get("vms", [])):
            return False, "Deploy a VM from the content library OVF"

    if rules.get("linked_mode_enabled"):
        if not state.get("linked_mode"):
            return False, "Enable Enhanced Linked Mode to attach DC-DR"

    if rules.get("nsx_microseg_configured"):
        nsx = state.get("nsx", {})
        if not nsx.get("enabled") or nsx.get("microseg_missing"):
            return False, "Configure NSX-T and create required DFW micro-segmentation rule"

    if rules.get("srm_recovery_tested"):
        srm = state.get("srm", {})
        if not srm.get("last_test") and not srm.get("failover_ready"):
            return False, "Configure SRM and run recovery plan test"

    if rules.get("vami_patches_installed"):
        if state.get("vami", {}).get("pending_patches", 0) > 0:
            return False, "Install pending vCenter VAMI patches"

    if rules.get("wizard_vm_created"):
        if not any(v.get("wizard_created") for v in state.get("vms", [])):
            return False, "Create a VM using the New Virtual Machine wizard"

    if rules:
        return True, "Validation passed — issue resolved"

    target = rules.get("target_vm", "web-prod-01")
    vm = _find_vm(state, vm_name=target)
    if not vm:
        return False, f"VM {target} not found"
    if vm.get("power") != "poweredOn":
        return False, f"{target} must be poweredOn (currently {vm.get('power')})"
    return True, f"{target} is poweredOn — validation passed"
