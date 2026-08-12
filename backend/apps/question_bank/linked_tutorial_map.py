"""Map dangling ``*-fundamentals`` tutorial refs to real course_slugs (audit §C1).

YAML historically pointed every scenario at ``<tech>-fundamentals``. Real courses
use ``<tech>-…-zero-hero``. Seed ingest and the one-shot YAML rewrite both apply
this table so the Scenario field and the catalog stay aligned.
"""

from __future__ import annotations

# Dangling linked_tutorial value → real apps.tutorials course_slug.
# Three techs have no course yet — map to "" so the link is omitted rather than
# advertising a 404.
LINKED_TUTORIAL_MAP: dict[str, str] = {
    "aws-fundamentals": "aws-cloud-zero-hero",
    "linux-fundamentals": "linux-sysadmin-zero-hero",
    "gpu-fundamentals": "gpu-nvidia-zero-hero",
    "windows-fundamentals": "windows-server-zero-hero",
    "terraform-fundamentals": "terraform-iac-zero-hero",
    "database-fundamentals": "database-engineering-zero-hero",
    "postgresql-fundamentals": "postgresql-dba-zero-hero",
    "nodejs-fundamentals": "nodejs-zero-hero",
    "rhel-linux-fundamentals": "rhel-linux-zero-hero",
    "devops-fundamentals": "devops-engineering-zero-hero",
    "docker-fundamentals": "docker-containers-zero-hero",
    "python-fundamentals": "python-devops-zero-hero",
    "peoplesoft-fundamentals": "peoplesoft-zero-hero",
    "data-science-fundamentals": "data-science-zero-hero",
    "security-fundamentals": "cybersecurity-zero-hero",
    "prompt-engineering-fundamentals": "prompt-engineering-zero-hero",
    "networking-fundamentals": "tcpip-networking-zero-hero",
    "baremetal-fundamentals": "bare-metal-datacenter-zero-hero",
    "grafana-fundamentals": "grafana-visualization-zero-hero",
    "java-fundamentals": "java-zero-hero",
    "html-fundamentals": "html-web-zero-hero",
    "sqlite-fundamentals": "sqlite-embedded-zero-hero",
    "ansible-fundamentals": "ansible-automation-zero-hero",
    "ai-ml-fundamentals": "ai-infrastructure-zero-hero",
    "shell-script-fundamentals": "bash-shell-zero-hero",
    "mysql-fundamentals": "mysql-dba-zero-hero",
    "prometheus-fundamentals": "prometheus-grafana-zero-hero",
    "javascript-fundamentals": "javascript-language-zero-hero",
    "nmap-fundamentals": "nmap-zero-hero",
    "kubernetes-fundamentals": "kubernetes-platform-zero-hero",
    "react-fundamentals": "react-frontend-zero-hero",
    "wireshark-fundamentals": "wireshark-zero-hero",
    "vmware-fundamentals": "vmware-vsphere-zero-hero",
    "devsecops-supplychain-fundamentals": "devsecops-zero-hero",
    "gitops-fundamentals": "argocd-gitops-zero-hero",
    "opentelemetry-fundamentals": "jaeger-tracing-zero-hero",
    "service-mesh-fundamentals": "kubernetes-deep-zero-hero",
    "soc-fundamentals": "soc-operations-zero-hero",
    "azure-fundamentals": "azure-cloud-zero-hero",
    "gcp-fundamentals": "gcp-cloud-zero-hero",
    "datacenter-fundamentals": "bare-metal-datacenter-zero-hero",
    # No course authored yet — blank the link rather than keep a dead slug.
    "netapp-fundamentals": "",
    "commvault-fundamentals": "",
    "dellemc-fundamentals": "",
}


def resolve_linked_tutorial(raw: str | None) -> str:
    """Return the course_slug to persist, applying the §C1 map when needed."""
    value = (raw or "").strip()
    if not value:
        return ""
    if value in LINKED_TUTORIAL_MAP:
        return LINKED_TUTORIAL_MAP[value]
    return value
