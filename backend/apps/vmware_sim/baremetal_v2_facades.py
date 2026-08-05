"""Baremetal / MAAS V2 facades — spaces, tags, commissioning scripts.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
Keeps BMC as in-memory facade (real VirtualBMC deferred).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "spaces": [
            {"id": "sp-1", "name": "default", "subnets": ["10.10.1.0/24", "10.10.2.0/24"]},
            {"id": "sp-2", "name": "storage", "subnets": ["10.20.0.0/24"]},
        ],
        "tags": [
            {"name": "gpu", "definition": "true", "machines": ["gpu-node-01", "gpu-node-02"]},
            {"name": "storage", "definition": "true", "machines": ["storage-01"]},
            {"name": "needs-firmware", "definition": "", "machines": ["gpu-node-02"]},
        ],
        "commissioning_scripts": [
            {"name": "00-maas-01-dhcp-nic", "type": "commissioning", "applied_to": ["*"]},
            {"name": "20-maas-hardware-info", "type": "commissioning", "applied_to": ["*"]},
            {"name": "50-fixitlab-gpu-check", "type": "commissioning", "applied_to": ["gpu"]},
        ],
        "boot_resources": [
            {
                "name": "ubuntu/jammy",
                "architecture": "amd64/generic",
                "type": "Synced",
                "size_gb": 2.1,
                "status": "Synced",
                "source": "images.maas.io",
            },
            {
                "name": "ubuntu/noble",
                "architecture": "amd64/generic",
                "type": "Synced",
                "size_gb": 2.4,
                "status": "Synced",
                "source": "images.maas.io",
            },
        ],
    }


def ensure_v2(state: dict) -> None:
    maas = state.setdefault("maas", {})
    seed = seed_v2()
    for key, value in seed.items():
        if key not in maas or maas.get(key) is None:
            maas[key] = value


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)
    maas = state["maas"]

    if action == "maas_create_space":
        name = (payload.get("name") or f"space-{len(maas.get('spaces') or []) + 1}").strip()
        if any(s.get("name") == name for s in maas.get("spaces") or []):
            return {"ok": False, "error": f"Space '{name}' already exists"}
        subnet = payload.get("subnet") or f"10.{30 + len(maas.get('spaces') or [])}.0.0/24"
        row = {"id": f"sp-{len(maas.get('spaces') or []) + 1}", "name": name, "subnets": [subnet]}
        maas.setdefault("spaces", []).append(row)
        return {"ok": True, "message": f"Space {name} created", "space": row}

    if action == "maas_add_subnet":
        space_name = payload.get("space") or "default"
        space = next((s for s in maas.get("spaces") or [] if s.get("name") == space_name), None)
        if not space:
            return {"ok": False, "error": "Space not found"}
        cidr = (payload.get("subnet") or payload.get("cidr") or "10.99.0.0/24").strip()
        space.setdefault("subnets", []).append(cidr)
        return {"ok": True, "message": f"Added {cidr} to {space_name}", "space": space}

    if action == "maas_tag_machine":
        tag_name = (payload.get("tag") or "lab").strip()
        hostname = (payload.get("hostname") or payload.get("machine") or "").strip()
        if not hostname:
            machines = maas.get("machines") or []
            hostname = machines[0].get("hostname") if machines else ""
        if not hostname:
            return {"ok": False, "error": "Machine not found"}
        tags = maas.setdefault("tags", [])
        tag = next((t for t in tags if t.get("name") == tag_name), None)
        if not tag:
            tag = {"name": tag_name, "definition": payload.get("definition") or "", "machines": []}
            tags.append(tag)
        if hostname not in tag["machines"]:
            tag["machines"].append(hostname)
        # Mirror onto machine object if present.
        for m in maas.get("machines") or []:
            if m.get("hostname") == hostname:
                m.setdefault("tags", [])
                if tag_name not in m["tags"]:
                    m["tags"].append(tag_name)
        return {"ok": True, "message": f"Tagged {hostname} with {tag_name}", "tag": tag}

    if action == "maas_attach_script":
        name = (payload.get("name") or f"script-{len(maas.get('commissioning_scripts') or []) + 1}").strip()
        applied = payload.get("applied_to") or ["*"]
        if isinstance(applied, str):
            applied = [applied]
        row = {
            "name": name,
            "type": payload.get("type") or "commissioning",
            "applied_to": applied,
            "created": _now(),
        }
        scripts = maas.setdefault("commissioning_scripts", [])
        existing = next((s for s in scripts if s.get("name") == name), None)
        if existing:
            existing.update(row)
            row = existing
        else:
            scripts.append(row)
        return {"ok": True, "message": f"Commissioning script {name} attached", "script": row}

    if action in ("maas_publish_boot_resource", "maas_import_boot_resource", "packer_publish_maas"):
        sku = (payload.get("sku") or payload.get("name") or "h100").strip().lower()
        sku = sku.replace("custom/", "").replace("-jammy", "")
        name = (payload.get("boot_resource") or f"custom/{sku}-jammy").strip()
        arch = (payload.get("architecture") or "amd64/generic").strip()
        resources = maas.setdefault("boot_resources", [])
        existing = next((r for r in resources if r.get("name") == name), None)
        row = {
            "name": name,
            "architecture": arch,
            "type": "Uploaded",
            "size_gb": float(payload.get("size_gb") or 12.0),
            "status": "Synced",
            "source": payload.get("source") or f"packer output-gpu-{sku}/",
            "sku": sku,
            "published_at": _now(),
        }
        if existing:
            existing.update(row)
            row = existing
        else:
            resources.append(row)
        # Clear image-factory broken flag when present (Packer→MAAS graded labs).
        broken = state.get("broken")
        if isinstance(broken, dict):
            broken.pop("missing_boot_resource", None)
            broken.pop("packer_image_unpublished", None)
            if not broken:
                state["broken"] = {}
        return {
            "ok": True,
            "message": f"Published {name} to MAAS boot-resources",
            "boot_resource": row,
            "boot_resources": resources,
        }

    return None
