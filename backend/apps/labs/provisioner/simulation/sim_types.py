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


def lab_server_banner(sim_type: str, slug: str = "") -> str:
    """Learner-facing terminal banner for the scenario's Lab Server persona."""
    st = normalize_sim_type(sim_type)
    by_type = {
        "aws": "AWS EC2 Lab Server — Amazon Linux",
        "azure": "Azure Virtual Machine — RHEL 9",
        "gcp": "Google Compute Engine VM — RHEL 9",
        "openstack": "OpenStack Instance — RHEL 9",
        "vmware": "VMware Guest — RHEL 9",
        "kubernetes": "Kubernetes Node — RHEL 9",
        "gpu": "GPU Server — RHEL 9",
        "windows": "Windows Server Lab",
        "windows-server": "Windows Server Lab",
        "baremetal": "Physical Bare Metal Server — RHEL 9",
        "commvault": "Commvault Protected Server — RHEL 9",
        "netapp": "NetApp Storage Host",
        "dellemc": "Dell EMC Storage Host",
        "datacenter": "Physical Data Center Host — RHEL 9",
        "soc": "SOC Workstation — RHEL 9",
        "terraform": "Terraform Workspace Host — RHEL 9",
        "ansible": "Ansible Control Host — RHEL 9",
        "ansible-awx": "AWX Control Host — RHEL 9",
        "docker": "Docker Host — RHEL 9",
        "networking": "Network Lab Appliance — RHEL 9",
        "grafana": "Observability Host — RHEL 9",
        "prometheus": "Observability Host — RHEL 9",
        "rhel": "Linux Lab Server — RHEL 9",
        "generic": "Linux Lab Server — RHEL 9",
    }
    s = (slug or "").lower()
    if st == "generic":
        if s.startswith(("academy-aws", "aws-", "ec2-")):
            return by_type["aws"]
        if s.startswith(("academy-azure", "azure-")):
            return by_type["azure"]
        if s.startswith(("academy-gcp", "gcp-")):
            return by_type["gcp"]
        if s.startswith(("academy-openstack", "openstack-")):
            return by_type["openstack"]
    return by_type.get(st, "Linux Lab Server — RHEL 9")


def hostname_for_type(sim_type: str, slug: str = "") -> str:
    defaults = {
        "generic": "rhel-lab",
        "rhel": "rhel-lab",
        "kubernetes": "k8s-master",
        "gpu": "gpu-node",
        "baremetal": "bmc-host",
        "database": "db-server",
        "ansible": "ansible-control",
        "python": "dev-server",
        "java": "dev-server",
        "vmware": "vcenter-lab",
        "terraform": "terraform-ws",
        "windows": "WIN-SRV-01",
        "devops": "gitlab-runner",
        "networking": "core-router",
        "grafana": "grafana-lab",
        "prometheus": "prometheus-lab",
        "commvault": "commvault-commcell",
        "netapp": "netapp-ontap",
        "dellemc": "dellemc-unisphere",
        "datacenter": "dcim-console",
        "soc": "soc-siem",
        "azure": "vm-web01",
        "gcp": "web01",
        "openstack": "web-01",
        "aws": "ip-10-0-1-25",
    }
    if "ansible" in slug:
        return "ansible-control"
    if "gpu" in slug or "nvidia" in slug:
        return "gpu-node"
    if "k8s" in slug or "kubernetes" in slug:
        return "k8s-master"
    return defaults.get(sim_type, "rhel-lab")


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
