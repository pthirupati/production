"""Rich, beginner-friendly scenario copy for academy labs.

Used by generate_complete_technology_scenarios.py and enrich_scenario_copy.py.
"""
from __future__ import annotations

import re
from typing import Any

KINDS = (
    "learn",
    "build",
    "operate",
    "troubleshoot",
    "production",
    "security",
    "automation",
    "observability",
    "backup",
    "integration",
)

KIND_LABELS = {
    "learn": "Fundamentals Lab",
    "build": "Build From Scratch",
    "operate": "Daily Operations",
    "troubleshoot": "Troubleshooting Drill",
    "production": "Production Readiness",
    "security": "Security Practice",
    "automation": "Automation Practice",
    "observability": "Observability Practice",
    "backup": "Backup and Recovery",
    "integration": "Integration Lab",
}

# ---------------------------------------------------------------------------
# CATALOG STANDARDS (single source of truth reused by the generator + the
# validator). Two conventions define what "good" scenario copy looks like:
#
#   1. HINT_LADDER  — five graduated, teaching-oriented rungs at escalating
#      XP cost. Each rung has an unmistakable label prefix so the validator
#      can recognise it and so learners see the escalation. The ladder never
#      pastes the full answer: even the final rung describes the *shape* of
#      the fix and how to verify it, still requiring the learner to act.
#
#   2. TICKET_SECTIONS — the "company incident ticket" description structure.
#      Every rich description opens with these labelled sections so a learner
#      reads a realistic ticket (business impact, environment, symptom, the
#      concrete work to do, how to verify) instead of a vague blurb.
# ---------------------------------------------------------------------------

# Five rungs, escalating XP cost. order/cost are stable so the seeder, scorer
# and frontend keep working; label is the recognisable prefix for each rung.
HINT_LADDER = (
    {"order": 1, "cost": 0, "label": "ORIENT"},
    {"order": 2, "cost": 10, "label": "APPROACH"},
    {"order": 3, "cost": 25, "label": "WHICH TOOL"},
    {"order": 4, "cost": 40, "label": "NARROW DOWN"},
    {"order": 5, "cost": 60, "label": "NEAR-SOLUTION"},
)
HINT_LADDER_RUNGS = len(HINT_LADDER)
# Human-readable name for each rung, used in the label prefix of the content.
HINT_RUNG_TITLES = {
    "ORIENT": "ORIENT — what to observe and why",
    "APPROACH": "APPROACH — the troubleshooting method",
    "WHICH TOOL": "WHICH TOOL — the diagnostic command(s)",
    "NARROW DOWN": "NARROW DOWN — isolate the subsystem",
    "NEAR-SOLUTION": "NEAR-SOLUTION — the fix shape + verify",
}

# The labelled sections of a company-ticket description, in order. The first
# five (through OBJECTIVE / WHAT TO AVOID) are the legacy sections the older
# validator + tests already look for; the remainder are the richer additions
# (concrete work, verification, rollback) the enrichment adds on top.
TICKET_SECTIONS = (
    "CONTEXT",              # business background, customer, impact
    "ENVIRONMENT",          # architecture overview + current environment
    "SYMPTOM / STARTING STATE",
    "OBJECTIVE",            # expected outcome + acceptance criteria
    "WORK TO DO",           # required installs + config changes to make
    "VERIFY",               # validation / verification steps + success criteria
    "ROLLBACK",             # how to back out safely
    "WHAT TO AVOID",        # anti-patterns / guard rails
)
# Section labels the validator MUST find for a description to count as rich.
# Kept identical to the legacy DESCRIPTION_SECTIONS so grading-neutral, plus
# the two new load-bearing sections that carry the "detailed requirements".
TICKET_REQUIRED_SECTIONS = (
    "CONTEXT:",
    "ENVIRONMENT:",
    "SYMPTOM",
    "OBJECTIVE:",
    "WORK TO DO:",
    "VERIFY:",
    "WHAT TO AVOID:",
)

