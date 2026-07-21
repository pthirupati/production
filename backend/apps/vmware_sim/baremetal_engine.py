"""In-memory MAAS / LXD / KVM bare-metal simulator for training labs.

MAAS machines model a real commissioning/deploy lifecycle that advances on
wall-clock time (New -> Commissioning -> Ready -> Allocated -> Deploying ->
Deployed, plus Failed).  A machine started commissioning at t0 keeps advancing
even when no request comes in — every read/action/validate calls ``_tick`` which
recomputes status + progress from ``time.time()`` deltas.

Grading (``validate_baremetal_lab``) is unchanged in contract: the lab passes
only when the ``broken`` map is empty.  The ``broken`` flags are cleared by the
action that *initiates* the fix (commission / deploy / start / power-on), so a
learner who kicks off the right action grades as complete; the visible machine
status advances afterwards over wall-clock to look realistic.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

from .baremetal_v2_facades import apply_v2_action, ensure_v2

SESSION_TTL = 7200

# Wall-clock durations (seconds) for each async phase.  Kept short so a learner
# sees the machine reach the terminal state within a single lab sitting.
COMMISSION_SECONDS = 18
DEPLOY_SECONDS = 22

# Canonical MAAS lifecycle order used for detail-view rendering / validation.
LIFECYCLE = [
    "New",
    "Commissioning",
    "Ready",
    "Allocated",
    "Deploying",
    "Deployed",
    "Failed",
]


def _session_key(session_id: str) -> str:
    return f"baremetal_session:{session_id}"


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


def _log(machine: dict, message: str) -> None:
    machine.setdefault("log", []).append({"time": _now_iso(), "message": message})
    # Keep the boot/commissioning log bounded.
    if len(machine["log"]) > 40:
        machine["log"] = machine["log"][-40:]


def _default_interfaces(mid: int) -> list[dict]:
    return [
        {"name": "eth0", "mac": f"52:54:00:aa:bb:{mid:02d}", "link": "up", "vlan": "pxe"},
        {"name": "eth1", "mac": f"52:54:00:cc:dd:{mid:02d}", "link": "down", "vlan": "mgmt"},
    ]


def _default_storage() -> list[dict]:
    return [
        {"name": "sda", "size_gb": 480, "type": "SSD", "role": "root"},
        {"name": "sdb", "size_gb": 1920, "type": "NVMe", "role": "unused"},
    ]


def _machine(mid: int, hostname: str, status: str, power: str, ip: str) -> dict:
    """Build a machine record with lifecycle + detail fields."""
    return {
        "id": mid,
        "hostname": hostname,
        "status": status,
        "power": power,
        "ip": ip,
        "progress": 100 if status in ("Ready", "Deployed", "Allocated") else 0,
        "phase_started_at": None,
        "phase_duration": 0,
        "arch": "amd64/generic",
        "cpu_count": 32,
        "ram_gb": 256,
        "os": "Ubuntu 22.04 LTS" if status == "Deployed" else "",
        "interfaces": _default_interfaces(mid),
        "storage": _default_storage(),
        "log": [],
    }


def _base_state() -> dict:
    m1 = _machine(1, "gpu-node-01", "Ready", "on", "10.10.1.11")
    m2 = _machine(2, "gpu-node-02", "Failed", "off", "")
    m3 = _machine(3, "storage-01", "Deployed", "on", "10.10.1.20")
    _log(m2, "Enlisted via PXE — commissioning aborted (no response from BMC)")
    _log(m1, "Commissioning complete — hardware inventory captured")
    _log(m3, "Deployment complete — Ubuntu 22.04 LTS")
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"site": "fixitlab", "version": "MAAS 3.4 / LXD 5.x / KVM 8.x"},
        "maas": {
            "machines": [m1, m2, m3],
            "fabrics": [{"name": "default", "vlans": ["pxe", "mgmt"]}],
        },
        "lxd": {
            "containers": [
                {"name": "infer-svc", "status": "Running", "ipv4": "10.10.2.5", "image": "ubuntu:22.04"},
                {"name": "batch-job", "status": "Stopped", "ipv4": "", "image": "ubuntu:22.04"},
            ],
            "profiles": ["default", "gpu-passthrough"],
        },
        "kvm": {
            "vms": [
                {"name": "train-vm-1", "state": "running", "vcpu": 8, "ram_gb": 32, "ip": "192.168.122.10"},
                {"name": "train-vm-2", "state": "shut off", "vcpu": 4, "ram_gb": 16, "ip": ""},
            ],
            "networks": ["default", "br-ai"],
            "pools": ["default"],
        },
        "ipmi": {"bmc_hosts": [{"name": "gpu-node-02", "reachable": False, "power": "unknown"}]},
        "goal": {"title": "Fix bare metal", "objective": "Commission the failed MAAS machine and deploy it."},
        "broken": {"machine_needs_commission": 2, "bmc_unreachable": True},
        "events": [],
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "lxd" in slug or "lxc" in slug:
        state["goal"] = {"title": "LXD container", "objective": "Start the stopped container and verify it has an IP."}
        state["broken"] = {"container_stopped": "batch-job"}
    elif "kvm" in slug or "virsh" in slug:
        state["goal"] = {"title": "KVM VM", "objective": "Start the shut-off VM and confirm it is running."}
        state["broken"] = {"vm_stopped": "train-vm-2"}
    elif "maas" in slug:
        state["goal"] = {"title": "MAAS commission", "objective": "Commission gpu-node-02 and deploy Ubuntu."}
        state["broken"] = {"machine_needs_commission": 2, "bmc_unreachable": True}
    elif "pxe" in slug:
        state["goal"] = {"title": "PXE boot", "objective": "Fix VLAN tagging so PXE discovery succeeds."}
        state["broken"] = {"pxe_vlan_wrong": True}
    elif "ipmi" in slug and "unreachable" in slug:
        state["goal"] = {"title": "IPMI unreachable", "objective": "Restore BMC connectivity and verify IPMI responds."}
        state["broken"] = {"bmc_unreachable": True, "machine_needs_commission": 2}
    elif "thermal" in slug or "gpu" in slug and "commission" in slug:
        state["goal"] = {"title": "GPU thermal commission", "objective": "Clear thermal alert and complete MAAS commissioning."}
        state["broken"] = {"thermal_alert": True, "machine_needs_commission": 2}
    elif "commission" in slug and "stuck" in slug:
        state["goal"] = {"title": "Commission stuck", "objective": "Reset stuck commissioning state and redeploy the node."}
        state["broken"] = {"commission_stuck": 2}


# ── Wall-clock lifecycle advance ──────────────────────────────────────────────
_COMMISSION_STEPS = [
    (10, "PXE boot — loading MAAS ephemeral environment"),
    (30, "Running hardware discovery (lshw, lldp)"),
    (55, "Probing storage devices and NICs"),
    (80, "Uploading hardware inventory to region controller"),
    (100, "Commissioning scripts passed — machine Ready"),
]
_DEPLOY_STEPS = [
    (15, "Allocating machine and applying network config"),
    (40, "Writing OS image to root disk (curtin)"),
    (70, "Installing cloud-init and initial packages"),
    (90, "Configuring bootloader and rebooting into deployed OS"),
    (100, "Deployment complete — Ubuntu 22.04 LTS"),
]


def _advance_machine(m: dict, now: float) -> None:
    """Advance a single machine's async phase based on wall-clock elapsed time."""
    status = m.get("status")
    started = m.get("phase_started_at")
    duration = m.get("phase_duration") or 0
    if status not in ("Commissioning", "Deploying") or not started or duration <= 0:
        return

    elapsed = max(0.0, now - float(started))
    pct = int(min(100, round((elapsed / duration) * 100)))
    prev = m.get("progress") or 0

    steps = _COMMISSION_STEPS if status == "Commissioning" else _DEPLOY_STEPS
    for threshold, message in steps:
        if prev < threshold <= pct:
            _log(m, message)

    m["progress"] = pct
    if pct >= 100:
        # Phase finished — transition to the terminal state for this phase.
        m["phase_started_at"] = None
        m["phase_duration"] = 0
        if status == "Commissioning":
            m["status"] = "Ready"
            m["power"] = "on"
            if not m.get("ip"):
                m["ip"] = f"10.10.1.{10 + int(m.get('id') or 0)}"
            for iface in m.get("interfaces", []):
                if iface.get("name") == "eth0":
                    iface["link"] = "up"
        elif status == "Deploying":
            m["status"] = "Deployed"
            m["power"] = "on"
            m["os"] = "Ubuntu 22.04 LTS"


