"""
Programmatic zero-to-hero course catalog — expands into full Tutorial seed specs.

Called from seed_tutorials so we ship hundreds of structured modules without
hand-authoring giant JSON files.
"""

from __future__ import annotations

LEVEL_BY_MODULE = (
    "beginner",
    "beginner",
    "intermediate",
    "intermediate",
    "advanced",
    "advanced",
    "expert",
    "expert",
    "enterprise",
    "enterprise",
)

DIFFICULTY_BY_LEVEL = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
    "expert": "advanced",
    "enterprise": "advanced",
}

# course_slug, course_title, topic, playground_slug, module titles
COURSE_DEFINITIONS: list[dict] = [
    {
        "course_slug": "linux-sysadmin-zero-hero",
        "course_title": "Linux Sysadmin: Zero to Hero",
        "topic": "Linux",
        "playground_slug": "linux",
        "modules": [
            "Shell navigation and file hierarchy",
            "Users, groups, and permissions",
            "Package managers and services",
            "Processes, signals, and systemd",
            "Storage, partitions, and LVM",
            "Networking, DNS, and firewalls",
            "Logs, journald, and troubleshooting",
            "Shell scripting fundamentals",
            "Security hardening and SELinux basics",
            "Production runbooks and on-call drills",
        ],
    },
    {
        "course_slug": "docker-containers-zero-hero",
        "course_title": "Docker & Containers: Zero to Hero",
        "topic": "Docker",
        "playground_slug": "docker",
        "modules": [
            "Images, layers, and registries",
            "Running containers and port mapping",
            "Volumes and bind mounts",
            "Dockerfile best practices",
            "Compose multi-service stacks",
            "Networking and service discovery",
            "Resource limits and health checks",
            "Security scanning and rootless mode",
            "CI/CD image pipelines",
            "Production orchestration handoff to Kubernetes",
        ],
    },
    {
        "course_slug": "terraform-iac-zero-hero",
        "course_title": "Terraform & IaC: Zero to Hero",
        "topic": "Terraform",
        "playground_slug": "terraform",
        "modules": [
            "HCL syntax and state basics",
            "Providers, resources, and data sources",
            "Variables, outputs, and locals",
            "Modules and composition",
            "Remote state and locking",
            "Workspaces and environments",
            "Plan/apply workflows in CI",
            "Drift detection and import",
            "Policy as code with Sentinel/OPA",
            "Enterprise module registry patterns",
        ],
    },
    {
        "course_slug": "ansible-automation-zero-hero",
        "course_title": "Ansible Automation: Zero to Hero",
        "topic": "Ansible",
        "playground_slug": "ansible",
        "modules": [
            "Inventory and ad-hoc commands",
            "Playbooks, tasks, and handlers",
            "Roles and directory layout",
            "Variables, facts, and templates",
            "Vault secrets and dynamic inventory",
            "Conditionals, loops, and blocks",
            "Roles from Galaxy and collections",
            "AWX / Automation Controller intro",
            "CI pipelines with ansible-lint",
            "Large-scale rollout patterns",
        ],
    },
    {
        "course_slug": "aws-cloud-zero-hero",
        "course_title": "AWS Cloud Engineering: Zero to Hero",
        "topic": "AWS",
        "playground_slug": "aws",
        "modules": [
            "IAM, accounts, and Organizations",
            "VPC design and security groups",
            "EC2, AMIs, and launch templates",
            "S3, IAM policies, and encryption",
            "RDS, backups, and Multi-AZ",
            "ELB, Auto Scaling, and health checks",
            "CloudWatch metrics and alarms",
            "Lambda and event-driven patterns",
            "EKS and container workloads",
            "Well-Architected review and cost ops",
        ],
    },
    {
        "course_slug": "azure-cloud-zero-hero",
        "course_title": "Azure Cloud Engineering: Zero to Hero",
        "topic": "Azure",
        "playground_slug": "azure",
        "modules": [
            "Subscriptions, RBAC, and policies",
            "Virtual networks and NSGs",
            "VMs, disks, and availability sets",
            "Storage accounts and blob lifecycle",
            "Azure SQL and backup policies",
            "Load Balancer and Application Gateway",
            "Monitor, alerts, and Log Analytics",
            "Functions and Event Grid",
            "AKS cluster operations",
            "Landing zones and governance",
        ],
    },
    {
        "course_slug": "gcp-cloud-zero-hero",
        "course_title": "GCP Cloud Engineering: Zero to Hero",
        "topic": "GCP",
        "playground_slug": "gcp",
        "modules": [
            "Projects, IAM, and org policies",
            "VPC, subnets, and firewall rules",
            "Compute Engine and instance groups",
            "Cloud Storage and IAM conditions",
            "Cloud SQL HA and PITR",
            "Load balancing and Cloud CDN",
            "Cloud Monitoring and SLOs",
            "Cloud Functions and Pub/Sub",
            "GKE cluster administration",
            "FinOps and reliability engineering",
        ],
    },
    {
        "course_slug": "networking-vyos-zero-hero",
        "course_title": "Networking & VyOS: Zero to Hero",
        "topic": "Networking",
        "playground_slug": "networking",
        "modules": [
            "OSI model and packet flow",
            "IP addressing and subnetting",
            "Routing, static routes, and OSPF basics",
            "NAT, PAT, and firewall zones",
            "VyOS CLI and configuration management",
            "VPN site-to-site with IPsec",
            "BGP fundamentals for multi-homing",
            "QoS, shaping, and bufferbloat",
            "Network troubleshooting toolkit",
            "Enterprise WAN design patterns",
        ],
    },
    {
        "course_slug": "security-engineering-zero-hero",
        "course_title": "Security Engineering: Zero to Hero",
        "topic": "Security",
        "playground_slug": "security",
        "modules": [
            "Threat modeling and attack surfaces",
            "Identity, MFA, and SSO patterns",
            "Secrets management and Vault",
            "TLS, certificates, and mTLS",
            "Container and supply-chain security",
            "SIEM, detection, and incident response",
            "WAF, DDoS, and edge protection",
            "Compliance frameworks (SOC2, ISO)",
            "Purple-team exercises",
            "Security automation in CI/CD",
        ],
    },
    {
        "course_slug": "git-cicd-zero-hero",
        "course_title": "Git & CI/CD: Zero to Hero",
        "topic": "Git",
        "playground_slug": "git",
        "modules": [
            "Git objects, branches, and remotes",
            "Merge vs rebase workflows",
            "Pull requests and code review",
            "GitHub Actions / GitLab CI basics",
            "Build matrices and caching",
            "Artifact promotion and environments",
            "Deployment strategies (blue/green, canary)",
            "Secrets in CI and OIDC to cloud",
            "Quality gates: lint, test, SAST",
            "Release engineering at scale",
        ],
    },
    {
        "course_slug": "postgresql-dba-zero-hero",
        "course_title": "PostgreSQL DBA: Zero to Hero",
        "topic": "PostgreSQL",
        "playground_slug": "postgresql",
        "modules": [
            "Installation and psql essentials",
            "Schemas, types, and constraints",
            "Indexes and EXPLAIN plans",
            "Transactions, MVCC, and locks",
            "Replication and streaming standby",
            "Backups with pg_dump and PITR",
            "Connection pooling and PgBouncer",
            "Vacuum, bloat, and autovacuum tuning",
            "Monitoring with pg_stat views",
            "High-availability Patroni patterns",
        ],
    },
    {
        "course_slug": "python-devops-zero-hero",
        "course_title": "Python for DevOps: Zero to Hero",
        "topic": "Python",
        "playground_slug": "python",
        "modules": [
            "Python syntax and virtual environments",
            "Files, JSON, and subprocess",
            "Requests, APIs, and retries",
            "Boto3 and cloud automation",
            "Fabric / Paramiko for remote ops",
            "FastAPI microservices",
            "Testing with pytest",
            "Packaging and Docker for Python apps",
            "Async IO for high-throughput tools",
            "Building internal platform CLIs",
        ],
    },
    {
        "course_slug": "nginx-loadbalancing-zero-hero",
        "course_title": "Nginx & Load Balancing: Zero to Hero",
        "topic": "Nginx",
        "playground_slug": "nginx",
        "modules": [
            "Nginx architecture and events model",
            "Virtual hosts and reverse proxy",
            "TLS termination and HTTP/2",
            "Upstream pools and health checks",
            "Rate limiting and connection limits",
            "Caching and compression",
            "WebSocket and sticky sessions",
            "ModSecurity and WAF basics",
            "Observability and access log analytics",
            "High-availability pairs and failover",
        ],
    },
    {
        "course_slug": "redis-caching-zero-hero",
        "course_title": "Redis & Caching: Zero to Hero",
        "topic": "Redis",
        "playground_slug": "redis",
        "modules": [
            "Data structures and key design",
            "TTL, eviction, and memory policies",
            "Pub/Sub and streams",
            "Persistence: RDB vs AOF",
            "Replication and read replicas",
            "Redis Sentinel failover",
            "Redis Cluster sharding",
            "Caching patterns for web apps",
            "Rate limiting and session stores",
            "Production monitoring and slowlog",
        ],
    },
    {
        "course_slug": "vmware-vsphere-zero-hero",
        "course_title": "VMware vSphere: Zero to Hero",
        "topic": "VMware",
        "playground_slug": "vmware",
        "modules": [
            "vCenter inventory and datacenters",
            "ESXi hosts and clusters",
            "VM provisioning and templates",
            "Storage: VMFS, NFS, and vSAN intro",
            "Networking: vSwitches and port groups",
            "vMotion and DRS",
            "HA, admission control, and FT intro",
            "Snapshots and backup integration",
            "Monitoring with vRealize / Aria",
            "Troubleshooting CPU ready and storage latency",
        ],
    },
    {
        "course_slug": "monitoring-observability-zero-hero",
        "course_title": "Monitoring & Observability: Zero to Hero",
        "topic": "Monitoring",
        "playground_slug": "monitoring",
        "modules": [
            "Metrics, logs, and traces overview",
            "Prometheus scrape and PromQL",
            "Grafana dashboards and variables",
            "Alertmanager routing and silences",
            "SLOs, error budgets, and burn rates",
            "Loki log aggregation",
            "OpenTelemetry instrumentation",
            "On-call runbooks and incident response",
            "Capacity planning from metrics",
            "Observability in Kubernetes",
        ],
    },
    {
        "course_slug": "windows-server-zero-hero",
        "course_title": "Windows Server: Zero to Hero",
        "topic": "Windows",
        "playground_slug": "windows",
        "modules": [
            "Server Manager and roles",
            "Active Directory and Group Policy",
            "DNS and DHCP on Windows",
            "IIS and reverse proxy",
            "PowerShell remoting and DSC intro",
            "Failover clustering",
            "WSUS and patch management",
            "Event logs and performance counters",
            "Hyper-V and nested virtualization",
            "Hybrid identity with Azure AD",
        ],
    },
    {
        "course_slug": "mysql-dba-zero-hero",
        "course_title": "MySQL DBA: Zero to Hero",
        "topic": "MySQL",
        "playground_slug": "mysql",
        "modules": [
            "Installation and mysql client",
            "Schemas, engines, and charset",
            "Indexes and query optimization",
            "Replication: async and semi-sync",
            "Backups with mysqldump and binlog",
            "Users, grants, and least privilege",
            "InnoDB tuning and buffer pool",
            "ProxySQL and connection routing",
            "Monitoring with performance_schema",
            "Galera / Group Replication intro",
        ],
    },
    {
        "course_slug": "kubernetes-platform-zero-hero",
        "course_title": "Kubernetes Platform Engineering: Zero to Hero",
        "topic": "Kubernetes",
        "playground_slug": "kubernetes",
        "modules": [
            "Pods, Deployments, and Services",
            "ConfigMaps, Secrets, and volumes",
            "Ingress, TLS, and external DNS",
            "RBAC, PSP/PSA, and network policies",
            "Helm charts and releases",
            "Observability: metrics, logs, traces",
            "Cluster autoscaling and quotas",
            "GitOps with Argo CD / Flux",
            "Service mesh fundamentals",
            "Multi-cluster and disaster recovery",
        ],
    },
    {
        "course_slug": "baremetal-maas-zero-hero",
        "course_title": "Bare Metal & MAAS: Zero to Hero",
        "topic": "Bare Metal",
        "playground_slug": "baremetal",
        "modules": [
            "PXE boot and DHCP/TFTP chain",
            "MAAS regions, racks, and fabrics",
            "Commissioning and hardware testing",
            "IPMI/BMC power management",
            "VLANs, subnets, and static routes",
            "Image customization and cloud-init",
            "GPU nodes and thermal management",
            "Juju / Ansible handoff after deploy",
            "Storage fabrics and RAID controllers",
            "Production bare-metal fleet ops",
        ],
    },
]


