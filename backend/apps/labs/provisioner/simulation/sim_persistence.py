"""Serialize / restore in-memory simulation engine state across worker restarts."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict

from .boot_sequence import BootState
from .rhel_os import RHELOSState, SimGPU, SimProcess, SimService, SimUser
from .unified_sim import UnifiedSimulationEngine


logger = logging.getLogger(__name__)
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
        # Monotonic wall clock for cross-worker cache authority (audit Z5-1).
        "mutated_at": time.time(),
        "scenario_slug": engine.scenario_slug,
        "simulation_type": engine.simulation_type,
        "hostname": st.hostname,
        "scenario_slug_state": st.scenario_slug,
        "kernel": st.kernel,
        # Seeded hardware profile (unified-server VMware labs); nproc/lscpu/free
        # read these live fields, so they must survive a worker restart.
        "cpu_count": getattr(st, "cpu_count", 4),
        "mem_mb": getattr(st, "mem_mb", 16384),
        "current_user": st.current_user,
        "cwd": st.cwd,
        "uid_counter": st.uid_counter,
        "pid_counter": st.pid_counter,
        # Persist boot_time so `uptime` survives worker restarts / server reboots.
        # Note: an in-sim `reboot` intentionally resets boot_time to now (uptime → ~0).
        "boot_time": st.boot_time,
        "vfs": st.vfs,
        "users": {k: _user_to_dict(v) for k, v in st.users.items()},
        "groups": st.groups,
        "services": {k: _service_to_dict(v) for k, v in st.services.items()},
        "processes": [_process_to_dict(p) for p in st.processes],
        "env": st.env,
        "dmesg_extra": list(st.dmesg_extra),
        "gpu_healthy": st.gpu_healthy,
        "gpus": [
            {
                "index": g.index,
                "name": g.name,
                "uuid": g.uuid,
                "sku": getattr(g, "sku", ""),
                "pci_bus_id": getattr(g, "pci_bus_id", ""),
                "healthy": g.healthy,
                "memory_total_mib": g.memory_total_mib,
                "memory_used_mib": g.memory_used_mib,
                "temp_c": getattr(g, "temp_c", 32),
                "mem_temp_c": getattr(g, "mem_temp_c", 38),
                "power_w": getattr(g, "power_w", 70.0),
                "power_cap_w": getattr(g, "power_cap_w", 300),
                "util_gpu": getattr(g, "util_gpu", 0),
                "util_mem": getattr(g, "util_mem", 0),
                "sm_clock": getattr(g, "sm_clock", 1410),
                "mem_clock": getattr(g, "mem_clock", 1593),
                "graphics_clock": getattr(g, "graphics_clock", 1410),
                "persistence_mode": getattr(g, "persistence_mode", True),
                "ecc_mode": getattr(g, "ecc_mode", "Enabled"),
                "ecc_volatile_corrected": getattr(g, "ecc_volatile_corrected", 0),
                "ecc_volatile_uncorrected": getattr(g, "ecc_volatile_uncorrected", 0),
                "ecc_aggregate_corrected": getattr(g, "ecc_aggregate_corrected", 0),
                "ecc_aggregate_uncorrected": getattr(g, "ecc_aggregate_uncorrected", 0),
                "retired_pages_sbe": getattr(g, "retired_pages_sbe", 0),
                "retired_pages_dbe": getattr(g, "retired_pages_dbe", 0),
                "retired_pages_pending": getattr(g, "retired_pages_pending", False),
                "remap_pending": getattr(g, "remap_pending", False),
                "remap_failure": getattr(g, "remap_failure", False),
                "throttle_reasons": list(getattr(g, "throttle_reasons", None) or []),
                "xid_events": list(getattr(g, "xid_events", None) or []),
                "mig_mode": getattr(g, "mig_mode", False),
                "mig_instances": list(getattr(g, "mig_instances", None) or []),
                "nvlink_links": list(getattr(g, "nvlink_links", None) or []),
                "diag_pcie_fail": getattr(g, "diag_pcie_fail", False),
                "diag_memory_fail": getattr(g, "diag_memory_fail", False),
                "diag_bandwidth_fail": getattr(g, "diag_bandwidth_fail", False),
                "diag_stress_fail": getattr(g, "diag_stress_fail", False),
                "diag_power_fail": getattr(g, "diag_power_fail", False),
                "oom": getattr(g, "oom", False),
            }
            for g in (getattr(st, "gpus", None) or [])
        ],
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
        # Installed packages + their binaries — must round-trip or a cross-worker
        # restore mid-lab loses `which <tool>`/`rpm -q <pkg>`/unit knowledge for
        # anything the learner installed (services already round-trip below).
        "installed_packages": dict(getattr(st, "installed_packages", {}) or {}),
        "installed_binaries": dict(getattr(st, "installed_binaries", {}) or {}),
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
        # Networking / DevOps / k8s world-model — without these, persist+restore
        # (and cache-authority refresh after E2E fix) re-seeds Idle BGP / failed
        # pipelines / Pending pods and validate PASS regresses.
        "networking": (
            engine.networking.to_dict()
            if getattr(engine, "networking", None) is not None
            else None
        ),
        "devops": _devops_to_dict(getattr(engine, "devops", None)),
        "cluster": _cluster_to_dict(getattr(engine, "cluster", None)),
        "engine_flags": {
            "ssh_key_fixed": getattr(engine, "_ssh_key_fixed", False),
            "ansible_playbook_ok": getattr(engine, "_ansible_playbook_ok", False),
            "power_state": getattr(engine, "_power_state", "on"),
            "container_running": getattr(engine, "_container_running", False),
            "patch_hint_shown": getattr(engine, "_patch_hint_shown", False),
            "grub_countdown_token": getattr(engine, "_grub_countdown_token", 0),
        },
    }


def _devops_to_dict(devops) -> dict | None:
    if devops is None:
        return None
    return {
        "scenario_slug": getattr(devops, "scenario_slug", ""),
        "pipeline_status": getattr(devops, "pipeline_status", "success"),
        "helm_release_status": getattr(devops, "helm_release_status", "deployed"),
        "helm_revision": getattr(devops, "helm_revision", 3),
        "kubeconfig_valid": getattr(devops, "kubeconfig_valid", True),
        "image_tag": getattr(devops, "image_tag", "v1.2.0"),
    }


def _cluster_to_dict(cluster) -> dict | None:
    if cluster is None:
        return None
    return {
        "session_id": getattr(cluster, "session_id", ""),
        "pods": [
            {
                "name": p.name,
                "status": p.status,
                "namespace": getattr(p, "namespace", "default"),
                "node": getattr(p, "node", ""),
            }
            for p in (getattr(cluster, "pods", None) or [])
        ],
        "nodes": [
            {
                "name": n.name,
                "status": n.status,
                "schedulable": getattr(n, "schedulable", True),
                "vm_hung": getattr(n, "vm_hung", False),
                "gpu_allocatable": getattr(n, "gpu_allocatable", 0),
            }
            for n in (getattr(cluster, "nodes", None) or [])
        ],
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
    st.cpu_count = data.get("cpu_count", getattr(st, "cpu_count", 4))
    st.mem_mb = data.get("mem_mb", getattr(st, "mem_mb", 16384))
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
    # Overlay persisted install state onto the constructor-seeded base set so a
    # cross-worker restore preserves both base tools and anything installed mid-lab.
    if isinstance(data.get("installed_packages"), dict) and hasattr(st, "installed_packages"):
        merged = dict(st.installed_packages); merged.update(data["installed_packages"]); st.installed_packages = merged
    if isinstance(data.get("installed_binaries"), dict) and hasattr(st, "installed_binaries"):
        merged = dict(st.installed_binaries); merged.update(data["installed_binaries"]); st.installed_binaries = merged
    st.env = data.get("env", st.env)
    st.dmesg_extra = list(data.get("dmesg_extra", []))
    # Prefer full per-GPU inventory when present; fall back to the aggregate flag.
    raw_gpus = data.get("gpus")
    if isinstance(raw_gpus, list) and raw_gpus:
        restored = []
        for row in raw_gpus:
            if not isinstance(row, dict):
                continue
            restored.append(SimGPU(
                index=int(row.get("index", 0)),
                name=row.get("name", "NVIDIA L4"),
                uuid=row.get("uuid", "GPU-00000000-0000-0000-0000-000000000001"),
                sku=row.get("sku", "l4"),
                pci_bus_id=row.get("pci_bus_id", "00000000:01:00.0"),
                healthy=bool(row.get("healthy", True)),
                memory_total_mib=int(row.get("memory_total_mib", 23034)),
                memory_used_mib=int(row.get("memory_used_mib", 0)),
                temp_c=int(row.get("temp_c", 32)),
                mem_temp_c=int(row.get("mem_temp_c", 38)),
                power_w=float(row.get("power_w", 70.0)),
                power_cap_w=int(row.get("power_cap_w", 300)),
                util_gpu=int(row.get("util_gpu", 0)),
                util_mem=int(row.get("util_mem", 0)),
                sm_clock=int(row.get("sm_clock", 1410)),
                mem_clock=int(row.get("mem_clock", 1593)),
                graphics_clock=int(row.get("graphics_clock", 1410)),
                persistence_mode=bool(row.get("persistence_mode", True)),
                ecc_mode=row.get("ecc_mode", "Enabled"),
                ecc_volatile_corrected=int(row.get("ecc_volatile_corrected", 0)),
                ecc_volatile_uncorrected=int(row.get("ecc_volatile_uncorrected", 0)),
                ecc_aggregate_corrected=int(row.get("ecc_aggregate_corrected", 0)),
                ecc_aggregate_uncorrected=int(row.get("ecc_aggregate_uncorrected", 0)),
                retired_pages_sbe=int(row.get("retired_pages_sbe", 0)),
                retired_pages_dbe=int(row.get("retired_pages_dbe", 0)),
                retired_pages_pending=bool(row.get("retired_pages_pending", False)),
                remap_pending=bool(row.get("remap_pending", False)),
                remap_failure=bool(row.get("remap_failure", False)),
                throttle_reasons=list(row.get("throttle_reasons") or []),
                xid_events=list(row.get("xid_events") or []),
                mig_mode=bool(row.get("mig_mode", False)),
                mig_instances=list(row.get("mig_instances") or []),
                nvlink_links=list(row.get("nvlink_links") or []),
                diag_pcie_fail=bool(row.get("diag_pcie_fail", False)),
                diag_memory_fail=bool(row.get("diag_memory_fail", False)),
                diag_bandwidth_fail=bool(row.get("diag_bandwidth_fail", False)),
                diag_stress_fail=bool(row.get("diag_stress_fail", False)),
                diag_power_fail=bool(row.get("diag_power_fail", False)),
                oom=bool(row.get("oom", False)),
            ))
        if restored:
            st.gpus = restored
    else:
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

    net_data = data.get("networking")
    if isinstance(net_data, dict):
        from .networking_state import NetworkingState
        engine.networking = NetworkingState.from_dict(net_data)

    devops_data = data.get("devops")
    if isinstance(devops_data, dict):
        from .devops_state import DevOpsState
        devops = DevOpsState(devops_data.get("scenario_slug") or slug)
        devops.pipeline_status = devops_data.get("pipeline_status", devops.pipeline_status)
        devops.helm_release_status = devops_data.get(
            "helm_release_status", devops.helm_release_status
        )
        devops.helm_revision = devops_data.get("helm_revision", devops.helm_revision)
        devops.kubeconfig_valid = devops_data.get("kubeconfig_valid", devops.kubeconfig_valid)
        devops.image_tag = devops_data.get("image_tag", devops.image_tag)
        engine.devops = devops

    cluster_data = data.get("cluster")
    if isinstance(cluster_data, dict) and getattr(engine, "cluster", None) is not None:
        _apply_cluster_overlay(engine.cluster, cluster_data)

    flags = data.get("engine_flags", {})
    engine._ssh_key_fixed = flags.get("ssh_key_fixed", False)
    engine._ansible_playbook_ok = flags.get("ansible_playbook_ok", False)
    engine._power_state = flags.get("power_state", "on")
    engine._container_running = flags.get("container_running", False)
    engine._patch_hint_shown = flags.get("patch_hint_shown", False)
    engine._grub_countdown_token = flags.get("grub_countdown_token", 0)

    engine.shell._engine = engine
    return engine


def _apply_cluster_overlay(cluster, data: dict) -> None:
    """Re-apply pod/node health from a snapshot onto a freshly seeded cluster."""
    if data.get("session_id"):
        cluster.session_id = data["session_id"]
    by_pod = {p.name: p for p in (cluster.pods or [])}
    for row in data.get("pods") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        pod = by_pod.get(name) if name else None
        if pod is None:
            continue
        if row.get("status"):
            pod.status = row["status"]
        if row.get("node") is not None:
            pod.node = row["node"]
    by_node = {n.name: n for n in (cluster.nodes or [])}
    for row in data.get("nodes") or []:
        if not isinstance(row, dict):
            continue
        name = row.get("name")
        node = by_node.get(name) if name else None
        if node is None:
            continue
        if row.get("status"):
            node.status = row["status"]
        if "schedulable" in row:
            node.schedulable = bool(row["schedulable"])
        if "vm_hung" in row:
            node.vm_hung = bool(row["vm_hung"])
        if "gpu_allocatable" in row:
            node.gpu_allocatable = int(row["gpu_allocatable"] or 0)


def persist_session_snapshot(session_id: str) -> None:
    """Save engine state to LabSession.simulation_snapshot (best-effort)."""
    from apps.labs.models import LabSession
    from .shell import get_local_sim_engine, mark_sim_engine_mutated

    # Never go through get_sim_session here — cache-authority refresh can replace
    # a just-repaired live engine with an older incomplete snapshot first.
    engine = get_local_sim_engine(str(session_id))
    if not isinstance(engine, UnifiedSimulationEngine):
        return
    try:
        snap = snapshot_engine(engine)
        LabSession.objects.filter(id=session_id).update(simulation_snapshot=snap)
        # Shared-cache mirror (audit Z5-1 partial). Live streams stay process-local
        # in `_SIM_SESSIONS`; this blob lets another worker rehydrate without waiting
        # on Postgres JSONB when the local dict misses. Same TTL shape as vmware_sim.
        cache_put_engine_snapshot(str(session_id), snap)
        # Keep local authority timestamp in sync so the next get_sim_session does
        # not treat this write as a *foreign* newer snapshot and replace the live
        # engine with a restore that drops un-snapshotted fields.
        mark_sim_engine_mutated(str(session_id))
    except Exception:
        pass


# ── Cross-process engine blob (audit Z5-1 partial Redis port) ─────────────────
#
# Full engines cannot live only in Redis while a terminal WebSocket is open —
# stream handles are process-local. What *can* be shared is the serialised
# snapshot the DB already stores. Putting it in cache (Redis in prod, LocMem in
# tests) gives a worker that never saw the session a faster hydrate path than
# Postgres, matching the vmware_sim SESSION_TTL=7200 pattern for *state*.
#
# This does NOT by itself eliminate multi-worker hot copies; `_SIM_MAX_SESSIONS`
# + idle TTL still bound process memory. It closes the "only the DB has state"
# half of the cross-process gap.

SIM_ENGINE_CACHE_TTL = 7200  # matches apps/vmware_sim/* SESSION_TTL


def _engine_cache_key(session_id: str) -> str:
    return f"fixitlab:sim_engine:{session_id}"


def cache_put_engine_snapshot(session_id: str, snap: dict | None = None, engine=None) -> None:
    """Best-effort write of a versioned engine snapshot to the shared cache."""
    try:
        from django.core.cache import cache

        if snap is None:
            if not isinstance(engine, UnifiedSimulationEngine):
                return
            snap = snapshot_engine(engine)
        if not snap or snap.get("version") != SNAPSHOT_VERSION:
            return
        cache.set(_engine_cache_key(str(session_id)), snap, SIM_ENGINE_CACHE_TTL)
    except Exception:
        logger.debug("sim engine cache put failed for %s", session_id, exc_info=True)


def cache_get_engine(session_id: str):
    """Restore an engine from the shared cache, or None on miss/corruption."""
    snap = cache_get_snapshot(session_id)
    if snap is None:
        return None
    try:
        return restore_engine(snap)
    except Exception:
        return None


def cache_get_snapshot(session_id: str) -> dict | None:
    """Raw versioned snapshot from shared cache (includes ``mutated_at``)."""
    try:
        from django.core.cache import cache

        snap = cache.get(_engine_cache_key(str(session_id)))
        if not snap or not isinstance(snap, dict):
            return None
        if snap.get("version") != SNAPSHOT_VERSION:
            return None
        return snap
    except Exception:
        return None


def cache_drop_engine(session_id: str) -> None:
    try:
        from django.core.cache import cache

        cache.delete(_engine_cache_key(str(session_id)))
    except Exception:
        pass


def cache_touch_engine(session_id: str, engine=None) -> None:
    """Write-through helper: keep Redis/cache hot on every persist (Z5-1).

    Call sites that mutate the live engine should prefer this over relying solely
    on the debounced DB JSONB snapshot. Live WebSocket streams remain process-local.
    """
    cache_put_engine_snapshot(str(session_id), engine=engine)
    try:
        from .shell import mark_sim_engine_mutated

        mark_sim_engine_mutated(str(session_id))
    except Exception:
        pass
