"""Commvault Command Center V2 facades — ransomware, K8s, SaaS, plans, reports."""

from __future__ import annotations

import random
import time
from typing import Any

_HEX = "0123456789abcdef"


def _hex(n: int = 6) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_v2() -> dict[str, Any]:
    return {
        "ransomware": {
            "enabled": True, "honeypot_files": 48, "anomaly_events": [
                {"id": "RAN-1", "client": "fs-file01", "severity": "High",
                 "detail": "Backup size +42% vs 7-day baseline", "time": _now()},
            ], "worm_coverage_pct": 78, "threat_scan_last": _now(),
        },
        "k8s_apps": [
            {"id": f"k8s-{_hex()}", "name": "eks-prod-us", "distribution": "EKS",
             "namespaces": ["payments", "checkout"], "plan": "K8s-Daily",
             "last_backup": "Success", "pvcs": 12},
        ],
        "saas_apps": [
            {"id": f"saas-{_hex()}", "name": "M365-Corp", "type": "Microsoft 365",
             "workloads": ["Exchange", "OneDrive", "SharePoint", "Teams"],
             "users": 420, "last_backup": "Success"},
            {"id": f"saas-{_hex()}", "name": "GWS-Corp", "type": "Google Workspace",
             "workloads": ["Gmail", "Drive", "Shared Drives"],
             "users": 180, "last_backup": "Success"},
        ],
        "plans": [
            {"id": f"plan-{_hex()}", "name": "Server-Gold", "type": "Server",
             "rpo_hours": 24, "retention_days": 30, "encryption": "AES-256-GCM",
             "secondary_copy": True, "workloads": 14},
        ],
        "report_defs": [
            {"id": f"rpt-{_hex()}", "name": "SLA Compliance", "source": "Jobs",
             "last_run": _now(), "rows": 24},
        ],
    }


def ensure_v2(state: dict) -> None:
    for k, v in seed_v2().items():
        if k not in state or state.get(k) is None:
            state[k] = v


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    if action == "enable_ransomware_protection":
        rw = state.setdefault("ransomware", seed_v2()["ransomware"])
        rw["enabled"] = True
        rw["threat_scan_last"] = _now()
        rw.setdefault("anomaly_events", []).insert(0, {
            "id": f"RAN-{_hex(4)}", "client": payload.get("client") or "fs-file01",
            "severity": "Info", "detail": "Protection scan completed", "time": _now(),
        })
        return {"ok": True, "message": "Ransomware protection scan completed", "ransomware": rw}

    if action == "create_k8s_backup":
        name = (payload.get("name") or f"k8s-{_hex(4)}").strip()
        item = {
            "id": f"k8s-{_hex()}", "name": name,
            "distribution": payload.get("distribution") or "EKS",
            "namespaces": payload.get("namespaces") or ["default"],
            "plan": payload.get("plan") or "K8s-Daily",
            "last_backup": "Pending", "pvcs": int(payload.get("pvcs") or 0),
        }
        state.setdefault("k8s_apps", []).append(item)
        return {"ok": True, "message": f"Registered Kubernetes app {name}", "app": item}

    if action == "create_plan":
        name = (payload.get("name") or f"Plan-{_hex(4)}").strip()
        item = {
            "id": f"plan-{_hex()}", "name": name,
            "type": payload.get("type") or "Server",
            "rpo_hours": int(payload.get("rpo_hours") or 24),
            "retention_days": int(payload.get("retention_days") or 30),
            "encryption": payload.get("encryption") or "AES-256-GCM",
            "secondary_copy": bool(payload.get("secondary_copy", True)),
            "workloads": 0,
        }
        state.setdefault("plans", []).append(item)
        return {"ok": True, "message": f"Created plan {name}", "plan": item}

    if action == "run_custom_report":
        name = (payload.get("name") or "Custom Report").strip()
        item = {
            "id": f"rpt-{_hex()}", "name": name,
            "source": payload.get("source") or "Jobs",
            "last_run": _now(), "rows": random.randint(10, 80),
        }
        state.setdefault("report_defs", []).insert(0, item)
        return {"ok": True, "message": f"Report '{name}' generated", "report": item}

    if action == "register_saas_app":
        name = (payload.get("name") or f"SaaS-{_hex(4)}").strip()
        item = {
            "id": f"saas-{_hex()}", "name": name,
            "type": payload.get("type") or "Microsoft 365",
            "workloads": payload.get("workloads") or ["Exchange"],
            "users": int(payload.get("users") or 10),
            "last_backup": "Pending",
        }
        state.setdefault("saas_apps", []).append(item)
        return {"ok": True, "message": f"Registered {name}", "app": item}

    return None
