"""Cross-technology bridge: VMware simulator ⇄ Linux lab terminal.

The VMware simulator (apps.vmware_sim.engine) and the Linux lab simulator
(this package's UnifiedSimulationEngine) are SEPARATE in-memory engines, but for
a cross-technology lab they describe the SAME server and share one LabSession id.

This module is the seam between them. When the user adds a disk in the VMware
"Edit Settings → Add Hard Disk" dialog, the VMware engine records a *pending
hot-added disk* here, keyed by the lab session id. The hardware now exists at the
hypervisor, but — exactly like a real VM — the guest kernel does NOT see it until
the operator forces a SCSI rescan (`echo "- - -" > /sys/class/scsi_host/hostX/scan`
or `rescan-scsi-bus.sh`), and for some controllers not even then, until a reboot.

Storage is Django cache (Redis in prod), so a disk added on the VMware web worker
is visible to the terminal WebSocket worker — the two never share process memory.
Fail-closed by construction: with no pending disk the terminal sees nothing, so a
scenario can only be solved after the disk is genuinely added in VMware AND
revealed in the terminal AND the filesystem/LVM is actually extended.
"""

from __future__ import annotations

import json

from django.core.cache import cache

BRIDGE_TTL = 7200  # match the VMware/Linux session TTLs (2h)

# The cross-tech disk train. Each lab session hot-adds disks starting at /dev/sdc
# (sda = boot, sdb = the seeded spare), so the first VMware-added disk is sdc.
_DISK_LETTERS = "cdefghijklmnop"


def _key(session_id: str) -> str:
    return f"vmware_bridge:{session_id}"


def _load(session_id: str) -> dict:
    raw = cache.get(_key(str(session_id)))
    if raw is None:
        return {"pending": [], "revealed": []}
    data = json.loads(raw) if isinstance(raw, str) else raw
    data.setdefault("pending", [])
    data.setdefault("revealed", [])
    return data


def _save(session_id: str, data: dict) -> None:
    cache.set(_key(str(session_id)), json.dumps(data, default=str), BRIDGE_TTL)


def _next_device(data: dict) -> str:
    """Allocate the next /dev/sdX across both pending and already-revealed disks."""
    used = {d.get("dev") for d in data.get("pending", [])}
    used |= set(data.get("revealed", []))
    for letter in _DISK_LETTERS:
        dev = f"/dev/sd{letter}"
        if dev not in used:
            return dev
    return "/dev/sdz"


def record_pending_disk(
    session_id: str,
    size_gb: int = 50,
    *,
    requires_reboot: bool = False,
    device: str | None = None,
) -> str:
    """VMware add_disk → register a hot-added disk the guest cannot yet see.

    `requires_reboot=True` models a controller/scenario where even a SCSI rescan
    will not surface the disk — the operator must reboot the guest (Scenario B).
    Returns the /dev path the disk will appear as once revealed.
    """
    data = _load(session_id)
    dev = device or _next_device(data)
    # Idempotent: re-adding the same device does not duplicate it.
    if not any(d.get("dev") == dev for d in data["pending"]) and dev not in data["revealed"]:
        data["pending"].append({
            "dev": dev,
            "size_gb": int(size_gb),
            "requires_reboot": bool(requires_reboot),
        })
        _save(session_id, data)
    return dev


def has_pending_disk(session_id: str) -> bool:
    return bool(_load(session_id).get("pending"))


def pending_disks(session_id: str) -> list[dict]:
    return list(_load(session_id).get("pending", []))


def consume_revealed_disks(session_id: str, *, after_reboot: bool = False) -> list[dict]:
    """Drain the disks the guest should now see.

    A SCSI rescan (`after_reboot=False`) reveals every pending disk EXCEPT those
    flagged `requires_reboot`. A reboot (`after_reboot=True`) reveals everything
    still pending. Returned disks are moved from pending → revealed so a second
    rescan does not re-add them.
    """
    data = _load(session_id)
    pending = data.get("pending", [])
    if not pending:
        return []
    take, keep = [], []
    for disk in pending:
        if disk.get("requires_reboot") and not after_reboot:
            keep.append(disk)
        else:
            take.append(disk)
    if take:
        data["pending"] = keep
        data["revealed"] = list(data.get("revealed", [])) + [d["dev"] for d in take]
        _save(session_id, data)
    return take


def record_vm_reset(session_id: str) -> None:
    """VMware power Reset/Restart of a hung guest → mark the guest recovered so
    the terminal becomes responsive again (server-hung-needs-vmware-reset)."""
    data = _load(session_id)
    data["vm_reset"] = True
    _save(session_id, data)


