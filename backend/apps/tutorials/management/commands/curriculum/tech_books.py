"""
Textbook-style chapters for every tutorial technology.

Each topic maps to a category book plus topic-specific overrides.
Every module gets full theory, architecture, notes, and explanations.
"""

from __future__ import annotations

import re

LEVEL_LABELS = {
    "beginner": "Beginner",
    "intermediate": "Intermediate",
    "advanced": "Advanced",
    "expert": "Expert",
    "enterprise": "Real Enterprise",
}

# Rich paragraphs per section type (category-level textbook content)
CATEGORY_SECTIONS: dict[str, dict[str, list[str]]] = {
    "database": {
        "theory": [
            "Relational and distributed data systems underpin every enterprise application. You must understand how data is modeled, stored, queried, replicated, and recovered before you touch production.",
            "Transactions group work into atomic units. Isolation levels control what concurrent sessions see. Durability comes from write-ahead logs and replicated storage.",
            "Schema design affects performance for years. Normalize to reduce redundancy; denormalize deliberately for read-heavy paths with clear ownership of update anomalies.",
        ],
        "architecture": [
            "Clients connect through connection pools to a primary database. Read replicas serve analytics and read scaling. Backups and WAL archiving enable point-in-time recovery.",
            "Separate OLTP from OLAP workloads. Heavy reporting on primary causes lock contention and replication lag that manifests as user-facing latency.",
        ],
        "concepts": [
            "Primary keys, foreign keys, indexes, and query plans are daily tools. EXPLAIN output is evidence — never tune without before/after metrics.",
            "Replication lag, bloat, and connection exhaustion are the top production killers. Monitor them proactively.",
        ],
        "labs": [
            "Practice schema creation, transactional commits and rollbacks, index creation, EXPLAIN ANALYZE, backup/restore drills, and failover simulation in FixitLab database labs.",
        ],
        "notes": [
            "Always test restores — backups you have not restored are Schrödinger's backups.",
            "Use least-privilege DB roles for applications; never run apps as superuser.",
        ],
    },
    "linux": {
        "theory": [
            "Linux is the operating system of the cloud and enterprise data center. The kernel mediates hardware, the shell orchestrates automation, and systemd manages service lifecycle.",
            "Everything is a file — devices, sockets, and processes expose interfaces through the filesystem. Permissions and SELinux enforce mandatory access control beyond discretionary rwx bits.",
            "RHCSA/RHCE-level skills mean you can install, configure, troubleshoot, automate, and secure RHEL and clones under time pressure.",
        ],
        "architecture": [
            "Boot flow: firmware/UEFI → bootloader (GRUB) → kernel → initramfs → systemd → target units. Failed units block dependencies — read journalctl first.",
            "Storage stack: block device → partition → LVM PV/VG/LV → filesystem (xfs/ext4) → mount unit. Network: NIC → NetworkManager → routes → firewalld/nftables.",
        ],
        "concepts": [
            "systemd units, cgroups v2, namespaces, and containers share the same kernel primitives. LVM and RAID protect against disk failure; they do not replace backups.",
        ],
        "labs": [
            "Practice user management, systemd services, LVM extend, SELinux contexts, firewalld rules, journal analysis, and shell scripting in FixitLab Linux terminal labs.",
        ],
        "notes": [
            "Before chmod 777, ask whether SELinux or ACLs are the real blocker.",
            "Document every production change in a ticket with rollback steps.",
        ],
    },
    "kubernetes": {
        "theory": [
            "Kubernetes orchestrates containers at scale. It reconciles desired state (YAML in etcd) with actual cluster state through controllers.",
            "Pods are ephemeral; Deployments, StatefulSets, and DaemonSets express different workload patterns. Services provide stable networking; Ingress exposes HTTP routes.",
            "Production clusters require RBAC, network policies, resource quotas, pod security, backup of etcd, and upgrade strategy.",
        ],
        "architecture": [
            "Control plane: API server, etcd, scheduler, controller-manager. Worker nodes: kubelet, kube-proxy, CRI runtime. Add-ons: CNI, CSI, ingress controller, cert-manager.",
            "GitOps (Argo CD, Flux) treats Git as source of truth for cluster state — preferred over kubectl apply from laptops.",
        ],
        "concepts": [
            "Probes (liveness, readiness, startup) prevent traffic to broken pods. Resource requests/limits affect scheduling and OOM behavior.",
        ],
        "labs": [
            "Deploy workloads, debug with kubectl describe/logs, configure Ingress, apply NetworkPolicy, install Helm chart, and simulate pod failure recovery.",
        ],
        "notes": [
            "kubectl delete pod is not a fix — find the controller and fix the spec.",
            "Never expose the Kubernetes API publicly without strong auth and audit logging.",
        ],
    },
    "container": {
        "theory": [
            "Containers package applications with dependencies using Linux namespaces and cgroups. OCI images are immutable layers; registries distribute them.",
            "Docker/Podman/Containerd are runtime stacks — know which you run in production and how Kubernetes CRI interacts with containerd.",
        ],
        "architecture": [
            "Build pipeline produces signed images → registry → pull on host → CRI creates container from image + runtime config → optional orchestrator manages lifecycle.",
        ],
        "labs": [
            "Build Dockerfile, run containers, map ports/volumes, use Compose/Podman pods, scan images, and practice rootless mode.",
        ],
        "notes": [
            "Pin image digests in production; tags are mutable.",
        ],
    },
    "iac": {
        "theory": [
            "Infrastructure as Code declares desired cloud/state resources in version-controlled files. Plan/apply workflows preview changes before execution.",
            "State tracks mapping between code addresses and real resource IDs. Remote state with locking prevents concurrent corruption.",
        ],
        "architecture": [
            "Modules encapsulate reusable patterns. CI runs plan on PR; apply from trusted pipeline with OIDC to cloud — not long-lived keys on laptops.",
        ],
        "labs": [
            "Write modules, run init/plan/apply, practice drift detection, import existing resources, and use the FixitLab Terraform Lab Environment.",
        ],
        "notes": [
            "terraform apply without plan review is how outages happen.",
        ],
    },
    "automation": {
        "theory": [
            "Configuration management ensures systems converge to declared state. Ansible is agentless over SSH; AWX adds RBAC, scheduling, and surveys.",
            "Idempotency means re-running playbooks is safe — essential for continuous compliance.",
        ],
        "labs": [
            "Write inventory, ad-hoc modules, playbooks with roles, vault secrets, and AWX job templates.",
        ],
        "notes": [
            "Test playbooks with --check --diff before production.",
        ],
    },
    "monitoring": {
        "theory": [
            "Observability combines metrics, logs, and traces. SLIs measure behavior; SLOs set targets; error budgets guide release velocity.",
            "Prometheus pulls metrics; Grafana visualizes; Loki aggregates logs; Tempo/Jaeger store traces. Correlate all three during incidents.",
        ],
        "labs": [
            "Write PromQL, build Grafana dashboards, configure alerts, explore logs in Loki, and follow traces across services.",
        ],
        "notes": [
            "Alert on symptoms tied to SLOs, not every CPU spike.",
        ],
    },
    "network": {
        "theory": [
            "Networks move packets through switching (L2), routing (L3), and policy (firewall, NAT, VPN). DNS maps names to addresses — broken DNS looks like app failure.",
            "BGP connects autonomous systems on the Internet and in enterprise WANs. OSPF links internal routers.",
        ],
        "labs": [
            "Configure interfaces, static routes, OSPF/BGP peers, firewall rules, VPN tunnels, and troubleshoot with tcpdump, mtr, dig.",
        ],
        "notes": [
            "Change windows for routing — commit confirm on VyOS saves careers.",
        ],
    },
    "security": {
        "theory": [
            "Security is layered: identity, network segmentation, encryption, detection, response. Zero trust verifies every request regardless of network location.",
            "DevSecOps embeds scanning in CI. SOC/SIEM teams detect and respond to threats using correlated telemetry.",
        ],
        "labs": [
            "Harden systems, analyze alerts, write detection rules, practice incident triage, and run tabletop exercises.",
        ],
        "notes": [
            "Assume breach — design so compromise of one credential does not own the estate.",
        ],
    },
    "cloud": {
        "theory": [
            "Cloud providers offer shared-responsibility security: they secure the platform; you secure your data, IAM, and configurations.",
            "Design for multi-AZ resilience, autoscaling, managed services, and cost visibility from day one.",
        ],
        "labs": [
            "Provision VPC/VNet, IAM roles, compute, storage, databases, and Kubernetes with IaC and validate with CLI.",
        ],
        "notes": [
            "Tag every resource — untagged spend is unowned spend.",
        ],
    },
    "frontend": {
        "theory": [
            "The web platform combines semantic HTML, accessible CSS, and JavaScript. Modern SPAs use React with TypeScript for maintainability.",
            "Performance (Core Web Vitals), accessibility (WCAG), and security (XSS, CSP) are non-negotiable in production frontends.",
        ],
        "labs": [
            "Build responsive layouts, React components, Next.js routes, test with RTL, and audit with Lighthouse.",
        ],
        "notes": [
            "Never trust user input — sanitize and encode output.",
        ],
    },
    "backend": {
        "theory": [
            "Backend systems expose APIs, persist data, enqueue async work, and integrate with identity providers. Design for horizontal scale and graceful degradation.",
            "Frameworks (Django, FastAPI, Express) accelerate development but you still own schema design, auth, and observability.",
        ],
        "labs": [
            "Build REST APIs, connect databases, add auth, write tests, containerize, and load-test endpoints.",
        ],
        "notes": [
            "Version your API; never break clients silently.",
        ],
    },
    "ai": {
        "theory": [
            "AI systems combine data pipelines, model training, evaluation, deployment, and monitoring. LLMOps adds prompt versioning, RAG, and guardrails.",
            "GPU infrastructure requires driver management, thermal monitoring, scheduling, and inference optimization (batching, quantization).",
        ],
        "labs": [
            "Profile GPU usage, deploy inference servers (vLLM/Triton), instrument RAG pipelines, and run eval suites.",
        ],
        "notes": [
            "Track model lineage and dataset versions for reproducibility and audit.",
        ],
    },
    "datascience": {
        "theory": [
            "Data science workflows: ingest → clean → feature engineer → train → evaluate → deploy. Pandas and scikit-learn dominate tabular ML.",
            "Watch for leakage, bias, and overfitting. Production models need monitoring for drift.",
        ],
        "labs": [
            "Explore datasets with Pandas, visualize with Matplotlib, train pipelines with scikit-learn, track experiments.",
        ],
        "notes": [
            "Notebooks are for exploration — production code lives in tested modules.",
        ],
    },
    "baremetal": {
        "theory": [
            "Bare metal means physical servers: BMC for out-of-band, PXE for boot, MAAS/Metal3 for provisioning, then OS and Kubernetes.",
            "Hardware failures are real — plan for disk, PSU, NIC, and GPU replacement without halting the fleet.",
        ],
        "labs": [
            "Use ipmitool, trace PXE boot, commission MAAS machines, customize cloud-init, and join nodes to clusters.",
        ],
        "notes": [
            "Firmware updates are changes — schedule them with rollback plans.",
        ],
    },
    "vcs": {
        "theory": [
            "Git tracks content-addressed snapshots. Branches are cheap; merge/rebase workflows affect history and CI triggers.",
            "Hosting platforms add PR reviews, branch protection, and CI/CD integration.",
        ],
        "labs": [
            "Branch, commit, rebase, resolve conflicts, open PRs, configure GitHub Actions or GitLab CI pipelines.",
        ],
        "notes": [
            "Never force-push shared branches without team agreement.",
        ],
    },
    "cicd": {
        "theory": [
            "CI builds and tests every change; CD promotes artifacts to environments with approval gates. Pipelines must be fast, cached, and secure.",
            "OIDC federation to cloud avoids long-lived CI secrets.",
        ],
        "labs": [
            "Author pipeline YAML, matrix builds, deploy to staging, run quality gates, promote to production.",
        ],
        "notes": [
            "Secrets in CI use platform secret stores — never echo them in logs.",
        ],
    },
    "vmware": {
        "theory": [
            "vSphere virtualizes compute on ESXi clusters managed by vCenter. VMs, storage, and networking are software-defined.",
            "HA, DRS, and vMotion provide resilience and load balancing. Snapshots are not backups.",
        ],
        "labs": [
            "Navigate inventory, create VMs, configure port groups, practice vMotion, and troubleshoot in the FixitLab VMware Lab Environment.",
        ],
        "notes": [
            "CPU ready time and storage latency dominate VM performance issues.",
        ],
    },
    "windows": {
        "theory": [
            "Windows Server runs AD, DNS, DHCP, GPO, and IIS. PowerShell is the automation backbone.",
            "Hybrid identity with Azure AD Connect links on-prem to cloud identity.",
        ],
        "labs": [
            "Use Server Manager, create AD users, apply GPO, analyze event logs, practice in the FixitLab Windows GUI Lab Environment.",
        ],
        "notes": [
            "Patch Tuesday — test patches in staging AD lab first.",
        ],
    },
    "enterprise_app": {
        "theory": [
            "Enterprise applications (PeopleSoft, Nginx, etc.) have specialized admin consoles, batch schedules, and integration buses.",
            "Treat upgrades as major projects with regression testing and rollback.",
        ],
        "labs": [
            "Navigate admin UI, run scheduled jobs, verify integrations, troubleshoot with vendor logs.",
        ],
        "notes": [
            "Read vendor release notes before any production change.",
        ],
    },
    "platform": {
        "theory": [
            "Platform engineering builds internal developer platforms (IDPs) with golden paths, self-service, and paved roads.",
            "DevOps culture metrics (DORA) measure delivery performance.",
        ],
        "labs": [
            "Design templates, document runbooks, automate toil, measure lead time and MTTR.",
        ],
        "notes": [
            "Automate the boring — humans should review exceptions, not repeat clicks.",
        ],
    },
    "simulation": {
        "theory": [
            "FixitLab Lab Environments mirror production safely: terminal markers, GUI consoles, cross-tech sessions, and graded scenarios.",
        ],
        "labs": [
            "Open Lab Environments from the lab toolbar, complete objectives, use hints sparingly, validate with Check Solution.",
        ],
        "notes": [
            "Treat Lab Server output like staging — build habits that transfer to real on-call.",
        ],
    },
}

