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

TECH_PROFILES: dict[str, dict[str, str]] = {
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
    "shell-script": {"domain": "shell scripting", "env": "bash practice environment", "surface": "scripts, cron, logs, and shellcheck"},
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
    "simulation": {"domain": "FixitLab simulation", "env": "simulation sandbox", "surface": "terminal state, validation hooks, and lab authoring markers"},
}

from topic_snippets_extended import EXTENDED_TOPIC_SNIPPETS

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

TOPIC_SNIPPETS.update({k: v for k, v in EXTENDED_TOPIC_SNIPPETS.items() if k not in TOPIC_SNIPPETS})

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
    profile = TECH_PROFILES.get(tech, {"domain": tech.replace("-", " "), "env": "practice environment", "surface": "CLI and configuration"})
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


def build_academy_copy(
    *,
    tech: str,
    kind: str,
    topic: str,
    slug: str,
    display_name: str | None = None,
    marker: str | None = None,
) -> dict[str, Any]:
    profile = TECH_PROFILES.get(tech, {"domain": tech.replace("-", " "), "env": "practice environment", "surface": "CLI and configuration"})
    snip = snippet_for(tech, topic)
    label = snip["label"]
    concept = snip["concept"]
    inspect = snip["inspect"]
    symptom = snip["symptom"]
    verify = snip["verify"]
    name = display_name or profile["domain"].title()
    marker = marker or _marker_from_slug(slug)
    kind_label = KIND_LABELS[kind]

    if kind == "learn":
        description = (
            f"This beginner-friendly {name} lab introduces {label}. "
            f"You will explore {concept} on the {profile['env']}. "
            "Read the environment first, then complete the guided steps — no prior production experience required."
        )
        initial_state = (
            f"The {profile['env']} is online with a starter {label} setup. "
            "Some pieces are intentionally incomplete so you can learn how the pieces fit together. "
            "Nothing is on fire yet — focus on observation and understanding."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": f"Orient yourself: {inspect}. Write down what looks normal vs missing.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": f"Core idea — {concept}. Make one small, reversible change at a time and re-check status.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"When the lab objective is done, record completion by adding `# FIXED-OK` to `{marker}`, then click Check Solution.",
            },
        ]
    elif kind == "build":
        description = (
            f"Build {label} from scratch in this {name} lab. "
            f"You start from a minimal environment and must produce a working configuration that demonstrates {concept}. "
            "Treat this like a greenfield task — plan, implement, then prove it works."
        )
        initial_state = (
            f"The {profile['env']} is ready but {label} is not configured yet. "
            "Required packages/tools may already be installed; your job is to create the config and bring the capability online."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": f"List prerequisites first: which packages, files, or API objects must exist for {label}?",
            },
            {
                "order": 2,
                "cost": 15,
                "content": f"Implement incrementally — create the smallest working slice of {label}, validate, then add the remaining pieces.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Prove success: {verify}. Mark the lab complete with `# FIXED-OK` in `{marker}` and run Check Solution.",
            },
        ]
    elif kind == "troubleshoot":
        description = (
            f"Production alert: {symptom}. "
            f"You are on call for {name} and must troubleshoot {label} methodically — triage symptoms, find root cause, apply the smallest safe fix, and confirm recovery."
        )
        initial_state = (
            f"The {profile['env']} is degraded. {symptom.capitalize()}. "
            f"Recent changes may exist around {label}, but do not restart blindly — gather evidence first."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": f"Triage: {inspect}. Capture timestamps, error messages, and what still works.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Separate symptom from cause. Fix the underlying misconfiguration, not only the noisy log line.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Verify recovery: {verify}. Document the fix, add `# FIXED-OK` to `{marker}`, and rerun Check Solution.",
            },
        ]
    elif kind == "security":
        description = (
            f"Security review: harden {label} on this {name} system. "
            f"Close unsafe defaults, enforce least privilege, and ensure {concept} cannot be abused — without breaking legitimate use."
        )
        initial_state = (
            f"The environment is functional but overly permissive around {label}. "
            "Assume an auditor or pen test is next week — tighten controls with evidence."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": f"Baseline current exposure: {inspect}. Note world-readable files, open ports, or excessive roles.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Apply least privilege incrementally. Prefer explicit allows over broad wildcards.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Re-test legitimate workflows after hardening. Finish with `# FIXED-OK` in `{marker}` and Check Solution.",
            },
        ]
    elif kind == "backup":
        description = (
            f"Backup and recovery drill for {label}. "
            f"Ensure backups run on schedule, retention is correct, and you can restore {concept} within the lab RTO."
        )
        initial_state = (
            f"Backup jobs exist but reliability is uncertain for {label}. "
            "Leadership wants proof that restore works — not just that backup scripts exit zero."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": "Inspect backup schedules, last success time, and destination free space.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Run or repair the backup job, then perform a controlled restore to a scratch location.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Compare restored data to source. Complete the lab via `# FIXED-OK` in `{marker}`.",
            },
        ]
    elif kind == "integration":
        description = (
            f"Integration lab: connect {label} with an adjacent platform in the {name} stack. "
            f"Validate authentication, data handoff, and failure behavior for {concept}."
        )
        initial_state = (
            f"Two systems are deployed but not fully wired together for {label}. "
            "Downstream consumers are waiting on this integration path."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": "Map the contract: which endpoints, queues, files, or CRDs connect the systems?",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Configure credentials and networking first, then test a minimal happy-path transaction.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Run an end-to-end check plus one failure case. Mark `{marker}` with `# FIXED-OK` when green.",
            },
        ]
    elif kind == "observability":
        description = (
            f"Observability task: make {label} visible in logs, metrics, or traces. "
            f"On-call should answer 'what is broken?' quickly using signals from {concept}."
        )
        initial_state = (
            f"The system runs, but {label} lacks useful telemetry. "
            "Dashboards/alerts are blank or noisy — improve signal quality."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": f"Find existing signals: {inspect}. Identify what is missing for fast triage.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Add or fix exporters/dashboards/alerts with clear names, labels, and thresholds.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Trigger a test event and confirm it appears where on-call looks. Complete via `{marker}`.",
            },
        ]
    elif kind == "automation":
        description = (
            f"Automation lab: remove toil around {label}. "
            f"Codify repeatable steps for {concept} and prove the automation is idempotent."
        )
        initial_state = (
            f"Operators still perform manual steps for {label}. "
            "Automate the boring parts without hiding important safety checks."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": "Write down the manual checklist. Circle steps that are safe to automate first.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Implement automation with dry-run/check mode when available. Run it twice — second run should be clean.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Attach logging and failure notifications. Finish with `# FIXED-OK` in `{marker}`.",
            },
        ]
    elif kind == "production":
        description = (
            f"Production readiness for {label}. "
            f"Harden, document, and validate {concept} so the change is safe to run during a maintenance window."
        )
        initial_state = (
            f"A feature fix works in dev, but {label} is not production ready — missing guardrails, runbooks, or capacity checks."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": "Review SLO impact, rollback plan, and blast radius before changing production settings.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": f"Apply production standards: limits, monitoring, and access controls for {label}.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Run post-change verification: {verify}. Record `# FIXED-OK` in `{marker}` when complete.",
            },
        ]
    else:  # operate
        description = (
            f"Day-2 operations: perform a routine {label} task safely in {name}. "
            f"Follow change control — inspect, change, verify — while working with {concept}."
        )
        initial_state = (
            f"The {profile['env']} is healthy enough for scheduled work on {label}. "
            "Complete the maintenance task without unnecessary downtime."
        )
        hints = [
            {
                "order": 1,
                "cost": 10,
                "content": f"Pre-check: {inspect}. Confirm backups or snapshots if the change is risky.",
            },
            {
                "order": 2,
                "cost": 15,
                "content": "Execute the maintenance in small steps. Prefer reversible changes.",
            },
            {
                "order": 3,
                "cost": 20,
                "content": f"Post-check: {verify}. Add `# FIXED-OK` to `{marker}` and run Check Solution.",
            },
        ]

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

    profile = TECH_PROFILES.get(tech_dir, {"domain": tech_dir.replace("-", " "), "env": "practice environment"})
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
    if not hints[0].get("content"):
        hints[0]["content"] = f"Start with read-only discovery on the {profile['env']}: logs, status commands, and config related to {label}."
    if not hints[1].get("content") or "smallest correct change" in hints[1]["content"].lower():
        hints[1]["content"] = "Change one thing at a time. Prefer reversible fixes and note evidence before/after."
    if not hints[2].get("content"):
        hints[2]["content"] = "Re-run the failing check or user workflow to confirm the incident is resolved."

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