def _tick(state: dict, now: float | None = None) -> bool:
    """Advance every machine's lifecycle to the current wall-clock. Returns True if
    anything changed (so callers can persist)."""
    now = _now() if now is None else now
    changed = False
    for m in state.get("maas", {}).get("machines", []):
        before = (m.get("status"), m.get("progress"), len(m.get("log", [])))
        _advance_machine(m, now)
        if before != (m.get("status"), m.get("progress"), len(m.get("log", []))):
            changed = True
    return changed


def _find_machine(state: dict, mid: int) -> dict | None:
    for m in state.get("maas", {}).get("machines", []):
        if m.get("id") == mid:
            return m
    return None


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    ensure_v2(entry["state"])
    # Advance the lifecycle on read so status/progress reflect wall-clock time
    # even when no action has been taken since the phase started.
    _tick(entry["state"])
    _save(session_id, entry)
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": copy.deepcopy(entry["state"]),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "Bare metal session not found"}
    state = entry["state"]
    # Advance wall-clock lifecycle before handling the action so decisions are
    # made against the up-to-date state.
    _tick(state)
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "admin"}
        state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": "Signed in to bare metal console", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in first"}

    if action == "maas_commission":
        mid = int(payload.get("machine_id") or broken.get("machine_needs_commission") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        # BMC must be reachable to power-cycle for commissioning.
        for b in state["ipmi"]["bmc_hosts"]:
            b["reachable"] = True
            b["power"] = "on"
        m["status"] = "Commissioning"
        m["power"] = "on"
        m["progress"] = 0
        m["phase_started_at"] = _now()
        m["phase_duration"] = COMMISSION_SECONDS
        _log(m, "Commissioning started — powering on via IPMI")
        # Grading contract preserved: initiating the correct action clears the
        # broken flags (validation checks `broken`, not the transient status).
        broken.pop("machine_needs_commission", None)
        broken.pop("bmc_unreachable", None)
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} commissioning started", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Commissioning started"}

    if action == "maas_deploy":
        mid = int(payload.get("machine_id") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        if m.get("status") not in ("Ready", "Allocated"):
            return {"ok": False, "error": f"Machine {mid} must be Ready before deploy (is {m.get('status')})"}
        m["status"] = "Deploying"
        m["progress"] = 0
        m["phase_started_at"] = _now()
        m["phase_duration"] = DEPLOY_SECONDS
        _log(m, "Deployment started — allocating machine")
        state["events"].insert(0, {"time": _now_iso(), "message": f"Machine {mid} deployment started", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": "Deploy started"}

    if action == "maas_power":
        mid = int(payload.get("machine_id") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        target = (payload.get("power") or ("off" if m.get("power") == "on" else "on")).lower()
        m["power"] = "on" if target == "on" else "off"
        _log(m, f"Power {'on' if target == 'on' else 'off'} via IPMI")
        _save(session_id, entry)
        return {"ok": True, "message": f"Power {m['power']}"}

    if action == "ipmi_power":
        # Full `ipmitool power on|off|cycle|status` verbs against a machine's BMC.
        mid = int(payload.get("machine_id") or 2)
        m = _find_machine(state, mid)
        if not m:
            return {"ok": False, "error": f"Machine {mid} not found"}
        verb = (payload.get("verb") or payload.get("power") or "status").lower()
        # The BMC must be reachable to control power out-of-band.
        bmc = next((b for b in state["ipmi"]["bmc_hosts"]
                    if b.get("name") == m.get("hostname")), None)
        if verb == "status":
            return {"ok": True, "message": f"Chassis Power is {m.get('power', 'off')}",
                    "power": m.get("power", "off")}
        if bmc is not None and not bmc.get("reachable"):
            return {"ok": False,
                    "error": (f"IPMI to {m.get('hostname')} BMC failed — host unreachable. "
                              "Restore BMC connectivity first (ipmi_power_on).")}
        if verb == "cycle":
            # Power cycle: off, POST, PXE re-request, back on.
            m["power"] = "on"
            _log(m, "IPMI chassis power cycle — resetting host")
            _log(m, "POST: memory + CPU check passed")
            _log(m, "PXE: DHCP request on eth0 (vlan pxe) — awaiting next-server")
            state["events"].insert(0, {"time": _now_iso(),
                                       "message": f"{m.get('hostname')} power-cycled via IPMI", "severity": "info"})
            _save(session_id, entry)
            return {"ok": True, "message": f"Power cycle issued to {m.get('hostname')}",
                    "power": "on"}
        target = "on" if verb == "on" else "off"
        m["power"] = target
        _log(m, f"IPMI chassis power {target}")
        if bmc is not None:
            bmc["power"] = target
        _save(session_id, entry)
        return {"ok": True, "message": f"Chassis Power set to {target}", "power": target}

    if action == "maas_enlist":
        # A new bare-metal node PXE-boots and enlists into MAAS as "New" (the
        # first step of the enlist -> commission -> ready -> deploy lifecycle).
        machines = state["maas"]["machines"]
        new_id = (max((mm.get("id") or 0) for mm in machines) + 1) if machines else 1
        hostname = payload.get("hostname") or f"node-{new_id:02d}"
        m = _machine(new_id, hostname, "New", "off", "")
        _log(m, "PXE boot detected — enlisting into MAAS region controller")
        _log(m, "Captured BMC/MAC — machine registered as New (needs commissioning)")
        machines.append(m)
        state["ipmi"]["bmc_hosts"].append(
            {"name": hostname, "reachable": True, "power": "off"})
        state["events"].insert(0, {"time": _now_iso(),
                                   "message": f"New machine {hostname} enlisted via PXE", "severity": "info"})
        _save(session_id, entry)
        return {"ok": True, "message": f"Machine {hostname} enlisted (New)", "machine_id": new_id}

    if action == "lxd_start":
        name = payload.get("name") or broken.get("container_stopped") or "batch-job"
        for c in state["lxd"]["containers"]:
            if c["name"] == name:
                c["status"] = "Running"
                c["ipv4"] = c.get("ipv4") or "10.10.2.6"
        broken.pop("container_stopped", None)
        _save(session_id, entry)
        return {"ok": True, "message": f"Container {name} started"}

    if action == "lxd_stop":
        name = payload.get("name") or ""
        for c in state["lxd"]["containers"]:
            if c["name"] == name:
                c["status"] = "Stopped"
                c["ipv4"] = ""
        _save(session_id, entry)
        return {"ok": True, "message": f"Container {name} stopped"}

    if action == "kvm_start":
        name = payload.get("name") or broken.get("vm_stopped") or "train-vm-2"
        for v in state["kvm"]["vms"]:
            if v["name"] == name:
                v["state"] = "running"
                v["ip"] = v.get("ip") or "192.168.122.11"
        broken.pop("vm_stopped", None)
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} started"}

    if action == "kvm_stop":
        name = payload.get("name") or ""
        for v in state["kvm"]["vms"]:
            if v["name"] == name:
                v["state"] = "shut off"
                v["ip"] = ""
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} stopped"}

    if action == "fix_pxe_vlan":
        broken.pop("pxe_vlan_wrong", None)
        _save(session_id, entry)
        return {"ok": True, "message": "PXE VLAN corrected"}

    if action == "ipmi_power_on":
        for b in state["ipmi"]["bmc_hosts"]:
            b["reachable"] = True
            b["power"] = "on"
        broken.pop("bmc_unreachable", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "BMC reachable via IPMI", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "BMC power on — IPMI reachable"}

    if action == "clear_thermal_alert":
        broken.pop("thermal_alert", None)
        state["events"].insert(0, {"time": _now_iso(), "message": "Thermal alert cleared", "severity": "success"})
        _save(session_id, entry)
        return {"ok": True, "message": "Thermal threshold restored"}

    if action == "reset_commission":
        mid = int(payload.get("machine_id") or broken.get("commission_stuck") or 2)
        m = _find_machine(state, mid)
        if m:
            # Reset a stuck node back to a clean Commissioning run.
            m["status"] = "Commissioning"
            m["power"] = "on"
            m["progress"] = 0
            m["phase_started_at"] = _now()
            m["phase_duration"] = COMMISSION_SECONDS
            _log(m, "Stuck state cleared — restarting commissioning")
            if not m.get("ip"):
                m["ip"] = f"10.10.1.{10 + mid}"
        broken.pop("commission_stuck", None)
        broken.pop("machine_needs_commission", None)
        _save(session_id, entry)
        return {"ok": True, "message": "Commission reset complete"}

    if action == "create_lxd":
        name = payload.get("name") or "new-svc"
        state["lxd"]["containers"].append(
            {"name": name, "status": "Running", "ipv4": "10.10.2.7", "image": payload.get("image") or "ubuntu:22.04"}
        )
        _save(session_id, entry)
        return {"ok": True, "message": f"Container {name} created"}

    if action == "create_kvm":
        name = payload.get("name") or "new-vm"
        state["kvm"]["vms"].append(
            {"name": name, "state": "running", "vcpu": 4, "ram_gb": 8, "ip": "192.168.122.12"}
        )
        _save(session_id, entry)
        return {"ok": True, "message": f"VM {name} created"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            state.setdefault("events", []).insert(0, {
                "time": _now_iso(), "message": v2.get("message") or action, "severity": "success",
            })
            _save(session_id, entry)
        return v2

    # An action may have advanced the lifecycle even if it hit no explicit branch;
    # persist so the tick is not lost.
    _save(session_id, entry)
    return {"ok": False, "error": f"Unknown action: {action}"}


def validate_baremetal_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No bare metal session"
    # Advance the wall-clock lifecycle before grading so a machine that finished
    # commissioning/deploying between requests is scored against its real state.
    if _tick(entry["state"]):
        _save(session_id, entry)
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, "Bare metal environment still has unresolved issues"
    return True, "Bare metal lab objectives met"
