"""
Hand-authored deep module content — merged over generated sections.

Keys: (course_slug, module_order) → {section_key: body_text}
"""

from __future__ import annotations

# Rich end-to-end lessons for flagship courses (Database, Linux, Kubernetes, Terraform, Docker)
DEEP_SECTIONS: dict[tuple[str, int], dict[str, str]] = {}

def _add(course: str, mod: int, sections: dict[str, str]) -> None:
    key = (course, mod)
    if key not in DEEP_SECTIONS:
        DEEP_SECTIONS[key] = {}
    DEEP_SECTIONS[key].update(sections)


# ── Database Engineering: Zero to Hero ──────────────────────────────────────
_add("database-engineering-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "The **relational model** is the foundation of most enterprise data platforms. Data lives in **tables** "
        "(relations) made of **rows** (tuples) and **columns** (attributes). Integrity comes from **keys**: a "
        "**primary key** uniquely identifies a row; a **foreign key** references another table's primary key.\n\n"
        "**Normalization** reduces redundancy: First Normal Form (1NF) removes repeating groups; 2NF removes partial "
        "dependencies on composite keys; 3NF removes transitive dependencies. Denormalization is a conscious trade-off "
        "for read performance — you accept update anomalies for fewer joins.\n\n"
        "**ACID transactions** guarantee reliable commits:\n"
        "- **Atomicity** — all statements commit or none do (ROLLBACK on failure).\n"
        "- **Consistency** — constraints (CHECK, FK, UNIQUE) hold after every transaction.\n"
        "- **Isolation** — concurrent sessions see controlled snapshots (isolation levels: READ COMMITTED, REPEATABLE READ, SERIALIZABLE).\n"
        "- **Durability** — committed data survives crash via write-ahead logging (WAL).\n\n"
        "Indexes accelerate lookups but slow writes. A **B-tree** index supports equality and range scans on leading "
        "columns. Choose indexes from query patterns — EXPLAIN is your evidence, not intuition."
    ),
    "architecture": (
        "## Architecture\n\n"
        "A typical OLTP stack: application → **connection pool** (PgBouncer/ProxySQL) → **primary database** → "
        "**streaming replicas** for read scaling and DR. Backups run via pg_basebackup/WAL archive or logical dumps.\n\n"
        "Separate **OLTP** (short transactions, many users) from **OLAP** (analytics warehouses). Mixing heavy "
        "reporting on primary OLTP causes p99 latency spikes — route analytics to replicas or columnar stores."
    ),
    "concepts": (
        "## Core concepts\n\n"
        "**Schema design:** choose appropriate types (TIMESTAMPTZ not TEXT for dates). Use NOT NULL where business "
        "rules require values. Default values and CHECK constraints catch bad data at the boundary.\n\n"
        "**Transactions:** wrap related updates in BEGIN…COMMIT. Deadlocks happen when transactions lock rows in "
        "different orders — retry with exponential backoff in application code.\n\n"
        "**Isolation anomalies:** dirty read (uncommitted data), non-repeatable read, phantom read — know which "
        "your isolation level prevents."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "Create a minimal schema and prove ACID behavior:\n\n"
        "1. Create tables `customers` and `orders` with FK relationship.\n"
        "2. INSERT inside a transaction; ROLLBACK — verify order vanished.\n"
        "3. COMMIT — verify both rows persist.\n"
        "4. Add an index; run EXPLAIN on a filtered SELECT and compare cost.\n\n"
        "Use FixitLab PostgreSQL or MySQL Docker sim labs."
    ),
})

