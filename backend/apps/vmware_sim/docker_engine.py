"""
Complete in-memory Docker daemon simulator for training labs.
Replicates a realistic Docker host state including containers, images,
networks, volumes, and docker-compose service groups.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import time
from typing import Any

from django.core.cache import cache

from .docker_v2_facades import apply_v2_action, ensure_v2

SESSION_TTL = 7200  # 2-hour TTL matching VMware/K8s sessions

# Sessions stored in Django cache (Redis in production) for multi-worker safety
# Key: "docker_session:{session_id}"  Value: JSON-serialized session dict


def _session_key(session_id: str) -> str:
    return f"docker_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _ago_iso(seconds: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - seconds))


def _ago_human(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} seconds ago"
    if seconds < 3600:
        return f"{seconds // 60} minutes ago"
    if seconds < 86400:
        return f"{seconds // 3600} hours ago"
    return f"{seconds // 86400} days ago"


def _short_id() -> str:
    chars = "abcdef0123456789"
    return "".join(random.choice(chars) for _ in range(12))


def _container(
    name: str,
    image: str,
    status: str = "running",
    state: str = "running",
    exit_code: int = 0,
    ports: list | None = None,
    volumes: list | None = None,
    env: list | None = None,
    network: str = "bridge",
    cpu_pct: float = 0.0,
    mem_usage_mb: float = 0.0,
    mem_limit_mb: float = 512.0,
    restart_policy: str = "unless-stopped",
    restart_count: int = 0,
    age_seconds: int = 86400,
    compose_service: str = "",
    compose_project: str = "",
    labels: dict | None = None,
) -> dict:
    container_id = _short_id()
    return {
        "id": container_id,
        "name": f"/{name}",
        "shortName": name,
        "image": image,
        "imageId": f"sha256:{_short_id()}{_short_id()}{_short_id()}{_short_id()}",
        "status": status,
        "state": state,
        "exitCode": exit_code,
        "created": _ago_iso(age_seconds),
        "started": _ago_iso(age_seconds - 5) if state == "running" else None,
        "finished": _ago_iso(age_seconds - 10) if state not in ("running", "created") else None,
        "uptime": _ago_human(age_seconds) if state == "running" else None,
        "ports": ports or [],
        "volumes": volumes or [],
        "env": env or [],
        "network": network,
        "networkMode": network,
        "ipAddress": f"172.17.0.{random.randint(2, 250)}" if state == "running" else None,
        "cpuPercent": round(cpu_pct, 2) if state == "running" else 0.0,
        "memUsageMb": round(mem_usage_mb, 1) if state == "running" else 0.0,
        "memLimitMb": mem_limit_mb,
        "memPercent": round(mem_usage_mb / mem_limit_mb * 100, 1) if state == "running" and mem_limit_mb else 0.0,
        "restartPolicy": restart_policy,
        "restartCount": restart_count,
        "composeService": compose_service,
        "composeProject": compose_project,
        "labels": labels or {},
        "platform": "linux/amd64",
    }


def _image(
    repo: str,
    tag: str = "latest",
    size_mb: int = 150,
    age_seconds: int = 172800,
    dangling: bool = False,
) -> dict:
    img_id = f"sha256:{_short_id()}{_short_id()}{_short_id()}{_short_id()}"
    return {
        "id": img_id,
        "repository": repo if not dangling else "<none>",
        "tag": tag if not dangling else "<none>",
        "repoTag": f"{repo}:{tag}" if not dangling else "<none>:<none>",
        "sizeMb": size_mb,
        "created": _ago_iso(age_seconds),
        "dangling": dangling,
    }


def _network(
    name: str,
    driver: str = "bridge",
    scope: str = "local",
    subnet: str = "",
    gateway: str = "",
    internal: bool = False,
    containers: list | None = None,
) -> dict:
    return {
        "id": _short_id() + _short_id(),
        "name": name,
        "driver": driver,
        "scope": scope,
        "subnet": subnet or f"172.{random.randint(18, 30)}.0.0/16",
        "gateway": gateway or "172.18.0.1",
        "internal": internal,
        "containers": containers or [],
        "created": _ago_iso(random.randint(3600, 864000)),
    }


def _volume(
    name: str,
    driver: str = "local",
    mount_point: str = "",
    size_mb: int = 100,
    dangling: bool = False,
    age_seconds: int = 86400,
    labels: dict | None = None,
) -> dict:
    return {
        "name": name,
        "driver": driver,
        "mountPoint": mount_point or f"/var/lib/docker/volumes/{name}/_data",
        "sizeMb": size_mb,
        "dangling": dangling,
        "created": _ago_iso(age_seconds),
        "labels": labels or {},
    }


def _compose_service(name: str, image: str, status: str = "running", replicas: int = 1, project: str = "fixitlab") -> dict:
    return {
        "name": name,
        "project": project,
        "image": image,
        "status": status,
        "replicas": replicas,
        "runningReplicas": replicas if status == "running" else 0,
    }


# ---------------------------------------------------------------------------
# Mounted secrets
#
# docker_v2_facades.seed_v2 already ships a `secrets` list, but those rows are
# name-only cosmetics: no value, no mount, and nothing a container can resolve.
# That makes the "move the credential out of the env var" scenario ungradeable —
# the only observable action would be deleting the env var, which also passes a
# learner who simply broke the container. The rows below carry a real value and a
# real mount target so the fix has a destination and the checker can require BOTH
# halves (leak closed AND workload still resolving the credential).
# ---------------------------------------------------------------------------

# Planted credential for the env-leak scenario. Fake, generated for the lab, and
# never valid anywhere — the secret scanner allowlists this marker.
# SIMULATED-CREDENTIAL: lab fixture, grants no access. See docs/AUDIT_2026_08_TODO.md §Y2e.
LEAKED_DB_PASSWORD = "p9RtQ2vLx7mK4wZn"  # noqa: S105
LEAKED_SECRET_NAME = "api_db_password"
LEAKED_SECRET_ENV = "DATABASE_PASSWORD"
LEAKED_SECRET_CONTAINER = "api"


def _secret(name: str, value: str, age_seconds: int = 86400) -> dict:
    """A docker secret that actually holds a value.

    `value` stays server-side: _redact_secrets strips it from every state payload
    the console renders, mirroring real Docker, where a secret's plaintext is
    readable only from inside a container that mounts it.
    """
    return {
        "id": f"sec-{name}",
        "name": name,
        "value": value,
        "created": _ago_iso(age_seconds),
        "updated": _ago_iso(age_seconds),
    }


def _find_secret(state: dict, name: str) -> dict | None:
    for s in state.get("secrets") or []:
        if s.get("name") == name or s.get("id") == name:
            return s
    return None


def _secret_mounts(container: dict) -> list:
    return container.get("secretMounts") or []


def _mounted_secret_path(name: str) -> str:
    return f"/run/secrets/{name}"


def _resolves_secret(state: dict, container: dict, secret_name: str) -> bool:
    """True when the container can actually read the secret at runtime.

    Requires the mount to exist AND the underlying secret to still be present —
    a learner who mounts a secret and then deletes it has not fixed anything.
    """
    mount = next((m for m in _secret_mounts(container) if m.get("secret") == secret_name), None)
    if not mount:
        return False
    return _find_secret(state, secret_name) is not None


def _redact_secrets(state: dict) -> None:
    """Strip plaintext secret values from an outbound state payload.

    Mutates a deep copy only — callers must never pass the live session state.
    """
    for s in state.get("secrets") or []:
        if "value" in s:
            s["value"] = "<hidden>"


def _plant_env_secret_leak(state: dict) -> None:
    """Seed the 'credential exposed via docker inspect' fault.

    The api container carries the DB password in plaintext in its env list, so it
    leaks through both `docker inspect` and `docker exec api env`. The secret
    store already holds the same value under `api_db_password`, so the fix is to
    mount it rather than to invent it — and the container must keep resolving the
    credential afterwards.
    """
    state.setdefault("secrets", []).append(
        _secret(LEAKED_SECRET_NAME, LEAKED_DB_PASSWORD, age_seconds=604800)
    )

    api = _find_container(state, LEAKED_SECRET_CONTAINER)
    if api:
        # Replace the masked seed value with the real one so the leak is observable.
        api["env"] = [e for e in api.get("env") or [] if not e.startswith("DATABASE_URL=")]
        api["env"].append(f"{LEAKED_SECRET_ENV}={LEAKED_DB_PASSWORD}")
        api["env"].append(
            f"DATABASE_URL=postgresql://fixitlab:{LEAKED_DB_PASSWORD}@db:5432/fixitlab"
        )

    state["events"].append({
        "time": _now_iso(),
        "type": "warning",
        "action": "secret_exposed",
        "actor": LEAKED_SECRET_CONTAINER,
        "message": (
            f"Audit: container '{LEAKED_SECRET_CONTAINER}' exposes {LEAKED_SECRET_ENV} "
            f"in plaintext via docker inspect"
        ),
    })
    state["validation"] = {
        "require_secret_not_in_env": {
            "container": LEAKED_SECRET_CONTAINER,
            "secret": LEAKED_SECRET_NAME,
            "value": LEAKED_DB_PASSWORD,
            "env_keys": [LEAKED_SECRET_ENV, "DATABASE_URL"],
        }
    }


def _base_daemon() -> dict:
    containers = [
        _container(
            "nginx", "nginx:1.25.3", status="Up 5 days", state="running",
            ports=[{"host": 80, "container": 80, "protocol": "tcp"},
                   {"host": 443, "container": 443, "protocol": "tcp"}],
            volumes=[{"host": "/srv/nginx/conf.d", "container": "/etc/nginx/conf.d", "mode": "ro"},
                     {"host": "/srv/nginx/html", "container": "/usr/share/nginx/html", "mode": "ro"}],
            env=["NGINX_PORT=80"],
            network="fixitlab_prod",
            cpu_pct=1.2, mem_usage_mb=42.5, mem_limit_mb=256.0,
            restart_policy="unless-stopped", restart_count=0, age_seconds=432000,
            compose_service="nginx", compose_project="fixitlab",
            labels={"com.docker.compose.service": "nginx", "com.docker.compose.project": "fixitlab"},
        ),
        _container(
            "api", "fixitlab/api:v2.4.1", status="Up 2 days", state="running",
            ports=[{"host": 8080, "container": 8080, "protocol": "tcp"}],
            volumes=[{"host": "api-config", "container": "/app/config", "mode": "ro"}],
            env=["APP_ENV=production", "LOG_LEVEL=info", "PORT=8080",
                 "DATABASE_URL=postgresql://fixitlab:***@db:5432/fixitlab"],
            network="fixitlab_prod",
            cpu_pct=15.8, mem_usage_mb=312.4, mem_limit_mb=512.0,
            restart_policy="unless-stopped", restart_count=0, age_seconds=172800,
            compose_service="api", compose_project="fixitlab",
            labels={"com.docker.compose.service": "api", "com.docker.compose.project": "fixitlab"},
        ),
        _container(
            "db", "postgres:15.4", status="Up 30 days", state="running",
            ports=[{"host": 5432, "container": 5432, "protocol": "tcp"}],
            volumes=[{"host": "db-data", "container": "/var/lib/postgresql/data", "mode": "rw"}],
            env=["POSTGRES_DB=fixitlab", "POSTGRES_USER=fixitlab", "POSTGRES_PASSWORD=***",
                 "PGDATA=/var/lib/postgresql/data/pgdata"],
            network="fixitlab_prod",
            cpu_pct=8.3, mem_usage_mb=484.2, mem_limit_mb=1024.0,
            restart_policy="unless-stopped", restart_count=0, age_seconds=2592000,
            compose_service="db", compose_project="fixitlab",
            labels={"com.docker.compose.service": "db", "com.docker.compose.project": "fixitlab"},
        ),
        _container(
            "redis", "redis:7.2-alpine", status="Up 30 days", state="running",
            ports=[{"host": 6379, "container": 6379, "protocol": "tcp"}],
            volumes=[{"host": "redis-data", "container": "/data", "mode": "rw"}],
            env=["REDIS_MAXMEMORY=256mb", "REDIS_MAXMEMORY_POLICY=allkeys-lru"],
            network="fixitlab_prod",
            cpu_pct=0.5, mem_usage_mb=28.1, mem_limit_mb=512.0,
            restart_policy="unless-stopped", restart_count=0, age_seconds=2592000,
            compose_service="redis", compose_project="fixitlab",
            labels={"com.docker.compose.service": "redis", "com.docker.compose.project": "fixitlab"},
        ),
        _container(
            "worker", "fixitlab/worker:v1.2.0",
            status="Exited (1) 3 hours ago", state="exited", exit_code=1,
            volumes=[{"host": "worker-logs", "container": "/app/logs", "mode": "rw"}],
            env=["WORKER_CONCURRENCY=4", "QUEUE_BACKEND=redis",
                 "REDIS_URL=redis://redis:6379/0", "APP_ENV=production"],
            network="fixitlab_prod",
            cpu_pct=0.0, mem_usage_mb=0.0, mem_limit_mb=1024.0,
            restart_policy="on-failure", restart_count=12, age_seconds=10800,
            compose_service="worker", compose_project="fixitlab",
            labels={"com.docker.compose.service": "worker", "com.docker.compose.project": "fixitlab"},
        ),
        _container(
            "monitoring", "prom/prometheus:v2.47.0", status="Up 7 days", state="running",
            ports=[{"host": 9090, "container": 9090, "protocol": "tcp"}],
            volumes=[{"host": "prometheus-data", "container": "/prometheus", "mode": "rw"},
                     {"host": "/srv/prometheus/prometheus.yml", "container": "/etc/prometheus/prometheus.yml", "mode": "ro"}],
            env=[],
            network="monitoring_net",
            cpu_pct=4.2, mem_usage_mb=256.8, mem_limit_mb=2048.0,
            restart_policy="unless-stopped", restart_count=0, age_seconds=604800,
            compose_service="prometheus", compose_project="monitoring",
            labels={"com.docker.compose.service": "prometheus", "com.docker.compose.project": "monitoring"},
        ),
        _container(
            "backup", "fixitlab/backup:v1.0.0",
            status="Created", state="created", exit_code=0,
            volumes=[{"host": "db-data", "container": "/data:ro", "mode": "ro"},
                     {"host": "/srv/backups", "container": "/backups", "mode": "rw"}],
            env=["BACKUP_SCHEDULE=0 2 * * *", "BACKUP_RETENTION_DAYS=30",
                 "S3_BUCKET=fixitlab-backups"],
            network="fixitlab_prod",
            cpu_pct=0.0, mem_usage_mb=0.0, mem_limit_mb=256.0,
            restart_policy="no", restart_count=0, age_seconds=86400,
            compose_service="backup", compose_project="fixitlab",
            labels={"com.docker.compose.service": "backup", "com.docker.compose.project": "fixitlab"},
        ),
        _container(
            "cache", "memcached:1.6.21",
            status="Exited (137) 1 hour ago", state="exited", exit_code=137,
            ports=[{"host": 11211, "container": 11211, "protocol": "tcp"}],
            volumes=[],
            env=["MEMCACHED_MEMORY_LIMIT=512"],
            network="fixitlab_prod",
            cpu_pct=0.0, mem_usage_mb=0.0, mem_limit_mb=512.0,
            restart_policy="unless-stopped", restart_count=3, age_seconds=3600,
            compose_service="cache", compose_project="fixitlab",
            labels={"com.docker.compose.service": "cache", "com.docker.compose.project": "fixitlab",
                    "oom_killed": "true"},
        ),
    ]

    images = [
        _image("nginx", "1.25.3", size_mb=187, age_seconds=604800),
        _image("nginx", "1.24.0", size_mb=187, age_seconds=1296000),
        _image("fixitlab/api", "v2.4.1", size_mb=542, age_seconds=172800),
        _image("fixitlab/api", "v2.4.0", size_mb=538, age_seconds=864000),
        _image("fixitlab/api", "v2.3.5", size_mb=520, age_seconds=2592000),
        _image("postgres", "15.4", size_mb=426, age_seconds=604800),
        _image("postgres", "15.3", size_mb=422, age_seconds=1296000),
        _image("redis", "7.2-alpine", size_mb=43, age_seconds=604800),
        _image("fixitlab/worker", "v1.2.0", size_mb=480, age_seconds=864000),
        _image("fixitlab/worker", "v1.1.0", size_mb=465, age_seconds=2592000),
        _image("prom/prometheus", "v2.47.0", size_mb=252, age_seconds=1296000),
        _image("memcached", "1.6.21", size_mb=68, age_seconds=604800),
        _image("fixitlab/backup", "v1.0.0", size_mb=158, age_seconds=2592000),
        # Dangling images (untagged layers from old builds)
        _image("", "", size_mb=312, age_seconds=3600, dangling=True),
        _image("", "", size_mb=88, age_seconds=7200, dangling=True),
    ]

    networks = [
        _network("bridge", driver="bridge", scope="local",
                  subnet="172.17.0.0/16", gateway="172.17.0.1",
                  containers=["nginx", "api", "db", "redis", "worker", "cache"]),
        _network("fixitlab_prod", driver="bridge", scope="local",
                  subnet="172.20.0.0/16", gateway="172.20.0.1",
                  containers=["nginx", "api", "db", "redis", "worker", "backup", "cache"]),
        _network("monitoring_net", driver="bridge", scope="local",
                  subnet="172.21.0.0/16", gateway="172.21.0.1",
                  containers=["monitoring"]),
        _network("host", driver="host", scope="local"),
        _network("none", driver="null", scope="local"),
    ]

    volumes = [
        _volume("db-data", driver="local", size_mb=4200, age_seconds=2592000),
        _volume("redis-data", driver="local", size_mb=128, age_seconds=2592000),
        _volume("prometheus-data", driver="local", size_mb=1800, age_seconds=604800),
        _volume("worker-logs", driver="local", size_mb=512, age_seconds=172800),
        _volume("api-config", driver="local", size_mb=2, age_seconds=604800),
        _volume("nginx-certs", driver="local", size_mb=1, age_seconds=604800),
        _volume("backup-data", driver="local", size_mb=8400, age_seconds=86400),
        # Dangling volumes (not mounted by any container)
        _volume("4a9b2c3d1e5f", driver="local", size_mb=320, dangling=True, age_seconds=2592000),
        _volume("old_api_uploads_backup", driver="local", size_mb=1200, dangling=True, age_seconds=5184000),
        _volume("tmp_build_cache_2024", driver="local", size_mb=650, age_seconds=2592000),
    ]

    compose_services = [
        {"project": "fixitlab", "services": [
            _compose_service("nginx", "nginx:1.25.3", status="running"),
            _compose_service("api", "fixitlab/api:v2.4.1", status="running"),
            _compose_service("db", "postgres:15.4", status="running"),
            _compose_service("redis", "redis:7.2-alpine", status="running"),
            _compose_service("worker", "fixitlab/worker:v1.2.0", status="exited"),
            _compose_service("cache", "memcached:1.6.21", status="exited"),
            _compose_service("backup", "fixitlab/backup:v1.0.0", status="created"),
        ]},
        {"project": "monitoring", "services": [
            _compose_service("prometheus", "prom/prometheus:v2.47.0", status="running", project="monitoring"),
        ]},
    ]

    # Calculate disk usage
    image_size = sum(img["sizeMb"] for img in images)
    container_size = 350  # container writable layers estimate MB
    volume_size = sum(v["sizeMb"] for v in volumes)
    build_cache_mb = 1800

    return {
        "server_version": "24.0.7",
        "api_version": "1.43",
        "os": "linux",
        "arch": "x86_64",
        "kernel": "6.1.0-21-amd64",
        "session": {"logged_in": False, "user": ""},
        "containers": containers,
        "images": images,
        "networks": networks,
        "volumes": volumes,
        "compose_services": compose_services,
        "disk_usage": {
            "totalMb": image_size + container_size + volume_size + build_cache_mb,
            "imagesMb": image_size,
            "containersMb": container_size,
            "volumesMb": volume_size,
            "buildCacheMb": build_cache_mb,
        },
        "events": [],
        "validation": {"require_container_running": "worker"},
    }


def _apply_scenario_preset(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    events = state["events"]

    # Checked before the generic branches: this slug must not fall through to the
    # "cache"/"memory" matcher, and its fault is planted on `api`, not `worker`.
    if "secret" in slug:
        _plant_env_secret_leak(state)
        return

    if "oom" in slug or "memory" in slug or "cache" in slug:
        for c in state["containers"]:
            if c["shortName"] == "cache":
                c["state"] = "exited"
                c["exitCode"] = 137
                c["status"] = "Exited (137) 1 hour ago"
                c["labels"]["oom_killed"] = "true"
        events.append({
            "time": _now_iso(),
            "type": "die",
            "action": "oom",
            "actor": "cache",
            "message": "Container cache killed by OOM killer (exit code 137)",
        })
        state["validation"] = {"require_container_running": "cache"}

    elif "worker-exit" in slug or "worker" in slug:
        for c in state["containers"]:
            if c["shortName"] == "worker":
                c["state"] = "exited"
                c["exitCode"] = 1
                c["status"] = "Exited (1) 3 hours ago"
        events.append({
            "time": _now_iso(),
            "type": "die",
            "action": "exit",
            "actor": "worker",
            "message": "Container worker exited with code 1 — check logs for details",
        })
        state["validation"] = {"require_container_running": "worker"}

    elif "disk-full" in slug or "disk" in slug:
        state["disk_usage"]["totalMb"] = 2048 * 1024  # ~2TB, simulate full
        events.append({
            "time": _now_iso(),
            "type": "oom",
            "action": "disk_full",
            "actor": "docker",
            "message": "No space left on device — container writes failing",
        })
        state["validation"] = {"require_disk_below_gb": 10}

    else:
        events.append({
            "time": _now_iso(),
            "type": "start",
            "action": "info",
            "actor": "docker",
            "message": "Docker daemon state loaded",
        })
        events.append({
            "time": _now_iso(),
            "type": "die",
            "action": "exit",
            "actor": "worker",
            "message": "Container worker exited with code 1 — restart required",
        })
        events.append({
            "time": _now_iso(),
            "type": "die",
            "action": "oom",
            "actor": "cache",
            "message": "Container cache OOM killed",
        })


def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = _base_daemon()
        _apply_scenario_preset(state, scenario_slug)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state, "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    ensure_v2(entry["state"])
    _save_session(str(session_id), entry)
    state = copy.deepcopy(entry["state"])
    # Deep copy above, so this redacts the outbound payload only — the live session
    # keeps the value that `docker exec cat /run/secrets/...` resolves.
    _redact_secrets(state)

    running = [c for c in state["containers"] if c["state"] == "running"]
    exited = [c for c in state["containers"] if c["state"] == "exited"]
    created = [c for c in state["containers"] if c["state"] == "created"]
    dangling_images = [i for i in state["images"] if i.get("dangling")]
    dangling_volumes = [v for v in state["volumes"] if v.get("dangling")]

    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "daemon": state,
        "summary": {
            "containers_running": len(running),
            "containers_stopped": len(exited) + len(created),
            "containers_total": len(state["containers"]),
            "images_total": len(state["images"]),
            "images_dangling": len(dangling_images),
            "volumes_total": len(state["volumes"]),
            "volumes_dangling": len(dangling_volumes),
            "networks_total": len(state["networks"]),
            "swarm_services": len(state.get("swarm_services") or []),
            "disk_usage_gb": round(state["disk_usage"]["totalMb"] / 1024, 2),
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find_container(state: dict, name: str) -> dict | None:
    for c in state["containers"]:
        if c["shortName"] == name or c["name"] == f"/{name}" or c["id"].startswith(name):
            return c
    return None


def _find_image(state: dict, repo_tag: str) -> dict | None:
    for img in state["images"]:
        if img["repoTag"] == repo_tag or img["id"].startswith(repo_tag):
            return img
        if ":" in repo_tag:
            repo, tag = repo_tag.rsplit(":", 1)
            if img["repository"] == repo and img["tag"] == tag:
                return img
    return None


def _find_network(state: dict, name: str) -> dict | None:
    for n in state["networks"]:
        if n["name"] == name or n["id"].startswith(name):
            return n
    return None


def _find_volume(state: dict, name: str) -> dict | None:
    for v in state["volumes"]:
        if v["name"] == name:
            return v
    return None


def _find_compose_service(state: dict, project: str, service: str) -> dict | None:
    for group in state["compose_services"]:
        if group["project"] == project:
            for svc in group["services"]:
                if svc["name"] == service:
                    return svc
    return None


# ---------------------------------------------------------------------------
# Action handler
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Docker session not found"}
    state = entry["state"]
    events = state.setdefault("events", [])

    def _docker_event(event_type: str, event_action: str, actor: str, message: str = "") -> dict:
        return {"time": _now_iso(), "type": event_type, "action": event_action,
                "actor": actor, "message": message}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        events.append(_docker_event("login", "login", "console", "Signed in to Docker Host Console"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Logged in"}

    # --- Container lifecycle ---

    if action == "start_container":
        name = payload.get("container") or payload.get("name")
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        if c["state"] == "running":
            return {"ok": False, "error": f"Container '{name}' is already running"}
        c["state"] = "running"
        c["status"] = "Up Less than a second"
        c["exitCode"] = 0
        c["started"] = _now_iso()
        c["finished"] = None
        c["uptime"] = "Less than a second"
        c["ipAddress"] = f"172.20.0.{random.randint(2, 250)}"
        c["cpuPercent"] = round(random.uniform(0.5, 10.0), 2)
        c["memUsageMb"] = round(random.uniform(30.0, 200.0), 1)
        c["memPercent"] = round(c["memUsageMb"] / c["memLimitMb"] * 100, 1)
        c["restartCount"] = 0
        # Remove the oom_killed label if set
        c["labels"].pop("oom_killed", None)
        # Clear alarms
        state["validation"]["_resolved"] = state["validation"].get("_resolved", []) + [name]
        events.append(_docker_event("start", "start", name, f"Container {name} started"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": name}

    if action == "stop_container":
        name = payload.get("container") or payload.get("name")
        timeout = int(payload.get("timeout", 10))
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        if c["state"] != "running":
            return {"ok": False, "error": f"Container '{name}' is not running"}
        c["state"] = "exited"
        c["status"] = "Exited (0) Less than a second ago"
        c["exitCode"] = 0
        c["finished"] = _now_iso()
        c["uptime"] = None
        c["ipAddress"] = None
        c["cpuPercent"] = 0.0
        c["memUsageMb"] = 0.0
        c["memPercent"] = 0.0
        events.append(_docker_event("die", "stop", name, f"Container {name} stopped (timeout={timeout}s)"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": name}

    if action == "remove_container":
        name = payload.get("container") or payload.get("name")
        force = payload.get("force", False)
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        if c["state"] == "running" and not force:
            return {"ok": False, "error": f"You cannot remove a running container '{name}'. Stop the container before attempting removal or force remove"}
        state["containers"] = [x for x in state["containers"] if x["shortName"] != name]
        events.append(_docker_event("destroy", "destroy", name, f"Container {name} removed"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": name}

    if action == "restart_container":
        name = payload.get("container") or payload.get("name")
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        if c["state"] == "running":
            c["restartCount"] = c.get("restartCount", 0) + 1
        else:
            c["state"] = "running"
            c["exitCode"] = 0
        c["status"] = "Up Less than a second"
        c["started"] = _now_iso()
        c["uptime"] = "Less than a second"
        c["cpuPercent"] = round(random.uniform(0.5, 10.0), 2)
        c["memUsageMb"] = round(random.uniform(30.0, 200.0), 1)
        c["labels"].pop("oom_killed", None)
        events.append(_docker_event("restart", "restart", name, f"Container {name} restarted"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": name}

    # --- Image operations ---

    if action in ("build_image", "docker_build"):
        # Dockerfile layer semantics (X4): cache by instruction digest, multi-stage,
        # digest-pinned FROM, failure → no image tag (docker run → Unable to find image).
        dockerfile = payload.get("dockerfile") or payload.get("Dockerfile") or ""
        context_files = payload.get("files") if isinstance(payload.get("files"), dict) else {}
        tag = (payload.get("tag") or payload.get("name") or "app:latest").strip()
        if ":" in tag:
            repo, img_tag = tag.rsplit(":", 1)
        else:
            repo, img_tag = tag, "latest"

        ignore = set()
        dockerignore = context_files.get(".dockerignore") or payload.get("dockerignore") or ""
        for line in str(dockerignore).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ignore.add(line)

        if not dockerfile and "Dockerfile" in context_files:
            dockerfile = str(context_files["Dockerfile"])
        if not dockerfile.strip():
            return {"ok": False, "error": "Dockerfile is required"}

        lines = [ln.rstrip() for ln in dockerfile.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        if not any(ln.upper().startswith("FROM ") for ln in lines):
            return {"ok": False, "error": "Dockerfile must start with FROM"}

        cache = state.setdefault("build_cache", {})
        layers = []
        stage = "default"
        stages: dict[str, list] = {}
        final_layers = []
        cache_hits = 0
        parent = "scratch"

        for instr in lines:
            upper = instr.upper()
            if upper.startswith("FROM "):
                # FROM image@sha256:… AS name  OR  FROM name AS stage
                m = re.match(
                    r"FROM\s+(\S+)(?:\s+AS\s+(\w+))?",
                    instr,
                    re.I,
                )
                base = m.group(1) if m else "scratch"
                stage = (m.group(2) if m and m.group(2) else "default")
                if "@sha256:" not in base and payload.get("require_digest_pin"):
                    return {
                        "ok": False,
                        "error": (
                            "build failed: base image must be pinned by digest "
                            "(FROM repo@sha256:…)"
                        ),
                    }
                parent = base
                stages.setdefault(stage, [])
                continue

            # Failure injection for teaching
            if "FAIL_BUILD" in instr or payload.get("force_fail"):
                state.setdefault("events", []).append(
                    _docker_event("build", "die", tag, f"Build failed at: {instr[:80]}")
                )
                _save_session(str(session_id), entry)
                return {
                    "ok": False,
                    "error": f"build failed: {instr[:120]}",
                    "layers": layers,
                    "cache_hits": cache_hits,
                }

            # COPY/ADD respect .dockerignore (bloat teaching)
            if upper.startswith(("COPY ", "ADD ")):
                parts = instr.split()
                src = parts[1] if len(parts) > 1 else ""
                if src in ignore or any(src.startswith(p.rstrip("*")) for p in ignore if p.endswith("*")):
                    # Still creates a layer but notes ignored content
                    instr = f"{instr}  # ignored by .dockerignore"

            digest_src = f"{parent}\n{instr}\n"
            for path, content in sorted(context_files.items()):
                if path == "Dockerfile":
                    continue
                if path in ignore:
                    continue
                digest_src += f"{path}:{hashlib.sha256(str(content).encode()).hexdigest()[:16]}\n"
            layer_digest = "sha256:" + hashlib.sha256(digest_src.encode()).hexdigest()
            hit = layer_digest in cache
            if hit:
                cache_hits += 1
            else:
                cache[layer_digest] = {"instr": instr[:200], "at": _now_iso()}
            layer = {
                "digest": layer_digest,
                "instruction": instr[:200],
                "cache_hit": hit,
                "stage": stage,
            }
            layers.append(layer)
            stages.setdefault(stage, []).append(layer)
            parent = layer_digest

        final_layers = stages.get(stage) or layers
        size_mb = 40 + 15 * max(1, len(final_layers) - cache_hits)
        img = _image(repo, img_tag, size_mb=size_mb, age_seconds=1)
        img["layers"] = final_layers
        img["digest"] = final_layers[-1]["digest"] if final_layers else img["id"]
        img["stages"] = list(stages.keys())
        img["cacheHits"] = cache_hits
        # Replace existing tag
        state["images"] = [
            i for i in state.get("images") or []
            if not (i.get("repository") == repo and i.get("tag") == img_tag)
        ]
        state.setdefault("images", []).insert(0, img)
        state["disk_usage"]["imagesMb"] = sum(i.get("sizeMb") or 0 for i in state["images"])
        state["disk_usage"]["totalMb"] = (
            state["disk_usage"]["imagesMb"]
            + state["disk_usage"].get("containersMb", 0)
            + state["disk_usage"].get("volumesMb", 0)
            + state["disk_usage"].get("buildCacheMb", 0)
        )
        events.append(_docker_event("build", "build", tag, f"Built {tag} ({len(final_layers)} layers, {cache_hits} cache hits)"))
        _save_session(str(session_id), entry)
        return {
            "ok": True,
            "message": f"Successfully tagged {repo}:{img_tag}",
            "image": img,
            "layers": final_layers,
            "cache_hits": cache_hits,
        }

    if action == "pull_image":
        image = payload.get("image") or payload.get("name")
        if not image:
            return {"ok": False, "error": "Image name is required"}
        if ":" in image:
            repo, tag = image.rsplit(":", 1)
        else:
            repo, tag = image, "latest"
        if _find_image(state, f"{repo}:{tag}"):
            return {"ok": True, "message": f"Image '{repo}:{tag}' already up to date"}
        size_mb = random.randint(50, 600)
        state["images"].append(_image(repo, tag, size_mb=size_mb, age_seconds=5))
        state["disk_usage"]["imagesMb"] += size_mb
        state["disk_usage"]["totalMb"] += size_mb
        events.append(_docker_event("pull", "pull", f"{repo}:{tag}", f"Pulled image {repo}:{tag}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"{repo}:{tag}: Pull complete"}

    if action == "remove_image":
        image = payload.get("image") or payload.get("name")
        force = payload.get("force", False)
        img = _find_image(state, image)
        if not img:
            return {"ok": False, "error": f"No such image: {image}"}
        if not img.get("dangling") and not force:
            # Check if any container uses this image
            in_use = [c["shortName"] for c in state["containers"] if c["image"] == img["repoTag"]]
            if in_use:
                return {"ok": False, "error": f"image is being used by running container {in_use[0]}"}
        reclaimed = img["sizeMb"]
        state["images"] = [i for i in state["images"] if i["id"] != img["id"]]
        state["disk_usage"]["imagesMb"] -= reclaimed
        state["disk_usage"]["totalMb"] -= reclaimed
        events.append(_docker_event("delete", "delete", img["repoTag"], f"Deleted image {img['repoTag']}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": img["id"], "reclaimedMb": reclaimed}

    # --- Network operations ---

    if action == "create_network":
        name = payload.get("name") or payload.get("network")
        driver = payload.get("driver", "bridge")
        if not name:
            return {"ok": False, "error": "Network name is required"}
        if _find_network(state, name):
            return {"ok": False, "error": f"Network with name '{name}' already exists"}
        net = _network(name, driver=driver, scope="local")
        state["networks"].append(net)
        events.append(_docker_event("create", "create", name, f"Network {name} created"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": net["id"]}

    if action in ("connect_network", "network_connect"):
        container_name = payload.get("container") or payload.get("name") or ""
        network_name = payload.get("network") or payload.get("network_name") or ""
        if not container_name or not network_name:
            return {"ok": False, "error": "container and network are required"}
        c = _find_container(state, container_name)
        if not c:
            return {"ok": False, "error": f"No such container: {container_name}"}
        net = _find_network(state, network_name)
        if not net:
            return {"ok": False, "error": f"No such network: {network_name}"}
        c["network"] = network_name
        c["networkMode"] = network_name
        if c.get("state") == "running" and not c.get("ipAddress"):
            c["ipAddress"] = f"172.18.0.{random.randint(2, 250)}"
        containers = net.setdefault("containers", [])
        if c["shortName"] not in containers and c.get("name") not in containers:
            containers.append(c["shortName"])
        events.append(_docker_event("connect", "connect", c["shortName"],
                                    f"Connected {c['shortName']} to {network_name}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Connected {c['shortName']} to {network_name}",
                "container": c["shortName"], "network": network_name}

    if action in ("disconnect_network", "network_disconnect"):
        container_name = payload.get("container") or payload.get("name") or ""
        network_name = payload.get("network") or payload.get("network_name") or ""
        c = _find_container(state, container_name)
        if not c:
            return {"ok": False, "error": f"No such container: {container_name}"}
        if network_name:
            net = _find_network(state, network_name)
            if net:
                net["containers"] = [x for x in (net.get("containers") or [])
                                     if x not in (c["shortName"], c.get("name"))]
        c["network"] = "bridge"
        c["networkMode"] = "bridge"
        events.append(_docker_event("disconnect", "disconnect", c["shortName"],
                                    f"Disconnected {c['shortName']} from {network_name or 'network'}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Disconnected {c['shortName']}"}

    if action in ("create_container", "run_container", "docker_run"):
        name = (payload.get("name") or payload.get("container") or f"ctr-{_short_id()[:6]}").strip()
        image = (payload.get("image") or "nginx:latest").strip()
        if _find_container(state, name):
            return {"ok": False, "error": f"Conflict. The container name \"/{name}\" is already in use"}
        # X4 failure propagation: failed build → no tag → Unable to find image
        # (check before mutating containers).
        repo, _, tag = image.partition(":")
        tag = tag or "latest"
        has_img = any(
            i.get("repoTag") == image or (i.get("repository") == repo and i.get("tag") == tag)
            for i in state.get("images") or []
        )
        if not has_img:
            if payload.get("create_missing_image") is False or payload.get("pull") is False:
                return {
                    "ok": False,
                    "error": f"Unable to find image '{image}' locally",
                }
            state.setdefault("images", []).insert(0, _image(repo or image, tag=tag, size_mb=80, age_seconds=1))
        network = payload.get("network") or payload.get("network_mode") or "bridge"
        ports_in = payload.get("ports") or []
        ports = []
        for p in ports_in if isinstance(ports_in, list) else []:
            if isinstance(p, dict):
                ports.append({
                    "host": p.get("host") or p.get("host_port") or 0,
                    "container": p.get("container") or p.get("container_port") or 80,
                    "protocol": p.get("protocol") or "tcp",
                })
            elif isinstance(p, str) and ":" in p:
                host, cont = p.split(":", 1)
                ports.append({"host": int(host) if host.isdigit() else 0,
                              "container": int(cont.split("/")[0]) if cont.split("/")[0].isdigit() else 80,
                              "protocol": "tcp"})
        publish = payload.get("publish") or payload.get("p")
        if publish and not ports:
            if isinstance(publish, str) and ":" in publish:
                host, cont = publish.split(":", 1)
                ports.append({"host": int(host) if str(host).isdigit() else 0,
                              "container": int(str(cont).split("/")[0]) if str(cont).split("/")[0].isdigit() else 80,
                              "protocol": "tcp"})
        start = bool(payload.get("start", payload.get("detach", True)))
        c = _container(
            name, image,
            status="Up Less than a second" if start else "Created",
            state="running" if start else "created",
            ports=ports,
            network=network,
            env=payload.get("env") or [],
            age_seconds=1,
            mem_usage_mb=32.0 if start else 0.0,
            cpu_pct=1.0 if start else 0.0,
        )
        state["containers"].append(c)
        net = _find_network(state, network)
        if net:
            containers = net.setdefault("containers", [])
            if name not in containers:
                containers.append(name)
        events.append(_docker_event("create", "create", name, f"Created container {name}"))
        if start:
            events.append(_docker_event("start", "start", name, f"Started container {name}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": c["id"], "container": c}

    if action == "remove_network":
        name = payload.get("name") or payload.get("network")
        if name in ("bridge", "host", "none"):
            return {"ok": False, "error": f"Cannot delete predefined network: {name}"}
        net = _find_network(state, name)
        if not net:
            return {"ok": False, "error": f"No such network: {name}"}
        in_use = [c["shortName"] for c in state["containers"]
                  if c["networkMode"] == name and c["state"] == "running"]
        if in_use:
            return {"ok": False, "error": f"Network '{name}' is still in use by: {', '.join(in_use)}"}
        state["networks"] = [n for n in state["networks"] if n["name"] != name]
        events.append(_docker_event("destroy", "destroy", name, f"Network {name} removed"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": ""}

    # --- Volume operations ---

    if action == "create_volume":
        name = payload.get("name") or payload.get("volume")
        driver = payload.get("driver", "local")
        if not name:
            return {"ok": False, "error": "Volume name is required"}
        if _find_volume(state, name):
            return {"ok": False, "error": f"Volume '{name}' already exists"}
        vol = _volume(name, driver=driver, size_mb=0, age_seconds=1)
        state["volumes"].append(vol)
        events.append(_docker_event("create", "create", name, f"Volume {name} created"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": name}

    if action == "remove_volume":
        name = payload.get("name") or payload.get("volume")
        force = payload.get("force", False)
        vol = _find_volume(state, name)
        if not vol:
            return {"ok": False, "error": f"No such volume: {name}"}
        in_use = [c["shortName"] for c in state["containers"]
                  if any(v.get("host") == name for v in c.get("volumes", []))]
        if in_use and not force:
            return {"ok": False, "error": f"Volume '{name}' is in use by container: {in_use[0]}"}
        reclaimed = vol["sizeMb"]
        state["volumes"] = [v for v in state["volumes"] if v["name"] != name]
        state["disk_usage"]["volumesMb"] -= reclaimed
        state["disk_usage"]["totalMb"] -= reclaimed
        events.append(_docker_event("destroy", "destroy", name, f"Volume {name} removed"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "", "reclaimedMb": reclaimed}

    if action == "prune_volumes":
        dangling = [v for v in state["volumes"] if v.get("dangling")]
        if not dangling:
            return {"ok": True, "message": "No dangling volumes to remove", "reclaimedMb": 0}
        reclaimed = sum(v["sizeMb"] for v in dangling)
        dangling_names = [v["name"] for v in dangling]
        state["volumes"] = [v for v in state["volumes"] if not v.get("dangling")]
        state["disk_usage"]["volumesMb"] -= reclaimed
        state["disk_usage"]["totalMb"] -= reclaimed
        events.append(_docker_event("prune", "prune", "docker",
                                     f"Pruned {len(dangling_names)} dangling volumes, reclaimed {reclaimed}MB"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Total reclaimed space: {round(reclaimed / 1024, 2)}GB",
                "volumesDeleted": dangling_names, "reclaimedMb": reclaimed}

    # --- Docker Compose ---

    if action == "docker_compose_up":
        project = payload.get("project") or "fixitlab"
        service_name = payload.get("service")
        started = []
        for group in state["compose_services"]:
            if group["project"] != project:
                continue
            for svc in group["services"]:
                if service_name and svc["name"] != service_name:
                    continue
                svc["status"] = "running"
                svc["runningReplicas"] = svc["replicas"]
                # Also update matching container
                c = _find_container(state, svc["name"])
                if c and c["state"] != "running":
                    c["state"] = "running"
                    c["exitCode"] = 0
                    c["status"] = "Up Less than a second"
                    c["cpuPercent"] = round(random.uniform(0.5, 10.0), 2)
                    c["memUsageMb"] = round(random.uniform(30.0, 200.0), 1)
                    c["labels"].pop("oom_killed", None)
                started.append(svc["name"])
        if not started:
            return {"ok": False, "error": f"No services found in project '{project}'"}
        events.append(_docker_event("start", "compose_up", project,
                                     f"docker compose up: started {', '.join(started)}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Started: {', '.join(started)}"}

    if action == "docker_compose_down":
        project = payload.get("project") or "fixitlab"
        stopped = []
        for group in state["compose_services"]:
            if group["project"] != project:
                continue
            for svc in group["services"]:
                svc["status"] = "exited"
                svc["runningReplicas"] = 0
                c = _find_container(state, svc["name"])
                if c and c["state"] == "running":
                    c["state"] = "exited"
                    c["exitCode"] = 0
                    c["status"] = "Exited (0) Less than a second ago"
                    c["cpuPercent"] = 0.0
                    c["memUsageMb"] = 0.0
                    c["uptime"] = None
                    stopped.append(svc["name"])
        events.append(_docker_event("stop", "compose_down", project,
                                     f"docker compose down: stopped {', '.join(stopped)}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Stopped: {', '.join(stopped)}"}

    if action == "docker_compose_restart":
        project = payload.get("project") or "fixitlab"
        service_name = payload.get("service")
        restarted = []
        for group in state["compose_services"]:
            if group["project"] != project:
                continue
            for svc in group["services"]:
                if service_name and svc["name"] != service_name:
                    continue
                svc["status"] = "running"
                svc["runningReplicas"] = svc["replicas"]
                c = _find_container(state, svc["name"])
                if c:
                    c["state"] = "running"
                    c["exitCode"] = 0
                    c["status"] = "Up Less than a second"
                    c["cpuPercent"] = round(random.uniform(0.5, 10.0), 2)
                    c["memUsageMb"] = round(random.uniform(30.0, 200.0), 1)
                    c["labels"].pop("oom_killed", None)
                restarted.append(svc["name"])
        events.append(_docker_event("restart", "compose_restart", project,
                                     f"docker compose restart: {', '.join(restarted)}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Restarted: {', '.join(restarted)}"}

    # --- Container exec / inspect / stats ---

    if action == "exec_container":
        name = payload.get("container") or payload.get("name")
        cmd = payload.get("cmd") or "sh"
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        if c["state"] != "running":
            return {"ok": False, "error": f"Container '{name}' is not running"}
        # Simulate command output based on common commands
        cmd_lower = cmd.lower().strip()
        output = ""
        # Mounted secrets are readable only from inside the container, and only by
        # path — this is what makes the mount a real destination for the credential
        # rather than a label the learner ticks off.
        if "/run/secrets" in cmd_lower:
            mounts = _secret_mounts(c)
            if cmd_lower.startswith("ls") or " ls " in cmd_lower:
                names = sorted(m["target"].rsplit("/", 1)[-1] for m in mounts)
                return {"ok": True, "output": "  ".join(names), "exitCode": 0}
            wanted = next((tok for tok in cmd.split() if "/run/secrets" in tok), "")
            mount = next((m for m in mounts if m.get("target") == wanted), None)
            if not mount:
                return {"ok": True,
                        "output": f"cat: {wanted}: No such file or directory", "exitCode": 1}
            sec = _find_secret(state, mount["secret"])
            if not sec:
                # Mount survives but the secret was deleted: the file is empty, the
                # app breaks. Surfacing this is the point — it is the failure mode
                # the checker refuses to pass.
                return {"ok": True, "output": "", "exitCode": 1}
            return {"ok": True, "output": sec["value"], "exitCode": 0}
        if "env" in cmd_lower:
            output = "\n".join(c.get("env", []))
        elif "ps" in cmd_lower:
            output = "PID   USER     TIME  COMMAND\n    1 root      0:00 /bin/sh -c exec entrypoint.sh\n   12 root      0:05 app"
        elif "ls" in cmd_lower:
            output = "app  bin  config  data  etc  lib  log  tmp  usr  var"
        elif "cat" in cmd_lower and "log" in cmd_lower:
            output = f"[{_now_iso()}] INFO  Application started\n[{_now_iso()}] ERROR Connection refused to redis:6379\n"
        elif "df" in cmd_lower:
            output = "Filesystem      Size  Used Avail Use% Mounted on\noverlay          50G   12G   36G  25% /\ntmpfs            64M     0   64M   0% /dev\n"
        elif "free" in cmd_lower:
            output = f"              total        used        free      shared  buff/cache   available\nMem:        {int(c['memLimitMb'])}       {int(c['memUsageMb'])}       {int(c['memLimitMb'] - c['memUsageMb'])}          0         0    {int(c['memLimitMb'] - c['memUsageMb'])}\n"
        else:
            output = f"Executed: {cmd}"
        return {"ok": True, "output": output, "exitCode": 0}

    if action == "inspect_container":
        name = payload.get("container") or payload.get("name")
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        detail = copy.deepcopy(c)
        detail["hostConfig"] = {
            "restartPolicy": {"Name": c["restartPolicy"], "MaximumRetryCount": 5},
            "networkMode": c["networkMode"],
            "cpuPeriod": 100000,
            "cpuQuota": 0,
            "memory": int(c["memLimitMb"] * 1024 * 1024),
            "logConfig": {"Type": "json-file", "Config": {"max-size": "10m", "max-file": "5"}},
        }
        # Real `docker inspect` lists the secret's target path but never its value —
        # that asymmetry against the env list is the whole lesson of this scenario.
        detail["secrets"] = [
            {"secret": m["secret"], "target": m["target"], "mode": m.get("mode", "0400")}
            for m in _secret_mounts(c)
        ]
        return {"ok": True, "inspect": detail}

    if action == "stats_container":
        name = payload.get("container") or payload.get("name")
        c = _find_container(state, name)
        if not c:
            return {"ok": False, "error": f"No such container: {name}"}
        if c["state"] != "running":
            return {"ok": False, "error": f"Container '{name}' is not running"}
        return {
            "ok": True,
            "stats": {
                "name": c["name"],
                "cpuPercent": c["cpuPercent"],
                "memUsageMb": c["memUsageMb"],
                "memLimitMb": c["memLimitMb"],
                "memPercent": c["memPercent"],
                "netInputMb": round(random.uniform(0.1, 50.0), 2),
                "netOutputMb": round(random.uniform(0.1, 20.0), 2),
                "blockReadMb": round(random.uniform(0.0, 5.0), 2),
                "blockWriteMb": round(random.uniform(0.0, 2.0), 2),
                "pids": random.randint(1, 30),
            },
        }

    # --- System prune ---

    if action == "system_prune":
        all_flag = payload.get("all", False)
        volumes_flag = payload.get("volumes", False)
        reclaimed_mb = 0

        # Remove dangling images
        dangling_imgs = [i for i in state["images"] if i.get("dangling")]
        for img in dangling_imgs:
            reclaimed_mb += img["sizeMb"]
        state["images"] = [i for i in state["images"] if not i.get("dangling")]

        # Remove stopped containers
        stopped = [c for c in state["containers"] if c["state"] in ("exited", "created")]
        for c in stopped:
            reclaimed_mb += 50  # writable layer estimate
        state["containers"] = [c for c in state["containers"] if c["state"] == "running"]

        # Remove unused networks
        used_nets = {c["networkMode"] for c in state["containers"]}
        unused_nets = [n for n in state["networks"] if n["name"] not in used_nets and n["name"] not in ("host", "none", "bridge")]
        state["networks"] = [n for n in state["networks"] if n["name"] in used_nets or n["name"] in ("host", "none", "bridge")]

        # Remove dangling volumes if --volumes flag
        if volumes_flag:
            dangling_vols = [v for v in state["volumes"] if v.get("dangling")]
            for vol in dangling_vols:
                reclaimed_mb += vol["sizeMb"]
            state["volumes"] = [v for v in state["volumes"] if not v.get("dangling")]

        # Build cache
        cache_reclaimed = state["disk_usage"]["buildCacheMb"]
        reclaimed_mb += cache_reclaimed
        state["disk_usage"]["buildCacheMb"] = 0

        state["disk_usage"]["imagesMb"] = sum(i["sizeMb"] for i in state["images"])
        state["disk_usage"]["volumesMb"] = sum(v["sizeMb"] for v in state["volumes"])
        state["disk_usage"]["totalMb"] = (
            state["disk_usage"]["imagesMb"]
            + state["disk_usage"]["containersMb"]
            + state["disk_usage"]["volumesMb"]
            + state["disk_usage"]["buildCacheMb"]
        )

        events.append(_docker_event("prune", "system_prune", "docker",
                                     f"System prune complete, reclaimed {reclaimed_mb}MB"))
        _save_session(str(session_id), entry)
        return {
            "ok": True,
            "message": f"Total reclaimed space: {round(reclaimed_mb / 1024, 2)}GB",
            "reclaimedMb": reclaimed_mb,
            "containersDeleted": [c["shortName"] for c in stopped],
            "networksDeleted": [n["name"] for n in unused_nets],
            "buildCacheReclaimedMb": cache_reclaimed,
        }

    # --- Secret operations ---
    #
    # These intercept `create_secret` ahead of the v2 facade, which only records a
    # name. A secret with no value cannot be mounted, and a mount that resolves to
    # nothing cannot be graded, so the engine owns the whole lifecycle here.

    if action == "create_secret":
        ensure_v2(state)
        name = (payload.get("name") or "").strip()
        value = payload.get("value")
        if not name:
            return {"ok": False, "error": "Secret name is required"}
        if _find_secret(state, name):
            return {"ok": False, "error": f"Secret '{name}' already exists"}
        if value in (None, ""):
            return {"ok": False, "error": "Secret value is required (docker secret create reads from stdin or a file)"}
        row = _secret(name, str(value), age_seconds=1)
        state.setdefault("secrets", []).append(row)
        events.append(_docker_event("create", "secret_create", name, f"Secret {name} created"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": row["id"],
                "secret": {k: v for k, v in row.items() if k != "value"}}

    if action == "remove_secret":
        ensure_v2(state)
        name = (payload.get("name") or payload.get("secret") or "").strip()
        sec = _find_secret(state, name)
        if not sec:
            return {"ok": False, "error": f"No such secret: {name}"}
        in_use = [c["shortName"] for c in state["containers"]
                  if any(m.get("secret") == sec["name"] for m in _secret_mounts(c))]
        if in_use:
            return {"ok": False,
                    "error": f"Error response from daemon: secret '{sec['name']}' is in use by service: {in_use[0]}"}
        state["secrets"] = [s for s in state["secrets"] if s["id"] != sec["id"]]
        events.append(_docker_event("destroy", "secret_remove", sec["name"], f"Secret {sec['name']} removed"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": sec["name"]}

    if action in ("mount_secret", "attach_secret"):
        ensure_v2(state)
        container_name = payload.get("container") or payload.get("name") or ""
        secret_name = (payload.get("secret") or "").strip()
        c = _find_container(state, container_name)
        if not c:
            return {"ok": False, "error": f"No such container: {container_name}"}
        sec = _find_secret(state, secret_name)
        if not sec:
            return {"ok": False, "error": f"No such secret: {secret_name}"}
        mounts = c.setdefault("secretMounts", [])
        if any(m.get("secret") == sec["name"] for m in mounts):
            return {"ok": False, "error": f"Secret '{sec['name']}' is already mounted in {c['shortName']}"}
        # Real Docker exposes the secret as a tmpfs file, never as an env var, so
        # the mount deliberately records only a path — mounting must not re-create
        # the very leak the learner is being asked to close.
        target = payload.get("target") or _mounted_secret_path(sec["name"])
        mounts.append({"secret": sec["name"], "target": target, "mode": "0400", "uid": "0", "gid": "0"})
        events.append(_docker_event("mount", "secret_mount", c["shortName"],
                                    f"Mounted secret {sec['name']} at {target} in {c['shortName']}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Mounted {sec['name']} at {target}",
                "container": c["shortName"], "target": target}

    if action in ("unmount_secret", "detach_secret"):
        ensure_v2(state)
        container_name = payload.get("container") or payload.get("name") or ""
        secret_name = (payload.get("secret") or "").strip()
        c = _find_container(state, container_name)
        if not c:
            return {"ok": False, "error": f"No such container: {container_name}"}
        before = len(_secret_mounts(c))
        c["secretMounts"] = [m for m in _secret_mounts(c) if m.get("secret") != secret_name]
        if len(c["secretMounts"]) == before:
            return {"ok": False, "error": f"Secret '{secret_name}' is not mounted in {c['shortName']}"}
        events.append(_docker_event("unmount", "secret_unmount", c["shortName"],
                                    f"Unmounted secret {secret_name} from {c['shortName']}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Unmounted {secret_name}"}

    if action in ("remove_container_env", "unset_env"):
        container_name = payload.get("container") or payload.get("name") or ""
        key = (payload.get("key") or payload.get("env") or "").strip()
        c = _find_container(state, container_name)
        if not c:
            return {"ok": False, "error": f"No such container: {container_name}"}
        if not key:
            return {"ok": False, "error": "Env key is required"}
        before = list(c.get("env") or [])
        c["env"] = [e for e in before if e.split("=", 1)[0] != key]
        if len(c["env"]) == len(before):
            return {"ok": False, "error": f"Container '{c['shortName']}' has no env var '{key}'"}
        events.append(_docker_event("update", "env_unset", c["shortName"],
                                    f"Removed env var {key} from {c['shortName']}"))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Removed {key} from {c['shortName']}"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _save_session(str(session_id), entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_docker_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    rules = state.get("validation") or {}

    if rules.get("require_secret_not_in_env"):
        rule = rules["require_secret_not_in_env"]
        name = rule["container"]
        secret_name = rule["secret"]
        value = rule["value"]
        c = _find_container(state, name)
        if not c:
            return False, f"Container '{name}' no longer exists — the workload must survive the fix"

        # Half 1: the credential must be gone from every inspect/exec surface.
        # Checked by value, not by key name: renaming DATABASE_PASSWORD to
        # DB_PASS_2 moves the leak, it does not close it.
        leaking = [e for e in c.get("env") or [] if value in e]
        if leaking:
            leaked_keys = ", ".join(sorted({e.split("=", 1)[0] for e in leaking}))
            return False, (
                f"'{name}' still exposes the credential via docker inspect "
                f"(env: {leaked_keys}) — move it to a mounted secret"
            )

        # Half 2: the workload must still resolve the credential. Without this the
        # scenario would pass a learner who simply deleted the env var and broke
        # the container — the exact failure the audit flagged.
        if not _resolves_secret(state, c, secret_name):
            if _find_secret(state, secret_name) is None:
                return False, (
                    f"Secret '{secret_name}' does not exist — '{name}' has no way to "
                    f"resolve the credential; deleting it is not a fix"
                )
            return False, (
                f"'{name}' no longer has the credential: mount secret "
                f"'{secret_name}' at {_mounted_secret_path(secret_name)}"
            )

        # Half 3: the mounted secret must carry the real credential, not a
        # placeholder the learner typed to satisfy the mount check.
        sec = _find_secret(state, secret_name)
        if sec.get("value") != value:
            return False, (
                f"Secret '{secret_name}' does not hold the working credential — "
                f"'{name}' would fail to authenticate against db"
            )

        if c.get("state") != "running":
            return False, f"Container '{name}' must be running after the fix (currently {c.get('state')})"

        return True, (
            f"'{name}' resolves {secret_name} from {_mounted_secret_path(secret_name)} "
            f"and no longer leaks it through docker inspect — validation passed"
        )

    if rules.get("require_container_running"):
        name = rules["require_container_running"]
        c = _find_container(state, name)
        if not c or c.get("state") != "running":
            return False, f"Container '{name}' must be running"
        return True, f"Container '{name}' is running — validation passed"

    if rules.get("require_disk_below_gb"):
        limit_gb = rules["require_disk_below_gb"]
        current_gb = round(state["disk_usage"]["totalMb"] / 1024, 2)
        if current_gb > limit_gb:
            return False, f"Disk usage must be below {limit_gb}GB (currently {current_gb}GB)"
        return True, f"Disk usage is {current_gb}GB — validation passed"

    return True, "Validation passed"
