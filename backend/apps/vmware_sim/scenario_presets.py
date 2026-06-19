"""VMware lab scenario presets — broken inventory + validation rules per slug."""

from __future__ import annotations

import random
import time
from typing import Any


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(message: str, severity: str = "info", entity: str = "") -> dict:
    return {"time": _now_iso(), "message": message, "severity": severity, "entity": entity, "user": "root"}


def _task(name: str, target: str) -> dict:
    t = _now_iso()
    return {
        "id": f"task-{int(time.time())}-{random.randint(1000, 9999)}",
        "name": name, "target": target, "initiator": "root",
        "queued": t, "started": t, "result": "Completed successfully",
        "completed": t, "status": "success",
    }


def _find_vm(state: dict, vm_name: str | None = None) -> dict | None:
    if not vm_name:
        return None
    return next((v for v in state.get("vms", []) if v.get("name") == vm_name), None)


def _web_vm(state: dict) -> dict | None:
    return _find_vm(state, vm_name="web-prod-01")


def _set_validation(state: dict, **rules: Any) -> None:
    state["validation"] = rules


def apply_vmware_scenario_preset(state: dict, scenario_slug: str) -> None:
    slug = (scenario_slug or "").lower()
    events = state["events"]
    tasks = state["recent_tasks"]
    web = _web_vm(state)

    def alarm(aid: str, name: str, entity: str, severity: str = "critical") -> None:
        state.setdefault("alarms", []).append({
            "id": aid, "name": name, "entity": entity,
            "severity": severity, "status": "active", "time": events[-1]["time"] if events else "",
        })

    # ── Power / guest state ─────────────────────────────────────────────
    if "guest-powered-off" in slug or slug.endswith("guest-powered-off"):
        if web:
            web["power"] = "poweredOff"
            web["tools"] = "notRunning"
            web["cpu_pct"] = 0
            web["mem_pct"] = 0
        events.append(_event("VM web-prod-01 powered off unexpectedly", "warning", "web-prod-01"))
        alarm("alm-vm-off", "VM powered off", "web-prod-01")
        _set_validation(state, target_vm="web-prod-01", require_power="poweredOn")

    elif "guest-hung" in slug or "hung-guest" in slug or "guest-unresponsive" in slug:
        if web:
            web["power"] = "poweredOn"
            web["guest_hung"] = True
            web["tools"] = "notRunning"
            web["cpu_pct"] = 98
        state["linux_ssh_ok"] = False
        state["jira_incident_updated"] = False
        state["customer_reboot_approved"] = False
        events.append(_event("Guest heartbeat lost on web-prod-01 — VM may be hung", "critical", "web-prod-01"))
        alarm("alm-hung", "Guest heartbeat lost", "web-prod-01")
        _set_validation(
            state,
            target_vm="web-prod-01",
            require_guest_responsive=True,
            require_ssh_ok=True,
            require_jira_updated=True,
            require_customer_approval=True,
        )

    elif "question-pending" in slug:
        if web:
            web["question_pending"] = True
        events.append(_event("VM web-prod-01 has a pending question", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", require_question_cleared=True)

    # ── Host connectivity ───────────────────────────────────────────────
    elif "host-disconnected" in slug or "esxi-host-disconnected" in slug:
        h = state["hosts"][0]
        h["status"] = "disconnected"
        h["connection_state"] = "disconnected"
        for vm in state["vms"]:
            if vm["host_id"] == h["id"]:
                vm["power"] = "poweredOff"
                vm["tools"] = "notRunning"
        events.append(_event(f"Host {h['name']} disconnected from vCenter", "critical", h["name"]))
        alarm("alm-host-dc", "Host disconnected", h["name"])
        _set_validation(state, require_host_connected=h["name"])

    elif "management-network" in slug:
        h = state["hosts"][0]
        h["management_network"] = "down"
        events.append(_event(f"Management network lost on {h['name']}", "critical", h["name"]))
        _set_validation(state, require_host_connected=h["name"])

    elif "ntp-out-of-sync" in slug or "ntp" in slug:
        for h in state["hosts"]:
            h["ntp_synced"] = False
        events.append(_event("NTP sync failed on ESXi hosts", "warning", "Cluster-01"))
        _set_validation(state, require_ntp_synced=True)

    elif "coredump-full" in slug:
        h = state["hosts"][0]
        h["coredump_full"] = True
        events.append(_event(f"Core dump partition full on {h['name']}", "warning", h["name"]))
        _set_validation(state, require_coredump_cleared=True)

    # ── Cluster: HA / DRS ───────────────────────────────────────────────
    elif "ha-failure" in slug or slug.endswith("ha-failure"):
        state["cluster_ha"] = False
        state["hosts"][1]["status"] = "notResponding"
        state["hosts"][1]["connection_state"] = "notResponding"
        if web:
            web["power"] = "poweredOff"
        events.append(_event("HA protection disabled on Cluster-01", "critical", "Cluster-01"))
        alarm("alm-ha", "vSphere HA protection disabled", "Cluster-01")
        _set_validation(state, cluster_ha=True, target_vm="web-prod-01", require_power="poweredOn")

    elif "ha-admission" in slug or "admission-control" in slug:
        state["cluster_ha"] = True
        state["admission_control_failed"] = True
        events.append(_event("HA admission control preventing VM power-on", "critical", "Cluster-01"))
        _set_validation(state, admission_control_ok=True)

    elif "drs-disabled" in slug:
        state["cluster_drs"] = False
        state["drs_balanced"] = False
        state["hosts"][0]["cpu_pct"] = 92
        state["hosts"][1]["cpu_pct"] = 28
        events.append(_event("DRS disabled on Cluster-01 — hosts imbalanced", "warning", "Cluster-01"))
        _set_validation(state, cluster_drs=True, drs_balanced=True)

    elif "enable-ha" in slug or "ha-drs" in slug:
        state["cluster_ha"] = False
        state["cluster_drs"] = False
        state["drs_balanced"] = False
        events.append(_event("Cluster HA and DRS disabled", "critical", "Cluster-01"))
        _set_validation(state, cluster_ha=True, cluster_drs=True, drs_balanced=True)

    # ── Storage ─────────────────────────────────────────────────────────
    elif "datastore" in slug and ("full" in slug or "almost" in slug):
        state["datastores"][0]["free_gb"] = 2
        events.append(_event("Datastore datastore-ssd-01 at 99.9% capacity", "critical", "datastore-ssd-01"))
        alarm("alm-ds-full", "Datastore usage exceeded threshold", "datastore-ssd-01")
        _set_validation(state, datastore_min_free_gb=100, datastore="datastore-ssd-01")

    elif "vsan-disk" in slug or "vsan" in slug:
        state["cluster_vsan"] = True
        state["vsan_disk_unclaimed"] = True
        vsan = state.setdefault("vsan", {})
        vsan["enabled"] = True
        vsan["health"] = "warning"
        vsan["cluster_status"] = "degraded"
        vsan["unclaimed_disks"] = [
            {"id": "naa.6000C29b1", "host": "esxi-02.fixitlab.local", "size_tb": 1.8, "state": "eligible"},
        ]
        vsan["components_healthy"] = False
        events.append(_event("vSAN disk claim failed on esxi-02", "critical", "esxi-02.fixitlab.local"))
        _set_validation(state, vsan_disks_claimed=True)

    elif "guest-disk" in slug or "disk-missing" in slug or "disk-not-visible" in slug:
        if web:
            web["power"] = "poweredOn"
            web["tools"] = "ok"
            web["guest_disk_hidden"] = True
            web["guest_disk_visible"] = False
            web["guest_disk_mounted"] = False
        events.append(_event("New disk not visible in guest OS on web-prod-01", "warning", "web-prod-01"))
        alarm("alm-disk", "Guest disk not mounted", "web-prod-01", "warning")
        _set_validation(state, target_vm="web-prod-01", guest_disk_mounted=True)

    elif "boot-failure" in slug or "initramfs" in slug or "guest-boot" in slug:
        if web:
            web["power"] = "poweredOn"
            web["boot_failure"] = True
            web["guest_hung"] = False
        events.append(_event("Guest OS boot failure on web-prod-01 — drops to initramfs", "critical", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", boot_resolved=True)

    elif "kernel-module" in slug or "module-missing" in slug:
        if web:
            web["power"] = "poweredOn"
            web["kernel_module_missing"] = True
        events.append(_event("Required kernel module not loaded on web-prod-01", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", kernel_module_loaded=True)

    elif "patch-pending" in slug or "esxi-patch" in slug or "host-patch" in slug:
        h = state["hosts"][0]
        h["pending_patches"] = 3
        h["patch_reboot_required"] = True
        state.setdefault("updates", {})["hosts"] = {h["name"]: {"pending": 3}}
        events.append(_event(f"ESXi patches pending on {h['name']}", "warning", h["name"]))
        _set_validation(state, host_patches_installed=True)

    elif "permission" in slug or "rbac" in slug:
        state["permission_missing"] = True
        events.append(_event("Required vCenter permission missing for lab operator", "warning", "DC-Prod"))
        _set_validation(state, permission_assigned=True)

    elif "ovf-deploy" in slug or "content-library" in slug:
        events.append(_event("Deploy VM from content library OVF required", "info", "FixitLab Library"))
        _set_validation(state, ovf_deployed=True)

    elif "storage-vmotion" in slug or "vmotion-stuck" in slug:
        state["storage_vmotion_stuck"] = True
        events.append(_event("Storage vMotion stuck at 47%", "warning", "web-prod-01"))
        _set_validation(state, storage_vmotion_complete=True)

    elif "add-disk" in slug or "disk-expand" in slug or "extend-disk" in slug:
        if web:
            web["disk_gb"] = 40
            web["disk_target_gb"] = 120
        events.append(_event("web-prod-01 disk capacity below requirement", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", min_disk_gb=100)

    # ── Network ─────────────────────────────────────────────────────────
    elif "network-disconnected" in slug or "vm-network" in slug:
        if web:
            web["network_disconnected"] = True
            web["net_mbps"] = 0
        events.append(_event("Network adapter disconnected on web-prod-01", "critical", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", require_network_connected=True)

    elif "distributed-switch" in slug or "mtu" in slug:
        state["dv_switch_mtu_mismatch"] = True
        events.append(_event("Distributed switch MTU mismatch detected", "warning", "dvSwitch-Prod"))
        _set_validation(state, dv_switch_mtu_fixed=True)

    elif "portgroup" in slug or "create-network" in slug:
        state["portgroup_missing"] = "Prod-VLAN-200"
        events.append(_event("Required port group Prod-VLAN-200 missing", "warning", "dvSwitch-Prod"))
        _set_validation(state, portgroup_created="Prod-VLAN-200")

    # ── VM ops ──────────────────────────────────────────────────────────
    elif "tools-outdated" in slug:
        if web:
            web["tools"] = "old"
        events.append(_event("VMware Tools outdated on web-prod-01", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", require_tools="ok")

    elif "cpu-ready" in slug or "cpu-ready-high" in slug:
        if web:
            web["cpu_ready_pct"] = 45
        events.append(_event("CPU ready time high on web-prod-01", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", max_cpu_ready_pct=10)

    elif "snapshot-chain" in slug or "snapshot-delete" in slug:
        if web:
            web["snapshots"] = [
                {"id": "s1", "name": "before-patch", "description": "", "created": "2026-01-01T00:00:00Z"},
                {"id": "s2", "name": "before-patch-2", "description": "", "created": "2026-02-01T00:00:00Z"},
            ]
        events.append(_event("Long snapshot chain on web-prod-01", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", max_snapshots=1)

    elif "vmotion-failed" in slug:
        state["vmotion_failed"] = True
        events.append(_event("vMotion failed for api-prod-01", "critical", "api-prod-01"))
        _set_validation(state, vmotion_resolved=True)

    elif "clone-from-template" in slug or "template-convert" in slug:
        state["template_convert_failed"] = True
        events.append(_event("Template conversion failed", "warning", "web-template"))
        _set_validation(state, template_converted=True)

    # ── vCenter ─────────────────────────────────────────────────────────
    elif "vcenter-certificate" in slug or "certificate-expired" in slug:
        state["vcenter_cert_expired"] = True
        events.append(_event("vCenter certificate expired", "critical", "vCenter"))
        _set_validation(state, vcenter_cert_renewed=True)

    elif "vcenter-db-full" in slug or "db-full" in slug:
        state["vcenter_db_full"] = True
        events.append(_event("vCenter database partition nearly full", "critical", "vCenter"))
        _set_validation(state, vcenter_db_expanded=True)

    elif "vcenter-sso" in slug or "sso-locked" in slug:
        state["vcenter_sso_locked"] = True
        events.append(_event("SSO administrator account locked", "critical", "vCenter"))
        _set_validation(state, vcenter_sso_unlocked=True)

    else:
        # Unmapped VMware slug: fail validation until learner powers on web-prod-01
        # (default inventory already has it on — force a real broken state)
        if web:
            web["power"] = "poweredOff"
            web["tools"] = "notRunning"
        events.append(_event("Production VM web-prod-01 is down", "critical", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", require_power="poweredOn")

    events.append(_event("vCenter inventory loaded", "info", "vCenter"))
    if not tasks:
        tasks.extend([
            _task("Power On Virtual Machine", "api-prod-01"),
            _task("Power On Virtual Machine", "db-prod-01"),
        ])