TECH_PROFILES: dict[str, dict[str, str]] = {
    "aws": {"domain": "AWS cloud operations", "env": "AWS practice account", "surface": "AWS CLI, IAM policies, EC2/S3/VPC, security groups, and CloudFormation/Terraform"},
    "linux": {"domain": "Linux administration", "env": "Linux practice server", "surface": "terminal and config files under /etc and /var"},
    "rhel-linux": {"domain": "Red Hat Enterprise Linux", "env": "RHEL practice host", "surface": "dnf, subscription-manager, firewalld, and SELinux"},
    "docker": {"domain": "Docker containers", "env": "Docker host", "surface": "docker CLI, images, containers, and compose files"},
    "kubernetes": {"domain": "Kubernetes", "env": "Kubernetes cluster", "surface": "kubectl, manifests, and cluster resources"},
    "terraform": {"domain": "Terraform IaC", "env": "Terraform workspace", "surface": "HCL files, state, and plan/apply workflow"},
    "ansible": {"domain": "Ansible automation", "env": "Ansible control node", "surface": "inventory, playbooks, roles, and ansible-playbook"},
    "networking": {"domain": "network operations", "env": "network lab", "surface": "interfaces, routing tables, DNS, and firewall rules"},
    "vmware": {"domain": "VMware vSphere", "env": "vSphere lab", "surface": "VMs, datastores, vCenter, and ESXi tasks"},
    "windows": {"domain": "Windows Server", "env": "Windows Server host", "surface": "PowerShell, Server Manager, and AD tools"},
    "python": {"domain": "Python development", "env": "Python project workspace", "surface": "source files, venv, tests, and CLI entrypoints"},
    "javascript": {"domain": "JavaScript", "env": "JavaScript practice project", "surface": "modules, browser console, and Node tooling"},
    "nodejs": {"domain": "Node.js backends", "env": "Node.js application", "surface": "Express routes, middleware, and package.json"},
    "react": {"domain": "React frontends", "env": "React application", "surface": "components, hooks, router, and build output"},
    "html": {"domain": "HTML and web delivery", "env": "web server lab", "surface": "HTML pages, nginx/apache config, and browser devtools"},
    "java": {"domain": "Java applications", "env": "Java project", "surface": "Maven/Gradle, JVM logs, and Spring configuration"},
    "shell-script": {"domain": "shell scripting", "env": "bash lab host", "surface": "scripts, cron, logs, and shellcheck"},
    "database": {"domain": "database administration", "env": "database server", "surface": "SQL client, schemas, backups, and performance views"},
    "devops": {"domain": "DevOps delivery", "env": "CI/CD lab", "surface": "git repos, pipelines, artifacts, and runbooks"},
    "mysql": {"domain": "MySQL", "env": "MySQL instance", "surface": "mysql client, InnoDB, grants, and slow query log"},
    "postgresql": {"domain": "PostgreSQL", "env": "PostgreSQL cluster", "surface": "psql, pg_hba.conf, roles, and WAL"},
    "sqlite": {"domain": "SQLite", "env": "SQLite database file", "surface": "sqlite3 CLI, schema, WAL mode, and pragmas"},
    "grafana": {"domain": "Grafana observability", "env": "Grafana stack", "surface": "dashboards, datasources, alerts, and provisioning YAML"},
    "prometheus": {"domain": "Prometheus monitoring", "env": "Prometheus stack", "surface": "scrape configs, PromQL, rules, and Alertmanager"},
    "security": {"domain": "security hardening", "env": "hardening lab", "surface": "SSH, firewall, TLS, audit logs, and IAM settings"},
    "gpu": {"domain": "GPU operations", "env": "GPU node", "surface": "nvidia-smi, drivers, CUDA, and container toolkit"},
    "baremetal": {"domain": "bare metal operations", "env": "physical server lab", "surface": "IPMI, RAID, BIOS, and out-of-band console"},
    "nmap": {"domain": "network scanning", "env": "scanning lab", "surface": "nmap CLI, targets, and scan output"},
    "wireshark": {"domain": "packet analysis", "env": "capture lab", "surface": "pcap files, display filters, and protocol decode"},
    "ai-ml": {"domain": "AI/ML workflows", "env": "ML practice workspace", "surface": "datasets, training scripts, metrics, and model artifacts"},
    "data-science": {"domain": "data science", "env": "notebook lab", "surface": "pandas/notebook workflows, joins, and charts"},
    "prompt-engineering": {"domain": "prompt engineering", "env": "LLM practice workspace", "surface": "prompt templates, eval sets, and tool configs"},
    "peoplesoft": {"domain": "PeopleSoft administration", "env": "PeopleSoft app server lab", "surface": "PIA, Process Scheduler, Integration Broker, and app server logs"},
    "azure": {"domain": "Azure cloud operations", "env": "Azure practice subscription", "surface": "Portal, Azure CLI, VMs, disks, NSGs, and resource groups"},
    "gcp": {"domain": "Google Cloud operations", "env": "GCP practice project", "surface": "Console, gcloud, Compute Engine, disks, VPC, and IAM"},
    "openstack": {"domain": "OpenStack cloud operations", "env": "OpenStack practice cloud", "surface": "Horizon, Nova, Neutron, Cinder, and Glance"},
    "commvault": {"domain": "Commvault backup operations", "env": "CommCell practice lab", "surface": "CommServe, MediaAgent, backup plans, and restore jobs"},
    "netapp": {"domain": "NetApp ONTAP storage", "env": "ONTAP practice cluster", "surface": "System Manager, SVMs, volumes, LUNs, and SnapMirror"},
    "dellemc": {"domain": "Dell EMC storage", "env": "PowerStore/Unity practice array", "surface": "pools, volumes, snapshots, and host mapping"},
    "datacenter": {"domain": "enterprise data center operations", "env": "data center practice floor", "surface": "racks, PDUs, cooling, cabling, and physical servers"},
    "soc": {"domain": "SOC and cybersecurity operations", "env": "security operations lab", "surface": "SIEM, EDR, tickets, and investigation timelines"},
    "gitops": {"domain": "GitOps delivery", "env": "GitOps practice cluster", "surface": "Git repos, sync agents, and declarative workloads"},
    "devsecops-supplychain": {"domain": "DevSecOps supply chain", "env": "secure pipeline lab", "surface": "SCA, image scanning, signing, and policy gates"},
    "opentelemetry": {"domain": "OpenTelemetry observability", "env": "telemetry practice stack", "surface": "traces, metrics, logs, and collectors"},
    "service-mesh": {"domain": "service mesh operations", "env": "mesh practice cluster", "surface": "sidecars, traffic policy, mTLS, and observability"},
}

