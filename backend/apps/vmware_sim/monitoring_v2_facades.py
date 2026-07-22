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
        "grafana_browse": {
            "folders": [
                {"id": "general", "name": "General", "dashboards": 3},
                {"id": "infra", "name": "Infrastructure", "dashboards": 5},
                {"id": "apps", "name": "Applications", "dashboards": 4},
                {"id": "slo", "name": "SLO / SLI", "dashboards": 2},
            ],
            "playlists": [
                {"id": "pl1", "name": "NOC Rotation", "dashboards": 4, "interval": "30s"},
                {"id": "pl2", "name": "Executive Summary", "dashboards": 2, "interval": "60s"},
            ],
            "snapshots": [
                {"id": "sn1", "name": "Incident 2026-06-20", "created": "2026-06-20T14:00:00Z", "expires": "2026-07-20"},
            ],
            "library_panels": [
                {"id": "lp1", "name": "CPU Usage Stat", "type": "stat", "datasource": "Prometheus"},
                {"id": "lp2", "name": "Request Rate Graph", "type": "timeseries", "datasource": "Prometheus"},
            ],
            "browse_dashboards": [
                {"uid": "infra-nodes", "title": "Node Exporter Full", "folder": "Infrastructure", "tags": ["linux", "prometheus"], "updated": "2026-06-24"},
                {"uid": "k8s-cluster", "title": "Kubernetes Cluster", "folder": "Infrastructure", "tags": ["k8s"], "updated": "2026-06-23"},
                {"uid": "api-latency", "title": "API Latency SLO", "folder": "SLO / SLI", "tags": ["http", "slo"], "updated": "2026-06-22"},
                {"uid": "home-overview", "title": "Home Overview", "folder": "General", "tags": ["home"], "updated": "2026-06-20"},
            ],
        },
        "grafana_admin": {
            "users": [
                {"login": "admin", "name": "Org Admin", "email": "admin@fixitlab.local", "role": "Admin", "lastSeen": "2 minutes ago"},
                {"login": "j.editor", "name": "Jordan Lee", "email": "jordan.lee@fixitlab.local", "role": "Editor", "lastSeen": "3 hours ago"},
                {"login": "v.viewer", "name": "Vik Rao", "email": "vik.rao@fixitlab.local", "role": "Viewer", "lastSeen": "2 days ago"},
            ],
            "teams": [
                {"name": "Observability", "email": "obs@fixitlab.local", "members": 6, "role": "Admin"},
                {"name": "Platform", "email": "platform@fixitlab.local", "members": 9, "role": "Editor"},
            ],
            "service_accounts": [
                {"name": "ci-dashboards", "role": "Editor", "tokens": 2, "token": "glsa_lab_ci", "disabled": False},
                {"name": "terraform-provisioner", "role": "Admin", "tokens": 1, "token": "glsa_lab_tf", "disabled": False},
            ],
        },
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, dict) else dict(value)
        elif key in ("grafana_browse", "grafana_admin") and isinstance(value, dict) and isinstance(state.get(key), dict):
            for nested, nested_val in value.items():
                state[key].setdefault(nested, nested_val)

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
            ("node_exporter", "10.0.1.5:9100", "up"),
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

    if action == "create_playlist":
        browse = state.setdefault("grafana_browse", {})
        name = (payload.get("name") or f"Playlist {len(browse.get('playlists') or []) + 1}").strip()
        row = {
            "id": f"pl-{len(browse.get('playlists') or []) + 1}",
            "name": name,
            "dashboards": int(payload.get("dashboards") or 1),
            "interval": payload.get("interval") or "30s",
        }
        browse.setdefault("playlists", []).append(row)
        return {"ok": True, "message": f"Playlist {name} created", "playlist": row}

    if action == "create_snapshot":
        browse = state.setdefault("grafana_browse", {})
        name = (payload.get("name") or f"Snapshot {len(browse.get('snapshots') or []) + 1}").strip()
        row = {
            "id": f"sn-{len(browse.get('snapshots') or []) + 1}",
            "name": name,
            "created": _now(),
            "expires": payload.get("expires") or "2026-12-31",
        }
        browse.setdefault("snapshots", []).append(row)
        return {"ok": True, "message": f"Snapshot {name} created", "snapshot": row}

    if action == "create_library_panel":
        browse = state.setdefault("grafana_browse", {})
        name = (payload.get("name") or f"Panel {len(browse.get('library_panels') or []) + 1}").strip()
        row = {
            "id": f"lp-{len(browse.get('library_panels') or []) + 1}",
            "name": name,
            "type": payload.get("type") or "timeseries",
            "datasource": payload.get("datasource") or "Prometheus",
        }
        browse.setdefault("library_panels", []).append(row)
        return {"ok": True, "message": f"Library panel {name} created", "panel": row}

    if action == "create_folder":
        browse = state.setdefault("grafana_browse", {})
        name = (payload.get("name") or f"Folder {len(browse.get('folders') or []) + 1}").strip()
        fid = (payload.get("id") or name.lower().replace(" ", "-"))[:32]
        if any(f.get("id") == fid or f.get("name") == name for f in browse.get("folders") or []):
            return {"ok": False, "error": "Folder already exists"}
        row = {"id": fid, "name": name, "dashboards": 0}
        browse.setdefault("folders", []).append(row)
        return {"ok": True, "message": f"Folder {name} created", "folder": row}

    if action == "create_grafana_user":
        admin = state.setdefault("grafana_admin", seed_v2()["grafana_admin"])
        login = (payload.get("login") or payload.get("name") or f"user{len(admin.get('users') or []) + 1}").strip()
        if any(u.get("login") == login for u in admin.get("users") or []):
            return {"ok": False, "error": f"User '{login}' already exists"}
        row = {
            "login": login,
            "name": payload.get("display") or payload.get("name") or login,
            "email": payload.get("email") or f"{login}@fixitlab.local",
            "role": payload.get("role") or "Viewer",
            "lastSeen": "Just now",
        }
        admin.setdefault("users", []).append(row)
        return {"ok": True, "message": f"Created Grafana user {login}", "user": row}

    if action == "create_grafana_team":
        admin = state.setdefault("grafana_admin", seed_v2()["grafana_admin"])
        name = (payload.get("name") or f"Team {len(admin.get('teams') or []) + 1}").strip()
        if any(t.get("name") == name for t in admin.get("teams") or []):
            return {"ok": False, "error": f"Team '{name}' already exists"}
        row = {
            "name": name,
            "email": payload.get("email") or f"{name.lower().replace(' ', '-')}@fixitlab.local",
            "members": int(payload.get("members") or 1),
            "role": payload.get("role") or "Editor",
        }
        admin.setdefault("teams", []).append(row)
        return {"ok": True, "message": f"Created team {name}", "team": row}

    if action == "create_service_account":
        admin = state.setdefault("grafana_admin", seed_v2()["grafana_admin"])
        name = (payload.get("name") or f"sa-{len(admin.get('service_accounts') or []) + 1}").strip()
        if any(s.get("name") == name for s in admin.get("service_accounts") or []):
            return {"ok": False, "error": f"Service account '{name}' already exists"}
        row = {
            "name": name,
            "role": payload.get("role") or "Editor",
            "tokens": int(payload.get("tokens") or 1),
            "token": payload.get("token") or f"glsa_lab_{name[:8]}",
            "disabled": False,
        }
        admin.setdefault("service_accounts", []).append(row)
        return {"ok": True, "message": f"Created service account {name}", "service_account": row}

    if action == "create_grafana_alert_rule":
        graf = state.setdefault("grafana", {})
        title = (payload.get("title") or payload.get("name") or f"Rule {len(graf.get('alert_rules') or []) + 1}").strip()
        row = {
            "uid": payload.get("uid") or f"rule-{title.lower().replace(' ', '-')[:24]}",
            "title": title,
            "folder": payload.get("folder") or "General",
            "group": payload.get("group") or "default",
            "condition": payload.get("condition") or payload.get("expr") or "up == 0",
            "for": payload.get("for") or "5m",
            "severity": payload.get("severity") or "warning",
            "state": payload.get("state") or "Normal",
            "contact_point": payload.get("contact_point") or "grafana-default-email",
            "datasource": payload.get("datasource") or "Prometheus",
            "no_data_state": "NoData",
        }
        graf.setdefault("alert_rules", []).append(row)
        return {"ok": True, "message": f"Created alert rule {title}", "rule": row}

    if action == "create_contact_point":
        graf = state.setdefault("grafana", {})
        name = (payload.get("name") or f"contact-{len(graf.get('contact_points') or []) + 1}").strip()
        if any(c.get("name") == name for c in graf.get("contact_points") or []):
            return {"ok": False, "error": f"Contact point '{name}' already exists"}
        row = {
            "name": name,
            "type": payload.get("type") or "email",
            "configured": True,
            "address": payload.get("address") or "oncall@fixitlab.local",
        }
        graf.setdefault("contact_points", []).append(row)
        return {"ok": True, "message": f"Created contact point {name}", "contact_point": row}

    return None