# Default paragraphs for any section not defined in a category block (textbook depth)
_DEFAULT_SECTION_PARAS: dict[str, list[str]] = {
    "theory": [
        "Master the theory before configuration — understanding prevents outages under pressure.",
        "Every production system has a story: who uses it, what breaks, and how operators detect failure early.",
        "Read official documentation alongside this chapter; vendor docs change — verify version numbers.",
    ],
    "architecture": [
        "Draw components, data flows, and failure domains before implementing.",
        "Label trust boundaries: where authentication happens, where data is encrypted, where logs emit.",
        "Document RTO/RPO for stateful parts — executives ask during incidents.",
    ],
    "concepts": [
        "Learn precise terminology — ambiguous words cause wrong fixes on call.",
        "Build a personal glossary as you study; link each term to a metric or log line.",
        "If you cannot explain a concept to a junior, you do not yet understand it deeply enough.",
    ],
    "use_cases": [
        "Map each use case to SLIs and the team who approves production change.",
        "Greenfield, migration, incident recovery, and compliance audits repeat across all technologies.",
        "Cost optimization without SLO breach is a senior-level skill — measure utilization first.",
    ],
    "labs": [
        "Complete FixitLab hands-on labs; document commands and outcomes in your runbook.",
        "Run each lab twice: guided, then cold — muscle memory matters under stress.",
        "Never paste production secrets into lab environments.",
    ],
    "simulations": [
        "Use FixitLab Lab Environments to practice without production risk.",
        "Compare Lab Environment output to real vendor UIs and CLI — build transferable habits.",
        "Cross-tech labs link terminal fixes to GUI console state on the same Lab Server.",
    ],
    "projects": [
        "Deliver capstone with architecture diagram, IaC, CI output, dashboard, and rollback doc.",
        "Acceptance criteria: on-call can execute your runbook without calling you.",
        "Present capstone as if to a architecture review board.",
    ],
    "troubleshooting": [
        "Follow: scope impact → collect signals → bisect changes → validate dependencies → mitigate → verify.",
        "Capture logs before restart — evidence beats guesswork in postmortems.",
        "Communicate early; stakeholders prefer known issues over silence.",
    ],
    "interview": [
        "Practice explaining concepts aloud in under two minutes.",
        "Prepare one production story per module demonstrating your experience.",
        "System design questions want trade-offs with numbers — latency, cost, risk.",
    ],
    "scenario": [
        "Structure on-call response: stabilize, communicate, diagnose, fix, verify, postmortem.",
        "First 15 minutes matter most — have a personal checklist laminated.",
        "Escalate when impact or uncertainty exceeds your authority.",
    ],
    "assessment": [
        "Self-rate 1–5 on explain, execute, troubleshoot, teach, defend to security.",
        "Score below 4 on any dimension → repeat labs before advancing.",
        "FixitLab certification tracks provide timed validation.",
    ],
    "certification": [
        "Map module to vendor exam objectives and FixitLab cert tracks.",
        "Build objective ID → module → lab → mock question study sheet.",
        "Troubleshooting and security domains dominate practical exams.",
    ],
    "enterprise": [
        "Enterprise adds CAB, multi-region DR, audited break-glass, and contractual SLAs.",
        "Fortune-500 patterns include automated compliance scans and quarterly DR drills.",
        "Executive visibility requires plain-language status during incidents.",
    ],
    "best_practices": [
        "Automate, keep changes small, mirror prod in staging, document golden paths.",
        "Prefer GitOps and IaC over snowflake servers.",
        "Game days validate runbooks before real emergencies.",
    ],
    "security": [
        "Least privilege, encryption in transit/at rest, secrets management, supply-chain scanning.",
        "Threat-model insider and external attack paths for every component.",
        "Annual pen-test findings tracked to closure with owners.",
    ],
    "performance": [
        "Baseline before tuning; change one variable at a time; record evidence.",
        "Saturation appears before errors — watch queue depth and latency p99.",
        "Capacity plan with failover headroom (N+1 or multi-AZ).",
    ],
    "monitoring": [
        "Define SLI/SLO; actionable alerts only; multi-window burn rates for error budgets.",
        "Dashboards answer: healthy? if not, why?",
        "Every page links to a runbook with first steps.",
    ],
    "incidents": [
        "Study public postmortems; extract detection gaps and preventive controls.",
        "Timeline in UTC; blameless culture focuses on systems not people.",
        "Close loop when same alert fires less often.",
    ],
    "rca": [
        "Blameless RCA with timeline, contributing factors, corrective vs preventive actions.",
        "Verify fixes under load and chaos tests.",
        "Update monitors and runbooks — RCA without action is theatre.",
    ],
    "notes": [
        "Maintain a personal notebook of commands, warnings, exam tips, and interview stories.",
        "Revisit notes after 48 hours (spaced repetition).",
        "Link each note to a FixitLab lab you completed.",
    ],
}

