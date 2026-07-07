"""Serialize / restore in-memory simulation engine state across worker restarts."""

from __future__ import annotations

from dataclasses import asdict

from .boot_sequence import BootState
from .rhel_os import RHELOSState, SimProcess, SimService, SimUser
from .unified_sim import UnifiedSimulationEngine


SNAPSHOT_VERSION = 1


def _user_to_dict(u: SimUser) -> dict:
    return {
        "username": u.username,
        "uid": u.uid,
        "gid": u.gid,
        "home": u.home,
        "shell": u.shell,
        "gecos": u.gecos,
        "locked": u.locked,
    }


def _user_from_dict(d: dict) -> SimUser:
    return SimUser(
        d["username"],
        d["uid"],
        d["gid"],
        d["home"],
        d.get("shell", "/bin/bash"),
        d.get("gecos", ""),
        d.get("locked", False),
    )


def _service_to_dict(s: SimService) -> dict:
    return asdict(s)


def _service_from_dict(d: dict) -> SimService:
    return SimService(**d)


def _process_to_dict(p: SimProcess) -> dict:
    return asdict(p)


def _process_from_dict(d: dict) -> SimProcess:
    return SimProcess(**d)


def snapshot_engine(engine: UnifiedSimulationEngine) -> dict:
    st = engine.shell.state
    boot = engine.boot
    lvm = st.lvm
    return {
        "version": SNAPSHOT_VERSION,
        "scenario_slug": engine.scenario_slug,
        "simulation_type": engine.simulation_type,
        "hostname": st.hostname,
        "scenario_slug_state": st.scenario_slug,
        "kernel": st.kernel,
        "current_user": st.current_user,
        "cwd": st.cwd,
        "uid_counter": st.uid_counter,
        "pid_counter": st.pid_counter,
        # Persist the boot epoch so `uptime` reflects real elapsed time since the
        # session started (and survives reboots) instead of resetting to ~1h on
        # every cross-worker restore.
        "boot_time": st.boot_time,
        "vfs": st.vfs,
        "users": {k: _user_to_dict(v) for k, v in st.users.items()},
        "groups": st.groups,
        "services": {k: _service_to_dict(v) for k, v in st.services.items()},
        "processes": [_process_to_dict(p) for p in st.processes],
        "env": st.env,
        "dmesg_extra": list(st.dmesg_extra),
        "gpu_healthy": st.gpu_healthy,
        "initramfs_fixed": st.initramfs_fixed,
        "grub_fixed": st.grub_fixed,
        "mbr_fixed": st.mbr_fixed,
        "kernel_fixed": st.kernel_fixed,
        "patching_done": st.patching_done,
        "precheck_ran": st.precheck_ran,
        "postcheck_ran": st.postcheck_ran,
        "rebooted_after_patch": st.rebooted_after_patch,
        "emergency_mode": st.emergency_mode,
        "fstab_valid": st.fstab_valid,
        "ops_backup_taken": st.ops_backup_taken,
        "ops_db_stopped": st.ops_db_stopped,
        "ops_app_stopped": st.ops_app_stopped,
        "ops_db_started": st.ops_db_started,
        "ops_app_started": st.ops_app_started,
        "ops_services_restarted": st.ops_services_restarted,
        "mount_issue_after_reboot": st.mount_issue_after_reboot,
        "mount_filesystems_fixed": st.mount_filesystems_fixed,
        "pending_storage_device": st.pending_storage_device,
        "storage_disk_provisioned": st.storage_disk_provisioned,
        "pending_nic_config": st.pending_nic_config,
        "network_nic_provisioned": st.network_nic_provisioned,
        # Cross-technology VMware bridge linkage — must round-trip so a rescan or
        # reboot on a different worker still finds the hot-added disk in cache.
        "session_id": getattr(st, "session_id", ""),
        "server_hung": getattr(st, "server_hung", False),
        "block_devices": {
            k: {
                "name": v.name, "size": v.size, "dev_type": v.dev_type,
                "parent": v.parent, "fstype": v.fstype, "uuid": v.uuid,
                "mountpoint": v.mountpoint, "present": v.present,
                "removable": v.removable, "needs_reboot": getattr(v, "needs_reboot", False),
            } for k, v in st.block_devices.items()
        },
        "hidden_block_devices": {
            k: {
                "name": v.name, "size": v.size, "dev_type": v.dev_type,
                "parent": v.parent, "fstype": v.fstype, "uuid": v.uuid,
                "mountpoint": v.mountpoint, "present": v.present,
                "removable": v.removable, "needs_reboot": getattr(v, "needs_reboot", False),
            } for k, v in st.hidden_block_devices.items()
        },
        # Fix-flags read by the validator — must survive a Redis round-trip or
        # cross-worker validation reads them as unfixed (e.g. ldconfig in CI).
        "ldconfig_updated": getattr(st, "ldconfig_updated", False),
        "myapp_working": getattr(st, "myapp_working", False),
        "terraform_fixed": getattr(st, "terraform_fixed", False),
        "windows_fixed": getattr(st, "windows_fixed", False),
        "network_ifs": st.network_ifs,
        # Git repos (branches/commits/staging) — must survive cross-worker
        # restores or `git log`/validation sees an empty repo mid-lab.
        "git": st.git.to_dict() if getattr(st, "git", None) else None,
        "lvm": {
            "pvs": {k: asdict(v) for k, v in lvm.pvs.items()},
            "vgs": {k: asdict(v) for k, v in lvm.vgs.items()},
            "lvs": {k: asdict(v) for k, v in lvm.lvs.items()},
        },
        "firewall": {
            "runtime": st.firewall.runtime,
            "permanent": st.firewall.permanent,
        },
        "boot": asdict(boot) if boot else None,
        "docker": engine.docker.to_dict() if getattr(engine, "docker", None) else None,
        "engine_flags": {
            "ssh_key_fixed": getattr(engine, "_ssh_key_fixed", False),
            "power_state": getattr(engine, "_power_state", "on"),
            "container_running": getattr(engine, "_container_running", False),
            "patch_hint_shown": getattr(engine, "_patch_hint_shown", False),
            "grub_countdown_token": getattr(engine, "_grub_countdown_token", 0),
        },
    }


