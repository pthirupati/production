"""OpenStack Horizon V2 facades — Heat, Neutron routers, Octavia, keypairs, snapshots."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

_HEX = "0123456789abcdef"


def _hex(n: int = 8) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _uuid() -> str:
    return f"{_hex(8)}-{_hex(4)}-{_hex(4)}-{_hex(4)}-{_hex(12)}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "routers": [
            {
                "id": _uuid(), "name": "router1", "status": "ACTIVE",
                "external_network": "public", "admin_state": True,
                "ha": True, "distributed": False,
                "interfaces": [{"subnet": "private-subnet", "ip": "10.0.0.1"}],
                "routes": [],
            },
        ],
        "keypairs": [
            {"name": "lab-key", "fingerprint": "SHA256:abc123def456", "type": "ssh"},
        ],
        "server_groups": [
            {"id": _uuid(), "name": "anti-affinity-web", "policy": "anti-affinity", "members": 0},
        ],
        "load_balancers": [
            {
                "id": _uuid(), "name": "lb-web", "vip": "10.0.0.50",
                "status": "ACTIVE", "provisioning": "ACTIVE",
                "listeners": [{"protocol": "HTTP", "port": 80}],
                "pool": {"algorithm": "ROUND_ROBIN", "protocol": "HTTP", "members": 2},
            },
        ],
        "volume_snapshots": [
            {
                "id": _uuid(), "name": "snap-db-01", "volume": "vol-db",
                "size_gb": 40, "status": "available", "created": _now(),
            },
        ],
        "heat_stacks": [
            {
                "id": _uuid(), "name": "web-tier",
                "status": "CREATE_COMPLETE",
                "created": _now(),
                "updated": _now(),
                "resources": [
                    {"name": "web_server", "type": "OS::Nova::Server", "status": "CREATE_COMPLETE"},
                    {"name": "web_floating_ip", "type": "OS::Neutron::FloatingIP", "status": "CREATE_COMPLETE"},
                ],
                "parameters": {"image": "ubuntu-22.04", "flavor": "m1.medium"},
            },
        ],
        "object_containers": [
            {"name": "lab-artifacts", "objects": 12, "bytes": 48200000, "public": False},
        ],
        "hypervisors": [
            {"hostname": "compute01", "type": "QEMU", "vcpus_used": 8, "vcpus": 32, "ram_used_gb": 24, "ram_gb": 128, "vms": 4, "status": "up"},
            {"hostname": "compute02", "type": "QEMU", "vcpus_used": 4, "vcpus": 32, "ram_used_gb": 12, "ram_gb": 128, "vms": 2, "status": "up"},
        ],
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "create_router":
        name = (payload.get("name") or f"router-{_hex(4)}").strip()
        if any(r.get("name") == name for r in state.get("routers") or []):
            return {"ok": False, "error": f"Router '{name}' already exists"}
        row = {
            "id": _uuid(), "name": name, "status": "ACTIVE",
            "external_network": payload.get("external_network") or "public",
            "admin_state": True, "ha": bool(payload.get("ha", True)),
            "distributed": bool(payload.get("distributed")),
            "interfaces": [], "routes": [],
        }
        state.setdefault("routers", []).append(row)
        return {"ok": True, "message": f"Created router {name}", "router": row}

    if action == "add_router_interface":
        router = next((r for r in state.get("routers") or [] if r.get("name") == payload.get("name") or r.get("id") == payload.get("router_id")), None)
        if not router:
            return {"ok": False, "error": "Router not found"}
        subnet = payload.get("subnet") or "private-subnet"
        ip = payload.get("ip") or f"10.0.0.{random.randint(2, 50)}"
        router.setdefault("interfaces", []).append({"subnet": subnet, "ip": ip})
        return {"ok": True, "message": f"Added interface on {router['name']}", "router": router}

    if action == "create_keypair":
        name = (payload.get("name") or f"key-{_hex(4)}").strip()
        if any(k.get("name") == name for k in state.get("keypairs") or []):
            return {"ok": False, "error": f"Keypair '{name}' already exists"}
        row = {"name": name, "fingerprint": f"SHA256:{_hex(12)}", "type": payload.get("type") or "ssh"}
        state.setdefault("keypairs", []).append(row)
        return {"ok": True, "message": f"Created keypair {name}", "keypair": row}

    if action == "create_load_balancer":
        name = (payload.get("name") or f"lb-{_hex(4)}").strip()
        row = {
            "id": _uuid(), "name": name,
            "vip": payload.get("vip") or f"10.0.0.{random.randint(50, 200)}",
            "status": "ACTIVE", "provisioning": "ACTIVE",
            "listeners": [{"protocol": payload.get("protocol") or "HTTP", "port": int(payload.get("port") or 80)}],
            "pool": {
                "algorithm": payload.get("algorithm") or "ROUND_ROBIN",
                "protocol": payload.get("protocol") or "HTTP",
                "members": int(payload.get("members") or 1),
            },
        }
        state.setdefault("load_balancers", []).append(row)
        return {"ok": True, "message": f"Created load balancer {name}", "load_balancer": row}

    if action == "create_volume_snapshot":
        vol_name = payload.get("volume") or payload.get("name") or "vol-db"
        snap_name = (payload.get("snapshot_name") or f"snap-{_hex(4)}").strip()
        row = {
            "id": _uuid(), "name": snap_name, "volume": vol_name,
            "size_gb": int(payload.get("size_gb") or 40),
            "status": "available", "created": _now(),
        }
        state.setdefault("volume_snapshots", []).append(row)
        return {"ok": True, "message": f"Created snapshot {snap_name}", "snapshot": row}

    if action == "create_heat_stack":
        name = (payload.get("name") or f"stack-{_hex(4)}").strip()
        if any(s.get("name") == name for s in state.get("heat_stacks") or []):
            return {"ok": False, "error": f"Stack '{name}' already exists"}
        row = {
            "id": _uuid(), "name": name, "status": "CREATE_COMPLETE",
            "created": _now(), "updated": _now(),
            "resources": [
                {"name": "server", "type": "OS::Nova::Server", "status": "CREATE_COMPLETE"},
            ],
            "parameters": payload.get("parameters") or {"image": "ubuntu-22.04", "flavor": "m1.small"},
            "template_preview": (payload.get("template") or "")[:500],
        }
        state.setdefault("heat_stacks", []).append(row)
        return {"ok": True, "message": f"Created Heat stack {name}", "stack": row}

    if action == "delete_heat_stack":
        name = payload.get("name") or ""
        stacks = state.get("heat_stacks") or []
        before = len(stacks)
        state["heat_stacks"] = [s for s in stacks if s.get("name") != name and s.get("id") != name]
        if len(state["heat_stacks"]) == before:
            return {"ok": False, "error": "Stack not found"}
        return {"ok": True, "message": f"Deleted stack {name}"}

    if action == "create_object_container":
        name = (payload.get("name") or f"container-{_hex(4)}").strip()
        if any(c.get("name") == name for c in state.get("object_containers") or []):
            return {"ok": False, "error": f"Container '{name}' already exists"}
        row = {"name": name, "objects": 0, "bytes": 0, "public": bool(payload.get("public"))}
        state.setdefault("object_containers", []).append(row)
        return {"ok": True, "message": f"Created container {name}", "container": row}

    return None
