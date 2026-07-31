"""Lab Server hosting persona — OS identity, DMI, and Hosted-as labels.

The terminal IS the guest OS of the scenario's Lab Server. Banner, /etc/os-release,
and dmidecode must agree with where that server is hosted (AWS EC2, Azure VM,
GCE, VMware guest, bare metal, etc.).
"""

from __future__ import annotations

import hashlib
from typing import Any

# Platforms that shape guest OS + hardware identity in the Lab Terminal.
HOST_PLATFORMS = (
    "aws",
    "azure",
    "gcp",
    "vmware",
    "openstack",
    "baremetal",
    "datacenter",
    "linux",
)

_AMAZON_LINUX_RELEASE = (
    'NAME="Amazon Linux"\n'
    'VERSION="2023"\n'
    'ID="amzn"\n'
    'ID_LIKE="fedora"\n'
    'VERSION_ID="2023"\n'
    'PLATFORM_ID="platform:al2023"\n'
    'PRETTY_NAME="Amazon Linux 2023.4.20240416"\n'
    'ANSI_COLOR="0;33"\n'
    'CPE_NAME="cpe:2.3:o:amazon:amazon_linux:2023"\n'
    'HOME_URL="https://aws.amazon.com/linux/amazon-linux-2023/"\n'
    'SUPPORT_END="2028-03-15"\n'
)

_RHEL_OS_RELEASE = (
    'NAME="Red Hat Enterprise Linux"\n'
    'VERSION="9.3 (Plow)"\n'
    'ID="rhel"\n'
    'ID_LIKE="fedora"\n'
    'VERSION_ID="9.3"\n'
    'PRETTY_NAME="Red Hat Enterprise Linux 9.3 (Plow)"\n'
    'ANSI_COLOR="0;31"\n'
    'CPE_NAME="cpe:/o:redhat:enterprise_linux:9::baseos"\n'
)

# dmidecode -t 1 style identity per hosting platform
_DMI: dict[str, tuple[str, str]] = {
    "aws": ("Amazon EC2", "m7i.large"),
    "azure": ("Microsoft Corporation", "Virtual Machine"),
    "gcp": ("Google", "Google Compute Engine"),
    "vmware": ("VMware, Inc.", "VMware Virtual Platform"),
    "openstack": ("OpenStack Foundation", "OpenStack Nova"),
    "baremetal": ("HPE", "ProLiant DL380 Gen10"),
    "datacenter": ("HPE", "ProLiant DL380 Gen10"),
    "linux": ("Red Hat", "KVM"),
}

_HOSTED_AS: dict[str, str] = {
    "aws": "Hosted as: AWS EC2 Instance (same guest as AWS Console)",
    "azure": "Hosted as: Azure Virtual Machine (same guest as Azure Portal)",
    "gcp": "Hosted as: Google Compute Engine VM (same guest as GCP Console)",
    "vmware": "Hosted as: VMware Virtual Machine (same guest as vCenter)",
    "openstack": "Hosted as: OpenStack Instance (same guest as Horizon)",
    "baremetal": "Hosted as: Physical Bare Metal Server",
    "datacenter": "Hosted as: Physical rack server (same host as Data Center Floor)",
    "linux": "Hosted as: Linux Lab Server (scenario-scoped)",
}

# Linux / generic labs without an explicit cloud sim_type still need a real
# hosting story (VMware / AWS / Azure / GCP / bare metal). Deterministic by slug.
_LINUX_HOST_ROTATION = ("vmware", "aws", "azure", "gcp", "baremetal")


def _slug_hash_pick(slug: str, choices: tuple[str, ...]) -> str:
    digest = hashlib.sha256((slug or "lab").encode("utf-8")).hexdigest()
    return choices[int(digest[:8], 16) % len(choices)]