def was_vm_reset(session_id: str) -> bool:
    return bool(_load(session_id).get("vm_reset"))


def record_guest_power(session_id: str, action: str) -> None:
    """Terminal → VMware: the guest OS changed power state from inside the shell
    (`reboot`, `poweroff`/`halt`/`shutdown`). The VMware engine drains this on its
    next state read and updates the VM tile (rebooting → poweredOn, or poweredOff).
    Last-writer-wins: a later action supersedes an unconsumed earlier one."""
    if action not in ("reboot", "poweroff"):
        return
    data = _load(session_id)
    data["guest_power"] = action
    _save(session_id, data)


def consume_guest_power(session_id: str) -> str | None:
    """Drain a pending guest power event (returns 'reboot' | 'poweroff' | None)."""
    data = _load(session_id)
    action = data.get("guest_power")
    if not action:
        return None
    data.pop("guest_power", None)
    _save(session_id, data)
    return action


def record_pending_nic(session_id: str, ip: str = "10.0.0.30/24") -> None:
    """VMware add_network_adapter → a NIC the guest will see (as a new link) only
    after a rescan/`ip link` brings it up (network-nic-add-vmware-rescan)."""
    data = _load(session_id)
    data["pending_nic"] = {"ip": ip}
    _save(session_id, data)


# ── Kubernetes-on-VMware: VMware VM actions ⇄ k8s node state ──────────────────
# For a cross-tech k8s lab the cluster's worker nodes ARE VMware VMs (k8s-worker-*).
# Powering on / creating that VM in VMware makes the node join and become Ready;
# resetting a hung node VM recovers a NotReady node. The K8sCluster (rebuilt per
# terminal request, a different worker) reconstructs node Ready/scheduling state by
# reading these flags from the shared cache — so the terminal's `kubectl get nodes`
# reflects the VMware action, and scheduling is fail-closed until the VM is online.
#
# Stored shape under the session key:
#   k8s_nodes_online : {node_name: True}  → node is Ready & schedulable
#   k8s_nodes_reset  : {node_name: True}  → a hung node VM was reset (recovered)
# The VMware VM name maps to the k8s node name via the VM's `k8s_node` field.

def record_k8s_node_online(session_id: str, node_name: str) -> None:
    """VMware power-on / create of a worker-node VM → that node joins as Ready."""
    if not node_name:
        return
    data = _load(session_id)
    online = data.setdefault("k8s_nodes_online", {})
    online[node_name] = True
    _save(session_id, data)


def record_k8s_node_offline(session_id: str, node_name: str) -> None:
    """VMware power-off of a worker-node VM → that node leaves the cluster.

    Clears any prior online/reset marker so a drained-then-powered-off node does
    not still count as a schedulable target."""
    if not node_name:
        return
    data = _load(session_id)
    data.get("k8s_nodes_online", {}).pop(node_name, None)
    data.get("k8s_nodes_reset", {}).pop(node_name, None)
    _save(session_id, data)


def record_k8s_node_reset(session_id: str, node_name: str) -> None:
    """VMware reset/restart of a hung worker-node VM → the NotReady node recovers."""
    if not node_name:
        return
    data = _load(session_id)
    reset = data.setdefault("k8s_nodes_reset", {})
    reset[node_name] = True
    # A reset also implies the VM is powered on again.
    data.setdefault("k8s_nodes_online", {})[node_name] = True
    _save(session_id, data)


def k8s_node_online(session_id: str, node_name: str) -> bool:
    return bool(_load(session_id).get("k8s_nodes_online", {}).get(node_name))


def k8s_node_reset(session_id: str, node_name: str) -> bool:
    return bool(_load(session_id).get("k8s_nodes_reset", {}).get(node_name))


def k8s_node_states(session_id: str) -> dict:
    """Snapshot of all node online/reset markers for this session."""
    data = _load(session_id)
    return {
        "online": dict(data.get("k8s_nodes_online", {})),
        "reset": dict(data.get("k8s_nodes_reset", {})),
    }


def consume_pending_nic(session_id: str) -> dict | None:
    data = _load(session_id)
    nic = data.get("pending_nic")
    if nic:
        data["pending_nic"] = None
        data["nic_revealed"] = nic
        _save(session_id, data)
    return nic