def all_course_definitions() -> list[dict]:
    """Base + extended tracks for seed expansion."""
    try:
        from .course_catalog_tracks import EXTENDED_COURSES

        return COURSE_DEFINITIONS + EXTENDED_COURSES
    except ImportError:
        return list(COURSE_DEFINITIONS)


def _sections_for_module(course: dict, module_title: str, level: str) -> list:
    """Full learning-module structure: theory through RCA (enterprise-grade)."""
    topic = course["topic"]
    playground = course.get("playground_slug") or topic.lower()
    t = module_title
    tl = t.lower()
    code_sample = (
        f"# {t} — {topic} ({level})\n"
        f"# Open the {topic} playground or linked lab scenario\n"
        f"help 2>/dev/null | head -5 || echo 'Practice {tl} hands-on'"
    )
    return [
        (
            "Theory",
            f"**{t}** in {topic} is foundational at the **{level}** tier. "
            f"Operators use this daily in production: design reviews, change windows, and on-call. "
            f"Read this section before touching systems — understanding *why* prevents costly mistakes.",
            "",
            "text",
            "",
        ),
        (
            "Architecture",
            f"Map the control plane vs data plane for {tl}. "
            f"Identify upstream dependencies (network, identity, storage) and downstream consumers. "
            f"Draw a one-page diagram: components, trust boundaries, and failure domains.",
            "",
            "text",
            "",
        ),
        (
            "Core concepts",
            f"Key terms for {tl}: lifecycle states, idempotency, blast radius, and rollback paths. "
            f"At {level} depth you should explain each concept without notes and tie it to a real component.",
            code_sample,
            "bash",
            f"Run in the {topic} playground.",
        ),
        (
            "Use cases",
            f"Common {topic} scenarios requiring {tl}: greenfield deploys, migrations, incident recovery, "
            f"compliance audits, and cost optimization. Match each use case to metrics and SLIs.",
            "",
            "text",
            "",
        ),
        (
            "Hands-on labs",
            f"Complete the linked FixitLab scenario for {tl}. "
            f"Follow hints only after attempting diagnosis. Document commands run and outcomes in your runbook.",
            code_sample,
            "bash",
            "Use Check Solution when the lab scenario is linked.",
        ),
        (
            "Interactive simulations",
            f"Where available, use the {topic} simulator to reproduce {tl} without production risk. "
            f"Compare simulated metrics/logs to what you would expect on bare metal or cloud.",
            "",
            "text",
            "",
        ),
        (
            "Projects",
            f"Capstone: implement {tl} end-to-end in a sandbox — IaC, CI gate, monitoring, and rollback. "
            f"Deliverables: architecture doc, test evidence, and an operator handoff checklist.",
            "",
            "text",
            "",
        ),
        (
            "Troubleshooting",
            f"When {tl} fails: (1) scope impact, (2) collect logs/metrics/traces, (3) bisect recent changes, "
            f"(4) validate dependencies, (5) execute rollback or mitigation, (6) confirm recovery.",
            "",
            "text",
            "",
        ),
        (
            "Interview questions",
            f"Practice explaining {tl} in 2 minutes, then deep-dive on trade-offs. "
            f"Expect follow-ups on failure modes, security, and how you measured success in past roles.",
            "",
            "text",
            "",
        ),
        (
            "Scenario questions",
            f"Situational prompt: \"{t} is degraded in production — walk me through your first 15 minutes.\" "
            f"Structure: stabilize, communicate, diagnose, fix, verify, postmortem.",
            "",
            "text",
            "",
        ),
        (
            "Assessments",
            f"Self-check: can you perform {tl} unaided, teach it to a junior, and defend design choices to security? "
            f"Score each dimension 1–5; below 4 means repeat the lab and simulation.",
            "",
            "text",
            "",
        ),
        (
            "Certification exam prep",
            f"Map this module to vendor objectives (RHCSA/RHCE, CKA/CKAD, AWS SA, etc.) for {topic}. "
            f"Note objective IDs in your study plan and cross-link FixitLab certification tracks.",
            "",
            "text",
            "",
        ),
        (
            "Enterprise production examples",
            f"At enterprise scale, {tl} runs with change advisory boards, automated compliance scans, "
            f"multi-region failover, and audited break-glass. Review a sanitized runbook from a Fortune-500 pattern.",
            "",
            "text",
            "",
        ),
        (
            "Best practices",
            f"Automate {tl}, keep changes small, test in staging that mirrors prod, and maintain golden paths. "
            f"Prefer GitOps / IaC over snowflake servers.",
            "",
            "text",
            "",
        ),
        (
            "Security practices",
            f"Apply least privilege, encrypt data in transit/at rest, rotate credentials, and scan artifacts. "
            f"Threat-model {tl} for insider abuse and supply-chain tampering.",
            "",
            "text",
            "",
        ),
        (
            "Performance tuning",
            f"Profile {tl} under load: CPU, memory, I/O, and latency percentiles. "
            f"Set baselines; tune only with before/after evidence.",
            "",
            "text",
            "",
        ),
        (
            "Monitoring",
            f"Define SLIs/SLOs for {tl}. Dashboards should answer: \"Are we healthy?\" and \"Why not?\" "
            f"Wire alerts to runbooks — pages must be actionable.",
            "",
            "text",
            "",
        ),
        (
            "Real incidents",
            f"Study a public postmortem related to {topic}. Extract signals that would have caught the issue earlier "
            f"and how {tl} skills would shorten mean time to recovery.",
            "",
            "text",
            "",
        ),
        (
            "Root cause analysis",
            f"After any {tl} incident: timeline, contributing factors, corrective vs preventive actions, "
            f"and verification that fixes hold under load. Blameless culture; focus on systems.",
            "",
            "text",
            f"Next module in {course['course_title']} builds on this foundation.",
        ),
    ]


