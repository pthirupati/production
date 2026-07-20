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


def infer_sim_type(
    raw: str | None,
    slug: str = "",
    technology: str = "",
) -> str:
    """Normalize simulation_type, promoting cloud/gitops slugs out of generic.

    Many academy YAML files still ship ``simulation_type: generic`` even when
    ``technology: aws`` / slug is ``academy-aws-*``. Without promotion the Lab
    Terminal boots a plain RHEL bare-metal persona while the banner says AWS.
    """
    st = normalize_sim_type(raw)
    low = (slug or "").lower()
    tech = (technology or "").strip().lower()
    if st != "generic":
        # Still map gitops → devops for CI GUI modules
        if tech in ("gitops", "github") or low.startswith(("academy-gitops", "gitops-")):
            if st in ("generic", "rhel"):
                return "devops"
        return st
    if tech == "aws" or low.startswith(("academy-aws", "aws-", "ec2-")):
        return "aws"
    if tech == "azure" or low.startswith(("academy-azure", "azure-")):
        return "azure"
    if tech == "gcp" or low.startswith(("academy-gcp", "gcp-")):
        return "gcp"
    if tech == "openstack" or low.startswith(("academy-openstack", "openstack-")):
        return "openstack"
    if tech == "vmware" or low.startswith(("academy-vmware", "vmware-")):
        return "vmware"
    if tech in ("gitops", "github", "devops") or low.startswith(
        ("academy-gitops", "gitops-", "academy-devops", "devops-")
    ):
        return "devops"
    if tech == "baremetal" or low.startswith(("academy-baremetal", "baremetal-")):
        return "baremetal"
    return st


def lab_server_banner(sim_type: str, slug: str = "") -> str:
    """Learner-facing terminal banner for the scenario's Lab Server persona."""
    st = infer_sim_type(sim_type, slug)
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
        "devops": "GitOps / CI Lab Server — RHEL 9",
        "rhel": "Linux Lab Server — RHEL 9",
        "generic": "Linux Lab Server — RHEL 9",
    }
    try:
        from .hosting_persona import resolve_host_platform

        platform = resolve_host_platform(st, slug)
        platform_banners = {
            "aws": by_type["aws"],
            "azure": by_type["azure"],
            "gcp": by_type["gcp"],
            "openstack": by_type["openstack"],
            "vmware": by_type["vmware"],
            "baremetal": by_type["baremetal"],
            "datacenter": by_type["datacenter"],
        }
        if st in ("generic", "rhel", "linux") and platform in platform_banners:
            return platform_banners[platform]
        if platform == "aws" and st == "aws":
            return by_type["aws"]
    except Exception:
        pass
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
    low = (slug or "").lower()
    if "ansible" in low:
        return "ansible-control"
    if "gpu" in low or "nvidia" in low:
        return "gpu-node"
    if "k8s" in low or "kubernetes" in low:
        return "k8s-master"
    st = infer_sim_type(sim_type, slug)
    if st == "aws" or low.startswith(("academy-aws", "aws-", "ec2-")):
        return "ip-172-31-14-52"
    if st == "devops" or low.startswith(("academy-gitops", "gitops-")):
        return "gitops-runner"
    return defaults.get(st, defaults.get(sim_type, "rhel-lab"))


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
