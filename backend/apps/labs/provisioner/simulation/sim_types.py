"""Normalize legacy simulation_type values to unified categories."""

from __future__ import annotations

# Unified lab personas shown in admin (learner-facing labels — never "Simulation")
UNIFIED_SIM_TYPES = {
    "generic": "Linux Lab Server (full RHEL — all technologies)",
    "rhel": "RHEL Linux Lab Server",
    "kubernetes": "Kubernetes Cluster Lab",
    "gpu": "GPU / NVIDIA Lab Server",
    "baremetal": "Bare Metal / IPMI Lab",
    "vmware": "VMware vCenter Lab",
    "database": "Database Lab Server",
    "ansible": "Ansible Control Lab",
    "ansible-awx": "Ansible AWX / Tower Lab",
    "python": "Python Development Lab",
    "java": "Java Development Lab",
    "terraform": "Terraform / AWS IaC Lab",
    "windows": "Windows Server Lab",
    "devops": "DevOps / CI-CD Lab",
    "networking": "Networking / BGP Lab",
    "grafana": "Grafana Observability Lab",
    "prometheus": "Prometheus Monitoring Lab",
    "commvault": "Commvault CommCell Lab",
    "netapp": "NetApp ONTAP System Manager Lab",
    "dellemc": "Dell EMC Unisphere / PowerMax Lab",
    "datacenter": "Physical Data Center (DCIM) Lab",
    "soc": "SOC / SIEM Analyst Lab",
    "azure": "Microsoft Azure Portal Lab",
    "gcp": "Google Cloud Console Lab",
    "openstack": "OpenStack Horizon Lab",
    "aws": "AWS Management Console Lab",
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
    "monitoring": "grafana",
    "loki": "grafana",
    "alertmanager": "prometheus",
    "promql": "prometheus",
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
        "grafana": "grafana-sim",
        "prometheus": "prometheus-sim",
        "commvault": "commvault-commcell",
        "netapp": "netapp-ontap",
        "dellemc": "dellemc-unisphere",
        "datacenter": "dcim-console",
        "soc": "soc-siem",
        "azure": "vm-web01",
        "gcp": "web01",
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
    if sim_type in (
        "windows", "terraform", "devops", "networking",
        "commvault", "netapp", "dellemc", "datacenter", "soc", "azure", "gcp",
    ):
        # These personas have their own surfaces and never use the RHEL boot flow.
        return False
    return any(k in s for k in (
        "boot", "grub", "initramfs", "mbr", "kernel-panic", "dracut", "patching",
    ))
