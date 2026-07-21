"""Enterprise hardware catalogs for the datacenter digital twin.

Typed reference data (OEMs, CPUs, GPUs, cables, switches). Used to seed
inventory, enrich servers, and drive failure/training scenarios. Not a
photoreal mesh library — Lab Environment catalog authority.
"""

from __future__ import annotations

SERVER_OEMS = [
    "Dell", "HP", "HPE", "Lenovo", "Cisco", "Supermicro",
    "Gigabyte", "ASUS", "Inspur", "Quanta", "Wiwynn", "Open Compute",
]

# Profiles used to seed the live floor fleet (subset of SERVER_OEMS with models).
FLEET_SERVER_PROFILES = [
    {"vendor": "Dell", "model": "PowerEdge R750", "tag_prefix": "DL"},
    {"vendor": "HPE", "model": "ProLiant DL380 Gen10", "tag_prefix": "MX"},
    {"vendor": "Lenovo", "model": "ThinkSystem SR650 V3", "tag_prefix": "LN"},
    {"vendor": "Supermicro", "model": "SYS-221H-TNR", "tag_prefix": "SM"},
    {"vendor": "Cisco", "model": "UCS C240 M6", "tag_prefix": "UC"},
    {"vendor": "Gigabyte", "model": "G292-Z43", "tag_prefix": "GB"},
    {"vendor": "ASUS", "model": "ESC8000A-E12", "tag_prefix": "AS"},
    {"vendor": "Inspur", "model": "NF5280M6", "tag_prefix": "IN"},
    {"vendor": "Quanta", "model": "Grid D52BQ-2U", "tag_prefix": "QT"},
    {"vendor": "Wiwynn", "model": "SV7220G3", "tag_prefix": "WW"},
    {"vendor": "Open Compute", "model": "OCP Tioga Pass", "tag_prefix": "OC"},
]


def fleet_profile_for(*, vendor: str | None = None, rack_num: int = 1) -> dict:
    """Pick a live-fleet OEM profile by vendor override or rack rotation."""
    if vendor:
        v = vendor.upper()
        for p in FLEET_SERVER_PROFILES:
            if p["vendor"].upper() == v or (v == "HP" and p["vendor"] == "HPE"):
                return p
        # Alias HP → HPE already handled; unknown vendors fall through to Dell
        return FLEET_SERVER_PROFILES[0]
    return FLEET_SERVER_PROFILES[(max(1, rack_num) - 1) % len(FLEET_SERVER_PROFILES)]

CPU_CATALOG = [
    {"vendor": "Intel", "family": "Xeon Scalable", "gen": "Ice Lake", "socket": "LGA4189", "example": "Gold 6338"},
    {"vendor": "Intel", "family": "Xeon Scalable", "gen": "Emerald Rapids", "socket": "LGA4677", "example": "Gold 6548Y+"},
    {"vendor": "Intel", "family": "Xeon D", "gen": "Ice Lake-D", "socket": "FCBGA2579", "example": "D-2796TE"},
    {"vendor": "Intel", "family": "Xeon Max", "gen": "Sapphire Rapids HBM", "socket": "LGA4677", "example": "9480"},
    {"vendor": "AMD", "family": "EPYC", "gen": "Naples", "socket": "SP3", "example": "7601"},
    {"vendor": "AMD", "family": "EPYC", "gen": "Rome", "socket": "SP3", "example": "7742"},
    {"vendor": "AMD", "family": "EPYC", "gen": "Milan", "socket": "SP3", "example": "7763"},
    {"vendor": "AMD", "family": "EPYC", "gen": "Genoa", "socket": "SP5", "example": "9654"},
    {"vendor": "AMD", "family": "EPYC", "gen": "Turin", "socket": "SP5", "example": "9965"},
    {"vendor": "Ampere", "family": "Altra", "gen": "ARM Neoverse", "socket": "LGA4926", "example": "M128-30"},
    {"vendor": "NVIDIA", "family": "Grace", "gen": "Grace", "socket": "custom", "example": "Grace CPU"},
    {"vendor": "Apple", "family": "Silicon", "gen": "M-series server", "socket": "SoC", "example": "M2 Ultra"},
    {"vendor": "IBM", "family": "Power", "gen": "Power10", "socket": "custom", "example": "Power10"},
]

GPU_CATALOG = [
    {"family": "DGX", "model": "DGX H100", "gpus": 8, "memory_gb": 640},
    {"family": "HGX", "model": "HGX H100", "gpus": 8, "memory_gb": 640},
    {"family": "MGX", "model": "MGX Grace Hopper", "gpus": 1, "memory_gb": 96},
    {"family": "GB200", "model": "GB200 NVL72", "gpus": 72, "memory_gb": 13824},
    {"family": "GB300", "model": "GB300", "gpus": 72, "memory_gb": 0},
    {"family": "Grace Hopper", "model": "GH200", "gpus": 1, "memory_gb": 96},
    {"family": "Grace Blackwell", "model": "GB200", "gpus": 2, "memory_gb": 384},
    {"family": "Data Center", "model": "A100 80GB", "gpus": 1, "memory_gb": 80},
    {"family": "Data Center", "model": "H100 80GB", "gpus": 1, "memory_gb": 80},
    {"family": "Data Center", "model": "H200", "gpus": 1, "memory_gb": 141},
    {"family": "Data Center", "model": "B200", "gpus": 1, "memory_gb": 192},
    {"family": "Data Center", "model": "L40S", "gpus": 1, "memory_gb": 48},
    {"family": "Data Center", "model": "A40", "gpus": 1, "memory_gb": 48},
    {"family": "Data Center", "model": "A30", "gpus": 1, "memory_gb": 24},
    {"family": "Data Center", "model": "A16", "gpus": 1, "memory_gb": 16},
    {"family": "Data Center", "model": "A2", "gpus": 1, "memory_gb": 16},
    {"family": "RTX", "model": "RTX 6000 Ada", "gpus": 1, "memory_gb": 48},
    {"family": "RTX Pro", "model": "RTX PRO 6000", "gpus": 1, "memory_gb": 96},
    {"family": "Tesla", "model": "Tesla V100", "gpus": 1, "memory_gb": 32},
]

