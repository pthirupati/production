"""
Topic knowledge profiles — factual anchors for end-to-end tutorial prose.

Each profile supplies architecture, commands, concepts, and production patterns
that section writers expand into full lessons.
"""

from __future__ import annotations

from functools import lru_cache

# fmt: off
TOPIC_PROFILES: dict[str, dict] = {
    "Database": {
        "tagline": "Relational and polyglot data platforms for transactional and analytical workloads",
        "engines": ["PostgreSQL", "MySQL/InnoDB", "SQLite", "MongoDB", "Redis"],
        "architecture": (
            "A production database stack spans clients, connection pools (PgBouncer, ProxySQL), "
            "primary/replica topology, backup agents, and observability (slow query logs, pg_stat_*, "
            "Performance Schema). The query path runs: parse → plan/optimize → execute → WAL/commit → "
            "replicate to standbys."
        ),
        "concepts": {
            "relational": "Tables, rows, primary/foreign keys, normalization (1NF–3NF), and ACID transactions.",
            "acid": "Atomicity (all-or-nothing), Consistency (constraints hold), Isolation (concurrent visibility), Durability (WAL on disk).",
            "index": "B-tree for equality/range; partial indexes; covering indexes avoid heap lookups.",
            "replication": "Streaming/async replication, semi-sync, logical decoding, and conflict handling.",
            "backup": "Logical (pg_dump, mysqldump) vs physical (PITR, WAL archiving, binlog).",
        },
        "commands": {
            "psql": "psql -h HOST -U USER -d DB -c \"SELECT version();\"",
            "explain": "EXPLAIN (ANALYZE, BUFFERS) SELECT ...",
            "mysql": "mysql -e \"SHOW ENGINE INNODB STATUS\\G\"",
            "redis": "redis-cli INFO memory",
        },
        "certs": "AWS Database Specialty, PostgreSQL CE, MySQL DBA, MongoDB DBA",
        "slo": "Query p99 latency, replication lag seconds, backup success rate, connection pool saturation",
    },
    "PostgreSQL": {
        "tagline": "Advanced open-source OLTP database with MVCC and extensibility",
        "architecture": (
            "Postmaster forks backends per connection. Shared buffers cache pages; WAL ensures durability. "
            "Background workers: checkpointer, autovacuum, walwriter, stats collector. "
            "Extensions (pg_stat_statements, pgvector) load into each database."
        ),
        "concepts": {
            "mvcc": "Each row has xmin/xmax; readers don't block writers; VACUUM reclaims dead tuples.",
            "vacuum": "Autovacuum prevents transaction ID wraparound and bloat; manual VACUUM FULL rewrites tables.",
            "replication": "Physical streaming to standbys; logical replication for selective tables.",
            "pooling": "PgBouncer transaction pooling reduces connection overhead on app servers.",
        },
        "commands": {
            "init": "initdb -D /var/lib/pgsql/data && pg_ctl start",
            "backup": "pg_dump -Fc mydb > mydb.dump && pg_basebackup -D /backup/base",
            "monitor": "SELECT * FROM pg_stat_activity; SELECT * FROM pg_stat_replication;",
        },
        "certs": "PostgreSQL CE Associate/Professional, EDB certifications",
    },
    "MySQL": {
        "tagline": "Widely deployed OLTP database with InnoDB storage engine",
        "architecture": "Connection layer → SQL layer → InnoDB (buffer pool, redo log, doublewrite buffer) → tablespaces on disk.",
        "concepts": {
            "innodb": "Row-level locking, clustered PK, secondary indexes point to PK.",
            "replication": "Async binlog replication; GTID simplifies failover; Group Replication for HA clusters.",
            "slowlog": "long_query_time and log_queries_not_using_indexes surface tuning candidates.",
        },
        "commands": {
            "status": "SHOW GLOBAL STATUS LIKE 'Threads%'; SHOW ENGINE INNODB STATUS\\G",
            "backup": "mysqldump --single-transaction --routines mydb > dump.sql",
        },
        "certs": "MySQL DBA, Oracle MySQL certification tracks",
    },
    "SQLite": {
        "tagline": "Embedded zero-config SQL engine for edge and mobile",
        "architecture": "Single writer, multiple readers. Pager module, B-tree storage, WAL journal mode for concurrency.",
        "concepts": {
            "wal": "Write-Ahead Logging allows concurrent reads during writes; -wal and -shm sidecar files.",
            "limits": "Single writer lock; not for high-concurrency web backends — use client/server DB instead.",
        },
        "commands": {
            "cli": "sqlite3 app.db \".schema\" \"PRAGMA journal_mode=WAL;\"",
        },
    },
    "MongoDB": {
        "tagline": "Document database with flexible schema and horizontal scaling",
        "architecture": "mongod processes hold data; mongos routes in sharded clusters; config servers store chunk metadata.",
        "concepts": {
            "replica set": "Primary elections, oplog tailing, read preferences, write concern majority.",
            "sharding": "Shard key choice is irreversible — causes jumbo chunks if wrong.",
        },
        "commands": {
            "shell": "mongosh --eval 'db.serverStatus()'",
            "index": "db.collection.createIndex({ field: 1 })",
        },
    },
    "Redis": {
        "tagline": "In-memory data structure store for cache, pub/sub, and streams",
        "architecture": "Single-threaded event loop (per Redis 6+ with IO threads optional). RDB snapshots + AOF persistence.",
        "concepts": {
            "eviction": "maxmemory-policy: allkeys-lru, volatile-lru, noeviction for cache tiers.",
            "cluster": "16384 hash slots; resharding moves slots between masters.",
        },
        "commands": {
            "info": "redis-cli INFO stats",
            "memory": "redis-cli --bigkeys",
        },
    },
    "Linux": {
        "tagline": "Enterprise Linux administration exceeding RHCSA/RHCE scope",
        "architecture": "Kernel space (syscalls, VFS, network stack, cgroups) vs user space (systemd, shells, daemons).",
        "concepts": {
            "systemd": "Units (service, socket, timer, mount); targets replace runlevels; journald centralizes logs.",
            "selinux": "Type enforcement; booleans; audit2allow for custom policies; enforcing vs permissive.",
            "lvm": "PV → VG → LV; online extend with xfs_growfs or resize2fs.",
            "boot": "UEFI → shim/grub2 → initramfs → systemd → default.target.",
        },
        "commands": {
            "systemd": "systemctl status sshd && journalctl -u sshd -b",
            "storage": "lsblk && vgs && lvs && df -hT",
            "selinux": "getenforce && ausearch -m avc -ts recent",
        },
        "certs": "RHCSA EX200, RHCE EX294, LFCS, LPIC",
    },
    "Kubernetes": {
        "tagline": "Container orchestration from pods to multi-cluster GitOps",
        "architecture": (
            "Control plane: kube-apiserver (REST), etcd (state), scheduler, controller-manager, cloud-controller. "
            "Node: kubelet, kube-proxy, container runtime (containerd/CRI-O). CNI handles pod networking."
        ),
        "concepts": {
            "pod": "Smallest schedulable unit; shared network namespace; ephemeral by design.",
            "deployment": "ReplicaSet manages Pod templates; rolling updates with maxSurge/maxUnavailable.",
            "service": "ClusterIP internal; NodePort/LoadBalancer external; Endpoints slice to ready pods.",
            "ingress": "L7 routing via Ingress controller (nginx, traefik); TLS via cert-manager.",
            "rbac": "Role/ClusterRole + Binding; ServiceAccount tokens for in-cluster auth.",
        },
        "commands": {
            "basics": "kubectl get nodes,pods,svc -A && kubectl describe pod POD",
            "debug": "kubectl logs POD -c CONTAINER --previous && kubectl debug -it POD --image=busybox",
            "helm": "helm upgrade --install APP ./chart -f values-prod.yaml",
        },
        "certs": "CKA, CKAD, CKS, KCNA",
    },
    "Docker": {
        "tagline": "OCI container packaging and runtime on a single host",
        "architecture": "docker CLI → dockerd → containerd → runc. Images are layered union filesystems; containers add writable layer.",
        "concepts": {
            "image": "Immutable layers; Dockerfile instructions create layers; cache invalidation on COPY/ RUN order.",
            "volume": "Named volumes survive container delete; bind mounts map host paths.",
            "network": "bridge default; user-defined networks provide DNS by container name.",
            "compose": "Declarative multi-service; healthcheck + depends_on for startup order.",
        },
        "commands": {
            "run": "docker run -d --name web -p 8080:80 --restart unless-stopped nginx:alpine",
            "compose": "docker compose up -d && docker compose logs -f web",
        },
    },
    "Terraform": {
        "tagline": "Declarative infrastructure as code with plan/apply workflow",
        "architecture": "CLI → provider plugins → cloud APIs. State file maps config addresses to real resource IDs.",
        "concepts": {
            "state": "terraform.tfstate tracks reality; remote backend (S3+lock) for teams.",
            "plan": "Refresh + diff; shows create/update/destroy before apply.",
            "module": "Reusable packages; output → input wiring; version constraints in required_providers.",
        },
        "commands": {
            "workflow": "terraform init && terraform validate && terraform plan -out=plan.tfplan",
            "apply": "terraform apply plan.tfplan",
        },
        "certs": "HashiCorp Terraform Associate/Professional",
    },
    "Ansible": {
        "tagline": "Agentless configuration management and automation",
        "architecture": "Control node SSHs to managed nodes; modules are idempotent; facts gathered via setup module.",
        "concepts": {
            "inventory": "Static INI/YAML or dynamic from cloud; groups and host_vars.",
            "playbook": "Plays → tasks → modules; handlers run once on notify.",
            "vault": "ansible-vault encrypts secrets; AWX/Tower adds RBAC and scheduling.",
        },
        "commands": {
            "ad hoc": "ansible web -m ping && ansible web -m apt -a 'name=nginx state=present' -b",
            "playbook": "ansible-playbook site.yml --check --diff",
        },
    },
    "Prometheus": {
        "tagline": "Pull-based metrics and PromQL alerting",
        "architecture": "Scrape targets → TSDB blocks → PromQL → Alertmanager → notifications.",
        "concepts": {
            "promql": "rate() for counters; histogram_quantile for latency; label matchers filter series.",
            "alerting": "Recording rules pre-compute; alert rules fire on thresholds; Alertmanager routes/silences.",
        },
        "commands": {
            "query": "curl -s 'localhost:9090/api/v1/query?query=up'",
        },
    },
    "Grafana": {
        "tagline": "Unified observability dashboards and alerting",
        "architecture": "Datasources (Prometheus, Loki, Tempo) → panels → dashboards → alert rules → contact points.",
        "concepts": {
            "variables": "Templating filters dashboards by cluster, namespace, job.",
            "explore": "Ad-hoc query mode with split view for metrics/logs/traces.",
        },
    },
    "AI Infrastructure": {
        "tagline": "GPU clusters, inference serving, and ML platform operations",
        "architecture": "GPU nodes (driver + container toolkit) → Kubernetes device plugin → workload (Training/Inference).",
        "concepts": {
            "gpu": "nvidia-smi, MIG partitioning, GPU memory fragmentation, thermal throttling.",
            "inference": "vLLM, Triton, TensorRT-LLM, batching, KV cache, quantization.",
            "scheduling": "GPU requests/limits; MIG profiles; topology-aware scheduling for NVLink.",
        },
        "commands": {
            "gpu": "nvidia-smi && nvidia-smi dmon -s pucvmet",
            "k8s": "kubectl describe node GPU-NODE | grep -A5 Allocatable",
        },
    },
    "Bare Metal": {
        "tagline": "Physical server lifecycle from BMC to Kubernetes",
        "architecture": "BMC (iDRAC/iLO) → PXE/MAAS → OS → Kubernetes/Metal3.",
        "concepts": {
            "pxe": "DHCP option 66/67, TFTP boot file, iPXE chainload.",
            "ipmi": "ipmitool power status; SOL serial console; Redfish REST API.",
        },
        "commands": {
            "ipmi": "ipmitool -I lanplus -H BMC -U USER -P PASS power status",
        },
    },
    "MAAS": {
        "tagline": "Canonical Metal-as-a-Service bare metal provisioning",
        "architecture": "Region controller + rack controllers; DHCP/TFTP/DNS; commissioning scripts; curtin deployment.",
        "concepts": {
            "commissioning": "Hardware tests, disk erasure, firmware inventory before deploy.",
            "fabrics": "VLANs, subnets, static routes, IP allocation policies.",
        },
    },
    "VyOS": {
        "tagline": "Linux-based network OS for routing and firewall",
        "architecture": "Vyatta heritage; config in config.boot; commit/confirm for safe changes.",
        "concepts": {
            "routing": "Static, OSPF, BGP; route-maps and prefix-lists for policy.",
            "vpn": "IPsec site-to-site; WireGuard; NAT and firewall zones.",
        },
    },
    "Cybersecurity": {
        "tagline": "Defense-in-depth from network to application",
        "architecture": "Perimeter → IAM → workload → data → SIEM detection → IR playbooks.",
        "concepts": {
            "zero trust": "Verify explicitly, least privilege, assume breach.",
            "siem": "Correlation rules; MITRE ATT&CK mapping; SOAR automation.",
        },
    },
    "Python": {
        "tagline": "Automation, APIs, and data tooling",
        "architecture": "Interpreter, venv isolation, pip/poetry packaging, asyncio event loop.",
        "commands": {"venv": "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"},
    },
    "Bash": {
        "tagline": "Shell scripting for portable automation",
        "concepts": {"quoting": "Single quotes literal; double allows expansion; \"$var\" always quote."},
        "commands": {"lint": "shellcheck script.sh && bash -n script.sh"},
    },
    "Git": {
        "tagline": "Distributed version control",
        "concepts": {"branch": "Branches are pointers to commits; merge vs rebase trade-offs."},
        "commands": {"log": "git log --oneline --graph --all -20"},
    },
    "DevOps": {
        "tagline": "Culture and toolchain for fast, reliable delivery",
        "concepts": {"dora": "Deployment frequency, lead time, MTTR, change failure rate."},
    },
    "Networking": {
        "tagline": "TCP/IP, routing, switching, and load balancing",
        "concepts": {"osi": "L2 switching, L3 routing, L4/L7 load balancing, DNS resolution path."},
        "commands": {"trace": "ip route get 8.8.8.8 && ss -tulpn && dig +trace example.com"},
    },
    "Monitoring": {
        "tagline": "Metrics, logs, traces, and SRE practices",
        "concepts": {"slo": "SLI → SLO → error budget → alerting on burn rate."},
    },
    "Simulation": {
        "tagline": "FixitLab hands-on training without production risk",
        "concepts": {
            "grading": "Terminal labs use real state checks; GUI Lab Environments validate VMware, Grafana, Terraform, Windows, and other tool state.",
            "cross tech": "Shared session links terminal fixes to GUI state.",
        },
    },
}

