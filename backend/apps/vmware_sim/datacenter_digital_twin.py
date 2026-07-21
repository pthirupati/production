"""Digital-twin hardware layer for the physical datacenter lab.

Motherboard map, RAID controller, BIOS/UEFI, and vendor BMC (iDRAC/iLO/IPMI)
facades. Kept separate from datacenter_engine.py so the facility model stays
readable while servers expose production-grade management surfaces.
"""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Motherboard (interactive component map) ─────────────────────────────────

def build_motherboard(vendor: str = "Dell") -> dict:
    """Selectable motherboard components with live bus telemetry stubs."""
    is_hpe = vendor.upper() in ("HPE", "HP")
    return {
        "model": "ProLiant Gen10 System Board" if is_hpe else "PowerEdge R750 System Board",
        "form_factor": "OCP 3.0 dual-socket",
        "pcb": {
            "width_mm": 305,
            "depth_mm": 330,
            "layers": 16,
            "color": "#1A5C1A",
            "finish": "ENIG",
        },
        "cpu_sockets": [
            {
                "id": "CPU1",
                "type": "LGA4677" if not is_hpe else "SP5",
                "populated": True,
                "status": "healthy",
                "die": "Xeon Gold 6338" if not is_hpe else "EPYC 7543",
                "tdp_w": 205,
                "temp_c": 48.2,
                "paste_applied": True,
                "heatsink": "aluminum finstack + heatpipes",
                "vrm_phases": 16,
            },
            {
                "id": "CPU2",
                "type": "LGA4677" if not is_hpe else "SP5",
                "populated": True,
                "status": "healthy",
                "die": "Xeon Gold 6338" if not is_hpe else "EPYC 7543",
                "tdp_w": 205,
                "temp_c": 51.0,
                "paste_applied": True,
                "heatsink": "aluminum finstack + heatpipes",
                "vrm_phases": 16,
            },
        ],
        "dimm_slots": [
            {
                "id": f"{ch}{n}",
                "channel": ch,
                "cpu": 1 if ch in "ABCD" else 2,
                "populated": True,
                "module": "32GB DDR4-3200 ECC RDIMM",
                "status": "healthy",
                "ecc_corrections_24h": 0,
            }
            for ch in "ABCDEFGH"
            for n in (1, 2)
        ][:16],
        "pcie_slots": [
            {"id": "PCIE1", "gen": 4, "lanes": 16, "device": "NVIDIA A40", "status": "healthy", "bw_gbs": 12.4},
            {"id": "PCIE2", "gen": 4, "lanes": 8, "device": "PERC H755" if not is_hpe else "Smart Array P408i", "status": "healthy", "bw_gbs": 3.1},
            {"id": "PCIE3", "gen": 4, "lanes": 8, "device": "ConnectX-6 25GbE", "status": "healthy", "bw_gbs": 5.2},
            {"id": "PCIE4", "gen": 3, "lanes": 8, "device": "Emulex LPe32002", "status": "healthy", "bw_gbs": 1.8},
            {"id": "PCIE5", "gen": 3, "lanes": 4, "device": None, "status": "empty", "bw_gbs": 0},
        ],
        "storage_connectors": [
            {"id": "U2-0", "type": "U.2", "gen": 4, "status": "linked"},
            {"id": "U2-1", "type": "U.2", "gen": 4, "status": "linked"},
            {"id": "SAS0", "type": "MiniSAS-HD SFF-8643", "status": "linked"},
            {"id": "M2-1", "type": "M.2 2280", "status": "empty"},
            {"id": "OCP30", "type": "OCP 3.0", "status": "linked"},
        ],
        "chips": [
            {"id": "BMC", "model": "ASPEED AST2600A3", "role": "BMC", "status": "healthy"},
            {"id": "BIOS1", "model": "SPI-NOR 256Mbit", "role": "BIOS primary", "status": "healthy"},
            {"id": "BIOS2", "model": "SPI-NOR 256Mbit", "role": "BIOS backup", "status": "healthy"},
            {"id": "TPM", "model": "TCG 2.0", "role": "TPM", "status": "healthy"},
            {"id": "CLK", "model": "PCIe refclk", "role": "Clock generator", "status": "healthy"},
            {"id": "CMOS", "model": "CR2032", "role": "CMOS battery", "status": "healthy", "voltage_v": 3.05},
        ],
        "buses": [
            {"id": "PCIe_Gen4", "util_pct": 42, "errors": 0, "color": "#00CC66"},
            {"id": "DDR4", "util_pct": 28, "errors": 0, "color": "#0088FF"},
            {"id": "UPI_3_0", "util_pct": 15, "errors": 0, "color": "#FF8800"},
            {"id": "SMBus", "util_pct": 4, "errors": 0, "color": "#888888"},
            {"id": "SATA_III", "util_pct": 11, "errors": 0, "color": "#FF4444"},
        ],
        "cover_open": False,
        "maintenance_mode": False,
    }


