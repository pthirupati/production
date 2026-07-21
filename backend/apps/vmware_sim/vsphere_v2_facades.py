"""vSphere Client V2 facades — host profiles, SPBM, tags, DRS/HA, guest OS, LCM."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "host_profiles": [
            {
                "id": "hp-std",
                "name": "Standard-ESXi-Profile",
                "compliance": "Compliant",
                "hosts": ["esxi-01.lab.local", "esxi-02.lab.local"],
            },
        ],
        "storage_policies": [
            {
                "id": "sp-gold",
                "name": "vSAN Default Storage Policy",
                "rules": "FTM=RAID1, FTT=1",
                "vms": 12,
            },
            {
                "id": "sp-encrypt",
                "name": "VM Encryption Policy",
                "rules": "encryption=IOFilter",
                "vms": 2,
            },
        ],
        "tags": [
            {"id": "tag-prod", "category": "Environment", "name": "Production", "objects": 24},
            {"id": "tag-backup", "category": "Protection", "name": "Backup-Required", "objects": 18},
        ],
        "drs_rules": [
            {
                "id": "drs-anti",
                "name": "Keep-App-DB-Apart",
                "type": "SeparateVirtualMachines",
                "enabled": True,
                "vms": ["app-01", "db-01"],
            },
        ],
        "ha_settings": {
            "enabled": True,
            "admission_control": "cluster_resource_pct",
            "host_isolation": "powerOff",
            "vm_monitoring": "vmAndAppMonitoring",
            "response_to_host_failure": "restartVMs",
        },
        "guest_customizations": [
            {
                "id": "gc-linux",
                "name": "Linux-Corp-Std",
                "os": "Linux",
                "domain": "lab.local",
                "timezone": "UTC",
            },
            {
                "id": "gc-win",
                "name": "Windows-Corp-Std",
                "os": "Windows",
                "domain": "LAB",
                "timezone": "Eastern Standard Time",
            },
        ],
        "lifecycle_baselines": [
            {
                "id": "bl-esxi",
                "name": "ESXi-8.0U3-Baseline",
                "type": "Host",
                "compliant_hosts": 2,
                "non_compliant": 1,
            },
        ],
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        state.setdefault(key, value if not isinstance(value, dict) else dict(value))


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "attach_host_profile":
        profiles = state.setdefault("host_profiles", [])
        name = (payload.get("name") or f"Profile-{len(profiles) + 1}").strip()
        host = (payload.get("host") or "esxi-new.lab.local").strip()
        row = {
            "id": f"hp-{len(profiles) + 1}",
            "name": name,
            "compliance": "Unknown",
            "hosts": [host],
        }
        profiles.append(row)
        return {"ok": True, "message": f"Host profile {name} attached to {host}", "profile": row}

    if action == "extract_host_profile":
        profiles = state.setdefault("host_profiles", [])
        host = (payload.get("host") or payload.get("host_name") or "esxi-01.lab.local").strip()
        profile_name = (payload.get("profile_name") or payload.get("name") or f"{host.split('.')[0]}-profile").strip()
        if any(p.get("name") == profile_name for p in profiles):
            return {"ok": False, "error": f"Host profile '{profile_name}' already exists"}
        row = {
            "id": f"hp-{len(profiles) + 1}",
            "name": profile_name,
            "compliance": "Unknown",
            "hosts": [host],
            "reference_host": host,
        }
        profiles.append(row)
        return {"ok": True, "message": f"Extracted host profile {profile_name} from {host}", "profile": row}

    if action == "check_host_profile_compliance":
        for p in state.get("host_profiles") or []:
            if p.get("id") == payload.get("profile_id") or p.get("name") == payload.get("name"):
                p["compliance"] = "Compliant"
                p["last_check"] = _now()
                return {"ok": True, "message": f"Compliance check passed for {p['name']}", "profile": p}
        return {"ok": False, "error": "Host profile not found"}

    if action == "create_storage_policy":
        policies = state.setdefault("storage_policies", [])
        name = (payload.get("name") or f"Policy-{len(policies) + 1}").strip()
        rules = (payload.get("rules") or "FTM=RAID1, FTT=1").strip()
        row = {"id": f"sp-{len(policies) + 1}", "name": name, "rules": rules, "vms": 0}
        policies.append(row)
        return {"ok": True, "message": f"Storage policy {name} created", "policy": row}

    if action == "create_tag":
        tags = state.setdefault("tags", [])
        category = (payload.get("category") or "Custom").strip()
        name = (payload.get("name") or f"Tag-{len(tags) + 1}").strip()
        row = {"id": f"tag-{len(tags) + 1}", "category": category, "name": name, "objects": 0}
        tags.append(row)
        return {"ok": True, "message": f"Tag {category}/{name} created", "tag": row}

    if action == "create_drs_rule":
        rules = state.setdefault("drs_rules", [])
        name = (payload.get("name") or f"DRS-Rule-{len(rules) + 1}").strip()
        rule_type = payload.get("type") or "SeparateVirtualMachines"
        vms = payload.get("vms") or []
        row = {
            "id": f"drs-{len(rules) + 1}",
            "name": name,
            "type": rule_type,
            "enabled": True,
            "vms": vms if isinstance(vms, list) else [str(vms)],
        }
        rules.append(row)
        return {"ok": True, "message": f"DRS rule {name} created", "rule": row}

    if action == "update_ha_settings":
        ha = state.setdefault("ha_settings", {})
        for key in ("admission_control", "host_isolation", "vm_monitoring", "response_to_host_failure"):
            if key in payload:
                ha[key] = payload[key]
        if "enabled" in payload:
            ha["enabled"] = bool(payload["enabled"])
        return {"ok": True, "message": "HA settings updated", "ha_settings": ha}

    if action == "create_guest_customization":
        specs = state.setdefault("guest_customizations", [])
        name = (payload.get("name") or f"Guest-Spec-{len(specs) + 1}").strip()
        row = {
            "id": f"gc-{len(specs) + 1}",
            "name": name,
            "os": payload.get("os") or "Linux",
            "domain": payload.get("domain") or "lab.local",
            "timezone": payload.get("timezone") or "UTC",
        }
        specs.append(row)
        return {"ok": True, "message": f"Guest customization {name} created", "spec": row}

    if action == "remediate_baseline":
        for b in state.get("lifecycle_baselines") or []:
            if b.get("id") == payload.get("baseline_id") or b.get("name") == payload.get("name"):
                non = int(b.get("non_compliant") or 0)
                b["compliant_hosts"] = int(b.get("compliant_hosts") or 0) + non
                b["non_compliant"] = 0
                b["last_remediated"] = _now()
                return {"ok": True, "message": f"Baseline {b['name']} remediated", "baseline": b}
        return {"ok": False, "error": "Baseline not found"}

    return None
