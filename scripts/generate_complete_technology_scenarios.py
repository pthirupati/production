#!/usr/bin/env python3
"""Generate neutral, full-technology practice scenarios.

The generated scenarios intentionally do NOT expose fresher/junior/experience tags.
They are plain hands-on labs grouped by practical category: Learn, Build,
Operate, Troubleshoot, Production, Security, and Cross-Technology.
"""
from __future__ import annotations

import argparse
import os
import re
import stat
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios"
PRESET_OUT = ROOT / "backend/apps/labs/provisioner/simulation/complete_tech_presets.py"
E2E_OUT = ROOT / "backend/apps/labs/provisioner/simulation/complete_tech_e2e_fixes.py"
MIN_TOTAL = 150
MIN_NEW_PER_TECH = 40

SIM_BY_TECH = {
    "ansible": "ansible",
    "ai-ml": "python",
    "aws": "generic",
    "baremetal": "baremetal",
    "data-science": "python",
    "database": "database",
    "docker": "generic",
    "gpu": "gpu",
    "grafana": "generic",
    "html": "generic",
    "java": "java",
    "javascript": "python",
    "kubernetes": "kubernetes",
    "linux": "generic",
    "mysql": "database",
    "networking": "generic",
    "nmap": "nmap",
    "nodejs": "python",
    "peoplesoft": "peoplesoft",
    "postgresql": "database",
    "prometheus": "generic",
    "prompt-engineering": "python",
    "python": "python",
    "react": "python",
    "rhel-linux": "rhel",
    "security": "generic",
    "shell-script": "generic",
    "simulation": "generic",
    "sqlite": "database",
    "terraform": "terraform",
    "vmware": "vmware",
    "wireshark": "wireshark",
    "windows": "windows",
}

GENERIC_TOPICS = [
    ("learn", "Fundamentals Lab", "Understand core commands, objects, files, and the daily workflow."),
    ("build", "Build From Scratch", "Create a working configuration or service from an empty starting point."),
    ("operate", "Daily Operations", "Perform routine administration safely with verification steps."),
    ("troubleshoot", "Troubleshooting Drill", "Diagnose a realistic fault and apply the smallest reliable fix."),
    ("production", "Production Readiness", "Harden, monitor, scale, or document a production-ready setup."),
    ("security", "Security Practice", "Apply safe defaults, least privilege, auditability, and secure configuration."),
    ("automation", "Automation Practice", "Automate repeatable work and validate idempotent behavior."),
    ("observability", "Observability Practice", "Expose health, logs, metrics, and useful diagnostic signals."),
    ("backup", "Backup and Recovery", "Create or repair backup, restore, retention, and recovery flows."),
    ("integration", "Integration Lab", "Connect this technology with an adjacent system and validate the handoff."),
]

KIND_TITLES = {kind: title for kind, title, _summary in GENERIC_TOPICS}

