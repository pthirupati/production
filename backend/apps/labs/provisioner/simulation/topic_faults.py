"""Topic-aware fault injection — plant REAL broken state from scenario keywords.

Academy generators often recycle nginx/rsyslog breaks for unrelated titles.
This module maps slug keywords onto genuine Lab Server state so the terminal
and GUI reflect the scenario narrative before the learner starts fixing.
"""

from __future__ import annotations

from typing import Any

# Shared with scripts/upgrade_academy_labs.py — keep keyword lists in sync.
CI_KEYWORDS = (
    "git-flow", "git-merge", "learn-git", "ci-pipeline", "cicd", "gitlab-ci",
    "jenkins", "artifacts", "cd-release", "change-management", "incident-response",
)
GITOPS_KEYWORDS = ("gitops", "argocd", "flux", "outofsync", "kustomize", "drift", "sync")
PERM_KEYWORDS = ("permissions", "acl", "chmod", "chown", "sudoers")
NETSEC_KEYWORDS = ("dns", "resolv", "ntp", "chrony", "firewall", "selinux", "vlan", "bonding", "mtu", "nat")
K8S_KEYWORDS = ("kubernetes", "k8s", "pod-", "crashloop", "kubelet", "helm-")
TF_KEYWORDS = ("terraform", "tfstate", "iac-")
DOCKER_KEYWORDS = ("docker-compose", "compose", "containerd", "dockerfile")
DB_KEYWORDS = ("postgres", "mysql", "mariadb", "redis", "mongodb", "pgbouncer")
JAVA_KEYWORDS = ("spring-boot", "jvm", "tomcat", "heap-", "gc-pause", "springboot")
SEC_KEYWORDS = ("secrets", "vault", "tls-", "cert-", "rbac", "owasp")
OPENSTACK_KEYWORDS = ("openstack", "nova", "neutron", "keystone", "glance", "cinder", "horizon")
MEMCACHE_KEYWORDS = ("memcached", "memcache")
MQ_KEYWORDS = ("rabbitmq", "amqp")

# Storage / DC / SOC / mesh / OTel — the G3 "9 worst" academy families that
# previously recycled nginx breaks. Narrow prefixes so we do not steal
# unrelated slugs (e.g. bare "mesh" in hostnames).
NETAPP_KEYWORDS = ("academy-netapp-", "netapp-", "-ontap-", "snapmirror")
DELL_KEYWORDS = ("academy-dellemc-", "dellemc-", "powermax", "unisphere")
DATACENTER_KEYWORDS = ("academy-datacenter-", "datacenter-", "dcim-")
SOC_KEYWORDS = ("academy-soc-", "soc-", "-siem-", "wazuh", "suricata")
OTEL_KEYWORDS = ("academy-opentelemetry-", "opentelemetry-", "otel-", "otelcol")
MESH_KEYWORDS = ("academy-service-mesh-", "service-mesh-", "istio-", "linkerd-")
COMMVAULT_KEYWORDS = ("academy-commvault-", "commvault-", "cvlt-", "simpana")
AI_INFRA_KEYWORDS = ("academy-ai-infra-", "ai-infra-", "gpu-operator", "dcgm-exporter")

# AI vertical. These are deliberately NARROW and hyphen-anchored: a bare
# "model"/"agent"/"rag" family would hijack unrelated slugs that merely contain
# the substring (measured: "awx-agent-node", "data-model-migration", and the
# Jenkins "agent" labs), re-seeding the world for scenarios that are already
# written and graded. Every keyword below was checked against the real slug
# corpus so it only matches AI-track labs.
GPU_KEYWORDS = (
    "gpu", "nvidia", "cuda", "nvlink", "nccl", "rccl", "dcgm", "xid-",
    "hbm", "mig-", "rocm", "amd-smi", "cuda-oom", "out-of-memory", "-oom-",
)
LLM_KEYWORDS = (
    "llm-", "vllm", "inference", "triton", "tensorrt", "model-serving",
    "text-generation", "kserve", "ollama",
)
TRAINING_KEYWORDS = (
    # NOT a bare "checkpoint-": that collides with db-postgres-checkpoint-spikes,
    # a Postgres WAL lab which must keep its DB fault (measured collision).
    "training-job", "fine-tune", "fine-tuning", "model-checkpoint", "deepspeed",
    "torchrun", "pytorch-", "distributed-training",
)
RAG_KEYWORDS = (
    "rag-", "vector-db", "vectordb", "embedding", "pgvector", "milvus",
    "qdrant", "weaviate", "faiss",
)