_add("database-engineering-zero-hero", 2, {
    "theory": (
        "## Theory\n\n"
        "**PostgreSQL** is an advanced open-source ORDBMS. **MVCC** (Multi-Version Concurrency Control) lets readers "
        "never block writers: each row version has xmin/xmax transaction IDs. UPDATE creates a new row version; "
        "old versions become **dead tuples** until **VACUUM** reclaims space.\n\n"
        "The **postmaster** process accepts connections and forks **backend** processes. Shared memory holds "
        "**shared buffers** (page cache). **WAL** (Write-Ahead Log) ensures durability before data pages hit disk."
    ),
    "concepts": (
        "## Core concepts\n\n"
        "**Roles and databases:** clusters contain databases; roles (users) have LOGIN and privileges. "
        "`GRANT SELECT ON TABLE` follows least privilege.\n\n"
        "**Extensions:** `CREATE EXTENSION pg_stat_statements;` tracks query performance. "
        "**Connection pooling:** apps should not open 500 direct connections — use PgBouncer in transaction mode.\n\n"
        "**Vacuum:** autovacuum prevents XID wraparound catastrophe; monitor `n_dead_tup` in pg_stat_user_tables."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "1. `psql -c \"SELECT version();\"`\n"
        "2. Create role and database; GRANT privileges.\n"
        "3. Run a slow query with `EXPLAIN (ANALYZE, BUFFERS)` — read shared hit vs read blocks.\n"
        "4. Inspect `pg_stat_activity` during load.\n"
        "5. Enable pg_stat_statements and find top queries by total_time."
    ),
})

_add("database-engineering-zero-hero", 3, {
    "theory": (
        "## Theory\n\n"
        "**MySQL** with **InnoDB** is the default production engine. InnoDB stores rows in **clustered index** "
        "order (primary key). Secondary indexes store PK values as pointers — keep PKs narrow.\n\n"
        "**Buffer pool** caches data/index pages. **Redo log** (ib_logfile) ensures crash recovery. "
        "**Doublewrite buffer** protects against torn pages."
    ),
    "concepts": (
        "## Core concepts\n\n"
        "**Replication:** binary log (binlog) records changes; replicas apply events. **GTID** simplifies failover. "
        "**Semi-sync** waits for one replica ack before commit — reduces data loss window.\n\n"
        "**Slow query log:** set `long_query_time` and `log_queries_not_using_indexes` to find tuning targets."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "1. `SHOW VARIABLES LIKE 'innodb%buffer%';`\n"
        "2. `SHOW ENGINE INNODB STATUS\\G` — transactions, locks, buffer pool.\n"
        "3. Enable slow log; run intentional full table scan; analyze log output.\n"
        "4. Configure read replica; verify `SHOW SLAVE STATUS\\G` (or replica status)."
    ),
})

_add("database-engineering-zero-hero", 4, {
    "theory": (
        "## Theory\n\n"
        "**SQLite** embeds in applications (mobile, edge, desktop). Single **writer** at a time; multiple readers "
        "with WAL mode. File-based — copy `.db` file to backup.\n\n"
        "**WAL mode** (`PRAGMA journal_mode=WAL`) improves concurrency: readers see consistent snapshot while writer appends."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "1. `sqlite3 app.db \".tables\"`\n"
        "2. `PRAGMA journal_mode;` then `PRAGMA journal_mode=WAL;`\n"
        "3. `EXPLAIN QUERY PLAN SELECT ...`\n"
        "4. Test concurrent read during write from two shells."
    ),
})

_add("database-engineering-zero-hero", 5, {
    "theory": (
        "## Theory\n\n"
        "**MongoDB** stores **BSON documents** in collections. Flexible schema — but enforce shape at application "
        "or JSON Schema validation. **Replica sets** elect primary; **sharded clusters** split data by shard key."
    ),
    "concepts": (
        "## Core concepts\n\n"
        "**Shard key** choice is critical — hot shards if key has low cardinality. "
        "**Write concern** `majority` survives primary failure. **Read preference** `secondaryPreferred` offloads reads."
    ),
})

_add("database-engineering-zero-hero", 6, {
    "theory": (
        "## Theory\n\n"
        "**Redis** is in-memory with optional persistence (RDB snapshots, AOF append-only file). "
        "Use for cache, session store, rate limiting, pub/sub, streams — not primary system of record unless "
        "persistence + replication carefully configured."
    ),
    "concepts": (
        "## Core concepts\n\n"
        "**Eviction:** when `maxmemory` hit, policies like `allkeys-lru` drop keys. "
        "**TTL** on cache keys prevents stale data. **Redis Cluster** shards 16384 hash slots across masters."
    ),
})