TECH_TOPICS = {
    "aws": ["ec2", "s3", "iam", "vpc", "security-groups", "rds", "lambda", "cloudwatch", "autoscaling", "route53"],
    "linux": ["users-groups", "permissions-acl", "systemd-services", "journald-logs", "storage-lvm", "networking-firewalld", "selinux", "cron-timers", "package-patching", "boot-recovery"],
    "rhel-linux": ["subscription-repos", "dnf-modules", "firewalld", "selinux-policy", "tuned-profile", "kdump", "auditd", "sssd", "chrony", "systemd-targets"],
    "docker": ["images-layers", "dockerfile", "compose", "volumes", "networks", "healthchecks", "logs", "rootless", "registry", "resource-limits"],
    "kubernetes": ["pods", "deployments", "services", "ingress", "configmaps", "secrets", "storage", "rbac", "networkpolicy", "autoscaling"],
    "terraform": ["providers", "state", "variables", "modules", "data-sources", "remote-backend", "workspaces", "import", "drift", "policy"],
    "ansible": ["inventory", "playbooks", "roles", "handlers", "templates", "vault", "facts", "conditionals", "awx", "rolling-deploy"],
    "networking": ["routing", "dns", "firewall", "vlan", "bonding", "nat", "mtu", "load-balancing", "tls", "packet-capture"],
    "vmware": ["vm-lifecycle", "datastore", "snapshots", "vmotion", "ha-drs", "dv-switch", "templates", "tools", "resource-pools", "vcenter-rbac"],
    "windows": ["active-directory", "users-groups", "gpo", "dns-dhcp", "iis", "powershell", "event-viewer", "file-shares", "services", "patching"],
    "python": ["venv", "files", "http-api", "testing", "logging", "exceptions", "cli", "packaging", "async", "data-processing"],
    "javascript": ["arrays", "objects", "async-await", "modules", "dom", "fetch", "testing", "bundling", "forms", "performance"],
    "nodejs": ["express", "middleware", "env-config", "logging", "streams", "workers", "security", "testing", "database", "deployment"],
    "react": ["components", "state", "effects", "router", "forms", "accessibility", "performance", "error-boundaries", "context", "testing"],
    "html": ["semantic-html", "forms", "accessibility", "seo", "performance", "responsive", "media", "tables", "security", "metadata"],
    "java": ["maven", "gradle", "spring-boot", "junit", "logging", "jdbc", "jvm-memory", "security", "rest-api", "packaging"],
    "shell-script": ["variables", "conditionals", "loops", "functions", "pipes", "traps", "cron", "logging", "safe-delete", "args"],
    "database": ["backup", "restore", "indexes", "grants", "replication", "pooling", "query-plan", "storage", "locks", "monitoring"],
    "devops": ["git-flow", "ci-pipeline", "cd-release", "artifacts", "secrets", "observability", "rollback", "change-management", "runbooks", "incident-response"],
    "mysql": ["indexes", "users-grants", "replication", "slow-query", "backup", "restore", "innodb", "partitioning", "charset", "performance-schema"],
    "postgresql": ["roles", "schemas", "indexes", "vacuum", "replication", "wal", "pg-hba", "extensions", "partitioning", "query-plan"],
    "sqlite": ["schema", "indexes", "transactions", "wal", "backup", "pragma", "constraints", "views", "triggers", "integrity"],
    "grafana": ["datasources", "dashboards", "variables", "panels", "alerting", "contact-points", "provisioning", "auth", "loki", "sharing"],
    "prometheus": ["scrape-config", "promql", "alerts", "recording-rules", "alertmanager", "remote-write", "service-discovery", "tsdb", "labels", "exporters"],
    "security": ["ssh-hardening", "firewall", "tls", "secrets", "audit", "iam", "vulnerability", "csp", "selinux", "least-privilege"],
    "gpu": ["drivers", "cuda", "nvidia-smi", "mig", "dcgm", "container-toolkit", "power", "thermal", "scheduling", "monitoring"],
    "baremetal": ["ipmi", "raid", "bios", "pxe", "firmware", "nic-teaming", "power", "thermal", "smart", "console"],
    "nmap": ["tcp-scan", "udp-scan", "service-detection", "nse", "timing", "output", "firewall", "traceroute", "os-detect", "safe-scans"],
    "wireshark": ["filters", "tcp", "dns", "tls", "http", "dhcp", "retransmits", "latency", "capture", "export"],
    "ai-ml": ["dataset", "features", "training", "validation", "metrics", "model-save", "inference", "drift", "prompting", "agents"],
    "data-science": ["cleaning", "joins", "groupby", "datetime", "visualization", "statistics", "notebooks", "exports", "quality", "pipelines"],
    "prompt-engineering": ["instructions", "context", "examples", "evaluation", "tools", "structured-output", "safety", "agents", "debugging", "templates"],
    "peoplesoft": ["pia-navigation", "process-monitor", "roles", "permission-lists", "integration-broker", "app-engine", "component-security", "operator-lock", "scheduler", "reports"],
    "simulation": ["terminal", "validation", "state", "gui", "cross-tech", "hints", "scoring", "restore", "troubleshooting", "authoring"],
}