TOPIC_CATEGORY: dict[str, str] = {
    "Database": "database", "PostgreSQL": "database", "MySQL": "database", "SQLite": "database",
    "MongoDB": "database", "Redis": "database",
    "Linux": "linux", "Bash": "linux", "RHEL": "linux",
    "Kubernetes": "kubernetes", "OpenShift": "kubernetes", "Helm": "kubernetes", "ArgoCD": "kubernetes",
    "Docker": "container", "Podman": "container", "Containerd": "container",
    "Terraform": "iac", "Pulumi": "iac", "CloudFormation": "iac", "Packer": "iac",
    "Ansible": "automation",
    "Monitoring": "monitoring", "Prometheus": "monitoring", "Grafana": "monitoring",
    "ELK": "monitoring", "Loki": "monitoring", "Tempo": "monitoring", "Jaeger": "monitoring",
    "Networking": "network", "VyOS": "network", "pfSense": "network", "MikroTik": "network", "Cisco": "network",
    "Cybersecurity": "security", "DevSecOps": "security", "IAM": "security", "SOC": "security", "SIEM": "security", "Security": "security",
    "AWS": "cloud", "Azure": "cloud", "GCP": "cloud",
    "HTML": "frontend", "CSS": "frontend", "JavaScript": "frontend", "TypeScript": "frontend",
    "React": "frontend", "Next.js": "frontend", "Frontend": "frontend",
    "Backend": "backend", "Python": "backend", "Django": "backend", "FastAPI": "backend",
    "Node.js": "backend", "Express.js": "backend",
    "AI Engineering": "ai", "AI Infrastructure": "ai",
    "Data Science": "datascience",
    "Bare Metal": "baremetal", "MAAS": "baremetal",
    "Git": "vcs", "GitHub": "vcs", "GitLab": "vcs", "Bitbucket": "vcs",
    "DevOps": "platform", "Jenkins": "cicd",
    "VMware": "vmware", "Windows": "windows", "Nginx": "enterprise_app", "PeopleSoft": "enterprise_app",
    "Simulation": "simulation",
}