# Default profile for topics without explicit entry
_DEFAULT_PROFILE = {
    "tagline": "Production engineering fundamentals",
    "architecture": "Control plane manages configuration; data plane serves requests; observability closes the feedback loop.",
    "concepts": {"operations": "Design for failure, automate toil, document runbooks, measure everything."},
    "commands": {"health": "curl -sf localhost/health || systemctl is-active SERVICE"},
    "certs": "Vendor and FixitLab certification tracks",
}


@lru_cache(maxsize=None)
def get_profile(topic: str) -> dict:
    """Return the knowledge profile for a topic (memoized).

    The result is deterministic per topic and callers treat it as read-only.
    Memoizing avoids rebuilding the merged ``get_all_profiles()`` dict on every
    call — this ran once per section (16k+ times during a full seed).
    """
    try:
        from .topic_profiles_all import get_all_profiles
        profiles = get_all_profiles()
    except ImportError:
        profiles = TOPIC_PROFILES
    if topic in profiles:
        return profiles[topic]
    # Synthesized profile so every catalog topic gets substantive section writers
    t = topic.lower()
    return {
        **_DEFAULT_PROFILE,
        "tagline": f"{topic} engineering for production workloads",
        "architecture": (
            f"{topic} systems combine control-plane configuration with data-plane execution. "
            "Document dependencies on network, identity, storage, and observability before changes."
        ),
        "concepts": {
            "operations": f"Day-2 {t} ops: patch, scale, backup, monitor, incident response.",
            "automation": f"Automate {t} with IaC, CI/CD, and GitOps to eliminate snowflakes.",
        },
        "commands": {"health": f"# {topic} health check\nhelp 2>/dev/null | head -5 || echo 'open {t} playground'"},
        "certs": f"{topic} vendor certifications and FixitLab assessment tracks",
        "slo": "availability, latency p99, error rate, saturation",
    }