def apply_topic_fault(slug: str, state: Any) -> bool:
    """Apply a topic fault if the slug matches. Returns True when something changed."""
    low = (slug or "").lower()
    if not low:
        return False

    # Disk pressure (exact families — avoid inode/deleted-open hijacks)
    if low in ("disk-full", "sim-disk-full", "sim-rhel-disk-full") or (
        low.endswith("-disk-full") and "inode" not in low and "deleted" not in low
    ):
        from .scenario_presets import _preset_disk_full
        _preset_disk_full(state)
        return True

    # Cloud academies FIRST — slug keywords like "firewall"/"dns" must not steal
    # GCP firewall-rules / Azure NSG labs into host firewalld/named breaks.
    if low.startswith("academy-aws") or (low.startswith("aws-") and "terraform" not in low):
        return _fault_aws_academy(state, low)
    if low.startswith(("academy-azure", "azure-")):
        return _fault_cloud_cli(state, low, "azure")
    if low.startswith(("academy-gcp", "gcp-")):
        return _fault_cloud_cli(state, low, "gcp")
    if low.startswith(("academy-openstack", "openstack-")) or any(
        k in low for k in OPENSTACK_KEYWORDS
    ):
        return _fault_openstack(state, low)

    # G3 worst-tech families — plant tech-native breaks BEFORE CI/AI keyword
    # families so "academy-soc-*-security-*" is not stolen by SEC_KEYWORDS into
    # a vault/tls break that still looks like a Linux daemon incident.
    if low.startswith("academy-netapp-") or any(k in low for k in NETAPP_KEYWORDS):
        return _fault_netapp(state, low)
    if low.startswith("academy-dellemc-") or any(k in low for k in DELL_KEYWORDS):
        return _fault_dellemc(state, low)
    if low.startswith("academy-datacenter-") or any(k in low for k in DATACENTER_KEYWORDS):
        return _fault_datacenter(state, low)
    if low.startswith("academy-soc-") or any(k in low for k in SOC_KEYWORDS):
        return _fault_soc(state, low)
    if low.startswith("academy-opentelemetry-") or any(k in low for k in OTEL_KEYWORDS):
        return _fault_otel(state, low)
    if low.startswith("academy-service-mesh-") or any(k in low for k in MESH_KEYWORDS):
        return _fault_service_mesh(state, low)
    if low.startswith("academy-commvault-") or any(k in low for k in COMMVAULT_KEYWORDS):
        return _fault_commvault(state, low)
    if low.startswith("academy-ai-infra-") or any(k in low for k in AI_INFRA_KEYWORDS):
        return _fault_ai_infra(state, low)

    # Git / devops CI topics — plant a broken CI config + inactive runner, not nginx
    # Deliberately BEFORE the AI families so a Jenkins "pipeline agent" lab keeps
    # its CI break instead of being pulled into a GPU fault.
    if any(k in low for k in CI_KEYWORDS):
        return _fault_ci_git(state, low)

    # AI vertical — GPU hardware faults, model serving, training, RAG/vector.
    # Must run before K8S_KEYWORDS: "gpu-k8s-device-plugin-daemonset" and
    # "ai-infra-k8s-gpu-operator" are GPU labs that happen to contain "k8s".
    if any(k in low for k in GPU_KEYWORDS):
        return _fault_gpu(state, low)
    # academy-ai-ml-* already gets a dedicated "model-server" unit from
    # academy_service_presets, and that unit is the one the registered E2E fix
    # repairs. Planting a second failed unit (vllm) here left the lab failing
    # AFTER the documented fix — i.e. unsolvable — so the academy track keeps
    # its own break. Measured on academy-ai-ml-007/017/027.
    if not low.startswith("academy-"):
        if any(k in low for k in LLM_KEYWORDS):
            return _fault_llm_serving(state, low)
        if any(k in low for k in TRAINING_KEYWORDS):
            return _fault_training(state, low)
        if any(k in low for k in RAG_KEYWORDS):
            return _fault_rag(state, low)

    # GitOps / Argo / Flux — OutOfSync app + missing FIXED path for marker labs
    if any(k in low for k in GITOPS_KEYWORDS):
        return _fault_gitops(state, low)

    # Permissions / ACL
    if any(k in low for k in PERM_KEYWORDS):
        return _fault_permissions(state, low)

    # Networking / host security basics
    if any(k in low for k in NETSEC_KEYWORDS):
        return _fault_network_security(state, low)

    # Kubernetes / workloads
    if any(k in low for k in K8S_KEYWORDS):
        return _fault_kubernetes(state, low)

    # Terraform / IaC
    if any(k in low for k in TF_KEYWORDS):
        return _fault_terraform(state, low)

    # Docker / compose
    if any(k in low for k in DOCKER_KEYWORDS):
        return _fault_docker(state, low)

    # Databases
    if any(k in low for k in DB_KEYWORDS):
        return _fault_database(state, low)

    # Memcached / message queues
    if any(k in low for k in MEMCACHE_KEYWORDS):
        return _fault_service_unit(state, low, "memcached", "Memcached")
    if any(k in low for k in MQ_KEYWORDS):
        return _fault_service_unit(state, low, "rabbitmq-server", "RabbitMQ broker")

    # Java / JVM apps — do not match "javascript"
    if "javascript" not in low and any(k in low for k in JAVA_KEYWORDS):
        return _fault_java(state, low)

    # Security / secrets / TLS
    if any(k in low for k in SEC_KEYWORDS):
        return _fault_security(state, low)

    return False