# Topic-specific extra paragraphs (textbook depth)
TOPIC_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "Terraform": {
        "theory": [
            "HashiCorp Terraform uses HCL to declare providers and resources. State file terraform.tfstate is the source of mapping between configuration addresses and cloud resource IDs.",
            "Workspaces and modules separate environments and reusable patterns. Sentinel/OPA policy checks gate risky plans in enterprise pipelines.",
        ],
    },
    "Ansible": {
        "theory": [
            "Ansible modules are idempotent units of work executed over SSH or WinRM. Facts from setup module drive conditional logic.",
            "Roles organize tasks, handlers, templates, and defaults. Collections distribute vendor-supported content.",
        ],
    },
    "Prometheus": {
        "theory": [
            "Prometheus scrapes HTTP metrics endpoints on an interval. Time series are identified by metric name and label set.",
            "PromQL rate() converts counters to per-second rates. histogram_quantile computes latency percentiles from buckets.",
        ],
    },
    "Grafana": {
        "theory": [
            "Grafana connects to multiple datasources and unifies visualization. Dashboard variables enable multi-cluster views.",
            "Alert rules in Grafana 9+ unify metrics and logs alerting with contact points and notification policies.",
        ],
    },
    "Python": {
        "theory": [
            "Python 3 is the lingua franca of DevOps, data, and backend APIs. Virtual environments isolate dependencies per project.",
            "Type hints, pytest, and linters (ruff, mypy) keep large codebases maintainable.",
        ],
    },
    "GitHub": {
        "theory": [
            "GitHub Actions workflows trigger on push, PR, schedule, or webhook. Reusable workflows and composite actions reduce duplication.",
            "Branch protection requires reviews and passing checks before merge to main.",
        ],
    },
    "GitLab": {
        "theory": [
            "GitLab CI uses .gitlab-ci.yml with stages and jobs. Runners execute jobs; shared or project-specific.",
            "Merge trains and review apps improve multi-developer throughput.",
        ],
    },
    "AI Infrastructure": {
        "theory": [
            "GPU nodes need NVIDIA driver, container toolkit, and device plugin on Kubernetes. Monitor temperature, power, ECC errors, and GPU utilization.",
            "Inference stacks include vLLM, Triton, TensorRT-LLM, and KServe for model serving at scale.",
        ],
    },
    "Bare Metal": {
        "theory": [
            "IPMI/Redfish provide out-of-band power and console. PXE chain loads kernel via DHCP/TFTP/iPXE.",
            "MAAS automates commissioning, testing, and OS deployment on physical fleets.",
        ],
    },
    "VyOS": {
        "theory": [
            "VyOS uses commit/confirm — if you lose access, reboot reverts unconfirmed changes.",
            "Configuration modes: set, delete, commit. Show commands are read-only operational state.",
        ],
    },
}

