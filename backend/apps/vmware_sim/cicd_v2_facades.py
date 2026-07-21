"""CI/CD + GitOps V2 facades — Argo CD applications and Flux CD resources.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "argo_apps": [
            {
                "name": "api-server",
                "project": "default",
                "cluster": "in-cluster",
                "namespace": "production",
                "sync_status": "Synced",
                "health": "Healthy",
                "repo": "github.com/fixitlab/app",
                "path": "k8s/overlays/prod",
                "target_revision": "main",
                "auto_sync": True,
                "last_sync": _now(),
                "resources": [
                    {"kind": "Deployment", "name": "api-server", "status": "Synced", "health": "Healthy"},
                    {"kind": "Service", "name": "api-server", "status": "Synced", "health": "Healthy"},
                    {"kind": "ConfigMap", "name": "api-server-config", "status": "Synced", "health": "Healthy"},
                ],
            },
            {
                "name": "staging-api",
                "project": "staging",
                "cluster": "in-cluster",
                "namespace": "staging",
                "sync_status": "OutOfSync",
                "health": "Healthy",
                "repo": "github.com/fixitlab/app",
                "path": "k8s/overlays/staging",
                "target_revision": "develop",
                "auto_sync": False,
                "last_sync": None,
                "resources": [
                    {"kind": "Deployment", "name": "api-server", "status": "OutOfSync", "health": "Healthy"},
                    {"kind": "Service", "name": "api-server", "status": "Synced", "health": "Healthy"},
                ],
            },
        ],
        "flux": {
            "kustomizations": [
                {
                    "name": "apps",
                    "namespace": "flux-system",
                    "ready": True,
                    "revision": "main@sha1:abc1234",
                    "path": "./clusters/prod",
                    "interval": "5m",
                    "suspended": False,
                    "last_applied": _now(),
                },
                {
                    "name": "monitoring",
                    "namespace": "flux-system",
                    "ready": False,
                    "revision": "main@sha1:def5678",
                    "path": "./infra/monitoring",
                    "interval": "10m",
                    "suspended": False,
                    "last_applied": None,
                    "message": "dependency not ready",
                },
            ],
            "helm_releases": [
                {
                    "name": "prometheus",
                    "namespace": "monitoring",
                    "ready": True,
                    "chart": "prometheus-community/kube-prometheus-stack",
                    "version": "58.1.0",
                    "suspended": False,
                },
            ],
            "sources": [
                {"kind": "GitRepository", "name": "flux-system", "url": "https://github.com/fixitlab/gitops", "ready": True},
                {"kind": "HelmRepository", "name": "prometheus-community", "url": "https://prometheus-community.github.io/helm-charts", "ready": True},
            ],
            "image_automations": [
                {"name": "api-image", "image": "ghcr.io/fixitlab/api", "policy": "semver:^2", "last_update": "v2.3.1"},
            ],
        },
        "github": {
            "repo": "fixitlab/app",
            "default_branch": "main",
            "open_prs": 2,
            "open_issues": 5,
            "actions_runs": [
                {"id": 247, "workflow": "ci.yml", "status": "success", "branch": "main", "sha": "abc1234", "duration_s": 272},
                {"id": 246, "workflow": "security-scan.yml", "status": "failure", "branch": "main", "sha": "bcd5678", "duration_s": 43},
            ],
        },
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, dict) else dict(value)
        elif isinstance(value, dict) and isinstance(state.get(key), dict):
            for nested, nested_val in value.items():
                state[key].setdefault(nested, nested_val)


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "argo_sync":
        name = (payload.get("name") or "").strip()
        app = next((a for a in state.get("argo_apps") or [] if a.get("name") == name), None)
        if not app:
            return {"ok": False, "error": "Argo CD application not found"}
        app["sync_status"] = "Synced"
        app["health"] = "Healthy"
        app["last_sync"] = _now()
        for r in app.get("resources") or []:
            r["status"] = "Synced"
            r["health"] = "Healthy"
        return {"ok": True, "message": f"Synced {name}", "app": app}

    if action == "argo_create_app":
        name = (payload.get("name") or f"app-{(len(state.get('argo_apps') or []) + 1)}").strip()
        if any(a.get("name") == name for a in state.get("argo_apps") or []):
            return {"ok": False, "error": f"Application '{name}' already exists"}
        row = {
            "name": name,
            "project": payload.get("project") or "default",
            "cluster": "in-cluster",
            "namespace": payload.get("namespace") or "default",
            "sync_status": "Synced",
            "health": "Healthy",
            "repo": payload.get("repo") or "github.com/fixitlab/app",
            "path": payload.get("path") or "k8s/base",
            "target_revision": payload.get("revision") or "main",
            "auto_sync": bool(payload.get("auto_sync", True)),
            "last_sync": _now(),
            "resources": [
                {"kind": "Deployment", "name": name, "status": "Synced", "health": "Healthy"},
            ],
        }
        state.setdefault("argo_apps", []).append(row)
        return {"ok": True, "message": f"Created Argo CD app {name}", "app": row}

    if action == "flux_reconcile":
        name = (payload.get("name") or "").strip()
        flux = state.setdefault("flux", {})
        ks = next((k for k in flux.get("kustomizations") or [] if k.get("name") == name), None)
        if not ks:
            return {"ok": False, "error": "Kustomization not found"}
        ks["ready"] = True
        ks["message"] = ""
        ks["last_applied"] = _now()
        ks["revision"] = payload.get("revision") or ks.get("revision") or f"main@sha1:{_now()[-6:]}"
        return {"ok": True, "message": f"Reconciled Flux kustomization {name}", "kustomization": ks}

    if action == "flux_suspend":
        name = (payload.get("name") or "").strip()
        flux = state.setdefault("flux", {})
        ks = next((k for k in flux.get("kustomizations") or [] if k.get("name") == name), None)
        if not ks:
            return {"ok": False, "error": "Kustomization not found"}
        ks["suspended"] = bool(payload.get("suspended", True))
        return {"ok": True, "message": f"{'Suspended' if ks['suspended'] else 'Resumed'} {name}", "kustomization": ks}

    if action == "github_rerun_workflow":
        runs = (state.get("github") or {}).setdefault("actions_runs", [])
        run_id = payload.get("run_id")
        run = next((r for r in runs if r.get("id") == run_id), None)
        if not run and runs:
            run = runs[0]
        if not run:
            return {"ok": False, "error": "Workflow run not found"}
        run["status"] = "success"
        run["duration_s"] = int(payload.get("duration_s") or 180)
        return {"ok": True, "message": f"Re-ran workflow #{run['id']}", "run": run}

    return None
