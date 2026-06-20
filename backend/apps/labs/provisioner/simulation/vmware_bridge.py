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


def record_pending_nic(session_id: str, ip: str = "10.0.0.30/24") -> None:
    """VMware add_network_adapter → a NIC the guest will see (as a new link) only
    after a rescan/`ip link` brings it up (network-nic-add-vmware-rescan)."""
    data = _load(session_id)
    data["pending_nic"] = {"ip": ip}
    _save(session_id, data)


def consume_pending_nic(session_id: str) -> dict | None:
    data = _load(session_id)
    nic = data.get("pending_nic")
    if nic:
        data["pending_nic"] = None
        data["nic_revealed"] = nic
        _save(session_id, data)
    return nic


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
}


def is_cross_tech_scenario(slug: str) -> bool:
    return (slug or "").lower() in CROSS_TECH_SCENARIOS


def cross_tech_config(slug: str) -> dict | None:
    return CROSS_TECH_SCENARIOS.get((slug or "").lower())