# Auto-fill topic overrides for every catalog topic not explicitly listed above
def _build_auto_topic_overrides() -> dict[str, dict[str, list[str]]]:
    auto: dict[str, dict[str, list[str]]] = {}
    for topic, cat in TOPIC_CATEGORY.items():
        if topic in TOPIC_OVERRIDES:
            continue
        cat_name = cat.replace("_", " ")
        auto[topic] = {
            "theory": [
                f"**{topic}** is a core discipline in the {cat_name} category. Production teams hire for depth here because mistakes cause outages, security incidents, or runaway cost.",
                f"Study {topic} as a full stack: vocabulary, architecture, hands-on labs, troubleshooting, and enterprise governance — not as isolated trivia.",
            ],
            "architecture": [
                f"A typical {topic} deployment spans multiple components with clear control-plane vs data-plane separation. Draw diagrams before changing production.",
            ],
            "concepts": [
                f"Learn {topic}-specific terms precisely. Ambiguity during incidents wastes minutes you do not have.",
            ],
            "use_cases": [
                f"Map {topic} use cases to SLIs: greenfield, migration, incident recovery, compliance, and cost optimization each need different runbooks.",
            ],
            "troubleshooting": [
                f"When {topic} fails, collect logs and metrics first, correlate with recent changes, then mitigate with a documented rollback.",
            ],
            "monitoring": [
                f"Define {topic} SLIs (latency, errors, saturation) and wire dashboards before go-live — retroactive observability misses the first outage.",
            ],
            "security": [
                f"Apply least privilege, encryption, and audit logging to every {topic} component; threat-model insider and external paths.",
            ],
            "enterprise": [
                f"Enterprise {topic} adds change control, multi-region DR, audited break-glass, and contractual SLAs executives track during incidents.",
            ],
            "notes": [
                f"Keep a running {topic} notebook: commands, port numbers, config paths, exam objectives, and war stories from labs.",
            ],
        }
    return auto