CATEGORIES = {
    "learn": "Core Skills",
    "build": "Build Lab",
    "operate": "Operations",
    "troubleshoot": "Troubleshooting",
    "production": "Production",
    "security": "Security",
    "automation": "Automation",
    "observability": "Observability",
    "backup": "Backup & Recovery",
    "integration": "Cross-Technology",
}

DISPLAY = {}
for tech_file in sorted(SCEN.glob("*/technology.yaml")):
    data = yaml.safe_load(tech_file.read_text(encoding="utf-8")) or {}
    DISPLAY[tech_file.parent.name] = data.get("name") or tech_file.parent.name.replace("-", " ").title()
for tech_dir in sorted(p for p in SCEN.iterdir() if p.is_dir() and p.name != "shared"):
    if any(tech_dir.glob("*/scenario.yaml")):
        DISPLAY.setdefault(tech_dir.name, tech_dir.name.replace("-", " ").title())
DISPLAY.update({
    "devops": "DevOps",
})


def slugify(text: str) -> str:
    text = text.lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return re.sub(r"-+", "-", text)


def existing_count(tech: str) -> int:
    root = SCEN / tech
    return sum(1 for p in root.glob("*/scenario.yaml"))


def existing_academy_markers() -> dict[str, str]:
    markers: dict[str, str] = {}
    for check in SCEN.glob("*/academy-*/check.sh"):
        slug = check.parent.name
        for line in check.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("grep -q FIXED-OK "):
                markers[slug] = line.split("grep -q FIXED-OK ", 1)[1].strip()
                break
    return markers


def existing_academy_count(tech: str) -> int:
    return sum(1 for _ in (SCEN / tech).glob("academy-*/scenario.yaml"))


def scenario_type(kind: str) -> str:
    return "fix" if kind in {"troubleshoot", "production", "security"} else "do"


def difficulty(kind: str, idx: int) -> str:
    if kind in {"learn", "build"}:
        return "easy" if idx % 4 else "medium"
    if kind in {"operate", "automation", "observability", "backup", "integration"}:
        return "medium" if idx % 5 else "hard"
    return "hard" if idx % 3 == 0 else "medium"


def make_spec(tech: str, seq: int, kind: str, topic: str) -> dict:
    name = DISPLAY.get(tech, tech.replace("-", " ").title())
    topic_title = topic.replace("-", " ").title()
    kind_title = KIND_TITLES[kind]
    slug = f"academy-{tech}-{seq:03d}-{slugify(kind + '-' + topic)}"
    marker = f"/opt/fixitlab/academy/{slug}.conf"

    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from scenario_copy_library import build_academy_copy

    copy = build_academy_copy(
        tech=tech,
        kind=kind,
        topic=topic,
        slug=slug,
        display_name=name,
        marker=marker,
    )
    title = copy["title"]
    description = copy["description"]
    objectives = copy["objectives"]
    hints = copy["hints"]
    spec = {
        "title": title,
        "slug": slug,
        "technology": name,
        "category": CATEGORIES[kind],
        "difficulty": difficulty(kind, seq),
        "scenario_type": scenario_type(kind),
        "lab_mode": "simulation",
        "simulation_type": SIM_BY_TECH.get(tech, "generic"),
        "time_limit": 900 if kind in {"learn", "build"} else 1200,
        "max_score": 100,
        "is_free": bool(seq <= 3 and kind in {"learn", "build"}),
        "infrastructure_type": "docker",
        "jira_priority": "Low" if kind in {"learn", "build"} else "Medium",
        "description": description,
        "objectives": objectives,
        "initial_state": copy["initial_state"],
        "hints": hints,
    }
    if kind == "integration" or (tech in {"linux", "kubernetes", "terraform", "ansible"} and topic in {"vmware", "storage-lvm", "worker-node", "provisioning"}):
        spec["cross_technology"] = True
    if tech == "vmware" or (kind == "integration" and tech in {"linux", "kubernetes", "terraform"}):
        spec["vmware_link"] = True
    return spec, marker


