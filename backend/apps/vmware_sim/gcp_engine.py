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

from .gcp_v2_facades import apply_v2_action, ensure_v2, seed_v2

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


def _event(state: dict, message: str, severity: str = "info", *, trace_id: str | None = None) -> None:
    entry = {"time": _now_iso(), "message": message, "severity": severity}
    if trace_id:
        entry["trace_id"] = trace_id
    state.setdefault("events", []).insert(0, entry)
    state.setdefault("operations", []).insert(0, {
        "name": f"operation-{_hex(6)}",
        "time": entry["time"],
        "description": message,
        "status": "DONE" if severity != "error" else "ERROR",
        "target": "project",
        "trace_id": trace_id,
    })
    state["events"] = state["events"][:200]
    state["operations"] = state["operations"][:200]


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
        "buckets": [
            {
                "name": "fixitlab-prod-assets", "location": "US", "storage_class": "STANDARD",
                "objects": [
                    {"name": "app/config.json", "size_kb": 4},
                    {"name": "backups/daily.tgz", "size_kb": 102400},
                ],
            },
        ],
        "iam_bindings": [
            {"member": "user:admin@fixitlab.io", "role": "roles/owner"},
            {"member": "user:ops@fixitlab.io", "role": "roles/editor"},
            {"member": "user:viewer@fixitlab.io", "role": "roles/viewer"},
            {"member": "serviceAccount:compute@fixitlab-prod-247319.iam.gserviceaccount.com", "role": "roles/compute.instanceAdmin.v1"},
        ],
        "routes": [
            {"name": "default-route-internet", "network": network_name, "dest": "0.0.0.0/0", "next_hop": "default-internet-gateway", "priority": 1000},
            {"name": "route-to-onprem", "network": network_name, "dest": "10.0.0.0/8", "next_hop": "vpn-tunnel-1", "priority": 900},
        ],
        "forwarding_rules": [
            {
                "name": "fr-http", "region": "us-central1", "ip": "34.72.1.100",
                "port": 80, "target": "target-pool-web", "backend": [vm_name],
            },
        ],
        "snapshots": [],
        "operations": [],
        "images": [],
        "instance_templates": [],
        "migs": [],
        "goal": {"title": "GCP lab", "objective": "Resolve the flagged GCP issue."},
        "broken": {},
        "events": [],
        **seed_v2(PROJECT_ID),
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
    # Record whether a console objective was actually seeded. validate_gcp_lab
    # grades "no broken markers left" as success, which is only meaningful if a
    # marker existed to begin with — otherwise an unmatched slug auto-passes.
    state["_preset_applied"] = bool(state.get("broken"))


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
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    changed = _advance_lifecycle(entry["state"]) or set(entry["state"].keys()) != keys_before
    if changed:
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


def _resolve_image(state: dict, *, image: str | None = None, family: str | None = None) -> dict | None:
    images = state.get("images") or []
    if image:
        return next((i for i in images if i.get("name") == image or i.get("id") == image), None)
    if family:
        family_imgs = [i for i in images if i.get("family") == family and not i.get("deprecated")]
        if not family_imgs:
            return None
        family_imgs.sort(key=lambda i: i.get("created") or "", reverse=True)
        return family_imgs[0]
    return None


