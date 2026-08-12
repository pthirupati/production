"""
Complete in-memory Kubernetes simulator for training labs.
Replicates a realistic multi-namespace cluster state including unhealthy pods,
pending scheduling, ConfigMaps, Secrets, PVCs, RBAC, and more.
"""

from __future__ import annotations

import copy
import json
import random
import re
import time
from typing import Any

from django.core.cache import cache

from .k8s_v2_facades import apply_v2_action, ensure_v2

SESSION_TTL = 7200  # 2-hour TTL matching VMware sessions

# Sessions stored in Django cache (Redis in production) for multi-worker safety
# Key: "k8s_session:{session_id}"  Value: JSON-serialized session dict

# Wall-clock durations (seconds) for graceful lifecycle transitions. Kept short
# so a learner watches a drain / termination complete within one lab sitting.
# A node drain evicts its pods (graceful termination) before the node reports
# fully drained; a deleted pod's grace period elapses before it disappears.
POD_GRACE_SECONDS = 6        # default terminationGracePeriodSeconds feel
NODE_DRAIN_SECONDS = 12      # cordoned -> draining -> drained window


def _session_key(session_id: str) -> str:
    return f"k8s_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now() -> float:
    return time.time()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ago_iso(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))


def _event(message: str, reason: str = "Normal", involved_object: str = "", namespace: str = "default") -> dict:
    return {
        "time": _now_iso(),
        "message": message,
        "reason": reason,
        "involvedObject": involved_object,
        "namespace": namespace,
        "type": "Warning" if reason in ("BackOff", "Failed", "Killing", "Unhealthy", "FailedScheduling", "NodeNotReady") else "Normal",
    }


def _pod(
    name: str,
    namespace: str,
    labels: dict,
    phase: str = "Running",
    node: str = "node1",
    container_name: str = "",
    container_image: str = "",
    restart_count: int = 0,
    container_state: str = "running",
    reason: str = "",
    cpu_request: str = "100m",
    mem_request: str = "128Mi",
    cpu_limit: str = "500m",
    mem_limit: str = "512Mi",
    age_seconds: int = 86400,
) -> dict:
    ready = phase == "Running" and container_state == "running"
    return {
        "name": name,
        "namespace": namespace,
        "labels": labels,
        "phase": phase,
        "node": node if phase not in ("Pending",) else None,
        "podIP": f"10.244.{random.randint(0, 3)}.{random.randint(2, 250)}" if ready else None,
        "startTime": _ago_iso(age_seconds),
        "containers": [
            {
                "name": container_name or name.split("-")[0],
                "image": container_image or f"fixitlab/{container_name or name.split('-')[0]}:latest",
                "ready": ready,
                "restartCount": restart_count,
                "state": container_state,
                "reason": reason,
                "cpuRequest": cpu_request,
                "memRequest": mem_request,
                "cpuLimit": cpu_limit,
                "memLimit": mem_limit,
            }
        ],
        "conditions": [
            {"type": "PodScheduled", "status": "True" if phase != "Pending" else "False"},
            {"type": "Initialized", "status": "True" if phase != "Pending" else "False"},
            {"type": "ContainersReady", "status": "True" if ready else "False"},
            {"type": "Ready", "status": "True" if ready else "False"},
        ],
    }


def _deployment(
    name: str,
    namespace: str,
    replicas: int = 3,
    available: int = 3,
    ready: int = 3,
    image: str = "",
    labels: dict | None = None,
    cpu_request: str = "100m",
    mem_request: str = "128Mi",
    cpu_limit: str = "500m",
    mem_limit: str = "512Mi",
) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "replicas": replicas,
        "availableReplicas": available,
        "readyReplicas": ready,
        "updatedReplicas": replicas,
        "image": image or f"fixitlab/{name}:latest",
        "labels": labels or {"app": name},
        "selector": {"app": name},
        "strategy": "RollingUpdate",
        "maxSurge": 1,
        "maxUnavailable": 0,
        "minReadySeconds": 0,
        "revisionHistoryLimit": 10,
        "creationTimestamp": _ago_iso(random.randint(86400, 864000)),
        "resources": {
            "requests": {"cpu": cpu_request, "memory": mem_request},
            "limits": {"cpu": cpu_limit, "memory": mem_limit},
        },
    }


def _service(
    name: str,
    namespace: str,
    svc_type: str = "ClusterIP",
    port: int = 80,
    target_port: int = 8080,
    selector: dict | None = None,
    cluster_ip: str = "",
    node_port: int | None = None,
    external_ip: str = "",
) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "type": svc_type,
        "clusterIP": cluster_ip or f"10.96.{random.randint(0, 255)}.{random.randint(1, 254)}",
        "externalIP": external_ip or ("<none>" if svc_type == "ClusterIP" else ""),
        "ports": [
            {
                "port": port,
                "targetPort": target_port,
                "protocol": "TCP",
                "nodePort": node_port,
            }
        ],
        "selector": selector or {"app": name},
        "sessionAffinity": "None",
        "creationTimestamp": _ago_iso(random.randint(86400, 864000)),
    }


def _node(
    name: str,
    status: str = "Ready",
    roles: list | None = None,
    version: str = "v1.28.5",
    os: str = "linux",
    arch: str = "amd64",
    cpu_capacity: str = "4",
    mem_capacity: str = "8Gi",
    cpu_allocatable: str = "3900m",
    mem_allocatable: str = "7620Mi",
    cpu_requested: str = "1200m",
    mem_requested: str = "2048Mi",
    pod_count: int = 12,
    unschedulable: bool = False,
    age_seconds: int = 2592000,
    taints: list | None = None,
) -> dict:
    ready_cond = status == "Ready"
    return {
        "name": name,
        "status": status,
        "roles": roles or ["worker"],
        "version": version,
        "os": os,
        "arch": arch,
        "unschedulable": unschedulable,
        "taints": taints or [],
        "capacity": {"cpu": cpu_capacity, "memory": mem_capacity, "pods": "110"},
        "allocatable": {"cpu": cpu_allocatable, "memory": mem_allocatable, "pods": "110"},
        "requested": {"cpu": cpu_requested, "memory": mem_requested},
        "podCount": pod_count,
        "creationTimestamp": _ago_iso(age_seconds),
        "labels": {
            "kubernetes.io/hostname": name,
            "kubernetes.io/os": os,
            "kubernetes.io/arch": arch,
            "node-role.kubernetes.io/" + (roles[0] if roles else "worker"): "",
        },
        "conditions": [
            {"type": "MemoryPressure", "status": "False", "reason": "KubeletHasSufficientMemory"},
            {"type": "DiskPressure", "status": "False", "reason": "KubeletHasNoDiskPressure"},
            {"type": "PIDPressure", "status": "False", "reason": "KubeletHasSufficientPID"},
            {
                "type": "Ready",
                "status": "True" if ready_cond else "False",
                "reason": "KubeletReady" if ready_cond else "KubeletNotReady",
                "message": "kubelet is posting ready status" if ready_cond else "PLEG is not healthy",
            },
        ],
    }


def _configmap(name: str, namespace: str, data: dict) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "data": data,
        "creationTimestamp": _ago_iso(random.randint(3600, 864000)),
    }


def _secret(name: str, namespace: str, secret_type: str = "Opaque", keys: list | None = None,
            source: str = "manifest") -> dict:
    """A Secret as the API server reports it.

    `storageEncoding` models what an operator finds when they read the object
    straight out of etcd. Kubernetes stores Secret values base64-*encoded* by
    default, which is emphatically not encryption — `etcdctl get` returns
    `k8s\x00v1\x00Secret...` with the cleartext value sitting right there. The
    field only flips to "aescbc"/"kms" once an EncryptionConfiguration is wired
    into the API server AND the object is rewritten, which is why re-applying a
    manifest alone never changes it. `source` distinguishes a manifest-managed
    Secret from one materialised by an external secrets operator, whose value
    never lives in git or etcd in the first place.
    """
    return {
        "name": name,
        "namespace": namespace,
        "type": secret_type,
        "dataKeys": keys or [],
        "storageEncoding": "base64",
        "source": source,
        "creationTimestamp": _ago_iso(random.randint(3600, 864000)),
    }


