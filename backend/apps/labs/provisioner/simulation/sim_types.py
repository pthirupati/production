"""Normalize legacy simulation_type values to unified categories."""

from __future__ import annotations

# Unified simulation personas shown in admin
UNIFIED_SIM_TYPES = {
    "generic": "Normal Simulation (full RHEL — all technologies)",
    "rhel": "RHEL Linux Simulation",
    "kubernetes": "Kubernetes Simulation",
    "gpu": "GPU / NVIDIA Simulation",
    "baremetal": "Bare Metal / IPMI Simulation",
    "vmware": "VMware vCenter Simulation",
    "database": "Database Simulation",
    "ansible": "Ansible Simulation",
    "python": "Python Simulation",
    "java": "Java Development Simulation",
}

_LEGACY_MAP = {
    "none": "generic",
    "normal": "generic",
    "boot": "rhel",
    "patching": "rhel",
    "html": "rhel",
    "shell_script": "rhel",
    "docker": "generic",
    "k8s": "kubernetes",
}


def normalize_sim_type(raw: str | None) -> str:
    """Map DB/YAML simulation_type to unified persona."""
    key = (raw or "generic").strip().lower()
    if key in UNIFIED_SIM_TYPES:
        return key
    return _LEGACY_MAP.get(key, "generic")


def hostname_for_type(sim_type: str, slug: str = "") -> str:
    defaults = {
        "generic": "rhel-sim",
        "rhel": "rhel-sim",
        "kubernetes": "k8s-master",
        "gpu": "gpu-node",
        "baremetal": "bmc-host",
        "database": "db-server",
        "ansible": "ansible-control",
        "python": "dev-server",
        "java": "dev-server",
        "vmware": "vcenter-sim",
    }
    if "ansible" in slug:
        return "ansible-control"
    if "gpu" in slug or "nvidia" in slug:
        return "gpu-node"
    if "k8s" in slug or "kubernetes" in slug:
        return "k8s-master"
    return defaults.get(sim_type, "rhel-sim")


def boot_console_for(scenario_slug: str, sim_type: str) -> bool:
    """RHEL boot/GRUB console at lab start."""
    s = scenario_slug.lower()
    if sim_type == "rhel":
        return any(k in s for k in ("boot", "grub", "initramfs", "mbr", "kernel-panic", "dracut", "patching"))
    return False