def _load_scenario_yaml(slug: str) -> dict:
    """Load scenario.yaml for ``slug`` (empty dict if missing)."""
    if not slug:
        return {}
    try:
        from pathlib import Path
        import yaml

        root = Path(__file__).resolve().parents[5] / "scenarios"
        if not root.is_dir():
            return {}
        for candidate in root.rglob("scenario.yaml"):
            if candidate.parent.name != slug:
                continue
            data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def load_scenario_hosted_as(slug: str) -> str | None:
    """Read optional ``hosted_as`` / ``hosting_platform`` from scenario.yaml."""
    data = _load_scenario_yaml(slug)
    if not data:
        return None
    raw = data.get("hosted_as") or data.get("hosting_platform")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    for decl in data.get("lab_servers") or []:
        if not isinstance(decl, dict):
            continue
        h = decl.get("hosted_as") or decl.get("hosting_platform")
        if isinstance(h, str) and h.strip():
            return h.strip().lower()
        persona = str(decl.get("persona") or "").lower()
        if persona in HOST_PLATFORMS and persona not in ("linux",):
            return persona
    return None


def resolve_host_platform(
    sim_type: str = "",
    slug: str = "",
    *,
    tech_slug: str = "",
    hosted_as: str | None = None,
) -> str:
    """Return the hosting platform key for OS identity + Hosted-as banner."""
    st = (sim_type or "").strip().lower()
    tech = (tech_slug or "").strip().lower()
    low = (slug or "").lower()
    meta = _load_scenario_yaml(slug) if slug else {}
    if not tech:
        tech = str(meta.get("technology") or "").strip().lower()
    explicit = (hosted_as or "").strip().lower() or load_scenario_hosted_as(slug)

    if explicit in HOST_PLATFORMS:
        return explicit
    if explicit in ("ec2", "amazon"):
        return "aws"
    if explicit in ("gce", "google"):
        return "gcp"
    if explicit in ("vsphere", "vcenter"):
        return "vmware"
    if explicit in ("physical", "ipmi", "maas"):
        return "baremetal"

    # Explicit VMware companion / NIC-disk cross-tech labs are VMware guests.
    if meta.get("vmware_link") is True or low.startswith(("linux-nic-add-vmware", "linux-disk-add-vmware")):
        return "vmware"

    if st in ("aws", "azure", "gcp", "vmware", "openstack", "baremetal", "datacenter"):
        return st
    if tech in ("aws", "azure", "gcp", "vmware", "openstack", "baremetal", "datacenter"):
        return tech

    if low.startswith(("academy-aws", "aws-", "ec2-")) or tech == "aws":
        return "aws"
    if low.startswith(("academy-azure", "azure-")) or tech == "azure":
        return "azure"
    if low.startswith(("academy-gcp", "gcp-")) or tech == "gcp":
        return "gcp"
    if low.startswith(("academy-openstack", "openstack-")) or tech == "openstack":
        return "openstack"
    if low.startswith(("academy-vmware", "vmware-", "vm-")) or tech == "vmware":
        return "vmware"
    if low.startswith(("academy-baremetal", "baremetal-", "maas-")) or tech == "baremetal":
        return "baremetal"
    if low.startswith(("academy-datacenter", "datacenter-", "dc-")) or tech == "datacenter":
        return "datacenter"

    # App / coding / automation techs must not rotate onto fake cloud DMI
    # (PeopleSoft looking like EC2, JS academy looking like Azure, etc.).
    _NO_ROTATE = (
        "peoplesoft", "javascript", "react", "java", "html", "shell-script", "nodejs",
        "python", "ansible", "ansible-awx", "gitops", "ai-ml", "data-science",
        "prompt-engineering", "ai-infra", "gpu",
    )
    if (
        tech in _NO_ROTATE
        or st in _NO_ROTATE
        or low.startswith((
            "ps-", "peoplesoft-", "academy-peoplesoft",
            "academy-javascript", "academy-react", "academy-java", "academy-html",
            "academy-shell", "js-", "react-", "java-", "html-", "shell-",
            "academy-ai-infra", "ai-infra-", "academy-gpu", "gpu-",
        ))
    ):
        return "linux"

    # Pure Linux / RHEL / generic practice labs: rotate hosting for realism.
    _ROTATE_TYPES = (
        "generic", "rhel", "linux", "", "devops", "docker", "networking",
        "grafana", "prometheus", "database", "security", "simulation",
    )
    if st in _ROTATE_TYPES or tech in _ROTATE_TYPES or tech in ("linux", "rhel", ""):
        return _slug_hash_pick(low or tech or "linux", _LINUX_HOST_ROTATION)

    return "linux"