TOPIC_SNIPPETS: dict[str, dict[str, str]] = {
    "users-groups": {
        "label": "users and groups",
        "concept": "how accounts, UIDs/GIDs, primary groups, and supplementary membership are defined",
        "inspect": "`id`, `getent passwd`, and `getent group` (or equivalent directory tools on Windows)",
        "symptom": "users cannot log in, sudo fails, or shared directories return permission denied",
        "verify": "account and group entries match the expected owner and membership",
    },
    "permissions-acl": {
        "label": "file permissions and ACLs",
        "concept": "owner/group/other bits, ACL entries, and default ACL inheritance",
        "inspect": "`ls -la`, `getfacl`, and `namei -l` on the affected path",
        "symptom": "applications fail with permission denied even though the user exists",
        "verify": "the process user can read/write/execute exactly what the service needs",
    },
    "systemd-services": {
        "label": "systemd services",
        "concept": "unit files, dependencies, restart policies, and journal logging",
        "inspect": "`systemctl status`, `systemctl cat`, and `journalctl -u <service>`",
        "symptom": "a service is failed, flapping, or not starting after reboot",
        "verify": "the unit is enabled, active, and logging cleanly",
    },
    "journald-logs": {
        "label": "journald logging",
        "concept": "structured logs, priorities, boots, and persistent journal storage",
        "inspect": "`journalctl -p err..alert`, `journalctl -b`, and `/etc/systemd/journald.conf`",
        "symptom": "errors are hard to find or logs rotate away before investigation",
        "verify": "the relevant error window is visible with useful metadata",
    },
    "storage-lvm": {
        "label": "storage and LVM",
        "concept": "PV/VG/LV layout, filesystem growth, and mount persistence",
        "inspect": "`lsblk`, `pvs`, `vgs`, `lvs`, and `df -h`",
        "symptom": "a filesystem is full or a volume did not come online after maintenance",
        "verify": "capacity is sufficient and mounts survive reboot",
    },
    "dns": {
        "label": "DNS",
        "concept": "name resolution, records, forward/reverse lookups, and resolver config",
        "inspect": "`dig`, `nslookup`, or `Resolve-DnsName` plus zone/config files",
        "symptom": "applications cannot resolve service names or lookups return wrong targets",
        "verify": "queries return the expected records from the intended resolver",
    },
    "firewall": {
        "label": "host firewall",
        "concept": "allow/deny rules, zones, services, and rule persistence",
        "inspect": "`firewall-cmd --list-all`, `iptables -S`, `ufw status`, or Windows firewall cmdlets",
        "symptom": "valid traffic is blocked or unexpected ports are exposed",
        "verify": "only the intended ports and sources are permitted",
    },
    "pods": {
        "label": "Kubernetes pods",
        "concept": "pod spec, containers, probes, resources, and scheduling",
        "inspect": "`kubectl describe pod`, `kubectl logs`, and the rendered manifest",
        "symptom": "pods crashloop, stay pending, or never become ready",
        "verify": "pods are Running/Ready with healthy probe results",
    },
    "deployments": {
        "label": "Deployments",
        "concept": "replicas, rollout strategy, selectors, and revision history",
        "inspect": "`kubectl get deploy`, `kubectl rollout status`, and `kubectl describe deploy`",
        "symptom": "a rollout is stuck or new replicas never receive traffic",
        "verify": "desired replicas are available and the rollout completed",
    },
    "dockerfile": {
        "label": "Dockerfiles",
        "concept": "image layers, build context, ENTRYPOINT/CMD, and caching",
        "inspect": "`docker build` output, `docker history`, and the Dockerfile stages",
        "symptom": "images are huge, builds fail, or containers exit immediately",
        "verify": "the image builds reproducibly and the container starts as intended",
    },
    "compose": {
        "label": "Docker Compose",
        "concept": "multi-service stacks, networks, volumes, and dependency order",
        "inspect": "`docker compose config`, `docker compose ps`, and service logs",
        "symptom": "dependent services start before databases or ports collide",
        "verify": "the stack is healthy end-to-end with persistent data where required",
    },
    "volumes": {
        "label": "Docker volumes",
        "concept": "named volumes, bind mounts, permissions, and data persistence across restarts",
        "inspect": "`docker volume ls`, `docker inspect` mount sections, and `docker compose config`",
        "symptom": "containers start but lose data, hit permission denied on mounts, or disk fills from anonymous volumes",
        "verify": "data persists across container recreation and mount paths are writable by the container user",
    },
    "networks": {
        "label": "Docker networks",
        "concept": "bridge/overlay networks, DNS names, published ports, and container-to-container connectivity",
        "inspect": "`docker network ls`, `docker network inspect`, and `docker port`",
        "symptom": "containers cannot reach each other or published ports are unreachable from the host",
        "verify": "expected containers share the correct network and connectivity works on the service port",
    },
    "images-layers": {
        "label": "images and layers",
        "concept": "image tags, layer caching, dangling images, and registry pulls",
        "inspect": "`docker images`, `docker history`, and `docker system df`",
        "symptom": "pulls fail, wrong image tag is running, or disk is exhausted by dangling layers",
        "verify": "the intended image digest/tag is running and reclaimable waste is cleaned safely",
    },
    "services": {
        "label": "Kubernetes Services",
        "concept": "ClusterIP/NodePort/LoadBalancer, selectors, endpoints, and kube-proxy routing",
        "inspect": "`kubectl get svc,endpoints`, `kubectl describe svc`, and pod labels",
        "symptom": "traffic never reaches pods or hits the wrong backend",
        "verify": "Service endpoints match ready pods and probes succeed through the Service IP",
    },
    "ingress": {
        "label": "Ingress",
        "concept": "hosts, paths, TLS secrets, and ingress controller routing",
        "inspect": "`kubectl describe ingress`, controller logs, and backend Service health",
        "symptom": "HTTP routes return 404/502 or TLS handshake fails",
        "verify": "requests reach the intended backend with a valid certificate chain",
    },
    "configmaps": {
        "label": "ConfigMaps",
        "concept": "key/value config, mounted files, envFrom, and rollout after config changes",
        "inspect": "`kubectl get cm`, mounted paths in pods, and `kubectl describe pod`",
        "symptom": "applications read stale config or crash because required keys are missing",
        "verify": "pods see updated config after rollout and apps start cleanly",
    },
    "secrets": {
        "label": "Secrets",
        "concept": "secret types, mounting, RBAC access, and rotation",
        "inspect": "`kubectl get secret`, volume mounts, and ServiceAccount permissions",
        "symptom": "pods cannot mount credentials or apps fail authentication",
        "verify": "only intended workloads can read the secret and apps authenticate successfully",
    },
    "variables": {
        "label": "Terraform variables",
        "concept": "input variables, defaults, validation, and tfvars layering",
        "inspect": "variables.tf, *.tfvars, and `terraform console`",
        "symptom": "plans fail with missing variables or wrong environment values are applied",
        "verify": "the correct tfvars set is used and `terraform validate` passes",
    },
    "modules": {
        "label": "Terraform modules",
        "concept": "module sources, versions, outputs, and composition",
        "inspect": "module blocks, `terraform get`, and child module outputs",
        "symptom": "module upgrades break dependents or outputs changed unexpectedly",
        "verify": "module inputs/outputs match the wrapper and plans are clean",
    },
    "roles": {
        "label": "Ansible roles",
        "concept": "role layout, defaults/vars, tasks, handlers, and dependencies",
        "inspect": "roles/ tree, `ansible-galaxy list`, and role variable precedence",
        "symptom": "role runs fail or behave differently per host",
        "verify": "role applies idempotently with the expected variables per group",
    },
    "replication": {
        "label": "database replication",
        "concept": "primary/replica topology, lag, failover, and consistency",
        "inspect": "replication status views, `SHOW REPLICA STATUS`, or `pg_stat_replication`",
        "symptom": "replicas lag, break, or promotions fail during failover drills",
        "verify": "replication is streaming, lag is within SLO, and read routing works",
    },
    "slow-query": {
        "label": "slow queries",
        "concept": "query plans, indexes, statistics, and timeout tuning",
        "inspect": "slow query log, EXPLAIN, and performance_schema/pg_stat_statements",
        "symptom": "API timeouts correlate with database load spikes",
        "verify": "target queries use efficient plans and p95 latency improves",
    },
    "routing": {
        "label": "network routing",
        "concept": "routing tables, default gateways, static routes, and asymmetric paths",
        "inspect": "`ip route`, `traceroute`, and interface addresses",
        "symptom": "some subnets are unreachable or traffic takes the wrong path",
        "verify": "packets follow the intended next-hop and return path is symmetric",
    },
    "selinux": {
        "label": "SELinux",
        "concept": "contexts, booleans, policies, and audit denials",
        "inspect": "`getenforce`, `ls -Z`, `ausearch -m avc`, and `semanage`",
        "symptom": "services fail with permission denied despite correct Unix permissions",
        "verify": "the service runs with the correct SELinux context and AVC denials are gone",
    },
    "vm-lifecycle": {
        "label": "VM lifecycle",
        "concept": "create, template deploy, power state, and guest tools",
        "inspect": "vCenter/ESXi VM summary, tasks, and VMware Tools status",
        "symptom": "VMs fail to power on, clone, or migrate",
        "verify": "VM reaches the desired power state with Tools running and correct resources",
    },
    "active-directory": {
        "label": "Active Directory",
        "concept": "domains, OUs, replication, and FSMO roles",
        "inspect": "ADUC, `dcdiag`, `repadmin`, and event logs",
        "symptom": "logons fail, GPO does not apply, or replication is broken",
        "verify": "AD is healthy, replication partners agree, and test logon succeeds",
    },
    "express": {
        "label": "Express APIs",
        "concept": "routes, middleware order, error handlers, and request parsing",
        "inspect": "route definitions, server logs, and HTTP traces",
        "symptom": "routes 404, middleware never runs, or JSON body is undefined",
        "verify": "endpoints return expected status/body and errors are handled centrally",
    },
    "components": {
        "label": "React components",
        "concept": "props, state, composition, and rendering boundaries",
        "inspect": "component tree, React DevTools, and console errors",
        "symptom": "UI does not update, props are undefined, or renders loop infinitely",
        "verify": "components render the expected UI for given state and props",
    },
    "venv": {
        "label": "Python virtual environments",
        "concept": "venv creation, dependency pinning, and interpreter isolation",
        "inspect": "`which python`, `pip freeze`, and activation scripts",
        "symptom": "imports fail or wrong package versions are used across machines",
        "verify": "the venv activates cleanly and required imports succeed",
    },
    "maven": {
        "label": "Maven builds",
        "concept": "POM structure, dependencies, plugins, and lifecycle phases",
        "inspect": "`mvn -q dependency:tree`, surefire reports, and pom.xml",
        "symptom": "builds fail on dependency resolution or tests never run",
        "verify": "`mvn verify` succeeds and artifacts are produced in target/",
    },
    "drivers": {
        "label": "GPU drivers",
        "concept": "driver/kernel module versions, persistence mode, and device nodes",
        "inspect": "`nvidia-smi`, `dmesg`, and driver package versions",
        "symptom": "GPUs are invisible to CUDA workloads or nodes fail GPU health checks",
        "verify": "nvidia-smi reports healthy devices and sample CUDA jobs run",
    },
    "dataset": {
        "label": "ML datasets",
        "concept": "schema, splits, labeling quality, and leakage",
        "inspect": "dataset profile, class balance, and feature distributions",
        "symptom": "training metrics look great but production performance collapses",
        "verify": "train/val/test splits are correct and features are free of leakage",
    },
    "pia-navigation": {
        "label": "PeopleSoft PIA navigation",
        "concept": "PIA domains, menus, components, and user sessions",
        "inspect": "PIA access logs, web server status, and app server domains",
        "symptom": "users cannot open components or sessions drop immediately",
        "verify": "PIA login and target component load without server errors",
    },
    "providers": {
        "label": "Terraform providers",
        "concept": "provider blocks, versions, authentication, and resource schemas",
        "inspect": "`terraform providers`, provider config, and `terraform validate`",
        "symptom": "plans fail because provider credentials or versions are wrong",
        "verify": "provider initialization succeeds and schemas resolve",
    },
    "state": {
        "label": "Terraform state",
        "concept": "local vs remote state, locking, drift, and resource addressing",
        "inspect": "`terraform state list`, `terraform show`, and backend config",
        "symptom": "state and real infrastructure disagree or locks block applies",
        "verify": "state accurately reflects deployed resources",
    },
    "inventory": {
        "label": "Ansible inventory",
        "concept": "hosts, groups, variables, and connection settings",
        "inspect": "`ansible-inventory --graph` and group/host vars files",
        "symptom": "plays target the wrong hosts or missing vars break templates",
        "verify": "inventory groups and vars match the intended environment",
    },
    "playbooks": {
        "label": "Ansible playbooks",
        "concept": "plays, tasks, handlers, idempotency, and check mode",
        "inspect": "`ansible-playbook --syntax-check`, `--check`, and task output",
        "symptom": "runs are not idempotent or handlers never fire",
        "verify": "a second run reports no unexpected changes",
    },
    "promql": {
        "label": "PromQL queries",
        "concept": "metric selectors, rates, aggregations, and alert expressions",
        "inspect": "Prometheus graph UI, `promtool query instant`, and rule files",
        "symptom": "dashboards/alerts show no data or fire constantly",
        "verify": "expressions return sensible series for the intended window",
    },
    "dashboards": {
        "label": "Grafana dashboards",
        "concept": "panels, variables, transformations, and datasource wiring",
        "inspect": "dashboard JSON, panel queries, and Explore view",
        "symptom": "panels show 'No data' or variables break all charts",
        "verify": "dashboards render with correct templated filters",
    },
    "backup": {
        "label": "backup workflows",
        "concept": "full/incremental backups, retention, encryption, and restore drills",
        "inspect": "backup job logs, catalog/metadata, and latest restore test results",
        "symptom": "backups fail silently or restores take longer than RTO",
        "verify": "a restore completes within policy and data checksums match",
    },
    "indexes": {
        "label": "database indexes",
        "concept": "B-tree indexes, selectivity, covering indexes, and plan impact",
        "inspect": "EXPLAIN/EXPLAIN ANALYZE and index usage views",
        "symptom": "queries time out as tables grow",
        "verify": "plans use the intended index and latency drops",
    },
    "rbac": {
        "label": "role-based access control",
        "concept": "roles, bindings, least privilege, and auditability",
        "inspect": "RBAC policy objects, role assignments, and effective permissions",
        "symptom": "users have too much access or legitimate access is denied",
        "verify": "effective permissions match the policy of least privilege",
    },
    "tls": {
        "label": "TLS configuration",
        "concept": "certificates, chains, ciphers, renewal, and mTLS",
        "inspect": "`openssl s_client`, cert file paths, and ingress/listener config",
        "symptom": "clients see certificate errors or weak cipher negotiation",
        "verify": "handshakes succeed with a trusted chain and modern ciphers",
    },
    "filters": {
        "label": "capture/display filters",
        "concept": "BPF/display filters, protocol fields, and follow streams",
        "inspect": "Wireshark filter bar, protocol decode panes, and IO graphs",
        "symptom": "captures are too noisy to isolate the failing conversation",
        "verify": "the target flow is isolated with enough context to explain latency/errors",
    },
    "tcp-scan": {
        "label": "TCP scanning",
        "concept": "SYN/connect scans, port states, and safe timing templates",
        "inspect": "`nmap -sS/-sT`, `--reason`, and service detection output",
        "symptom": "security review needs an accurate port/service inventory",
        "verify": "results match expected exposure with documented scan parameters",
    },
}