# ── Ansible (AWX) ⇄ Linux terminal ────────────────────────────────────────────
# For a cross-tech automation lab the AWX job template and the Linux box describe
# the SAME server sharing one lab session id. When an AWX job template that
# "configures a service" runs to SUCCESS, the AWX engine records the intended end
# state here (service installed + started + its config written), keyed by session
# id. The Linux terminal then drains this record the first time it inspects that
# service (`systemctl is-active/status`, `rpm -q`, cat of the config), exactly
# like the disk/NIC reveal train: the hardware/automation happened on the other
# engine, and the guest only reflects it once it looks.
#
# Fail-closed by construction: before the playbook runs there is NO ansible
# record, so the service reports inactive/unknown and the config file is absent.
# A scenario can only be solved after the playbook genuinely runs in AWX AND the
# terminal reveals the result AND (per the check.sh recipe) the learner confirms
# it. Multiple services are supported (a playbook may configure several); each is
# consumed independently and moved pending → applied so a re-inspect is stable.
#
# Stored shape under the session key:
#   ansible_pending : [ {service, installed, started, enabled, config_path,
#                        config_content, package} , ... ]  (not yet seen by guest)
#   ansible_applied : {service: {...}}  (already revealed to the guest)

def record_ansible_result(session_id: str, result: dict) -> None:
    """AWX job-template success → register the service state the playbook
    intended, for the Linux terminal to reveal. `result` carries at least
    `service`; optional installed/started/enabled/config_path/config_content/
    package refine what the guest shows once it inspects the unit."""
    if not result or not result.get("service"):
        return
    service = str(result["service"])
    data = _load(session_id)
    pending = data.setdefault("ansible_pending", [])
    applied = data.get("ansible_applied", {})
    entry = {
        "service": service,
        "installed": bool(result.get("installed", True)),
        "started": bool(result.get("started", True)),
        "enabled": bool(result.get("enabled", True)),
        "config_path": result.get("config_path") or "",
        "config_content": result.get("config_content") or "",
        "package": result.get("package") or service,
    }
    # Idempotent: a re-run replaces the pending record for that service rather
    # than duplicating it, and re-arms an already-applied service (a relaunch
    # re-converges the box).
    data["ansible_pending"] = [e for e in pending if e.get("service") != service]
    data["ansible_pending"].append(entry)
    applied.pop(service, None)
    _save(session_id, data)


def has_pending_ansible(session_id: str) -> bool:
    return bool(_load(session_id).get("ansible_pending"))


def pending_ansible(session_id: str) -> list[dict]:
    return list(_load(session_id).get("ansible_pending", []))


def consume_ansible_results(session_id: str) -> list[dict]:
    """Drain every service an AWX playbook configured for this session.

    Returned records are moved pending → applied so a second inspection does not
    re-apply them (but the applied snapshot is kept so a later reader can still
    tell the service came from Ansible). Returns [] when no playbook has run —
    the fail-closed default."""
    data = _load(session_id)
    pending = data.get("ansible_pending", [])
    if not pending:
        return []
    applied = data.setdefault("ansible_applied", {})
    for entry in pending:
        applied[entry["service"]] = entry
    data["ansible_pending"] = []
    _save(session_id, data)
    return list(pending)


def ansible_applied(session_id: str) -> dict:
    """Snapshot of services already revealed from Ansible (service → record)."""
    return dict(_load(session_id).get("ansible_applied", {}))


# ── Workload (Linux service / k8s pod) ⇄ Monitoring (Prometheus/Grafana) ──────
# A workload that is actually running in the Linux sim (a started systemd unit)
# or a k8s deployment with ready pods is, in the real world, a thing Prometheus
# can scrape. This bridge lets the workload side (Linux/k8s) publish a scrape
# target for the SAME lab session, which the monitoring engine reads so PromQL
# `up{...}` and the Prometheus target list reflect the real workload.
#
# Fail-closed by construction: the monitoring engine only synthesises an `up`
# series / target for a workload that has been recorded here with up=True. No
# workload recorded → no extra target, and `up` for it is absent (not fabricated
# as 1). A workload recorded with up=False surfaces as a target scraping DOWN
# (up == 0), which is what a stopped service should look like to monitoring.
#
# Stored shape under the session key:
#   workloads : {name: {name, up, job, instance, port}}

_WORKLOAD_DEFAULT_PORT = 9100