def _import_gcp_manifest_error(manifest: object) -> str | None:
    if not isinstance(manifest, dict):
        return "ERROR: Disk validation failed. Artifact manifest required."
    if int(manifest.get("schema_version") or 0) < 1:
        return "ERROR: Disk validation failed. Unsupported manifest schema."
    if not manifest.get("digest"):
        return "ERROR: Disk validation failed. Manifest digest missing."
    return None


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if entry is None and action == "create_instance":
        entry = _ensure(session_id, payload.get("scenario_slug") or "")
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

    if action == "create_instance" and not state.get("session", {}).get("logged_in"):
        state["session"] = {"logged_in": True, "user": "admin@fixitlab.io"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to the Google Cloud Console first"}

    if action == "import_image":
        manifest = payload.get("manifest")
        if not manifest:
            try:
                from apps.vmware_sim import packer_factory as pf
                mres = pf.get_manifest(state)
                if mres.get("ok"):
                    manifest = mres["manifest"]
            except Exception:
                manifest = None
        err = _import_gcp_manifest_error(manifest)
        if err:
            return {"ok": False, "error": err}
        expected = str(payload.get("digest") or "").strip()
        if expected and expected != manifest.get("digest"):
            return {"ok": False, "error": "ERROR: Disk validation failed. Manifest digest mismatch."}
        name = (payload.get("name") or f"imported-{manifest.get('sku') or 'image'}").strip()
        family = (payload.get("family") or "fixitlab-golden").strip()
        signed = bool(payload.get("signed", True))
        img = {
            "id": f"img-{_hex(8)}",
            "name": name,
            "family": family,
            "digest": manifest.get("digest"),
            "manifest": manifest,
            "signed": signed,
            "source": "import",
            "deprecated": False,
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "READY",
        }
        state.setdefault("images", []).append(img)
        _event(state, f"Imported image {name} (family={family})", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Created image [{name}].", "image": img}

    if action == "create_image":
        name = (payload.get("name") or f"img-{_hex(4)}").strip()
        family = (payload.get("family") or "").strip() or None
        img = {
            "id": f"img-{_hex(8)}",
            "name": name,
            "family": family,
            "digest": payload.get("digest") or f"sha256:{_hex(32)}",
            "signed": bool(payload.get("signed", False)),
            "source": payload.get("source") or "disk",
            "deprecated": False,
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "READY",
        }
        state.setdefault("images", []).append(img)
        _event(state, f"Created image {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Created image [{name}].", "image": img}

    if action == "list_images":
        family = payload.get("family")
        imgs = list(state.get("images") or [])
        if family:
            imgs = [i for i in imgs if i.get("family") == family]
        return {"ok": True, "images": imgs}

    if action == "create_instance_template":
        name = (payload.get("name") or f"tmpl-{_hex(4)}").strip()
        image = payload.get("image")
        family = payload.get("image_family") or payload.get("family")
        resolved = _resolve_image(state, image=image, family=family)
        if not resolved and (image or family):
            return {"ok": False, "error": f"Image '{image or family}' was not found"}
        tmpl = {
            "name": name,
            "machine_type": payload.get("machine_type") or "e2-medium",
            "source_image": (resolved or {}).get("name"),
            "image_family": (resolved or {}).get("family") or family,
            "image_digest": (resolved or {}).get("digest"),
            "signed": bool((resolved or {}).get("signed")),
            "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        state.setdefault("instance_templates", []).append(tmpl)
        _event(state, f"Created instance template {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Created instance template [{name}].", "template": tmpl}

    if action == "create_mig":
        name = (payload.get("name") or f"mig-{_hex(4)}").strip()
        tmpl_name = payload.get("template") or payload.get("instance_template")
        tmpl = next(
            (t for t in state.get("instance_templates") or [] if t.get("name") == tmpl_name),
            None,
        )
        if not tmpl:
            return {"ok": False, "error": "Instance template required"}
        size = int(payload.get("size") or payload.get("target_size") or 2)
        instances = []
        for i in range(size):
            instances.append({
                "name": f"{name}-{i + 1}",
                "source_image": tmpl.get("source_image"),
                "image_digest": tmpl.get("image_digest"),
                "status": "RUNNING",
            })
        mig = {
            "name": name,
            "instance_template": tmpl["name"],
            "target_size": size,
            "instances": instances,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        state.setdefault("migs", []).append(mig)
        _event(state, f"Created MIG {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Created MIG [{name}].", "mig": mig}

    if action == "rolling_update_mig":
        name = payload.get("name") or payload.get("mig") or ""
        mig = next((m for m in state.get("migs") or [] if m.get("name") == name), None)
        if not mig:
            return {"ok": False, "error": f"MIG '{name}' not found"}
        tmpl_name = payload.get("template") or payload.get("instance_template")
        tmpl = next(
            (t for t in state.get("instance_templates") or [] if t.get("name") == tmpl_name),
            None,
        )
        if not tmpl:
            return {"ok": False, "error": "New instance template required"}
        batch = int(payload.get("batch") or payload.get("max_surge") or len(mig.get("instances") or []))
        updated = 0
        for inst in mig.get("instances") or []:
            if updated >= batch:
                break
            if inst.get("image_digest") == tmpl.get("image_digest"):
                continue
            inst["source_image"] = tmpl.get("source_image")
            inst["image_digest"] = tmpl.get("image_digest")
            updated += 1
        mig["instance_template"] = tmpl["name"]
        mig["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _event(state, f"MIG {name} rolling update: {updated} instance(s)", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Updated {updated} instance(s)", "mig": mig, "updated": updated}

    if action == "create_instance":
        name = (payload.get("name") or f"vm-{_hex(4)}").strip()
        if any(i.get("name") == name for i in state.get("instances") or []):
            return {"ok": True, "message": "Instance already exists",
                    "instance": next(i for i in state["instances"] if i["name"] == name)}
        machine_type = payload.get("machine_type") or "e2-medium"
        if machine_type not in MACHINE_TYPES:
            machine_type = "e2-medium"
        zone = payload.get("zone") or "us-central1-a"
        network = (state.get("networks") or [{}])[0].get("name") or "default"
        subnet = ((state.get("networks") or [{}])[0].get("subnets") or [{}])[0].get("name") or "default"
        image_name = payload.get("image")
        image_family = payload.get("image_family") or payload.get("family")
        resolved = _resolve_image(state, image=image_name, family=image_family)
        secure_boot = bool(
            payload.get("shielded_secure_boot")
            or (payload.get("shielded_vm") or {}).get("secure_boot")
            or payload.get("secure_boot")
        )
        if secure_boot and resolved is not None and not resolved.get("signed"):
            return {
                "ok": False,
                "error": (
                    "ERROR: Secure Boot is enabled but the selected image is not signed. "
                    "Use a signed image or disable --shielded-secure-boot."
                ),
            }
        if (image_name or image_family) and resolved is None:
            return {
                "ok": False,
                "error": f"The resource 'images/{image_name or image_family}' was not found",
            }
        inst = {
            "id": f"vm-{_hex(8)}", "name": name, "zone": zone,
            "machine_type": machine_type, "os": payload.get("os") or "Debian GNU/Linux 12",
            "status": "RUNNING",
            "internal_ip": payload.get("internal_ip") or f"10.128.0.{random.randint(10, 250)}",
            "external_ip": payload.get("external_ip") or f"34.{random.randint(1, 200)}.{random.randint(1, 200)}.{random.randint(1, 200)}",
            "network": network, "subnet": subnet, "tags": payload.get("tags") or ["web"],
            "boot_disk": name, "extra_disks": [], "_transition": None,
            "lab_managed": True,
            "source_image": (resolved or {}).get("name"),
            "image_digest": (resolved or {}).get("digest"),
            "shielded_secure_boot": secure_boot,
        }
        state.setdefault("disks", []).append({
            "id": f"disk-{_hex(8)}", "name": name, "zone": zone,
            "size_gb": int(payload.get("boot_disk_gb") or 20), "type": "pd-balanced",
            "state": "READY", "attached_to": name, "boot": True,
        })
        state.setdefault("instances", []).append(inst)
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id, sync_gcp_instance
            trace_id = new_trace_id()
            sync_gcp_instance(session_id, inst, machine_types=MACHINE_TYPES)
        except Exception:
            trace_id = None
        _event(state, f"Created instance {name}", "success", trace_id=trace_id)
        _save(session_id, entry)
        return {"ok": True, "message": "Instance created", "instance": inst}

    if action == "delete_instance":
        inst = _find_instance(
            state,
            payload.get("instance_id") or payload.get("instance_name") or payload.get("name"),
        )
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        name = inst.get("name")
        state["instances"] = [i for i in (state.get("instances") or []) if i.get("name") != name]
        for d in state.get("disks") or []:
            if d.get("attached_to") == name:
                d["state"] = "READY"
                d["attached_to"] = None
        _event(state, f"Deleted instance {name}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": f"Instance '{name}' deleted"}

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
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id
            trace_id = new_trace_id()
        except Exception:
            trace_id = None
        _event(state, f"{op.title()} requested for {inst['name']}", "info", trace_id=trace_id)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import gcp_bridge
            gcp_bridge.record_instance_power(str(session_id), op, trace_id=trace_id)
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
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id
            trace_id = new_trace_id()
        except Exception:
            trace_id = None
        _event(state, f"Changed machine type of {inst['name']} from {old_type} to {new_type}", "success", trace_id=trace_id)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import gcp_bridge
            gcp_bridge.record_instance_resize(str(session_id), MACHINE_TYPES[new_type], trace_id=trace_id)
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
        try:
            from apps.labs.provisioner.simulation.server_identity import new_trace_id
            trace_id = new_trace_id()
        except Exception:
            trace_id = None
        _event(state, f"Attached disk {disk['name']} to {inst['name']}", "success", trace_id=trace_id)
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import gcp_bridge
            gcp_bridge.record_disk_attach(str(session_id), disk["name"], size_gb=disk.get("size_gb", 100), trace_id=trace_id)
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

    if action == "add_iam_binding":
        member = (payload.get("member") or "").strip()
        role = (payload.get("role") or "roles/viewer").strip()
        if not member:
            return {"ok": False, "error": "Member is required"}
        if not member.startswith(("user:", "serviceAccount:", "group:")):
            member = f"user:{member}"
        state.setdefault("iam_bindings", []).append({"member": member, "role": role})
        _event(state, f"Granted {role} to {member}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "IAM binding added"}

    if action == "remove_iam_binding":
        member = payload.get("member") or ""
        role = payload.get("role") or ""
        before = len(state.get("iam_bindings") or [])
        state["iam_bindings"] = [
            b for b in (state.get("iam_bindings") or [])
            if not (b.get("member") == member and b.get("role") == role)
        ]
        if len(state["iam_bindings"]) == before:
            return {"ok": False, "error": "IAM binding not found"}
        _event(state, f"Removed {role} from {member}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "IAM binding removed"}

    if action == "create_bucket":
        name = (payload.get("name") or f"fixitlab-{_hex(4)}").strip()
        if any(b.get("name") == name for b in state.get("buckets") or []):
            return {"ok": False, "error": f"Bucket '{name}' already exists"}
        bucket = {
            "name": name,
            "location": payload.get("location") or "US",
            "storage_class": payload.get("storage_class") or "STANDARD",
            "objects": [],
        }
        state.setdefault("buckets", []).append(bucket)
        _event(state, f"Created bucket gs://{name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Bucket created", "bucket": bucket}

    if action == "delete_bucket":
        name = payload.get("name") or ""
        before = len(state.get("buckets") or [])
        state["buckets"] = [b for b in (state.get("buckets") or []) if b.get("name") != name]
        if len(state["buckets"]) == before:
            return {"ok": False, "error": "Bucket not found"}
        _event(state, f"Deleted bucket gs://{name}", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Bucket deleted"}

    if action == "create_subnet":
        net = next(
            (n for n in state.get("networks") or []
             if n.get("name") == (payload.get("network") or "vpc-prod")),
            None,
        )
        if not net:
            return {"ok": False, "error": "VPC network not found"}
        sname = (payload.get("name") or "subnet-new").strip()
        if any(s.get("name") == sname for s in net.get("subnets") or []):
            return {"ok": False, "error": f"Subnet '{sname}' already exists"}
        subnet = {
            "name": sname,
            "region": payload.get("region") or "us-central1",
            "range": payload.get("range") or "10.128.16.0/20",
        }
        net.setdefault("subnets", []).append(subnet)
        _event(state, f"Created subnet {sname}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Subnet created", "subnet": subnet}

    if action == "create_forwarding_rule":
        fr = {
            "name": (payload.get("name") or f"fr-{_hex(4)}").strip(),
            "region": payload.get("region") or "us-central1",
            "ip": payload.get("ip") or f"34.72.{random.randint(1, 200)}.{random.randint(1, 200)}",
            "port": int(payload.get("port") or 443),
            "target": payload.get("target") or "target-pool-web",
            "backend": payload.get("backend") or [],
        }
        state.setdefault("forwarding_rules", []).append(fr)
        _event(state, f"Created forwarding rule {fr['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Forwarding rule created", "forwarding_rule": fr}

    if action == "create_snapshot":
        disk = _find_disk(state, payload.get("disk_id") or payload.get("disk_name"))
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        snap = {
            "name": (payload.get("name") or f"{disk['name']}-snap").strip(),
            "source_disk": disk["name"],
            "size_gb": disk.get("size_gb"),
            "status": "READY",
            "created": _now_iso(),
        }
        state.setdefault("snapshots", []).append(snap)
        _event(state, f"Created snapshot {snap['name']}", "success")
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
    # Fail-CLOSED on an unseeded world — see validate_azure_lab for the full
    # rationale. Replaying _apply_preset over the shipped academy-gcp-* slugs
    # leaves 117 of 147 with no `broken` key, and those all auto-passed here.
    if not state.get("_preset_applied"):
        return False, "NO_VALIDATION_SCRIPT"
    return True, "GCP validation passed"


# ---------------------------------------------------------------------------
# `gcloud` / `gsutil` CLI surface
#
# Write commands delegate to apply_action so `broken` flags, guest bridges and
# trace ids behave identically whether the learner clicked the Cloud Console or
# typed the command. Unknown commands return rc!=0 with a gcloud-shaped error;
# a silent no-op would strand a learner on a lab whose flag never cleared.
# ---------------------------------------------------------------------------

_GCLOUD_HINT = "Run 'gcloud help' to see the supported command groups."


def _gc_error(message: str, *, rc: int = 1) -> dict:
    return {"ok": False, "rc": rc, "error": message, "stdout": "", "stderr": f"ERROR: {message}"}


def _gc_ok(stdout: str, *, message: str = "") -> dict:
    return {"ok": True, "rc": 0, "stdout": stdout, "stderr": "", "message": message or stdout}


def _gc_parse(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split gcloud `--flag[=value]` pairs from positionals, underscoring keys."""
    positionals: list[str] = []
    opts: dict[str, str] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("--"):
            raw = tok[2:]
            if "=" in raw:
                key, value = raw.split("=", 1)
            else:
                key = raw
                if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                    value = tokens[i + 1]
                    i += 1
                else:
                    value = "true"
            opts[key.replace("-", "_")] = value
        else:
            positionals.append(tok)
        i += 1
    return positionals, opts


def _gc_table(headers: list[str], rows: list[list[str]]) -> str:
    """gcloud-style whitespace-aligned output (no box drawing, like the real CLI)."""
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()]
    for row in rows:
        lines.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip())
    return "\n".join(lines)


_GCLOUD_HELP = """Available command groups:
  gcloud compute instances list|describe|create|delete|start|stop|reset
  gcloud compute instances set-machine-type NAME --machine-type=TYPE
  gcloud compute instances attach-disk NAME --disk=DISK
  gcloud compute instances detach-disk NAME --disk=DISK
  gcloud compute disks list|create|snapshot
  gcloud compute snapshots list
  gcloud compute firewall-rules list|create|delete
  gcloud compute networks list  |  gcloud compute networks subnets list|create
  gcloud projects get-iam-policy|add-iam-policy-binding|remove-iam-policy-binding
  gsutil ls  |  gsutil mb gs://NAME  |  gsutil rb gs://NAME
"""


def _gc_instances(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]
    name = opts.get("name") or (rest[0] if rest else "")

    if verb == "list":
        rows = [
            [i.get("name", ""), i.get("zone", ""), i.get("machine_type", ""),
             i.get("internal_ip", ""), i.get("external_ip") or "", i.get("status", "")]
            for i in state.get("instances") or []
        ]
        return _gc_ok(_gc_table(["NAME", "ZONE", "MACHINE_TYPE", "INTERNAL_IP", "EXTERNAL_IP", "STATUS"], rows))

    if verb == "describe":
        if not name:
            return _gc_error("argument INSTANCE_NAME: Must be specified.")
        inst = _find_instance(state, name)
        if not inst:
            return _gc_error(f"The resource 'instances/{name}' was not found")
        return _gc_ok("\n".join(f"{k}: {v}" for k, v in inst.items() if not k.startswith("_")))

    if verb == "create":
        if not name:
            return _gc_error("argument INSTANCE_NAMES: Must be specified.")
        payload = {"name": name}
        if opts.get("machine_type"):
            payload["machine_type"] = opts["machine_type"]
        if opts.get("zone"):
            payload["zone"] = opts["zone"]
        if opts.get("tags"):
            payload["tags"] = [t for t in opts["tags"].split(",") if t]
        if opts.get("boot_disk_size"):
            payload["boot_disk_gb"] = opts["boot_disk_size"].rstrip("GBgb") or "20"
        return apply_action(session_id, "create_instance", payload)

    if verb in ("delete", "start", "stop", "reset"):
        if not name:
            return _gc_error("argument INSTANCE_NAMES: Must be specified.")
        action = {"delete": "delete_instance", "start": "start_instance",
                  "stop": "stop_instance", "reset": "reset_instance"}[verb]
        return apply_action(session_id, action, {"instance_name": name})

    if verb == "set-machine-type":
        if not name:
            return _gc_error("argument INSTANCE_NAME: Must be specified.")
        machine_type = opts.get("machine_type") or ""
        if not machine_type:
            return _gc_error("argument --machine-type: Must be specified.")
        return apply_action(session_id, "set_machine_type",
                            {"instance_name": name, "machine_type": machine_type})

    if verb in ("attach-disk", "detach-disk"):
        if not name:
            return _gc_error("argument INSTANCE_NAME: Must be specified.")
        disk = opts.get("disk") or ""
        if not disk:
            return _gc_error("argument --disk: Must be specified.")
        action = "attach_disk" if verb == "attach-disk" else "detach_disk"
        return apply_action(session_id, action, {"instance_name": name, "disk_name": disk})

    return _gc_error(f"Invalid choice: '{verb}'. {_GCLOUD_HINT}")


def _gc_disks(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]
    if verb == "list":
        rows = [
            [d.get("name", ""), d.get("zone", ""), str(d.get("size_gb", "")),
             d.get("type", ""), d.get("attached_to") or "", d.get("state", "")]
            for d in state.get("disks") or []
        ]
        return _gc_ok(_gc_table(["NAME", "ZONE", "SIZE_GB", "TYPE", "ATTACHED_TO", "STATUS"], rows))
    if verb == "create":
        name = opts.get("name") or (rest[0] if rest else "")
        if not name:
            return _gc_error("argument DISK_NAME: Must be specified.")
        payload = {"name": name}
        if opts.get("size"):
            payload["size_gb"] = opts["size"].rstrip("GBgb") or "100"
        if opts.get("type"):
            payload["type"] = opts["type"]
        if opts.get("zone"):
            payload["zone"] = opts["zone"]
        return apply_action(session_id, "create_disk", payload)
    if verb == "snapshot":
        disk = rest[0] if rest else opts.get("disk", "")
        if not disk:
            return _gc_error("argument DISK_NAME: Must be specified.")
        payload = {"disk_name": disk}
        if opts.get("snapshot_names"):
            payload["name"] = opts["snapshot_names"]
        return apply_action(session_id, "create_snapshot", payload)
    return _gc_error(f"Invalid choice: '{verb}'. {_GCLOUD_HINT}")


def _gc_firewall_rules(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]
    if verb == "list":
        rows = [
            [r.get("name", ""), r.get("network", ""), r.get("direction", ""),
             str(r.get("priority", "")), r.get("action", ""), r.get("protocols", "")]
            for r in state.get("firewall_rules") or []
        ]
        return _gc_ok(_gc_table(["NAME", "NETWORK", "DIRECTION", "PRIORITY", "ACTION", "ALLOW"], rows))
    if verb == "create":
        name = opts.get("name") or (rest[0] if rest else "")
        if not name:
            return _gc_error("argument NAME: Must be specified.")
        payload = {"name": name}
        # `--allow tcp:22` is the ALLOW form; `--rules` pairs with `--action`.
        if opts.get("allow"):
            payload["protocols"] = opts["allow"]
            payload["action"] = "ALLOW"
        elif opts.get("rules"):
            payload["protocols"] = opts["rules"]
            payload["action"] = (opts.get("action") or "ALLOW").upper()
        if opts.get("source_ranges"):
            payload["source_ranges"] = [r for r in opts["source_ranges"].split(",") if r]
        if opts.get("target_tags"):
            payload["target_tags"] = [t for t in opts["target_tags"].split(",") if t]
        if opts.get("network"):
            payload["network"] = opts["network"]
        if opts.get("priority"):
            payload["priority"] = opts["priority"]
        if opts.get("direction"):
            payload["direction"] = opts["direction"].upper()
        return apply_action(session_id, "create_firewall_rule", payload)
    if verb == "delete":
        name = opts.get("name") or (rest[0] if rest else "")
        if not name:
            return _gc_error("argument NAME: Must be specified.")
        return apply_action(session_id, "delete_firewall_rule", {"name": name})
    return _gc_error(f"Invalid choice: '{verb}'. {_GCLOUD_HINT}")


def _gc_networks(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    if args and args[0] == "subnets":
        rest = args[1:]
        verb = rest[0] if rest else ""
        if verb == "list":
            rows = []
            for net in state.get("networks") or []:
                for sub in net.get("subnets") or []:
                    rows.append([sub.get("name", ""), net.get("name", ""),
                                 sub.get("region", ""), sub.get("range", "")])
            return _gc_ok(_gc_table(["NAME", "NETWORK", "REGION", "RANGE"], rows))
        if verb == "create":
            name = rest[1] if len(rest) > 1 else opts.get("name", "")
            if not name:
                return _gc_error("argument NAME: Must be specified.")
            payload = {"name": name}
            for flag in ("network", "region", "range"):
                if opts.get(flag):
                    payload[flag] = opts[flag]
            return apply_action(session_id, "create_subnet", payload)
        return _gc_error(f"Invalid choice: '{verb}'. {_GCLOUD_HINT}")

    verb = args[0] if args else ""
    if verb == "list":
        rows = [[n.get("name", ""), n.get("mode", ""), str(len(n.get("subnets") or []))]
                for n in state.get("networks") or []]
        return _gc_ok(_gc_table(["NAME", "SUBNET_MODE", "SUBNETS"], rows))
    return _gc_error(f"Invalid choice: '{verb}'. {_GCLOUD_HINT}")


def _gc_projects(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    if verb == "get-iam-policy":
        rows = [[b.get("member", ""), b.get("role", "")] for b in state.get("iam_bindings") or []]
        return _gc_ok(_gc_table(["MEMBER", "ROLE"], rows))
    if verb in ("add-iam-policy-binding", "remove-iam-policy-binding"):
        member = opts.get("member") or ""
        role = opts.get("role") or ""
        if not member or not role:
            return _gc_error("arguments --member and --role: Must be specified.")
        action = "add_iam_binding" if verb == "add-iam-policy-binding" else "remove_iam_binding"
        return apply_action(session_id, action, {"member": member, "role": role})
    return _gc_error(f"Invalid choice: '{verb}'. {_GCLOUD_HINT}")


def _gsutil(state: dict, session_id: str, tokens: list[str]) -> dict:
    verb = tokens[0] if tokens else ""
    rest = tokens[1:]

    def _strip(uri: str) -> str:
        return uri[len("gs://"):].rstrip("/") if uri.startswith("gs://") else uri.rstrip("/")

    if verb == "ls":
        if rest:
            bucket_name = _strip(rest[0])
            bucket = next((b for b in state.get("buckets") or [] if b.get("name") == bucket_name), None)
            if not bucket:
                return _gc_error(f"BucketNotFoundException: 404 gs://{bucket_name} bucket does not exist.")
            return _gc_ok("\n".join(f"gs://{bucket_name}/{o['name']}" for o in bucket.get("objects") or []))
        return _gc_ok("\n".join(f"gs://{b['name']}/" for b in state.get("buckets") or []))
    if verb == "mb":
        if not rest:
            return _gc_error("CommandException: The mb command requires a bucket URL.")
        return apply_action(session_id, "create_bucket", {"name": _strip(rest[0])})
    if verb == "rb":
        if not rest:
            return _gc_error("CommandException: The rb command requires a bucket URL.")
        return apply_action(session_id, "delete_bucket", {"name": _strip(rest[0])})
    return _gc_error(f"CommandException: Invalid command '{verb}'.")


def run_command(session_id: str, command: str) -> dict:
    """Execute one `gcloud ...` or `gsutil ...` line against the session state.

    Returns a shell-shaped dict ({ok, rc, stdout, stderr}). Unrecognized
    commands always come back rc!=0.
    """
    import shlex

    raw = (command or "").strip()
    if not raw:
        return _gc_error("Command name argument expected. " + _GCLOUD_HINT)

    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return _gc_error(f"Could not parse command ({exc})")

    if not tokens:
        return _gc_error("Command name argument expected. " + _GCLOUD_HINT)

    binary = tokens[0]
    if binary not in ("gcloud", "gsutil"):
        return _gc_error(f"'{binary}' is not a recognized command. {_GCLOUD_HINT}")
    tokens = tokens[1:]
    if not tokens:
        return _gc_error("Command name argument expected. " + _GCLOUD_HINT)

    if tokens[0] in ("help", "--help", "-h"):
        return _gc_ok(_GCLOUD_HELP)

    entry = _ensure(session_id)
    state = entry["state"]
    _advance_lifecycle(state)

    if not state.get("session", {}).get("logged_in"):
        return _gc_error(
            "(gcloud.auth) You do not currently have an active account selected. "
            "Run 'gcloud auth login' (or sign in to the Cloud Console) first.",
        )

    if binary == "gsutil":
        return _gsutil(state, session_id, tokens)

    positionals, opts = _gc_parse(tokens)
    if not positionals:
        return _gc_error("Command name argument expected. " + _GCLOUD_HINT)

    group = positionals[0]
    args = positionals[1:]

    if group == "auth":
        # Past the sign-in gate above, `gcloud auth login` is a successful no-op.
        if args and args[0] == "login":
            return _gc_ok(f"Already authenticated as {state['session'].get('user', '')}.")
        return _gc_error(f"Invalid choice: '{args[0] if args else ''}'. {_GCLOUD_HINT}")

    if group == "compute":
        if not args:
            return _gc_error("Command name argument expected. " + _GCLOUD_HINT)
        sub, rest = args[0], args[1:]
        if sub == "instances":
            return _gc_instances(state, session_id, rest, opts)
        if sub == "disks":
            return _gc_disks(state, session_id, rest, opts)
        if sub == "firewall-rules":
            return _gc_firewall_rules(state, session_id, rest, opts)
        if sub == "networks":
            return _gc_networks(state, session_id, rest, opts)
        if sub == "snapshots" and rest and rest[0] == "list":
            rows = [[s.get("name", ""), str(s.get("size_gb", "")), s.get("source_disk", ""), s.get("status", "")]
                    for s in state.get("snapshots") or []]
            return _gc_ok(_gc_table(["NAME", "DISK_SIZE_GB", "SRC_DISK", "STATUS"], rows))
        if sub == "forwarding-rules" and rest and rest[0] == "list":
            rows = [[f.get("name", ""), f.get("region", ""), f.get("ip", ""),
                     str(f.get("port", "")), f.get("target", "")]
                    for f in state.get("forwarding_rules") or []]
            return _gc_ok(_gc_table(["NAME", "REGION", "IP_ADDRESS", "PORT", "TARGET"], rows))
        return _gc_error(f"Invalid choice: '{sub}'. {_GCLOUD_HINT}")

    if group == "projects":
        return _gc_projects(state, session_id, args, opts)

    return _gc_error(f"Invalid choice: '{group}'. {_GCLOUD_HINT}")