# Merge curated extended snippets (covers the long tail of per-tech topics so
# generated copy names real commands/symptoms instead of using the fallback).
try:
    from topic_snippets_extended import EXTENDED_TOPIC_SNIPPETS
    for _k, _v in EXTENDED_TOPIC_SNIPPETS.items():
        TOPIC_SNIPPETS.setdefault(_k, _v)
except ImportError:
    pass

ACADEMY_SLUG_RE = re.compile(r"^academy-(?P<tech>[\w-]+)-(?P<seq>\d+)-(?P<rest>.+)$")


def humanize_topic(topic: str) -> str:
    base = re.sub(r"-\d+$", "", topic)
    if base in TOPIC_SNIPPETS:
        return TOPIC_SNIPPETS[base]["label"]
    text = base.replace("-", " ")
    replacements = {
        "acl": "ACL",
        "dns": "DNS",
        "tls": "TLS",
        "rbac": "RBAC",
        "lvm": "LVM",
        "wal": "WAL",
        "gpu": "GPU",
        "ipmi": "IPMI",
        "pxe": "PXE",
        "ci": "CI",
        "cd": "CD",
        "api": "API",
        "http": "HTTP",
        "gpo": "GPO",
        "iis": "IIS",
        "jdbc": "JDBC",
        "jvm": "JVM",
        "nvidia": "NVIDIA",
        "cuda": "CUDA",
        "mig": "MIG",
        "nse": "NSE",
        "promql": "PromQL",
        "pg": "PostgreSQL",
        "hba": "HBA",
        "vm": "VM",
        "ha": "HA",
        "drs": "DRS",
        "sso": "SSO",
        "oidc": "OIDC",
    }
    words = []
    for word in text.split():
        words.append(replacements.get(word.lower(), word.capitalize()))
    return " ".join(words)


