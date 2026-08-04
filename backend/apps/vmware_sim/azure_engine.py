"""In-memory Azure Portal console simulator for cloud training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of the
Azure Portal: Resource Groups, Virtual Networks/Subnets, Network Security
Groups (with real allow/deny rule evaluation), Virtual Machines (size/vCPU/
RAM, OS disk, NIC, power lifecycle), and Managed Disks (attach/detach to a
VM's data disk list). Models the exact cross-tech sync the platform commits
to for every cloud: resizing a VM's size changes its reported vCPU/RAM inside
the Linux guest terminal for the SAME session (see azure_bridge.py), and an
NSG rule blocking inbound 22/3389 is a real allow/deny evaluation, not a
scripted "connection refused" string.
"""

from __future__ import annotations

import copy
import json
import random
import time
from typing import Any

from django.core.cache import cache

from .azure_v2_facades import apply_v2_action, ensure_v2, seed_v2

SESSION_TTL = 7200
SUBSCRIPTION_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"

PENDING_SECONDS = 4  # wall-clock: VM stays "Starting"/"Stopping" before settling

_HEX = "0123456789abcdef"


def _hex(n: int) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def new_resource_id(rg: str, provider: str, kind: str, name: str) -> str:
    return (
        f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{rg}/providers/"
        f"{provider}/{kind}/{name}"
    )


# ── VM size catalog (vCPU / RAM — real Azure size-family shapes) ─────────────
VM_SIZES: dict[str, dict[str, Any]] = {
    "Standard_B1s": {"vcpus": 1, "ram_gb": 1, "family": "B-series (burstable)"},
    "Standard_B2s": {"vcpus": 2, "ram_gb": 4, "family": "B-series (burstable)"},
    "Standard_B2ms": {"vcpus": 2, "ram_gb": 8, "family": "B-series (burstable)"},
    "Standard_D2s_v5": {"vcpus": 2, "ram_gb": 8, "family": "Dsv5-series (general purpose)"},
    "Standard_D4s_v5": {"vcpus": 4, "ram_gb": 16, "family": "Dsv5-series (general purpose)"},
    "Standard_D8s_v5": {"vcpus": 8, "ram_gb": 32, "family": "Dsv5-series (general purpose)"},
    "Standard_E2s_v5": {"vcpus": 2, "ram_gb": 16, "family": "Esv5-series (memory optimized)"},
    "Standard_F2s_v2": {"vcpus": 2, "ram_gb": 4, "family": "Fsv2-series (compute optimized)"},
}


def _session_key(session_id: str) -> str:
    return f"azure_session:{session_id}"


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


def _event(state: dict, message: str, severity: str = "info", *, trace_id: str | None = None) -> None:
    entry = {"time": _now_iso(), "message": message, "severity": severity}
    if trace_id:
        entry["trace_id"] = trace_id
    state.setdefault("events", []).insert(0, entry)
    # Activity Log mirrors portal operations (same stream, richer fields).
    state.setdefault("activity_log", []).insert(0, {
        "time": entry["time"],
        "operation": message,
        "status": "Succeeded" if severity in ("info", "success") else "Failed",
        "caller": (state.get("session") or {}).get("user") or "system",
        "severity": severity,
        "trace_id": trace_id,
    })
    state["activity_log"] = state["activity_log"][:200]
    state["events"] = state["events"][:200]


def _find_vm(state: dict, ident: str) -> dict | None:
    for vm in state.get("vms", []):
        if vm.get("id") == ident or vm.get("name") == ident:
            return vm
    return None


def _find_nsg(state: dict, ident: str) -> dict | None:
    return next((n for n in state.get("nsgs", []) if n.get("id") == ident or n.get("name") == ident), None)


def _find_disk(state: dict, ident: str) -> dict | None:
    return next((d for d in state.get("disks", []) if d.get("id") == ident or d.get("name") == ident), None)