def hosted_as_line(platform: str) -> str:
    return _HOSTED_AS.get(platform, _HOSTED_AS["linux"])


def dmi_for_platform(platform: str) -> tuple[str, str]:
    return _DMI.get(platform, _DMI["linux"])


def apply_hosting_persona(state: Any, platform: str, *, slug: str = "") -> None:
    """Rewrite guest OS release files + DMI fields to match hosting platform."""
    platform = (platform or "linux").lower()
    manufacturer, product = dmi_for_platform(platform)
    state.dmi_manufacturer = manufacturer
    state.dmi_product = product
    state.host_platform = platform

    if platform == "aws":
        state.os_release = "Amazon Linux 2023.4.20240416"
        state.kernel = getattr(state, "kernel", None) or "6.1.82-99.168.amzn2023.x86_64"
        state._write_file("/etc/os-release", _AMAZON_LINUX_RELEASE)
        state._write_file("/etc/system-release", "Amazon Linux release 2023 (Amazon Linux)\n")
        # Amazon Linux has no /etc/redhat-release by default; remove RHEL marker.
        if "/etc/redhat-release" in getattr(state, "vfs", {}):
            try:
                del state.vfs["/etc/redhat-release"]
            except Exception:
                pass
        state._write_file(
            "/proc/version",
            f"Linux version {state.kernel} (mockbuild@amazon) "
            f"(gcc (GCC) 11.4.1 20230605 (Red Hat 11.4.1-2)) #1 SMP PREEMPT_DYNAMIC\n",
        )
        # Prefer EC2-style hostname when still on the generic lab default.
        hn = (getattr(state, "hostname", "") or "").lower()
        if hn in ("rhel-lab", "rhel-sim", "lab-server", "bmc-host") and not (slug or "").startswith("ip-"):
            ip = "172.31.14.52"
            try:
                addrs = (state.network_ifs or {}).get("eth0", {}).get("addrs") or []
                if addrs:
                    ip = str(addrs[0]).split("/")[0]
            except Exception:
                pass
            if hasattr(state, "set_hostname"):
                state.set_hostname(f"ip-{ip.replace('.', '-')}")
            if hasattr(state, "set_host_ip"):
                state.set_host_ip(ip)
        return

    # Azure / GCP / VMware / OpenStack / bare metal / linux → RHEL guest identity
    state.os_release = "Red Hat Enterprise Linux 9.3 (Plow)"
    state._write_file("/etc/os-release", _RHEL_OS_RELEASE)
    state._write_file("/etc/redhat-release", state.os_release + "\n")
    state._write_file("/etc/system-release", state.os_release + "\n")
    if platform == "vmware":
        state._write_file(
            "/sys/class/dmi/id/sys_vendor",
            "VMware, Inc.\n",
        )
        state._write_file("/sys/class/dmi/id/product_name", "VMware Virtual Platform\n")
    elif platform == "azure":
        state._write_file("/sys/class/dmi/id/sys_vendor", "Microsoft Corporation\n")
        state._write_file("/sys/class/dmi/id/product_name", "Virtual Machine\n")
    elif platform == "gcp":
        state._write_file("/sys/class/dmi/id/sys_vendor", "Google\n")
        state._write_file("/sys/class/dmi/id/product_name", "Google Compute Engine\n")