def topic_base(topic: str) -> str:
    return re.sub(r"-\d+$", "", topic)


def snippet_for(tech: str, topic: str) -> dict[str, str]:
    base = topic_base(topic)
    if base in TOPIC_SNIPPETS:
        return TOPIC_SNIPPETS[base]
    profile = TECH_PROFILES.get(tech, {"domain": tech.replace("-", " "), "env": "lab environment", "surface": "CLI and configuration"})
    label = humanize_topic(topic)
    return {
        "label": label,
        "concept": f"how {label.lower()} fits into {profile['domain']}",
        "inspect": f"the relevant {profile['surface']} for {label.lower()}",
        "symptom": f"{label} is misconfigured and dependent workflows are failing",
        "verify": f"{label} behaves correctly under normal and failure checks",
    }


def parse_academy_slug(slug: str) -> dict[str, str] | None:
    match = ACADEMY_SLUG_RE.match(slug)
    if not match:
        return None
    tech = match.group("tech")
    rest = match.group("rest")
    for kind in KINDS:
        prefix = f"{kind}-"
        if rest.startswith(prefix):
            return {
                "tech": tech,
                "seq": match.group("seq"),
                "kind": kind,
                "topic": rest[len(prefix) :],
            }
    return None


def _marker_from_slug(slug: str) -> str:
    return f"/opt/fixitlab/academy/{slug}.conf"


