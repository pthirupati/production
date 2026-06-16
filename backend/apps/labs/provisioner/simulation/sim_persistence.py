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
        "network_ifs": st.network_ifs,
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
    st.vfs = data.get("vfs", st.vfs)
    st.users = {k: _user_from_dict(v) for k, v in data.get("users", {}).items()}
    st.groups = data.get("groups", st.groups)
    st.services = {k: _service_from_dict(v) for k, v in data.get("services", {}).items()}
    st.processes = [_process_from_dict(p) for p in data.get("processes", [])]
    st.env = data.get("env", st.env)
    st.dmesg_extra = list(data.get("dmesg_extra", []))
    st.gpu_healthy = data.get("gpu_healthy", True)
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
    st.network_ifs = data.get("network_ifs", st.network_ifs)
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