_add("database-engineering-zero-hero", 7, {
    "theory": (
        "## Theory\n\n"
        "**Backups** must be restorable — untested backups are wishful thinking. "
        "**Logical backup** (pg_dump, mysqldump): portable SQL/custom format. "
        "**Physical backup** (pg_basebackup, Percona XtraBackup): faster restore for large DBs. "
        "**PITR** replays WAL/binlog to arbitrary timestamp before mistake."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "1. `pg_dump -Fc mydb > mydb.dump`\n"
        "2. Drop test table; `pg_restore -d mydb mydb.dump` to recover.\n"
        "3. Document RPO/RTO for your restore drill."
    ),
})

_add("database-engineering-zero-hero", 8, {
    "theory": (
        "## Theory\n\n"
        "**High availability:** automatic failover when primary dies. PostgreSQL: Patroni + etcd/consul. "
        "MySQL: Orchestrator, MHA, or Group Replication. Measure **replication lag** — stale reads if app "
        "doesn't route writes to primary."
    ),
})

_add("database-engineering-zero-hero", 9, {
    "theory": (
        "## Theory\n\n"
        "**Database security:** encrypt connections (TLS), rotate passwords, column-level encryption for PII, "
        "audit logging (pgaudit), network isolation (private subnets), no superuser for apps."
    ),
})

_add("database-engineering-zero-hero", 10, {
    "theory": (
        "## Theory\n\n"
        "**Enterprise DBA operations:** change windows, schema migration tools (Flyway, Liquibase, gh-ost), "
        "capacity planning from growth metrics, quarterly restore drills, on-call runbooks for replication lag "
        "and disk full scenarios."
    ),
    "enterprise": (
        "## Enterprise production examples\n\n"
        "Fortune-500 patterns: dual-region active/passive Postgres with Patroni, ProxySQL query routing, "
        "automated pgBackRest to object storage, SOC2 evidence from pgaudit logs, CAB-approved DDL via "
        "online schema change tools."
    ),
})

# ── Linux Sysadmin ───────────────────────────────────────────────────────────
_add("linux-sysadmin-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "The Linux **filesystem hierarchy** (FHS) organizes the system: `/etc` configuration, `/var` variable data, "
        "`/home` user homes, `/tmp` ephemeral. **Paths** are absolute (from `/`) or relative. "
        "`.` is current directory; `..` is parent.\n\n"
        "**Navigation:** `pwd`, `cd`, `ls -la`. **Globbing:** `*` any chars, `?` single char. "
        "**Tab completion** saves time and prevents typos."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "cd /etc && ls -la | head\n"
        "find /var/log -type f -name '*.log' 2>/dev/null | head\n"
        "mkdir -p ~/lab/practice && touch ~/lab/practice/notes.txt"
    ),
})

_add("linux-sysadmin-zero-hero", 4, {
    "theory": (
        "## Theory\n\n"
        "**systemd** is PID 1 on modern Linux. **Units** describe services, sockets, timers, mounts. "
        "`systemctl start|stop|enable|status`. **journald** collects logs: `journalctl -u nginx -f`.\n\n"
        "**Signals:** SIGTERM graceful stop, SIGKILL force kill. **Exit codes** 0 success, non-zero failure."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "systemctl status sshd\n"
        "journalctl -u sshd -n 50 --no-pager\n"
        "systemctl is-enabled sshd"
    ),
})