def record_workload(session_id: str, workload: dict) -> None:
    """Linux/k8s side → publish/refresh a scrape target for the monitoring
    engine. `workload` needs `name`; `up` (default True) sets whether the target
    scrapes up. Optional job/instance/port refine the emitted series labels."""
    if not workload or not workload.get("name"):
        return
    name = str(workload["name"])
    data = _load(session_id)
    workloads = data.setdefault("workloads", {})
    port = int(workload.get("port") or _WORKLOAD_DEFAULT_PORT)
    workloads[name] = {
        "name": name,
        "up": bool(workload.get("up", True)),
        "job": workload.get("job") or "workload",
        "instance": workload.get("instance") or f"{name}:{port}",
        "port": port,
    }
    _save(session_id, data)


def remove_workload(session_id: str, name: str) -> None:
    """Workload stopped/deleted → drop it so monitoring no longer scrapes it."""
    if not name:
        return
    data = _load(session_id)
    if data.get("workloads", {}).pop(name, None) is not None:
        _save(session_id, data)


def workloads(session_id: str) -> list[dict]:
    """All workloads published for this session (for the monitoring engine)."""
    return list(_load(session_id).get("workloads", {}).values())


def clear(session_id: str) -> None:
    cache.delete(_key(str(session_id)))


# ── Cross-technology scenario registry ───────────────────────────────────────
# Single source of truth shared by the VMware engine (to decide whether an
# add_disk should bridge into the terminal), the Linux presets (to hide the
# starting disk), and the API/UI (to surface the "Open VMware" affordance).
#
# Maps the cross-tech Linux scenario slug → bridge behaviour:
#   action          : which VMware hardware op the lab expects ("add_disk"/"reset"/"add_nic")
#   requires_reboot : disk stays hidden after a SCSI rescan; only a reboot reveals it
#   vmware_vm       : the VM name in the VMware inventory that represents this server
CROSS_TECH_SCENARIOS: dict[str, dict] = {
    "linux-lvm-extend-vmware-disk-rescan": {
        "action": "add_disk",
        "requires_reboot": False,
        "vmware_vm": "web-prod-01",
    },
    "linux-lvm-extend-vmware-disk-reboot": {
        "action": "add_disk",
        "requires_reboot": True,
        "vmware_vm": "web-prod-01",
    },
    "linux-datastore-full-add-disk-vmware": {
        "action": "add_disk",
        "requires_reboot": False,
        "vmware_vm": "web-prod-01",
    },
    "linux-server-hung-needs-vmware-reset": {
        "action": "reset",
        "requires_reboot": False,
        "vmware_vm": "web-prod-01",
    },
    "linux-nic-add-vmware-rescan": {
        "action": "add_nic",
        "requires_reboot": False,
        "vmware_vm": "web-prod-01",
    },
    # ── Kubernetes-on-VMware (the worker node is a VMware VM) ──
    # `tech: kubernetes` tells the engine/UI this is a k8s cross-tech lab; the
    # VMware VM named `vmware_vm` carries `k8s_node` so power/reset actions on it
    # map to the named node. `action` is the VMware op the lab expects:
    #   k8s_node_add   : power on / create the worker VM → node joins Ready
    #   k8s_node_reset : reset the hung worker VM → NotReady node recovers
    "k8s-hpa-needs-new-node-vmware": {
        "action": "k8s_node_add",
        "tech": "kubernetes",
        "vmware_vm": "k8s-worker-2",
        "k8s_node": "worker-2",
    },
    "k8s-scale-out-add-vmware-node": {
        "action": "k8s_node_add",
        "tech": "kubernetes",
        "vmware_vm": "k8s-worker-2",
        "k8s_node": "worker-2",
    },
    "k8s-daemonset-needs-node-vmware": {
        "action": "k8s_node_add",
        "tech": "kubernetes",
        "vmware_vm": "k8s-worker-2",
        "k8s_node": "worker-2",
    },
    "k8s-node-notready-vmware-reset": {
        "action": "k8s_node_reset",
        "tech": "kubernetes",
        "vmware_vm": "k8s-worker-1",
        "k8s_node": "worker-1",
    },
    "k8s-drain-node-poweroff-vmware": {
        "action": "k8s_node_add",
        "tech": "kubernetes",
        "vmware_vm": "k8s-worker-2",
        "k8s_node": "worker-2",
    },
}


def is_cross_tech_scenario(slug: str) -> bool:
    return (slug or "").lower() in CROSS_TECH_SCENARIOS


def cross_tech_config(slug: str) -> dict | None:
    return CROSS_TECH_SCENARIOS.get((slug or "").lower())


def is_k8s_cross_tech_scenario(slug: str) -> bool:
    cfg = cross_tech_config(slug)
    return bool(cfg and cfg.get("tech") == "kubernetes")
