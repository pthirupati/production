"""Kubernetes / OpenShift V2 facades — Ingress, NetworkPolicy, Helm, HPA, Routes, Projects.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "network_policies": [
            {
                "name": "deny-all-ingress",
                "namespace": "production",
                "pod_selector": {},
                "policy_types": ["Ingress"],
                "ingress": [],
            },
            {
                "name": "allow-frontend-to-api",
                "namespace": "production",
                "pod_selector": {"app": "api"},
                "policy_types": ["Ingress"],
                "ingress": [{"from": [{"podSelector": {"app": "frontend"}}], "ports": [{"port": 8080}]}],
            },
        ],
        "helm_releases": [
            {
                "name": "nginx-ingress",
                "namespace": "ingress-nginx",
                "chart": "ingress-nginx/ingress-nginx",
                "version": "4.10.0",
                "status": "deployed",
                "revision": 3,
                "updated": _now(),
            },
            {
                "name": "cert-manager",
                "namespace": "cert-manager",
                "chart": "jetstack/cert-manager",
                "version": "v1.14.4",
                "status": "deployed",
                "revision": 1,
                "updated": _now(),
            },
        ],
        "hpas": [
            {
                "name": "api",
                "namespace": "production",
                "target_ref": "Deployment/api",
                "min_replicas": 2,
                "max_replicas": 8,
                "current_replicas": 3,
                "cpu_target": 70,
            },
        ],
        # OpenShift-flavoured objects (also available on plain K8s labs).
        "openshift_projects": [
            {"name": "production", "display_name": "Production", "status": "Active"},
            {"name": "staging", "display_name": "Staging", "status": "Active"},
        ],
        "openshift_routes": [
            {
                "name": "api-route",
                "namespace": "production",
                "host": "api.apps.fixitlab.local",
                "to": "Service/api",
                "port": 8080,
                "tls": "edge",
                "status": "Admitted",
            },
        ],
        "openshift_builds": [
            {
                "name": "api-1",
                "namespace": "production",
                "from": "Dockerfile",
                "status": "Complete",
                "duration_s": 94,
                "started": _now(),
            },
        ],
        "sccs": [
            {"name": "anyuid", "users": ["system:serviceaccount:production:deployer"], "priority": 10},
            {"name": "restricted-v2", "users": ["system:authenticated"], "priority": 0},
        ],
    }


def ensure_v2(state: dict) -> None:
    seed = seed_v2()
    for key, value in seed.items():
        if key not in state or state.get(key) is None:
            state[key] = value


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "create_ingress":
        name = (payload.get("name") or f"ing-{len(state.get('ingresses') or []) + 1}").strip()
        ns = payload.get("namespace") or "production"
        if any(i.get("name") == name and i.get("namespace") == ns for i in state.get("ingresses") or []):
            return {"ok": False, "error": f"Ingress '{name}' already exists"}
        row = {
            "name": name,
            "namespace": ns,
            "className": payload.get("className") or "nginx",
            "rules": payload.get("rules") or [
                {"host": payload.get("host") or f"{name}.fixitlab.io", "path": "/", "service": payload.get("service") or "frontend", "port": int(payload.get("port") or 80)},
            ],
            "tls": payload.get("tls") or [],
            "creationTimestamp": _now(),
        }
        state.setdefault("ingresses", []).append(row)
        return {"ok": True, "message": f"ingress/{name} created", "ingress": row}

    if action == "create_network_policy":
        name = (payload.get("name") or f"np-{len(state.get('network_policies') or []) + 1}").strip()
        ns = payload.get("namespace") or "production"
        row = {
            "name": name,
            "namespace": ns,
            "pod_selector": payload.get("pod_selector") or {"app": payload.get("app") or "api"},
            "policy_types": payload.get("policy_types") or ["Ingress"],
            "ingress": payload.get("ingress") or [{"from": [{"podSelector": {"app": "frontend"}}], "ports": [{"port": 8080}]}],
        }
        state.setdefault("network_policies", []).append(row)
        return {"ok": True, "message": f"networkpolicy/{name} created", "network_policy": row}

    if action == "helm_install":
        name = (payload.get("name") or f"rel-{len(state.get('helm_releases') or []) + 1}").strip()
        if any(r.get("name") == name for r in state.get("helm_releases") or []):
            return {"ok": False, "error": f"Release '{name}' already exists"}
        row = {
            "name": name,
            "namespace": payload.get("namespace") or "default",
            "chart": payload.get("chart") or "bitnami/nginx",
            "version": payload.get("version") or "15.0.0",
            "status": "deployed",
            "revision": 1,
            "updated": _now(),
        }
        state.setdefault("helm_releases", []).append(row)
        return {"ok": True, "message": f"Helm release {name} deployed", "release": row}

    if action == "create_hpa":
        name = (payload.get("name") or payload.get("target") or "app").strip()
        ns = payload.get("namespace") or "production"
        if any(h.get("name") == name and h.get("namespace") == ns for h in state.get("hpas") or []):
            return {"ok": False, "error": f"HPA '{name}' already exists"}
        row = {
            "name": name,
            "namespace": ns,
            "target_ref": payload.get("target_ref") or f"Deployment/{name}",
            "min_replicas": int(payload.get("min_replicas") or 1),
            "max_replicas": int(payload.get("max_replicas") or 5),
            "current_replicas": int(payload.get("current_replicas") or 1),
            "cpu_target": int(payload.get("cpu_target") or 70),
        }
        state.setdefault("hpas", []).append(row)
        return {"ok": True, "message": f"hpa/{name} created", "hpa": row}

    if action == "create_role_binding":
        name = (payload.get("name") or f"rb-{len(state.get('role_bindings') or []) + 1}").strip()
        ns = payload.get("namespace") or "production"
        row = {
            "name": name,
            "namespace": ns,
            "roleRef": {"kind": "Role", "name": payload.get("role") or "secret-reader", "apiGroup": "rbac.authorization.k8s.io"},
            "subjects": [{"kind": payload.get("subject_kind") or "ServiceAccount", "name": payload.get("subject") or "default", "namespace": ns}],
        }
        state.setdefault("role_bindings", []).append(row)
        return {"ok": True, "message": f"rolebinding/{name} created", "role_binding": row}

    if action == "create_openshift_project":
        name = (payload.get("name") or f"proj-{len(state.get('openshift_projects') or []) + 1}").strip()
        if any(p.get("name") == name for p in state.get("openshift_projects") or []):
            return {"ok": False, "error": f"Project '{name}' already exists"}
        row = {
            "name": name,
            "display_name": payload.get("display_name") or name.title(),
            "status": "Active",
        }
        state.setdefault("openshift_projects", []).append(row)
        # Mirror as namespace if missing.
        if not any(n.get("name") == name for n in state.get("namespaces") or []):
            state.setdefault("namespaces", []).append({
                "name": name, "status": "Active", "labels": {"openshift.io/cluster-monitoring": "true"},
                "creationTimestamp": _now(),
            })
        return {"ok": True, "message": f"Project {name} created", "project": row}

    if action == "create_openshift_route":
        name = (payload.get("name") or f"route-{len(state.get('openshift_routes') or []) + 1}").strip()
        ns = payload.get("namespace") or "production"
        row = {
            "name": name,
            "namespace": ns,
            "host": payload.get("host") or f"{name}.apps.fixitlab.local",
            "to": payload.get("to") or f"Service/{payload.get('service') or 'api'}",
            "port": int(payload.get("port") or 8080),
            "tls": payload.get("tls") or "edge",
            "status": "Admitted",
        }
        state.setdefault("openshift_routes", []).append(row)
        return {"ok": True, "message": f"Route {name} created", "route": row}

    if action == "start_openshift_build":
        name = (payload.get("name") or "api").strip()
        ns = payload.get("namespace") or "production"
        builds = state.setdefault("openshift_builds", [])
        num = sum(1 for b in builds if str(b.get("name", "")).startswith(f"{name}-")) + 1
        row = {
            "name": f"{name}-{num}",
            "namespace": ns,
            "from": payload.get("from") or "Dockerfile",
            "status": "Complete",
            "duration_s": int(payload.get("duration_s") or 60),
            "started": _now(),
        }
        builds.insert(0, row)
        return {"ok": True, "message": f"Build {row['name']} completed", "build": row}

    return None
