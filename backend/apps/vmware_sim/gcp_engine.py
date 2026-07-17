"""In-memory Google Cloud Console simulator for cloud training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of the GCP
Console: VPC networks/subnets, Firewall rules (real priority-ordered
allow/deny evaluation — GCP evaluates lower `priority` numbers first, exactly
like this engine), Compute Engine instances (machine type/vCPU/RAM, power
lifecycle), and Persistent Disks (attach/detach). Mirrors the same cross-tech
sync commitment used for every cloud in this platform: resizing an instance's
machine type changes its reported vCPU/RAM inside the Linux guest terminal for
the SAME session (see gcp_bridge.py).
"""

from __future__ import annotations

import copy
import json
import random
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200
PROJECT_ID = "fixitlab-prod-247319"

PENDING_SECONDS = 4  # wall-clock: instance stays "PROVISIONING"/"STOPPING" before settling

_HEX = "0123456789abcdef"


def _hex(n: int) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


# ── Machine type catalog (real GCP families — vCPU / RAM) ───────────────────
MACHINE_TYPES: dict[str, dict[str, Any]] = {
    "e2-micro": {"vcpus": 2, "ram_gb": 1, "family": "E2 (shared-core, cost-optimized)"},
    "e2-small": {"vcpus": 2, "ram_gb": 2, "family": "E2 (shared-core, cost-optimized)"},
    "e2-medium": {"vcpus": 2, "ram_gb": 4, "family": "E2 (shared-core, cost-optimized)"},
    "e2-standard-2": {"vcpus": 2, "ram_gb": 8, "family": "E2 (general purpose)"},
    "e2-standard-4": {"vcpus": 4, "ram_gb": 16, "family": "E2 (general purpose)"},
    "n2-standard-2": {"vcpus": 2, "ram_gb": 8, "family": "N2 (general purpose)"},
    "n2-standard-4": {"vcpus": 4, "ram_gb": 16, "family": "N2 (general purpose)"},
    "n2-highmem-2": {"vcpus": 2, "ram_gb": 16, "family": "N2 (memory optimized)"},
    "c2-standard-4": {"vcpus": 4, "ram_gb": 16, "family": "C2 (compute optimized)"},
}


def _session_key(session_id: str) -> str:
    return f"gcp_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now() -> float:
    return time.time()


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message, "severity": severity})


def _find_instance(state: dict, ident: str) -> dict | None:
    for inst in state.get("instances", []):
        if inst.get("id") == ident or inst.get("name") == ident:
            return inst
    return None


def _find_firewall(state: dict, ident: str) -> dict | None:
    return next((f for f in state.get("firewall_rules", []) if f.get("id") == ident or f.get("name") == ident), None)


def _find_disk(state: dict, ident: str) -> dict | None:
    return next((d for d in state.get("disks", []) if d.get("id") == ident or d.get("name") == ident), None)