# ── RAID ───────────────────────────────────────────────────────────────────

def build_raid(vendor: str = "Dell") -> dict:
    is_hpe = vendor.upper() in ("HPE", "HP")
    controller = "HPE Smart Array P408i-a" if is_hpe else "Dell PERC H755"
    disks = [
        {"id": "PD0", "bay": 0, "model": "Samsung PM9A3", "size_gb": 1920, "bus": "NVMe", "status": "online", "smart": "OK", "temp_c": 38, "wear_pct": 4},
        {"id": "PD1", "bay": 1, "model": "Samsung PM9A3", "size_gb": 1920, "bus": "NVMe", "status": "online", "smart": "OK", "temp_c": 39, "wear_pct": 4},
        {"id": "PD2", "bay": 2, "model": "Seagate Exos", "size_gb": 4000, "bus": "SAS", "status": "online", "smart": "OK", "temp_c": 34, "wear_pct": 12},
        {"id": "PD3", "bay": 3, "model": "Seagate Exos", "size_gb": 4000, "bus": "SAS", "status": "hotspare", "smart": "OK", "temp_c": 32, "wear_pct": 8},
    ]
    return {
        "controller": controller,
        "firmware": "51.16.0-4076",
        "cache": {"mode": "WriteBack", "bbu": "present", "bbu_charge_pct": 100, "size_mb": 8192},
        "physical_disks": disks,
        "virtual_disks": [
            {
                "id": "VD0",
                "name": "OS",
                "raid_level": "RAID1",
                "size_gb": 1920,
                "members": ["PD0", "PD1"],
                "status": "optimal",
                "read_policy": "ReadAhead",
                "write_policy": "WriteBack",
                "stripe_kb": 64,
                "rebuild_pct": None,
            },
            {
                "id": "VD1",
                "name": "DATA",
                "raid_level": "RAID5",
                "size_gb": 8000,
                "members": ["PD2"],
                "status": "degraded",
                "read_policy": "NoReadAhead",
                "write_policy": "WriteThrough",
                "stripe_kb": 256,
                "rebuild_pct": None,
                "note": "Awaiting additional member / hotspare promote",
            },
        ],
        "operations": [],
        "patrol_read": {"enabled": True, "last_run": None, "status": "idle"},
        "consistency_check": {"enabled": True, "last_run": None, "status": "idle"},
        "foreign_config": False,
    }


# ── BIOS / UEFI ────────────────────────────────────────────────────────────

def build_bios(vendor: str = "Dell") -> dict:
    return {
        "vendor": vendor,
        "version": "2.12.0",
        "mode": "UEFI",
        "secure_boot": True,
        "tpm": "2.0 Enabled",
        "password_set": False,
        "password": None,
        "boot_order": ["Hard Disk", "PXE Network", "USB", "CD/DVD", "Virtual Media"],
        "settings": {
            "VirtualizationTechnology": "Enabled",
            "SRIOV": "Enabled",
            "HyperThreading": "Enabled",
            "TurboBoost": "Enabled",
            "NUMA": "Enabled",
            "PowerProfile": "Performance Per Watt Optimized",
            "ThermalProfile": "Default",
            "WakeOnLAN": "Enabled",
            "PXEBoot": "Enabled",
            "FanCurve": "Optimal",
            "MemoryTiming": "Auto",
            "PCIeGeneration": "Auto",
        },
        "post_state": "idle",  # idle | posting | setup | os
        "post_log": [],
        "setup_open": False,
        "cmos_cleared": False,
        "flash_in_progress": False,
    }


