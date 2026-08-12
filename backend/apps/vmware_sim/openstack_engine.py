"""In-memory OpenStack Horizon console for cloud training labs.

Server-authoritative session state: Keystone project, Nova instances,
Neutron networks, Cinder volumes, Glance images. Zero real OpenStack APIs.
"""

from __future__ import annotations

import copy
import json
import random
import time
from typing import Any

from django.core.cache import cache

from .openstack_v2_facades import apply_v2_action, ensure_v2, seed_v2

SESSION_TTL = 7200
PENDING_SECONDS = 3

FLAVORS: dict[str, dict[str, Any]] = {
    "m1.tiny": {"vcpus": 1, "ram_gb": 1, "disk_gb": 10},
    "m1.small": {"vcpus": 1, "ram_gb": 2, "disk_gb": 20},
    "m1.medium": {"vcpus": 2, "ram_gb": 4, "disk_gb": 40},
    "m1.large": {"vcpus": 4, "ram_gb": 8, "disk_gb": 80},
    "m1.xlarge": {"vcpus": 8, "ram_gb": 16, "disk_gb": 160},
}

_HEX = "0123456789abcdef"


def _hex(n: int) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _uuid() -> str:
    return f"{_hex(8)}-{_hex(4)}-{_hex(4)}-{_hex(4)}-{_hex(12)}"


def _session_key(session_id: str) -> str:
    return f"openstack_session:{session_id}"


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
    state.setdefault("events", []).insert(0, {
        "time": _now_iso(), "message": message, "severity": severity,
    })


def _find_instance(state: dict, ident: str) -> dict | None:
    for inst in state.get("instances", []):
        if inst.get("id") == ident or inst.get("name") == ident:
            return inst
    return None


def _find_volume(state: dict, ident: str) -> dict | None:
    return next((v for v in state.get("volumes", []) if v.get("id") == ident or v.get("name") == ident), None)


def _base_state() -> dict:
    project = "fixitlab-prod"
    net_id = _uuid()
    vol_id = _uuid()
    inst_id = _uuid()
    return {
        "session": {"logged_in": False, "user": ""},
        "project": {"id": _uuid(), "name": project, "domain": "Default"},
        "flavors": [{"name": k, **v} for k, v in FLAVORS.items()],
        "images": [
            {"id": _uuid(), "name": "cirros-0.6.2", "status": "active", "size_gb": 1},
            {"id": _uuid(), "name": "ubuntu-22.04", "status": "active", "size_gb": 8},
            {"id": _uuid(), "name": "rhel-9", "status": "active", "size_gb": 10},
        ],
        "networks": [
            {
                "id": net_id, "name": "private", "project": project,
                "subnets": [{"name": "private-subnet", "cidr": "10.0.0.0/24", "gateway": "10.0.0.1"}],
                "status": "ACTIVE",
            },
            {
                "id": _uuid(), "name": "public", "project": project,
                "subnets": [{"name": "public-subnet", "cidr": "172.24.4.0/24", "gateway": "172.24.4.1"}],
                "status": "ACTIVE",
            },
        ],
        "volumes": [
            {
                "id": vol_id, "name": "vol-web-data", "size_gb": 50, "status": "available",
                "attached_to": None, "device": None, "bootable": False,
            },
        ],
        "security_groups": [
            {
                "id": _uuid(), "name": "default",
                "rules": [
                    {"direction": "ingress", "protocol": "tcp", "port_min": 22, "port_max": 22, "remote": "0.0.0.0/0"},
                    {"direction": "egress", "protocol": "any", "port_min": None, "port_max": None, "remote": "0.0.0.0/0"},
                ],
            },
            {
                "id": _uuid(), "name": "web",
                "rules": [
                    {"direction": "ingress", "protocol": "tcp", "port_min": 80, "port_max": 80, "remote": "0.0.0.0/0"},
                    {"direction": "ingress", "protocol": "tcp", "port_min": 443, "port_max": 443, "remote": "0.0.0.0/0"},
                ],
            },
        ],
        "floating_ips": [
            {"id": _uuid(), "address": "172.24.4.100", "pool": "public", "status": "DOWN", "instance": None},
        ],
        "instances": [
            {
                "id": inst_id, "name": "web-01", "status": "ACTIVE",
                "flavor": "m1.medium", "image": "ubuntu-22.04",
                "network": "private", "private_ip": "10.0.0.15",
                "power_state": "Running", "created": _now_iso(),
                "lab_managed": False,
            },
        ],
        "events": [
            {"time": _now_iso(), "message": "Horizon dashboard ready", "severity": "info"},
        ],
        "goal": {
            "title": "OpenStack operations",
            "summary": "Manage Nova instances, Neutron networks, and Cinder volumes from Horizon.",
        },
        "broken": {},
        **seed_v2(),
    }


