"""
Complete in-memory VMware vCenter/ESXi simulator for training labs.
Replicates the full vSphere 6.x/7.x inventory, actions, and validation logic.
"""

from __future__ import annotations

import copy
import json
import random
import re
import time
from typing import Any

import django
from django.core.cache import cache

from .vsphere_v2_facades import apply_v2_action, ensure_v2, seed_v2

SESSION_TTL = 7200  # 2-hour TTL for VMware lab sessions

# Sessions stored in Django cache (Redis in production) for multi-worker safety
# Key: "vmware_session:{session_id}"  Value: JSON-serialized session dict


def _session_key(session_id: str) -> str:
    return f"vmware_session:{session_id}"


def _cross_tech_config(scenario_slug: str | None) -> dict | None:
    """Bridge config for a cross-technology scenario, or None. Import is local so
    the VMware app keeps no hard dependency on the labs simulation package."""
    try:
        from apps.labs.provisioner.simulation.vmware_bridge import cross_tech_config
        return cross_tech_config(scenario_slug or "")
    except Exception:
        return None


def _k8s_node_for_vm(cfg: dict | None, vm: dict) -> str | None:
    """The k8s node name a VMware VM represents in a cross-tech k8s lab, or None.

    A VM carries an explicit `k8s_node` (set by the preset / create payload); we
    also fall back to the scenario's configured worker VM ↔ node mapping so that a
    VM the learner creates with the expected name still binds to the node.
    """
    if not cfg or cfg.get("tech") != "kubernetes":
        return None
    node = vm.get("k8s_node")
    if node:
        return node
    if vm.get("name") and vm.get("name") == cfg.get("vmware_vm"):
        return cfg.get("k8s_node")
    return None


def _bridge_k8s_node(entry: dict, vm: dict, kind: str) -> None:
    """Map a VMware VM power action onto k8s node state via the shared bridge.

    kind: "online" (power on / create), "offline" (power off), "reset" (reset).
    No-op unless this is a k8s cross-tech scenario and the VM is the worker node.
    """
    cfg = _cross_tech_config(entry.get("scenario_slug"))
    node = _k8s_node_for_vm(cfg, vm)
    if not node:
        return
    sid = str(entry.get("session_id") or "")
    if not sid:
        return
    try:
        from apps.labs.provisioner.simulation import vmware_bridge as br
        if kind == "online":
            br.record_k8s_node_online(sid, node)
        elif kind == "offline":
            br.record_k8s_node_offline(sid, node)
        elif kind == "reset":
            br.record_k8s_node_reset(sid, node)
    except Exception:
        pass


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


def _mask_license_key(key: str) -> str:
    """vSphere shows the last block only: XXXXX-XXXXX-XXXXX-XXXXX-9MKH4."""
    if not key:
        return ""
    parts = key.split("-")
    if len(parts) <= 1:
        return key
    return "-".join(["XXXXX"] * (len(parts) - 1) + [parts[-1]])


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
    cable_connected: bool = True,
    ip_mode: str = "dhcp",
    guest_ip: str = "",
    guest_prefix: int = 24,
    guest_gateway: str = "",
    net_mode: str = "bridged",
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
        # Layer-2 cable/link state — distinct from `connected` (the "Connect at
        # power on" checkbox). A NIC can be connected in vSphere yet have its
        # cable pulled at the virtual switch, and vice-versa.
        "cable_connected": cable_connected,
        # Layer-3 guest addressing the terminal renders from (ip a / ifconfig).
        "ip_mode": ip_mode,          # dhcp | static | none
        "guest_ip": guest_ip,
        "guest_prefix": guest_prefix,
        "guest_gateway": guest_gateway,
        "net_mode": net_mode,        # bridged | nat | host-only
    }


def _make_cdrom(
    cdrom_id: str,
    iso_path: str = "",
    connected: bool = False,
    label: str = "",
) -> dict:
    """A virtual CD/DVD drive. `iso_path` empty means the drive is present but
    has no media mounted (Client Device); a non-empty path is a mounted ISO."""
    return {
        "id": cdrom_id,
        "label": label or "CD/DVD drive 1",
        "device_type": "datastore_iso" if iso_path else "client_device",
        "iso_path": iso_path,
        "connected": bool(connected and iso_path),
        "connect_at_power_on": bool(connected),
        "controller": "IDE 0",
    }


def _enrich_inventory(state: dict) -> None:
    """Add vSphere-realistic SCSI, MAC, and portgroup metadata."""
    net_by_id = {n["id"]: n for n in state.get("networks", [])}

    # Licensing: expose a masked key for the Configure ▸ Licensing panel without
    # ever shipping the full key to the client.
    lic = state.get("licensing")
    if isinstance(lic, dict) and lic.get("license_key"):
        lic["license_key_masked"] = _mask_license_key(lic["license_key"])

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
        cap = ds.get("capacity_gb") or 0
        used_pct = round(((cap - ds["free_gb"]) / cap) * 100, 1) if cap else 0
        free_pct = round((ds["free_gb"] / cap) * 100, 1) if cap else 100
        # Recompute every refresh so the warning tracks current free space
        # (datastores fill/empty as VMs are created, cloned, or deleted).
        ds["used_pct"] = used_pct
        ds["free_pct"] = free_pct
        ds.setdefault("vmfs_uuid", f"5f8{abs(hash(ds['id'])) & 0xFFFFFFFFFFF:011x}")
        ds.setdefault("extent_name", f"naa.6000C29{abs(hash(ds['id'])) & 0xFFFFFFFF:08x}")
        # Capacity health: <5% free is critical, <15% free is a warning banner.
        if free_pct < 5:
            ds["warning"] = "critical"
        elif free_pct < 15:
            ds["warning"] = "warning"
        else:
            ds["warning"] = None

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
        # VM Options defaults (boot, firewall, power behaviour) so the expanded
        # Edit Settings → VM Options tab always has values to render.
        vm.setdefault("boot_delay_ms", 0)
        vm.setdefault("boot_firmware", vm.get("firmware", "BIOS"))
        vm.setdefault("boot_order", ["disk", "network", "cdrom"])
        vm.setdefault("enter_bios_on_boot", False)
        vm.setdefault("firewall_enabled", True)
        vm.setdefault("reboot_power_action", "restart")  # restart | shutdown | poweroff
        vm.setdefault("resume_behavior", "powerOn")
        # vmware_tools_status mirrors `tools` but is the field the UI binds the
        # "Upgrade VMware Tools" button to (current | upgradeAvailable | notRunning).
        if not vm.get("vmware_tools_status"):
            if vm.get("tools") == "ok":
                vm["vmware_tools_status"] = "current"
            elif vm.get("tools") in ("old", "upgradeAvailable"):
                vm["vmware_tools_status"] = "upgradeAvailable"
            else:
                vm["vmware_tools_status"] = "notRunning"
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
        vm_ip = vm.get("ip") if str(vm.get("ip") or "").count(".") == 3 else ""
        vm_gw = ".".join(vm_ip.split(".")[:3] + ["1"]) if vm_ip else ""
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
                    cable_connected=not vm.get("network_disconnected"),
                    guest_ip=vm_ip,
                    guest_gateway=vm_gw,
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
                # Backfill the L2/L3 fields on NICs created before these existed.
                nic.setdefault("cable_connected", nic.get("connected", True))
                nic.setdefault("ip_mode", "dhcp")
                nic.setdefault("guest_prefix", 24)
                nic.setdefault("net_mode", "bridged")
                nic.setdefault("guest_gateway", "")

        if vm.get("nics"):
            primary = vm["nics"][0]
            vm["network_id"] = primary.get("network_id", net_id)
            vm["mac"] = primary.get("mac_address", mac)
            # The primary NIC's guest IP tracks the VM's `ip` field so the
            # terminal renders the same address the vSphere summary shows.
            if vm_ip and not primary.get("guest_ip"):
                primary["guest_ip"] = vm_ip
            if vm_gw and not primary.get("guest_gateway"):
                primary["guest_gateway"] = vm_gw

        # Every VM has a virtual CD/DVD drive (empty / Client Device by default).
        if not vm.get("cdroms"):
            vm["cdroms"] = [_make_cdrom(f"{vm['id']}-cdrom0")]


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

        # vApps (multi-tier app containers) live under a cluster/host.
        "vapps": [],
        # Datastore clusters (SDRS pods) group datastores for Storage DRS.
        "datastore_clusters": [],
        # Inventory folders (host/vm/storage/network) created under a datacenter.
        "folders": [],

        # Host/vCenter licensing surfaced in the Configure ▸ Licensing panel.
        "licensing": {
            "product": "VMware vSphere 7 Enterprise Plus",
            "license_key": "0J63K-4FH1M-A8XY2-0AHL2-9MKH4",
            "expiry": "2027-03-31",
            "capacity": "Unlimited CPUs",
            "used": "4 of unlimited CPUs",
            "features": [
                "vSphere Distributed Switch",
                "vSphere DRS",
                "vSphere High Availability",
                "vMotion / Storage vMotion",
                "Fault Tolerance",
                "Distributed Resource Scheduler",
                "Host Profiles",
            ],
        },

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
        # vSphere SSO users for the Users & Roles panel. lab_vmware is the
        # default training operator (password lab_vmware@123).
        "vcenter_users": [
            {"id": "user-admin", "username": "administrator@vsphere.local", "role": "Administrator",
             "enabled": True, "builtin": True, "last_login": "Today 09:14"},
            {"id": "user-lab", "username": "lab_vmware", "role": "Virtual Machine User",
             "enabled": True, "builtin": True, "last_login": "Today 08:40"},
        ],
        # Alarm/alert definitions surfaced in the Alarms config panel.
        "alarm_definitions": [
            {"id": "alarmdef-cpu", "name": "Virtual machine CPU usage", "entity_type": "VirtualMachine",
             "metric": "cpu.usage", "operator": ">", "threshold": 90, "severity": "warning", "enabled": True},
            {"id": "alarmdef-mem", "name": "Virtual machine memory usage", "entity_type": "VirtualMachine",
             "metric": "mem.usage", "operator": ">", "threshold": 90, "severity": "warning", "enabled": True},
            {"id": "alarmdef-ds", "name": "Datastore usage on disk", "entity_type": "Datastore",
             "metric": "disk.used", "operator": ">", "threshold": 85, "severity": "critical", "enabled": True},
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
        **seed_v2(),
    }