def _objectives(kind: str, label: str, symptom: str) -> list[str]:
    if kind == "learn":
        return [
            f"Understand how {label} work in this lab environment",
            f"Identify the main status and configuration signals for {label}",
            "Confirm you can read the current state confidently before changing anything",
        ]
    if kind == "build":
        return [
            f"A working {label} setup must exist by the end of this lab",
            "Configuration should follow team conventions and be easy to audit",
            "The result should pass validation without manual cleanup",
        ]
    if kind == "troubleshoot":
        return [
            f"The incident symptom is clear: {symptom}",
            "Root cause is isolated with evidence, not guesswork",
            "Service behavior returns to normal after the fix",
        ]
    if kind == "security":
        return [
            f"Unsafe defaults related to {label} are removed or constrained",
            "Access follows least privilege and is auditable",
            "Security checks pass without breaking required functionality",
        ]
    if kind == "backup":
        return [
            f"Backup coverage for {label} is complete and restorable",
            "Retention and encryption meet the stated policy",
            "A restore drill proves data integrity",
        ]
    if kind == "integration":
        return [
            f"{label} is connected to the adjacent system successfully",
            "Handoff points are authenticated and observable",
            "End-to-end workflow completes without manual intervention",
        ]
    return [
        f"Day-2 {label} work completes safely in this environment",
        "Changes are verified with before/after checks",
        "The system remains stable for dependent teams",
    ]


# Per-kind narrative templates. {name} {label} {concept} {symptom} {env} fill in.
_KIND_COPY: dict[str, dict[str, str]] = {
    "learn": {
        "description": (
            "This beginner-friendly {name} lab introduces {label}. "
            "You will explore {concept} on the {env}. "
            "Read the environment first, then follow the guided steps — no prior production experience required."
        ),
        "initial_state": (
            "The {env} is online with a starter {label} setup. Some pieces are intentionally "
            "incomplete so you can learn how they fit together. Nothing is on fire — focus on observation."
        ),
    },
    "build": {
        "description": (
            "Build {label} from scratch in this {name} lab. You start from a minimal environment and must "
            "produce a working configuration that demonstrates {concept}. Plan, implement, then prove it works."
        ),
        "initial_state": (
            "The {env} is ready but {label} is not configured yet. Required tools may already be installed; "
            "your job is to create the configuration and bring the capability online."
        ),
    },
    "troubleshoot": {
        "description": (
            "Production alert: {symptom}. You are on call for {name} and must troubleshoot {label} "
            "methodically — triage symptoms, isolate root cause, apply the smallest safe fix, and confirm recovery."
        ),
        "initial_state": (
            "The {env} is degraded. {Symptom}. Recent changes may exist around {label}, "
            "but do not restart blindly — gather evidence first."
        ),
    },
    "security": {
        "description": (
            "Security review: harden {label} on this {name} system. Close unsafe defaults, enforce least "
            "privilege, and ensure {concept} cannot be abused — without breaking legitimate use."
        ),
        "initial_state": (
            "The environment is functional but overly permissive around {label}. "
            "Assume an auditor or pen test is next week — tighten controls with evidence."
        ),
    },
    "backup": {
        "description": (
            "Backup and recovery drill for {label}. Ensure backups run on schedule, retention is correct, "
            "and you can restore {concept} within the lab RTO."
        ),
        "initial_state": (
            "Backup jobs exist but reliability is uncertain for {label}. "
            "Leadership wants proof that restore works — not just that scripts exit zero."
        ),
    },
    "integration": {
        "description": (
            "Integration lab: connect {label} with an adjacent platform in the {name} stack. "
            "Validate authentication, data handoff, and failure behavior for {concept}."
        ),
        "initial_state": (
            "Two systems are deployed but not fully wired together for {label}. "
            "Downstream consumers are waiting on this integration path."
        ),
    },
    "observability": {
        "description": (
            "Observability task: make {label} visible in logs, metrics, or traces. On-call should answer "
            "'what is broken?' quickly using signals from {concept}."
        ),
        "initial_state": (
            "The system runs, but {label} lacks useful telemetry. "
            "Dashboards/alerts are blank or noisy — improve signal quality."
        ),
    },
    "automation": {
        "description": (
            "Automation lab: remove toil around {label}. Codify repeatable steps for {concept} "
            "and prove the automation is idempotent."
        ),
        "initial_state": (
            "Operators still perform manual steps for {label}. "
            "Automate the boring parts without hiding important safety checks."
        ),
    },
    "production": {
        "description": (
            "Production readiness for {label}. Harden, document, and validate {concept} so the change "
            "is safe to run during a maintenance window."
        ),
        "initial_state": (
            "A feature fix works in dev, but {label} is not production ready — "
            "missing guardrails, runbooks, or capacity checks."
        ),
    },
    "operate": {
        "description": (
            "Day-2 operations: perform a routine {label} task safely in {name}. "
            "Follow change control — inspect, change, verify — while working with {concept}."
        ),
        "initial_state": (
            "The {env} is healthy enough for scheduled work on {label}. "
            "Complete the maintenance task without unnecessary downtime."
        ),
    },
}