TOPIC_OVERRIDES.update(_build_auto_topic_overrides())


def _category_for(topic: str) -> str:
    return TOPIC_CATEGORY.get(topic, "platform")


def _paragraphs(topic: str, section_key: str) -> list[str]:
    cat = _category_for(topic)
    cat_block = CATEGORY_SECTIONS.get(cat, CATEGORY_SECTIONS["platform"])
    cat_paras = list(cat_block.get(section_key) or [])
    default_paras = _DEFAULT_SECTION_PARAS.get(section_key, [])
    # Merge category textbook + universal defaults (dedupe while preserving order)
    seen = set(cat_paras)
    paras = cat_paras + [p for p in default_paras if p not in seen]
    overrides = TOPIC_OVERRIDES.get(topic, {}).get(section_key, [])
    paras.extend(overrides)
    return paras


def _module_focus(module: str, topic: str) -> list[str]:
    """Module-specific textbook paragraphs derived from title."""
    ml = module.lower()
    focus = [
        f"This chapter focuses on **{module}** within **{topic}**. Study it as a standalone unit that connects to prior and following modules in the course."
    ]
    # Split title into teachable units
    for part in re.split(r"[,/&]|\band\b", module, flags=re.I):
        part = part.strip()
        if len(part) < 4:
            continue
        focus.append(
            f"**{part}:** In production {topic} environments, {part.lower()} requires understanding configuration, "
            f"operational metrics, failure modes, security boundaries, and documented rollback. "
            f"Operators should maintain runbook entries for common {part.lower()} tasks and incidents. "
            f"When interviewing or on-call, you should explain how {part.lower()} interacts with adjacent "
            f"{topic} components and which SLIs prove it is healthy."
        )
    return focus