def _pvc(
    name: str,
    namespace: str,
    status: str = "Bound",
    capacity: str = "10Gi",
    access_modes: list | None = None,
    storage_class: str = "standard",
    volume_name: str = "",
) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "status": status,
        "capacity": capacity,
        "accessModes": access_modes or ["ReadWriteOnce"],
        "storageClass": storage_class,
        "volumeName": volume_name or f"pvc-{name}-{random.randint(10000, 99999)}",
        "creationTimestamp": _ago_iso(random.randint(3600, 864000)),
    }


def _pv(
    name: str,
    capacity: str = "10Gi",
    access_modes: list | None = None,
    reclaim_policy: str = "Delete",
    status: str = "Bound",
    claim: str = "",
    storage_class: str = "standard",
) -> dict:
    return {
        "name": name,
        "capacity": capacity,
        "accessModes": access_modes or ["ReadWriteOnce"],
        "reclaimPolicy": reclaim_policy,
        "status": status,
        "claim": claim,
        "storageClass": storage_class,
        "creationTimestamp": _ago_iso(random.randint(3600, 864000)),
    }


def _role(name: str, namespace: str, rules: list) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "rules": rules,
        "creationTimestamp": _ago_iso(random.randint(3600, 864000)),
    }


def _role_binding(name: str, namespace: str, role_name: str, subjects: list) -> dict:
    return {
        "name": name,
        "namespace": namespace,
        "roleRef": {"kind": "Role", "name": role_name},
        "subjects": subjects,
        "creationTimestamp": _ago_iso(random.randint(3600, 864000)),
    }