# Per-kind "do" step used as the middle action of the guided walkthrough (tier 3).
_KIND_ACTION: dict[str, str] = {
    "learn": "Make one small, reversible change toward the objective, re-reading status after each step so you understand cause and effect",
    "build": "Create the smallest working slice of {label} first, validate it, then add the remaining pieces one at a time",
    "troubleshoot": "Fix the underlying misconfiguration you identified (not just the noisy log line), changing one thing at a time",
    "security": "Apply least privilege: remove the unsafe default, then grant only the explicit access the workload actually needs",
    "backup": "Repair or run the backup job, then perform a controlled restore into a scratch location to prove it works",
    "integration": "Configure credentials and networking, then drive one happy-path transaction end to end across both systems",
    "observability": "Add or fix the exporter / dashboard / alert with clear names, labels, and a sensible threshold",
    "automation": "Implement the automation with dry-run / check mode, then run it twice — the second run must report no changes",
    "production": "Apply production standards for {label}: resource limits, monitoring, access controls, and a written rollback step",
    "operate": "Execute the maintenance in small, reversible steps, taking a snapshot or backup first if the change is risky",
}


def _guided_hints(
    kind: str, label: str, concept: str, inspect: str, symptom: str, verify: str, marker: str
) -> list[dict[str, Any]]:
    """Three escalating hints, each a numbered step-by-step guide (not a one-liner)."""
    action = _KIND_ACTION.get(kind, _KIND_ACTION["operate"]).format(label=label)

    tier1 = (
        f"Orient yourself before changing anything:\n"
        f"1. Inspect the current state — {inspect}.\n"
        f"2. Write down what looks normal versus wrong or missing for {label}.\n"
        f"3. Review the architecture diagram and objectives. Form one hypothesis before you act."
    )
    tier2 = (
        f"Plan your approach (still no spoilers):\n"
        f"1. Confirm the exact gap between current and desired state for {label}.\n"
        f"2. Decide the single smallest change that moves you toward the objective.\n"
        f"3. Capture evidence (command output / status) before the change so you can prove it worked afterward."
    )
    tier3 = (
        f"Exact fix + verification:\n"
        f"1. Re-check the current state — {inspect}.\n"
        f"2. {action}.\n"
        f"3. Verify the result — {verify}.\n"
        f"4. Click Check Solution once the objective is met (graded on real state, not a marker file)."
    )
    return [
        {"order": 1, "cost": 0, "content": tier1},
        {"order": 2, "cost": 25, "content": tier2},
        {"order": 3, "cost": 50, "content": tier3},
    ]


def build_hint_ladder(
    *,
    label: str,
    concept: str,
    inspect: str,
    symptom: str,
    verify: str,
    action: str,
    grader: str,
) -> list[dict[str, Any]]:
    """Build the 5-rung graduated HINT_LADDER for a specific topic/fault.

    Every rung is teaching-oriented and topic-specific — the caller passes the
    ``inspect`` diagnostic commands, ``symptom`` and ``verify`` phrases for the
    real subsystem, so a VLAN lab talks about VLAN/routing, not generic filler.
    The final rung gives the fix *shape* + how to verify, never the full answer.

    ``label``   short subsystem name (e.g. "VLAN routing", "the nginx service").
    ``concept`` one-clause explanation of how the subsystem works.
    ``inspect`` the read-only diagnostic command(s), already backtick-wrapped.
    ``symptom`` the observable failure phrase.
    ``verify``  the phrase describing a healthy end state.
    ``action``  the kind-specific fix method (from _KIND_ACTION), imperative.
    ``grader``  the verification command the checker uses, backtick-wrapped.
    """
    rungs = {
        "ORIENT": (
            f"ORIENT — what to observe and why:\n"
            f"Do not touch anything yet. First observe the symptom: {symptom}. "
            f"This lab is about {label} — {concept}. "
            "Read the objectives and the current state, and note precisely what looks "
            "wrong versus healthy before you form any theory."
        ),
        "APPROACH": (
            f"APPROACH — the troubleshooting method:\n"
            f"Work from evidence, not guesses. For {label} problems the reliable method is: "
            "(1) reproduce/observe the failure, (2) narrow from the whole system down to the one "
            "component that owns the symptom, (3) change exactly one thing, (4) re-check. "
            f"{action}."
        ),
        "WHICH TOOL": (
            f"WHICH TOOL — the diagnostic command(s):\n"
            f"1. Inspect the current state with {inspect}.\n"
            "2. Each command above tells you something specific — status/health, recent errors, "
            "and the effective configuration. Read them in that order.\n"
            "3. Compare what you see to the objectives; the gap points at the fault."
        ),
        "NARROW DOWN": (
            f"NARROW DOWN — isolate the subsystem:\n"
            f"1. From the evidence above, decide which single part of {label} is at fault.\n"
            f"2. Re-run the most relevant of {inspect} focused on just that part to confirm it.\n"
            "3. State a one-line hypothesis: the smallest change that would move the state from "
            f"'{symptom}' toward '{verify}'."
        ),
        "NEAR-SOLUTION": (
            f"NEAR-SOLUTION — the fix shape + verify (you still apply it):\n"
            f"1. Apply the smallest reversible change your hypothesis points to. {action}.\n"
            f"2. Re-run {grader} and confirm {verify}.\n"
            "3. If it still fails, the hypothesis was wrong — go back to the evidence, do not "
            "stack changes.\n\n"
            "WHY: the grader validates real system state, not marker files — a fix only counts "
            "when the subsystem is actually healthy."
        ),
    }
    ladder: list[dict[str, Any]] = []
    for spec in HINT_LADDER:
        ladder.append(
            {
                "order": spec["order"],
                "cost": spec["cost"],
                "content": rungs[spec["label"]],
            }
        )
    return ladder