def _base_state() -> dict:
    rg = "rg-fixitlab-prod"
    vnet_name = "vnet-prod"
    subnet_name = "snet-web"
    nsg_name = "nsg-web"
    vm_name = "vm-web01"
    return {
        "session": {"logged_in": False, "user": ""},
        "subscription": {"id": SUBSCRIPTION_ID, "name": "FixItLab Enterprise Subscription"},
        "resource_groups": [
            {"name": rg, "location": "eastus", "resources": 0},
        ],
        "vnets": [
            {
                "name": vnet_name, "resource_group": rg, "location": "eastus",
                "address_space": "10.10.0.0/16",
                "subnets": [
                    {"name": subnet_name, "address_prefix": "10.10.1.0/24", "nsg": nsg_name},
                ],
            },
        ],
        "nsgs": [
            {
                "id": f"nsg-{_hex(8)}", "name": nsg_name, "resource_group": rg, "location": "eastus",
                "attached_to": [subnet_name],
                "rules": [
                    {"name": "AllowHTTP", "priority": 100, "direction": "Inbound", "access": "Allow",
                     "protocol": "TCP", "source": "*", "destination_port": "80"},
                    {"name": "AllowSSH", "priority": 110, "direction": "Inbound", "access": "Allow",
                     "protocol": "TCP", "source": "*", "destination_port": "22"},
                    {"name": "DenyAllInbound", "priority": 4096, "direction": "Inbound", "access": "Deny",
                     "protocol": "*", "source": "*", "destination_port": "*", "system": True},
                ],
            },
        ],
        "disks": [
            {"id": f"disk-{_hex(8)}", "name": f"{vm_name}_OsDisk", "resource_group": rg,
             "size_gb": 30, "sku": "Premium_SSD_LRS", "state": "Attached", "attached_to": vm_name, "os_disk": True},
            {"id": f"disk-{_hex(8)}", "name": "disk-data-unattached", "resource_group": rg,
             "size_gb": 128, "sku": "Standard_SSD_LRS", "state": "Unattached", "attached_to": None, "os_disk": False},
        ],
        "vms": [
            {
                "id": f"vm-{_hex(8)}", "name": vm_name, "resource_group": rg, "location": "eastus",
                "size": "Standard_B2s", "os": "Ubuntu 22.04 LTS", "power_state": "running",
                "provisioning_state": "Succeeded", "private_ip": "10.10.1.4", "public_ip": "20.1.2.3",
                "vnet": vnet_name, "subnet": subnet_name, "nsg": nsg_name,
                "os_disk": f"{vm_name}_OsDisk", "data_disks": [],
                "_transition": None,
            },
        ],
        "storage_accounts": [
            {
                "id": f"sa-{_hex(8)}", "name": "stfixitlabprod", "resource_group": rg,
                "location": "eastus", "sku": "Standard_LRS", "kind": "StorageV2",
                "access_tier": "Hot", "https_only": True, "blob_containers": [
                    {"name": "app-data", "public_access": "None", "blobs": 3},
                    {"name": "backups", "public_access": "None", "blobs": 12},
                ],
            },
        ],
        "key_vaults": [
            {
                "id": f"kv-{_hex(8)}", "name": "kv-fixitlab-prod", "resource_group": rg,
                "location": "eastus", "sku": "standard",
                "secrets": [
                    {"name": "app-connection-string", "enabled": True, "content_type": "text"},
                    {"name": "ssh-admin-password", "enabled": True, "content_type": "password"},
                ],
                "certificates": [
                    {"name": "wildcard-fixitlab", "enabled": True, "expires": "2027-06-01"},
                ],
            },
        ],
        "role_assignments": [
            {
                "id": f"ra-{_hex(8)}", "principal": "admin@fixitlab.onmicrosoft.com",
                "role": "Owner", "scope": f"/subscriptions/{SUBSCRIPTION_ID}",
            },
            {
                "id": f"ra-{_hex(8)}", "principal": "ops@fixitlab.onmicrosoft.com",
                "role": "Contributor", "scope": f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{rg}",
            },
            {
                "id": f"ra-{_hex(8)}", "principal": "reader@fixitlab.onmicrosoft.com",
                "role": "Reader", "scope": f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{rg}",
            },
        ],
        "load_balancers": [
            {
                "id": f"lb-{_hex(8)}", "name": "lb-web", "resource_group": rg, "location": "eastus",
                "sku": "Standard", "frontend_ip": "20.1.2.10", "backend_pool": [vm_name],
                "rules": [
                    {"name": "http", "frontend_port": 80, "backend_port": 80, "protocol": "Tcp"},
                ],
                "probes": [
                    {"name": "http-probe", "protocol": "Http", "port": 80, "path": "/health"},
                ],
            },
        ],
        "public_ips": [
            {
                "id": f"pip-{_hex(8)}", "name": "pip-web01", "resource_group": rg,
                "ip": "20.1.2.3", "sku": "Standard", "allocation": "Static", "attached_to": vm_name,
            },
            {
                "id": f"pip-{_hex(8)}", "name": "pip-lb", "resource_group": rg,
                "ip": "20.1.2.10", "sku": "Standard", "allocation": "Static", "attached_to": "lb-web",
            },
        ],
        "activity_log": [],
        "goal": {"title": "Azure lab", "objective": "Resolve the flagged Azure issue."},
        "broken": {},
        "events": [],
        **seed_v2(rg),
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    vm = state["vms"][0]
    if "resize" in slug or "cpu" in slug or "ram" in slug or "undersized" in slug:
        vm["size"] = "Standard_B1s"
        state["goal"] = {
            "title": "VM undersized for its workload",
            "objective": "Resize vm-web01 to a size with more vCPU/RAM and confirm the change inside the guest.",
        }
        state["broken"] = {"vm_undersized": vm["name"]}
    elif "nsg" in slug or "rdp" in slug or "ssh" in slug or "blocked" in slug:
        nsg = state["nsgs"][0]
        nsg["rules"] = [r for r in nsg["rules"] if r["name"] != "AllowSSH"]
        state["goal"] = {
            "title": "SSH connection times out",
            "objective": "Add an inbound NSG rule allowing TCP/22 so the on-call engineer can reach vm-web01.",
        }
        state["broken"] = {"nsg_blocks_ssh": nsg["name"]}
    elif "disk" in slug or "attach" in slug:
        state["goal"] = {
            "title": "Attach the pending data disk",
            "objective": "Attach disk-data-unattached to vm-web01 so the application team can mount it.",
        }
        state["broken"] = {"disk_unattached": "disk-data-unattached"}
    elif "stop" in slug or "start" in slug or "power" in slug:
        vm["power_state"] = "stopped"
        state["goal"] = {
            "title": "VM is stopped",
            "objective": "Start vm-web01 and confirm it reaches the Running power state.",
        }
        state["broken"] = {"vm_stopped": vm["name"]}


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
    for vm in state.get("vms", []):
        transition = vm.get("_transition")
        if not transition:
            continue
        if _now() - transition.get("started_ts", 0) >= PENDING_SECONDS:
            vm["power_state"] = transition["target"]
            vm.pop("_transition", None)
            changed = True
    return changed


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    changed = _advance_lifecycle(entry["state"]) or set(entry["state"].keys()) != keys_before
    if changed:
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_azure_vm
        primary = state["vms"][0] if state.get("vms") else None
        if primary:
            sync_azure_vm(session_id, primary, vm_sizes=VM_SIZES)
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


def _nsg_allows(nsg: dict, port: str) -> bool:
    """Real allow/deny evaluation: highest-priority (lowest number) matching
    inbound rule for this port wins — mirrors real Azure NSG rule processing
    order, not a scripted "blocked" flag."""
    rules = sorted(
        (r for r in nsg.get("rules", []) if r.get("direction") == "Inbound"),
        key=lambda r: r.get("priority", 65500),
    )
    for rule in rules:
        dport = rule.get("destination_port")
        if dport == "*" or dport == port:
            return rule.get("access") == "Allow"
    return False


def check_port_reachable(session_id: str, port: str = "22") -> bool:
    """Used by the cross-tech terminal/SSH bridge to decide whether an
    inbound connection on this port would actually reach the VM."""
    entry = _load(session_id)
    if not entry:
        return False
    state = entry["state"]
    vm = state["vms"][0] if state.get("vms") else None
    if not vm or vm.get("power_state") != "running":
        return False
    nsg = _find_nsg(state, vm.get("nsg") or "")
    if not nsg:
        return True
    return _nsg_allows(nsg, port)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    # Terraform apply may create VMs before the portal was opened — seed on demand.
    if entry is None and action == "create_vm":
        entry = _ensure(session_id, payload.get("scenario_slug") or "")
    if not entry:
        return {"ok": False, "error": "Azure session not found"}
    state = entry["state"]
    _advance_lifecycle(state)
    broken = state.setdefault("broken", {})

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin@fixitlab.onmicrosoft.com"}
        _event(state, "Signed in to the Azure portal", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Signed in"}

    # Provisioning path (Terraform / API): auto-sign-in so create_vm works without a portal click.
    if action == "create_vm" and not state.get("session", {}).get("logged_in"):
        state["session"] = {"logged_in": True, "user": "admin@fixitlab.onmicrosoft.com"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to the Azure portal first"}

    if action == "create_vm":
        rg = (state.get("resource_groups") or [{}])[0].get("name") or "rg-lab"
        name = (payload.get("name") or f"vm-{_hex(4)}").strip()
        if any(v.get("name") == name for v in state.get("vms") or []):
            return {"ok": True, "message": "VM already exists", "vm": next(v for v in state["vms"] if v["name"] == name)}
        size = payload.get("size") or "Standard_B2s"
        if size not in VM_SIZES:
            size = "Standard_B2s"
        vnet = (state.get("vnets") or [{}])[0].get("name") or "vnet-lab"
        subnet = ((state.get("vnets") or [{}])[0].get("subnets") or [{}])[0].get("name") or "subnet-web"
        nsg = (state.get("nsgs") or [{}])[0].get("name") or "nsg-web"
        os_disk = f"{name}_OsDisk"
        vm = {
            "id": f"vm-{_hex(8)}", "name": name, "resource_group": rg,
            "location": payload.get("location") or "eastus",
            "size": size, "os": payload.get("os") or "Ubuntu 22.04 LTS",
            "power_state": "running", "provisioning_state": "Succeeded",
            "private_ip": payload.get("private_ip") or f"10.10.1.{random.randint(10, 250)}",
            "public_ip": payload.get("public_ip") or f"20.{random.randint(1, 200)}.{random.randint(1, 200)}.{random.randint(1, 200)}",
            "vnet": vnet, "subnet": subnet, "nsg": nsg,
            "os_disk": os_disk, "data_disks": [], "_transition": None,
            "lab_managed": True,
        }
        state.setdefault("disks", []).append({
            "id": f"disk-{_hex(8)}", "name": os_disk, "resource_group": rg,
            "size_gb": int(payload.get("os_disk_gb") or 30), "sku": "Premium_SSD_LRS",
            "state": "Attached", "attached_to": name, "os_disk": True,
        })
        state.setdefault("vms", []).append(vm)
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id, sync_azure_vm
            trace_id = new_trace_id()
            sync_azure_vm(session_id, vm, vm_sizes=VM_SIZES)
        except Exception:
            trace_id = None
        _event(state, f"Created virtual machine {name}", "success", trace_id=trace_id)
        _save(session_id, entry)
        return {"ok": True, "message": "VM created", "vm": vm}

    if action == "delete_vm":
        vm = _find_vm(state, payload.get("vm_id") or payload.get("vm_name") or payload.get("name"))
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        name = vm.get("name")
        state["vms"] = [v for v in (state.get("vms") or []) if v.get("name") != name]
        # Detach OS disks tied to this VM
        for d in state.get("disks") or []:
            if d.get("attached_to") == name:
                d["state"] = "Unattached"
                d["attached_to"] = None
        _event(state, f"Deleted virtual machine {name}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": f"VM '{name}' deleted"}

    if action in ("start_vm", "stop_vm", "restart_vm", "vm_action"):
        op = payload.get("op") or {"start_vm": "start", "stop_vm": "stop", "restart_vm": "restart"}.get(action, "start")
        vm = _find_vm(state, payload.get("vm_id") or payload.get("vm_name") or payload.get("name"))
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        if op == "start":
            vm["power_state"] = "starting"
            vm["_transition"] = {"target": "running", "started_ts": _now()}
            if broken.get("vm_stopped") == vm["name"]:
                broken.pop("vm_stopped", None)
        elif op == "stop":
            vm["power_state"] = "stopping"
            vm["_transition"] = {"target": "stopped", "started_ts": _now()}
        elif op == "restart":
            vm["power_state"] = "starting"
            vm["_transition"] = {"target": "running", "started_ts": _now()}
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id
            trace_id = new_trace_id()
        except Exception:
            trace_id = None
        _event(state, f"{op.title()} requested for {vm['name']}", "info", trace_id=trace_id)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import azure_bridge
            azure_bridge.record_vm_power(str(session_id), op, trace_id=trace_id)
        except Exception:
            pass
        return {"ok": True, "message": f"{op.title()} requested", "power_state": vm["power_state"]}

    # ── Resize (the master-prompt canonical example: vCPU/RAM change syncs to the Linux guest) ──
    if action == "resize_vm":
        vm = _find_vm(state, payload.get("vm_id") or payload.get("vm_name") or payload.get("name"))
        if not vm:
            return {"ok": False, "error": "Virtual machine not found"}
        new_size = payload.get("size") or ""
        if new_size not in VM_SIZES:
            return {"ok": False, "error": f"The size '{new_size}' is not available"}
        if vm.get("power_state") not in ("stopped", "running"):
            return {"ok": False, "error": "VM must be running or stopped to resize"}
        old_size = vm["size"]
        vm["size"] = new_size
        if broken.get("vm_undersized") == vm["name"]:
            broken.pop("vm_undersized", None)
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id
            trace_id = new_trace_id()
        except Exception:
            trace_id = None
        _event(state, f"Resized {vm['name']} from {old_size} to {new_size}", "success", trace_id=trace_id)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import azure_bridge
            azure_bridge.record_vm_resize(str(session_id), VM_SIZES[new_size], trace_id=trace_id)
        except Exception:
            pass
        return {"ok": True, "message": "Resize completed", "size": new_size}

    # ── NSG rules (real allow/deny, evaluated by priority) ─────────────────
    if action == "add_nsg_rule":
        nsg = _find_nsg(state, payload.get("nsg_id") or payload.get("nsg_name"))
        if not nsg:
            return {"ok": False, "error": "Network security group not found"}
        rule = {
            "name": (payload.get("name") or "NewRule").strip(),
            "priority": int(payload.get("priority") or 200),
            "direction": payload.get("direction") or "Inbound",
            "access": payload.get("access") or "Allow",
            "protocol": payload.get("protocol") or "TCP",
            "source": payload.get("source") or "*",
            "destination_port": str(payload.get("destination_port") or payload.get("port") or "*"),
        }
        nsg["rules"].append(rule)
        if broken.get("nsg_blocks_ssh") == nsg["name"] and rule["destination_port"] in ("22", "*") and rule["access"] == "Allow":
            broken.pop("nsg_blocks_ssh", None)
        _event(state, f"Added rule {rule['name']} to {nsg['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Rule added", "rule": rule}

    if action == "remove_nsg_rule":
        nsg = _find_nsg(state, payload.get("nsg_id") or payload.get("nsg_name"))
        if not nsg:
            return {"ok": False, "error": "Network security group not found"}
        name = payload.get("name") or ""
        before = len(nsg["rules"])
        nsg["rules"] = [r for r in nsg["rules"] if r.get("name") != name or r.get("system")]
        if len(nsg["rules"]) == before:
            return {"ok": False, "error": f"Rule '{name}' not found"}
        _event(state, f"Removed rule {name} from {nsg['name']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Rule removed"}

    # ── Managed disks ───────────────────────────────────────────────────────
    if action == "attach_disk":
        vm = _find_vm(state, payload.get("vm_id") or payload.get("vm_name"))
        disk = _find_disk(state, payload.get("disk_id") or payload.get("disk_name"))
        if not vm or not disk:
            return {"ok": False, "error": "Virtual machine or disk not found"}
        if disk.get("state") == "Attached":
            return {"ok": False, "error": f"Disk '{disk['name']}' is already attached"}
        disk["state"] = "Attached"
        disk["attached_to"] = vm["name"]
        vm.setdefault("data_disks", []).append(disk["name"])
        if broken.get("disk_unattached") == disk["name"]:
            broken.pop("disk_unattached", None)
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id
            trace_id = new_trace_id()
        except Exception:
            trace_id = None
        _event(state, f"Attached disk {disk['name']} to {vm['name']}", "success", trace_id=trace_id)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import azure_bridge
            azure_bridge.record_disk_attach(str(session_id), disk["name"], size_gb=disk.get("size_gb", 128), trace_id=trace_id)
        except Exception:
            pass
        return {"ok": True, "message": "Disk attached"}

    if action == "detach_disk":
        disk = _find_disk(state, payload.get("disk_id") or payload.get("disk_name"))
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        vm = _find_vm(state, disk.get("attached_to") or "")
        if disk.get("state") != "Attached":
            return {"ok": False, "error": f"Disk '{disk['name']}' is not attached"}
        disk["state"] = "Unattached"
        disk["attached_to"] = None
        if vm:
            vm["data_disks"] = [d for d in (vm.get("data_disks") or []) if d != disk["name"]]
        _event(state, f"Detached disk {disk['name']}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Disk detached"}

    if action == "create_disk":
        rg = state["resource_groups"][0]["name"]
        disk = {
            "id": f"disk-{_hex(8)}", "name": (payload.get("name") or f"disk-{_hex(4)}").strip(),
            "resource_group": rg, "size_gb": int(payload.get("size_gb") or 128),
            "sku": payload.get("sku") or "Standard_SSD_LRS", "state": "Unattached",
            "attached_to": None, "os_disk": False,
        }
        state.setdefault("disks", []).append(disk)
        _event(state, f"Created disk {disk['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Disk created", "disk": disk}

    if action == "create_resource_group":
        name = (payload.get("name") or "").strip()
        location = (payload.get("location") or "eastus").strip()
        if not name:
            return {"ok": False, "error": "Resource group name is required"}
        if any(r.get("name") == name for r in state.get("resource_groups") or []):
            return {"ok": False, "error": f"Resource group '{name}' already exists"}
        rg = {"name": name, "location": location, "resources": 0}
        state.setdefault("resource_groups", []).append(rg)
        _event(state, f"Created resource group {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Resource group created", "resource_group": rg}

    if action == "create_storage_account":
        rg = (payload.get("resource_group")
              or (state.get("resource_groups") or [{}])[0].get("name")
              or "rg-fixitlab-prod")
        name = (payload.get("name") or f"st{_hex(6)}").strip().lower()
        if any(s.get("name") == name for s in state.get("storage_accounts") or []):
            return {"ok": False, "error": f"Storage account '{name}' already exists"}
        sa = {
            "id": f"sa-{_hex(8)}", "name": name, "resource_group": rg,
            "location": payload.get("location") or "eastus",
            "sku": payload.get("sku") or "Standard_LRS", "kind": "StorageV2",
            "access_tier": payload.get("access_tier") or "Hot", "https_only": True,
            "blob_containers": [],
        }
        state.setdefault("storage_accounts", []).append(sa)
        _event(state, f"Created storage account {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Storage account created", "storage_account": sa}

    if action == "create_blob_container":
        sa = next(
            (s for s in state.get("storage_accounts") or []
             if s.get("name") == (payload.get("account") or payload.get("storage_account"))),
            None,
        )
        if not sa:
            return {"ok": False, "error": "Storage account not found"}
        cname = (payload.get("name") or "data").strip()
        if any(c.get("name") == cname for c in sa.get("blob_containers") or []):
            return {"ok": False, "error": f"Container '{cname}' already exists"}
        sa.setdefault("blob_containers", []).append({
            "name": cname, "public_access": payload.get("public_access") or "None", "blobs": 0,
        })
        _event(state, f"Created container {cname} on {sa['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Container created"}

    if action == "set_secret":
        kv = next(
            (k for k in state.get("key_vaults") or []
             if k.get("name") == (payload.get("vault") or payload.get("key_vault"))),
            None,
        )
        if not kv:
            return {"ok": False, "error": "Key vault not found"}
        sname = (payload.get("name") or "").strip()
        if not sname:
            return {"ok": False, "error": "Secret name is required"}
        existing = next((s for s in kv.get("secrets") or [] if s.get("name") == sname), None)
        if existing:
            existing["enabled"] = True
            existing["updated"] = _now_iso()
        else:
            kv.setdefault("secrets", []).append({
                "name": sname, "enabled": True,
                "content_type": payload.get("content_type") or "text",
                "updated": _now_iso(),
            })
        if (state.get("broken") or {}).get("missing_secret") == sname:
            state["broken"].pop("missing_secret", None)
        _event(state, f"Set secret {sname} in {kv['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Secret set"}

    if action == "import_certificate":
        kv = next(
            (k for k in state.get("key_vaults") or []
             if k.get("name") == (payload.get("vault") or payload.get("key_vault"))),
            None,
        )
        if not kv:
            return {"ok": False, "error": "Key vault not found"}
        cname = (payload.get("name") or "").strip()
        if not cname:
            return {"ok": False, "error": "Certificate name is required"}
        existing = next((c for c in kv.get("certificates") or [] if c.get("name") == cname), None)
        if existing:
            existing["enabled"] = True
            existing["expires"] = payload.get("expires") or existing.get("expires") or "2028-01-01"
        else:
            kv.setdefault("certificates", []).append({
                "name": cname,
                "enabled": True,
                "expires": payload.get("expires") or "2028-01-01",
            })
        _event(state, f"Imported certificate {cname} in {kv['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Certificate imported"}

    if action == "assign_role":
        principal = (payload.get("principal") or "").strip()
        role = (payload.get("role") or "Reader").strip()
        scope = (payload.get("scope")
                 or f"/subscriptions/{SUBSCRIPTION_ID}")
        if not principal:
            return {"ok": False, "error": "Principal is required"}
        ra = {
            "id": f"ra-{_hex(8)}", "principal": principal, "role": role, "scope": scope,
        }
        state.setdefault("role_assignments", []).append(ra)
        _event(state, f"Assigned {role} to {principal}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Role assigned", "role_assignment": ra}

    if action == "remove_role_assignment":
        rid = payload.get("id") or ""
        before = len(state.get("role_assignments") or [])
        state["role_assignments"] = [
            r for r in (state.get("role_assignments") or []) if r.get("id") != rid
        ]
        if len(state["role_assignments"]) == before:
            return {"ok": False, "error": "Role assignment not found"}
        _event(state, f"Removed role assignment {rid}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Role assignment removed"}

    if action == "create_load_balancer_rule":
        lb = next(
            (x for x in state.get("load_balancers") or []
             if x.get("name") == (payload.get("lb") or payload.get("name") or "lb-web")),
            None,
        )
        if not lb:
            return {"ok": False, "error": "Load balancer not found"}
        rule = {
            "name": (payload.get("rule_name") or "rule").strip(),
            "frontend_port": int(payload.get("frontend_port") or 443),
            "backend_port": int(payload.get("backend_port") or 443),
            "protocol": payload.get("protocol") or "Tcp",
        }
        lb.setdefault("rules", []).append(rule)
        _event(state, f"Added LB rule {rule['name']} on {lb['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Load balancer rule added", "rule": rule}

    if action == "create_subnet":
        vnet = next(
            (v for v in state.get("vnets") or []
             if v.get("name") == (payload.get("vnet") or payload.get("vnet_name"))),
            None,
        )
        if not vnet:
            return {"ok": False, "error": "Virtual network not found"}
        sname = (payload.get("name") or "snet-new").strip()
        if any(s.get("name") == sname for s in vnet.get("subnets") or []):
            return {"ok": False, "error": f"Subnet '{sname}' already exists"}
        subnet = {
            "name": sname,
            "address_prefix": payload.get("address_prefix") or "10.10.2.0/24",
            "nsg": payload.get("nsg") or "",
        }
        vnet.setdefault("subnets", []).append(subnet)
        _event(state, f"Created subnet {sname} on {vnet['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Subnet created", "subnet": subnet}

    if action == "create_nsg":
        rg = (payload.get("resource_group")
              or (state.get("resource_groups") or [{}])[0].get("name"))
        name = (payload.get("name") or f"nsg-{_hex(4)}").strip()
        if any(n.get("name") == name for n in state.get("nsgs") or []):
            return {"ok": False, "error": f"NSG '{name}' already exists"}
        nsg = {
            "id": f"nsg-{_hex(8)}", "name": name, "resource_group": rg,
            "location": payload.get("location") or "eastus", "attached_to": [],
            "rules": [
                {"name": "DenyAllInbound", "priority": 4096, "direction": "Inbound",
                 "access": "Deny", "protocol": "*", "source": "*",
                 "destination_port": "*", "system": True},
            ],
        }
        state.setdefault("nsgs", []).append(nsg)
        _event(state, f"Created network security group {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "NSG created", "nsg": nsg}

    if action == "snapshot_disk":
        disk = _find_disk(state, payload.get("disk_id") or payload.get("disk_name"))
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        snap = {
            "id": f"snap-{_hex(8)}",
            "name": (payload.get("name") or f"{disk['name']}-snap").strip(),
            "source_disk": disk["name"],
            "size_gb": disk.get("size_gb"),
            "created": _now_iso(),
            "resource_group": disk.get("resource_group"),
        }
        state.setdefault("snapshots", []).append(snap)
        _event(state, f"Created snapshot {snap['name']} from {disk['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Snapshot created", "snapshot": snap}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or action, "success")
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Grader — fail-CLOSED, matching every sibling engine's contract.
# ---------------------------------------------------------------------------

def validate_azure_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No Azure session"
    state = entry["state"]
    broken = state.get("broken") or {}
    if broken:
        reason = next(iter(broken.values()))
        kind = next(iter(broken.keys()))
        return False, f"Unresolved Azure issue ({kind}): {reason}"
    vm = state["vms"][0] if state.get("vms") else None
    if vm and vm.get("_transition"):
        return False, f"{vm['name']} is still transitioning ({vm['power_state']}) — wait for it to settle"
    return True, "Azure validation passed"