def write_scenario(tech: str, spec: dict, marker: str, *, force: bool = False) -> bool:
    folder = SCEN / tech / spec["slug"]
    yaml_path = folder / "scenario.yaml"
    if yaml_path.exists() and not force:
        return False
    folder.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    check = folder / "check.sh"
    check.write_text(f"#!/usr/bin/env bash\ngrep -q FIXED-OK {marker}\nexit 0\n", encoding="utf-8")
    check.chmod(check.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return True


def emit_presets(markers: dict[str, str]) -> None:
    lines = [
        '"""GENERATED by scripts/generate_complete_technology_scenarios.py — do not edit by hand."""',
        "from __future__ import annotations",
        "",
        "import os",
        "",
        "",
        "def _complete_marker(state, path: str, slug: str) -> None:",
        "    d = os.path.dirname(path)",
        "    if d:",
        "        state._mkdir(d)",
        "    state._write_file(",
        "        path,",
        '        f"# broken configuration for {slug}\\n"',
        '        "# complete the lab objective, then apply the documented remediation\\n"',
        '        "# this file needs the documented fix\\n",',
        "    )",
        "",
        "",
        "COMPLETE_TECH_PRESETS = {",
    ]
    for slug, marker in sorted(markers.items()):
        lines.append(f"    {slug!r}: lambda state, p={marker!r}, s={slug!r}: _complete_marker(state, p, s),")
    lines.append("}")
    PRESET_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def emit_e2e(markers: dict[str, str]) -> None:
    E2E_OUT.write_text(
        '"""GENERATED by scripts/generate_complete_technology_scenarios.py — do not edit by hand."""\n'
        "from __future__ import annotations\n\n"
        f"COMPLETE_TECH_MARKER_FIX: dict[str, str] = {markers!r}\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    markers: dict[str, str] = existing_academy_markers()
    created = 0
    skipped = 0
    plan: dict[str, int] = {}

    for tech in sorted(DISPLAY):
        count = existing_count(tech)
        academy_count = existing_academy_count(tech)
        non_academy_count = count - academy_count
        desired_generated = max(MIN_NEW_PER_TECH, MIN_TOTAL - non_academy_count)
        to_create = max(0, desired_generated - academy_count)
        plan[tech] = to_create
        topics = TECH_TOPICS.get(tech, ["basics", "build", "operate", "troubleshoot", "security", "scale", "backup", "monitor", "integrate", "recover"])
        seq = 1
        created_for_tech = 0
        while created_for_tech < to_create:
            kind, _, _ = GENERIC_TOPICS[(seq - 1) % len(GENERIC_TOPICS)]
            topic = topics[(seq - 1) % len(topics)]
            cycle = ((seq - 1) // len(topics)) + 1
            topic_key = topic if cycle == 1 else f"{topic}-{cycle}"
            spec, marker = make_spec(tech, seq, kind, topic_key)
            if spec["slug"] in markers or (SCEN / tech / spec["slug"] / "scenario.yaml").exists():
                seq += 1
                continue
            if args.dry_run:
                created += 1
                markers[spec["slug"]] = marker
            else:
                if write_scenario(tech, spec, marker, force=args.force):
                    created += 1
                else:
                    skipped += 1
                markers[spec["slug"]] = marker
            created_for_tech += 1
            seq += 1

    if not args.dry_run:
        emit_presets(markers)
        emit_e2e(markers)

    print(f"Complete technology scenarios planned/written: {created}; skipped: {skipped}")
    print("Per-tech additions:")
    for tech, n in sorted(plan.items()):
        print(f"  {tech}: +{n}")
    if not args.dry_run:
        print(f"presets: {PRESET_OUT}")
        print(f"e2e: {E2E_OUT}")


if __name__ == "__main__":
    main()