def build_book_section(
    topic: str,
    module: str,
    section_key: str,
    level: str,
) -> str:
    """Full textbook section body — category book + topic overrides + module focus."""
    heading_map = {
        "theory": "Theory",
        "architecture": "Architecture",
        "concepts": "Core concepts",
        "use_cases": "Use cases",
        "labs": "Hands-on labs",
        "simulations": "Lab Environment practice",
        "projects": "Projects",
        "troubleshooting": "Troubleshooting",
        "interview": "Interview questions",
        "scenario": "Scenario questions",
        "assessment": "Assessments",
        "certification": "Certification exam prep",
        "enterprise": "Enterprise production examples",
        "best_practices": "Best practices",
        "security": "Security practices",
        "performance": "Performance tuning",
        "monitoring": "Monitoring",
        "incidents": "Real incidents",
        "rca": "Root cause analysis",
        "notes": "Notes and key takeaways",
    }
    heading = heading_map.get(section_key, section_key.replace("_", " ").title())
    paras = _paragraphs(topic, section_key)
    parts = [
        f"## {heading}",
        "",
        f"**{topic} · {module} · {LEVEL_LABELS.get(level, level)} track**",
        "",
    ]
    for p in paras:
        parts.append(p)
        parts.append("")
    if section_key in ("theory", "concepts", "architecture", "notes", "labs", "troubleshooting", "interview", "monitoring", "security"):
        for fp in _module_focus(module, topic)[:10]:
            parts.append(fp)
            parts.append("")
    parts.append(
        f"**Study guide:** Read slowly, diagram the system, run the lab, then close the book and explain "
        f"{module.lower()} aloud without notes. That is the bar for completing this {level} module."
    )
    return "\n".join(parts)
