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
    elif action == "network_nic_added":
        state.network_nic_provisioned = True
        cfg = state.pending_nic_config or "10.0.0.20/24"
        state.append_host_ip(cfg.split("/")[0] if "/" in cfg else cfg, "eth0")
    elif action == "mount_issue_reported":
        state.mount_issue_after_reboot = True


def get_simulation_engine_for_session(session_id: str):
    from .shell import get_sim_session

    entry = get_sim_session(str(session_id))
    if not entry:
        return None
    return entry.get("engine")