# ── Kubernetes ───────────────────────────────────────────────────────────────
_add("kubernetes-platform-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "A **Pod** is the smallest deployable unit — one or more containers sharing network namespace and volumes. "
        "Pods are ephemeral; Deployments manage ReplicaSets that recreate failed pods.\n\n"
        "**kubectl** talks to kube-apiserver. Contexts/namespaces scope commands: "
        "`kubectl -n prod get pods`."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "kubectl run nginx --image=nginx:alpine --port=80\n"
        "kubectl get pods -o wide\n"
        "kubectl describe pod POD_NAME\n"
        "kubectl logs POD_NAME\n"
        "kubectl delete pod POD_NAME"
    ),
})

_add("kubernetes-platform-zero-hero", 5, {
    "theory": (
        "## Theory\n\n"
        "**Helm** packages Kubernetes manifests as **charts**. `values.yaml` parameterizes templates. "
        "`helm upgrade --install` is idempotent GitOps-friendly deployment. "
        "Use `--atomic` to auto-rollback failed releases."
    ),
})

# ── Terraform ─────────────────────────────────────────────────────────────────
_add("terraform-iac-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**HCL** (HashiCorp Configuration Language) declares desired infrastructure. "
        "Resources have types (`aws_instance`), names (`web`), and arguments. "
        "**State** maps config to real cloud IDs — never commit secrets or state to public Git.\n\n"
        "Workflow: `init` (providers) → `plan` (preview diff) → `apply` (execute)."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "terraform init\n"
        "terraform validate\n"
        "terraform plan\n"
        "Open FixitLab Terraform simulator for init/plan/apply with scenario output."
    ),
})

# ── Docker ────────────────────────────────────────────────────────────────────
_add("docker-containers-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**Images** are read-only layers (Dockerfile instructions create layers). "
        "**Containers** add a writable layer on top. **Registry** stores images (Docker Hub, ECR, GCR).\n\n"
        "`docker pull`, `docker run`, `docker ps`, `docker logs` — daily commands."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "docker run -d --name web -p 8080:80 nginx:alpine\n"
        "docker ps\n"
        "docker logs web\n"
        "docker exec -it web sh"
    ),
})

# ── Grafana ───────────────────────────────────────────────────────────────────
_add("grafana-visualization-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**Grafana** is an observability front-end that unifies metrics, logs, and traces from multiple "
        "datasources (Prometheus, Loki, Tempo, Elasticsearch, CloudWatch). The server stores dashboards, "
        "folders, users, and alert rules; **plugins** extend datasources and panels.\n\n"
        "**Architecture:** Grafana server → datasource proxies → backend systems. "
        "Authentication integrates with LDAP, OAuth, SAML, or Grafana's built-in users. "
        "Organizations and folders RBAC-control who sees which dashboards."
    ),
    "architecture": (
        "## Architecture\n\n"
        "Grafana runs as a stateless-ish web app (SQLite/Postgres/MySQL for config DB). "
        "Each datasource query goes through Grafana's proxy (unless direct browser access enabled — avoid in prod). "
        "Alerting evaluates rules on schedule and routes to contact points (PagerDuty, Slack, email)."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "1. Add Prometheus datasource; test query `up`.\n"
        "2. Import community dashboard; save to folder.\n"
        "3. Create user with Viewer role; verify RBAC.\n"
        "4. Open FixitLab Grafana simulator and complete dashboard objectives."
    ),
})

_add("grafana-visualization-zero-hero", 3, {
    "theory": (
        "## Theory\n\n"
        "**Dashboard variables** (`$cluster`, `$namespace`) make one dashboard work across environments. "
        "Use **query variables** for dynamic label values; **custom** for static enums.\n\n"
        "**Panel types:** Time series for metrics, Stat for single values, Table for logs, "
        "Heatmap for latency distributions. **Repeat rows/panels** by variable for multi-cluster views."
    ),
    "concepts": (
        "## Core concepts\n\n"
        "**Templating syntax:** `${var:queryparam}` in URLs; `$__interval` for auto step. "
        "**Annotations** mark deploys on graphs. **Transformations** join/merge query results in-panel."
    ),
})