def build_academy_copy(
    *,
    tech: str,
    kind: str,
    topic: str,
    slug: str,
    display_name: str | None = None,
    marker: str | None = None,
) -> dict[str, Any]:
    profile = TECH_PROFILES.get(tech, {"domain": tech.replace("-", " "), "env": "lab environment", "surface": "CLI and configuration"})
    snip = snippet_for(tech, topic)
    label = snip["label"]
    concept = snip["concept"]
    inspect = snip["inspect"]
    symptom = snip["symptom"]
    verify = snip["verify"]
    name = display_name or profile["domain"].title()
    marker = marker or _marker_from_slug(slug)
    kind_label = KIND_LABELS[kind]

    fmt = {
        "name": name,
        "label": label,
        "concept": concept,
        "symptom": symptom,
        "Symptom": symptom.capitalize(),
        "env": profile["env"],
    }
    copy = _KIND_COPY.get(kind, _KIND_COPY["operate"])
    description = copy["description"].format(**fmt)
    initial_state = copy["initial_state"].format(**fmt)
    hints = _guided_hints(kind, label, concept, inspect, symptom, verify, marker)

    title = f"{name}: {label.title()} — {kind_label}"
    return {
        "title": title,
        "description": description,
        "initial_state": initial_state,
        "objectives": _objectives(kind, label, symptom),
        "hints": hints,
    }


def is_generic_academy_copy(data: dict) -> bool:
    desc = (data.get("description") or "").lower()
    if "designed to teach the technology end to end" in desc:
        return True
    if "you will learn the workflow and prove the core commands" in desc:
        return True
    objectives = data.get("objectives") or []
    if any("apply the correct" in str(o).lower() and "workflow" in str(o).lower() for o in objectives):
        return True
    hints = data.get("hints") or []
    if hints and "smallest correct change" in (hints[1].get("content") or "").lower():
        return True
    return False


def enrich_scenario_data(data: dict, *, folder_name: str, tech_dir: str) -> dict | None:
    slug = data.get("slug") or folder_name
    parsed = parse_academy_slug(slug)
    if parsed:
        marker = _marker_from_slug(slug)
        copy = build_academy_copy(
            tech=parsed["tech"],
            kind=parsed["kind"],
            topic=parsed["topic"],
            slug=slug,
            display_name=data.get("technology"),
            marker=marker,
        )
        data = {**data, **copy}
        return data

    if not is_generic_academy_copy(data) and len(data.get("hints") or []) >= 3:
        return None

    # Light pass for thin non-academy scenarios
    title = (data.get("title") or folder_name).strip()
    category = (data.get("category") or "General").strip()
    desc = (data.get("description") or "").strip()
    if len(desc) >= 180 and not is_generic_academy_copy(data):
        return None

    profile = TECH_PROFILES.get(tech_dir, {"domain": tech_dir.replace("-", " "), "env": "lab environment"})
    label = title
    improved_desc = (
        f"{desc} " if desc and not is_generic_academy_copy(data) else ""
    ) + (
        f"This {profile['domain']} scenario focuses on {category.lower()}: {label}. "
        "Read the environment, form a hypothesis, apply a minimal fix, and verify behavior before closing the ticket."
    )
    improved_desc = improved_desc.strip()

    hints = list(data.get("hints") or [])
    while len(hints) < 3:
        hints.append({"order": len(hints) + 1, "cost": 10 + (len(hints) * 5), "content": ""})
    env = profile.get("env", "lab environment")
    if not hints[0].get("content"):
        hints[0]["content"] = (
            f"Orient yourself before changing anything:\n"
            f"1. Do read-only discovery on the {env}: logs, status commands, and config related to {label}.\n"
            f"2. Note what looks normal versus wrong or missing.\n"
            f"3. Form one hypothesis about the failure before you act."
        )
    if not hints[1].get("content") or "smallest correct change" in hints[1]["content"].lower():
        hints[1]["content"] = (
            "Plan your approach:\n"
            "1. Pin down the exact gap between current and desired state.\n"
            "2. Choose the single smallest, reversible change that addresses it.\n"
            "3. Capture command output before the change so you can prove it worked."
        )
    if not hints[2].get("content"):
        hints[2]["content"] = (
            "Guided walkthrough:\n"
            "1. Apply the change one step at a time.\n"
            "2. Re-run the failing check or user workflow to confirm recovery.\n"
            "3. Document the symptom → cause → fix before closing the ticket."
        )

    objectives = data.get("objectives") or []
    if len(objectives) < 2 or any("apply the correct" in str(o).lower() for o in objectives):
        objectives = [
            f"Understand the current failure mode affecting {label}",
            "Restore expected service behavior with a minimal, documented change",
            "Verify the fix holds under a realistic smoke test",
        ]

    return {
        **data,
        "description": improved_desc,
        "initial_state": data.get("initial_state") or improved_desc,
        "objectives": objectives,
        "hints": hints[:3],
    }