CABLE_TYPES = [
    "RJ45", "Cat5", "Cat6", "Cat6A", "Cat7", "Cat8",
    "Twinax", "DAC", "AOC",
    "Fiber-LC", "Fiber-SC", "Fiber-ST", "MPO",
    "QSFP", "OSFP",
    "Power-C13", "Power-C19", "Ground",
    "USB", "Serial", "VGA", "HDMI", "DisplayPort",
    "KVM", "IPMI", "Management", "Console",
]

SWITCH_OEMS = [
    {"vendor": "Cisco", "models": ["Nexus 93180YC-FX", "Catalyst 9300"]},
    {"vendor": "Juniper", "models": ["QFX5120", "MX204"]},
    {"vendor": "Arista", "models": ["7050CX3", "7280R3"]},
    {"vendor": "NVIDIA", "models": ["Spectrum-4 SN5600", "Spectrum-3"]},
    {"vendor": "Mellanox", "models": ["SN3700", "SN2700"]},
    {"vendor": "Dell", "models": ["S5248F-ON", "Z9664F-ON"]},
    {"vendor": "Extreme", "models": ["9920", "7520"]},
]

RAID_CONTROLLERS = [
    "Dell PERC H755", "Dell PERC H740P",
    "HPE Smart Array P408i", "HPE Smart Array E208i",
    "LSI MegaRAID 9560", "Broadcom 9500-8i", "Adaptec SmartRAID 3154",
    "mdadm", "Windows Storage Spaces", "ZFS", "Ceph",
]

BMC_PRODUCTS = {
    "Dell": ["iDRAC8", "iDRAC9", "iDRAC10"],
    "HPE": ["iLO4", "iLO5", "iLO6"],
    "HP": ["iLO4", "iLO5", "iLO6"],
    "Lenovo": ["XClarity Controller"],
    "Supermicro": ["IPMI AST2600"],
    "OpenBMC": ["OpenBMC"],
}

FAILURE_PRESETS = [
    {"id": "psu", "label": "Failed PSU", "component": "power", "target": "server"},
    {"id": "dimm", "label": "Failed DIMM / ECC", "component": "dimm", "target": "server"},
    {"id": "cpu", "label": "CPU Failure", "component": "cpu", "target": "server"},
    {"id": "fan", "label": "Fan Failure", "component": "fan", "target": "server"},
    {"id": "ssd", "label": "SSD Failure", "component": "disk", "target": "server"},
    {"id": "raid", "label": "RAID Failure", "component": "raid", "target": "server"},
    {"id": "gpu", "label": "GPU Failure", "component": "gpu", "target": "server"},
    {"id": "gpu_driver", "label": "GPU Driver / CUDA", "component": "gpu", "target": "server", "detail": "driver"},
    {"id": "nvlink", "label": "NVLink Failure", "component": "pcie", "target": "server", "detail": "nvlink"},
    {"id": "firmware", "label": "Firmware Corruption", "component": "firmware", "target": "server"},
    {"id": "switch", "label": "Switch Failure", "component": "switch", "target": "network"},
    {"id": "fiber", "label": "Fiber Cut", "component": "cable", "target": "server", "detail": "fiber"},
    {"id": "ups", "label": "UPS Failure", "component": "ups", "target": "facility"},
    {"id": "cooling", "label": "Cooling Failure", "component": "cooling", "target": "facility"},
    {"id": "thermal", "label": "Thermal Runaway", "component": "cooling", "target": "facility", "detail": "thermal"},
    {"id": "water", "label": "Water Leak", "component": "leak", "target": "facility"},
    {"id": "smoke", "label": "Smoke Detection", "component": "fire", "target": "facility"},
    {"id": "bgp", "label": "BGP Failure", "component": "bgp", "target": "network"},
    {"id": "vlan", "label": "VLAN Misconfiguration", "component": "vlan", "target": "network"},
    {"id": "dns", "label": "DNS Failure", "component": "dns", "target": "network"},
    {"id": "dhcp", "label": "DHCP Failure", "component": "dhcp", "target": "network"},
    {"id": "pxe", "label": "PXE Failure", "component": "pxe", "target": "server"},
]


def full_catalog() -> dict:
    return {
        "server_oems": SERVER_OEMS,
        "fleet_profiles": FLEET_SERVER_PROFILES,
        "cpus": CPU_CATALOG,
        "gpus": GPU_CATALOG,
        "cables": CABLE_TYPES,
        "switches": SWITCH_OEMS,
        "raid_controllers": RAID_CONTROLLERS,
        "bmc_products": BMC_PRODUCTS,
        "failure_presets": FAILURE_PRESETS,
    }
