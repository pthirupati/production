"""Monitoring V2 facades — Alertmanager depth, exporters, richer Prom targets/rules."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any
import random


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _later(hours: int = 2) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "exporters": {
            "node_exporter": {
                "url": "http://10.0.1.1:9100/metrics",
                "up": True,
                "sample_metrics": [
                    'node_cpu_seconds_total{cpu="0",mode="idle"} 1.234567e+07',
                    'node_memory_MemAvailable_bytes 4.294967e+09',
                    'node_load1 0.42',
                ],
            },
            "blackbox": {
                "url": "http://127.0.0.1:9115",
                "modules": ["http_2xx", "http_post_2xx", "tcp_connect", "icmp", "dns"],
                "probes": [
                    {"target": "https://example.com", "module": "http_2xx", "success": True, "duration_s": 0.12},
                    {"target": "https://api.example.com/health", "module": "http_2xx", "success": True, "duration_s": 0.08},
                    {"target": "https://down.example.com", "module": "http_2xx", "success": False, "duration_s": 5.0},
                ],
            },
            "pushgateway": {
                "url": "http://127.0.0.1:9091",
                "groups": [
                    {"job": "batch", "instance": "cron-1", "last_push": _now(), "metrics": 12},
                ],
            },
        },
        "prom_runtime": {
            "start_time": "2024-06-11T09:12:34.123Z",
            "cwd": "/",
            "config_file": "/etc/prometheus/prometheus.yml",
            "GOMAXPROCS": 8,
            "storage_retention": "15d",
            "version": "2.52.0",
            "go_version": "go1.22.3",
        },
        "prom_flags": [
            {"flag": "--config.file", "value": "/etc/prometheus/prometheus.yml"},
            {"flag": "--storage.tsdb.path", "value": "/prometheus/data"},
            {"flag": "--storage.tsdb.retention.time", "value": "15d"},
            {"flag": "--web.listen-address", "value": "0.0.0.0:9090"},
            {"flag": "--web.enable-lifecycle", "value": "false"},
            {"flag": "--query.timeout", "value": "2m"},
            {"flag": "--query.max-concurrency", "value": "20"},
        ],
        "service_discovery": [
            {"type": "static", "job": "prometheus", "discovered": 1, "active": 1},
            {"type": "static", "job": "node_exporter", "discovered": 8, "active": 7},
            {"type": "kubernetes_sd", "role": "pod", "discovered": 47, "active": 24},
            {"type": "kubernetes_sd", "role": "node", "discovered": 5, "active": 5},
            {"type": "file_sd", "path": "/etc/prometheus/targets/prod-nodes.json", "discovered": 8, "active": 8},
        ],
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, dict) else dict(value)

    prom = state.setdefault("prometheus", {})
    am = prom.setdefault("alertmanager", {})
    am.setdefault("url", "http://alertmanager:9093")
    am.setdefault("cluster_status", "Ready")
    am.setdefault("peers", 1)
    if not am.get("silences"):
        am["silences"] = [
            {
                "id": "sil-001",
                "created_by": "admin",
                "starts_at": _now(),
                "ends_at": _later(2),
                "matchers": [{"name": "alertname", "value": "NodeDown", "isRegex": False}],
                "comment": "Planned maintenance",
                "state": "active",
            },
        ]
    am.setdefault("config_yaml", (
        "global:\n  resolve_timeout: 5m\n"
        "route:\n  receiver: default-receiver\n  group_by: [alertname, cluster]\n"
        "receivers:\n  - name: default-receiver\n"
    ))

    # Enrich targets if thin
    targets = prom.setdefault("targets", [])
    if len(targets) < 20:
        extra_jobs = [
            ("kubernetes-pods", "pod-api-1:8080", "up"),
            ("kubernetes-pods", "pod-api-2:8080", "up"),
            ("kubernetes-nodes", "node-1:10250", "up"),
            ("postgres", "pg-1:9187", "up"),
            ("mysql", "mysql-1:9104", "up"),
            ("redis", "redis-1:9121", "up"),
            ("nginx", "nginx-1:9113", "up"),
            ("node_exporter", "10.0.1.5:9100", "down"),
        ]
        existing = {(t.get("job"), t.get("instance")) for t in targets}
        for job, inst, health in extra_jobs:
            if (job, inst) in existing:
                continue
            row = {
                "job": job, "instance": inst, "health": health,
                "scrape_url": f"http://{inst}/metrics",
                "last_scrape": _now(),
                "scrape_duration_ms": random.randint(10, 80),
                "labels": {"job": job},
            }
            if health == "down":
                row["last_error"] = "context deadline exceeded"
            targets.append(row)

    rules = prom.setdefault("alerting_rules", [])
    if len(rules) < 8:
        for name, expr, state_name in [
            ("NodeDown", 'up{job="node"} == 0', "firing"),
            ("HighCPUUsage", '100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85', "inactive"),
            ("LowDiskSpace", '(node_filesystem_avail_bytes / node_filesystem_size_bytes) * 100 < 10', "firing"),
            ("KubePodCrashLooping", "rate(kube_pod_container_status_restarts_total[15m]) * 300 > 0", "firing"),
            ("HighErrorRate", 'sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05', "inactive"),
        ]:
            if any(r.get("name") == name for r in rules):
                continue
            rules.append({
                "group": "v2_alerts", "name": name, "expr": expr, "for": "5m",
                "labels": {"severity": "critical" if "Down" in name or "Crash" in name else "warning"},
                "annotations": {"summary": f"{name} fired"},
                "state": state_name, "health": "ok",
            })


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)
    am = state.setdefault("prometheus", {}).setdefault("alertmanager", {})

    if action == "create_silence":
        matchers = payload.get("matchers") or [{"name": "alertname", "value": payload.get("alertname") or "NodeDown", "isRegex": False}]
        row = {
            "id": f"sil-{random.randint(100, 999)}",
            "created_by": payload.get("created_by") or "labuser",
            "starts_at": payload.get("starts_at") or _now(),
            "ends_at": payload.get("ends_at") or _later(int(payload.get("hours") or 2)),
            "matchers": matchers,
            "comment": payload.get("comment") or "Lab silence",
            "state": "active",
        }
        am.setdefault("silences", []).append(row)
        return {"ok": True, "message": f"Created silence {row['id']}", "silence": row}

    if action == "expire_silence":
        sid = payload.get("silence_id") or payload.get("id") or ""
        sil = next((s for s in am.get("silences") or [] if s.get("id") == sid), None)
        if not sil:
            return {"ok": False, "error": "Silence not found"}
        sil["state"] = "expired"
        sil["ends_at"] = _now()
        return {"ok": True, "message": f"Expired {sid}", "silence": sil}

    if action == "blackbox_probe":
        target = (payload.get("target") or "https://example.com").strip()
        module = payload.get("module") or "http_2xx"
        success = "down" not in target.lower() and "fail" not in target.lower()
        probe = {
            "target": target, "module": module, "success": success,
            "duration_s": 0.1 if success else 5.0, "probed_at": _now(),
        }
        exporters = state.setdefault("exporters", {})
        bb = exporters.setdefault("blackbox", {"modules": [], "probes": []})
        bb.setdefault("probes", []).insert(0, probe)
        return {"ok": True, "message": f"Probe {'OK' if success else 'FAILED'}: {target}", "probe": probe}

    if action == "pushgateway_push":
        job = payload.get("job") or "batch"
        instance = payload.get("instance") or "cron-1"
        groups = state.setdefault("exporters", {}).setdefault("pushgateway", {}).setdefault("groups", [])
        g = next((x for x in groups if x.get("job") == job and x.get("instance") == instance), None)
        if not g:
            g = {"job": job, "instance": instance, "metrics": 0}
            groups.append(g)
        g["last_push"] = _now()
        g["metrics"] = int(g.get("metrics") or 0) + int(payload.get("metrics") or 1)
        return {"ok": True, "message": f"Pushed metrics for {job}/{instance}", "group": g}

    return None