_add("grafana-visualization-zero-hero", 10, {
    "enterprise": (
        "## Enterprise observability design\n\n"
        "Fortune-500 pattern: centralized Grafana with SSO, folder-per-team RBAC, "
        "Git-synced dashboards (Grafana Operator or as-code), multi-tenant Loki/Tempo backends, "
        "SLO dashboards with error-budget burn alerts, and executive NOC wallboards fed from golden signals."
    ),
})

# ── AI Infrastructure ─────────────────────────────────────────────────────────
_add("ai-infrastructure-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**GPUs** accelerate parallel workloads (matrix multiply, convolutions) via thousands of CUDA cores. "
        "**NVIDIA** dominates datacenter AI (A100, H100, L40S); **AMD** offers ROCm on MI-series. "
        "Each GPU has **VRAM** (capacity limit for model weights + KV cache), **Tensor Cores** for "
        "mixed-precision ops, and **NVLink** for multi-GPU communication within a node.\n\n"
        "**MIG** (Multi-Instance GPU) partitions A100 into isolated instances for inference multi-tenancy."
    ),
    "architecture": (
        "## Architecture\n\n"
        "AI node stack: bare metal → OS + NVIDIA driver → CUDA toolkit → container toolkit → "
        "Kubernetes device plugin → inference/training workload. Network: high-bandwidth NICs for "
        "distributed training (NCCL over RoCE/InfiniBand)."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "nvidia-smi\n"
        "nvidia-smi -q -d MEMORY,POWER,TEMPERATURE\n"
        "nvidia-smi mig -lgip  # list MIG profiles if supported"
    ),
})

_add("ai-infrastructure-zero-hero", 5, {
    "theory": (
        "## Theory\n\n"
        "**vLLM** serves LLMs with PagedAttention and continuous batching for high throughput. "
        "**NVIDIA Triton** supports multiple frameworks (TensorRT, ONNX, PyTorch) in one server. "
        "**NIM** packages optimized inference containers.\n\n"
        "Watch **GPU memory**: model weights + KV cache grow with context length and concurrent requests."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "Deploy vLLM or Triton in K8s with GPU resource limits.\n"
        "Load-test with hey or locust; watch nvidia-smi dmon for utilization.\n"
        "Tune max batch size and max model len for latency vs throughput."
    ),
})

_add("ai-infrastructure-zero-hero", 10, {
    "troubleshooting": (
        "## GPU incident response\n\n"
        "**Symptoms:** CUDA OOM, ECC errors, thermal throttle, NCCL timeout, pod Pending (no GPU).\n\n"
        "**Playbook:** capture nvidia-smi + dmesg → check driver/CUDA version mismatch → "
        "verify device plugin → cordon node if hardware fault → drain workloads → RMA if needed.\n\n"
        "**RCA:** timeline, contributing factors, driver/firmware versions, preventive monitoring."
    ),
})

# ── Bare Metal ────────────────────────────────────────────────────────────────
_add("bare-metal-datacenter-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**BIOS/UEFI** firmware initializes hardware before OS boot. UEFI supports GPT disks and Secure Boot. "
        "Configure boot order, virtualization (VT-x/AMD-V), and power policies in firmware — "
        "wrong settings cause silent performance loss or failed PXE."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "Document current BIOS version via ipmitool or vendor CLI.\n"
        "Verify Secure Boot and virtualization flags match cluster requirements."
    ),
})

_add("bare-metal-datacenter-zero-hero", 4, {
    "theory": (
        "## Theory\n\n"
        "**IPMI** (Intelligent Platform Management) provides out-of-band power, sensors, and SOL console over "
        "dedicated BMC NIC. **Redfish** is REST-based successor. Never expose BMC to public internet.\n\n"
        "**SOL** (Serial Over LAN) gives console when OS network is broken."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "ipmitool -I lanplus -H BMC -U user -P pass power status\n"
        "ipmitool -I lanplus -H BMC sol activate  # serial console"
    ),
})