def _fault_gpu(state: Any, slug: str) -> bool:
    """Break the GPU for real: unhealthy inventory + a matching kernel log.

    Previously every gpu-* slug fell through this module entirely, so the node
    booted with gpu_healthy=True and an empty dmesg. Only a broken-config text
    sentinel made the lab fail-closed, which meant `nvidia-smi` and
    `dmesg | grep Xid` showed a perfectly healthy H100 while the brief claimed
    an uncorrectable ECC error. Setting gpu_healthy=False also keeps the
    existing validation guard ("GPU still unhealthy — load the nvidia driver
    first") meaningful instead of vacuously satisfied.

    Specific narratives also plant residual SimGPU counters (audit §A1) so that
    after the learner reloads the driver, `dcgmi diag` / `nvidia-smi nvlink`
    still reflect the break instead of randomly green numbers.
    """
    # Seed inventory from SKU before planting per-GPU counters.
    try:
        from .simulation_modules import _resolve_gpu_sku
        sku = _resolve_gpu_sku(slug)
        if hasattr(state, "ensure_gpu_inventory"):
            state.ensure_gpu_inventory(
                count=int(sku.get("count") or 1),
                name=sku.get("name") or "NVIDIA H100 80GB HBM3",
                mem_mib=int(sku.get("mem_mib") or 81559),
                power_cap_w=int(sku.get("pwr_cap") or 700),
                sku=str(sku.get("arch") or "gpu"),
            )
    except Exception:
        pass

    # Xid codes are the real NVRM diagnostic a learner greps for; pick the one
    # matching the scenario so the log corroborates the brief.
    if "nvlink" in slug:
        lines = [
            "[  512.884] NVRM: Xid (PCI:0000:01:00): 74, pid=0, NVLink: fatal error on link 3",
            "[  512.885] NVRM: GPU 0000:01:00.0: NVLink lane down, falling back to PCIe",
        ]
    elif "thermal" in slug or "overheat" in slug or "power-cap" in slug or "throttle" in slug:
        lines = [
            "[  733.201] NVRM: Xid (PCI:0000:01:00): 62, pid=0, HBM temperature above slowdown threshold",
            "[  733.202] nvidia-smi: clocks throttled — SW_THERMAL_SLOWDOWN active",
        ]
    elif "fallen-off-bus" in slug or "pcie" in slug:
        lines = [
            "[  412.331] NVRM: GPU at 0000:01:00.0 has fallen off the bus.",
            "[  412.332] NVRM: GPU 0000:01:00.0: RmInitAdapter failed! (0x26:0x65:0x1)",
        ]
    elif "nccl" in slug or "rccl" in slug:
        lines = [
            "[  901.117] NVRM: Xid (PCI:0000:01:00): 13, pid=8842, Graphics Exception on channel",
            "[  901.118] NCCL WARN Bootstrap : allreduce timed out waiting for peer rank 3",
        ]
        state.nccl_hang = True
    elif "fp16" in slug or ("nan" in slug and "training" in slug):
        lines = [
            "[  512.001] CUDA: loss became NaN under float16 — check GradScaler / bf16",
        ]
        state.training_fp16_nan = True
    elif "driver" in slug or "not-loaded" in slug or "mismatch" in slug:
        lines = [
            "[   12.004] NVRM: API mismatch: the client has version 550.54.15, but this kernel "
            "module has version 535.161.07",
            "[   12.005] NVRM: nvidia driver failed to initialize — module/library version mismatch",
        ]
    elif "cuda-oom" in slug or "out-of-memory" in slug or "-oom-" in slug or slug.endswith("-oom"):
        lines = [
            "[  901.440] NVRM: Xid (PCI:0000:01:00): 13, pid=0, Graphics Exception on channel",
            "[  901.441] CUDA out of memory — device 0 exhausted HBM",
        ]
    else:
        # ECC / HBM / Xid 48 / row-remap default.
        lines = [
            "[  612.440] NVRM: Xid (PCI:0000:01:00): 48, pid=0, An uncorrectable double-bit ECC "
            "error was detected on GPU 0.",
            "[  612.441] NVRM: GPU 0000:01:00.0: row remapping pending — drain and reset required",
        ]
    state.dmesg_extra = list(getattr(state, "dmesg_extra", []) or []) + lines
    state.gpu_healthy = False

    gpus = list(getattr(state, "gpus", None) or [])
    if not gpus:
        return True

    if "nvlink" in slug:
        for g in gpus:
            g.ensure_default_nvlink(dense=len(gpus) >= 8)
            if g.nvlink_links:
                g.nvlink_links[0] = {
                    **g.nvlink_links[0],
                    "width_gbps": 13.281,
                    "active": False,
                    "replay_errors": 42,
                }
            g.diag_pcie_fail = True
    elif "thermal" in slug or "overheat" in slug or "power-cap" in slug or "throttle" in slug:
        for g in gpus:
            g.temp_c = 89
            g.mem_temp_c = 95
            g.power_w = float(g.power_cap_w)
            g.throttle_reasons = ["SW_THERMAL_SLOWDOWN"]
            g.diag_power_fail = True
    elif "fallen-off-bus" in slug or ("pcie" in slug and "nvlink" not in slug):
        for g in gpus:
            g.diag_pcie_fail = True
    elif any(k in slug for k in ("ecc", "xid", "hbm", "row-remap", "remap", "double-bit")):
        g = gpus[0]
        g.ecc_volatile_uncorrected = 1
        g.ecc_aggregate_uncorrected = 3
        g.retired_pages_dbe = 2
        g.retired_pages_pending = True
        g.remap_pending = True
        g.diag_memory_fail = True
        g.xid_events = list(g.xid_events or []) + ["48"]
    elif "cuda-oom" in slug or "out-of-memory" in slug or "-oom-" in slug or slug.endswith("-oom"):
        g = gpus[0]
        g.oom = True
        g.memory_used_mib = int(g.memory_total_mib)
        g.util_gpu = 99
        g.util_mem = 99
    return True