# ── BMC / iDRAC / iLO ──────────────────────────────────────────────────────

def build_bmc(hostname: str, vendor: str, power_state: str = "on", *, generation: str | None = None) -> dict:
    is_hpe = vendor.upper() in ("HPE", "HP")
    is_lenovo = vendor.upper() == "LENOVO"
    is_sm = vendor.upper() == "SUPERMICRO"
    if generation:
        product = generation
    elif is_hpe:
        product = "iLO 5"
    elif is_lenovo:
        product = "XClarity Controller"
    elif is_sm:
        product = "Supermicro IPMI"
    else:
        product = "iDRAC9"
    chip = "iLO ASIC" if is_hpe else ("ASPEED AST2600" if not is_lenovo else "XCC ASIC")
    fw = "2.86.00" if is_hpe else ("9.1.0" if is_lenovo else "6.10.30.00")
    on = power_state == "on"
    return {
        "product": product,
        "generations_available": (
            ["iLO4", "iLO5", "iLO6"] if is_hpe
            else ["iDRAC8", "iDRAC9", "iDRAC10"] if not (is_lenovo or is_sm)
            else [product]
        ),
        "chip": chip,
        "firmware": fw,
        "endpoint": f"https://bmc-{hostname}.mgmt.corp.local",
        "protocol": "redfish",
        "protocols_enabled": ["IPMI", "Redfish", "SNMP", "SSH", "HTTPS", "Syslog"],
        "power": "on" if on else "off",
        "network": {
            "mode": "Dedicated",
            "ipv4": f"10.90.{abs(hash(hostname)) % 200 + 10}.{(abs(hash(hostname)) // 200) % 250 + 2}",
            "netmask": "255.255.255.0",
            "gateway": "10.90.0.1",
            "vlan": 90,
            "dns": ["10.90.0.10", "10.90.0.11"],
            "ntp": "ntp.corp.local",
            "ldap": False,
            "active_directory": False,
        },
        "users": [
            {"name": "root", "role": "Administrator", "enabled": True, "mfa": False},
            {"name": "readonly", "role": "ReadOnly", "enabled": True, "mfa": False},
            {"name": "operator", "role": "Operator", "enabled": True, "mfa": True},
        ],
        "sensors": {
            "inlet_c": 22.1,
            "exhaust_c": 34.0 if on else 22.0,
            "cpu1_c": 48.2 if on else 24.0,
            "cpu2_c": 51.0 if on else 24.0,
            "dimm_c": 36.5 if on else 23.0,
            "fans_rpm": 4200 if on else 0,
            "psu1_w": 420 if on else 12,
            "psu2_w": 380 if on else 8,
            "12v": 12.01,
            "5v": 5.02,
            "3v3": 3.31,
            "chassis_intrusion": False,
        },
        "sel": [
            {"time": _now(), "severity": "info", "message": f"{product} self-test passed, sensors nominal"},
        ],
        "lifecycle_log": [
            {"time": _now(), "message": f"{product} firmware {fw} active"},
        ],
        "virtual_media": {"mounted": False, "image": None},
        "console": {"html5": True, "java_legacy": False, "kvm_active": False},
        "firmware_targets": ["BIOS", "BMC", "CPLD", "RAID", "NIC", "PSU", "Backplane"],
        "inventory": {
            "cpus": 2,
            "dimms_populated": 16,
            "drives": 4,
            "nics": 2,
            "gpus": 1,
            "psus": 2,
        },
        "diagnostics": {
            "last_run": None,
            "result": None,
            "suites": ["Memory", "CPU", "Storage", "PCIe", "Network", "Thermal", "Power", "Burn-In"],
        },
    }