def _base_cluster() -> dict:
    nodes = [
        _node("node1", status="Ready", roles=["control-plane", "master"], cpu_capacity="8", mem_capacity="16Gi",
              cpu_allocatable="7900m", mem_allocatable="15360Mi", cpu_requested="2400m",
              mem_requested="4096Mi", pod_count=18, age_seconds=5184000),
        _node("node2", status="Ready", roles=["worker"], cpu_capacity="4", mem_capacity="8Gi",
              cpu_requested="1800m", mem_requested="3072Mi", pod_count=14, age_seconds=5184000),
        _node("node3", status="NotReady", roles=["worker"], cpu_capacity="4", mem_capacity="8Gi",
              cpu_requested="0m", mem_requested="0Mi", pod_count=0, age_seconds=5184000),
    ]

    namespaces = [
        {"name": "default", "status": "Active", "labels": {}},
        {"name": "kube-system", "status": "Active", "labels": {"kubernetes.io/metadata.name": "kube-system"}},
        {"name": "production", "status": "Active", "labels": {"env": "production"}},
        {"name": "staging", "status": "Active", "labels": {"env": "staging"}},
        {"name": "monitoring", "status": "Active", "labels": {"app": "monitoring"}},
    ]

    deployments = [
        _deployment("nginx", "production", replicas=3, available=3, ready=3,
                    image="nginx:1.25.3", cpu_request="50m", mem_request="64Mi", cpu_limit="200m", mem_limit="256Mi"),
        _deployment("api", "production", replicas=5, available=5, ready=5,
                    image="fixitlab/api:v2.4.1", cpu_request="250m", mem_request="256Mi", cpu_limit="1000m", mem_limit="512Mi"),
        _deployment("frontend", "production", replicas=3, available=3, ready=3,
                    image="fixitlab/frontend:v1.8.0", cpu_request="100m", mem_request="128Mi", cpu_limit="500m", mem_limit="256Mi"),
        _deployment("db", "production", replicas=1, available=1, ready=1,
                    image="postgres:15.4", cpu_request="500m", mem_request="512Mi", cpu_limit="2000m", mem_limit="2Gi"),
        _deployment("redis", "production", replicas=2, available=1, ready=1,
                    image="redis:7.2", cpu_request="100m", mem_request="128Mi", cpu_limit="500m", mem_limit="512Mi"),
        _deployment("worker", "production", replicas=4, available=0, ready=0,
                    image="fixitlab/worker:v1.2.0", cpu_request="200m", mem_request="256Mi", cpu_limit="1000m", mem_limit="1Gi"),
        _deployment("metrics", "monitoring", replicas=1, available=1, ready=1,
                    image="prom/prometheus:v2.47.0", cpu_request="250m", mem_request="512Mi", cpu_limit="1000m", mem_limit="2Gi"),
        _deployment("gateway", "production", replicas=2, available=2, ready=2,
                    image="fixitlab/gateway:v3.0.1", cpu_request="200m", mem_request="256Mi", cpu_limit="1000m", mem_limit="1Gi"),
    ]

    pods = [
        # nginx pods — healthy
        _pod("nginx-7d5b6c4f9d-xk2jm", "production", {"app": "nginx"}, node="node1",
             container_name="nginx", container_image="nginx:1.25.3", age_seconds=86400),
        _pod("nginx-7d5b6c4f9d-rt8pn", "production", {"app": "nginx"}, node="node2",
             container_name="nginx", container_image="nginx:1.25.3", age_seconds=86400),
        _pod("nginx-7d5b6c4f9d-wq3lv", "production", {"app": "nginx"}, node="node1",
             container_name="nginx", container_image="nginx:1.25.3", age_seconds=86400),
        # api pods — healthy
        _pod("api-6b8f7d9c5a-mn4pk", "production", {"app": "api"}, node="node1",
             container_name="api", container_image="fixitlab/api:v2.4.1", age_seconds=43200),
        _pod("api-6b8f7d9c5a-kp9qr", "production", {"app": "api"}, node="node2",
             container_name="api", container_image="fixitlab/api:v2.4.1", age_seconds=43200),
        _pod("api-6b8f7d9c5a-jw2xs", "production", {"app": "api"}, node="node1",
             container_name="api", container_image="fixitlab/api:v2.4.1", age_seconds=43200),
        _pod("api-6b8f7d9c5a-vt7nh", "production", {"app": "api"}, node="node2",
             container_name="api", container_image="fixitlab/api:v2.4.1", age_seconds=43200),
        _pod("api-6b8f7d9c5a-zc5ml", "production", {"app": "api"}, node="node1",
             container_name="api", container_image="fixitlab/api:v2.4.1", age_seconds=43200),
        # frontend pods — healthy
        _pod("frontend-5f9c4b7d8e-hj6kw", "production", {"app": "frontend"}, node="node2",
             container_name="frontend", container_image="fixitlab/frontend:v1.8.0", age_seconds=21600),
        _pod("frontend-5f9c4b7d8e-yp1rs", "production", {"app": "frontend"}, node="node1",
             container_name="frontend", container_image="fixitlab/frontend:v1.8.0", age_seconds=21600),
        _pod("frontend-5f9c4b7d8e-bq4tl", "production", {"app": "frontend"}, node="node2",
             container_name="frontend", container_image="fixitlab/frontend:v1.8.0", age_seconds=21600),
        # db pod — healthy
        _pod("db-7c8d9e4f5b-qr3xp", "production", {"app": "db"}, node="node1",
             container_name="db", container_image="postgres:15.4",
             cpu_request="500m", mem_request="512Mi", cpu_limit="2000m", mem_limit="2Gi",
             age_seconds=259200),
        # redis pods — one CrashLoopBackOff
        _pod("redis-6d5c4b3a2e-mw8kj", "production", {"app": "redis"}, node="node2",
             container_name="redis", container_image="redis:7.2", age_seconds=7200),
        _pod("redis-6d5c4b3a2e-xn9pl", "production", {"app": "redis"},
             phase="Running", node="node2",
             container_name="redis", container_image="redis:7.2",
             restart_count=18, container_state="waiting", reason="CrashLoopBackOff", age_seconds=3600),
        # worker pods — all CrashLoopBackOff
        _pod("worker-9a8b7c6d5e-fk2lm", "production", {"app": "worker"},
             phase="Running", node="node1",
             container_name="worker", container_image="fixitlab/worker:v1.2.0",
             restart_count=25, container_state="waiting", reason="CrashLoopBackOff", age_seconds=1800),
        _pod("worker-9a8b7c6d5e-gt3np", "production", {"app": "worker"},
             phase="Running", node="node1",
             container_name="worker", container_image="fixitlab/worker:v1.2.0",
             restart_count=23, container_state="waiting", reason="CrashLoopBackOff", age_seconds=1800),
        _pod("worker-9a8b7c6d5e-hr4qk", "production", {"app": "worker"},
             phase="Running", node="node2",
             container_name="worker", container_image="fixitlab/worker:v1.2.0",
             restart_count=22, container_state="waiting", reason="CrashLoopBackOff", age_seconds=1800),
        _pod("worker-9a8b7c6d5e-jv5st", "production", {"app": "worker"},
             phase="Running", node="node2",
             container_name="worker", container_image="fixitlab/worker:v1.2.0",
             restart_count=20, container_state="waiting", reason="CrashLoopBackOff", age_seconds=1800),
        # gateway pods — healthy
        _pod("gateway-4e3f2a1b0c-wp6xn", "production", {"app": "gateway"}, node="node1",
             container_name="gateway", container_image="fixitlab/gateway:v3.0.1", age_seconds=14400),
        _pod("gateway-4e3f2a1b0c-ck7ym", "production", {"app": "gateway"}, node="node2",
             container_name="gateway", container_image="fixitlab/gateway:v3.0.1", age_seconds=14400),
        # metrics pod — healthy
        _pod("metrics-prometheus-0", "monitoring", {"app": "metrics"}, node="node1",
             container_name="prometheus", container_image="prom/prometheus:v2.47.0",
             cpu_request="250m", mem_request="512Mi", cpu_limit="1000m", mem_limit="2Gi",
             age_seconds=172800),
        # Pending pods (node3 NotReady — nothing can be scheduled there)
        _pod("api-6b8f7d9c5a-pnd01", "production", {"app": "api"},
             phase="Pending", node=None, container_name="api",
             container_image="fixitlab/api:v2.4.1", age_seconds=600),
        _pod("worker-pending-reschedule", "production", {"app": "worker"},
             phase="Pending", node=None, container_name="worker",
             container_image="fixitlab/worker:v1.2.0", age_seconds=900),
        # kube-system pods
        _pod("coredns-5d78c9d8c7-abcde", "kube-system", {"k8s-app": "kube-dns"}, node="node1",
             container_name="coredns", container_image="registry.k8s.io/coredns/coredns:v1.10.1",
             cpu_request="100m", mem_request="70Mi", age_seconds=5184000),
        _pod("coredns-5d78c9d8c7-fghij", "kube-system", {"k8s-app": "kube-dns"}, node="node1",
             container_name="coredns", container_image="registry.k8s.io/coredns/coredns:v1.10.1",
             cpu_request="100m", mem_request="70Mi", age_seconds=5184000),
        _pod("kube-proxy-node1", "kube-system", {"k8s-app": "kube-proxy"}, node="node1",
             container_name="kube-proxy", container_image="registry.k8s.io/kube-proxy:v1.28.5",
             age_seconds=5184000),
        _pod("kube-proxy-node2", "kube-system", {"k8s-app": "kube-proxy"}, node="node2",
             container_name="kube-proxy", container_image="registry.k8s.io/kube-proxy:v1.28.5",
             age_seconds=5184000),
    ]

    services = [
        _service("nginx", "production", svc_type="LoadBalancer", port=80, target_port=80,
                 cluster_ip="10.96.10.10", external_ip="203.0.113.10"),
        _service("api", "production", svc_type="ClusterIP", port=8080, target_port=8080,
                 cluster_ip="10.96.10.11"),
        _service("frontend", "production", svc_type="LoadBalancer", port=3000, target_port=3000,
                 cluster_ip="10.96.10.12", external_ip="203.0.113.11"),
        _service("db", "production", svc_type="ClusterIP", port=5432, target_port=5432,
                 cluster_ip="10.96.10.13"),
        _service("redis", "production", svc_type="ClusterIP", port=6379, target_port=6379,
                 cluster_ip="10.96.10.14"),
        _service("gateway", "production", svc_type="LoadBalancer", port=443, target_port=8443,
                 cluster_ip="10.96.10.15", external_ip="203.0.113.12", node_port=30443),
        _service("metrics", "monitoring", svc_type="ClusterIP", port=9090, target_port=9090,
                 cluster_ip="10.96.20.10"),
        _service("kubernetes", "default", svc_type="ClusterIP", port=443, target_port=6443,
                 cluster_ip="10.96.0.1"),
    ]

    configmaps = [
        _configmap("app-config", "production", {
            "APP_ENV": "production",
            "LOG_LEVEL": "info",
            "MAX_CONNECTIONS": "100",
            "CACHE_TTL": "300",
            "FEATURE_FLAG_NEW_UI": "true",
        }),
        _configmap("db-config", "production", {
            "POSTGRES_DB": "fixitlab",
            "POSTGRES_HOST": "db.production.svc.cluster.local",
            "POSTGRES_PORT": "5432",
            "POOL_SIZE": "20",
        }),
        _configmap("nginx-config", "production", {
            "nginx.conf": "worker_processes auto;\nevents { worker_connections 1024; }\nhttp { include /etc/nginx/conf.d/*.conf; }",
        }),
        _configmap("worker-config", "production", {
            "QUEUE_BACKEND": "redis",
            "REDIS_HOST": "redis.production.svc.cluster.local",
            "REDIS_PORT": "6379",
            "WORKER_CONCURRENCY": "4",
            "JOB_TIMEOUT": "300",
        }),
        _configmap("prometheus-config", "monitoring", {
            "prometheus.yml": "global:\n  scrape_interval: 15s\nscrape_configs:\n  - job_name: kubernetes\n    kubernetes_sd_configs:\n      - role: node\n",
        }),
        _configmap("kube-dns", "kube-system", {
            "Corefile": ".:53 {\n    errors\n    health\n    kubernetes cluster.local\n    forward . /etc/resolv.conf\n    cache 30\n}",
        }),
    ]

    secrets = [
        _secret("db-credentials", "production", secret_type="Opaque",
                 keys=["POSTGRES_USER", "POSTGRES_PASSWORD"]),
        _secret("api-tls", "production", secret_type="kubernetes.io/tls",
                 keys=["tls.crt", "tls.key"]),
        _secret("registry-pull-secret", "production", secret_type="kubernetes.io/dockerconfigjson",
                 keys=[".dockerconfigjson"]),
        _secret("redis-auth", "production", secret_type="Opaque",
                 keys=["REDIS_PASSWORD"]),
        _secret("gateway-jwt-secret", "production", secret_type="Opaque",
                 keys=["JWT_SECRET", "JWT_REFRESH_SECRET"]),
        _secret("default-token-xyz", "default", secret_type="kubernetes.io/service-account-token",
                 keys=["ca.crt", "namespace", "token"]),
    ]

    pvcs = [
        _pvc("db-data-pvc", "production", status="Bound", capacity="50Gi",
              access_modes=["ReadWriteOnce"], storage_class="fast-ssd"),
        _pvc("redis-data-pvc", "production", status="Bound", capacity="10Gi",
              access_modes=["ReadWriteOnce"], storage_class="standard"),
        _pvc("prometheus-data-pvc", "monitoring", status="Bound", capacity="100Gi",
              access_modes=["ReadWriteOnce"], storage_class="standard"),
        _pvc("worker-logs-pvc", "production", status="Pending",
              access_modes=["ReadWriteMany"], storage_class="nfs",
              volume_name=""),
        _pvc("backup-pvc", "production", status="Bound", capacity="200Gi",
              access_modes=["ReadWriteOnce"], storage_class="standard"),
    ]

    pvs = [
        _pv("pv-db-data", capacity="50Gi", access_modes=["ReadWriteOnce"],
             reclaim_policy="Retain", status="Bound",
             claim="production/db-data-pvc", storage_class="fast-ssd"),
        _pv("pv-redis", capacity="10Gi", access_modes=["ReadWriteOnce"],
             reclaim_policy="Delete", status="Bound",
             claim="production/redis-data-pvc", storage_class="standard"),
        _pv("pv-prometheus", capacity="100Gi", access_modes=["ReadWriteOnce"],
             reclaim_policy="Delete", status="Bound",
             claim="monitoring/prometheus-data-pvc", storage_class="standard"),
        _pv("pv-backup", capacity="200Gi", access_modes=["ReadWriteOnce"],
             reclaim_policy="Retain", status="Bound",
             claim="production/backup-pvc", storage_class="standard"),
        _pv("pv-released-old", capacity="20Gi", access_modes=["ReadWriteOnce"],
             reclaim_policy="Retain", status="Released",
             claim="", storage_class="standard"),
    ]

    roles = [
        _role("pod-reader", "production", [
            {"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list", "watch"]},
        ]),
        _role("deployment-manager", "production", [
            {"apiGroups": ["apps"], "resources": ["deployments", "replicasets"],
             "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"]},
        ]),
        _role("secret-reader", "production", [
            {"apiGroups": [""], "resources": ["secrets"], "verbs": ["get", "list"]},
        ]),
    ]

    role_bindings = [
        _role_binding("pod-reader-binding", "production", "pod-reader", [
            {"kind": "ServiceAccount", "name": "monitoring-sa", "namespace": "monitoring"},
        ]),
        _role_binding("deployment-manager-binding", "production", "deployment-manager", [
            {"kind": "User", "name": "deploy-bot", "apiGroup": "rbac.authorization.k8s.io"},
        ]),
    ]

    ingresses = [
        {
            "name": "production-ingress",
            "namespace": "production",
            "className": "nginx",
            "rules": [
                {"host": "app.fixitlab.io", "path": "/", "service": "frontend", "port": 3000},
                {"host": "api.fixitlab.io", "path": "/", "service": "api", "port": 8080},
            ],
            "tls": [{"hosts": ["app.fixitlab.io", "api.fixitlab.io"], "secretName": "api-tls"}],
            "creationTimestamp": _ago_iso(86400),
        }
    ]

    return {
        "cluster_version": "v1.28.5",
        "cluster_name": "fixitlab-prod",
        "api_server": "https://k8s.fixitlab.local:6443",
        "session": {"logged_in": False, "user": ""},
        "nodes": nodes,
        "namespaces": namespaces,
        "deployments": deployments,
        "pods": pods,
        "services": services,
        "configmaps": configmaps,
        "secrets": secrets,
        "pvcs": pvcs,
        "pvs": pvs,
        "roles": roles,
        "role_bindings": role_bindings,
        "ingresses": ingresses,
        # API server --encryption-provider-config. Default Kubernetes ships with
        # NO EncryptionConfiguration at all: `resources` is empty and every
        # Secret is written to etcd as the `identity` (plaintext) provider.
        "encryption_config": {"present": False, "resources": []},
        "external_secrets": [],
        "events": [],
        "validation": {"target_deployment": "worker", "require_available": 4},
    }


