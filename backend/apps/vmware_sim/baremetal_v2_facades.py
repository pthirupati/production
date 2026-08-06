"""Baremetal / MAAS V2 facades — spaces, tags, scripts, devices, images, DHCP.

Lab Environment / Lab Server — Canonical MAAS–shaped region state.
BMC power and inventory live in-process with ServerIdentity (no separate seed).
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
            {"name": "gpu", "definition": "true", "comment": "GPU nodes", "machines": ["gpu-node-01", "gpu-node-02"]},
            {"name": "storage", "definition": "true", "machines": ["storage-01"]},
            {"name": "needs-firmware", "definition": "", "machines": ["gpu-node-02"]},
            {
                "name": "kernel-opts-iommu",
                "definition": "//node[not(hardware/gpu)]",
                "kernel_options": "intel_iommu=on",
                "machines": [],
            },
        ],
        "commissioning_scripts": [
            {"name": "00-maas-01-dhcp-nic", "type": "commissioning", "applied_to": ["*"]},
            {"name": "20-maas-hardware-info", "type": "commissioning", "applied_to": ["*"]},
            {"name": "50-fixitlab-gpu-check", "type": "commissioning", "applied_to": ["gpu"]},
            {"name": "60-gpu-sanity", "type": "testing", "applied_to": ["gpu"]},
        ],
        "boot_resources": [
            {
                "name": "ubuntu/jammy",
                "architecture": "amd64/generic",
                "type": "Synced",
                "size_gb": 2.1,
                "status": "Synced",
                "source": "images.maas.io",
                "title": "Ubuntu 22.04 LTS",
            },
            {
                "name": "ubuntu/noble",
                "architecture": "amd64/generic",
                "type": "Synced",
                "size_gb": 2.4,
                "status": "Synced",
                "source": "images.maas.io",
                "title": "Ubuntu 24.04 LTS",
            },
        ],
        "image_stream": {
            "url": "https://images.maas.io/ephemeral-v3/stable/",
            "last_sync": None,
            "syncing": False,
            "selected": ["ubuntu/jammy", "ubuntu/noble"],
        },
    }


def ensure_v2(state: dict) -> None:
    maas = state.setdefault("maas", {})
    seed = seed_v2()
    for key, value in seed.items():
        if key not in maas or maas.get(key) is None:
            maas[key] = value
    if "devices" not in state and "devices" not in maas:
        state["devices"] = [
            {
                "id": "dev-1",
                "hostname": "mgmt-switch-01",
                "ip": "10.10.1.2",
                "mac": "52:54:00:11:22:01",
                "zone": "default",
                "owner": "admin",
                "parent": "",
                "type": "switch",
            },
        ]
        maas["devices"] = list(state["devices"])
    elif "devices" not in maas and state.get("devices"):
        maas["devices"] = list(state["devices"])
    # Prefer maas.dhcp as canonical. After JSON cache round-trips, state["dhcp"]
    # and maas["dhcp"] can become separate objects — never let a stale top-level
    # copy overwrite region state (breaks enable/disable persistence).
    if isinstance(maas.get("dhcp"), dict):
        dhcp = maas["dhcp"]
    else:
        dhcp = state.get("dhcp") if isinstance(state.get("dhcp"), dict) else {}
        maas["dhcp"] = dhcp
    dhcp.setdefault("enabled", True)
    dhcp.setdefault("vlan", "untagged")
    dhcp.setdefault("primary_rack", "rack-1")
    dhcp.setdefault("secondary_rack", "")
    dhcp.setdefault("dynamic_ranges", ["10.10.1.100-10.10.1.200"])
    dhcp.setdefault("snippets", [])
    state["dhcp"] = dhcp
    maas["dhcp"] = dhcp


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
            tag = {
                "name": tag_name,
                "definition": payload.get("definition") or "",
                "kernel_options": payload.get("kernel_options") or "",
                "machines": [],
            }
            tags.append(tag)
        if hostname not in tag["machines"]:
            tag["machines"].append(hostname)
        for m in maas.get("machines") or []:
            if m.get("hostname") == hostname:
                m.setdefault("tags", [])
                if tag_name not in m["tags"]:
                    m["tags"].append(tag_name)
        return {"ok": True, "message": f"Tagged {hostname} with {tag_name}", "tag": tag}

    if action == "maas_create_tag":
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "Tag name required"}
        tags = maas.setdefault("tags", [])
        if any(t.get("name") == name for t in tags):
            return {"ok": False, "error": f"Tag '{name}' already exists"}
        row = {
            "name": name,
            "definition": payload.get("definition") or "",
            "kernel_options": payload.get("kernel_options") or "",
            "comment": payload.get("comment") or "",
            "machines": [],
        }
        tags.append(row)
        return {"ok": True, "message": f"Tag {name} created", "tag": row}

    if action == "maas_attach_script":
        name = (payload.get("name") or f"script-{len(maas.get('commissioning_scripts') or []) + 1}").strip()
        applied = payload.get("applied_to") or ["*"]
        if isinstance(applied, str):
            applied = [applied]
        row = {
            "name": name,
            "type": payload.get("type") or "commissioning",
            "applied_to": applied,
            "script": payload.get("script") or payload.get("content") or "",
            "created": _now(),
        }
        scripts = maas.setdefault("commissioning_scripts", [])
        existing = next((s for s in scripts if s.get("name") == name), None)
        if existing:
            existing.update(row)
            row = existing
        else:
            scripts.append(row)
        broken = state.get("broken")
        if isinstance(broken, dict):
            broken.pop("scripts_unattached", None)
        return {"ok": True, "message": f"Script {name} attached", "script": row}

    if action in ("maas_publish_boot_resource", "maas_import_boot_resource", "packer_publish_maas"):
        sku = (payload.get("sku") or payload.get("name") or "h100").strip().lower()
        sku = sku.replace("custom/", "").replace("-jammy", "")
        name = (payload.get("boot_resource") or f"custom/{sku}-jammy").strip()
        if sku in ("rhel-gpu", "rhel") and "boot_resource" not in payload and "name" not in payload:
            name = "custom/rhel-gpu"
            sku = "rhel-gpu"
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
            "title": payload.get("title") or name,
            "published_at": _now(),
        }
        if existing:
            existing.update(row)
            row = existing
        else:
            resources.append(row)
        broken = state.get("broken")
        if isinstance(broken, dict):
            broken.pop("missing_boot_resource", None)
            broken.pop("packer_image_unpublished", None)
            missing = broken.get("missing_boot_resources")
            if isinstance(missing, list) and name in missing:
                broken["missing_boot_resources"] = [n for n in missing if n != name]
                if not broken["missing_boot_resources"]:
                    broken.pop("missing_boot_resources", None)
            if not broken:
                state["broken"] = {}
        return {
            "ok": True,
            "message": f"Published {name} to MAAS boot-resources",
            "boot_resource": row,
            "boot_resources": resources,
        }

    if action == "maas_sync_images":
        stream = maas.setdefault("image_stream", seed_v2()["image_stream"])
        stream["syncing"] = True
        stream["last_sync"] = _now()
        selected = payload.get("releases") or stream.get("selected") or ["ubuntu/jammy", "ubuntu/noble"]
        stream["selected"] = list(selected)
        resources = maas.setdefault("boot_resources", [])
        catalog = {
            "ubuntu/jammy": {"title": "Ubuntu 22.04 LTS", "size_gb": 2.1},
            "ubuntu/noble": {"title": "Ubuntu 24.04 LTS", "size_gb": 2.4},
            "ubuntu/focal": {"title": "Ubuntu 20.04 LTS", "size_gb": 1.9},
            "centos/8": {"title": "CentOS 8", "size_gb": 3.0},
            "rhel/9": {"title": "RHEL 9", "size_gb": 3.2},
        }
        for name in selected:
            meta = catalog.get(name) or {"title": name, "size_gb": 2.0}
            existing = next((r for r in resources if r.get("name") == name), None)
            row = {
                "name": name,
                "architecture": "amd64/generic",
                "type": "Synced",
                "size_gb": meta["size_gb"],
                "status": "Synced",
                "source": stream.get("url") or "images.maas.io",
                "title": meta["title"],
                "synced_at": _now(),
            }
            if existing:
                existing.update(row)
            else:
                resources.append(row)
        stream["syncing"] = False
        return {
            "ok": True,
            "message": f"Synced {len(selected)} image(s) from {stream.get('url')}",
            "boot_resources": resources,
            "image_stream": stream,
        }

    if action == "maas_upload_boot_resource":
        name = (payload.get("name") or payload.get("boot_resource") or "").strip()
        if not name:
            return {"ok": False, "error": "Image name required (e.g. custom/h100-jammy)"}
        if not name.startswith("custom/"):
            name = f"custom/{name}"
        return apply_v2_action(state, "maas_publish_boot_resource", {
            **payload,
            "boot_resource": name,
            "source": payload.get("source") or "upload",
        })

    if action == "maas_add_device":
        hostname = (payload.get("hostname") or payload.get("name") or "").strip()
        mac = (payload.get("mac") or "").strip()
        if not hostname or not mac:
            return {"ok": False, "error": "Hostname and MAC are required"}
        devices = maas.setdefault("devices", [])
        if any((d.get("hostname") == hostname or d.get("mac") == mac) for d in devices):
            return {"ok": False, "error": "Device already exists"}
        row = {
            "id": f"dev-{len(devices) + 1}",
            "hostname": hostname,
            "mac": mac,
            "ip": (payload.get("ip") or payload.get("ip_address") or "").strip(),
            "zone": payload.get("zone") or "default",
            "owner": payload.get("owner") or "admin",
            "parent": payload.get("parent") or "",
            "type": payload.get("type") or "device",
        }
        devices.append(row)
        state["devices"] = devices
        return {"ok": True, "message": f"Device {hostname} registered", "device": row}

    if action == "maas_delete_device":
        hostname = (payload.get("hostname") or "").strip()
        mac = (payload.get("mac") or "").strip()
        devices = list(maas.get("devices") or [])
        before = len(devices)
        maas["devices"] = [
            d for d in devices
            if not ((hostname and d.get("hostname") == hostname) or (mac and d.get("mac") == mac))
        ]
        state["devices"] = maas["devices"]
        removed = before - len(maas["devices"])
        return {
            "ok": True,
            "message": "Device deleted" if removed else "Device not found",
            "devices": maas["devices"],
        }

    if action == "maas_dhcp_snippet_add":
        dhcp = state.setdefault("dhcp", maas.setdefault("dhcp", {}))
        snippets = dhcp.setdefault("snippets", [])
        name = (payload.get("name") or f"snippet-{len(snippets) + 1}").strip()
        value = payload.get("value") or payload.get("content") or "# DHCP snippet\n"
        scope = payload.get("scope") or "global"
        row = {
            "name": name,
            "value": value,
            "scope": scope,
            "subnet": payload.get("subnet") or "",
            "node": payload.get("node") or "",
            "enabled": payload.get("enabled", True),
            "updated": _now(),
        }
        existing = next((s for s in snippets if s.get("name") == name), None)
        if existing:
            existing.update(row)
            row = existing
        else:
            snippets.append(row)
        maas["dhcp"] = dhcp
        return {"ok": True, "message": f"DHCP snippet {name} saved", "snippet": row}

    if action == "maas_dhcp_snippet_delete":
        dhcp = state.setdefault("dhcp", maas.setdefault("dhcp", {}))
        name = (payload.get("name") or "").strip()
        before = len(dhcp.get("snippets") or [])
        dhcp["snippets"] = [s for s in (dhcp.get("snippets") or []) if s.get("name") != name]
        maas["dhcp"] = dhcp
        return {
            "ok": True,
            "message": "Snippet deleted" if len(dhcp["snippets"]) < before else "Snippet not found",
        }

    if action == "maas_compose_kvm":
        kvm = state.setdefault("kvm", {})
        vms = kvm.setdefault("vms", [])
        name = (payload.get("name") or f"vm-{len(vms) + 1}").strip()
        if any(v.get("name") == name for v in vms):
            return {"ok": False, "error": f"VM {name} already exists"}
        row = {
            "name": name,
            "state": "running" if payload.get("start", True) else "shut off",
            "vcpu": int(payload.get("vcpu") or payload.get("cores") or 2),
            "ram_gb": int(payload.get("ram_gb") or payload.get("memory") or 4),
            "ip": payload.get("ip") or f"10.10.2.{20 + len(vms)}",
            "pool": payload.get("pool") or "default",
            "host": payload.get("host") or "kvm-host-01",
        }
        vms.append(row)
        return {"ok": True, "message": f"Composed KVM instance {name}", "vm": row}

    if action == "maas_controller_restart_service":
        controllers = state.get("controllers") or maas.get("controllers") or []
        cname = (payload.get("controller") or payload.get("name") or "").strip()
        service = (payload.get("service") or "").strip()
        ctrl = next((c for c in controllers if c.get("name") == cname), None)
        if not ctrl:
            return {"ok": False, "error": "Controller not found"}
        services = ctrl.setdefault("services", {})
        if service and service in services:
            services[service] = "running"
            ctrl["health"] = "ok"
            return {"ok": True, "message": f"Restarted {service} on {cname}"}
        return {"ok": False, "error": f"Unknown service {service}"}

    return None