def _apply_scenario_preset(state: dict, scenario_slug: str) -> None:
    from .scenario_presets import apply_vmware_scenario_preset
    apply_vmware_scenario_preset(state, scenario_slug)


def _consume_guest_power(session_id: str, state: dict) -> bool:
    """Unified-server model (terminal → VMware): drain a power event the learner
    triggered from the guest console (`reboot`/`poweroff`) and reflect it on the
    target VM, so the VMware VM tile follows what happened inside the OS. Returns
    True when the VM state changed. Best-effort; never raises into a state read."""
    try:
        from apps.labs.provisioner.simulation.vmware_bridge import consume_guest_power
        action = consume_guest_power(str(session_id))
    except Exception:
        return False
    if not action:
        return False
    target = (state.get("validation", {}) or {}).get("target_vm")
    vm = _find_vm(state, vm_name=target) if target else None
    if vm is None and state.get("vms"):
        vm = state["vms"][0]
    if vm is None:
        return False
    events = state.setdefault("events", [])
    tasks = state.setdefault("recent_tasks", [])
    if action == "reboot":
        vm["power"] = "poweredOn"
        vm["tools"] = "ok"
        vm.pop("guest_hung", None)
        vm.pop("network_disconnected", None)
        vm["boot_pending"] = True
        events.append(_event(f"Guest OS on {vm['name']} rebooted (from console)", "info", vm["name"]))
        tasks.insert(0, _task("Guest Reboot", vm["name"]))
    else:  # poweroff
        vm["power"] = "poweredOff"
        vm["tools"] = "notRunning"
        vm["cpu_pct"] = 0
        vm["mem_pct"] = 0
        vm["net_mbps"] = 0
        vm["disk_io_mbps"] = 0
        vm.pop("boot_pending", None)
        events.append(_event(f"Guest OS on {vm['name']} shut down (from console)", "info", vm["name"]))
        tasks.insert(0, _task("Guest Shutdown", vm["name"]))
    return True


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
        # Refresh slug when the lab opens VMware with ?scenario=… — otherwise
        # hot-add bridge writes are gated on an empty/stale scenario_slug from
        # the first _ensure_session call (often before the lab slug was known).
        if scenario_slug and entry.get("scenario_slug") != scenario_slug:
            entry["scenario_slug"] = scenario_slug
        _enrich_inventory(entry["state"])
        _consume_guest_power(key, entry["state"])
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    if set(entry["state"].keys()) != keys_before:
        _save_session(str(session_id), entry)
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
            "vcenter_users_total": len(state.get("vcenter_users", [])),
            "alarm_definitions_total": len(state.get("alarm_definitions", [])),
            "resource_pools_total": len(state.get("resource_pools", [])),
            "vapps_total": len(state.get("vapps", [])),
            "datastore_clusters_total": len(state.get("datastore_clusters", [])),
            "folders_total": len(state.get("folders", [])),
            # Datastores at/under the low-free-space threshold, for tree badges + banners.
            "datastores_low_space": [
                {"name": d["name"], "id": d["id"], "free_pct": d.get("free_pct", 100), "warning": d.get("warning")}
                for d in state.get("datastores", []) if d.get("warning")
            ],
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
        return {"ok": False, "error": "vCenter session not found"}
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
        # The guest was just powered on this session, so the next console open
        # should replay the full POST/GRUB/boot sequence (consumed by the UI).
        vm["boot_pending"] = True
        vm.pop("guest_hung", None)
        vm.pop("question_pending", None)
        vm.pop("network_disconnected", None)
        if state.get("linux_ssh_ok") is False:
            state["linux_ssh_ok"] = True
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != vm["name"]]
        events.append(_event(f"VM {vm['name']} powered on", "info", vm["name"]))
        tasks.insert(0, _task("Power On Virtual Machine", vm["name"]))
        # Cross-tech k8s: powering on a worker-node VM makes its k8s node join Ready.
        _bridge_k8s_node(entry, vm, "online")
        try:
            from apps.labs.provisioner.simulation.vmware_bridge import record_hypervisor_reboot
            record_hypervisor_reboot(str(session_id))
        except Exception:
            pass
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
        # A powered-off guest is not "freshly booted"; the next power-on sets it.
        vm.pop("boot_pending", None)
        events.append(_event(f"VM {vm['name']} powered off", "info", vm["name"]))
        tasks.insert(0, _task("Power Off Virtual Machine", vm["name"]))
        # Cross-tech k8s: powering off a worker-node VM removes that node.
        _bridge_k8s_node(entry, vm, "offline")
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
        # A reset/restart replays the full boot sequence on the next console open.
        vm["boot_pending"] = True
        vm.pop("network_disconnected", None)
        if state.get("linux_ssh_ok") is False:
            state["linux_ssh_ok"] = True
        state["alarms"] = [a for a in state.get("alarms", []) if a.get("entity") != vm["name"]]
        events.append(_event(f"VM {vm['name']} rebooted", "info", vm["name"]))
        tasks.insert(0, _task("Restart Virtual Machine", vm["name"]))
        # Cross-tech: resetting a hung guest from VMware makes the Linux terminal
        # responsive again (server-hung-needs-vmware-reset).
        cfg = _cross_tech_config(entry.get("scenario_slug"))
        if cfg and cfg.get("action") == "reset":
            from apps.labs.provisioner.simulation.vmware_bridge import record_vm_reset
            record_vm_reset(str(session_id))
        # Cross-tech k8s: resetting a hung worker-node VM recovers its NotReady node.
        _bridge_k8s_node(entry, vm, "reset")
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
        vm["boot_pending"] = True
        vm["tools"] = "ok"
        events.append(_event(f"Restart guest OS on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Restart Guest", vm["name"]))
        try:
            from apps.labs.provisioner.simulation.vmware_bridge import record_hypervisor_reboot
            record_hypervisor_reboot(str(session_id))
        except Exception:
            pass
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{vm['name']} guest OS restarted — terminal reconnecting"}

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
        existing = vm.setdefault("snapshots", [])
        # Accept either the vSphere-style `snapshot_name` or a plain `name`; fall
        # back to a sequential "Snapshot N" (matching the vSphere default) rather
        # than a per-second timestamp so two snapshots taken in the same wall
        # clock second no longer collide on an identical name.
        snap_name = (payload.get("snapshot_name") or payload.get("name") or "").strip()
        if not snap_name:
            snap_name = f"Snapshot {len(existing) + 1}"
        # If the chosen name already exists on this VM, disambiguate so the
        # Snapshot Manager tree never shows two indistinguishable entries.
        if any(s.get("name") == snap_name for s in existing):
            base = snap_name
            n = 2
            while any(s.get("name") == f"{base} ({n})" for s in existing):
                n += 1
            snap_name = f"{base} ({n})"
        snap = {
            "id": f"snap-{int(time.time())}-{random.randint(100, 999)}",
            "name": snap_name,
            "description": payload.get("description") or "",
            "created": _now_iso(),
        }
        existing.append(snap)
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

    if action == "consolidate_snapshots":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        count = len(vm.get("snapshots", []))
        vm["snapshots"] = []
        vm["snapshot_consolidated"] = True
        vm.pop("needs_consolidation", None)
        events.append(_event(f"Consolidated snapshots on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Consolidate Snapshots", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Consolidated {count} snapshot{'s' if count != 1 else ''} on {vm['name']}"}

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

    if action in ("create_portgroup", "create_network"):
        pg_name = (payload.get("name") or state.get("portgroup_missing") or "Prod-VLAN-200").strip()
        if not pg_name:
            return {"ok": False, "error": "Port group name required"}
        if any(n.get("name") == pg_name for n in state.get("networks", [])):
            return {"ok": False, "error": f"Port group '{pg_name}' already exists"}
        # Switch the port group lives on; default to a distributed switch for
        # scenario compatibility, but honour an explicit switch from the UI.
        switch = (payload.get("switch") or "dvSwitch-Prod").strip()
        sw = next((v for v in state.get("vswitches", []) if v.get("name") == switch), None)
        # vlan may legitimately be 0 ("All"), so only fall back when the key is absent.
        vlan_raw = payload.get("vlan", payload.get("vlan_id"))
        vlan = int(vlan_raw) if vlan_raw not in (None, "") else 200
        net_id = f"net-{pg_name.lower().replace(' ', '-')}-{int(time.time()) % 100000}"
        pg_type = "distributed" if (sw and sw.get("type") == "distributed") else "standard"
        net = {
            "id": net_id, "name": pg_name, "type": pg_type,
            "vlan": vlan, "vlan_id": vlan, "switch": switch,
            "hosts": [h["id"] for h in state.get("hosts", [])],
        }
        state.setdefault("networks", []).append(net)
        if sw is not None:
            sw.setdefault("portgroups", []).append(pg_name)
        state.pop("portgroup_missing", None)
        _enrich_inventory(state)
        events.append(_event(f"Created port group {pg_name} (VLAN {vlan})", "info", switch))
        tasks.insert(0, _task("Create Port Group", pg_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Port group '{pg_name}' (VLAN {vlan}) created", "network_id": net_id}

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

    if action in ("upgrade_tools", "upgrade_vmware_tools"):
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm["tools"] = "ok"
        vm["tools_version"] = "12389"
        vm["vmware_tools_status"] = "current"
        events.append(_event(f"VMware Tools upgraded on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Upgrade VMware Tools", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"VMware Tools upgraded to current on {vm['name']}"}

    if action == "edit_vm_options":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        changed = []
        if "boot_delay_ms" in payload:
            vm["boot_delay_ms"] = max(0, int(payload["boot_delay_ms"]))
            changed.append("boot delay")
        if "boot_firmware" in payload:
            fw = str(payload["boot_firmware"]).upper()
            vm["boot_firmware"] = "EFI" if fw == "EFI" else "BIOS"
            changed.append("firmware")
        if "boot_order" in payload and isinstance(payload["boot_order"], list):
            vm["boot_order"] = [str(d) for d in payload["boot_order"]]
            changed.append("boot order")
        if "enter_bios_on_boot" in payload:
            vm["enter_bios_on_boot"] = bool(payload["enter_bios_on_boot"])
            changed.append("force BIOS setup")
        if "firewall_enabled" in payload:
            vm["firewall_enabled"] = bool(payload["firewall_enabled"])
            changed.append("guest firewall")
        if "reboot_power_action" in payload:
            act = str(payload["reboot_power_action"])
            vm["reboot_power_action"] = act if act in ("restart", "shutdown", "poweroff") else "restart"
            changed.append("reboot behaviour")
        if "resume_behavior" in payload:
            vm["resume_behavior"] = str(payload["resume_behavior"]) or "powerOn"
            changed.append("resume behaviour")
        if not changed:
            return {"ok": False, "error": "No VM options changed"}
        events.append(_event(f"VM options updated on {vm['name']}: {', '.join(changed)}", "info", vm["name"]))
        tasks.insert(0, _task("Edit Virtual Machine Options", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{vm['name']} VM options updated: {', '.join(changed)}"}

    if action == "create_vcenter_user":
        username = (payload.get("username") or "").strip()
        password = (payload.get("password") or "").strip()
        role = (payload.get("role") or "Read Only").strip()
        if not username:
            return {"ok": False, "error": "Username is required"}
        if not password or len(password) < 6:
            return {"ok": False, "error": "Password must be at least 6 characters"}
        users = state.setdefault("vcenter_users", [])
        if any(u["username"].lower() == username.lower() for u in users):
            return {"ok": False, "error": f"User '{username}' already exists"}
        if role not in state.get("roles_catalog", []):
            return {"ok": False, "error": f"Unknown role: {role}"}
        user = {
            "id": f"user-{int(time.time()) % 100000}",
            "username": username, "role": role, "enabled": True,
            "builtin": False, "last_login": "Never",
        }
        users.append(user)
        # Creating the lab operator also satisfies permission-style scenarios.
        if state.get("user_missing") and username == "lab_vmware":
            state["user_missing"] = False
        events.append(_event(f"Created vCenter user {username} with role {role}", "info", "SSO"))
        tasks.insert(0, _task("Create User", username))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"User '{username}' created with role {role}", "user_id": user["id"]}

    if action == "reset_user_password":
        user_id = payload.get("user_id")
        username = payload.get("username")
        new_password = (payload.get("password") or payload.get("new_password") or "").strip()
        if not new_password or len(new_password) < 6:
            return {"ok": False, "error": "New password must be at least 6 characters"}
        users = state.get("vcenter_users", [])
        user = next((u for u in users if u["id"] == user_id or u["username"] == username), None)
        if not user:
            return {"ok": False, "error": "User not found"}
        user["password_reset_at"] = _now_iso()
        events.append(_event(f"Password reset for {user['username']}", "info", "SSO"))
        tasks.insert(0, _task("Reset Password", user["username"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Password reset for {user['username']}"}

    if action == "assign_user_role":
        user_id = payload.get("user_id")
        username = payload.get("username")
        role = (payload.get("role") or "").strip()
        if role not in state.get("roles_catalog", []):
            return {"ok": False, "error": f"Unknown role: {role}"}
        users = state.get("vcenter_users", [])
        user = next((u for u in users if u["id"] == user_id or u["username"] == username), None)
        if not user:
            return {"ok": False, "error": "User not found"}
        user["role"] = role
        events.append(_event(f"Assigned role {role} to {user['username']}", "info", "SSO"))
        tasks.insert(0, _task("Assign Role", user["username"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{user['username']} is now {role}"}

    if action == "delete_vcenter_user":
        user_id = payload.get("user_id")
        username = payload.get("username")
        users = state.get("vcenter_users", [])
        user = next((u for u in users if u["id"] == user_id or u["username"] == username), None)
        if not user:
            return {"ok": False, "error": "User not found"}
        if user.get("builtin"):
            return {"ok": False, "error": "Cannot delete a built-in user"}
        state["vcenter_users"] = [u for u in users if u["id"] != user["id"]]
        events.append(_event(f"Deleted vCenter user {user['username']}", "warning", "SSO"))
        tasks.insert(0, _task("Delete User", user["username"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"User '{user['username']}' deleted"}

    if action == "create_alarm_definition":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Alarm name is required"}
        defs = state.setdefault("alarm_definitions", [])
        alarm_def = {
            "id": f"alarmdef-{int(time.time()) % 100000}",
            "name": name,
            "entity_type": payload.get("entity_type") or "VirtualMachine",
            "metric": payload.get("metric") or "cpu.usage",
            "operator": payload.get("operator") or ">",
            "threshold": int(payload.get("threshold") or 90),
            "severity": payload.get("severity") or "warning",
            "enabled": bool(payload.get("enabled", True)),
        }
        defs.append(alarm_def)
        events.append(_event(f"Alarm definition '{name}' created", "info", "vCenter"))
        tasks.insert(0, _task("Create Alarm Definition", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Alarm '{name}' created", "alarm_id": alarm_def["id"]}

    if action == "toggle_alarm_definition":
        def_id = payload.get("alarm_def_id") or payload.get("id")
        defs = state.get("alarm_definitions", [])
        alarm_def = next((d for d in defs if d["id"] == def_id), None)
        if not alarm_def:
            return {"ok": False, "error": "Alarm definition not found"}
        alarm_def["enabled"] = not alarm_def.get("enabled", True)
        state_label = "enabled" if alarm_def["enabled"] else "disabled"
        events.append(_event(f"Alarm '{alarm_def['name']}' {state_label}", "info", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Alarm '{alarm_def['name']}' {state_label}"}

    if action == "delete_alarm_definition":
        def_id = payload.get("alarm_def_id") or payload.get("id")
        defs = state.get("alarm_definitions", [])
        before = len(defs)
        state["alarm_definitions"] = [d for d in defs if d["id"] != def_id]
        if len(state["alarm_definitions"]) == before:
            return {"ok": False, "error": "Alarm definition not found"}
        events.append(_event("Alarm definition removed", "info", "vCenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Alarm definition removed"}

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
        # Symmetric with disconnect_network: reconnecting the primary adapter
        # flips its connected + cable state back on so the guest link comes up.
        if vm.get("nics"):
            vm["nics"][0]["connected"] = True
            vm["nics"][0]["cable_connected"] = True
        events.append(_event(f"Network adapter connected on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Connect Network", vm["name"]))
        _save_session(str(session_id), entry)
        try:
            from apps.labs.provisioner.simulation.chaos_engine import clear_faults as _chaos_clear
            _chaos_clear(session_id, fault_type="drop_nic", target=vm.get("name") or "")
        except Exception:  # pragma: no cover
            pass
        return {"ok": True, "message": f"Network connected on {vm['name']}"}

    if action == "disconnect_network":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        # Pulling the primary adapter: mark the VM disconnected AND flip the
        # first NIC's connected/cable state off so the guest reports NO-CARRIER.
        vm["network_disconnected"] = True
        vm["net_mbps"] = 0
        if vm.get("nics"):
            vm["nics"][0]["connected"] = False
            vm["nics"][0]["cable_connected"] = False
        events.append(_event(f"Network adapter disconnected on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Disconnect Network", vm["name"]))
        _save_session(str(session_id), entry)
        # Record into the shared cross-console fault ledger (Phase 3.2) so any
        # other open console for this session can see "drop_nic" is active —
        # mirrors the datacenter_engine trip_pdu_breaker pattern.
        try:
            from apps.labs.provisioner.simulation.chaos_engine import inject as _chaos_inject
            _chaos_inject(session_id, "drop_nic", vm.get("name") or "", detail={"vm_id": vm.get("id")})
        except Exception:  # pragma: no cover
            pass
        return {"ok": True, "message": f"Network disconnected on {vm['name']}"}

    if action == "set_nic_connected":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        nic_id = payload.get("nic_id")
        nics = vm.get("nics") or []
        nic = next((n for n in nics if n.get("id") == nic_id), None)
        if not nic:
            return {"ok": False, "error": "Network adapter not found"}
        connected = bool(payload.get("connected"))
        nic["connected"] = connected
        nic["cable_connected"] = connected
        # Keep the VM-level flag consistent when the *primary* NIC is toggled so
        # the guest terminal (which keys off network_disconnected + nics[0]) and
        # the vSphere summary stay in sync.
        if nics and nic is nics[0]:
            if connected:
                vm.pop("network_disconnected", None)
                vm["net_mbps"] = random.randint(5, 30)
            else:
                vm["network_disconnected"] = True
                vm["net_mbps"] = 0
        verb = "connected" if connected else "disconnected"
        events.append(_event(f"{nic.get('label', 'Network adapter')} {verb} on {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Edit Network Adapter", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{nic.get('label', 'Network adapter')} {verb}"}

    if action == "edit_nic":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        nic_id = payload.get("nic_id")
        nics = vm.get("nics") or []
        nic = next((n for n in nics if n.get("id") == nic_id), None)
        if not nic:
            return {"ok": False, "error": "Network adapter not found"}
        changed = []
        net_id = payload.get("network_id")
        if net_id:
            net = next((n for n in state.get("networks", []) if n["id"] == net_id), None)
            if not net:
                return {"ok": False, "error": "Network not found"}
            nic["network_id"] = net_id
            nic["network_name"] = net["name"]
            nic["vlan_id"] = net.get("vlan_id", net.get("vlan"))
            nic["portgroup_key"] = net.get("portgroup_key", "")
            # Reconnecting the specified NIC to a valid port group brings its link up.
            nic["connected"] = True
            nic["cable_connected"] = True
            changed.append(f"network → {net['name']}")
            # Only the primary NIC drives the VM-level network_id / summary.
            if nics and nic is nics[0]:
                vm["network_id"] = net_id
                vm.pop("network_disconnected", None)
                vm["net_mbps"] = random.randint(5, 30)
        adapter_type = payload.get("adapter_type")
        if adapter_type:
            nic["adapter_type"] = adapter_type
            changed.append(f"adapter → {adapter_type}")
        if not changed:
            return {"ok": False, "error": "No changes specified"}
        events.append(_event(f"{nic.get('label', 'Network adapter')} edited on {vm['name']}: {', '.join(changed)}", "info", vm["name"]))
        tasks.insert(0, _task("Edit Network Adapter", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{nic.get('label', 'Network adapter')} updated: {', '.join(changed)}"}

    if action == "edit_disk":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        disks = vm.get("disks") or []
        disk_id = payload.get("disk_id")
        scsi_id = payload.get("scsi_id")
        disk = next(
            (d for d in disks if d.get("id") == disk_id or (scsi_id and d.get("scsi_id") == scsi_id)),
            None,
        )
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        new_size = int(payload.get("size_gb") or 0)
        cur = int(disk.get("capacity_gb") or 0)
        if new_size <= 0:
            return {"ok": False, "error": "New size must be a positive number of GB"}
        # Virtual disks can only be grown online; shrinking is not supported.
        if new_size < cur:
            return {"ok": False, "error": f"Cannot shrink a virtual disk below its current {cur} GB"}
        if new_size == cur:
            return {"ok": False, "error": "New size matches the current size"}
        delta = new_size - cur
        ds = _find_ds(state, ds_id=disk.get("datastore_id") or vm.get("datastore_id"))
        if ds is not None and ds.get("free_gb", 0) < delta:
            return {"ok": False, "error": f"Datastore has only {ds.get('free_gb', 0)} GB free — cannot grow by {delta} GB"}
        disk["capacity_gb"] = new_size
        vm["disk_gb"] = sum(d.get("capacity_gb", 0) for d in disks)
        if ds is not None:
            ds["free_gb"] = max(0, ds["free_gb"] - delta)
        # A powered-on guest sees the extra capacity only after a rescan / online
        # resize inside the OS, so flag it pending (mirrors real hot-grow).
        if vm.get("power") == "poweredOn":
            disk["resize_pending"] = True
            vm["guest_disk_resize_pending"] = True
        events.append(_event(f"Grew {disk.get('scsi_id', '')} on {vm['name']} to {new_size} GB", "info", vm["name"]))
        tasks.insert(0, _task("Extend Virtual Disk", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Disk {disk.get('scsi_id', '')} grown to {new_size} GB"}

    if action == "add_cdrom":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        cdroms = vm.setdefault("cdroms", [])
        idx = len(cdroms) + 1
        cd_id = f"{vm['id']}-cdrom{idx}-{int(time.time()) % 100000}"
        iso = (payload.get("iso_path") or "").strip()
        cd = _make_cdrom(cd_id, iso_path=iso, connected=bool(iso), label=f"CD/DVD drive {idx}")
        cdroms.append(cd)
        events.append(_event(f"Added CD/DVD drive to {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Add CD/DVD Drive", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Added CD/DVD drive to {vm['name']}"}

    if action == "remove_cdrom":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        cdroms = vm.get("cdroms") or []
        cd_id = payload.get("cdrom_id")
        cd = next((c for c in cdroms if c.get("id") == cd_id), None)
        if not cd:
            return {"ok": False, "error": "CD/DVD drive not found"}
        vm["cdroms"] = [c for c in cdroms if c is not cd]
        events.append(_event(f"Removed {cd.get('label', 'CD/DVD drive')} from {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Remove CD/DVD Drive", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Removed CD/DVD drive from {vm['name']}"}

    if action in ("mount_iso", "unmount_iso"):
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        cdroms = vm.get("cdroms") or []
        cd_id = payload.get("cdrom_id")
        cd = next((c for c in cdroms if c.get("id") == cd_id), cdroms[0] if cdroms else None)
        if not cd:
            return {"ok": False, "error": "CD/DVD drive not found"}
        if action == "mount_iso":
            iso = (payload.get("iso_path") or "").strip()
            if not iso:
                return {"ok": False, "error": "ISO path is required"}
            cd["iso_path"] = iso
            cd["device_type"] = "datastore_iso"
            cd["connected"] = True
            cd["connect_at_power_on"] = True
            events.append(_event(f"Mounted {iso} on {vm['name']}", "info", vm["name"]))
            tasks.insert(0, _task("Edit CD/DVD Drive", vm["name"]))
            msg = f"Mounted {iso}"
        else:
            cd["iso_path"] = ""
            cd["device_type"] = "client_device"
            cd["connected"] = False
            events.append(_event(f"Unmounted ISO on {vm['name']}", "info", vm["name"]))
            tasks.insert(0, _task("Edit CD/DVD Drive", vm["name"]))
            msg = "Unmounted ISO"
        _save_session(str(session_id), entry)
        return {"ok": True, "message": msg}

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
        # Cross-tech k8s: if the learner creates the worker VM the scenario expects
        # (by name), bind it to the k8s node so powering it on joins that node.
        _xcfg = _cross_tech_config(entry.get("scenario_slug"))
        if _xcfg and _xcfg.get("tech") == "kubernetes" and name == _xcfg.get("vmware_vm"):
            vm["k8s_node"] = _xcfg.get("k8s_node")
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
        # provisioning: "thin" (default) or "thick"; UI may pass thin=False directly.
        thin = payload.get("thin")
        if thin is None:
            thin = str(payload.get("provisioning", "thin")).lower() != "thick"
        thin = bool(thin)
        _enrich_inventory(state)
        disks = vm.setdefault("disks", [])
        # SCSI unit 7 is reserved for the controller, so skip it when auto-assigning.
        used_units = {d.get("scsi_unit", 0) for d in disks}
        next_unit = 0
        while next_unit in used_units or next_unit == 7:
            next_unit += 1
        disk_id = f"{vm['id']}-disk{next_unit}-{int(time.time()) % 100000}"
        ds_id = payload.get("datastore_id") or vm.get("datastore_id") or (state["datastores"][0]["id"] if state["datastores"] else "")
        new_disk = _make_disk(disk_id, add_gb, ds_id, 0, next_unit, thin=thin)
        disks.append(new_disk)
        vm["disk_gb"] = sum(d.get("capacity_gb", 0) for d in disks)
        # VMware-only labs: hot-added disks must stay hidden in the guest until SCSI rescan.
        if vm.get("power") == "poweredOn" and next_unit > 0:
            vm["guest_disk_hidden"] = True
            vm["guest_disk_visible"] = False
            vm.setdefault("guest_pending_disks", []).append({
                "scsi_unit": next_unit,
                "capacity_gb": add_gb,
                "scsi_id": new_disk.get("scsi_id", f"0:{next_unit}"),
            })
        ds = _find_ds(state, ds_id=ds_id)
        if ds and ds["free_gb"] >= add_gb:
            ds["free_gb"] -= add_gb
        prov = "thin" if thin else "thick"
        events.append(_event(f"Added {add_gb} GB {prov} disk ({new_disk['scsi_id']}) to {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Add Hard Disk", vm["name"]))
        # ── Cross-technology bridge ──────────────────────────────────────────
        # For a cross-tech lab the disk we just attached at the hypervisor must
        # become visible in the Linux lab terminal — but only after the operator
        # forces a SCSI rescan (or, for the reboot scenario, a reboot). Record a
        # pending hot-added disk keyed by this lab session id so the terminal
        # engine (a different worker) can reveal it. Harmless for VMware-only labs.
        # Always record a pending hot-add for powered-on guests so the lab
        # terminal (and any cross-tech scenario) can reveal the disk after
        # rescan/reboot. Gating only on scenario_slug left Linux terminals
        # blind when the VMware session was created without a slug.
        bridge_msg = ""
        if vm.get("power") == "poweredOn":
            from apps.labs.provisioner.simulation.vmware_bridge import record_pending_disk
            cfg = _cross_tech_config(entry.get("scenario_slug"))
            requires_reboot = bool(cfg.get("requires_reboot")) if cfg else False
            dev = record_pending_disk(
                str(session_id), add_gb, requires_reboot=requires_reboot,
            )
            reveal = "reboot the guest" if requires_reboot else "rescan the SCSI bus in the terminal"
            bridge_msg = f" The guest will not see {dev} until you {reveal}."
            events.append(_event(
                f"Hot-add propagated to guest {vm['name']} as {dev} (pending {('reboot' if requires_reboot else 'SCSI rescan')})",
                "info", vm["name"],
            ))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Added {add_gb} GB {prov} disk at SCSI 0:{next_unit}.{bridge_msg}"}

    if action == "remove_disk":
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        disks = vm.get("disks") or []
        disk_id = payload.get("disk_id")
        scsi_id = payload.get("scsi_id")
        disk = next(
            (d for d in disks if d.get("id") == disk_id or (scsi_id and d.get("scsi_id") == scsi_id)),
            None,
        )
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        if disk.get("scsi_unit") == 0 and disk.get("scsi_controller", 0) == 0:
            return {"ok": False, "error": "Cannot remove the boot disk (SCSI 0:0)"}
        freed = disk.get("capacity_gb", 0)
        vm["disks"] = [d for d in disks if d is not disk]
        vm["disk_gb"] = sum(d.get("capacity_gb", 0) for d in vm["disks"])
        ds = _find_ds(state, ds_id=disk.get("datastore_id") or vm.get("datastore_id"))
        if ds:
            ds["free_gb"] = min(ds["capacity_gb"], ds["free_gb"] + freed)
        events.append(_event(f"Removed disk {disk.get('scsi_id', '')} ({freed} GB) from {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Remove Hard Disk", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Removed {freed} GB disk from {vm['name']}"}

    if action in ("add_nic", "add_network_adapter"):
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        net_id = payload.get("network_id") or vm.get("network_id") or (state["networks"][0]["id"] if state["networks"] else None)
        net = next((n for n in state.get("networks", []) if n["id"] == net_id), None)
        if not net:
            return {"ok": False, "error": "Port group / network not found"}
        _enrich_inventory(state)
        nics = vm.setdefault("nics", [])
        idx = len(nics) + 1
        nic_id = f"{vm['id']}-nic{idx}-{int(time.time()) % 100000}"
        mac = _vmware_mac(nic_id)
        adapter_type = payload.get("adapter_type") or "Vmxnet3"
        nic = _make_nic(
            nic_id, net_id, net.get("name", "VM Network"), mac,
            vlan_id=net.get("vlan_id", net.get("vlan")),
            connected=True, adapter_type=adapter_type,
            portgroup_key=net.get("portgroup_key", ""),
        )
        # Label as the next contiguous "Network adapter N" (one past the highest
        # existing adapter number) so a VM with "Network adapter 0" gets a
        # "Network adapter 1" next, instead of jumping to "2" and leaving a gap.
        next_label_num = 0
        for existing in nics:
            m = re.search(r"(\d+)\s*$", str(existing.get("label") or ""))
            if m:
                next_label_num = max(next_label_num, int(m.group(1)) + 1)
        nic["label"] = f"Network adapter {next_label_num}"
        nics.append(nic)
        if vm.get("power") == "poweredOn" and idx > 1:
            vm["guest_nic_pending"] = True
            vm.setdefault("guest_pending_nics", []).append({
                "label": nic.get("label", f"Network adapter {idx}"),
                "mac": mac,
                "name": f"eth{idx - 1}",
            })
        events.append(_event(f"Added {adapter_type} network adapter on {net.get('name')} to {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Add Network Adapter", vm["name"]))
        nic_msg = ""
        # Always bridge hot-added NICs for powered-on guests (same as disks).
        # Cross-tech labs previously required scenario_slug == nic-add action,
        # which silently no-op'd when the VMware session lacked that slug.
        if vm.get("power") == "poweredOn" and idx > 1:
            from apps.labs.provisioner.simulation.vmware_bridge import record_pending_nic
            record_pending_nic(str(session_id))
            nic_msg = " The guest sees the new link after a SCSI/PCI rescan or `ip a` in the lab terminal."
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Added network adapter (MAC {mac}) to {vm['name']}.{nic_msg}"}

    if action in ("remove_nic", "remove_network_adapter"):
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        nics = vm.get("nics") or []
        if len(nics) <= 1:
            return {"ok": False, "error": "Cannot remove the last network adapter"}
        nic_id = payload.get("nic_id")
        nic = next((n for n in nics if n.get("id") == nic_id), None)
        if not nic:
            return {"ok": False, "error": "Network adapter not found"}
        vm["nics"] = [n for n in nics if n is not nic]
        # Keep the VM's primary network_id consistent with the remaining first NIC.
        vm["network_id"] = vm["nics"][0].get("network_id", vm.get("network_id"))
        events.append(_event(f"Removed {nic.get('label', 'network adapter')} from {vm['name']}", "info", vm["name"]))
        tasks.insert(0, _task("Remove Network Adapter", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Removed network adapter from {vm['name']}"}

    if action == "create_vswitch":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "vSwitch name is required"}
        switches = state.setdefault("vswitches", [])
        if any(v.get("name") == name for v in switches):
            return {"ok": False, "error": f"vSwitch '{name}' already exists"}
        sw_type = "distributed" if str(payload.get("type", "standard")).lower() in ("distributed", "dvs", "dswitch") else "standard"
        mtu = int(payload.get("mtu") or 1500)
        uplinks = payload.get("uplinks") or []
        if isinstance(uplinks, str):
            uplinks = [u.strip() for u in uplinks.split(",") if u.strip()]
        vsw = {
            "id": f"vsw-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "type": sw_type,
            "ports": int(payload.get("ports") or (256 if sw_type == "distributed" else 120)),
            "mtu": mtu,
            "uplinks": uplinks,
            "portgroups": [],
        }
        if sw_type == "distributed":
            vsw["version"] = "7.0.3"
            vsw["hosts"] = [h["id"] for h in state.get("hosts", [])]
        else:
            vsw["host"] = payload.get("host_id") or (state["hosts"][0]["id"] if state["hosts"] else "")
        switches.append(vsw)
        events.append(_event(f"Created {sw_type} switch {name}", "info", name))
        tasks.insert(0, _task("Add Virtual Switch", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{sw_type.capitalize()} switch '{name}' created", "vswitch_id": vsw["id"]}

    if action == "remove_vswitch":
        sw_id = payload.get("vswitch_id") or payload.get("id")
        sw_name = payload.get("name")
        switches = state.get("vswitches") or []
        vsw = next((v for v in switches if v.get("id") == sw_id or v.get("name") == sw_name), None)
        if not vsw:
            return {"ok": False, "error": "vSwitch not found"}
        if vsw.get("name") in ("vSwitch0",):
            return {"ok": False, "error": "Cannot remove the management switch vSwitch0"}
        attached = [n for n in state.get("networks", []) if n.get("switch") == vsw.get("name")]
        if attached:
            return {"ok": False, "error": f"Remove its {len(attached)} port group(s) first"}
        state["vswitches"] = [v for v in switches if v is not vsw]
        events.append(_event(f"Removed virtual switch {vsw.get('name')}", "warning", vsw.get("name", "")))
        tasks.insert(0, _task("Remove Virtual Switch", vsw.get("name", "")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"vSwitch '{vsw.get('name')}' removed"}

    if action == "remove_portgroup":
        net_id = payload.get("network_id") or payload.get("id")
        net_name = payload.get("name")
        nets = state.get("networks") or []
        net = next((n for n in nets if n.get("id") == net_id or n.get("name") == net_name), None)
        if not net:
            return {"ok": False, "error": "Port group not found"}
        in_use = [v for v in state.get("vms", []) if v.get("network_id") == net["id"]]
        if in_use:
            return {"ok": False, "error": f"Port group in use by {len(in_use)} VM(s) — move them first"}
        state["networks"] = [n for n in nets if n is not net]
        for vsw in state.get("vswitches", []):
            if net.get("name") in (vsw.get("portgroups") or []):
                vsw["portgroups"] = [p for p in vsw["portgroups"] if p != net["name"]]
        events.append(_event(f"Removed port group {net.get('name')}", "warning", net.get("switch", "")))
        tasks.insert(0, _task("Remove Port Group", net.get("name", "")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Port group '{net.get('name')}' removed"}

    if action == "create_datastore":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Datastore name is required"}
        if _find_ds(state, ds_name=name):
            return {"ok": False, "error": f"Datastore '{name}' already exists"}
        ds_type = str(payload.get("type") or "VMFS").upper()
        if ds_type not in ("VMFS", "NFS", "VSAN"):
            ds_type = "VMFS"
        capacity = max(10, int(payload.get("capacity_gb") or 512))
        ds = {
            "id": f"ds-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "type": ds_type,
            "version": "VMFS 6.82" if ds_type == "VMFS" else ("NFS 4.1" if ds_type == "NFS" else "vSAN 7.0"),
            "capacity_gb": capacity,
            "free_gb": capacity,
            "accessible": True,
            "hosts": payload.get("hosts") or [h["id"] for h in state.get("hosts", [])],
            "vms": [],
        }
        state.setdefault("datastores", []).append(ds)
        _enrich_inventory(state)
        events.append(_event(f"Created {ds_type} datastore {name} ({capacity} GB)", "info", name))
        tasks.insert(0, _task("Create Datastore", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{ds_type} datastore '{name}' created", "datastore_id": ds["id"]}

    if action == "remove_datastore":
        ds = _find_ds(state, ds_id=payload.get("datastore_id"), ds_name=payload.get("name") or payload.get("datastore"))
        if not ds:
            return {"ok": False, "error": "Datastore not found"}
        if ds.get("vms"):
            return {"ok": False, "error": f"Datastore has {len(ds['vms'])} VM(s) — relocate them first"}
        state["datastores"] = [d for d in state.get("datastores", []) if d is not ds]
        events.append(_event(f"Removed datastore {ds.get('name')}", "warning", ds.get("name", "")))
        tasks.insert(0, _task("Remove Datastore", ds.get("name", "")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Datastore '{ds.get('name')}' removed"}

    if action == "create_cluster":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Cluster name is required"}
        dcs = state.setdefault("datacenters", [])
        dc = next((d for d in dcs if d.get("id") == payload.get("datacenter_id")), dcs[0] if dcs else None)
        if dc is None:
            dc = {"id": "dc-prod", "name": "DC-Prod", "site": "primary", "clusters": []}
            dcs.append(dc)
        clusters = dc.setdefault("clusters", [])
        if any(c.get("name") == name for c in clusters):
            return {"ok": False, "error": f"Cluster '{name}' already exists"}
        cluster = {
            "id": f"cluster-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "hosts": [],
            "ha": bool(payload.get("ha", True)),
            "drs": bool(payload.get("drs", True)),
            "vsan": bool(payload.get("vsan", False)),
        }
        clusters.append(cluster)
        feats = [f for f, on in (("HA", cluster["ha"]), ("DRS", cluster["drs"]), ("vSAN", cluster["vsan"])) if on]
        events.append(_event(f"Created cluster {name}" + (f" with {', '.join(feats)}" if feats else ""), "info", name))
        tasks.insert(0, _task("Create Cluster", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Cluster '{name}' created" + (f" ({', '.join(feats)})" if feats else ""), "cluster_id": cluster["id"]}

    if action == "add_host_uplink":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        # Ensure the default vmnic0-3 exist before numbering the next uplink, so
        # we don't collide with the on-read enriched adapters (e.g. a 2nd "vmnic0").
        _enrich_inventory(state)
        vmnics = host.setdefault("vmnics", [])
        nums = [int(v["name"][5:]) for v in vmnics if v.get("name", "").startswith("vmnic") and v["name"][5:].isdigit()]
        idx = (max(nums) + 1) if nums else 0
        name = f"vmnic{idx}"
        switch = payload.get("switch") or (state["vswitches"][0]["name"] if state.get("vswitches") else "vSwitch0")
        uplink = {
            "id": f"{host['id']}-{name}",
            "name": name,
            "mac_address": _vmware_mac(f"{host['id']}-{name}-{int(time.time())}"),
            "pci_id": f"0000:0{6 + idx // 2}:00.{idx % 2}",
            "driver": "bnxtnet",
            "speed_mbps": int(payload.get("speed_mbps") or 10000),
            "status": "up",
            "switch": switch,
            "duplex": "full",
        }
        vmnics.append(uplink)
        host["network_adapters"] = len(vmnics)
        for vsw in state.get("vswitches", []):
            if vsw.get("name") == switch:
                vsw.setdefault("uplinks", []).append(name)
        events.append(_event(f"Added uplink {name} to {switch} on {host['name']}", "info", host["name"]))
        tasks.insert(0, _task("Add Physical Adapter", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Added uplink {name} to {switch}"}

    if action == "remove_host_uplink":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        vmnics = host.get("vmnics") or []
        nic_id = payload.get("uplink_id") or payload.get("nic_id")
        name = payload.get("name")
        uplink = next((v for v in vmnics if v.get("id") == nic_id or v.get("name") == name), None)
        if not uplink:
            return {"ok": False, "error": "Uplink not found"}
        if len(vmnics) <= 1:
            return {"ok": False, "error": "Cannot remove the last physical uplink"}
        host["vmnics"] = [v for v in vmnics if v is not uplink]
        host["network_adapters"] = len(host["vmnics"])
        for vsw in state.get("vswitches", []):
            if uplink.get("name") in (vsw.get("uplinks") or []):
                vsw["uplinks"] = [u for u in vsw["uplinks"] if u != uplink["name"]]
        events.append(_event(f"Removed uplink {uplink.get('name')} from {host['name']}", "warning", host["name"]))
        tasks.insert(0, _task("Remove Physical Adapter", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Removed uplink {uplink.get('name')}"}

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

    if action in ("assign_permission", "assign_role"):
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
        vm["guest_nic_pending"] = False
        vm.pop("guest_pending_disks", None)
        vm.pop("guest_pending_nics", None)
        events.append(_event(f"SCSI rescan completed in guest {vm['name']}", "info", vm["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Guest hardware visible after SCSI rescan"}

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
        vm["vmware_tools_status"] = "current"
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

    if action == "add_host":
        name = (payload.get("name") or payload.get("hostname") or "").strip()
        if not name:
            return {"ok": False, "error": "Host name or IP is required"}
        if _find_host(state, host_name=name) or any(h.get("ip") == name for h in state["hosts"]):
            return {"ok": False, "error": f"Host '{name}' is already in the inventory"}
        ip = payload.get("ip") or (name if name.replace(".", "").isdigit() else f"192.168.10.{20 + len(state['hosts'])}")
        host_id = f"host-{name.lower().replace('.', '-').replace(' ', '-')}-{int(time.time()) % 100000}"
        dc_id = payload.get("datacenter_id") or "dc-prod"
        host = {
            "id": host_id,
            "name": name if "." in name or not name.replace(".", "").isdigit() else f"esxi-{name}.fixitlab.local",
            "ip": ip,
            "status": "connected",
            "connection_state": "connected",
            "maintenance": False,
            "version": payload.get("version") or "7.0.3",
            "build": "20328353",
            "vendor": "VMware, Inc.",
            "model": payload.get("model") or "VMware Virtual Platform",
            "cpu_model": payload.get("cpu_model") or "Intel(R) Xeon(R) Gold 6248R @ 3.00GHz",
            "cpu_sockets": int(payload.get("cpu_sockets") or 2),
            "cpu_cores_per_socket": int(payload.get("cpu_cores_per_socket") or 12),
            "cpu_threads": int(payload.get("cpu_threads") or 48),
            "cpu_mhz": int(payload.get("cpu_mhz") or 3000),
            "cpu_pct": random.randint(8, 20),
            "memory_gb": int(payload.get("memory_gb") or 128),
            "mem_pct": random.randint(20, 40),
            "network_mbps": 0,
            "network_adapters": 4,
            "storage_pct": random.randint(20, 40),
            "uptime_seconds": 3600,
            "vms": [],
            "ssh_enabled": False,
            "power_policy": "Balanced",
            "ntp_server": "pool.ntp.org",
            "ntp_synced": True,
            "dns_servers": ["8.8.8.8", "8.8.4.4"],
            "datacenter_id": dc_id,
        }
        state["hosts"].append(host)
        _enrich_inventory(state)
        # Attach to the target datacenter's first cluster if present.
        for dc in state.get("datacenters", []):
            if dc.get("id") == dc_id and dc.get("clusters"):
                dc["clusters"][0].setdefault("hosts", []).append(host_id)
                break
        if state.get("host_missing"):
            state["host_missing"] = False
        events.append(_event(f"Added host {host['name']} to {dc_id}", "info", host["name"]))
        tasks.insert(0, _task("Add Standalone Host", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Host '{host['name']}' added", "host_id": host_id}

    if action == "new_resource_pool":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Resource pool name is required"}
        pools = state.setdefault("resource_pools", [])
        parent = payload.get("parent") or state.get("cluster") or "Cluster-01"
        if any(p.get("name") == name and p.get("parent") == parent for p in pools):
            return {"ok": False, "error": f"Resource pool '{name}' already exists under {parent}"}
        pool = {
            "id": f"rp-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "parent": parent,
            "parent_id": payload.get("parent_id") or "cluster-01",
            "cpu_shares": payload.get("cpu_shares") or "normal",
            "mem_shares": payload.get("mem_shares") or "normal",
            "cpu_limit_mhz": int(payload.get("cpu_limit_mhz", -1)),
            "mem_limit_mb": int(payload.get("mem_limit_mb", -1)),
            "cpu_reservation_mhz": int(payload.get("cpu_reservation_mhz", 0)),
            "mem_reservation_mb": int(payload.get("mem_reservation_mb", 0)),
        }
        pools.append(pool)
        events.append(_event(f"Created resource pool {name} on {parent}", "info", name))
        tasks.insert(0, _task("Create Resource Pool", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Resource pool '{name}' created", "resource_pool_id": pool["id"]}

    if action == "remove_resource_pool":
        rp_id = payload.get("resource_pool_id") or payload.get("id")
        pools = state.get("resource_pools") or []
        pool = next((p for p in pools if p.get("id") == rp_id or p.get("name") == payload.get("name")), None)
        if not pool:
            return {"ok": False, "error": "Resource pool not found"}
        if any(v.get("resource_pool_id") == pool["id"] for v in state.get("vms", [])):
            return {"ok": False, "error": "Move the VMs out of this resource pool first"}
        state["resource_pools"] = [p for p in pools if p is not pool]
        events.append(_event(f"Removed resource pool {pool.get('name')}", "warning", pool.get("name", "")))
        tasks.insert(0, _task("Remove Resource Pool", pool.get("name", "")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Resource pool '{pool.get('name')}' removed"}

    if action == "new_vapp":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "vApp name is required"}
        vapps = state.setdefault("vapps", [])
        if any(va.get("name") == name for va in vapps):
            return {"ok": False, "error": f"vApp '{name}' already exists"}
        vapp = {
            "id": f"vapp-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "parent": payload.get("parent") or state.get("cluster") or "Cluster-01",
            "parent_id": payload.get("parent_id") or "cluster-01",
            "power": "poweredOff",
            "cpu_shares": payload.get("cpu_shares") or "normal",
            "mem_shares": payload.get("mem_shares") or "normal",
            "vms": payload.get("vms") or [],
            "start_order": payload.get("start_order") or [],
        }
        vapps.append(vapp)
        events.append(_event(f"Created vApp {name}", "info", name))
        tasks.insert(0, _task("Create vApp", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"vApp '{name}' created", "vapp_id": vapp["id"]}

    if action == "vapp_power":
        vapp = next((va for va in state.get("vapps", []) if va.get("id") == payload.get("vapp_id") or va.get("name") == payload.get("name")), None)
        if not vapp:
            return {"ok": False, "error": "vApp not found"}
        op = payload.get("op") or "on"
        new_power = "poweredOn" if op == "on" else "poweredOff"
        vapp["power"] = new_power
        for vid in vapp.get("vms", []):
            vm = _find_vm(state, vm_id=vid)
            if vm:
                vm["power"] = new_power
        events.append(_event(f"vApp {vapp['name']} powered {'on' if op == 'on' else 'off'}", "info", vapp["name"]))
        tasks.insert(0, _task(f"Power {'On' if op == 'on' else 'Off'} vApp", vapp["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"vApp '{vapp['name']}' powered {'on' if op == 'on' else 'off'}"}

    if action == "remove_vapp":
        vapp = next((va for va in state.get("vapps", []) if va.get("id") == payload.get("vapp_id") or va.get("name") == payload.get("name")), None)
        if not vapp:
            return {"ok": False, "error": "vApp not found"}
        state["vapps"] = [va for va in state.get("vapps", []) if va is not vapp]
        events.append(_event(f"Removed vApp {vapp.get('name')}", "warning", vapp.get("name", "")))
        tasks.insert(0, _task("Delete vApp", vapp.get("name", "")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"vApp '{vapp.get('name')}' removed"}

    if action == "create_datastore_cluster":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Datastore cluster name is required"}
        clusters = state.setdefault("datastore_clusters", [])
        if any(c.get("name") == name for c in clusters):
            return {"ok": False, "error": f"Datastore cluster '{name}' already exists"}
        member_ids = payload.get("datastore_ids") or payload.get("members") or []
        if isinstance(member_ids, str):
            member_ids = [m.strip() for m in member_ids.split(",") if m.strip()]
        cluster = {
            "id": f"dscl-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "sdrs_enabled": bool(payload.get("sdrs_enabled", payload.get("sdrs", True))),
            "automation_level": payload.get("automation_level") or "fullyAutomated",
            "datastore_ids": member_ids,
            "datacenter_id": payload.get("datacenter_id") or "dc-prod",
        }
        clusters.append(cluster)
        # Tag member datastores so the tree/listing can show their pod membership.
        for ds in state.get("datastores", []):
            if ds["id"] in member_ids:
                ds["datastore_cluster_id"] = cluster["id"]
        sdrs = "SDRS on" if cluster["sdrs_enabled"] else "SDRS off"
        events.append(_event(f"Created datastore cluster {name} ({sdrs})", "info", name))
        tasks.insert(0, _task("Create Datastore Cluster", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Datastore cluster '{name}' created ({sdrs})", "datastore_cluster_id": cluster["id"]}

    if action == "add_folder":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Folder name is required"}
        folder_type = str(payload.get("folder_type") or payload.get("type") or "vm").lower()
        if folder_type not in ("host", "vm", "storage", "network", "datacenter"):
            folder_type = "vm"
        folders = state.setdefault("folders", [])
        dc_id = payload.get("datacenter_id") or "dc-prod"
        if any(f.get("name") == name and f.get("folder_type") == folder_type and f.get("datacenter_id") == dc_id for f in folders):
            return {"ok": False, "error": f"A {folder_type} folder named '{name}' already exists"}
        folder = {
            "id": f"folder-{folder_type}-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "folder_type": folder_type,
            "datacenter_id": dc_id,
        }
        folders.append(folder)
        events.append(_event(f"Created {folder_type} folder {name}", "info", name))
        tasks.insert(0, _task("Create Folder", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{folder_type.capitalize()} folder '{name}' created", "folder_id": folder["id"]}

    if action == "create_role":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Role name is required"}
        catalog = state.setdefault("roles_catalog", [])
        if name in catalog:
            return {"ok": False, "error": f"Role '{name}' already exists"}
        catalog.append(name)
        priv_groups = payload.get("privilege_groups") or []
        state.setdefault("custom_roles", []).append({
            "id": f"role-{name.lower().replace(' ', '-')}-{int(time.time()) % 100000}",
            "name": name,
            "privilege_groups": priv_groups,
            "cloneable": True,
        })
        events.append(_event(f"Created role {name}", "info", "SSO"))
        tasks.insert(0, _task("Create Role", name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Role '{name}' created"}

    if action == "set_user_enabled":
        user_id = payload.get("user_id")
        username = payload.get("username")
        users = state.get("vcenter_users", [])
        user = next((u for u in users if u["id"] == user_id or u["username"] == username), None)
        if not user:
            return {"ok": False, "error": "User not found"}
        if user.get("builtin"):
            return {"ok": False, "error": "Cannot disable a built-in user"}
        user["enabled"] = bool(payload.get("enabled", not user.get("enabled", True)))
        label = "enabled" if user["enabled"] else "disabled"
        events.append(_event(f"User {user['username']} {label}", "info", "SSO"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{user['username']} {label}"}

    if action == "rescan_storage":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if host:
            host["hba_rescan_done"] = True
        events.append(_event(f"Rescan storage on {host['name'] if host else 'all hosts'}", "info", host["name"] if host else "Cluster-01"))
        tasks.insert(0, _task("Rescan Storage", host["name"] if host else "Datacenter"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Storage rescan completed"}

    if action == "renew_host_cert":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        host["cert_renewed_at"] = _now_iso()
        host.pop("cert_expired", None)
        events.append(_event(f"Renewed certificate on {host['name']}", "info", host["name"]))
        tasks.insert(0, _task("Renew Host Certificate", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Certificate renewed on {host['name']}"}

    if action == "extract_host_profile":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        if not host:
            return {"ok": False, "error": "Host not found"}
        profile_name = payload.get("profile_name") or f"{host['name'].split('.')[0]}-profile"
        host["host_profile"] = profile_name
        state.setdefault("host_profiles", [])
        if not any(p.get("name") == profile_name for p in state["host_profiles"]):
            state["host_profiles"].append({
                "id": f"hp-{int(time.time()) % 100000}", "name": profile_name,
                "reference_host": host["name"], "compliant_hosts": [host["id"]],
            })
        events.append(_event(f"Extracted host profile {profile_name} from {host['name']}", "info", host["name"]))
        tasks.insert(0, _task("Extract Host Profile", host["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Host profile '{profile_name}' extracted"}

    if action == "export_system_logs":
        host = _find_host(state, payload.get("host_id"), payload.get("host_name"))
        target = host["name"] if host else (state.get("cluster") or "Cluster-01")
        events.append(_event(f"Exported system logs for {target}", "info", target))
        tasks.insert(0, _task("Export System Logs", target))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"System logs bundle generated for {target}"}

    if action == "migrate_vms_network":
        src_id = payload.get("source_network_id")
        dst_id = payload.get("target_network_id")
        src = next((n for n in state.get("networks", []) if n["id"] == src_id), None)
        dst = next((n for n in state.get("networks", []) if n["id"] == dst_id), None)
        if not src or not dst:
            return {"ok": False, "error": "Source and target networks are required"}
        moved = 0
        for vm in state.get("vms", []):
            if vm.get("network_id") == src_id:
                vm["network_id"] = dst_id
                for nic in vm.get("nics", []):
                    if nic.get("network_id") == src_id:
                        nic["network_id"] = dst_id
                        nic["network_name"] = dst["name"]
                        nic["vlan_id"] = dst.get("vlan_id", dst.get("vlan"))
                moved += 1
        events.append(_event(f"Migrated {moved} VM(s) from {src['name']} to {dst['name']}", "info", dst["name"]))
        tasks.insert(0, _task("Migrate VMs to Another Network", dst["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Migrated {moved} VM(s) to {dst['name']}"}

    if action == "edit_default_vm_compat":
        compat = payload.get("compatibility") or "vmx-19"
        state["default_vm_compatibility"] = compat
        events.append(_event(f"Default VM compatibility set to {compat}", "info", state.get("datacenter", "DC-Prod")))
        tasks.insert(0, _task("Edit Default VM Compatibility", state.get("datacenter", "DC-Prod")))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Default VM compatibility set to {compat}"}

    if action == "rename_object":
        kind = payload.get("kind")
        new_name = (payload.get("name") or payload.get("new_name") or "").strip()
        if not new_name:
            return {"ok": False, "error": "New name is required"}
        obj = None
        if kind == "datacenter":
            obj = next((d for d in state.get("datacenters", []) if d["id"] == payload.get("id")), None)
            if obj and obj["id"] in ("dc-prod",) and state.get("datacenter") == obj["name"]:
                state["datacenter"] = new_name
        elif kind == "datastore":
            obj = _find_ds(state, ds_id=payload.get("id"))
        elif kind == "network":
            obj = next((n for n in state.get("networks", []) if n["id"] == payload.get("id")), None)
        elif kind == "vm":
            return apply_action(session_id, "edit_vm", {"vm_id": payload.get("id"), "name": new_name})
        if not obj:
            return {"ok": False, "error": "Object not found"}
        old = obj.get("name")
        obj["name"] = new_name
        events.append(_event(f"Renamed {kind} {old} → {new_name}", "info", new_name))
        tasks.insert(0, _task("Rename", new_name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Renamed to '{new_name}'"}

    if action == "toggle_datastore_sdrs":
        dscl = next((c for c in state.get("datastore_clusters", []) if c.get("id") == payload.get("datastore_cluster_id") or c.get("name") == payload.get("name")), None)
        if not dscl:
            return {"ok": False, "error": "Datastore cluster not found"}
        dscl["sdrs_enabled"] = bool(payload.get("sdrs_enabled", not dscl.get("sdrs_enabled", True)))
        label = "enabled" if dscl["sdrs_enabled"] else "disabled"
        events.append(_event(f"Storage DRS {label} on {dscl['name']}", "info", dscl["name"]))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Storage DRS {label} on {dscl['name']}"}

    if action == "console_booted":
        # UI-state sync: the web console has finished replaying the boot sequence
        # for this VM, so subsequent console opens should go straight to the login
        # prompt (like reconnecting to an already-running server). No event/task —
        # this is not a vSphere operation, just clearing a transient boot flag.
        vm = _find_vm(state, payload.get("vm_id"), payload.get("vm_name"))
        if not vm:
            return {"ok": False, "error": "VM not found"}
        vm.pop("boot_pending", None)
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "boot acknowledged"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            events.append(_event(v2.get("message") or action, "success"))
            _save_session(str(session_id), entry)
        return v2

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