def _base_state() -> dict:
    network_name = "vpc-prod"
    subnet_name = "subnet-us-central1"
    vm_name = "web01"
    return {
        "session": {"logged_in": False, "user": ""},
        "project": {"id": PROJECT_ID, "name": "FixItLab Enterprise Project"},
        "networks": [
            {
                "name": network_name, "mode": "custom",
                "subnets": [
                    {"name": subnet_name, "region": "us-central1", "range": "10.128.0.0/20"},
                ],
            },
        ],
        "firewall_rules": [
            {"id": f"fw-{_hex(8)}", "name": "allow-http", "network": network_name, "direction": "INGRESS",
             "priority": 1000, "action": "ALLOW", "source_ranges": ["0.0.0.0/0"], "protocols": "tcp:80",
             "target_tags": ["web"]},
            {"id": f"fw-{_hex(8)}", "name": "allow-ssh", "network": network_name, "direction": "INGRESS",
             "priority": 1000, "action": "ALLOW", "source_ranges": ["0.0.0.0/0"], "protocols": "tcp:22",
             "target_tags": ["web"]},
            {"id": f"fw-{_hex(8)}", "name": "default-deny-ingress", "network": network_name, "direction": "INGRESS",
             "priority": 65534, "action": "DENY", "source_ranges": ["0.0.0.0/0"], "protocols": "all",
             "target_tags": [], "system": True},
        ],
        "disks": [
            {"id": f"disk-{_hex(8)}", "name": f"{vm_name}", "zone": "us-central1-a",
             "size_gb": 20, "type": "pd-balanced", "state": "READY", "attached_to": vm_name, "boot": True},
            {"id": f"disk-{_hex(8)}", "name": "disk-data-unattached", "zone": "us-central1-a",
             "size_gb": 100, "type": "pd-ssd", "state": "READY", "attached_to": None, "boot": False},
        ],
        "instances": [
            {
                "id": f"vm-{_hex(8)}", "name": vm_name, "zone": "us-central1-a",
                "machine_type": "e2-medium", "os": "Debian GNU/Linux 12", "status": "RUNNING",
                "internal_ip": "10.128.0.4", "external_ip": "34.72.1.10",
                "network": network_name, "subnet": subnet_name, "tags": ["web"],
                "boot_disk": vm_name, "extra_disks": [],
                "_transition": None,
            },
        ],
        "goal": {"title": "GCP lab", "objective": "Resolve the flagged GCP issue."},
        "broken": {},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    vm = state["instances"][0]
    if "resize" in slug or "cpu" in slug or "ram" in slug or "undersized" in slug or "machine-type" in slug:
        vm["machine_type"] = "e2-micro"
        state["goal"] = {
            "title": "Instance undersized for its workload",
            "objective": "Change web01's machine type to one with more vCPU/RAM and confirm the change inside the guest.",
        }
        state["broken"] = {"vm_undersized": vm["name"]}
    elif "firewall" in slug or "ssh" in slug or "blocked" in slug:
        fw = next((f for f in state["firewall_rules"] if f["name"] == "allow-ssh"), None)
        if fw:
            state["firewall_rules"] = [f for f in state["firewall_rules"] if f["name"] != "allow-ssh"]
        state["goal"] = {
            "title": "SSH connection times out",
            "objective": "Add an ingress firewall rule allowing TCP/22 so the on-call engineer can reach web01.",
        }
        state["broken"] = {"firewall_blocks_ssh": network_or(state)}
    elif "disk" in slug or "attach" in slug:
        state["goal"] = {
            "title": "Attach the pending persistent disk",
            "objective": "Attach disk-data-unattached to web01 so the application team can mount it.",
        }
        state["broken"] = {"disk_unattached": "disk-data-unattached"}
    elif "stop" in slug or "start" in slug or "power" in slug:
        vm["status"] = "TERMINATED"
        state["goal"] = {
            "title": "Instance is stopped",
            "objective": "Start web01 and confirm it reaches the RUNNING state.",
        }
        state["broken"] = {"vm_stopped": vm["name"]}


def network_or(state: dict) -> str:
    return state["networks"][0]["name"] if state.get("networks") else "vpc-prod"


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


_ensure_session = _ensure


def _advance_lifecycle(state: dict) -> bool:
    changed = False
    for inst in state.get("instances", []):
        transition = inst.get("_transition")
        if not transition:
            continue
        if _now() - transition.get("started_ts", 0) >= PENDING_SECONDS:
            inst["status"] = transition["target"]
            inst.pop("_transition", None)
            changed = True
    return changed


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    if _advance_lifecycle(entry["state"]):
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_gcp_instance
        primary = state["instances"][0] if state.get("instances") else None
        if primary:
            sync_gcp_instance(session_id, primary, machine_types=MACHINE_TYPES)
    except Exception:
        pass
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": state,
        "goal": state.get("goal", {}),
        "events": state.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def _fw_allows(state: dict, port: str) -> bool:
    """Real allow/deny evaluation: GCP evaluates firewall rules by priority,
    lowest number first, first match wins — mirrors real Console behavior,
    not a scripted "blocked" flag."""
    rules = sorted(
        (f for f in state.get("firewall_rules", []) if f.get("direction") == "INGRESS"),
        key=lambda f: f.get("priority", 65535),
    )
    for rule in rules:
        protocols = rule.get("protocols", "")
        if protocols == "all" or f":{port}" in protocols or protocols == f"tcp:{port}":
            return rule.get("action") == "ALLOW"
    return False


def check_port_reachable(session_id: str, port: str = "22") -> bool:
    entry = _load(session_id)
    if not entry:
        return False
    state = entry["state"]
    vm = state["instances"][0] if state.get("instances") else None
    if not vm or vm.get("status") != "RUNNING":
        return False
    return _fw_allows(state, port)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "GCP session not found"}
    state = entry["state"]
    _advance_lifecycle(state)
    broken = state.setdefault("broken", {})

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin@fixitlab.io"}
        _event(state, "Signed in to the Google Cloud Console", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Signed in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to the Google Cloud Console first"}

    if action in ("start_instance", "stop_instance", "reset_instance", "instance_action"):
        op = payload.get("op") or {
            "start_instance": "start", "stop_instance": "stop", "reset_instance": "reset",
        }.get(action, "start")
        inst = _find_instance(state, payload.get("instance_id") or payload.get("instance_name") or payload.get("name"))
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if op == "start":
            inst["status"] = "PROVISIONING"
            inst["_transition"] = {"target": "RUNNING", "started_ts": _now()}
            if broken.get("vm_stopped") == inst["name"]:
                broken.pop("vm_stopped", None)
        elif op == "stop":
            inst["status"] = "STOPPING"
            inst["_transition"] = {"target": "TERMINATED", "started_ts": _now()}
        elif op == "reset":
            inst["status"] = "PROVISIONING"
            inst["_transition"] = {"target": "RUNNING", "started_ts": _now()}
        _event(state, f"{op.title()} requested for {inst['name']}", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import gcp_bridge
            gcp_bridge.record_instance_power(str(session_id), op)
        except Exception:
            pass
        return {"ok": True, "message": f"{op.title()} requested", "status": inst["status"]}

    # ── Machine type change (canonical cross-tech example): vCPU/RAM syncs to the Linux guest ──
    if action in ("set_machine_type", "resize_instance"):
        inst = _find_instance(state, payload.get("instance_id") or payload.get("instance_name") or payload.get("name"))
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        new_type = payload.get("machine_type") or ""
        if new_type not in MACHINE_TYPES:
            return {"ok": False, "error": f"The machine type '{new_type}' is not available"}
        if inst.get("status") == "RUNNING":
            return {"ok": False, "error": "Stop the instance before changing its machine type"}
        old_type = inst["machine_type"]
        inst["machine_type"] = new_type
        if broken.get("vm_undersized") == inst["name"]:
            broken.pop("vm_undersized", None)
        _event(state, f"Changed machine type of {inst['name']} from {old_type} to {new_type}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import gcp_bridge
            gcp_bridge.record_instance_resize(str(session_id), MACHINE_TYPES[new_type])
        except Exception:
            pass
        return {"ok": True, "message": "Machine type changed", "machine_type": new_type}

    # ── Firewall rules ────────────────────────────────────────────────────
    if action == "create_firewall_rule":
        rule = {
            "id": f"fw-{_hex(8)}", "name": (payload.get("name") or "new-rule").strip(),
            "network": payload.get("network") or network_or(state),
            "direction": payload.get("direction") or "INGRESS",
            "priority": int(payload.get("priority") or 1000),
            "action": payload.get("action") or "ALLOW",
            "source_ranges": payload.get("source_ranges") or ["0.0.0.0/0"],
            "protocols": payload.get("protocols") or "tcp:22",
            "target_tags": payload.get("target_tags") or [],
        }
        state.setdefault("firewall_rules", []).append(rule)
        if broken.get("firewall_blocks_ssh") and "22" in rule["protocols"] and rule["action"] == "ALLOW":
            broken.pop("firewall_blocks_ssh", None)
        _event(state, f"Created firewall rule {rule['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Firewall rule created", "rule": rule}

    if action == "delete_firewall_rule":
        rule = _find_firewall(state, payload.get("rule_id") or payload.get("name"))
        if not rule:
            return {"ok": False, "error": "Firewall rule not found"}
        if rule.get("system"):
            return {"ok": False, "error": f"'{rule['name']}' is a default rule and cannot be deleted"}
        state["firewall_rules"] = [f for f in state["firewall_rules"] if f.get("id") != rule.get("id")]
        _event(state, f"Deleted firewall rule {rule['name']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Firewall rule deleted"}

    # ── Persistent disks ────────────────────────────────────────────────────
    if action == "attach_disk":
        inst = _find_instance(state, payload.get("instance_id") or payload.get("instance_name"))
        disk = _find_disk(state, payload.get("disk_id") or payload.get("disk_name"))
        if not inst or not disk:
            return {"ok": False, "error": "Instance or disk not found"}
        if disk.get("attached_to"):
            return {"ok": False, "error": f"Disk '{disk['name']}' is already attached"}
        disk["attached_to"] = inst["name"]
        inst.setdefault("extra_disks", []).append(disk["name"])
        if broken.get("disk_unattached") == disk["name"]:
            broken.pop("disk_unattached", None)
        _event(state, f"Attached disk {disk['name']} to {inst['name']}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import gcp_bridge
            gcp_bridge.record_disk_attach(str(session_id), disk["name"], size_gb=disk.get("size_gb", 100))
        except Exception:
            pass
        return {"ok": True, "message": "Disk attached"}

    if action == "detach_disk":
        disk = _find_disk(state, payload.get("disk_id") or payload.get("disk_name"))
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        if disk.get("boot"):
            return {"ok": False, "error": "Cannot detach the boot disk"}
        inst = _find_instance(state, disk.get("attached_to") or "")
        if not disk.get("attached_to"):
            return {"ok": False, "error": f"Disk '{disk['name']}' is not attached"}
        disk["attached_to"] = None
        if inst:
            inst["extra_disks"] = [d for d in (inst.get("extra_disks") or []) if d != disk["name"]]
        _event(state, f"Detached disk {disk['name']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Disk detached"}

    if action == "create_disk":
        disk = {
            "id": f"disk-{_hex(8)}", "name": (payload.get("name") or f"disk-{_hex(4)}").strip(),
            "zone": payload.get("zone") or "us-central1-a", "size_gb": int(payload.get("size_gb") or 100),
            "type": payload.get("type") or "pd-balanced", "state": "READY", "attached_to": None, "boot": False,
        }
        state.setdefault("disks", []).append(disk)
        _event(state, f"Created disk {disk['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Disk created", "disk": disk}

    return {"ok": False, "error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Grader — fail-CLOSED, matching every sibling engine's contract.
# ---------------------------------------------------------------------------

def validate_gcp_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No GCP session"
    state = entry["state"]
    broken = state.get("broken") or {}
    if broken:
        reason = next(iter(broken.values()))
        kind = next(iter(broken.keys()))
        return False, f"Unresolved GCP issue ({kind}): {reason}"
    inst = state["instances"][0] if state.get("instances") else None
    if inst and inst.get("_transition"):
        return False, f"{inst['name']} is still transitioning ({inst['status']}) — wait for it to settle"
    return True, "GCP validation passed"