def _scenario_overlay(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    if "attach" in slug or "volume" in slug:
        state["goal"] = {
            "title": "Attach Cinder volume",
            "summary": "Attach vol-web-data to web-01, then confirm the disk in the lab terminal with lsblk.",
        }
        state["broken"] = {"volume_unattached": True}
        state["_preset_applied"] = True
    elif "stop" in slug or "power" in slug:
        inst = state["instances"][0]
        inst["status"] = "SHUTOFF"
        inst["power_state"] = "Shutdown"
        state["goal"] = {
            "title": "Restore instance power",
            "summary": "web-01 is SHUTOFF after a maintenance window. Start it from Horizon.",
        }
        state["broken"] = {"instance_stopped": True}
        state["_preset_applied"] = True
    elif "create" in slug or "launch" in slug:
        state["goal"] = {
            "title": "Launch a Nova instance",
            "summary": "Launch app-02 from ubuntu-22.04 on the private network using m1.small.",
        }
        state["broken"] = {"needs_instance": True}
        state["_preset_applied"] = True
    else:
        # Keyword overlay matched nothing — console has no objective for this
        # slug. validate_openstack_lab returns NO_VALIDATION_SCRIPT so Check
        # can fall through to the terminal sentinel (azure/gcp/aws pattern).
        state["_preset_applied"] = False


def _ensure(session_id: str, scenario_slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _scenario_overlay(state, scenario_slug)
        entry = {"scenario_slug": scenario_slug or "", "state": state}
        _save(session_id, entry)
    elif scenario_slug and not entry.get("scenario_slug"):
        entry["scenario_slug"] = scenario_slug
        _save(session_id, entry)
    return entry


def _advance_lifecycle(state: dict) -> bool:
    changed = False
    for inst in state.get("instances", []):
        transition = inst.get("_transition")
        if not transition:
            continue
        if _now() - transition.get("started_ts", 0) >= PENDING_SECONDS:
            inst["status"] = transition["status"]
            inst["power_state"] = transition["power_state"]
            inst.pop("_transition", None)
            changed = True
    return changed


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    if set(entry["state"].keys()) != keys_before:
        _save(session_id, entry)
    if _advance_lifecycle(entry["state"]):
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
        primary = state["instances"][0] if state.get("instances") else None
        if primary:
            sync_openstack_instance(session_id, primary, flavors=FLAVORS)
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


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if entry is None and action in ("create_instance", "login"):
        entry = _ensure(session_id, payload.get("scenario_slug") or "")
    if not entry:
        return {"ok": False, "error": "Session not found"}
    state = entry["state"]
    _advance_lifecycle(state)

    if action == "login":
        state["session"]["logged_in"] = True
        state["session"]["user"] = payload.get("user") or "admin"
        _event(state, f"Signed in as {state['session']['user']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Authenticated"}

    if action == "logout":
        state["session"]["logged_in"] = False
        state["session"]["user"] = ""
        _save(session_id, entry)
        return {"ok": True}

    if not state.get("session", {}).get("logged_in") and action != "login":
        return {"ok": False, "error": "Not authenticated"}

    if action == "create_instance":
        name = (payload.get("name") or "instance-new").strip()
        flavor = payload.get("flavor") or "m1.small"
        if flavor not in FLAVORS:
            return {"ok": False, "error": f"Unknown flavor '{flavor}'"}
        image = payload.get("image") or "ubuntu-22.04"
        network = payload.get("network") or "private"
        last_octet = 20 + len(state.get("instances", []))
        inst = {
            "id": _uuid(),
            "name": name,
            "status": "BUILD",
            "flavor": flavor,
            "image": image,
            "network": network,
            "private_ip": f"10.0.0.{last_octet}",
            "power_state": "No State",
            "created": _now_iso(),
            "lab_managed": True,
            "_transition": {
                "started_ts": _now(),
                "status": "ACTIVE",
                "power_state": "Running",
            },
        }
        state.setdefault("instances", []).append(inst)
        # Launch labs seed needs_instance; creating any instance clears it.
        broken = state.setdefault("broken", {})
        if broken.get("needs_instance"):
            broken.pop("needs_instance", None)
        _event(state, f"Launching instance {name} ({flavor})", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
            sync_openstack_instance(session_id, {**inst, "status": "ACTIVE", "power_state": "Running"}, flavors=FLAVORS)
        except Exception:
            pass
        return {"ok": True, "message": "Instance create started", "instance": inst}

    if action in ("start_instance", "stop_instance", "reboot_instance"):
        inst = _find_instance(state, payload.get("instance_id") or payload.get("name") or "")
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if action == "start_instance":
            inst["status"] = "ACTIVE"
            inst["power_state"] = "Running"
            op = "start"
            broken = state.setdefault("broken", {})
            if broken.get("instance_stopped"):
                broken.pop("instance_stopped", None)
        elif action == "stop_instance":
            inst["status"] = "SHUTOFF"
            inst["power_state"] = "Shutdown"
            op = "stop"
        else:
            inst["status"] = "REBOOT"
            inst["power_state"] = "Running"
            inst["_transition"] = {
                "started_ts": _now(), "status": "ACTIVE", "power_state": "Running",
            }
            op = "restart"
        _event(state, f"{op.title()} instance {inst['name']}", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            openstack_bridge.record_instance_power(str(session_id), op)
            from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
            sync_openstack_instance(session_id, inst, flavors=FLAVORS)
        except Exception:
            pass
        return {"ok": True, "message": f"Instance {op} requested"}

    if action == "delete_instance":
        ident = payload.get("instance_id") or payload.get("name") or ""
        before = len(state.get("instances", []))
        state["instances"] = [i for i in state.get("instances", []) if i.get("id") != ident and i.get("name") != ident]
        if len(state["instances"]) == before:
            return {"ok": False, "error": "Instance not found"}
        _event(state, f"Deleted instance {ident}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Instance deleted"}

    if action == "attach_volume":
        vol = _find_volume(state, payload.get("volume_id") or payload.get("name") or "")
        inst = _find_instance(state, payload.get("instance_id") or payload.get("instance") or "")
        if not vol:
            return {"ok": False, "error": "Volume not found"}
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if vol.get("status") == "in-use":
            return {"ok": False, "error": "Volume already attached"}
        device = payload.get("device") or "/dev/vdb"
        vol["status"] = "in-use"
        vol["attached_to"] = inst["id"]
        vol["device"] = device
        broken = state.setdefault("broken", {})
        if broken.get("volume_unattached"):
            broken.pop("volume_unattached", None)
        _event(state, f"Attached {vol['name']} to {inst['name']} at {device}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            openstack_bridge.record_disk_attach(
                str(session_id), vol["name"], size_gb=int(vol.get("size_gb") or 50), device=device,
            )
        except Exception:
            pass
        return {"ok": True, "message": "Volume attached", "device": device}

    if action == "detach_volume":
        vol = _find_volume(state, payload.get("volume_id") or payload.get("name") or "")
        if not vol:
            return {"ok": False, "error": "Volume not found"}
        device = vol.get("device")
        vol["status"] = "available"
        vol["attached_to"] = None
        vol["device"] = None
        _event(state, f"Detached volume {vol['name']}", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            if device:
                openstack_bridge.record_disk_detach(str(session_id), device)
        except Exception:
            pass
        return {"ok": True, "message": "Volume detached"}

    if action == "resize_instance":
        inst = _find_instance(state, payload.get("instance_id") or payload.get("name") or "")
        flavor = payload.get("flavor") or ""
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        if flavor not in FLAVORS:
            return {"ok": False, "error": f"Unknown flavor '{flavor}'"}
        inst["flavor"] = flavor
        _event(state, f"Resized {inst['name']} to {flavor}", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import openstack_bridge
            openstack_bridge.record_instance_resize(str(session_id), FLAVORS[flavor])
            from apps.labs.provisioner.simulation.server_identity import sync_openstack_instance
            sync_openstack_instance(session_id, inst, flavors=FLAVORS)
        except Exception:
            pass
        return {"ok": True, "message": "Resize complete"}

    if action == "create_security_group":
        name = (payload.get("name") or "sg-new").strip()
        if any(sg.get("name") == name for sg in state.get("security_groups", [])):
            return {"ok": False, "error": f"Security group {name} already exists"}
        sg = {"id": _uuid(), "name": name, "rules": payload.get("rules") or []}
        state.setdefault("security_groups", []).append(sg)
        _event(state, f"Created security group {name}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Security group created", "id": sg["id"]}

    if action == "add_security_group_rule":
        sg = next((s for s in state.get("security_groups", []) if s.get("name") == payload.get("name") or s.get("id") == payload.get("sg_id")), None)
        if not sg:
            return {"ok": False, "error": "Security group not found"}
        rule = {
            "direction": payload.get("direction") or "ingress",
            "protocol": payload.get("protocol") or "tcp",
            "port_min": int(payload.get("port_min") or payload.get("port") or 0) or None,
            "port_max": int(payload.get("port_max") or payload.get("port") or 0) or None,
            "remote": payload.get("remote") or "0.0.0.0/0",
        }
        sg.setdefault("rules", []).append(rule)
        _event(state, f"Added rule to {sg['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Rule added"}

    if action == "allocate_floating_ip":
        fip = {
            "id": _uuid(),
            "address": payload.get("address") or f"172.24.4.{random.randint(50, 200)}",
            "pool": payload.get("pool") or "public",
            "status": "DOWN",
            "instance": None,
        }
        state.setdefault("floating_ips", []).append(fip)
        _event(state, f"Allocated floating IP {fip['address']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Floating IP allocated", "floating_ip": fip}

    if action == "associate_floating_ip":
        addr = payload.get("address") or payload.get("floating_ip") or ""
        fip = next((f for f in state.get("floating_ips", []) if f.get("address") == addr or f.get("id") == addr), None)
        inst = _find_instance(state, payload.get("instance_id") or payload.get("instance") or "")
        if not fip:
            return {"ok": False, "error": "Floating IP not found"}
        if not inst:
            return {"ok": False, "error": "Instance not found"}
        fip["status"] = "ACTIVE"
        fip["instance"] = inst["id"]
        inst["floating_ip"] = fip["address"]
        _event(state, f"Associated {fip['address']} with {inst['name']}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Floating IP associated"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or action, "success")
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action '{action}'"}


# ---------------------------------------------------------------------------
# `openstack` CLI surface
#
# Every write command routes back through apply_action rather than touching
# state directly, so the `broken` flag clears and the Linux-guest bridges fire
# identically whether the learner clicked Horizon or typed the command. Read
# commands render from state so `openstack server list` can never disagree with
# the dashboard.
# ---------------------------------------------------------------------------

_CLI_PROMPT_HINT = "Try 'openstack help' for the supported command list."


def _cli_error(message: str, *, rc: int = 2) -> dict:
    """Shell-shaped failure. rc is non-zero so graders and learners both see it."""
    return {"ok": False, "rc": rc, "error": message, "stdout": "", "stderr": message}


def _cli_ok(stdout: str, *, message: str = "") -> dict:
    return {"ok": True, "rc": 0, "stdout": stdout, "stderr": "", "message": message or stdout}


def _parse_cli_opts(tokens: list[str]) -> tuple[list[str], dict[str, str]]:
    """Split `--flag value` / `--flag=value` pairs out of positional args.

    Flags are normalized to underscore keys so they line up with apply_action
    payload names (`--port-min 80` -> `port_min`). A flag with no value is
    treated as a boolean present-flag.
    """
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


def _fmt_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render an ONTAP/OpenStack-style aligned table; header only when empty."""
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [sep, "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |", sep]
    for row in rows:
        out.append("| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)) + " |")
    out.append(sep)
    return "\n".join(out)


_CLI_HELP = """Supported commands:
  openstack server list|show|create|delete|start|stop|reboot|resize
  openstack volume list|show|create
  openstack server add volume <server> <volume> [--device DEV]
  openstack server remove volume <server> <volume>
  openstack network list
  openstack image list
  openstack flavor list
  openstack security group list|create
  openstack security group rule create <group> [--protocol P] [--dst-port N]
  openstack floating ip list|create|set
"""


def _cli_server(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]

    if verb == "list":
        rows = [
            [i.get("id", ""), i.get("name", ""), i.get("status", ""),
             f"{i.get('network', '')}={i.get('private_ip', '')}", i.get("image", ""), i.get("flavor", "")]
            for i in state.get("instances", [])
        ]
        return _cli_ok(_fmt_table(["ID", "Name", "Status", "Networks", "Image", "Flavor"], rows))

    if verb == "show":
        if not rest:
            return _cli_error("openstack server show: a server name or ID is required")
        inst = _find_instance(state, rest[0])
        if not inst:
            return _cli_error(f"No server with a name or ID of '{rest[0]}' exists.")
        rows = [[k, str(v)] for k, v in inst.items() if not k.startswith("_")]
        return _cli_ok(_fmt_table(["Field", "Value"], rows))

    if verb == "create":
        if not rest and not opts.get("name"):
            return _cli_error("openstack server create: a server name is required")
        payload = {
            "name": opts.get("name") or rest[0],
            "flavor": opts.get("flavor") or "m1.small",
            "image": opts.get("image") or "ubuntu-22.04",
            "network": opts.get("network") or opts.get("nic") or "private",
        }
        return apply_action(session_id, "create_instance", payload)

    if verb in ("delete", "start", "stop", "reboot"):
        if not rest:
            return _cli_error(f"openstack server {verb}: a server name or ID is required")
        action = {"delete": "delete_instance", "start": "start_instance",
                  "stop": "stop_instance", "reboot": "reboot_instance"}[verb]
        return apply_action(session_id, action, {"instance_id": rest[0]})

    if verb == "resize":
        if not rest:
            return _cli_error("openstack server resize: a server name or ID is required")
        flavor = opts.get("flavor") or ""
        if not flavor:
            return _cli_error("openstack server resize: --flavor is required")
        return apply_action(session_id, "resize_instance", {"instance_id": rest[0], "flavor": flavor})

    # `openstack server add volume <server> <volume>` and its remove counterpart.
    if verb in ("add", "remove") and rest and rest[0] == "volume":
        operands = rest[1:]
        if len(operands) < 2:
            return _cli_error(f"openstack server {verb} volume: <server> and <volume> are required")
        server, volume = operands[0], operands[1]
        if verb == "add":
            payload = {"instance_id": server, "volume_id": volume}
            if opts.get("device"):
                payload["device"] = opts["device"]
            return apply_action(session_id, "attach_volume", payload)
        return apply_action(session_id, "detach_volume", {"volume_id": volume})

    return _cli_error(f"openstack server: '{verb}' is not a recognized subcommand. {_CLI_PROMPT_HINT}")


def _cli_volume(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]

    if verb == "list":
        rows = [
            [v.get("id", ""), v.get("name", ""), v.get("status", ""),
             str(v.get("size_gb", "")), v.get("device") or "-"]
            for v in state.get("volumes", [])
        ]
        return _cli_ok(_fmt_table(["ID", "Name", "Status", "Size", "Attached To"], rows))

    if verb == "show":
        if not rest:
            return _cli_error("openstack volume show: a volume name or ID is required")
        vol = _find_volume(state, rest[0])
        if not vol:
            return _cli_error(f"No volume with a name or ID of '{rest[0]}' exists.")
        return _cli_ok(_fmt_table(["Field", "Value"], [[k, str(v)] for k, v in vol.items()]))

    return _cli_error(f"openstack volume: '{verb}' is not a recognized subcommand. {_CLI_PROMPT_HINT}")


def _cli_security_group(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    # `security group ...` and `security group rule ...` share a prefix.
    if args and args[0] == "rule":
        rest = args[1:]
        verb = rest[0] if rest else ""
        if verb == "list":
            rows = []
            for sg in state.get("security_groups", []):
                for rule in sg.get("rules", []):
                    ports = "any"
                    if rule.get("port_min"):
                        ports = f"{rule['port_min']}:{rule.get('port_max') or rule['port_min']}"
                    rows.append([sg.get("name", ""), rule.get("direction", ""),
                                 rule.get("protocol", ""), ports, rule.get("remote", "")])
            return _cli_ok(_fmt_table(["Group", "Direction", "Protocol", "Port Range", "Remote"], rows))
        if verb == "create":
            group = rest[1] if len(rest) > 1 else opts.get("group", "")
            if not group:
                return _cli_error("openstack security group rule create: a group name is required")
            port = opts.get("dst_port") or opts.get("port") or ""
            payload = {
                "name": group,
                "direction": "egress" if opts.get("egress") else "ingress",
                "protocol": opts.get("protocol") or "tcp",
                "remote": opts.get("remote_ip") or opts.get("remote") or "0.0.0.0/0",
            }
            if port:
                # `--dst-port 8080:8090` is valid ONTAP-style range syntax.
                low, _, high = port.partition(":")
                payload["port_min"] = low
                payload["port_max"] = high or low
            return apply_action(session_id, "add_security_group_rule", payload)
        return _cli_error(f"openstack security group rule: '{verb}' is not recognized. {_CLI_PROMPT_HINT}")

    verb = args[0] if args else ""
    rest = args[1:]
    if verb == "list":
        rows = [[sg.get("id", ""), sg.get("name", ""), str(len(sg.get("rules", [])))]
                for sg in state.get("security_groups", [])]
        return _cli_ok(_fmt_table(["ID", "Name", "Rules"], rows))
    if verb == "create":
        if not rest:
            return _cli_error("openstack security group create: a name is required")
        return apply_action(session_id, "create_security_group", {"name": rest[0]})
    return _cli_error(f"openstack security group: '{verb}' is not recognized. {_CLI_PROMPT_HINT}")


def _cli_floating_ip(state: dict, session_id: str, args: list[str], opts: dict) -> dict:
    verb = args[0] if args else ""
    rest = args[1:]
    if verb == "list":
        rows = [[f.get("id", ""), f.get("address", ""), f.get("pool", ""),
                 f.get("instance") or "-", f.get("status", "")]
                for f in state.get("floating_ips", [])]
        return _cli_ok(_fmt_table(["ID", "Floating IP", "Pool", "Port", "Status"], rows))
    if verb == "create":
        return apply_action(session_id, "allocate_floating_ip", {"pool": rest[0] if rest else "public"})
    if verb == "set":
        # `openstack floating ip set --port <server> <address>` — accept either order.
        server = opts.get("port") or opts.get("server") or (rest[1] if len(rest) > 1 else "")
        address = rest[0] if rest else ""
        if not server or not address:
            return _cli_error("openstack floating ip set: an address and --port <server> are required")
        return apply_action(session_id, "associate_floating_ip", {"address": address, "instance_id": server})
    return _cli_error(f"openstack floating ip: '{verb}' is not recognized. {_CLI_PROMPT_HINT}")


def run_command(session_id: str, command: str) -> dict:
    """Execute one `openstack ...` CLI line against the session state.

    Returns a shell-shaped dict ({ok, rc, stdout, stderr}). Unknown commands
    always come back rc!=0 — a silent no-op would let a learner believe they
    solved a lab whose `broken` flag never cleared.
    """
    import shlex

    raw = (command or "").strip()
    if not raw:
        return _cli_error("openstack: no command given. " + _CLI_PROMPT_HINT)

    try:
        tokens = shlex.split(raw)
    except ValueError as exc:
        return _cli_error(f"openstack: could not parse command ({exc})")

    if tokens and tokens[0] == "openstack":
        tokens = tokens[1:]
    if not tokens:
        return _cli_error("openstack: no command given. " + _CLI_PROMPT_HINT)

    if tokens[0] in ("help", "--help", "-h"):
        return _cli_ok(_CLI_HELP)

    entry = _ensure(session_id)
    state = entry["state"]
    _advance_lifecycle(state)

    if not state.get("session", {}).get("logged_in"):
        return _cli_error(
            "Missing value auth-url required for auth plugin password — "
            "source the RC file (or sign in to Horizon) first.",
            rc=1,
        )

    positionals, opts = _parse_cli_opts(tokens)
    if not positionals:
        return _cli_error("openstack: no object given. " + _CLI_PROMPT_HINT)

    obj = positionals[0]
    args = positionals[1:]

    if obj == "server":
        return _cli_server(state, session_id, args, opts)
    if obj == "volume":
        return _cli_volume(state, session_id, args, opts)
    if obj == "security" and args and args[0] == "group":
        return _cli_security_group(state, session_id, args[1:], opts)
    if obj == "floating" and args and args[0] == "ip":
        return _cli_floating_ip(state, session_id, args[1:], opts)

    if obj == "network" and args and args[0] == "list":
        rows = [[n.get("id", ""), n.get("name", ""),
                 ",".join(s.get("cidr", "") for s in n.get("subnets", [])), n.get("status", "")]
                for n in state.get("networks", [])]
        return _cli_ok(_fmt_table(["ID", "Name", "Subnets", "Status"], rows))

    if obj == "image" and args and args[0] == "list":
        rows = [[i.get("id", ""), i.get("name", ""), i.get("status", "")]
                for i in state.get("images", [])]
        return _cli_ok(_fmt_table(["ID", "Name", "Status"], rows))

    if obj == "flavor" and args and args[0] == "list":
        rows = [[f.get("name", ""), str(f.get("vcpus", "")), str(f.get("ram_gb", "")), str(f.get("disk_gb", ""))]
                for f in state.get("flavors", [])]
        return _cli_ok(_fmt_table(["Name", "VCPUs", "RAM (GB)", "Disk (GB)"], rows))

    return _cli_error(f"openstack: '{obj}' is not an openstack command. {_CLI_PROMPT_HINT}")


# ---------------------------------------------------------------------------
# Grader — fail-CLOSED, matching azure/gcp/aws.
# ---------------------------------------------------------------------------

def validate_openstack_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    """Grade per-scenario objectives from the broken-marker seeded at ensure time.

    Fail-closed: an unmapped slug with no console objective must not auto-pass —
    it returns NO_VALIDATION_SCRIPT so the provisioner can fall through to the
    terminal sentinel path (same contract as validate_azure_lab).
    """
    entry = _load(session_id)
    if not entry:
        return False, "No OpenStack session"
    state = entry["state"]
    broken = state.get("broken") or {}
    if broken:
        kind = next(iter(broken.keys()))
        return False, f"Unresolved OpenStack issue ({kind})"
    if any(i.get("_transition") for i in state.get("instances") or []):
        return False, "An instance is still transitioning — wait for it to settle"
    if not state.get("_preset_applied"):
        return False, "NO_VALIDATION_SCRIPT"
    return True, "OpenStack validation passed"
