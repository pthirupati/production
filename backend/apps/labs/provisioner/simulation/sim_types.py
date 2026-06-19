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
    "terraform": "Terraform / AWS IaC Simulation",
    "windows": "Windows Server Simulation",
    "devops": "DevOps / CI-CD Simulation",
    "networking": "Networking / BGP Simulation",
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
        "terraform": "terraform-ws",
        "windows": "WIN-SRV-SIM",
        "devops": "gitlab-runner",
        "networking": "core-router",
    }
    if "ansible" in slug:
        return "ansible-control"
    if "gpu" in slug or "nvidia" in slug:
        return "gpu-node"
    if "k8s" in slug or "kubernetes" in slug:
        return "k8s-master"
    return defaults.get(sim_type, "rhel-sim")


def boot_console_for(scenario_slug: str, sim_type: str) -> bool:
    """Show the RHEL boot/GRUB console at lab start.

    Gate on the SCENARIO (boot-related slug keywords) rather than the persona.
    Previously this only fired for sim_type=="rhel", so the rich boot sequence
    (GRUB menu, kernel select, initramfs, mount, login) was dead for the far more
    common "generic" persona. Non-boot scenarios still get an immediate shell.
    """
    s = (scenario_slug or "").lower()
    if sim_type in ("windows", "terraform", "devops", "networking"):
        # These personas have their own surfaces and never use the RHEL boot flow.
        return False
    return any(k in s for k in (
        "boot", "grub", "initramfs", "mbr", "kernel-panic", "dracut", "patching",
    ))