def build_catalog_specs(base_order: int = 400) -> list[dict]:
    """Expand COURSE_DEFINITIONS into Tutorial seed dicts."""
    specs: list[dict] = []
    order = base_order
    for course in all_course_definitions():
        for idx, module_title in enumerate(course["modules"], start=1):
            level = LEVEL_BY_MODULE[min(idx - 1, len(LEVEL_BY_MODULE) - 1)]
            slug_part = module_title.lower()
            for ch, rep in ((" ", "-"), ("/", "-"), (",", ""), ("&", "and"), ("(", ""), (")", "")):
                slug_part = slug_part.replace(ch, rep)
            slug = f"{course['course_slug']}-m{idx:02d}-{slug_part[:40].strip('-')}"
            specs.append(
                {
                    "slug": slug,
                    "title": f"{course['topic']}: {module_title}",
                    "summary": f"Module {idx} — {module_title} ({level} track).",
                    "topic": course["topic"],
                    "difficulty": DIFFICULTY_BY_LEVEL.get(level, "intermediate"),
                    "estimated_minutes": 35 + (idx * 3),
                    "playground_slug": course.get("playground_slug", ""),
                    "scenario_slug": "",
                    "order": order,
                    "course_slug": course["course_slug"],
                    "course_title": course["course_title"],
                    "module_order": idx,
                    "level_track": level,
                    "seo_title": f"{module_title} — {course['course_title']}",
                    "seo_description": f"Module {idx} of {course['course_title']}: {module_title}. Hands-on {course['topic']} training from zero to hero.",
                    "seo_keywords": f"{course['topic'].lower()}, {module_title.lower()}, zero to hero, devops tutorial, {level}",
                    "sections": _sections_for_module(course, module_title, level),
                }
            )
            order += 1
    return specs
