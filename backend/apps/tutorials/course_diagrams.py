"""Per-course diagram, sequence/state, and expected-output generators.

De-templatizes tutorials: instead of collapsing many courses to ~12 shared
diagrams (the old ``_topic_key`` behaviour), this module builds a *distinct*
architecture diagram for each course/topic from its real components, plus a
Mermaid ``sequenceDiagram`` derived from the module's command list and a
``stateDiagram`` for lifecycle-type modules.

Everything here is offline and deterministic — no clock, no RNG. Any variation
is seeded from a stable topic+module hash so re-seeding produces identical
output.
"""
from __future__ import annotations

import hashlib
import re

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def _mermaid_id(text: str, fallback: str = "n") -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", (text or "")).strip("_")
    return clean or fallback


def _mermaid_label(text: str, limit: int = 28) -> str:
    """Sanitize free text into a safe mermaid node label."""
    clean = re.sub(r"[\"'\[\]\{\}\(\)<>|]", "", (text or "")).strip()
    clean = re.sub(r"\s+", " ", clean)
    return (clean[:limit] or "step").strip()


def stable_hash(*parts: str) -> int:
    """Deterministic non-cryptographic hash for seeding variation."""
    joined = "␟".join(p or "" for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


# ---------------------------------------------------------------------------
# Per-course component registry
# ---------------------------------------------------------------------------
# Curated component pipelines per course/topic. Keys are matched by course_slug
# first, then by a slugified topic. Each entry is an ordered list of
# (id, label) component nodes forming the data-flow of that specific stack.
# This is what makes each course's architecture diagram distinct.
#
# Where a topic is not curated here we fall back to deriving components from the
# topic profile (engines/components/concepts/commands), and only if *that* is
# empty do we fall back to the generic study→practice→validate diagram.

_COURSE_COMPONENTS: dict[str, list[tuple[str, str]]] = {
    # --- OS / shell ---------------------------------------------------------
    "linux": [("shell", "Shell / login"), ("systemd", "systemd units"), ("fs", "Filesystem & LVM"), ("net", "Network stack"), ("journal", "journald / audit")],
    "rhel-linux": [("sub", "subscription-manager"), ("dnf", "dnf / repos"), ("systemd", "systemd"), ("selinux", "SELinux policy"), ("firewalld", "firewalld")],
    "bash": [("script", ".sh script"), ("env", "env / PATH"), ("exec", "bash exec"), ("pipe", "pipes & redirects"), ("exit", "exit codes")],
    "windows": [("ad", "Active Directory"), ("gpo", "Group Policy"), ("srv", "Windows Server roles"), ("svc", "Services / IIS"), ("evt", "Event logs")],
    # --- containers / orchestration ----------------------------------------
    "docker": [("img", "Image layers"), ("containerd", "containerd / runc"), ("ctr", "Containers"), ("net", "Bridge / overlay net"), ("vol", "Named volumes")],
    "podman": [("img", "OCI image"), ("rootless", "rootless userns"), ("pod", "Pods"), ("ctr", "Containers"), ("net", "CNI network")],
    "containerd": [("cri", "CRI / kubelet"), ("ctr", "containerd"), ("runc", "runc shim"), ("snap", "snapshotter"), ("img", "image store")],
    "kubernetes": [("api", "kube-apiserver"), ("etcd", "etcd state"), ("sched", "scheduler"), ("kubelet", "kubelet"), ("pod", "Pods & Services")],
    "openshift": [("route", "Routes"), ("api", "API server"), ("scc", "SCC / RBAC"), ("build", "BuildConfig"), ("pod", "Pods")],
    "helm": [("chart", "Chart / values"), ("tmpl", "template render"), ("rel", "Release"), ("api", "kube-apiserver"), ("pod", "Workloads")],
    # --- IaC ----------------------------------------------------------------
    "terraform": [("hcl", ".tf config"), ("plan", "terraform plan"), ("state", "remote state"), ("apply", "terraform apply"), ("cloud", "Cloud resources")],
    "pulumi": [("prog", "Program (SDK)"), ("engine", "Pulumi engine"), ("state", "Stack state"), ("provider", "Providers"), ("cloud", "Cloud resources")],
    "cloudformation": [("tmpl", "Template"), ("changeset", "Change set"), ("stack", "Stack"), ("res", "Resources"), ("drift", "Drift detection")],
    "packer": [("hcl", "Packer template"), ("builder", "Builder"), ("provision", "Provisioners"), ("artifact", "Machine image"), ("registry", "Image registry")],
    "ansible": [("inv", "Inventory"), ("play", "Playbook"), ("task", "Tasks / handlers"), ("hosts", "Managed hosts"), ("facts", "Facts / idempotency")],
    # --- cloud --------------------------------------------------------------
    "aws": [("iam", "IAM roles"), ("vpc", "VPC / subnets"), ("ec2", "EC2 / ASG"), ("rds", "RDS"), ("s3", "S3")],
    "azure": [("rbac", "RBAC / RG"), ("vnet", "VNet / NSG"), ("vm", "VMs / VMSS"), ("sql", "Azure SQL"), ("storage", "Storage account")],
    "gcp": [("iam", "IAM / org policy"), ("vpc", "VPC / firewall"), ("gce", "Compute Engine"), ("sql", "Cloud SQL"), ("gcs", "Cloud Storage")],
    # --- databases ----------------------------------------------------------
    "database": [("app", "Application"), ("pool", "Connection pool"), ("primary", "Primary DB"), ("replica", "Read replica"), ("backup", "Backup / PITR")],
    "postgresql": [("client", "psql / app"), ("bouncer", "PgBouncer"), ("postmaster", "postmaster"), ("wal", "WAL / shared buffers"), ("standby", "Streaming standby")],
    "mysql": [("client", "mysql client"), ("proxysql", "ProxySQL"), ("sql", "SQL layer"), ("innodb", "InnoDB buffer pool"), ("replica", "Async replica")],
    "sqlite": [("app", "Application"), ("pager", "Pager module"), ("btree", "B-tree store"), ("wal", "WAL journal"), ("file", "app.db file")],
    "mongodb": [("mongos", "mongos router"), ("config", "Config servers"), ("primary", "Primary"), ("secondary", "Secondaries"), ("oplog", "Oplog")],
    "redis": [("client", "Client"), ("loop", "Event loop"), ("mem", "In-memory store"), ("rdb", "RDB snapshot"), ("aof", "AOF log")],
    # --- observability ------------------------------------------------------
    "prometheus": [("targets", "Exporters / apps"), ("scrape", "Prometheus scrape"), ("tsdb", "TSDB blocks"), ("rules", "Alert rules"), ("am", "Alertmanager")],
    "grafana": [("ds", "Datasources"), ("query", "Query engine"), ("panel", "Panels"), ("dash", "Dashboards"), ("alert", "Alert rules")],
    "monitoring": [("apps", "Instrumented apps"), ("collect", "Collectors / agents"), ("tsdb", "Metrics / logs / traces"), ("dash", "Dashboards"), ("oncall", "On-call")],
    "loki": [("app", "App logs"), ("agent", "Promtail / Agent"), ("ingest", "Loki ingester"), ("store", "Object store"), ("logql", "LogQL query")],
    "tempo": [("sdk", "OTel SDK"), ("collector", "Collector"), ("ingest", "Tempo ingester"), ("store", "Trace store"), ("grafana", "Grafana traces")],
    "jaeger": [("sdk", "Instrumentation"), ("agent", "Agent"), ("collector", "Collector"), ("store", "Span store"), ("ui", "Query UI")],
    "elk": [("ingest", "Beats / Logstash"), ("index", "Elasticsearch"), ("ilm", "ILM tiers"), ("kibana", "Kibana"), ("alert", "Alerting")],
    # --- networking ---------------------------------------------------------
    "networking": [("client", "Client"), ("switch", "L2 switch"), ("router", "L3 router"), ("fw", "Firewall / ACL"), ("dns", "DNS resolution")],
    "vyos": [("cli", "VyOS CLI"), ("config", "config.boot"), ("route", "Routing (OSPF/BGP)"), ("nat", "NAT / firewall"), ("vpn", "IPsec / WireGuard")],
    "cisco": [("cli", "IOS CLI"), ("vlan", "VLAN / trunk"), ("switch", "Switching"), ("route", "Routing"), ("acl", "ACL / QoS")],
    "mikrotik": [("cli", "RouterOS CLI"), ("bridge", "Bridge / VLAN"), ("route", "Routing"), ("fw", "Firewall / NAT"), ("queue", "Queues / QoS")],
    "pfsense": [("wan", "WAN"), ("rules", "Firewall rules"), ("nat", "NAT"), ("carp", "CARP failover"), ("lan", "LAN")],
    "nginx": [("client", "Client"), ("tls", "TLS termination"), ("proxy", "Reverse proxy"), ("upstream", "Upstream pool"), ("cache", "Cache / logs")],
    # --- security -----------------------------------------------------------
    "security": [("idp", "Identity provider"), ("iam", "IAM / RBAC"), ("app", "Application"), ("data", "Sensitive data"), ("siem", "SIEM / audit")],
    "cybersecurity": [("perimeter", "Perimeter"), ("iam", "IAM"), ("workload", "Workload"), ("data", "Data"), ("siem", "SIEM detection")],
    "devsecops": [("commit", "Git commit"), ("sast", "SAST scan"), ("build", "Build / SBOM"), ("dast", "DAST staging"), ("deploy", "Signed deploy")],
    "iam": [("user", "User / workload"), ("mfa", "MFA"), ("idp", "IdP (SSO)"), ("policy", "Policy / RBAC"), ("audit", "Audit log")],
    "siem": [("sources", "Log sources"), ("ingest", "Ingest / parse"), ("correlate", "Correlation rules"), ("attack", "MITRE ATT&CK"), ("soar", "SOAR / response")],
    "soc": [("alerts", "Alert queue"), ("tier1", "Tier 1 triage"), ("tier2", "Tier 2 investigate"), ("tier3", "Tier 3 hunt"), ("ir", "Incident response")],
    "nmap": [("scanner", "nmap scanner"), ("discover", "Host discovery"), ("ports", "Port scan"), ("svc", "Service / version"), ("nse", "NSE scripts")],
    "wireshark": [("nic", "Capture NIC"), ("capture", "Live capture"), ("filter", "Display filters"), ("dissect", "Protocol dissectors"), ("analyze", "Follow / analyze")],
    # --- CI / CD / VCS ------------------------------------------------------
    "git": [("work", "Working tree"), ("stage", "Staging area"), ("commit", "Commits"), ("branch", "Branches"), ("remote", "Remote / PR")],
    "github": [("push", "git push"), ("actions", "Actions workflow"), ("build", "Build & test"), ("scan", "Security scan"), ("deploy", "OIDC deploy")],
    "gitlab": [("push", "git push"), ("ci", ".gitlab-ci.yml"), ("runner", "Runners"), ("artifact", "Artifacts"), ("deploy", "Environments")],
    "bitbucket": [("push", "git push"), ("pipeline", "Pipelines"), ("build", "Build steps"), ("artifact", "Artifacts"), ("deploy", "Deployments")],
    "jenkins": [("scm", "SCM trigger"), ("jenkins", "Jenkins master"), ("agent", "Agents"), ("stage", "Pipeline stages"), ("deploy", "Deploy")],
    "argocd": [("git", "Git desired state"), ("argocd", "Argo CD"), ("diff", "Sync / diff"), ("api", "kube-apiserver"), ("live", "Live cluster")],
    "devops": [("commit", "Git commit"), ("ci", "CI pipeline"), ("test", "Build & test"), ("cd", "CD / GitOps"), ("prod", "Production")],
    # --- app dev ------------------------------------------------------------
    "python": [("src", ".py modules"), ("venv", "virtualenv"), ("test", "pytest"), ("pkg", "Package / API"), ("run", "Runtime")],
    "backend": [("client", "Client"), ("api", "REST API"), ("auth", "Auth (JWT/OAuth)"), ("svc", "Services"), ("db", "Database")],
    "django": [("req", "Request"), ("url", "URLconf / view"), ("orm", "ORM"), ("db", "Database"), ("tmpl", "Template / JSON")],
    "fastapi": [("req", "Request"), ("router", "Router"), ("pydantic", "Pydantic model"), ("svc", "Service"), ("resp", "Response / OpenAPI")],
    "express-js": [("req", "Request"), ("mw", "Middleware"), ("route", "Route handler"), ("svc", "Service"), ("resp", "Response")],
    "node-js": [("req", "Request"), ("loop", "Event loop"), ("handler", "Handler"), ("io", "Async I/O"), ("resp", "Response")],
    "next-js": [("browser", "Browser"), ("edge", "Edge / SSR"), ("rsc", "Server Components"), ("api", "Route handlers"), ("data", "Data source")],
    "react": [("state", "State / props"), ("hooks", "Hooks"), ("vdom", "Virtual DOM"), ("render", "Render"), ("dom", "DOM")],
    "javascript": [("src", "Source"), ("parse", "Parse / AST"), ("event", "Event loop"), ("dom", "DOM / fetch"), ("out", "Output")],
    "typescript": [("src", ".ts source"), ("tsc", "tsc compiler"), ("types", "Type check"), ("js", "Emitted JS"), ("run", "Runtime")],
    "html": [("markup", "Semantic HTML"), ("css", "CSS layout"), ("dom", "DOM tree"), ("a11y", "Accessibility"), ("render", "Rendered page")],
    "css": [("selector", "Selectors"), ("cascade", "Cascade"), ("box", "Box model"), ("layout", "Grid / Flexbox"), ("paint", "Paint")],
    "java": [("src", ".java source"), ("javac", "javac"), ("bytecode", "Bytecode"), ("jvm", "JVM"), ("app", "Application")],
    "frontend": [("html", "HTML"), ("css", "CSS"), ("js", "JavaScript"), ("bundle", "Bundle"), ("browser", "Browser")],
    # --- data / AI ----------------------------------------------------------
    "data-science": [("data", "Raw data"), ("clean", "Clean / features"), ("model", "scikit-learn model"), ("eval", "Evaluate"), ("report", "Report / viz")],
    "ai-engineering": [("data", "Data"), ("train", "Train / fine-tune"), ("registry", "Model registry"), ("serve", "Inference serving"), ("monitor", "Monitor / retrain")],
    "ai-infrastructure": [("gpu", "GPU nodes"), ("plugin", "Device plugin"), ("sched", "GPU scheduling"), ("serve", "Inference (vLLM/Triton)"), ("monitor", "GPU telemetry")],
    "gpu": [("driver", "NVIDIA driver"), ("toolkit", "Container toolkit"), ("mig", "MIG partitions"), ("workload", "Training / inference"), ("smi", "nvidia-smi telemetry")],
    "prompt-engineering": [("prompt", "Prompt"), ("context", "Context / RAG"), ("llm", "LLM"), ("guard", "Guardrails / evals"), ("out", "Response")],
    # --- infra / bare metal -------------------------------------------------
    "bare-metal": [("bmc", "BMC (iDRAC/iLO)"), ("pxe", "PXE / MAAS"), ("os", "OS install"), ("net", "VLAN / fabric"), ("k8s", "Kubernetes / Metal3")],
    "maas": [("region", "Region controller"), ("rack", "Rack controllers"), ("commission", "Commissioning"), ("deploy", "Curtin deploy"), ("machine", "Provisioned node")],
    "vmware": [("vc", "vCenter"), ("esxi", "ESXi hosts"), ("vm", "Virtual machines"), ("net", "vSwitch / port group"), ("store", "Datastore / vSAN")],
    "peoplesoft": [("browser", "Browser"), ("web", "Web server"), ("app", "App server"), ("process", "Process scheduler"), ("db", "Database")],
    "simulation": [("terminal", "Terminal lab"), ("state", "Real state checks"), ("gui", "GUI simulator"), ("grade", "Grader"), ("feedback", "Feedback")],
}

# Topics whose modules are lifecycle-shaped (create → configure → operate →
# upgrade → retire). Used to decide when a stateDiagram is meaningful.
_LIFECYCLE_TOPIC_HINTS = frozenset({
    "docker", "podman", "containerd", "kubernetes", "openshift", "helm",
    "terraform", "pulumi", "cloudformation", "packer", "ansible",
    "vmware", "bare-metal", "maas", "aws", "azure", "gcp",
    "database", "postgresql", "mysql", "mongodb", "redis", "sqlite",
    "git", "github", "gitlab", "bitbucket", "jenkins", "argocd", "devops",
})

_LIFECYCLE_MODULE_HINTS = (
    "lifecycle", "provision", "deploy", "rollout", "rollback", "upgrade",
    "release", "backup", "restore", "failover", "migration", "install",
    "commission", "scaling", "autoscal", "boot", "snapshot",
)


# ---------------------------------------------------------------------------
# Component resolution
# ---------------------------------------------------------------------------


def _profile_components(profile: dict) -> list[tuple[str, str]]:
    """Derive (id, label) components from a topic profile when not curated.

    Order of preference: explicit engines/components, then concept keys
    (which name real subsystems), then command keys.
    """
    if not isinstance(profile, dict):
        return []
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _add(label: str) -> None:
        label = (label or "").strip()
        if not label:
            return
        cid = _mermaid_id(label.split("/")[0])[:16] or f"c{len(out)}"
        if cid in seen:
            cid = f"{cid}_{len(out)}"
        seen.add(cid)
        out.append((cid, _mermaid_label(label)))

    comps = profile.get("engines") or profile.get("components") or []
    if isinstance(comps, str):
        comps = [c.strip() for c in comps.split(",") if c.strip()]
    for c in comps:
        _add(c)
    if len(out) < 3:
        for key in (profile.get("concepts") or {}):
            _add(key.replace("_", " ").title())
    if len(out) < 3:
        for key in (profile.get("commands") or {}):
            _add(key.replace("_", " ").title())
    return out[:6]


def resolve_components(
    topic: str,
    profile: dict | None = None,
    course_slug: str = "",
) -> list[tuple[str, str]]:
    """Return the ordered component list for this course.

    Priority: curated registry (by course_slug, then topic slug) → profile
    derivation → empty (caller falls back to the generic diagram).
    """
    cs = slugify(course_slug)
    ts = slugify(topic)
    for key in (cs, ts):
        if key and key in _COURSE_COMPONENTS:
            return list(_COURSE_COMPONENTS[key])
    # Try a trimmed course slug (drop the trailing -zero-hero / -*-zero-hero).
    if cs:
        trimmed = re.sub(r"-(zero-hero|zero-to-hero).*$", "", cs)
        for prefix in _COURSE_COMPONENTS:
            if trimmed == prefix or trimmed.startswith(prefix + "-"):
                return list(_COURSE_COMPONENTS[prefix])
    return _profile_components(profile or {})


# ---------------------------------------------------------------------------
# 1. Per-course architecture diagram
# ---------------------------------------------------------------------------


def course_architecture_diagram(
    topic: str,
    profile: dict | None = None,
    course_slug: str = "",
    module: str = "",
    title: str = "",
) -> str | None:
    """Build a distinct Mermaid architecture diagram from real components.

    Returns ``None`` when no components are available so the caller can fall
    back to the legacy generic diagram.
    """
    comps = resolve_components(topic, profile, course_slug)
    if not comps:
        return None
    label = _mermaid_label(topic or title or "Stack", 32)
    # Deterministic layout choice seeded by the course identity so each course
    # gets a stable orientation (TB vs LR) — adds visual variety without RNG.
    orient = "TB" if stable_hash(course_slug or topic, "orient") % 2 == 0 else "LR"
    lines = ["```mermaid", f"flowchart {orient}", f"  subgraph stack [{label}]"]
    lines.append("    direction LR")
    prev = None
    for cid, clabel in comps:
        node_id = cid
        # Last node rendered as a datastore-ish shape for a bit of variety.
        lines.append(f"    {node_id}[{clabel}]")
        if prev is not None:
            lines.append(f"    {prev} --> {node_id}")
        prev = node_id
    lines.append("  end")
    lines.append("  operator([Operator / User]) --> " + comps[0][0])
    lines.append(f"  {comps[-1][0]} --> obs[[Logs & Metrics]]")
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Sequence diagram from a command list + state diagram for lifecycles
# ---------------------------------------------------------------------------

# Map a leading command token to the actor/system it talks to, so the sequence
# diagram reads like a real interaction instead of a flat list.
_COMMAND_ACTORS: list[tuple[str, str]] = [
    (r"kubectl|helm|oc", "Kubernetes API"),
    (r"docker|podman|nerdctl|crictl", "Container runtime"),
    (r"terraform", "Terraform / Cloud"),
    (r"pulumi", "Pulumi / Cloud"),
    (r"ansible", "Managed hosts"),
    (r"aws", "AWS API"),
    (r"az\b", "Azure API"),
    (r"gcloud", "GCP API"),
    (r"git|gh\b|glab", "Git remote"),
    (r"psql|pg_|mysql|mysqldump|redis-cli|mongosh|sqlite3", "Database"),
    (r"curl|dig|ping|ip\b|ss\b|nmap|traceroute", "Network / endpoint"),
    (r"systemctl|journalctl|dnf|apt|subscription-manager", "Linux host"),
    (r"nvidia-smi", "GPU node"),
    (r"govc", "vSphere"),
    (r"promtool|curl.*9090", "Prometheus"),
]

_MODULE_ACTOR = "Operator"


def _actor_for_command(cmd: str) -> str:
    token = (cmd or "").strip()
    for pat, actor in _COMMAND_ACTORS:
        if re.match(rf"^\s*(sudo\s+)?({pat})", token, re.I):
            return actor
    return "System"


def _split_command_list(commands) -> list[str]:
    """Normalize a command source into a flat list of individual commands."""
    raw: list[str] = []
    if isinstance(commands, dict):
        for v in commands.values():
            raw.append(str(v))
    elif isinstance(commands, (list, tuple)):
        raw.extend(str(c) for c in commands)
    else:
        raw.append(str(commands or ""))
    out: list[str] = []
    for chunk in raw:
        for line in chunk.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Strip shell prompts and leading markers.
            line = re.sub(r"^\$\s+", "", line)
            # Collapse "&&" chains into the first meaningful command.
            first = line.split("&&")[0].strip()
            if first:
                out.append(first)
    return out


def command_sequence_diagram(
    commands,
    topic: str = "",
    module: str = "",
    max_steps: int = 6,
) -> str | None:
    """Emit a Mermaid ``sequenceDiagram`` from an actual command list.

    Returns ``None`` when there are no usable commands.
    """
    cmds = _split_command_list(commands)
    if not cmds:
        return None
    # Deduplicate while preserving order, then cap the number of steps.
    seen: set[str] = set()
    ordered: list[str] = []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    ordered = ordered[:max_steps]

    lines = ["```mermaid", "sequenceDiagram", f"  actor Op as {_MODULE_ACTOR}"]
    # Collect distinct systems for participant declarations.
    systems: list[str] = []
    steps: list[tuple[str, str]] = []
    for cmd in ordered:
        actor = _actor_for_command(cmd)
        if actor not in systems:
            systems.append(actor)
        steps.append((actor, cmd))
    for sysname in systems:
        lines.append(f"  participant {_mermaid_id(sysname)} as {sysname}")
    for actor, cmd in steps:
        aid = _mermaid_id(actor)
        label = _mermaid_label(cmd, 40)
        lines.append(f"  Op->>{aid}: {label}")
        lines.append(f"  {aid}-->>Op: result / exit code")
    lines.append("```")
    return "\n".join(lines)


def is_lifecycle_module(topic: str, module: str = "", course_slug: str = "") -> bool:
    ts = slugify(topic)
    cs = slugify(course_slug)
    mod = (module or "").lower()
    if any(h in mod for h in _LIFECYCLE_MODULE_HINTS):
        return True
    return ts in _LIFECYCLE_TOPIC_HINTS or any(
        cs.startswith(h) for h in _LIFECYCLE_TOPIC_HINTS
    )


def lifecycle_state_diagram(topic: str = "", module: str = "", course_slug: str = "") -> str:
    """Emit a Mermaid ``stateDiagram-v2`` for a lifecycle-type module.

    The lifecycle is tailored per broad category so it is not identical across
    every course, while staying deterministic.
    """
    ts = slugify(topic)
    cs = slugify(course_slug)

    def _match(*keys: str) -> bool:
        return ts in keys or any(cs.startswith(k) for k in keys)

    if _match("git", "github", "gitlab", "bitbucket", "jenkins", "argocd", "devops"):
        states = [
            ("Commit", "Change committed"),
            ("Build", "CI build & test"),
            ("Stage", "Deploy to staging"),
            ("Approve", "Gate / review"),
            ("Prod", "Deployed to prod"),
            ("Rollback", "Roll back"),
        ]
        transitions = [
            ("[*]", "Commit", ""),
            ("Commit", "Build", "push"),
            ("Build", "Stage", "green"),
            ("Build", "Rollback", "red"),
            ("Stage", "Approve", "smoke ok"),
            ("Approve", "Prod", "approved"),
            ("Prod", "Rollback", "SLO breach"),
            ("Rollback", "Build", "fix"),
            ("Prod", "[*]", "stable"),
        ]
    elif _match("database", "postgresql", "mysql", "mongodb", "redis", "sqlite"):
        states = [
            ("Provision", "Instance created"),
            ("Load", "Schema & data"),
            ("Serve", "Serving queries"),
            ("Replicate", "Replica in sync"),
            ("Backup", "Backup / PITR"),
            ("Failover", "Promote standby"),
        ]
        transitions = [
            ("[*]", "Provision", ""),
            ("Provision", "Load", "initdb"),
            ("Load", "Serve", "ready"),
            ("Serve", "Replicate", "stream"),
            ("Serve", "Backup", "scheduled"),
            ("Serve", "Failover", "primary down"),
            ("Failover", "Serve", "promoted"),
            ("Backup", "Serve", "verified"),
        ]
    elif _match("docker", "podman", "containerd", "kubernetes", "openshift", "helm"):
        states = [
            ("Pending", "Scheduled"),
            ("Pulling", "Image pull"),
            ("Running", "Healthy"),
            ("Updating", "Rolling update"),
            ("CrashLoop", "Restart backoff"),
            ("Terminated", "Removed"),
        ]
        transitions = [
            ("[*]", "Pending", ""),
            ("Pending", "Pulling", "assigned node"),
            ("Pulling", "Running", "started"),
            ("Running", "Updating", "new revision"),
            ("Updating", "Running", "healthy"),
            ("Running", "CrashLoop", "probe fail"),
            ("CrashLoop", "Running", "recovered"),
            ("Running", "Terminated", "scale down"),
            ("Terminated", "[*]", ""),
        ]
    elif _match("terraform", "pulumi", "cloudformation", "packer", "ansible"):
        states = [
            ("Written", "Config authored"),
            ("Planned", "plan / preview"),
            ("Applied", "Resources live"),
            ("Drifted", "Out of band change"),
            ("Destroyed", "Torn down"),
        ]
        transitions = [
            ("[*]", "Written", ""),
            ("Written", "Planned", "plan"),
            ("Planned", "Applied", "apply"),
            ("Applied", "Drifted", "manual change"),
            ("Drifted", "Planned", "refresh"),
            ("Applied", "Destroyed", "destroy"),
            ("Destroyed", "[*]", ""),
        ]
    elif _match("vmware", "bare-metal", "maas", "aws", "azure", "gcp"):
        states = [
            ("Requested", "Provision request"),
            ("Provisioning", "Building"),
            ("Running", "In service"),
            ("Maintenance", "Patch / resize"),
            ("Decommissioned", "Released"),
        ]
        transitions = [
            ("[*]", "Requested", ""),
            ("Requested", "Provisioning", "accepted"),
            ("Provisioning", "Running", "ready"),
            ("Running", "Maintenance", "change window"),
            ("Maintenance", "Running", "verified"),
            ("Running", "Decommissioned", "retire"),
            ("Decommissioned", "[*]", ""),
        ]
    else:
        states = [
            ("Design", "Design / configure"),
            ("Operate", "Running"),
            ("Incident", "Degraded"),
            ("Recover", "Mitigated"),
            ("Retire", "Decommissioned"),
        ]
        transitions = [
            ("[*]", "Design", ""),
            ("Design", "Operate", "deploy"),
            ("Operate", "Incident", "failure"),
            ("Incident", "Recover", "mitigate"),
            ("Recover", "Operate", "verified"),
            ("Operate", "Retire", "end of life"),
            ("Retire", "[*]", ""),
        ]

    lines = ["```mermaid", "stateDiagram-v2"]
    for name, desc in states:
        lines.append(f"  {name}: {desc}")
    for src, dst, label in transitions:
        if label:
            lines.append(f"  {src} --> {dst}: {label}")
        else:
            lines.append(f"  {src} --> {dst}")
    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Expected-output samples
# ---------------------------------------------------------------------------
# Realistic (but synthetic) sample output keyed by a leading command token.
# Paired with a shell block so ShellBlock's output pane / "compare to baseline"
# has content. Deterministic and offline.

OUTPUT_SAMPLES: dict[str, str] = {
    "kubectl get pods": "NAME                   READY   STATUS    RESTARTS   AGE\nweb-7d9f8c6b5-abcde    1/1     Running   0          4h12m\napi-5c7b6d4f9-fghij    1/1     Running   1          2d3h",
    "kubectl get nodes": "NAME        STATUS   ROLES           AGE   VERSION\nnode-01     Ready    control-plane   30d   v1.30.2\nnode-02     Ready    <none>          30d   v1.30.2",
    "kubectl": "deployment.apps/web configured\nservice/web unchanged",
    "helm": "Release \"web\" has been upgraded. Happy Helming!\nSTATUS: deployed\nREVISION: 3",
    "docker ps": "CONTAINER ID   IMAGE          STATUS         PORTS                  NAMES\na1b2c3d4e5f6   nginx:alpine   Up 12 minutes  0.0.0.0:8080->80/tcp   web",
    "docker run": "Unable to find image locally, pulling...\nStatus: Downloaded newer image\n9f2c8e1a3b4d",
    "docker": "web\nStatus: Up 12 minutes (healthy)",
    "terraform plan": "Plan: 3 to add, 1 to change, 0 to destroy.\n\nChanges to Outputs:\n  + instance_ip = (known after apply)",
    "terraform apply": "Apply complete! Resources: 3 added, 1 changed, 0 destroyed.\n\nOutputs:\ninstance_ip = \"10.0.1.42\"",
    "terraform validate": "Success! The configuration is valid.",
    "terraform init": "Terraform has been successfully initialized!",
    "terraform": "aws_instance.web: Refreshing state... [id=i-0abc123]",
    "ansible": "web-01 | SUCCESS => {\n    \"changed\": false,\n    \"ping\": \"pong\"\n}",
    "ansible-playbook": "PLAY RECAP *********************************************************\nweb-01  : ok=6    changed=1    unreachable=0    failed=0",
    "aws sts": "{\n    \"Account\": \"123456789012\",\n    \"Arn\": \"arn:aws:iam::123456789012:user/deployer\"\n}",
    "aws s3": "2026-05-01 09:14:22 fixitlab-artifacts\n2026-05-01 09:14:31 fixitlab-backups",
    "aws ec2": "[\n    \"running\",\n    \"running\",\n    \"stopped\"\n]",
    "aws": "{\n    \"Account\": \"123456789012\"\n}",
    "systemctl": "● sshd.service - OpenSSH server daemon\n     Loaded: loaded (/usr/lib/systemd/system/sshd.service; enabled)\n     Active: active (running) since Mon 2026-05-04 08:00:11 UTC",
    "journalctl": "May 04 08:00:11 host sshd[1123]: Server listening on 0.0.0.0 port 22.\nMay 04 08:01:44 host sshd[1188]: Accepted publickey for deploy",
    "id": "uid=1001(appuser) gid=1001(appuser) groups=1001(appuser),10(wheel)",
    "getent": "appuser:x:1001:1001::/home/appuser:/bin/bash",
    "ls": "total 20\ndrwxr-xr-x 2 appuser appuser 4096 May 04 08:00 .\n-rw-r--r-- 1 appuser appuser  220 May 04 08:00 notes.txt",
    "ip addr": "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500\n    inet 10.0.1.42/24 brd 10.0.1.255 scope global eth0",
    "ip route": "default via 10.0.1.1 dev eth0\n10.0.1.0/24 dev eth0 proto kernel scope link src 10.0.1.42",
    "ping": "PING example.com (93.184.216.34) 56(84) bytes of data.\n64 bytes from 93.184.216.34: icmp_seq=1 ttl=56 time=11.4 ms",
    "dig": "example.com.  300  IN  A  93.184.216.34",
    "ss": "State   Recv-Q  Send-Q  Local Address:Port   Peer Address:Port\nLISTEN  0       128     0.0.0.0:22          0.0.0.0:*",
    "psql": " version\n-----------------------------------------------------------\n PostgreSQL 16.2 on x86_64-pc-linux-gnu, compiled by gcc",
    "pg_dump": "-- PostgreSQL database dump complete",
    "SELECT": " pid  | state  |            query\n------+--------+------------------------------\n 1123 | active | SELECT * FROM orders WHERE ...",
    "EXPLAIN": "Index Scan using orders_pkey on orders  (cost=0.29..8.31 rows=1 width=64)\n  Index Cond: (id = 1)",
    "mysql": "+------------------+-------+\n| Variable_name    | Value |\n+------------------+-------+\n| Threads_running  | 3     |",
    "mysqldump": "-- Dump completed on 2026-05-04  8:00:11",
    "redis-cli": "# Memory\nused_memory_human:12.4M\nmaxmemory_policy:allkeys-lru",
    "mongosh": "{ ok: 1, uptime: 84213, connections: { current: 12 } }",
    "sqlite3": "CREATE TABLE app(id INTEGER PRIMARY KEY, name TEXT);\njournal_mode\nwal",
    "docker compose": "[+] Running 2/2\n ✔ Network app_default  Created\n ✔ Container app-web-1   Started",
    "git status": "On branch main\nnothing to commit, working tree clean",
    "git log": "a1b2c3d Add health-check endpoint\n9f8e7d6 Fix retry backoff",
    "git": "Switched to a new branch 'feature-login'",
    "gh run": "completed  success  CI  main  push  12s",
    "nvidia-smi": "+-----------------------------------------------------------------------------+\n| GPU  Name        Persistence-M| Bus-Id        | Memory-Usage | GPU-Util |\n|   0  NVIDIA A100        On     | 00000000:07:00.0 | 3421MiB/40GB | 87%     |",
    "up": "up{job=\"node\", instance=\"10.0.1.42:9100\"}  1",
    "rate": "{job=\"api\"}  42.7",
    "curl": "HTTP/1.1 200 OK\ncontent-type: application/json\n{\"status\":\"ok\"}",
    "python": "Python 3.12.3",
    "pytest": "===== 24 passed in 3.11s =====",
    "shellcheck": "In script.sh line 4:\nrm -rf $DIR\n       ^-- SC2086: Double quote to prevent globbing.",
    "nmap": "PORT     STATE  SERVICE\n22/tcp   open   ssh\n443/tcp  open   https",
    "getenforce": "Enforcing",
    "govc": "Name:           web-01\n  Power state:  poweredOn\n  Guest OS:     Ubuntu Linux (64-bit)",
}


def sample_output_for(command: str) -> str | None:
    """Return realistic sample output for a command, matched by longest prefix."""
    token = re.sub(r"^\s*\$\s*", "", (command or "").strip())
    token = re.sub(r"^sudo\s+", "", token)
    best: str | None = None
    best_len = 0
    for key, out in OUTPUT_SAMPLES.items():
        if token.startswith(key) and len(key) > best_len:
            best = out
            best_len = len(key)
    return best


def shell_block_with_output(commands, topic: str = "", title: str = "", max_lines: int = 4) -> str | None:
    """Build a ```bash block where each command is prefixed with ``$`` and
    followed by realistic sample output, so ShellBlock renders an output pane.

    Deterministic and offline. Returns ``None`` when no commands are usable.
    """
    cmds = _split_command_list(commands)
    if not cmds:
        return None
    seen: set[str] = set()
    ordered: list[str] = []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    ordered = ordered[:max_lines]

    lines = ["```bash"]
    matched_any = False
    for cmd in ordered:
        lines.append(f"$ {cmd}")
        out = sample_output_for(cmd)
        if out:
            matched_any = True
            lines.extend(out.splitlines())
    lines.append("```")
    if not matched_any:
        # Without at least one sample the output pane would be empty; still
        # return the block (commands render), but caller may prefer the legacy
        # example. We keep it — commands are still useful and deterministic.
        pass
    return "\n".join(lines)
