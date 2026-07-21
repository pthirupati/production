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
            "issues": [
                {
                    "number": 42, "title": "Flaky deploy job on staging",
                    "state": "open", "author": "ops-bot", "labels": ["bug", "ci"],
                    "created": "2024-06-10T12:00:00Z", "assignees": ["alice"],
                },
                {
                    "number": 41, "title": "Document Flux image automation",
                    "state": "open", "author": "docs", "labels": ["docs"],
                    "created": "2024-06-08T09:30:00Z", "assignees": [],
                },
                {
                    "number": 38, "title": "Bump kube-prometheus-stack",
                    "state": "closed", "author": "alice", "labels": ["deps"],
                    "created": "2024-05-20T16:00:00Z", "assignees": ["bob"],
                },
            ],
            "pull_requests": [
                {
                    "number": 88, "title": "feat: add canary rollout for api-server",
                    "state": "open", "author": "alice", "base": "main", "head": "feat/canary",
                    "checks": "pending", "review": "approved", "created": "2024-06-18T10:00:00Z",
                },
                {
                    "number": 87, "title": "fix: harden security-scan workflow",
                    "state": "open", "author": "bob", "base": "main", "head": "fix/gha-scan",
                    "checks": "failure", "review": "changes_requested", "created": "2024-06-17T14:22:00Z",
                },
                {
                    "number": 80, "title": "chore: bump actions/checkout to v4",
                    "state": "merged", "author": "ops-bot", "base": "main", "head": "chore/checkout-v4",
                    "checks": "success", "review": "approved", "created": "2024-06-01T08:00:00Z",
                },
            ],
        },
        "pipeline_secrets": [
            {"name": "GITHUB_TOKEN", "scope": "repository", "updated": "2d ago", "empty": False},
            {"name": "REGISTRY_TOKEN", "scope": "repository", "updated": "5d ago", "empty": True},
            {"name": "KUBE_TOKEN", "scope": "environment:production", "updated": "1w ago", "empty": False},
        ],
        "pipeline_variables": [
            {"name": "NODE_VERSION", "value": "18", "scope": "repository"},
            {"name": "DEPLOY_REGION", "value": "us-east-1", "scope": "repository"},
            {"name": "IMAGE_TAG", "value": "main", "scope": "environment:staging"},
        ],
        "pipeline_environments": [
            {"name": "staging", "protection": False, "url": "https://staging.fixitlab.local", "deployment": None},
            {"name": "production", "protection": True, "url": "https://app.fixitlab.local", "deployment": None},
        ],
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
        kind = (payload.get("kind") or "kustomization").lower()
        if kind in ("helmrelease", "helm_release", "helm"):
            hr = next((h for h in flux.get("helm_releases") or [] if h.get("name") == name), None)
            if not hr and flux.get("helm_releases"):
                hr = flux["helm_releases"][0]
            if not hr:
                return {"ok": False, "error": "HelmRelease not found"}
            hr["suspended"] = bool(payload.get("suspended", True))
            return {"ok": True, "message": f"{'Suspended' if hr['suspended'] else 'Resumed'} HelmRelease {hr['name']}", "helm_release": hr}
        ks = next((k for k in flux.get("kustomizations") or [] if k.get("name") == name), None)
        if not ks:
            return {"ok": False, "error": "Kustomization not found"}
        ks["suspended"] = bool(payload.get("suspended", True))
        return {"ok": True, "message": f"{'Suspended' if ks['suspended'] else 'Resumed'} {name}", "kustomization": ks}

    if action == "flux_helm_reconcile":
        name = (payload.get("name") or "").strip()
        flux = state.setdefault("flux", {})
        hr = next((h for h in flux.get("helm_releases") or [] if h.get("name") == name), None)
        if not hr and flux.get("helm_releases"):
            hr = flux["helm_releases"][0]
        if not hr:
            return {"ok": False, "error": "HelmRelease not found"}
        hr["ready"] = True
        hr["suspended"] = False
        hr["last_applied"] = _now()
        return {"ok": True, "message": f"Reconciled HelmRelease {hr['name']}", "helm_release": hr}

    if action == "flux_create_kustomization":
        name = (payload.get("name") or f"ks-{len(state.get('flux', {}).get('kustomizations') or []) + 1}").strip()
        flux = state.setdefault("flux", {})
        if any(k.get("name") == name for k in flux.get("kustomizations") or []):
            return {"ok": False, "error": f"Kustomization '{name}' already exists"}
        row = {
            "name": name,
            "namespace": payload.get("namespace") or "flux-system",
            "ready": bool(payload.get("ready", True)),
            "revision": payload.get("revision") or f"main@sha1:{_now()[-6:]}",
            "path": payload.get("path") or f"./clusters/{name}",
            "interval": payload.get("interval") or "5m",
            "suspended": False,
            "last_applied": _now(),
        }
        flux.setdefault("kustomizations", []).append(row)
        return {"ok": True, "message": f"Created Flux kustomization {name}", "kustomization": row}

    if action == "flux_create_helmrelease":
        name = (payload.get("name") or f"hr-{len(state.get('flux', {}).get('helm_releases') or []) + 1}").strip()
        flux = state.setdefault("flux", {})
        if any(h.get("name") == name for h in flux.get("helm_releases") or []):
            return {"ok": False, "error": f"HelmRelease '{name}' already exists"}
        row = {
            "name": name,
            "namespace": payload.get("namespace") or "default",
            "ready": bool(payload.get("ready", True)),
            "chart": payload.get("chart") or f"{name}/chart",
            "version": payload.get("version") or "1.0.0",
            "suspended": False,
            "last_applied": _now(),
        }
        flux.setdefault("helm_releases", []).append(row)
        return {"ok": True, "message": f"Created HelmRelease {name}", "helm_release": row}

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

    if action == "github_create_issue":
        gh = state.setdefault("github", {})
        issues = gh.setdefault("issues", [])
        number = max((i.get("number") or 0 for i in issues), default=40) + 1
        row = {
            "number": number,
            "title": (payload.get("title") or f"Issue {number}").strip(),
            "state": "open",
            "author": payload.get("author") or "lab-user",
            "labels": payload.get("labels") or ["triage"],
            "created": _now(),
            "assignees": payload.get("assignees") or [],
        }
        issues.insert(0, row)
        gh["open_issues"] = sum(1 for i in issues if i.get("state") == "open")
        return {"ok": True, "message": f"Opened issue #{number}", "issue": row}

    if action == "github_close_issue":
        gh = state.setdefault("github", {})
        number = int(payload.get("number") or 0)
        issue = next((i for i in gh.get("issues") or [] if i.get("number") == number), None)
        if not issue:
            return {"ok": False, "error": "Issue not found"}
        issue["state"] = "closed"
        gh["open_issues"] = sum(1 for i in (gh.get("issues") or []) if i.get("state") == "open")
        return {"ok": True, "message": f"Closed issue #{number}", "issue": issue}

    if action == "github_create_pr":
        gh = state.setdefault("github", {})
        prs = gh.setdefault("pull_requests", [])
        number = max((p.get("number") or 0 for p in prs), default=80) + 1
        row = {
            "number": number,
            "title": (payload.get("title") or f"PR {number}").strip(),
            "state": "open",
            "author": payload.get("author") or "lab-user",
            "base": payload.get("base") or gh.get("default_branch") or "main",
            "head": payload.get("head") or f"feature/{number}",
            "checks": "pending",
            "review": "pending",
            "created": _now(),
        }
        prs.insert(0, row)
        gh["open_prs"] = sum(1 for p in prs if p.get("state") == "open")
        return {"ok": True, "message": f"Opened PR #{number}", "pull_request": row}

    if action == "github_merge_pr":
        gh = state.setdefault("github", {})
        number = int(payload.get("number") or 0)
        pr = next((p for p in gh.get("pull_requests") or [] if p.get("number") == number), None)
        if not pr:
            return {"ok": False, "error": "Pull request not found"}
        if pr.get("state") == "merged":
            return {"ok": False, "error": "PR already merged"}
        pr["state"] = "merged"
        pr["checks"] = "success"
        pr["review"] = "approved"
        gh["open_prs"] = sum(1 for p in (gh.get("pull_requests") or []) if p.get("state") == "open")
        return {"ok": True, "message": f"Merged PR #{number}", "pull_request": pr}

    if action == "github_approve_pr":
        gh = state.setdefault("github", {})
        number = int(payload.get("number") or 0)
        pr = next((p for p in gh.get("pull_requests") or [] if p.get("number") == number), None)
        if not pr:
            return {"ok": False, "error": "Pull request not found"}
        pr["review"] = "approved"
        if pr.get("checks") == "failure":
            pr["checks"] = "success"
        return {"ok": True, "message": f"Approved PR #{number}", "pull_request": pr}

    if action == "upsert_secret":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Secret name required"}
        secrets = state.setdefault("pipeline_secrets", [])
        row = next((s for s in secrets if s.get("name") == name), None)
        if row:
            row["empty"] = bool(payload.get("empty", False))
            row["updated"] = "just now"
            row["scope"] = payload.get("scope") or row.get("scope") or "repository"
        else:
            row = {
                "name": name,
                "scope": payload.get("scope") or "repository",
                "updated": "just now",
                "empty": bool(payload.get("empty", False)),
            }
            secrets.append(row)
        return {"ok": True, "message": f"Secret {name} saved", "secret": row}

    if action == "delete_secret":
        name = (payload.get("name") or "").strip()
        before = len(state.get("pipeline_secrets") or [])
        state["pipeline_secrets"] = [s for s in (state.get("pipeline_secrets") or []) if s.get("name") != name]
        if len(state["pipeline_secrets"]) == before:
            return {"ok": False, "error": "Secret not found"}
        return {"ok": True, "message": f"Deleted secret {name}"}

    if action == "upsert_variable":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Variable name required"}
        variables = state.setdefault("pipeline_variables", [])
        row = next((v for v in variables if v.get("name") == name), None)
        if row:
            if "value" in payload:
                row["value"] = payload.get("value")
            row["scope"] = payload.get("scope") or row.get("scope") or "repository"
        else:
            row = {
                "name": name,
                "value": payload.get("value") or "",
                "scope": payload.get("scope") or "repository",
            }
            variables.append(row)
        return {"ok": True, "message": f"Variable {name} saved", "variable": row}

    if action == "delete_variable":
        name = (payload.get("name") or "").strip()
        before = len(state.get("pipeline_variables") or [])
        state["pipeline_variables"] = [v for v in (state.get("pipeline_variables") or []) if v.get("name") != name]
        if len(state["pipeline_variables"]) == before:
            return {"ok": False, "error": "Variable not found"}
        return {"ok": True, "message": f"Deleted variable {name}"}

    if action == "upsert_environment":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Environment name required"}
        envs = state.setdefault("pipeline_environments", [])
        row = next((e for e in envs if e.get("name") == name), None)
        if row:
            if "deployment" in payload:
                row["deployment"] = payload.get("deployment")
            if "url" in payload:
                row["url"] = payload.get("url")
            if "protection" in payload:
                row["protection"] = bool(payload.get("protection"))
        else:
            row = {
                "name": name,
                "protection": bool(payload.get("protection")),
                "url": payload.get("url") or "",
                "deployment": payload.get("deployment"),
            }
            envs.append(row)
        return {"ok": True, "message": f"Environment {name} saved", "environment": row}

    if action == "clear_environment_deployment":
        name = (payload.get("name") or "").strip()
        env = next((e for e in state.get("pipeline_environments") or [] if e.get("name") == name), None)
        if not env:
            return {"ok": False, "error": "Environment not found"}
        env["deployment"] = None
        return {"ok": True, "message": f"Rolled back {name}", "environment": env}

    return None