def restore_engine(data: dict) -> UnifiedSimulationEngine | None:
    if not data or data.get("version") != SNAPSHOT_VERSION:
        return None
    slug = data.get("scenario_slug", "")
    sim_type = data.get("simulation_type", "generic")
    engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
    st = engine.shell.state

    st.hostname = data.get("hostname", st.hostname)
    st.scenario_slug = data.get("scenario_slug_state", slug)
    st.kernel = data.get("kernel", st.kernel)
    st.current_user = data.get("current_user", "root")
    st.cwd = data.get("cwd", "/root")
    st.uid_counter = data.get("uid_counter", 1000)
    st.pid_counter = data.get("pid_counter", 900)
    if data.get("boot_time") is not None:
        st.boot_time = data["boot_time"]
    st.vfs = data.get("vfs", st.vfs)
    st.users = {k: _user_from_dict(v) for k, v in data.get("users", {}).items()}
    st.groups = data.get("groups", st.groups)
    st.services = {k: _service_from_dict(v) for k, v in data.get("services", {}).items()}
    st.processes = [_process_from_dict(p) for p in data.get("processes", [])]
    st.env = data.get("env", st.env)
    st.dmesg_extra = list(data.get("dmesg_extra", []))
    st.gpu_healthy = data.get("gpu_healthy", True)
    st.ldconfig_updated = data.get("ldconfig_updated", False)
    st.myapp_working = data.get("myapp_working", False)
    st.terraform_fixed = data.get("terraform_fixed", False)
    st.windows_fixed = data.get("windows_fixed", False)
    st.initramfs_fixed = data.get("initramfs_fixed", False)
    st.grub_fixed = data.get("grub_fixed", False)
    st.mbr_fixed = data.get("mbr_fixed", False)
    st.kernel_fixed = data.get("kernel_fixed", False)
    st.patching_done = data.get("patching_done", False)
    st.precheck_ran = data.get("precheck_ran", False)
    st.postcheck_ran = data.get("postcheck_ran", False)
    st.rebooted_after_patch = data.get("rebooted_after_patch", False)
    st.emergency_mode = data.get("emergency_mode", False)
    st.fstab_valid = data.get("fstab_valid", True)
    st.ops_backup_taken = data.get("ops_backup_taken", False)
    st.ops_db_stopped = data.get("ops_db_stopped", False)
    st.ops_app_stopped = data.get("ops_app_stopped", False)
    st.ops_db_started = data.get("ops_db_started", True)
    st.ops_app_started = data.get("ops_app_started", True)
    st.ops_services_restarted = data.get("ops_services_restarted", False)
    st.mount_issue_after_reboot = data.get("mount_issue_after_reboot", False)
    st.mount_filesystems_fixed = data.get("mount_filesystems_fixed", False)
    st.pending_storage_device = data.get("pending_storage_device", "/dev/sdb")
    st.storage_disk_provisioned = data.get("storage_disk_provisioned", True)
    st.pending_nic_config = data.get("pending_nic_config", "10.0.0.20/24")
    st.network_nic_provisioned = data.get("network_nic_provisioned", True)
    st.network_ifs = data.get("network_ifs", st.network_ifs)
    git_data = data.get("git")
    if git_data:
        from .git_state import GitSimState
        st.git = GitSimState.from_dict(git_data)
    st.session_id = data.get("session_id", "")
    st.server_hung = data.get("server_hung", False)
    # Restore the block-device model (the preset already seeded a default set in
    # __init__; replace it with the snapshot so revealed/hidden disks persist).
    from .rhel_os import SimBlockDevice
    bd = data.get("block_devices")
    if bd is not None:
        st.block_devices = {k: SimBlockDevice(**v) for k, v in bd.items()}
    hbd = data.get("hidden_block_devices")
    if hbd is not None:
        st.hidden_block_devices = {k: SimBlockDevice(**v) for k, v in hbd.items()}
    st._scenario_preset_applied = True

    lvm_data = data.get("lvm", {})
    from .lvm_state import LVMState, SimLV, SimPV, SimVG
    lvm = LVMState()
    lvm.pvs = {k: SimPV(**v) for k, v in lvm_data.get("pvs", {}).items()}
    lvm.vgs = {k: SimVG(**v) for k, v in lvm_data.get("vgs", {}).items()}
    lvm.lvs = {k: SimLV(**v) for k, v in lvm_data.get("lvs", {}).items()}
    st.lvm = lvm

    fw = data.get("firewall", {})
    if fw:
        st.firewall.runtime = fw.get("runtime", st.firewall.runtime)
        st.firewall.permanent = fw.get("permanent", st.firewall.permanent)

    boot_data = data.get("boot")
    if boot_data and engine.boot:
        for key, val in boot_data.items():
            if hasattr(engine.boot, key):
                setattr(engine.boot, key, val)

    docker_data = data.get("docker")
    if docker_data:
        from .docker_state import DockerState
        engine.docker = DockerState.from_dict(docker_data)

    flags = data.get("engine_flags", {})
    engine._ssh_key_fixed = flags.get("ssh_key_fixed", False)
    engine._power_state = flags.get("power_state", "on")
    engine._container_running = flags.get("container_running", False)
    engine._patch_hint_shown = flags.get("patch_hint_shown", False)
    engine._grub_countdown_token = flags.get("grub_countdown_token", 0)

    engine.shell._engine = engine
    return engine


def persist_session_snapshot(session_id: str) -> None:
    """Save engine state to LabSession.simulation_snapshot (best-effort)."""
    from apps.labs.models import LabSession
    from .shell import get_sim_session

    entry = get_sim_session(str(session_id))
    if not entry:
        return
    engine = entry.get("state", {}).get("engine")
    if not isinstance(engine, UnifiedSimulationEngine):
        return
    try:
        snap = snapshot_engine(engine)
        LabSession.objects.filter(id=session_id).update(simulation_snapshot=snap)
    except Exception:
        pass