def _apply_scenario_preset(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    events = state["events"]

    # Checked before the "worker" substring branch below: this slug contains
    # neither, but keeping it first documents that preset matching is
    # first-wins on substrings and a new slug must not collide.
    if "secret-base64" in slug or "secret-encryption" in slug:
        # The learner's misconception is that `data:` being base64 means the
        # value is protected. Seed a Secret that a security review flagged and
        # leave the cluster otherwise healthy, so "all pods Running" cannot be
        # mistaken for a pass — the graded fact is at-rest encryption.
        secret = _find_secret(state, "db-credentials", "production")
        if secret:
            secret["storageEncoding"] = "base64"
            secret["source"] = "manifest"
        events.append(_event(
            "Audit finding SEC-4412: Secret production/db-credentials is stored unencrypted in etcd "
            "(base64 is encoding, not encryption)",
            reason="PolicyViolation", involved_object="db-credentials", namespace="production",
        ))
        events.append(_event(
            "No --encryption-provider-config is set on kube-apiserver; the identity provider is in use",
            reason="Warning", involved_object="kube-apiserver", namespace="kube-system",
        ))
        state["validation"] = {
            "require_secret_encrypted_at_rest": "db-credentials",
            "namespace": "production",
        }

    elif "crashloop" in slug or "worker" in slug:
        events.append(_event(
            "Back-off restarting failed container worker in pod worker-9a8b7c6d5e-fk2lm",
            reason="BackOff", involved_object="worker-9a8b7c6d5e-fk2lm", namespace="production",
        ))
        events.append(_event(
            "Error: failed to load configuration from ConfigMap worker-config: key REDIS_HOST not found",
            reason="Failed", involved_object="worker-9a8b7c6d5e-fk2lm", namespace="production",
        ))
        state["validation"] = {"target_deployment": "worker", "require_available": 4}

    elif "node-notready" in slug or "node3" in slug:
        for node in state["nodes"]:
            if node["name"] == "node3":
                node["status"] = "NotReady"
                node["conditions"][-1]["status"] = "False"
                node["conditions"][-1]["reason"] = "KubeletNotReady"
        events.append(_event(
            "Node node3 status is now: NodeNotReady",
            reason="NodeNotReady", involved_object="node3",
        ))
        state["validation"] = {"require_node_ready": "node3"}

    elif "pending" in slug or "scheduling" in slug:
        events.append(_event(
            "0/3 nodes are available: 1 node(s) had taint {node-role.kubernetes.io/control-plane: NoSchedule}, 1 Insufficient cpu, 1 node(s) were unschedulable.",
            reason="FailedScheduling", involved_object="api-6b8f7d9c5a-pnd01", namespace="production",
        ))
        state["validation"] = {"require_pod_running": "api-6b8f7d9c5a-pnd01"}

    elif "pvc-pending" in slug:
        events.append(_event(
            "waiting for first consumer to be created before binding",
            reason="WaitForFirstConsumer", involved_object="worker-logs-pvc", namespace="production",
        ))
        state["validation"] = {"require_pvc_bound": "worker-logs-pvc"}

    else:
        events.append(_event("Cluster inventory loaded", reason="Normal"))
        events.append(_event("2 nodes Ready, 1 node NotReady — check node3", reason="NodeNotReady", involved_object="node3"))
        events.append(_event("worker deployment has 0/4 pods available", reason="Unhealthy",
                              involved_object="worker", namespace="production"))


def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = _base_cluster()
        _apply_scenario_preset(state, scenario_slug)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state, "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    ensure_v2(entry["state"])
    # Advance graceful termination / node drain on read so the cluster reflects
    # wall-clock time even when no action has been taken since a drain started.
    _tick(entry["state"])
    _save_session(str(session_id), entry)
    state = copy.deepcopy(entry["state"])

    nodes_ready = sum(1 for n in state["nodes"] if n["status"] == "Ready")
    pods_running = sum(1 for p in state["pods"] if p["phase"] == "Running"
                       and all(c["state"] == "running" for c in p.get("containers", [])))
    pods_pending = sum(1 for p in state["pods"] if p["phase"] == "Pending")
    pods_terminating = sum(1 for p in state["pods"] if p.get("phase") == "Terminating")
    nodes_draining = sum(1 for n in state["nodes"] if n.get("drain_state") == "draining")
    pods_crashloop = sum(
        1 for p in state["pods"]
        if any(c.get("reason") == "CrashLoopBackOff" for c in p.get("containers", []))
    )
    deployments_healthy = sum(
        1 for d in state["deployments"]
        if d["readyReplicas"] == d["replicas"]
    )

    try:
        from apps.labs.provisioner.simulation.server_identity import sync_k8s_nodes
        sync_k8s_nodes(session_id, state.get("nodes") or [])
    except Exception:
        pass

    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "cluster": state,
        "summary": {
            "nodes_ready": nodes_ready,
            "nodes_total": len(state["nodes"]),
            "pods_running": pods_running,
            "pods_pending": pods_pending,
            "pods_terminating": pods_terminating,
            "pods_crashloop": pods_crashloop,
            "nodes_draining": nodes_draining,
            "pods_total": len(state["pods"]),
            "deployments_healthy": deployments_healthy,
            "deployments_total": len(state["deployments"]),
            "namespaces": len(state["namespaces"]),
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find_pod(state: dict, name: str, namespace: str = "") -> dict | None:
    for p in state["pods"]:
        if p["name"] == name and (not namespace or p["namespace"] == namespace):
            return p
    return None


def _find_deployment(state: dict, name: str, namespace: str = "") -> dict | None:
    for d in state["deployments"]:
        if d["name"] == name and (not namespace or d["namespace"] == namespace):
            return d
    return None


def _find_node(state: dict, name: str) -> dict | None:
    for n in state["nodes"]:
        if n["name"] == name:
            return n
    return None


def _find_configmap(state: dict, name: str, namespace: str = "") -> dict | None:
    for cm in state["configmaps"]:
        if cm["name"] == name and (not namespace or cm["namespace"] == namespace):
            return cm
    return None


def _find_secret(state: dict, name: str, namespace: str = "") -> dict | None:
    for s in state["secrets"]:
        if s["name"] == name and (not namespace or s["namespace"] == namespace):
            return s
    return None


def _find_pvc(state: dict, name: str, namespace: str = "") -> dict | None:
    for pvc in state["pvcs"]:
        if pvc["name"] == name and (not namespace or pvc["namespace"] == namespace):
            return pvc
    return None


def _find_namespace(state: dict, name: str) -> dict | None:
    for ns in state["namespaces"]:
        if ns["name"] == name:
            return ns
    return None


# ---------------------------------------------------------------------------
# Wall-clock lifecycle advance — node drain + graceful pod termination.
#
# Real `kubectl drain` cordons the node, then evicts its pods, which enter
# Terminating (respecting terminationGracePeriodSeconds) before disappearing;
# the node reads "draining" until the eviction completes, then "SchedulingDisabled".
# We model this on wall-clock so a maintenance scenario feels live: a pod marked
# Terminating at t0 keeps showing (with a Terminating phase) until its grace
# period elapses, then it is removed. A draining node flips to drained after all
# its evicted pods are gone.
#
# `_tick` is called on read / action / validate (like the baremetal engine).
# It only advances transient drain/termination bookkeeping and never alters what
# the validators inspect (node.status, pod.phase for a *named* pod that isn't
# being terminated, pvc.status, deployment.availableReplicas), so grading is
# unaffected.
# ---------------------------------------------------------------------------

def _tick(state: dict, now: float | None = None) -> bool:
    """Advance graceful termination + node drain by wall-clock. Returns True if
    anything changed."""
    now = _now() if now is None else now
    changed = False
    events = state.setdefault("events", [])

    # 1) Terminating pods whose grace period elapsed are removed ("Gone").
    survivors = []
    for p in state.get("pods", []):
        term_at = p.get("terminating_at")
        if term_at is not None and now >= float(term_at):
            events.append(_event(
                f"Deleted pod {p['name']} (graceful termination complete)",
                reason="Killing", involved_object=p["name"], namespace=p.get("namespace", "default")))
            changed = True
            continue  # drop it
        survivors.append(p)
    if len(survivors) != len(state.get("pods", [])):
        state["pods"] = survivors

    # 2) Draining nodes flip to drained once their evicted pods are gone AND the
    #    drain window has elapsed.
    for n in state.get("nodes", []):
        if n.get("drain_state") == "draining":
            drain_done_at = n.get("drain_done_at")
            remaining = [p for p in state.get("pods", [])
                         if p.get("node") == n["name"] and p.get("terminating_at") is not None]
            if not remaining and drain_done_at is not None and now >= float(drain_done_at):
                n["drain_state"] = "drained"
                n.pop("drain_done_at", None)
                events.append(_event(
                    f"Node {n['name']} drained — all pods evicted, ready for maintenance",
                    involved_object=n["name"]))
                changed = True
    return changed


# ---------------------------------------------------------------------------
# Action handler
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Kubernetes session not found"}
    state = entry["state"]
    # Advance graceful termination / drain before handling the action so the
    # decision is made against the up-to-date cluster state.
    _tick(state)
    events = state.setdefault("events", [])

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        events.append(_event("Signed in to Kubernetes console", involved_object="console"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Logged in"}

    # --- Node actions ---

    if action == "cordon_node":
        name = payload.get("node_name") or payload.get("name")
        node = _find_node(state, name)
        if not node:
            return {"ok": False, "error": f"Node '{name}' not found"}
        if node.get("unschedulable"):
            return {"ok": False, "error": f"Node '{name}' is already unschedulable"}
        node["unschedulable"] = True
        node["drain_state"] = "cordoned"
        taint = {"key": "node.kubernetes.io/unschedulable", "effect": "NoSchedule"}
        if taint not in node.get("taints", []):
            node.setdefault("taints", []).append(taint)
        events.append(_event(f"Node {name} cordoned", involved_object=name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"node/{name} cordoned"}

    if action == "drain_node":
        name = payload.get("node_name") or payload.get("name")
        node = _find_node(state, name)
        if not node:
            return {"ok": False, "error": f"Node '{name}' not found"}
        # Draining implies cordon; a real drain evicts pods gracefully.
        node["unschedulable"] = True
        taint = {"key": "node.kubernetes.io/unschedulable", "effect": "NoSchedule"}
        if taint not in node.get("taints", []):
            node.setdefault("taints", []).append(taint)
        now = _now()
        # Mark this node's non-daemonset pods Terminating; they leave over the
        # grace period, then the node reports drained (see _tick).
        evicted = 0
        for p in state.get("pods", []):
            if p.get("node") != name:
                continue
            # kube-proxy / daemonset-style pods are not evicted by drain.
            if p.get("labels", {}).get("k8s-app") in ("kube-proxy",):
                continue
            if p.get("terminating_at") is not None:
                continue
            p["phase"] = "Terminating"
            p["terminating_at"] = now + POD_GRACE_SECONDS
            for c in p.get("containers", []):
                c["ready"] = False
            evicted += 1
            events.append(_event(
                f"Evicting pod {p['name']}", reason="Killing",
                involved_object=p["name"], namespace=p.get("namespace", "default")))
        node["drain_state"] = "draining"
        node["drain_done_at"] = now + NODE_DRAIN_SECONDS
        events.append(_event(
            f"Node {name} cordoned, evicting {evicted} pod(s)", involved_object=name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"node/{name} cordoned, {evicted} pod(s) evicting"}

    if action == "uncordon_node":
        name = payload.get("node_name") or payload.get("name")
        node = _find_node(state, name)
        if not node:
            return {"ok": False, "error": f"Node '{name}' not found"}
        node["unschedulable"] = False
        node["drain_state"] = None
        node.pop("drain_done_at", None)
        node["taints"] = [t for t in node.get("taints", [])
                          if t.get("key") != "node.kubernetes.io/unschedulable"]
        if node["status"] == "NotReady":
            node["status"] = "Ready"
            node["conditions"][-1]["status"] = "True"
            node["conditions"][-1]["reason"] = "KubeletReady"
        events.append(_event(f"Node {name} uncordoned", involved_object=name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"node/{name} uncordoned"}

    # --- Pod actions ---

    if action == "delete_pod":
        name = payload.get("pod_name") or payload.get("name")
        namespace = payload.get("namespace", "")
        pod = _find_pod(state, name, namespace)
        if not pod:
            return {"ok": False, "error": f"Pod '{name}' not found"}
        ns = pod["namespace"]
        dep_name = pod["labels"].get("app")
        state["pods"] = [p for p in state["pods"] if p["name"] != name]
        events.append(_event(f"Killing container {name}", reason="Killing",
                              involved_object=name, namespace=ns))
        # Simulate deployment re-creating pod
        if dep_name:
            dep = _find_deployment(state, dep_name, ns)
            if dep:
                new_suffix = f"{random.randint(10000, 99999)}"
                new_pod = _pod(
                    f"{dep_name}-rescheduled-{new_suffix}", ns, {"app": dep_name},
                    node="node1",
                    container_name=dep_name,
                    container_image=dep.get("image", f"fixitlab/{dep_name}:latest"),
                    age_seconds=5,
                )
                state["pods"].append(new_pod)
                events.append(_event(f"Created pod {new_pod['name']} (rescheduled)",
                                      involved_object=new_pod["name"], namespace=ns))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"pod/{name} deleted"}

    # --- Deployment actions ---

    if action == "scale_deployment":
        name = payload.get("deployment") or payload.get("name")
        namespace = payload.get("namespace", "production")
        replicas = payload.get("replicas")
        if replicas is None:
            return {"ok": False, "error": "replicas is required"}
        replicas = max(0, int(replicas))
        dep = _find_deployment(state, name, namespace)
        if not dep:
            return {"ok": False, "error": f"Deployment '{name}' not found in namespace '{namespace}'"}
        old_replicas = dep["replicas"]
        dep["replicas"] = replicas
        dep["availableReplicas"] = replicas
        dep["readyReplicas"] = replicas
        dep["updatedReplicas"] = replicas
        # Adjust pods to match
        existing = [p for p in state["pods"] if p["labels"].get("app") == name and p["namespace"] == namespace]
        if replicas > old_replicas:
            for i in range(replicas - old_replicas):
                new_pod = _pod(
                    f"{name}-scaled-{random.randint(10000, 99999)}", namespace, {"app": name},
                    node="node1" if i % 2 == 0 else "node2",
                    container_name=name,
                    container_image=dep.get("image", f"fixitlab/{name}:latest"),
                    age_seconds=3,
                )
                state["pods"].append(new_pod)
        elif replicas < old_replicas:
            to_remove = old_replicas - replicas
            remove_names = [p["name"] for p in existing[:to_remove]]
            state["pods"] = [p for p in state["pods"] if p["name"] not in remove_names]
        events.append(_event(
            f"Scaled deployment/{name} from {old_replicas} to {replicas}",
            involved_object=name, namespace=namespace,
        ))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"deployment.apps/{name} scaled"}

    if action == "delete_deployment":
        name = payload.get("deployment") or payload.get("name")
        namespace = payload.get("namespace", "production")
        dep = _find_deployment(state, name, namespace)
        if not dep:
            return {"ok": False, "error": f"Deployment '{name}' not found"}
        state["deployments"] = [d for d in state["deployments"] if not (d["name"] == name and d["namespace"] == namespace)]
        state["pods"] = [p for p in state["pods"] if not (p["labels"].get("app") == name and p["namespace"] == namespace)]
        events.append(_event(f"Deleted deployment/{name}", involved_object=name, namespace=namespace))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"deployment.apps/{name} deleted"}

    if action in ("create_deployment", "apply_deployment"):
        name = (payload.get("name") or payload.get("deployment") or f"dep-{random.randint(1000, 9999)}").strip()
        namespace = payload.get("namespace") or "production"
        if _find_deployment(state, name, namespace):
            return {"ok": False, "error": f"Deployment '{name}' already exists in namespace '{namespace}'"}
        replicas = max(0, int(payload.get("replicas") or 1))
        image = payload.get("image") or f"fixitlab/{name}:latest"
        dep = _deployment(name, namespace, replicas=replicas, available=replicas, ready=replicas, image=image)
        state.setdefault("deployments", []).append(dep)
        for i in range(replicas):
            state.setdefault("pods", []).append(_pod(
                f"{name}-{random.randint(10000, 99999)}", namespace, {"app": name},
                node="node1" if i % 2 == 0 else "node2",
                container_name=name,
                container_image=image,
                age_seconds=2,
            ))
        events.append(_event(f"Created deployment/{name}", involved_object=name, namespace=namespace))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"deployment.apps/{name} created", "deployment": dep}

    if action == "restart_deployment":
        name = payload.get("deployment") or payload.get("name")
        namespace = payload.get("namespace", "production")
        dep = _find_deployment(state, name, namespace)
        if not dep:
            return {"ok": False, "error": f"Deployment '{name}' not found"}
        # Replace existing pods with fresh healthy ones
        existing = [p for p in state["pods"] if p["labels"].get("app") == name and p["namespace"] == namespace]
        state["pods"] = [p for p in state["pods"] if not (p["labels"].get("app") == name and p["namespace"] == namespace)]
        for i in range(dep["replicas"]):
            new_pod = _pod(
                f"{name}-restart-{random.randint(10000, 99999)}", namespace, {"app": name},
                node="node1" if i % 2 == 0 else "node2",
                container_name=name,
                container_image=dep.get("image", f"fixitlab/{name}:latest"),
                restart_count=0,
                container_state="running",
                reason="",
                age_seconds=2,
            )
            state["pods"].append(new_pod)
        dep["availableReplicas"] = dep["replicas"]
        dep["readyReplicas"] = dep["replicas"]
        events.append(_event(f"Restarted deployment/{name} (rolling restart)", involved_object=name, namespace=namespace))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"deployment.apps/{name} restarted"}

    # --- ConfigMap / Secret ---

    if action == "apply_configmap":
        name = payload.get("name")
        namespace = payload.get("namespace", "production")
        data = payload.get("data") or {}
        if not name:
            return {"ok": False, "error": "ConfigMap name is required"}
        cm = _find_configmap(state, name, namespace)
        if cm:
            cm["data"].update(data)
            events.append(_event(f"Updated ConfigMap {name}", involved_object=name, namespace=namespace))
        else:
            state["configmaps"].append(_configmap(name, namespace, data))
            events.append(_event(f"Created ConfigMap {name}", involved_object=name, namespace=namespace))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"configmap/{name} applied"}

    if action == "apply_secret":
        name = payload.get("name")
        namespace = payload.get("namespace", "production")
        keys = payload.get("keys") or []
        secret_type = payload.get("type", "Opaque")
        if not name:
            return {"ok": False, "error": "Secret name is required"}
        existing = _find_secret(state, name, namespace)
        if existing:
            if keys:
                existing["dataKeys"] = list(set(existing["dataKeys"]) | set(keys))
            events.append(_event(f"Updated Secret {name}", involved_object=name, namespace=namespace))
        else:
            state["secrets"].append(_secret(name, namespace, secret_type=secret_type, keys=keys))
            events.append(_event(f"Created Secret {name}", involved_object=name, namespace=namespace))
        # Deliberately does NOT touch storageEncoding. Re-applying a manifest —
        # even with a freshly base64'd value — cannot change how the API server
        # serialises the object into etcd. Only an EncryptionConfiguration (plus
        # a rewrite) or moving the value out to an external store does that.
        # Encoding the value harder is the exact misconception these labs
        # correct, so it must not be rewarded here.
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"secret/{name} applied"}

    if action == "apply_encryption_config":
        # Models writing /etc/kubernetes/enc/enc.yaml and restarting kube-apiserver
        # with --encryption-provider-config. `identity` is the no-op provider: a
        # config that lists it first encrypts nothing, which is a real and common
        # misconfiguration, so we accept the config but keep the cluster failing.
        resources = payload.get("resources") or []
        providers = [str(p).lower() for p in (payload.get("providers") or [])]
        if not resources:
            resources = ["secrets"] if providers else []
        if not providers:
            return {"ok": False, "error": "encryption config requires at least one provider (aescbc, aesgcm, secretbox, or kms)"}
        state["encryption_config"] = {"present": True, "resources": list(resources), "providers": providers}
        first = providers[0]
        if first == "identity":
            events.append(_event(
                "EncryptionConfiguration applied but 'identity' is listed first — writes remain unencrypted",
                reason="Warning", involved_object="kube-apiserver", namespace="kube-system",
            ))
            _save_session(str(session_id), entry)
            return {"ok": True, "message": "encryption config applied (identity first — Secrets still stored in plaintext)"}
        # Applying the config only affects objects written *after* the restart, so
        # a real operator must follow with `kubectl get secrets -A -o json |
        # kubectl replace -f -`. We model that as an explicit rewrite action.
        events.append(_event(
            f"kube-apiserver restarted with --encryption-provider-config (provider: {first})",
            reason="Normal", involved_object="kube-apiserver", namespace="kube-system",
        ))
        events.append(_event(
            "Existing Secrets are still stored with the old encoding until they are rewritten",
            reason="Warning", involved_object="kube-apiserver", namespace="kube-system",
        ))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"encryption config applied (provider: {first}); rewrite existing Secrets to re-encrypt them"}

    if action == "rewrite_secrets":
        # `kubectl get secrets --all-namespaces -o json | kubectl replace -f -`
        enc = state.get("encryption_config") or {}
        providers = [str(p).lower() for p in (enc.get("providers") or [])]
        if not enc.get("present") or not providers or providers[0] == "identity":
            return {"ok": False, "error": "no active encryption provider — rewriting Secrets would re-store them in plaintext"}
        if "secrets" not in [str(r).lower() for r in (enc.get("resources") or [])]:
            return {"ok": False, "error": "encryption config does not cover the 'secrets' resource"}
        namespace = payload.get("namespace", "")
        name = payload.get("name", "")
        rewritten = 0
        for sec in state["secrets"]:
            if namespace and sec["namespace"] != namespace:
                continue
            if name and sec["name"] != name:
                continue
            if sec.get("source") == "external-secret":
                continue
            sec["storageEncoding"] = providers[0]
            rewritten += 1
        events.append(_event(
            f"Rewrote {rewritten} Secret(s); now stored with the {providers[0]} provider",
            reason="Normal", involved_object="kube-apiserver", namespace="kube-system",
        ))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{rewritten} secret(s) re-encrypted with {providers[0]}"}

    if action == "apply_external_secret":
        # The other legitimate remediation: External Secrets Operator syncs the
        # value from a real vault, so the cleartext never lives in git or etcd.
        name = payload.get("name")
        namespace = payload.get("namespace", "production")
        store = payload.get("secret_store") or payload.get("store") or ""
        remote_key = payload.get("remote_key") or payload.get("remoteRef") or ""
        if not name:
            return {"ok": False, "error": "ExternalSecret name is required"}
        if not store:
            return {"ok": False, "error": "ExternalSecret requires a secretStoreRef (e.g. vault-backend)"}
        if not remote_key:
            return {"ok": False, "error": "ExternalSecret requires a remoteRef key in the external store"}
        target = payload.get("target") or name
        state.setdefault("external_secrets", []).append({
            "name": name,
            "namespace": namespace,
            "secretStoreRef": store,
            "remoteRef": remote_key,
            "target": target,
            "creationTimestamp": _now_iso(),
        })
        secret = _find_secret(state, target, namespace)
        if secret:
            secret["source"] = "external-secret"
            secret["externalStore"] = store
        else:
            state["secrets"].append(_secret(
                target, namespace, keys=[remote_key], source="external-secret",
            ))
            _find_secret(state, target, namespace)["externalStore"] = store
        events.append(_event(
            f"ExternalSecret {name} synced target Secret {target} from {store}",
            reason="Normal", involved_object=name, namespace=namespace,
        ))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"externalsecret/{name} applied; {target} now sourced from {store}"}

    # --- Namespace ---

    if action == "create_namespace":
        name = payload.get("name") or payload.get("namespace")
        if not name:
            return {"ok": False, "error": "Namespace name is required"}
        if _find_namespace(state, name):
            return {"ok": False, "error": f"Namespace '{name}' already exists"}
        state["namespaces"].append({"name": name, "status": "Active", "labels": payload.get("labels") or {}})
        events.append(_event(f"Created namespace {name}", involved_object=name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"namespace/{name} created"}

    if action == "delete_namespace":
        name = payload.get("name") or payload.get("namespace")
        if name in ("default", "kube-system"):
            return {"ok": False, "error": f"Cannot delete protected namespace '{name}'"}
        ns = _find_namespace(state, name)
        if not ns:
            return {"ok": False, "error": f"Namespace '{name}' not found"}
        state["namespaces"] = [n for n in state["namespaces"] if n["name"] != name]
        state["pods"] = [p for p in state["pods"] if p["namespace"] != name]
        state["deployments"] = [d for d in state["deployments"] if d["namespace"] != name]
        state["services"] = [s for s in state["services"] if s["namespace"] != name]
        events.append(_event(f"Deleted namespace {name}", involved_object=name))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"namespace/{name} deleted"}

    # --- PVC ---

    if action == "bind_pvc":
        name = payload.get("pvc_name") or payload.get("name")
        namespace = payload.get("namespace", "production")
        pvc = _find_pvc(state, name, namespace)
        if not pvc:
            return {"ok": False, "error": f"PVC '{name}' not found"}
        pvc["status"] = "Bound"
        pvc["volumeName"] = payload.get("volume_name") or f"pvc-{name}-{random.randint(10000, 99999)}"
        events.append(_event(f"PVC {name} bound", involved_object=name, namespace=namespace))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"persistentvolumeclaim/{name} bound"}

    # --- Generic patch ---

    if action == "patch_resource":
        kind = (payload.get("kind") or "").lower()
        name = payload.get("name") or ""
        namespace = payload.get("namespace", "")
        patch = payload.get("patch") or {}
        target = None
        if kind == "deployment":
            target = _find_deployment(state, name, namespace)
        elif kind == "configmap":
            target = _find_configmap(state, name, namespace)
        elif kind == "pod":
            target = _find_pod(state, name, namespace)
        elif kind == "node":
            target = _find_node(state, name)
        if target is None:
            return {"ok": False, "error": f"{kind}/{name} not found"}
        target.update(patch)
        events.append(_event(f"Patched {kind}/{name}", involved_object=name, namespace=namespace))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{kind}/{name} patched"}

    if action in ("kubernetes_http", "k8s_http", "http_api"):
        url = payload.get("url") or payload.get("path") or ""
        status, body = kubernetes_http_api(url, state)
        return {"ok": status < 400, "status": status, "body": body}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _save_session(str(session_id), entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Kubernetes HTTP API (Y3 teaching surface — curl to apiserver)
# ---------------------------------------------------------------------------

def _pod_to_k8s_object(p: dict) -> dict:
    ns = p.get("namespace") or "default"
    name = p.get("name") or "pod"
    containers = []
    for c in p.get("containers") or []:
        containers.append({
            "name": c.get("name") or name,
            "image": c.get("image") or "fixitlab/app:latest",
            "ready": bool(c.get("ready")),
            "restartCount": int(c.get("restartCount") or 0),
            "state": {str(c.get("state") or "running"): {}},
        })
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": ns,
            "labels": dict(p.get("labels") or {}),
            "creationTimestamp": p.get("startTime"),
        },
        "spec": {
            "nodeName": p.get("node"),
            "containers": [
                {"name": c.get("name"), "image": c.get("image")}
                for c in (p.get("containers") or [])
            ],
        },
        "status": {
            "phase": p.get("phase") or "Unknown",
            "podIP": p.get("podIP"),
            "containerStatuses": containers,
            "conditions": list(p.get("conditions") or []),
        },
    }


