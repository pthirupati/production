"""
Keyword-triggered deep content — matches module titles to rich explanations.

Used when hand-authored (course_slug, module) entries are not present.
"""

from __future__ import annotations

import re

# keyword → section_key → body (partial overrides)
KEYWORD_DEEP: dict[str, dict[str, str]] = {
    "postgresql": {
        "theory": (
            "PostgreSQL uses MVCC so readers never block writers. Each UPDATE creates a new row version; "
            "VACUUM reclaims dead tuples. WAL guarantees durability — commits fsync WAL before acknowledging."
        ),
        "labs": "psql -c \"EXPLAIN (ANALYZE, BUFFERS) SELECT ...\"  # read shared hit vs disk\npsql -c \"SELECT * FROM pg_stat_activity;\"",
    },
    "mysql": {
        "theory": "InnoDB clustered index stores rows in PK order. Buffer pool caches pages; redo log enables crash recovery.",
        "labs": "mysql -e \"SHOW ENGINE INNODB STATUS\\G\"\nmysql -e \"SHOW GLOBAL STATUS LIKE 'Threads%';\"",
    },
    "sqlite": {
        "theory": "SQLite embeds in-process. WAL mode allows concurrent readers during writes. Not for high-write web tiers.",
        "labs": "sqlite3 app.db \"PRAGMA journal_mode=WAL;\"\nsqlite3 app.db \"EXPLAIN QUERY PLAN SELECT ...;\"",
    },
    "mongodb": {
        "theory": "Document model with flexible schema. Replica sets for HA; sharding for horizontal scale — shard key is permanent.",
        "labs": "mongosh --eval 'db.serverStatus().connections'",
    },
    "redis": {
        "theory": "In-memory structures with optional RDB/AOF persistence. Use TTL and eviction policies for cache tiers.",
        "labs": "redis-cli INFO memory\nredis-cli --bigkeys",
    },
    "relational": {
        "theory": "Tables, keys, normalization, ACID. Primary keys identify rows; foreign keys enforce referential integrity.",
    },
    "backup": {
        "theory": "Logical dumps (pg_dump) vs physical (basebackup/PITR). Test restores quarterly — untested backups fail in crises.",
        "labs": "pg_dump -Fc dbname > backup.dump\npg_restore -l backup.dump  # list contents",
    },
    "replication": {
        "theory": "Streaming replication with lag monitoring. Failover requires consensus (Patroni, Orchestrator) to avoid split-brain.",
    },
    "gpu": {
        "theory": "GPUs excel at parallel matrix ops. Monitor temperature, power, ECC errors. MIG splits A100 into isolated instances.",
        "labs": "nvidia-smi\nnvidia-smi dmon -s pucvmet",
    },
    "cuda": {
        "theory": "CUDA is NVIDIA's parallel computing platform. Driver + toolkit + container toolkit required on K8s GPU nodes.",
    },
    "kubernetes": {
        "theory": "Control plane (API, etcd, scheduler) + nodes (kubelet, CRI). Pods are ephemeral; controllers reconcile desired state.",
        "labs": "kubectl get nodes,pods,svc -A\nkubectl describe pod POD",
    },
    "helm": {
        "theory": "Charts templatize manifests. helm upgrade --install is idempotent. Use values files per environment.",
        "labs": "helm upgrade --install app ./chart -f values.yaml --atomic",
    },
    "terraform": {
        "theory": "Declarative IaC with plan/apply. Remote state + locking for teams. Modules encapsulate reusable infrastructure.",
        "labs": "terraform init && terraform plan -out=plan.tfplan",
    },
    "ansible": {
        "theory": "Agentless SSH automation. Playbooks are idempotent. Vault encrypts secrets; AWX adds RBAC and scheduling.",
        "labs": "ansible-playbook site.yml --check --diff",
    },
    "docker": {
        "theory": "Images are layered OCI artifacts; containers add writable layer. Use multi-stage builds for smaller images.",
        "labs": "docker build -t app:dev . && docker run --rm app:dev",
    },
    "prometheus": {
        "theory": "Pull metrics via scrape configs. PromQL rate() for counters; Alertmanager routes notifications.",
        "labs": "curl -s localhost:9090/api/v1/query?query=up",
    },
    "grafana": {
        "theory": "Unified dashboards across Prometheus, Loki, Tempo. Variables filter by cluster/namespace.",
    },
    "systemd": {
        "theory": "PID 1 manages units (service, socket, timer). journald centralizes logs. systemctl enable persists across reboot.",
        "labs": "systemctl status SERVICE && journalctl -u SERVICE -n 50",
    },
    "selinux": {
        "theory": "Mandatory access control via types and contexts. getenforce; restorecon; audit2allow for custom rules.",
        "labs": "getenforce\nausearch -m avc -ts recent",
    },
    "lvm": {
        "theory": "PV → VG → LV abstraction enables online grow. xfs_growfs / resize2fs after lvextend.",
        "labs": "lsblk && vgs && lvs && df -hT",
    },
    "pxe": {
        "theory": "PXE: DHCP offers boot filename → TFTP loads loader → kernel+initrd. iPXE enables HTTP boot chains.",
    },
    "ipmi": {
        "theory": "Out-of-band BMC management: power cycle, sensors, SOL console. Redfish is modern REST replacement.",
        "labs": "ipmitool -I lanplus -H BMC power status",
    },
    "maas": {
        "theory": "MAAS commissions hardware, allocates IPs, deploys Ubuntu via curtin/cloud-init.",
    },
    "bgp": {
        "theory": "BGP exchanges routes between ASNs. Prefix lists and route-maps implement policy. Watch for route leaks.",
    },
    "firewall": {
        "theory": "Default deny inbound. Stateful inspection tracks connections. Document rules with owner and ticket.",
    },
    "nginx": {
        "theory": "Event-driven reverse proxy. worker_connections and upstream keepalive affect concurrency.",
    },
    "python": {
        "theory": "Use venv for isolation. Type hints + pytest for quality. asyncio for I/O-bound concurrency.",
        "labs": "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt",
    },
    "react": {
        "theory": "Component model with hooks (useState, useEffect). Unidirectional data flow; lift state up when shared.",
    },
    "fastapi": {
        "theory": "ASGI framework with Pydantic validation. Automatic OpenAPI docs at /docs.",
    },
    "django": {
        "theory": "Batteries-included web framework. ORM migrations track schema; admin for internal tools.",
    },
    "security": {
        "theory": "Defense in depth: identity, network segmentation, encryption, detection, response.",
    },
    "siem": {
        "theory": "Centralize logs; correlation rules detect TTPs. Tune to reduce false positives; integrate SOAR playbooks.",
    },
    "rag": {
        "theory": "Retrieval-Augmented Generation: embed docs, retrieve top-k chunks, inject into LLM context. Evaluate recall/precision.",
    },
    "vllm": {
        "theory": "High-throughput LLM serving with PagedAttention and continuous batching. Watch GPU memory for KV cache.",
    },
    "podman": {
        "theory": "Rootless containers without daemon. Pods group containers; systemd units integrate with quadlet on RHEL.",
        "labs": "podman run -d --name web -p 8080:80 docker.io/library/nginx:alpine",
    },
    "containerd": {
        "theory": "CRI runtime beneath Kubernetes. ctr and crictl debug pods. Namespaces isolate image stores.",
    },
    "openshift": {
        "theory": "Enterprise Kubernetes with Routes, SCCs, and built-in operators. OLM manages operator lifecycle.",
    },
    "argocd": {
        "theory": "GitOps controller syncs cluster state from Git. App-of-apps pattern for bootstrapping environments.",
    },
    "jenkins": {
        "theory": "Controller + agents execute pipelines. Declarative Jenkinsfile in SCM; shared libraries reuse Groovy steps.",
    },
    "github": {
        "theory": "Branch protection, required reviews, and Actions workflows enforce quality gates before merge.",
    },
    "gitlab": {
        "theory": "Integrated DevOps: Git, CI/CD, registry, security scanning in one platform.",
    },
    "bitbucket": {
        "theory": "Atlassian Git with Pipelines. Branch permissions and merge checks gate production branches.",
    },
    "pulumi": {
        "theory": "IaC in general-purpose languages (Python, TS). State and preview similar to Terraform.",
    },
    "cloudformation": {
        "theory": "AWS-native templates (YAML/JSON). StackSets deploy across accounts; drift detection finds manual changes.",
    },
    "packer": {
        "theory": "Golden AMI/image factory. Builders + provisioners + post-processors pipeline immutable artifacts.",
    },
    "loki": {
        "theory": "Label-indexed logs like Prometheus indexes metrics. LogQL queries filter by {job=\"app\"}.",
    },
    "tempo": {
        "theory": "Trace storage backend for Grafana stack. OpenTelemetry SDKs emit spans; TraceQL queries traces.",
    },
    "jaeger": {
        "theory": "CNCF tracing: agent/collector/query UI. Propagate trace context via HTTP/gRPC headers.",
    },
    "elk": {
        "theory": "Elasticsearch indexes documents; Logstash/Beats ingest; Kibana visualizes. ILM manages retention.",
    },
    "vyos": {
        "theory": "Vyatta-style CLI: set/commit/save. commit confirm 10 prevents lockout on bad network changes.",
    },
    "pfsense": {
        "theory": "FreeBSD firewall/router. WAN/LAN interfaces, NAT, IPsec/OpenVPN, HA with CARP.",
    },
    "mikrotik": {
        "theory": "RouterOS scripting and Winbox GUI. Bridge, firewall filter, OSPF/BGP for WISP scale.",
    },
    "cisco": {
        "theory": "IOS/IOS-XE CLI modes. VLANs on switches; routing protocols on routers; ACLs filter traffic.",
    },
    "vmware": {
        "theory": "ESXi runs VMs; vCenter manages inventory. vMotion migrates running VMs; HA restarts on host failure.",
    },
    "windows": {
        "theory": "Active Directory, DNS, GPO centralize identity and policy. PowerShell automates at scale.",
    },
    "typescript": {
        "theory": "Structural typing with compile-time checks. strict mode catches null/undefined bugs early.",
    },
    "javascript": {
        "theory": "Event loop handles async I/O. ESM modules vs CommonJS — know your bundler/runtime.",
    },
    "html": {
        "theory": "Semantic elements (main, nav, article) improve accessibility and SEO.",
    },
    "css": {
        "theory": "Flexbox for 1D layout; Grid for 2D. Mobile-first media queries with rem units.",
    },
    "next.js": {
        "theory": "App Router with server components reduces client JS. Caching directives control freshness.",
    },
    "express": {
        "theory": "Middleware chain processes requests. Centralized error handler returns consistent JSON errors.",
    },
    "node.js": {
        "theory": "Single-threaded event loop — offload CPU work to worker threads or separate services.",
    },
    "numpy": {
        "theory": "ndarray vectorization beats Python loops. Broadcasting rules align shapes for element-wise ops.",
    },
    "pandas": {
        "theory": "DataFrame joins, groupby, and vectorized string ops for analytics pipelines.",
    },
    "machine learning": {
        "theory": "Train/validation/test split prevents leakage. Track experiments with MLflow or W&B.",
    },
    "network": {
        "theory": "TCP three-way handshake; DNS recursion; MTU and fragmentation affect VPN tunnels.",
        "labs": "ip route && ss -tulpn && dig +short example.com",
    },
    "routing": {
        "theory": "Longest prefix match in FIB. OSPF link-state vs BGP path-vector for WAN.",
    },
    "dhcp": {
        "theory": "DORA process: Discover, Offer, Request, Ack. Reservations bind MAC to fixed IP.",
    },
    "dns": {
        "theory": "Recursive resolver vs authoritative server. TTL controls cache lifetime; lower TTL before migrations.",
    },
    "load balanc": {
        "theory": "L4 (TCP) vs L7 (HTTP) balancing. Health checks must validate app readiness, not just TCP open.",
    },
    "metal3": {
        "theory": "Kubernetes-native bare metal provisioning via Ironic/MAAS integration and Cluster API.",
    },
    "idrac": {
        "theory": "Dell out-of-band: lifecycle controller updates firmware; RACADM automates power and BIOS.",
    },
    "ilo": {
        "theory": "HPE Integrated Lights-Out: remote console, virtual media, health sensors.",
    },
    "firmware": {
        "theory": "BIOS/UEFI, NIC, RAID, BMC firmware — track versions; staged rollout prevents fleet-wide brick.",
    },
    "leapp": {
        "theory": "RHEL in-place upgrade assistant. Pre-upgrade reports list blockers; revert plan required.",
    },
    "upgrade": {
        "theory": "Rolling upgrades minimize downtime. Read release notes for breaking changes and deprecated APIs.",
    },
    "troubleshoot": {
        "theory": "Observe → hypothesize → test → fix. Never restart without capturing logs and metrics first.",
    },
    "monitoring": {
        "theory": "Golden signals: latency, traffic, errors, saturation. SLO-based alerting beats static thresholds.",
    },
    "incident": {
        "theory": "Incident commander coordinates; comms separate from debugging. Timeline in UTC.",
    },
    "devsecops": {
        "theory": "Shift-left security: SAST/DAST/SCA in CI, signed images, policy gates on deploy.",
        "labs": "Run trivy image scan in pipeline; fail build on CRITICAL CVEs without waiver.",
    },
    "rbac": {
        "theory": "Role-based access: least privilege, regular access reviews, break-glass with audit.",
    },
    "iam": {
        "theory": "Identity is the perimeter. MFA, conditional access, and short-lived tokens beat long-lived keys.",
    },
    "wireguard": {
        "theory": "Modern VPN: UDP-based, cryptokey routing, minimal attack surface vs IPsec complexity.",
    },
    "ipsec": {
        "theory": "Site-to-site VPN with IKE phases, encryption domains, and PFS. MTU/MSS clamp for fragmentation.",
    },
    "vrrp": {
        "theory": "Virtual Router Redundancy Protocol: floating VIP fails over between routers on master failure.",
    },
    "qos": {
        "theory": "Traffic shaping prioritizes voice/video over bulk transfer. Policers drop; shapers queue.",
    },
    "inference": {
        "theory": "Batch requests for throughput; stream tokens for latency. Quantization (INT8/FP8) saves VRAM.",
    },
    "kserve": {
        "theory": "Knative-based model serving on K8s: scale-to-zero, canary, multi-framework runtimes.",
    },
    "kubeflow": {
        "theory": "ML platform on K8s: pipelines, notebooks, Katib tuning, KServe integration.",
    },
    "ray": {
        "theory": "Distributed Python: Ray Train for ML, Ray Serve for inference, object store for data.",
    },
    "dashboard": {
        "theory": "Dashboards tell a story: golden signals first, drill-down variables, annotations for deploys.",
    },
    "alert": {
        "theory": "Alert on SLO burn rate, not static CPU. Every page needs runbook link and severity.",
    },
    "logql": {
        "theory": "LogQL: `{job=\"app\"} |= \"error\" | json | line_format`. Rate and metric queries over logs.",
    },
    "trace": {
        "theory": "Distributed tracing: propagate W3C traceparent; span attributes for service/version.",
    },
    "hardening": {
        "theory": "CIS benchmarks, disable unused services, auditd for file integrity, fail2ban for SSH.",
    },
    "forensic": {
        "theory": "Preserve chain of custody: disk images, memory dumps, log exports before reboot.",
    },
    "compliance": {
        "theory": "Map controls to evidence: who owns it, how often reviewed, automation vs manual gap.",
    },
    "cloud-init": {
        "theory": "First-boot customization: users, packages, write_files, runcmd. Idempotent cloud config.",
    },
    "kickstart": {
        "theory": "RHEL automated install: anaconda reads %packages, %post scripts for golden image builds.",
    },
    "commission": {
        "theory": "MAAS commissioning runs built-in tests (storage, network, CPU) before machine is Ready.",
    },
    "fabric": {
        "theory": "MAAS fabrics group VLANs and subnets for provisioning vs production isolation.",
    },
    "plugin": {
        "theory": "Grafana plugins extend datasources, panels, and apps. Sign and pin versions in enterprise.",
    },
    "datasource": {
        "theory": "Datasource config: URL, auth (OAuth, basic, TLS client cert), timeout, and query defaults.",
    },
}


def keyword_deep_body(module_title: str, section_key: str) -> str | None:
    title = module_title.lower()
    for keyword, sections in KEYWORD_DEEP.items():
        if keyword in title and section_key in sections:
            text = sections[section_key]
            if section_key in ("labs",) and "\n" in text and not text.startswith("##"):
                return f"## Hands-on labs\n\n{text}"
            if not text.startswith("##"):
                heading = section_key.replace("_", " ").title()
                return f"## {heading}\n\n{text}"
            return text
    return None