_add("bare-metal-datacenter-zero-hero", 7, {
    "theory": (
        "## Theory\n\n"
        "**MAAS** (Metal as a Service) models machines through lifecycle: "
        "New → Commissioning → Ready → Deployed → Released. "
        "Region controller + rack controllers manage DHCP, TFTP, and curtin deployment."
    ),
    "architecture": (
        "## Architecture\n\n"
        "MAAS region API → rack controllers (DHCP relay, TFTP) → bare metal machines. "
        "Fabrics/VLANs segment provisioning vs production traffic. "
        "cloud-init/curtin customizes deployed OS."
    ),
})

# ── Cybersecurity ─────────────────────────────────────────────────────────────
_add("cybersecurity-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**Defense in depth** layers controls: perimeter firewall, segmentation, host hardening, "
        "identity, encryption, detection, response. **Zero trust** verifies every request regardless "
        "of network location — assume breach.\n\n"
        "**CIA triad:** Confidentiality, Integrity, Availability — every control maps to one or more."
    ),
})

_add("cybersecurity-zero-hero", 8, {
    "theory": (
        "## Theory\n\n"
        "**SIEM** (Security Information and Event Management) centralizes logs and correlates events "
        "into alerts. **Detection engineering** writes rules for TTPs (MITRE ATT&CK). "
        "Tune false positives or analysts ignore alerts.\n\n"
        "**SOAR** playbooks automate enrichment, containment, and ticketing."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "Write a detection rule for failed SSH brute force (5+ failures in 5 min).\n"
        "Map alert to MITRE technique ID and run tabletop response."
    ),
})

_add("cybersecurity-zero-hero", 10, {
    "enterprise": (
        "## Enterprise compliance programs\n\n"
        "SOC2, ISO 27001, PCI-DSS, HIPAA — each requires evidence: access reviews, encryption, "
        "vulnerability scans, incident response drills, and vendor risk assessments. "
        "Automate evidence collection; auditors ask for timestamps and ownership."
    ),
})

# ── VyOS ──────────────────────────────────────────────────────────────────────
_add("vyos-networking-zero-hero", 1, {
    "theory": (
        "## Theory\n\n"
        "**VyOS** is a Linux-based network OS with Vyatta-style CLI. Configuration is hierarchical: "
        "`set` adds, `delete` removes, `commit` applies, `save` persists to `/config/config.boot`.\n\n"
        "**commit confirm 10** applies changes but auto-reverts unless confirmed — essential for remote WAN changes."
    ),
    "labs": (
        "## Hands-on labs\n\n"
        "configure\n"
        "set interfaces ethernet eth0 address dhcp\n"
        "commit confirm 10\n"
        "confirm  # if access works\n"
        "save"
    ),
})

_add("vyos-networking-zero-hero", 4, {
    "theory": (
        "## Theory\n\n"
        "**OSPF** (link-state, area 0 backbone) for internal routing. **BGP** (path-vector) for WAN and "
        "Internet peering. On VyOS: `set protocols ospf area 0 network ...` and "
        "`set protocols bgp neighbor ...` with route-maps for policy.\n\n"
        "Always filter routes — route leaks take down networks."
    ),
})

_add("vyos-networking-zero-hero", 10, {
    "troubleshooting": (
        "## Enterprise troubleshooting\n\n"
        "**Layered approach:** physical link → IP addressing → routing table → firewall rules → NAT → DNS.\n\n"
        "VyOS tools: `show interfaces`, `show ip route`, `show log`, `monitor traffic interface`. "
        "Use `commit confirm` for every production change. Document rollback before touching BGP."
    ),
})


def _ensure_all_modules_deep() -> None:
    try:
        from ..course_catalog import all_course_definitions
        from .auto_deep import populate_deep_sections
        populate_deep_sections(DEEP_SECTIONS, all_course_definitions())
    except Exception:
        pass


_ensure_all_modules_deep()


def get_deep_body(course_slug: str, module_order: int, section_key: str) -> str | None:
    pack = DEEP_SECTIONS.get((course_slug, module_order))
    if not pack:
        return None
    return pack.get(section_key)