def build_inventory_record(server: dict) -> dict:
    """CMDB-style asset record for a server chassis and key FRUs."""
    vendor = server.get("vendor") or "Dell"
    sid = server.get("id") or "srv"
    tag = server.get("service_tag") or f"AT-{abs(hash(sid)) % 10_000_000:07d}"
    purchase = "2023-06-15"
    return {
        "asset_tag": f"FIX-{abs(hash(sid)) % 100_000:05d}",
        "serial": tag,
        "vendor": vendor,
        "model": server.get("model") or "PowerEdge R750",
        "purchase_date": purchase,
        "warranty": {
            "type": "ProSupport Plus" if vendor == "Dell" else "HPE Foundation Care",
            "expires": "2027-06-15",
            "status": "active",
        },
        "firmware": {
            "bios": (server.get("bios") or {}).get("version") or server.get("firmware_version") or "2.12.0",
            "bmc": (server.get("bmc") or {}).get("firmware") or "6.10.30.00",
            "raid": (server.get("raid") or {}).get("firmware") or "51.16.0",
        },
        "lifecycle": {
            "eos": "2029-12-31",
            "eol": "2031-12-31",
            "stage": "production",
        },
        "replacement_history": server.get("inventory", {}).get("replacement_history") or [],
        "location": {
            "rack": server.get("rack"),
            "u_slot": server.get("u_slot"),
            "room": "data-hall-a",
        },
    }


def build_service_mode(vendor: str = "Dell") -> dict:
    return {
        "rails_extended": False,
        "cover_open": False,
        "air_shroud_removed": False,
        "power_cables_disconnected": False,
        "network_cables_disconnected": False,
        "cpu_removed": [],
        "heatsink_removed": [],
        "cmos_battery_ok": True,
        "tpm_present": True,
        "psu_hotswap_allowed": True,
        "notes": f"{vendor} field service checklist",
    }


def enrich_server(server: dict) -> dict:
    """Attach motherboard / RAID / BIOS / rich BMC if missing (idempotent)."""
    from apps.vmware_sim.datacenter_network_storage import enrich_cables, build_storage_stack

    vendor = server.get("vendor") or "Dell"
    hostname = server.get("hostname") or server.get("id") or "host"
    power = server.get("power_state") or "on"
    if not server.get("motherboard"):
        server["motherboard"] = build_motherboard(vendor)
    if not server.get("raid"):
        server["raid"] = build_raid(vendor)
    if not server.get("bios"):
        server["bios"] = build_bios(vendor)
    bmc = server.get("bmc") or {}
    if not bmc.get("product"):
        rich = build_bmc(hostname, vendor, power)
        # preserve existing endpoint/sel if present
        rich["endpoint"] = bmc.get("endpoint") or rich["endpoint"]
        rich["power"] = "on" if power == "on" else "off"
        if bmc.get("sel"):
            rich["sel"] = bmc["sel"]
        if bmc.get("sensors"):
            rich["sensors"].update({k: v for k, v in bmc["sensors"].items() if v is not None})
        server["bmc"] = rich
    if not server.get("inventory") or not server["inventory"].get("asset_tag"):
        prev_hist = (server.get("inventory") or {}).get("replacement_history") or []
        inv = build_inventory_record(server)
        inv["replacement_history"] = prev_hist
        server["inventory"] = inv
    if not server.get("service_mode"):
        server["service_mode"] = build_service_mode(vendor)
    # Keep motherboard cover in sync with service mode
    sm = server.get("service_mode") or {}
    mb = server.get("motherboard") or {}
    if sm.get("cover_open") and not mb.get("cover_open"):
        mb["cover_open"] = True
        mb["maintenance_mode"] = True
        server["motherboard"] = mb
    # Cables: enrich with catalog metadata
    hw = server.setdefault("hardware", {})
    if hw.get("cables"):
        hw["cables"] = enrich_cables(hw["cables"])
    if not server.get("storage_stack"):
        server["storage_stack"] = build_storage_stack(server.get("role"))
    return server


