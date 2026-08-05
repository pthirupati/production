"""Jira team-coordinated ops state — patching, storage, network."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .unified_sim import UnifiedSimulationEngine


def init_patching_ops(state) -> None:
    """Patching labs: apps/DB running until Jira teams stop them."""
    state.ops_backup_taken = False
    state.ops_db_stopped = False
    state.ops_app_stopped = False
    state.ops_db_started = True
    state.ops_app_started = True
    state.ops_services_restarted = False
    state.mount_issue_after_reboot = True
    state.mount_filesystems_fixed = False
    for svc in ("mysqld", "nginx", "httpd"):
        if svc in state.services:
            state.services[svc].active = "active"
            state.services[svc].sub_state = "running"


def init_lvm_storage_ops(state) -> None:
    """LVM extend: new disk hidden until @storage team provisions it."""
    state.pending_storage_device = "/dev/sdb"
    state.storage_disk_provisioned = False
    if "/dev/sdb" not in state.block_devices and "/dev/sdb" not in state.hidden_block_devices:
        state.add_block_device("/dev/sdb", "50G", "disk", present=False)
    if "/dev/sdb" in state.lvm.pvs:
        del state.lvm.pvs["/dev/sdb"]


def init_network_ops(state, extra_ip: str = "10.0.0.20/24") -> None:
    """Network labs: secondary IP added via @network team."""
    state.pending_nic_config = extra_ip
    state.network_nic_provisioned = False


def ops_ready_for_patching(state) -> bool:
    return (
        state.ops_backup_taken
        and state.ops_db_stopped
        and state.ops_app_stopped
    )


def clear_broken_config_sentinel(state, slug: str = "") -> None:
    """Mark the preset-planted broken-configuration sentinel as repaired.

    Sentinel scenarios (see scenario_presets._with_sentinel) plant a file
    ``/opt/fixitlab/academy/<slug>.conf`` containing ``# broken configuration
    for <slug>`` with NO ``FIXED-OK`` marker, so validation.py's fail-closed
    sweep keeps the lab unsolved until the documented remediation runs. The E2E
    harness (scripts/e2e_simulation_fix.apply_simulation_fix) clears it up front,
    but a learner who performs the genuine in-terminal fix (or a unit test that
    drives the engine repair directly) must also clear it — otherwise the sweep
    would fail an engine state that is in fact repaired. This appends the
    ``FIXED-OK`` marker for the given slug's sentinel file so "fixed -> PASS"
    holds regardless of whether the fix came from the harness or the terminal.
    """
    slug = (slug or getattr(state, "scenario_slug", "") or "").lower()
    if not slug:
        return
    path = f"/opt/fixitlab/academy/{slug}.conf"
    content = state.read_file(path)
    if content is None:
        return
    if "FIXED-OK" in content:
        return
    if f"# broken configuration for {slug}" not in content:
        return
    state.write_file(
        path,
        content + "\n# FIXED-OK: corrected per the documented remediation\n",
    )


def apply_team_ops_action(engine: UnifiedSimulationEngine | None, action: str, scenario_slug: str = "") -> None:
    """Mutate simulation state when a Jira team bot confirms an action."""
    if not engine or not getattr(engine, "shell", None):
        return
    state = engine.shell.state
    slug = (scenario_slug or state.scenario_slug or "").lower()

    if action == "backup_taken":
        state.ops_backup_taken = True
    elif action == "database_stopped":
        state.ops_db_stopped = True
        state.ops_db_started = False
        if "mysqld" in state.services:
            state.services["mysqld"].active = "inactive"
            state.services["mysqld"].sub_state = "dead"
        if "postgresql" in state.services:
            state.services["postgresql"].active = "inactive"
            state.services["postgresql"].sub_state = "dead"
    elif action == "application_stopped":
        state.ops_app_stopped = True
        state.ops_app_started = False
        for svc in ("nginx", "httpd", "app"):
            if svc in state.services:
                state.services[svc].active = "inactive"
                state.services[svc].sub_state = "dead"
    elif action == "database_started":
        if state.mount_issue_after_reboot and state.rebooted_after_patch and not state.mount_filesystems_fixed:
            return
        state.ops_db_started = True
        state.ops_db_stopped = False
        if "mysqld" in state.services:
            state.services["mysqld"].active = "active"
            state.services["mysqld"].sub_state = "running"
        if "postgresql" in state.services:
            state.services["postgresql"].active = "active"
            state.services["postgresql"].sub_state = "running"
    elif action == "application_started":
        if state.mount_issue_after_reboot and state.rebooted_after_patch and not state.mount_filesystems_fixed:
            return
        state.ops_app_started = True
        state.ops_app_stopped = False
        state.ops_services_restarted = True
        for svc in ("nginx", "httpd"):
            if svc in state.services:
                state.services[svc].active = "active"
                state.services[svc].sub_state = "running"
    elif action == "storage_disk_added":
        dev = state.pending_storage_device or "/dev/sdb"
        state.storage_disk_provisioned = True
        state.lvm.provision_disk(dev)
        # Bot reply tells the learner to run `lsblk` — promote the pending
        # device out of hidden inventory so it shows immediately (TODO 290/323).
        hidden = getattr(state, "hidden_block_devices", None) or {}
        blocks = getattr(state, "block_devices", None)
        if isinstance(hidden, dict) and dev in hidden:
            disk = hidden.pop(dev)
            disk.present = True
            if isinstance(blocks, dict):
                blocks[dev] = disk
        elif isinstance(blocks, dict) and dev in blocks:
            blocks[dev].present = True
        elif hasattr(state, "add_block_device"):
            state.add_block_device(dev, "50G", "disk", present=True)
    elif action == "network_nic_added":
        state.network_nic_provisioned = True
        cfg = state.pending_nic_config or "10.0.0.20/24"
        state.append_host_ip(cfg.split("/")[0] if "/" in cfg else cfg, "eth0")
        # The NIC hand-off is the documented remediation for the network-nic
        # sentinel labs; clear the planted sentinel so validation passes.
        clear_broken_config_sentinel(state, slug)
    elif action == "security_approved":
        state.ops_security_approved = True
        clear_broken_config_sentinel(state, slug)
    elif action == "mount_issue_reported":
        state.mount_issue_after_reboot = True


def get_simulation_engine_for_session(session_id: str):
    from .shell import get_sim_session

    entry = get_sim_session(str(session_id))
    if not entry:
        return None
    # Live engines are nested under entry["state"]["engine"] (see register_sim_session).
    state = entry.get("state")
    if isinstance(state, dict) and state.get("engine") is not None:
        return state["engine"]
    return entry.get("engine")