def _deployment_to_k8s_object(d: dict) -> dict:
    ns = d.get("namespace") or "default"
    name = d.get("name") or "deploy"
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": name,
            "namespace": ns,
            "labels": dict(d.get("labels") or {}),
            "creationTimestamp": d.get("creationTimestamp"),
        },
        "spec": {
            "replicas": int(d.get("replicas") or 0),
            "selector": {"matchLabels": dict(d.get("selector") or d.get("labels") or {})},
            "template": {
                "metadata": {"labels": dict(d.get("labels") or {})},
                "spec": {
                    "containers": [{
                        "name": name,
                        "image": d.get("image") or f"fixitlab/{name}:latest",
                    }],
                },
            },
        },
        "status": {
            "replicas": int(d.get("replicas") or 0),
            "availableReplicas": int(d.get("availableReplicas") or 0),
            "readyReplicas": int(d.get("readyReplicas") or 0),
            "updatedReplicas": int(d.get("updatedReplicas") or 0),
        },
    }


def kubernetes_http_api(url_or_path: str, state: dict | None = None) -> tuple[int, dict]:
    """Kubernetes apiserver HTTP surface for curl teaching labs (audit Y3).

    Routes ``/api/v1/pods`` and ``/apis/apps/v1/deployments`` (namespaced and
    cluster-scoped) against the in-session cluster. Returns ``(http_status, body)``.
    """
    from urllib.parse import parse_qs, urlparse

    state = state or {}
    raw = (url_or_path or "").strip()
    if not raw:
        return 400, {"kind": "Status", "apiVersion": "v1", "status": "Failure",
                     "message": "empty URL", "code": 400}

    if "://" in raw:
        parsed = urlparse(raw)
        path = parsed.path or "/"
        qs = parse_qs(parsed.query)
    elif "?" in raw:
        path, q = raw.split("?", 1)
        qs = parse_qs(q)
    else:
        path, qs = raw, {}

    norm = path.rstrip("/") or "/"
    label_selector = (qs.get("labelSelector") or [""])[0]

    def _labels_match(labels: dict) -> bool:
        if not label_selector:
            return True
        want = {}
        for part in label_selector.split(","):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                want[k.strip()] = v.strip()
        return all(labels.get(k) == v for k, v in want.items())

    # /api/v1/namespaces/{ns}/pods[/{name}]
    m = re.match(r"^/api/v1/namespaces/([^/]+)/pods(?:/([^/]+))?$", norm)
    if m:
        ns, name = m.group(1), m.group(2)
        pods = [p for p in state.get("pods") or [] if p.get("namespace") == ns]
        if name:
            pod = next((p for p in pods if p.get("name") == name), None)
            if not pod:
                return 404, {
                    "kind": "Status", "apiVersion": "v1", "status": "Failure",
                    "message": f'pods "{name}" not found', "reason": "NotFound", "code": 404,
                }
            return 200, _pod_to_k8s_object(pod)
        items = [_pod_to_k8s_object(p) for p in pods if _labels_match(p.get("labels") or {})]
        return 200, {"kind": "PodList", "apiVersion": "v1", "items": items}

    # /api/v1/pods (all namespaces)
    if norm == "/api/v1/pods":
        items = [
            _pod_to_k8s_object(p) for p in (state.get("pods") or [])
            if _labels_match(p.get("labels") or {})
        ]
        return 200, {"kind": "PodList", "apiVersion": "v1", "items": items}

    # /apis/apps/v1/namespaces/{ns}/deployments[/{name}]
    m = re.match(r"^/apis/apps/v1/namespaces/([^/]+)/deployments(?:/([^/]+))?$", norm)
    if m:
        ns, name = m.group(1), m.group(2)
        deps = [d for d in state.get("deployments") or [] if d.get("namespace") == ns]
        if name:
            dep = next((d for d in deps if d.get("name") == name), None)
            if not dep:
                return 404, {
                    "kind": "Status", "apiVersion": "v1", "status": "Failure",
                    "message": f'deployments.apps "{name}" not found', "reason": "NotFound", "code": 404,
                }
            return 200, _deployment_to_k8s_object(dep)
        items = [_deployment_to_k8s_object(d) for d in deps if _labels_match(d.get("labels") or {})]
        return 200, {"kind": "DeploymentList", "apiVersion": "apps/v1", "items": items}

    if norm == "/apis/apps/v1/deployments":
        items = [
            _deployment_to_k8s_object(d) for d in (state.get("deployments") or [])
            if _labels_match(d.get("labels") or {})
        ]
        return 200, {"kind": "DeploymentList", "apiVersion": "apps/v1", "items": items}

    if norm in ("/api", "/apis", "/healthz", "/readyz", "/livez"):
        return 200, {"kind": "Status", "apiVersion": "v1", "status": "Success", "code": 200}

    return 404, {
        "kind": "Status", "apiVersion": "v1", "status": "Failure",
        "message": f"Kubernetes API: unknown path {path}", "reason": "NotFound", "code": 404,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_k8s_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    # Advance the wall-clock lifecycle before grading so a drain/termination that
    # completed between requests is scored against its settled state. This never
    # changes the validator's inspected fields for graded targets — only transient
    # drain/termination bookkeeping — so the grading contract is preserved.
    if _tick(state):
        _save_session(str(session_id), entry)
    rules = state.get("validation") or {}

    if rules.get("require_node_ready"):
        node_name = rules["require_node_ready"]
        node = _find_node(state, node_name)
        if not node or node.get("status") != "Ready":
            return False, f"Node {node_name} must be Ready"
        return True, f"Node {node_name} is Ready — validation passed"

    if rules.get("require_pod_running"):
        pod_name = rules["require_pod_running"]
        pod = _find_pod(state, pod_name)
        if not pod or pod.get("phase") != "Running":
            return False, f"Pod {pod_name} must be Running"
        if any(c.get("state") != "running" for c in pod.get("containers", [])):
            return False, f"Pod {pod_name} containers are not ready"
        return True, f"Pod {pod_name} is Running — validation passed"

    if rules.get("require_secret_encrypted_at_rest"):
        # Fail-CLOSED on purpose. The naive "fix" for this lab is to re-base64
        # the value or re-apply the Secret manifest, which changes nothing about
        # how etcd stores it — so we never look at the Secret's *encoding* or at
        # its mere existence. Only two things count, and both are structural:
        # an active non-identity encryption provider that the object was
        # rewritten under, or an ExternalSecret that moves the value out of etcd
        # entirely.
        secret_name = rules["require_secret_encrypted_at_rest"]
        namespace = rules.get("namespace", "production")
        secret = _find_secret(state, secret_name, namespace)
        if not secret:
            return False, f"Secret {namespace}/{secret_name} not found — do not delete it, protect it"

        if secret.get("source") == "external-secret" and secret.get("externalStore"):
            return True, (
                f"Secret {namespace}/{secret_name} is sourced from external store "
                f"'{secret['externalStore']}' — the value no longer lives in etcd or git"
            )

        enc = state.get("encryption_config") or {}
        providers = [str(p).lower() for p in (enc.get("providers") or [])]
        if not enc.get("present") or not providers:
            return False, (
                "No EncryptionConfiguration on the API server — Secrets are still stored with the "
                "identity provider. base64 in the manifest is encoding, not encryption."
            )
        if providers[0] == "identity":
            return False, (
                "'identity' is listed first in the EncryptionConfiguration, so writes are still "
                "plaintext. Put a real provider (aescbc/aesgcm/secretbox/kms) first."
            )
        if "secrets" not in [str(r).lower() for r in (enc.get("resources") or [])]:
            return False, "EncryptionConfiguration does not cover the 'secrets' resource"
        if secret.get("storageEncoding", "base64") == "base64":
            return False, (
                f"Secret {namespace}/{secret_name} predates the encryption config and is still stored "
                "in plaintext. Rewrite existing Secrets so they are re-encrypted."
            )
        return True, (
            f"Secret {namespace}/{secret_name} is encrypted at rest with the "
            f"{secret['storageEncoding']} provider — validation passed"
        )

    if rules.get("require_pvc_bound"):
        pvc_name = rules["require_pvc_bound"]
        pvc = _find_pvc(state, pvc_name)
        if not pvc or pvc.get("status") != "Bound":
            return False, f"PVC {pvc_name} must be Bound"
        return True, f"PVC {pvc_name} is Bound — validation passed"

    # Default: check deployment replicas
    dep_name = rules.get("target_deployment", "worker")
    required_available = rules.get("require_available", 1)
    namespace = rules.get("namespace", "production")
    dep = _find_deployment(state, dep_name, namespace)
    if not dep:
        return False, f"Deployment {dep_name} not found in {namespace}"
    if dep.get("availableReplicas", 0) < required_available:
        return False, f"{dep_name} needs {required_available} available replicas (currently {dep.get('availableReplicas', 0)})"
    return True, f"{dep_name} has {dep['availableReplicas']} available replicas — validation passed"
