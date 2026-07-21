"""Docker Engine V2 facades — Swarm services, secrets, configs, local registry.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "swarm": {
            "active": True,
            "node_id": "node-manager-01",
            "managers": 1,
            "workers": 2,
        },
        "swarm_services": [
            {
                "id": "svc-web",
                "name": "web",
                "image": "nginx:1.25",
                "replicas": 3,
                "ports": "80:80",
                "mode": "replicated",
                "status": "Running",
            },
            {
                "id": "svc-api",
                "name": "api",
                "image": "fixitlab/api:2.1",
                "replicas": 2,
                "ports": "8080:8080",
                "mode": "replicated",
                "status": "Running",
            },
        ],
        "secrets": [
            {"id": "sec-db", "name": "db_password", "created": _now(), "updated": _now()},
            {"id": "sec-jwt", "name": "jwt_signing_key", "created": _now(), "updated": _now()},
        ],
        "configs": [
            {"id": "cfg-nginx", "name": "nginx_conf", "created": _now()},
        ],
        "registry": {
            "url": "localhost:5000",
            "images": [
                {"name": "localhost:5000/fixitlab/api", "tag": "2.1", "size_mb": 186, "pushed": _now()},
                {"name": "localhost:5000/fixitlab/web", "tag": "1.4", "size_mb": 42, "pushed": _now()},
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

    if action == "swarm_init":
        swarm = state.setdefault("swarm", {})
        swarm["active"] = True
        swarm["node_id"] = swarm.get("node_id") or "node-manager-01"
        swarm["managers"] = int(payload.get("managers") or max(swarm.get("managers") or 1, 1))
        swarm["workers"] = int(payload.get("workers") or swarm.get("workers") or 0)
        return {"ok": True, "message": "Swarm initialized", "swarm": swarm}

    if action == "create_swarm_service":
        name = (payload.get("name") or f"svc-{len(state.get('swarm_services') or []) + 1}").strip()
        if any(s.get("name") == name for s in state.get("swarm_services") or []):
            return {"ok": False, "error": f"Service '{name}' already exists"}
        row = {
            "id": f"svc-{name}",
            "name": name,
            "image": payload.get("image") or "nginx:alpine",
            "replicas": int(payload.get("replicas") or 1),
            "ports": payload.get("ports") or "",
            "mode": payload.get("mode") or "replicated",
            "status": "Running",
        }
        state.setdefault("swarm_services", []).append(row)
        return {"ok": True, "message": f"Service {name} created", "service": row}

    if action == "scale_swarm_service":
        name = payload.get("name") or ""
        svc = next((s for s in state.get("swarm_services") or [] if s.get("name") == name), None)
        if not svc:
            return {"ok": False, "error": "Service not found"}
        svc["replicas"] = max(0, int(payload.get("replicas") or svc.get("replicas") or 1))
        return {"ok": True, "message": f"Scaled {name} to {svc['replicas']}", "service": svc}

    if action == "create_secret":
        name = (payload.get("name") or f"secret_{len(state.get('secrets') or []) + 1}").strip()
        if any(s.get("name") == name for s in state.get("secrets") or []):
            return {"ok": False, "error": f"Secret '{name}' already exists"}
        row = {"id": f"sec-{name}", "name": name, "created": _now(), "updated": _now()}
        state.setdefault("secrets", []).append(row)
        return {"ok": True, "message": f"Secret {name} created", "secret": row}

    if action == "create_config":
        name = (payload.get("name") or f"config_{len(state.get('configs') or []) + 1}").strip()
        if any(c.get("name") == name for c in state.get("configs") or []):
            return {"ok": False, "error": f"Config '{name}' already exists"}
        row = {"id": f"cfg-{name}", "name": name, "created": _now()}
        state.setdefault("configs", []).append(row)
        return {"ok": True, "message": f"Config {name} created", "config": row}

    if action == "registry_push":
        name = (payload.get("name") or "localhost:5000/fixitlab/app").strip()
        tag = payload.get("tag") or "latest"
        reg = state.setdefault("registry", {"url": "localhost:5000", "images": []})
        images = reg.setdefault("images", [])
        existing = next((i for i in images if i.get("name") == name and i.get("tag") == tag), None)
        if existing:
            existing["pushed"] = _now()
            existing["size_mb"] = int(payload.get("size_mb") or existing.get("size_mb") or 64)
            row = existing
        else:
            row = {"name": name, "tag": tag, "size_mb": int(payload.get("size_mb") or 64), "pushed": _now()}
            images.insert(0, row)
        return {"ok": True, "message": f"Pushed {name}:{tag}", "image": row}

    if action == "registry_pull":
        name = (payload.get("name") or "").strip()
        tag = payload.get("tag") or "latest"
        reg = state.get("registry") or {}
        img = next((i for i in (reg.get("images") or []) if i.get("name") == name and i.get("tag") == tag), None)
        if not img and (reg.get("images") or []):
            img = reg["images"][0]
            name, tag = img["name"], img["tag"]
        if not img:
            return {"ok": False, "error": "Image not in registry"}
        # Mirror into daemon images list if present.
        ref = f"{name}:{tag}"
        images = state.setdefault("images", [])
        if not any(i.get("repoTags") == [ref] or i.get("name") == ref or ref in (i.get("repoTags") or []) for i in images):
            images.insert(0, {
                "id": f"sha256:{len(images):08x}",
                "repoTags": [ref],
                "sizeMb": img.get("size_mb") or 64,
                "dangling": False,
                "created": _now(),
            })
        return {"ok": True, "message": f"Pulled {ref}", "image": img}

    return None