def _fault_llm_serving(state: Any, slug: str) -> bool:
    """Model-serving stack down: failed unit + a config the learner must repair."""
    from .rhel_os import SimService

    state._mkdir("/opt/inference")
    state._write_file(
        "/opt/inference/model-config.yaml",
        "model: meta-llama/Llama-3-8B-Instruct\n"
        "tensor_parallel_size: 8\n"  # 8-way TP on a node that has fewer GPUs
        "gpu_memory_utilization: 0.99\n"
        "max_model_len: 131072\n",
    )
    state.services["vllm"] = SimService(
        "vllm", active="failed", enabled="enabled",
        description="vLLM inference server", loaded="loaded", sub_state="failed",
    )
    # OOM / oversubscribed TP labs also plant GPU memory pressure so `vllm serve`
    # fails with a real CUDA OOM once the unit is restarted (§A1/A2).
    if "oom" in slug or "memory" in slug or "tp-" in slug or "tensor-parallel" in slug:
        gpus = list(getattr(state, "gpus", None) or [])
        if gpus:
            g = gpus[0]
            g.oom = True
            g.memory_used_mib = int(g.memory_total_mib)
    return True


def _fault_training(state: Any, slug: str) -> bool:
    """Distributed training job wedged: failed unit + a truncated checkpoint."""
    from .rhel_os import SimService

    state._mkdir("/opt/training")
    state._mkdir("/opt/training/checkpoints")
    state._write_file(
        "/opt/training/train-config.yaml",
        "nnodes: 4\nnproc_per_node: 8\nbackend: nccl\n"
        "checkpoint_dir: /opt/training/checkpoints\nresume: true\n",
    )
    # Truncated checkpoint is the actual break — resume fails on a short read.
    state._write_file("/opt/training/checkpoints/step-4000.pt", "PK\x03\x04TRUNCATED")
    state.services["training-job"] = SimService(
        "training-job", active="failed", enabled="enabled",
        description="Distributed training job", loaded="loaded", sub_state="failed",
    )
    return True


