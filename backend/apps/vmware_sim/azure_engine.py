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
    # Record whether a console objective was actually seeded. validate_azure_lab
    # grades "no broken markers left" as success, which is only meaningful if a
    # marker existed to begin with — otherwise an unmatched slug auto-passes.
    state["_preset_applied"] = bool(state.get("broken"))


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
        rg = (
            (payload.get("resource_group") or "").strip()
            or (state.get("resource_groups") or [{}])[0].get("name")
            or "rg-lab"
        )
        name = (payload.get("name") or f"vm-{_hex(4)}").strip()
        if any(v.get("name") == name for v in state.get("vms") or []):
            return {"ok": True, "message": "VM already exists", "vm": next(v for v in state["vms"] if v["name"] == name)}
        size = payload.get("size") or "Standard_B2s"
        if size not in VM_SIZES:
            size = "Standard_B2s"
        location = (payload.get("location") or payload.get("region") or "eastus").strip()
        image = (payload.get("image") or payload.get("os") or "Ubuntu 22.04 LTS").strip()

        # Optional: create a default VNet + subnet when the portal asks for new networking.
        if payload.get("create_networking"):
            vnet_name = (payload.get("vnet") or f"vnet-{name}").strip()
            subnet_name = (payload.get("subnet") or "default").strip()
            if not any(v.get("name") == vnet_name for v in state.get("vnets") or []):
                state.setdefault("vnets", []).append({
                    "name": vnet_name, "resource_group": rg, "location": location,
                    "address_space": payload.get("address_space") or "10.20.0.0/16",
                    "subnets": [{
                        "name": subnet_name,
                        "address_prefix": payload.get("subnet_prefix") or "10.20.1.0/24",
                        "nsg": "",
                    }],
                })
            else:
                vnet_obj = next(v for v in state["vnets"] if v["name"] == vnet_name)
                if not any(s.get("name") == subnet_name for s in (vnet_obj.get("subnets") or [])):
                    vnet_obj.setdefault("subnets", []).append({
                        "name": subnet_name,
                        "address_prefix": payload.get("subnet_prefix") or "10.20.1.0/24",
                        "nsg": "",
                    })
            vnet, subnet = vnet_name, subnet_name
        else:
            vnet = (payload.get("vnet") or "").strip() or (state.get("vnets") or [{}])[0].get("name") or "vnet-lab"
            subnet = (payload.get("subnet") or "").strip()
            if not subnet:
                matched = next((v for v in (state.get("vnets") or []) if v.get("name") == vnet), None)
                subnet = ((matched or {}).get("subnets") or (state.get("vnets") or [{}])[0].get("subnets") or [{}])[0].get("name") or "subnet-web"

        nsg = (payload.get("nsg") or "").strip() or (state.get("nsgs") or [{}])[0].get("name") or "nsg-web"
        os_disk = f"{name}_OsDisk"
        os_disk_sku = (payload.get("os_disk_sku") or payload.get("os_disk_type") or "Premium_SSD_LRS").strip()
        os_disk_gb = int(payload.get("os_disk_gb") or payload.get("os_disk_size_gb") or 30)

        # Public IP: prefer explicit assign_public_ip; else honor public_ip string/bool; default on.
        if "assign_public_ip" in payload:
            assign_pip = bool(payload.get("assign_public_ip"))
        elif "public_ip" in payload:
            pip_raw = payload.get("public_ip")
            assign_pip = bool(pip_raw) and pip_raw not in (False, "false", "False", "none", "None", "No", "no")
        else:
            assign_pip = True
        if assign_pip:
            if isinstance(payload.get("public_ip"), str) and payload["public_ip"] not in ("", "none", "None"):
                public_ip = payload["public_ip"]
            else:
                public_ip = f"20.{random.randint(1, 200)}.{random.randint(1, 200)}.{random.randint(1, 200)}"
        else:
            public_ip = None

        admin_username = (payload.get("admin_username") or "azureuser").strip()
        auth_type = (payload.get("authentication_type") or payload.get("auth_type") or "sshPublicKey").strip()
        if auth_type in ("password", "Password"):
            auth_type = "password"
        else:
            auth_type = "sshPublicKey"

        vm = {
            "id": f"vm-{_hex(8)}", "name": name, "resource_group": rg,
            "location": location,
            "size": size, "os": image, "image": image,
            "power_state": "running", "provisioning_state": "Succeeded",
            "private_ip": payload.get("private_ip") or f"10.10.1.{random.randint(10, 250)}",
            "public_ip": public_ip,
            "vnet": vnet, "subnet": subnet, "nsg": nsg,
            "os_disk": os_disk, "os_disk_sku": os_disk_sku, "os_disk_gb": os_disk_gb,
            "data_disks": [], "_transition": None,
            "lab_managed": True,
            "admin_username": admin_username,
            "authentication_type": auth_type,
            # Sim only: never persist passwords; fingerprint is a lab marker.
            "ssh_key_configured": auth_type == "sshPublicKey",
            "password_auth": auth_type == "password",
        }
        if auth_type == "sshPublicKey":
            key_src = (payload.get("ssh_public_key") or payload.get("ssh_key") or "").strip()
            vm["ssh_key_fingerprint"] = f"sha256:{_hex(16)}" if key_src else f"sha256:lab-{_hex(8)}"

        state.setdefault("disks", []).append({
            "id": f"disk-{_hex(8)}", "name": os_disk, "resource_group": rg,
            "size_gb": os_disk_gb, "sku": os_disk_sku,
            "state": "Attached", "attached_to": name, "os_disk": True,
        })
        if assign_pip and public_ip:
            state.setdefault("public_ips", []).append({
                "id": f"pip-{_hex(8)}", "name": f"pip-{name}", "resource_group": rg,
                "ip": public_ip, "sku": "Standard", "allocation": "Static", "attached_to": name,
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
    # Fail-CLOSED on an unseeded world. _apply_preset is keyword-driven
    # (resize/nsg/disk/power); replaying it over the shipped academy-azure-*
    # slugs leaves 117 of 147 with no `broken` key at all. Returning True here
    # awarded completion on the first Check with zero learner actions. An
    # unmapped slug has no console objective to grade, so it must not pass —
    # it falls through to the terminal sentinel path instead.
    if not state.get("_preset_applied"):
        return False, "NO_VALIDATION_SCRIPT"
    return True, "Azure validation passed"


# ---------------------------------------------------------------------------
# `az` CLI surface
#
# Write commands delegate to apply_action so `broken` flags, guest bridges and
# trace ids fire identically whether the learner clicked the portal or typed
# the command. Unrecognized commands return rc!=0 with an az-shaped error —
# a silent no-op would leave a learner "done" on a lab whose flag never
# cleared, which is ungradeable.
# ---------------------------------------------------------------------------

_AZ_HINT = "Run 'az help' to see the supported command groups."


def _az_error(message: str, *, rc: int = 1) -> dict:
    return {"ok": False, "rc": rc, "error": message, "stdout": "", "stderr": f"ERROR: {message}"}


def _az_ok(stdout: str, *, message: str = "") -> dict:
    return {"ok": True, "rc": 0, "stdout": stdout, "stderr": "", "message": message or stdout}


def _az_parse(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split az `--flag[=value]` pairs from positionals, underscoring keys.

    Short aliases (`-n`, `-g`) are mapped to their long forms because the
    scenario text and the docs use both interchangeably.
    """
    short = {"n": "name", "g": "resource_group", "l": "location", "o": "output"}
    positionals: list[str] = []
    opts: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--") or (tok.startswith("-") and len(tok) > 1 and not tok[1].isdigit()):
            raw = tok.lstrip("-")
            if "=" in raw:
                key, value = raw.split("=", 1)
            else:
                key = raw
                if i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                    value = tokens[i + 1]
                    i += 1
                else:
                    value = "true"
            key = key.replace("-", "_")
            opts[short.get(key, key)] = value
        else:
            positionals.append(tok)
        i += 1
    return positionals, opts


def _az_table(headers: list[str], rows: list[list[str]]) -> str:
    """`--output table` style: header, dashed rule, whitespace-aligned rows."""
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))
    lines = [
        "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip(),
        "  ".join("-" * widths[i] for i in range(len(headers))).rstrip(),
    ]
    for row in rows:
        lines.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip())
    return "\n".join(lines)


_AZ_HELP = """Available command groups:
  az vm list|show|create|delete|start|stop|restart|resize
  az vm disk attach|detach
  az disk list|create|snapshot
  az network nsg list|create
  az network nsg rule create|delete|list
  az network vnet list  |  az network vnet subnet create|list
  az group list|create
  az storage account list|create  |  az storage container create|list
  az keyvault secret set|list  |  az keyvault certificate import|list
  az role assignment create|delete|list
"""


def _az_vm(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]
    name = opts.get("name") or (rest[0] if rest and verb != "disk" else "")

    if verb == "list":
        rows = [[v.get("name", ""), v.get("resource_group", ""), v.get("location", ""),
                 v.get("size", ""), v.get("power_state", "")]
                for v in state.get("vms") or []]
        return _az_ok(_az_table(["Name", "ResourceGroup", "Location", "Size", "PowerState"], rows))

    if verb in ("show", "get-instance-view"):
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        vm = _find_vm(state, name)
        if not vm:
            return _az_error(f"The Resource 'Microsoft.Compute/virtualMachines/{name}' was not found")
        return _az_ok("\n".join(f"{k}: {v}" for k, v in vm.items() if not k.startswith("_")))

    if verb == "create":
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        payload = {"name": name}
        for flag, key in (("size", "size"), ("location", "location"), ("image", "os")):
            if opts.get(flag):
                payload[key] = opts[flag]
        return apply_action(session_id, "create_vm", payload)

    if verb in ("delete", "start", "stop", "restart", "deallocate"):
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        action = {"delete": "delete_vm", "start": "start_vm", "stop": "stop_vm",
                  "deallocate": "stop_vm", "restart": "restart_vm"}[verb]
        return apply_action(session_id, action, {"vm_name": name})

    if verb == "resize":
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        size = opts.get("size") or ""
        if not size:
            return _az_error("the following arguments are required: --size")
        return apply_action(session_id, "resize_vm", {"vm_name": name, "size": size})

    if verb == "disk" and rest:
        sub = rest[0]
        if sub not in ("attach", "detach"):
            return _az_error(f"'{sub}' is not in the 'az vm disk' command group. {_AZ_HINT}")
        vm_name = opts.get("vm_name") or opts.get("name") or ""
        disk = opts.get("disk") or opts.get("disk_name") or (rest[1] if len(rest) > 1 else "")
        if not vm_name:
            return _az_error("the following arguments are required: --vm-name")
        if not disk:
            return _az_error("the following arguments are required: --disk")
        action = "attach_disk" if sub == "attach" else "detach_disk"
        return apply_action(session_id, action, {"vm_name": vm_name, "disk_name": disk})

    return _az_error(f"'{verb}' is not in the 'az vm' command group. {_AZ_HINT}")


def _az_disk(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]
    name = opts.get("name") or (rest[0] if rest else "")
    if verb == "list":
        rows = [[d.get("name", ""), d.get("resource_group", ""), str(d.get("size_gb", "")),
                 d.get("sku", ""), d.get("state", ""), d.get("attached_to") or ""]
                for d in state.get("disks") or []]
        return _az_ok(_az_table(["Name", "ResourceGroup", "SizeGb", "Sku", "State", "AttachedTo"], rows))
    if verb == "create":
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        payload = {"name": name}
        if opts.get("size_gb"):
            payload["size_gb"] = opts["size_gb"]
        if opts.get("sku"):
            payload["sku"] = opts["sku"]
        return apply_action(session_id, "create_disk", payload)
    if verb == "snapshot":
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        return apply_action(session_id, "snapshot_disk", {"disk_name": name})
    return _az_error(f"'{verb}' is not in the 'az disk' command group. {_AZ_HINT}")


def _az_network(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    if not args:
        return _az_error(f"the following arguments are required: subgroup. {_AZ_HINT}")
    sub = args[0]
    rest = args[1:]

    if sub == "nsg":
        if rest and rest[0] == "rule":
            rule_args = rest[1:]
            verb = rule_args[0] if rule_args else ""
            nsg_name = opts.get("nsg_name") or opts.get("nsg") or ""
            if verb == "list":
                rows = []
                for nsg in state.get("nsgs") or []:
                    if nsg_name and nsg.get("name") != nsg_name:
                        continue
                    for r in nsg.get("rules") or []:
                        rows.append([nsg.get("name", ""), r.get("name", ""), str(r.get("priority", "")),
                                     r.get("direction", ""), r.get("access", ""),
                                     r.get("protocol", ""), str(r.get("destination_port", ""))])
                return _az_ok(_az_table(
                    ["Nsg", "Name", "Priority", "Direction", "Access", "Protocol", "Port"], rows))
            if verb == "create":
                if not nsg_name:
                    return _az_error("the following arguments are required: --nsg-name")
                rule_name = opts.get("name") or (rule_args[1] if len(rule_args) > 1 else "")
                if not rule_name:
                    return _az_error("the following arguments are required: --name/-n")
                payload = {"nsg_name": nsg_name, "name": rule_name}
                for flag, key in (
                    ("priority", "priority"), ("direction", "direction"), ("access", "access"),
                    ("protocol", "protocol"), ("source_address_prefixes", "source"),
                    ("destination_port_ranges", "destination_port"),
                ):
                    if opts.get(flag):
                        payload[key] = opts[flag]
                # `--destination-port-range` (singular) is the more common form.
                if opts.get("destination_port_range"):
                    payload["destination_port"] = opts["destination_port_range"]
                if opts.get("source_address_prefix"):
                    payload["source"] = opts["source_address_prefix"]
                return apply_action(session_id, "add_nsg_rule", payload)
            if verb == "delete":
                rule_name = opts.get("name") or (rule_args[1] if len(rule_args) > 1 else "")
                if not nsg_name or not rule_name:
                    return _az_error("the following arguments are required: --nsg-name, --name/-n")
                return apply_action(session_id, "remove_nsg_rule", {"nsg_name": nsg_name, "name": rule_name})
            return _az_error(f"'{verb}' is not in the 'az network nsg rule' command group. {_AZ_HINT}")

        verb = rest[0] if rest else ""
        if verb == "list":
            rows = [[n.get("name", ""), n.get("resource_group", ""), n.get("location", ""),
                     str(len(n.get("rules") or []))]
                    for n in state.get("nsgs") or []]
            return _az_ok(_az_table(["Name", "ResourceGroup", "Location", "Rules"], rows))
        if verb == "create":
            name = opts.get("name") or (rest[1] if len(rest) > 1 else "")
            if not name:
                return _az_error("the following arguments are required: --name/-n")
            return apply_action(session_id, "create_nsg", {"name": name, "location": opts.get("location")})
        return _az_error(f"'{verb}' is not in the 'az network nsg' command group. {_AZ_HINT}")

    if sub == "vnet":
        if rest and rest[0] == "subnet":
            sub_args = rest[1:]
            verb = sub_args[0] if sub_args else ""
            if verb == "list":
                rows = []
                for vnet in state.get("vnets") or []:
                    for s in vnet.get("subnets") or []:
                        rows.append([s.get("name", ""), vnet.get("name", ""),
                                     s.get("address_prefix", ""), s.get("nsg") or ""])
                return _az_ok(_az_table(["Name", "Vnet", "AddressPrefix", "Nsg"], rows))
            if verb == "create":
                name = opts.get("name") or (sub_args[1] if len(sub_args) > 1 else "")
                vnet_name = opts.get("vnet_name") or opts.get("vnet") or ""
                if not name or not vnet_name:
                    return _az_error("the following arguments are required: --name/-n, --vnet-name")
                payload = {"name": name, "vnet": vnet_name}
                if opts.get("address_prefixes") or opts.get("address_prefix"):
                    payload["address_prefix"] = opts.get("address_prefixes") or opts["address_prefix"]
                return apply_action(session_id, "create_subnet", payload)
            return _az_error(f"'{verb}' is not in the 'az network vnet subnet' command group. {_AZ_HINT}")

        verb = rest[0] if rest else ""
        if verb == "list":
            rows = [[v.get("name", ""), v.get("resource_group", ""),
                     ",".join(v.get("address_space") or []) if isinstance(v.get("address_space"), list)
                     else str(v.get("address_space") or ""),
                     str(len(v.get("subnets") or []))]
                    for v in state.get("vnets") or []]
            return _az_ok(_az_table(["Name", "ResourceGroup", "AddressSpace", "Subnets"], rows))
        return _az_error(f"'{verb}' is not in the 'az network vnet' command group. {_AZ_HINT}")

    return _az_error(f"'{sub}' is not in the 'az network' command group. {_AZ_HINT}")


def _az_storage(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    if not args:
        return _az_error(f"the following arguments are required: subgroup. {_AZ_HINT}")
    sub = args[0]
    rest = args[1:]
    verb = rest[0] if rest else ""

    if sub == "account":
        if verb == "list":
            rows = [[s.get("name", ""), s.get("resource_group", ""), s.get("location", ""),
                     s.get("sku", ""), s.get("kind", "")]
                    for s in state.get("storage_accounts") or []]
            return _az_ok(_az_table(["Name", "ResourceGroup", "Location", "Sku", "Kind"], rows))
        if verb == "create":
            name = opts.get("name") or ""
            if not name:
                return _az_error("the following arguments are required: --name/-n")
            payload = {"name": name}
            for flag in ("sku", "location", "resource_group", "access_tier"):
                if opts.get(flag):
                    payload[flag] = opts[flag]
            return apply_action(session_id, "create_storage_account", payload)
        return _az_error(f"'{verb}' is not in the 'az storage account' command group. {_AZ_HINT}")

    if sub == "container":
        account = opts.get("account_name") or opts.get("account") or ""
        if verb == "list":
            rows = []
            for sa in state.get("storage_accounts") or []:
                if account and sa.get("name") != account:
                    continue
                for c in sa.get("blob_containers") or []:
                    rows.append([c.get("name", ""), sa.get("name", ""), c.get("public_access", "")])
            return _az_ok(_az_table(["Name", "Account", "PublicAccess"], rows))
        if verb == "create":
            name = opts.get("name") or ""
            if not name or not account:
                return _az_error("the following arguments are required: --name/-n, --account-name")
            payload = {"name": name, "account": account}
            if opts.get("public_access"):
                payload["public_access"] = opts["public_access"]
            return apply_action(session_id, "create_blob_container", payload)
        return _az_error(f"'{verb}' is not in the 'az storage container' command group. {_AZ_HINT}")

    return _az_error(f"'{sub}' is not in the 'az storage' command group. {_AZ_HINT}")


def _az_keyvault(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    if not args:
        return _az_error(f"the following arguments are required: subgroup. {_AZ_HINT}")
    sub = args[0]
    rest = args[1:]
    verb = rest[0] if rest else ""
    vault = opts.get("vault_name") or opts.get("vault") or ""

    if sub == "secret":
        if verb == "list":
            rows = []
            for kv in state.get("key_vaults") or []:
                if vault and kv.get("name") != vault:
                    continue
                for s in kv.get("secrets") or []:
                    rows.append([s.get("name", ""), kv.get("name", ""), str(s.get("enabled", ""))])
            return _az_ok(_az_table(["Name", "Vault", "Enabled"], rows))
        if verb == "set":
            name = opts.get("name") or ""
            if not name or not vault:
                return _az_error("the following arguments are required: --name/-n, --vault-name")
            return apply_action(session_id, "set_secret", {"name": name, "vault": vault})
        return _az_error(f"'{verb}' is not in the 'az keyvault secret' command group. {_AZ_HINT}")

    if sub == "certificate":
        if verb == "list":
            rows = []
            for kv in state.get("key_vaults") or []:
                if vault and kv.get("name") != vault:
                    continue
                for c in kv.get("certificates") or []:
                    rows.append([c.get("name", ""), kv.get("name", ""), str(c.get("expires", ""))])
            return _az_ok(_az_table(["Name", "Vault", "Expires"], rows))
        if verb == "import":
            name = opts.get("name") or ""
            if not name or not vault:
                return _az_error("the following arguments are required: --name/-n, --vault-name")
            return apply_action(session_id, "import_certificate", {"name": name, "vault": vault})
        return _az_error(f"'{verb}' is not in the 'az keyvault certificate' command group. {_AZ_HINT}")

    return _az_error(f"'{sub}' is not in the 'az keyvault' command group. {_AZ_HINT}")


def _az_role(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    if not args or args[0] != "assignment":
        return _az_error(f"'{args[0] if args else ''}' is not in the 'az role' command group. {_AZ_HINT}")
    verb = args[1] if len(args) > 1 else ""
    if verb == "list":
        rows = [[r.get("id", ""), r.get("principal", ""), r.get("role", ""), r.get("scope", "")]
                for r in state.get("role_assignments") or []]
        return _az_ok(_az_table(["Id", "Principal", "Role", "Scope"], rows))
    if verb == "create":
        assignee = opts.get("assignee") or opts.get("principal") or ""
        role = opts.get("role") or ""
        if not assignee or not role:
            return _az_error("the following arguments are required: --assignee, --role")
        payload = {"principal": assignee, "role": role}
        if opts.get("scope"):
            payload["scope"] = opts["scope"]
        return apply_action(session_id, "assign_role", payload)
    if verb == "delete":
        rid = opts.get("ids") or opts.get("id") or ""
        if not rid:
            return _az_error("the following arguments are required: --ids")
        return apply_action(session_id, "remove_role_assignment", {"id": rid})
    return _az_error(f"'{verb}' is not in the 'az role assignment' command group. {_AZ_HINT}")


def _az_group(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    if verb == "list":
        rows = [[g.get("name", ""), g.get("location", ""), str(g.get("resources", 0))]
                for g in state.get("resource_groups") or []]
        return _az_ok(_az_table(["Name", "Location", "Resources"], rows))
    if verb == "create":
        name = opts.get("name") or ""
        if not name:
            return _az_error("the following arguments are required: --name/-n")
        return apply_action(session_id, "create_resource_group",
                            {"name": name, "location": opts.get("location") or "eastus"})
    return _az_error(f"'{verb}' is not in the 'az group' command group. {_AZ_HINT}")


def run_command(session_id: str, command: str) -> dict:
    """Execute one `az ...` CLI line against the session state.

    Returns a shell-shaped dict ({ok, rc, stdout, stderr}). Unrecognized
    commands always come back rc!=0.
    """
    import shlex

    raw = (command or "").strip()
    if not raw:
        return _az_error("the following arguments are required: _command_package. " + _AZ_HINT)

    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return _az_error(f"Could not parse command ({exc})")

    if not tokens:
        return _az_error("the following arguments are required: _command_package. " + _AZ_HINT)

    if tokens[0] != "az":
        return _az_error(f"'{tokens[0]}' is not a recognized command. {_AZ_HINT}")
    tokens = tokens[1:]
    if not tokens:
        return _az_error("the following arguments are required: _command_package. " + _AZ_HINT)

    if tokens[0] in ("help", "--help", "-h"):
        return _az_ok(_AZ_HELP)

    entry = _ensure(session_id)
    state = entry["state"]
    _advance_lifecycle(state)

    if not state.get("session", {}).get("logged_in"):
        return _az_error(
            "Please run 'az login' to setup account (or sign in to the Azure portal first).",
        )

    positionals, opts = _az_parse(tokens)
    if not positionals:
        return _az_error("the following arguments are required: _command_package. " + _AZ_HINT)

    group = positionals[0]
    args = positionals[1:]

    if group == "login":
        return _az_ok(f"Already signed in as {state['session'].get('user', '')}.")
    if group == "vm":
        return _az_vm(state, session_id, args, opts)
    if group == "disk":
        return _az_disk(state, session_id, args, opts)
    if group == "network":
        return _az_network(state, session_id, args, opts)
    if group == "storage":
        return _az_storage(state, session_id, args, opts)
    if group == "keyvault":
        return _az_keyvault(state, session_id, args, opts)
    if group == "role":
        return _az_role(state, session_id, args, opts)
    if group == "group":
        return _az_group(state, session_id, args, opts)
    if group == "snapshot" and args and args[0] == "list":
        rows = [[s.get("name", ""), s.get("source_disk", ""), str(s.get("size_gb", "")), s.get("created", "")]
                for s in state.get("snapshots") or []]
        return _az_ok(_az_table(["Name", "SourceDisk", "SizeGb", "Created"], rows))

    return _az_error(f"'{group}' is not in the 'az' command group. {_AZ_HINT}")