def campus_rooms() -> list[dict]:
    """Full campus zones beyond the data hall (navigable room list)."""
    return [
        {"id": "campus", "name": "Campus Overview", "type": "campus", "racks": [], "zone": "exterior"},
        {"id": "security-gate", "name": "Security Gate", "type": "security", "racks": [], "zone": "exterior"},
        {"id": "reception", "name": "Reception", "type": "office", "racks": [], "zone": "building"},
        {"id": "noc", "name": "NOC", "type": "ops", "racks": [], "zone": "building"},
        {"id": "soc", "name": "SOC", "type": "ops", "racks": [], "zone": "building"},
        {"id": "loading-dock", "name": "Loading Dock", "type": "logistics", "racks": [], "zone": "building"},
        {"id": "staging", "name": "Staging Room", "type": "ops", "racks": [], "zone": "building"},
        {"id": "burn-in", "name": "Burn-in Room", "type": "ops", "racks": [], "zone": "building"},
        {"id": "spares", "name": "Spare Inventory", "type": "ops", "racks": [], "zone": "building"},
        {"id": "repair", "name": "Repair Bench", "type": "ops", "racks": [], "zone": "building"},
        {"id": "data-hall-a", "name": "Data Hall A", "type": "data_hall", "aisle": "hot_cold", "racks": None, "zone": "white_space"},
        {"id": "mdf", "name": "Network / MDF", "type": "network", "racks": None, "zone": "white_space"},
        {"id": "idf", "name": "IDF Closet", "type": "network", "racks": [], "zone": "white_space"},
        {"id": "mmr", "name": "Meet-Me Room", "type": "network", "racks": [], "zone": "white_space"},
        {"id": "fef", "name": "Fiber Entrance", "type": "network", "racks": [], "zone": "white_space"},
        {"id": "cable-room", "name": "Cable Room", "type": "network", "racks": [], "zone": "white_space"},
        {"id": "mechanical", "name": "Mechanical / Cooling", "type": "mechanical", "racks": [], "zone": "plant"},
        {"id": "chillers", "name": "Chillers / Towers", "type": "mechanical", "racks": [], "zone": "exterior"},
        {"id": "electrical", "name": "Electrical", "type": "electrical", "racks": [], "zone": "plant"},
        {"id": "battery", "name": "Battery Room", "type": "electrical", "racks": [], "zone": "plant"},
        {"id": "generator-yard", "name": "Generator Yard", "type": "electrical", "racks": [], "zone": "exterior"},
        {"id": "substation", "name": "Substation / Transformers", "type": "electrical", "racks": [], "zone": "exterior"},
        {"id": "fire-suppression", "name": "Fire Suppression", "type": "safety", "racks": [], "zone": "plant"},
    ]


def campus_assets() -> dict:
    return {
        "generators": [
            {"id": "GEN-1", "kw": 2000, "fuel_pct": 92, "status": "standby"},
            {"id": "GEN-2", "kw": 2000, "fuel_pct": 88, "status": "standby"},
        ],
        "diesel_tanks": [
            {"id": "TANK-A", "liters": 40000, "level_pct": 78},
            {"id": "TANK-B", "liters": 40000, "level_pct": 81},
        ],
        "cooling_towers": [
            {"id": "CT-1", "status": "running", "approach_c": 4.2},
            {"id": "CT-2", "status": "running", "approach_c": 4.0},
        ],
        "chillers": [
            {"id": "CH-1", "tons": 500, "status": "running", "cop": 5.8},
            {"id": "CH-2", "tons": 500, "status": "standby", "cop": None},
        ],
        "transformers": [
            {"id": "XFMR-A", "kva": 2500, "status": "online", "load_pct": 54},
            {"id": "XFMR-B", "kva": 2500, "status": "online", "load_pct": 51},
        ],
        "parking": {"spaces": 48, "occupied": 12},
        "access": {"gate": "secured", "biometrics": "online", "cameras": 24},
    }
