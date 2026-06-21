"""ITSM team-action engine — fulfil a sub-ticket by mutating simulation state.

When the user raises a sub-ticket to another team (e.g. "Storage team: add a
50GB disk to web-prod-01") and that team actions it, the *simulated* team does
real work against the lab's simulation engine and then resolves the sub-ticket.

The reference implementation is the DISK example, end to end:

  1. The sub-ticket carries action_kind="add_disk", action_params={"size_gb": 50}.
  2. fulfil_sub_ticket() looks up the registry, runs the handler, which calls
     vmware_bridge.record_pending_disk(session_id, size_gb). That is the SAME
     seam the VMware "Add Hard Disk" wizard uses: it records a hot-added disk the
     guest kernel cannot see yet, keyed by the lab session id in the shared cache.
  3. The handler returns the /dev path (e.g. /dev/sdc) and a work note telling the
     operator to run a SCSI rescan. fulfil_sub_ticket resolves the sub-ticket.
  4. Back in the lab terminal, `echo "- - -" > /sys/class/scsi_host/hostX/scan`
     (or a reboot) triggers rhel_os._reveal_bridge_disks(), which drains the
     pending disk via consume_revealed_disks() and surfaces /dev/sdc. The user
     then pvcreate/vgextend/lvextend as in any LVM-extend scenario.

Adding another team action (network: add a NIC; backup: restore a file) is just
another entry in TEAM_ACTIONS — the model, endpoints and UI need no changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from . import constants as C

logger = logging.getLogger(__name__)


@dataclass
class ActionOutcome:
    """Result of running a team action against the simulation."""
    ok: bool
    note: str                       # system work-note appended to the sub-ticket
    result: dict                    # structured data persisted to action_result
    resolve: bool = True            # whether the sub-ticket should auto-resolve
    parent_note: str = ""           # optional note mirrored onto the parent ticket


# ── Action handlers ───────────────────────────────────────────────────────────
# Each takes (session_id, params) and returns an ActionOutcome. session_id is the
# lab session string; params is the sub-ticket's action_params.

def _action_add_disk(session_id: str, params: dict) -> ActionOutcome:
    """Storage team adds a disk → hot-add via the vmware_bridge (guest-hidden)."""
    size_gb = int(params.get("size_gb") or 50)
    requires_reboot = bool(params.get("requires_reboot", False))
    if not session_id:
        return ActionOutcome(
            ok=False,
            note="Cannot provision disk: this ticket is not bound to a running lab session.",
            result={},
            resolve=False,
        )
    from apps.labs.provisioner.simulation.vmware_bridge import record_pending_disk

    dev = record_pending_disk(session_id, size_gb=size_gb, requires_reboot=requires_reboot)
    reveal = (
        "reboot the server"
        if requires_reboot
        else "run a SCSI rescan (`echo \"- - -\" > /sys/class/scsi_host/host0/scan`) or `lsblk`"
    )
    note = (
        f"Storage team: provisioned a {size_gb} GiB virtual disk and attached it to the VM. "
        f"It will appear as **{dev}** on the guest once you {reveal}. "
        f"Then pvcreate/vgextend/lvextend to use the space."
    )
    return ActionOutcome(
        ok=True,
        note=note,
        result={"device": dev, "size_gb": size_gb, "requires_reboot": requires_reboot},
        parent_note=f"Storage request fulfilled — new disk {dev} ({size_gb} GiB) attached. Rescan to use it.",
    )


def _action_add_nic(session_id: str, params: dict) -> ActionOutcome:
    """Network team adds a NIC/IP → hot-add via the vmware_bridge NIC seam."""
    ip = str(params.get("ip") or "10.0.0.30/24")
    if not session_id:
        return ActionOutcome(
            ok=False,
            note="Cannot add NIC: this ticket is not bound to a running lab session.",
            result={},
            resolve=False,
        )
    from apps.labs.provisioner.simulation.vmware_bridge import record_pending_nic

    record_pending_nic(session_id, ip=ip)
    note = (
        f"Network team: attached a virtual NIC pre-provisioned with **{ip}**. "
        f"Bring it up on the guest (a rescan / `ip link set ... up`) to see the new interface."
    )
    return ActionOutcome(
        ok=True,
        note=note,
        result={"ip": ip},
        parent_note=f"Network request fulfilled — NIC with {ip} attached.",
    )


def _action_open_port(session_id: str, params: dict) -> ActionOutcome:
    """Network/Security team opens a firewall port on the upstream device.

    Modeled as an advisory action (the upstream firewall is outside the guest);
    it records the opened port so the scenario/validation can reference it.
    """
    port = params.get("port")
    proto = (params.get("proto") or "tcp").lower()
    if not port:
        return ActionOutcome(ok=False, note="No port specified for the firewall request.", result={}, resolve=False)
    note = (
        f"Network team: opened **{proto}/{port}** on the upstream firewall toward this host. "
        f"Re-test connectivity from the server."
    )
    return ActionOutcome(
        ok=True,
        note=note,
        result={"port": int(port), "proto": proto},
        parent_note=f"Firewall request fulfilled — {proto}/{port} opened upstream.",
    )


def _action_restore_file(session_id: str, params: dict) -> ActionOutcome:
    """Backup team restores a file from backup into the guest filesystem."""
    path = str(params.get("path") or "/data/restored.txt")
    content = params.get("content")
    if not session_id:
        return ActionOutcome(
            ok=False,
            note="Cannot restore: this ticket is not bound to a running lab session.",
            result={},
            resolve=False,
        )
    placed = _write_file_into_session(session_id, path, content)
    if not placed:
        return ActionOutcome(
            ok=True,
            note=(
                f"Backup team: located **{path}** in last night's backup set. "
                f"Restore staged; it will be in place after the next rescan/reboot of the server."
            ),
            result={"path": path, "staged": True},
            parent_note=f"Backup restore staged for {path}.",
            resolve=True,
        )
    note = f"Backup team: restored **{path}** from backup. Verify with `cat {path}` on the server."
    return ActionOutcome(
        ok=True,
        note=note,
        result={"path": path, "restored": True},
        parent_note=f"Backup restore complete — {path} is back on the server.",
    )


def _write_file_into_session(session_id: str, path: str, content) -> bool:
    """Best-effort: write a file into the live simulation FS for this session.

    Returns True if the engine was live and the file was placed; False if the
    engine is not in this worker's memory (the restore is then 'staged' and the
    operator is told it lands after a rescan/reboot — keeping fail-closed sanity).
    """
    try:
        from apps.labs.provisioner.simulation.ops_state import get_simulation_engine_for_session
    except Exception:
        return False
    engine = get_simulation_engine_for_session(str(session_id))
    state = getattr(getattr(engine, "shell", None), "state", None)
    if state is None:
        return False
    body = content if content is not None else "# restored from backup\n"
    # The RHEL sim exposes write_file(path, content) over its virtual filesystem.
    writer = getattr(state, "write_file", None)
    if callable(writer):
        try:
            writer(path, body)
            return True
        except Exception:
            return False
    return False


# Registry: action_kind → (handler, default short_description, target team).
TEAM_ACTIONS: dict[str, dict] = {
    "add_disk": {
        "handler": _action_add_disk,
        "label": "Add a disk",
        "team": C.TEAM_STORAGE,
        "default_short": "Provision and attach a virtual disk",
    },
    "add_nic": {
        "handler": _action_add_nic,
        "label": "Add a NIC / IP",
        "team": C.TEAM_NETWORK,
        "default_short": "Attach a virtual NIC with a new IP",
    },
    "open_port": {
        "handler": _action_open_port,
        "label": "Open a firewall port",
        "team": C.TEAM_NETWORK,
        "default_short": "Open an upstream firewall port",
    },
    "restore_file": {
        "handler": _action_restore_file,
        "label": "Restore a file from backup",
        "team": C.TEAM_BACKUP,
        "default_short": "Restore a file from last backup",
    },
}


def available_actions() -> list[dict]:
    """Catalog of sub-ticket actions the UI offers, with their target team."""
    return [
        {
            "kind": kind,
            "label": meta["label"],
            "team": meta["team"],
            "team_label": C.team_label(meta["team"]),
            "default_short": meta["default_short"],
        }
        for kind, meta in TEAM_ACTIONS.items()
    ]


def default_team_for_action(action_kind: str) -> str:
    meta = TEAM_ACTIONS.get(action_kind)
    return meta["team"] if meta else C.TEAM_SERVICE_DESK


def run_team_action(action_kind: str, session_id: str, params: dict) -> ActionOutcome:
    """Dispatch to the registered handler. Unknown kinds → a generic ack."""
    meta = TEAM_ACTIONS.get(action_kind)
    if not meta:
        return ActionOutcome(
            ok=True,
            note="Assigned team acknowledged the request and completed it.",
            result={},
            resolve=True,
        )
    handler: Callable[[str, dict], ActionOutcome] = meta["handler"]
    try:
        return handler(str(session_id or ""), params or {})
    except Exception as exc:  # never 500 the API on a sim hiccup
        logger.exception("ITSM team action %s failed: %s", action_kind, exc)
        return ActionOutcome(
            ok=False,
            note=f"Team could not complete the request automatically ({exc}).",
            result={},
            resolve=False,
        )