def _fault_rag(state: Any, slug: str) -> bool:
    """RAG/vector store down: failed unit + an index config pointing nowhere."""
    from .rhel_os import SimService

    state._mkdir("/opt/rag")
    state._write_file(
        "/opt/rag/vectorstore.yaml",
        "provider: qdrant\nendpoint: http://127.0.0.1:6333\n"
        "collection: docs\nvector_size: 1536\ndistance: Cosine\n",
    )
    state.services["qdrant"] = SimService(
        "qdrant", active="failed", enabled="enabled",
        description="Qdrant vector database", loaded="loaded", sub_state="failed",
    )
    return True


def _fault_ci_git(state: Any, slug: str) -> bool:
    from .rhel_os import SimService, SimProcess

    state._mkdir("/opt/ci")
    state._mkdir("/root/app")
    state._write_file(
        "/opt/ci/.gitlab-ci.yml",
        "stages: [build]\nbuild:\n  script:\n    - echo BROKEN_PIPELINE\n    - exit 1\n",
    )
    state._write_file(
        "/opt/ci/Jenkinsfile",
        "pipeline { agent any; stages { stage('Build') { steps { sh 'exit 1' } } } }\n",
    )
    state._write_file(
        "/root/app/.git/config",
        "[core]\n\trepositoryformatversion = 0\n[branch \"main\"]\n\tremote = origin\n",
    )
    state.services["gitlab-runner"] = SimService(
        "gitlab-runner", active="failed", enabled="enabled",
        description="GitLab Runner", loaded="loaded", sub_state="failed",
    )
    # Graded via `systemctl is-active gitlab-runner` — no FIXED-OK sentinel.
    return True


def _fault_gitops(state: Any, slug: str) -> bool:
    state._mkdir("/opt/gitops")
    state._mkdir("/root/.kube")
    state._write_file(
        "/opt/gitops/application.yaml",
        "apiVersion: argoproj.io/v1alpha1\nkind: Application\nmetadata:\n  name: webapp\n"
        "spec:\n  source:\n    repoURL: https://github.com/example/gitops.git\n"
        "    path: overlays/prod\n  syncPolicy: {}\n"
        "status:\n  sync:\n    status: OutOfSync\n  health:\n    status: Degraded\n",
    )
    state._write_file(
        "/opt/gitops/flux-kustomization.yaml",
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\nkind: Kustomization\n"
        "metadata:\n  name: apps\nspec:\n  path: ./apps\n  prune: true\n"
        "status:\n  conditions:\n  - type: Ready\n    status: \"False\"\n"
        "    message: reconciliation failed\n",
    )
    state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\nclusters: []\n")
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_permissions(state: Any, slug: str) -> bool:
    state._mkdir("/opt/app")
    state._mkdir("/etc/sudoers.d")
    state._write_file("/opt/app/secret.env", "SECRET=changeme\n", mode="777")
    state._write_file(
        "/etc/sudoers.d/app",
        "appuser ALL=(ALL) NOPASSWD: ALL\n# insecure — needs lockdown\n",
        mode="644",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_network_security(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    if "dns" in slug or "resolv" in slug:
        state._write_file("/etc/resolv.conf", "nameserver 127.0.0.1\n# broken — no upstream\n")
        state.services["named"] = SimService(
            "named", active="failed", enabled="enabled", description="DNS server",
        )
    if "ntp" in slug or "chrony" in slug:
        state.services["chronyd"] = SimService(
            "chronyd", active="failed", enabled="enabled", description="NTP client/server",
        )
    if "firewall" in slug:
        state.services["firewalld"] = SimService(
            "firewalld", active="failed", enabled="enabled", description="firewalld",
        )
        # Academy list-ports labs grade via is_port_open(80). Default FirewallState
        # includes the "http" service, which auto-passes without learner work —
        # strip http/ports so the unfixed world fail-closes (grader-integrity).
        from .scenario_presets import _preset_firewalld_blocked
        _preset_firewalld_blocked(state)
        # Keep firewalld failed after the nginx/firewall preset (preset may leave
        # other services active; firewalld itself must stay down until started).
        state.services["firewalld"] = SimService(
            "firewalld", active="failed", enabled="enabled", description="firewalld",
        )
    if "selinux" in slug and "httpd-port" not in slug:
        # httpd-port-denied must stay Enforcing (fix via semanage, not setenforce 0).
        state.selinux_mode = "Permissive"
    if "vlan" in slug or "bonding" in slug or "mtu" in slug or "nat" in slug:
        state._write_file(
            "/etc/sysconfig/network-scripts/ifcfg-eth0",
            "DEVICE=eth0\nBOOTPROTO=none\nONBOOT=no\n# broken NIC config\n",
        )
        from .scenario_presets import _plant_broken_config_sentinel
        _plant_broken_config_sentinel(slug, state)
    elif "selinux" in slug and "httpd-port" not in slug:
        # httpd-port-denied is healed via semanage — do not plant a FIXED-OK
        # academy sentinel that would block after the real remediation.
        from .scenario_presets import _plant_broken_config_sentinel
        _plant_broken_config_sentinel(slug, state)
    # firewall/dns/chrony are graded via systemctl is-active <unit> — no sentinel.
    return True


def _fault_kubernetes(state: Any, slug: str) -> bool:
    state._mkdir("/root/.kube")
    state._mkdir("/opt/k8s")
    state._write_file("/root/.kube/config", "apiVersion: v1\nkind: Config\nclusters: []\n")
    state._write_file(
        "/opt/k8s/deployment.yaml",
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: webapp\n"
        "spec:\n  replicas: 1\n  template:\n    spec:\n      containers:\n"
        "      - name: app\n        image: broken:missing\n",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_terraform(state: Any, slug: str) -> bool:
    state._mkdir("/opt/terraform")
    state._write_file(
        "/opt/terraform/main.tf",
        'resource "null_resource" "broken" {\n  triggers = { status = "BROKEN" }\n}\n',
    )
    state._write_file("/opt/terraform/terraform.tfstate", '{"version":4,"resources":[]}\n')
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_docker(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/app")
    state._write_file(
        "/opt/app/docker-compose.yml",
        "services:\n  web:\n    image: nginx:broken\n    ports: [\"80:80\"]\n",
    )
    state.services["docker"] = SimService(
        "docker", active="failed", enabled="enabled",
        description="Docker Application Container Engine",
        loaded="loaded", sub_state="failed",
    )
    return True


def _fault_database(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    unit = "postgresql"
    if any(k in slug for k in ("mysql", "mariadb")):
        unit = "mysqld"
    elif "redis" in slug:
        unit = "redis"
    elif "mongo" in slug:
        unit = "mongod"
    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled",
        description=f"{unit} database", loaded="loaded", sub_state="failed",
    )
    return True


def _fault_java(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/app")
    state._write_file("/opt/app/application.properties", "server.port=0\n# broken bind\n")
    state.services["spring-boot"] = SimService(
        "spring-boot", active="failed", enabled="enabled",
        description="Spring Boot Application Service",
        loaded="loaded", sub_state="failed",
    )
    return True


def _fault_security(state: Any, slug: str) -> bool:
    state._mkdir("/opt/app")
    state._mkdir("/etc/pki/tls")
    if "secret" in slug or "vault" in slug:
        state._write_file("/opt/app/secrets.env", "API_KEY=plaintext-in-repo\n", mode="666")
    if "tls" in slug or "cert" in slug:
        state._write_file("/etc/pki/tls/certs/lab.crt", "# EXPIRED CERT\nBROKEN\n")
    if "rbac" in slug or "owasp" in slug:
        state._write_file(
            "/opt/app/rbac.yaml",
            "rules:\n- apiGroups: [\"*\"]\n  resources: [\"*\"]\n  verbs: [\"*\"]\n",
        )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_service_unit(state: Any, slug: str, unit: str, desc: str) -> bool:
    from .rhel_os import SimService

    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled",
        description=desc, loaded="loaded", sub_state="failed",
    )
    return True


def _fault_openstack(state: Any, slug: str) -> bool:
    state._mkdir("/opt/openstack")
    state._write_file(
        "/opt/openstack/clouds.yaml",
        "clouds:\n  lab:\n    auth:\n      auth_url: http://127.0.0.1:5000/v3\n"
        "      project_name: broken\n      username: broken\n      password: wrong\n"
        "    region_name: RegionOne\n",
    )
    state._write_file(
        "/opt/openstack/lab-state.json",
        '{"nova":"down","neutron":"misconfigured","status":"broken"}\n',
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_aws_academy(state: Any, slug: str) -> bool:
    """Close fail-open: academy-aws check.sh is `systemctl is-failed` with no prior break."""
    state._mkdir("/opt/aws")
    state._write_file(
        "/opt/aws/lab-state.json",
        '{"ec2":"misconfigured","sg":"too-open","status":"broken"}\n',
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_cloud_cli(state: Any, slug: str, cloud: str) -> bool:
    state._mkdir(f"/opt/{cloud}")
    state._write_file(
        f"/opt/{cloud}/config",
        f"# broken {cloud} CLI profile — subscription/project not set\n",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_netapp(state: Any, slug: str) -> bool:
    """Stop svm-prod / strip NFS — matches state_assertions for academy-netapp-001."""
    from .rhel_os import SimService

    state._mkdir("/opt/netapp")
    state._write_file(
        "/opt/netapp/lab-state.json",
        '{"svm-prod":"stopped","protocols":["cifs"],"status":"broken"}\n',
    )
    state.services["netapp-ontap"] = SimService(
        "netapp-ontap", active="failed", enabled="enabled",
        description="NetApp ONTAP management agent", loaded="loaded", sub_state="failed",
    )
    sid = getattr(state, "session_id", None)
    if sid:
        try:
            from apps.vmware_sim import netapp_engine as ne

            entry = ne._ensure(str(sid), slug)
            st = entry["state"]
            for svm in st.get("svms") or []:
                if svm.get("name") == "svm-prod":
                    svm["state"] = "stopped"
                    prots = [p for p in (svm.get("protocols") or []) if p != "nfs"]
                    svm["protocols"] = prots or ["cifs"]
            st["broken"] = {"svm_stopped": "svm-prod", "needs_nfs": "svm-prod"}
            st["goal"] = {
                "title": "Bring SVM online",
                "objective": "Start svm-prod and restore the NFS protocol.",
            }
            ne._save(str(sid), entry)
        except Exception:
            pass
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_dellemc(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/dellemc")
    state._write_file(
        "/opt/dellemc/lab-state.json",
        '{"storage_pool":"degraded","volume":"unmapped","status":"broken"}\n',
    )
    state.services["unisphere"] = SimService(
        "unisphere", active="failed", enabled="enabled",
        description="Dell EMC Unisphere", loaded="loaded", sub_state="failed",
    )
    sid = getattr(state, "session_id", None)
    if sid:
        try:
            from apps.vmware_sim import dellemc_engine as de

            entry = de._ensure(str(sid), slug)
            st = entry["state"]
            st["broken"] = {"unmapped_volume": "0004", "pool_degraded": True}
            de._save(str(sid), entry)
        except Exception:
            pass
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_datacenter(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/datacenter")
    narrative = "cooling" if "cool" in slug else ("pdu" if "pdu" in slug else "racks")
    state._write_file(
        "/opt/datacenter/lab-state.json",
        f'{{"subsystem":"{narrative}","status":"alarm","dcim":"degraded"}}\n',
    )
    unit = "dcim-agent"
    if "pdu" in slug:
        unit = "pdu-monitor"
    elif "cool" in slug or "hvac" in slug:
        unit = "cooling-controller"
    elif "ups" in slug:
        unit = "ups-agent"
    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled",
        description=f"Datacenter {unit}", loaded="loaded", sub_state="failed",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_soc(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/soc")
    state._write_file(
        "/opt/soc/lab-state.json",
        '{"siem":"disconnected","sensor":"silent","status":"broken"}\n',
    )
    state.services["wazuh-agent"] = SimService(
        "wazuh-agent", active="failed", enabled="enabled",
        description="Wazuh SIEM agent", loaded="loaded", sub_state="failed",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_otel(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/otel")
    state._write_file(
        "/opt/otel/config.yaml",
        "receivers:\n  otlp:\n    protocols:\n      grpc:\n        endpoint: 0.0.0.0:4317\n"
        "exporters:\n  logging:\n    loglevel: debug\n"
        "service:\n  pipelines:\n    traces:\n      receivers: [otlp]\n"
        "      exporters: [broken_backend]\n",
    )
    state.services["otelcol"] = SimService(
        "otelcol", active="failed", enabled="enabled",
        description="OpenTelemetry Collector", loaded="loaded", sub_state="failed",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_service_mesh(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/service-mesh")
    state._write_file(
        "/opt/service-mesh/lab-state.json",
        '{"control_plane":"unhealthy","sidecar":"injection-failed","status":"broken"}\n',
    )
    unit = "istiod" if "istio" in slug or "mesh" in slug else "linkerd-destination"
    state.services[unit] = SimService(
        unit, active="failed", enabled="enabled",
        description="Service mesh control plane", loaded="loaded", sub_state="failed",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_commvault(state: Any, slug: str) -> bool:
    from .rhel_os import SimService

    state._mkdir("/opt/commvault")
    state._write_file(
        "/opt/commvault/lab-state.json",
        '{"media_agent":"offline","backup_set":"failed","status":"broken"}\n',
    )
    state.services["commvault"] = SimService(
        "commvault", active="failed", enabled="enabled",
        description="Commvault MediaAgent", loaded="loaded", sub_state="failed",
    )
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True


def _fault_ai_infra(state: Any, slug: str) -> bool:
    """AI infra academy: prefer GPU/operator narrative over nginx."""
    from .rhel_os import SimService

    if any(k in slug for k in ("gpu", "xid", "nvlink", "ecc", "hbm", "cuda")):
        return _fault_gpu(state, slug)

    state._mkdir("/opt/ai-infra")
    state._write_file(
        "/opt/ai-infra/lab-state.json",
        '{"device_plugin":"CrashLoopBackOff","dcgm":"down","status":"broken"}\n',
    )
    state.services["nvidia-device-plugin"] = SimService(
        "nvidia-device-plugin", active="failed", enabled="enabled",
        description="NVIDIA GPU device plugin", loaded="loaded", sub_state="failed",
    )
    state.gpu_healthy = False
    from .scenario_presets import _plant_broken_config_sentinel
    _plant_broken_config_sentinel(slug, state)
    return True
