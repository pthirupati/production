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


def _cross_tech_config(slug: str) -> dict | None:
    try:
        from apps.labs.provisioner.simulation.vmware_bridge import cross_tech_config
        return cross_tech_config(slug or "")
    except Exception:
        return None


def _make_node_vm(name: str, host_id: str, node: str, *, power: str,
                  hung: bool = False) -> dict:
    """A worker-node VM for a k8s-on-VMware lab. `k8s_node` binds it to the node."""
    return {
        "id": f"vm-{name}",
        "name": name,
        "host_id": host_id,
        "datastore_id": "ds-01",
        "network_id": "net-02",
        "resource_pool_id": "rp-prod",
        "power": power,
        "cpu": 4,
        "memory_mb": 8192,
        "disk_gb": 80,
        "guest_os": "Ubuntu Linux (64-bit)",
        "guest_os_version": "Ubuntu 22.04 LTS",
        "ip": "10.20.30.5%s" % node[-1] if node and node[-1].isdigit() else "10.20.30.50",
        "hostname": f"{name}.fixitlab.local",
        "tools": "toolsNotRunning" if (hung or power != "poweredOn") else "ok",
        "tools_version": "11333",
        "hardware_version": "vmx-19",
        "annotation": f"Kubernetes {node} (node is this VM)",
        "snapshots": [],
        "cpu_pct": 95 if hung else (random.randint(20, 45) if power == "poweredOn" else 0),
        "mem_pct": random.randint(40, 70) if power == "poweredOn" else 0,
        "disk_io_mbps": 0,
        "net_mbps": random.randint(5, 30) if power == "poweredOn" else 0,
        "k8s_node": node,
        **({"guest_hung": True} if hung else {}),
    }


def _seed_k8s_on_vmware(state: dict, slug: str, cfg: dict, alarm) -> None:
    """Populate the VMware inventory with the cluster's worker-node VMs.

    Add scenarios: worker-1 is up; worker-2's VM is powered OFF (so node worker-2
    is absent and pods are Pending) until the learner powers it on / creates it.
    Reset scenario: worker-1's VM is powered on but HUNG (node NotReady) until the
    learner resets it.
    """
    hosts = state.get("hosts", [])
    h1 = hosts[0]["id"] if hosts else "host-01"
    h2 = hosts[1]["id"] if len(hosts) > 1 else h1
    action = cfg.get("action")

    if action == "k8s_node_reset":
        # worker-1 VM is hung → its node is NotReady; reset to recover.
        wvm = _make_node_vm("k8s-worker-1", h1, "worker-1", power="poweredOn", hung=True)
        state["vms"].append(wvm)
        # A healthy worker-2 so only worker-1 is the problem.
        state["vms"].append(_make_node_vm("k8s-worker-2", h2, "worker-2", power="poweredOn"))
        state["events"].append(_event(
            "Guest heartbeat lost on k8s-worker-1 — node NotReady, reset required",
            "critical", "k8s-worker-1"))
        alarm("alm-k8s-node-hung", "Worker node VM hung (NotReady)", "k8s-worker-1")
        return

    # add / drain scenarios: worker-2's VM exists but is powered OFF.
    state["vms"].append(_make_node_vm("k8s-worker-1", h1, "worker-1", power="poweredOn"))
    state["vms"].append(_make_node_vm("k8s-worker-2", h2, "worker-2", power="poweredOff"))
    if action == "k8s_node_add":
        state["events"].append(_event(
            "Cluster capacity exhausted — power on worker node VM k8s-worker-2",
            "warning", "k8s-worker-2"))
        alarm("alm-k8s-capacity", "Insufficient cluster capacity", "Cluster-01", "warning")
    else:  # drain
        state["events"].append(_event(
            "Maintenance: drain k8s-worker-1 and bring up replacement k8s-worker-2",
            "info", "Cluster-01"))


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

    # ── Cross-technology scenarios (VMware ⇄ Linux terminal, shared session) ──
    # These slugs come from the LINUX scenario; the VMware inventory just needs
    # web-prod-01 in the right power state so the hardware action the lab expects
    # (Add Hard Disk / Add Network Adapter / Reset) is available on a running VM.
    if slug in ("linux-lvm-extend-vmware-disk-rescan",
                "linux-lvm-extend-vmware-disk-reboot",
                "linux-datastore-full-add-disk-vmware",
                "linux-nic-add-vmware-rescan"):
        if web:
            web["power"] = "poweredOn"
            web["tools"] = "ok"
        events.append(_event(
            "web-prod-01 needs additional hardware — add it via Edit Settings", "info", "web-prod-01"))
        return
    if slug == "linux-server-hung-needs-vmware-reset":
        if web:
            web["power"] = "poweredOn"
            web["guest_hung"] = True
            web["tools"] = "toolsNotRunning"
        events.append(_event(
            "Guest heartbeat lost on web-prod-01 — VM is hung, reset required", "critical", "web-prod-01"))
        alarm("alm-cross-hung", "Guest heartbeat lost", "web-prod-01")
        return

    # ── Cross-technology Kubernetes-on-VMware: the cluster's worker nodes ARE
    # VMware VMs. The k8s terminal's `kubectl get nodes` reflects power/reset
    # actions taken on these VMs (via the bridge cache). ──────────────────────
    _k8s_xcfg = _cross_tech_config(slug)
    if _k8s_xcfg and _k8s_xcfg.get("tech") == "kubernetes":
        _seed_k8s_on_vmware(state, slug, _k8s_xcfg, alarm)
        events.append(_event("vCenter inventory loaded", "info", "vCenter"))
        return

    # ── New scenarios (wave 4): each reuses an existing validation rule AND
    # an existing e2e fix substring, so they fail-closed before the fix and
    # pass after. Matched FIRST so their distinct slugs don't fall through to
    # a broader branch. ──────────────────────────────────────────────────
    if "datastore-thin-overcommit-full" in slug:
        ds = next((d for d in state.get("datastores", []) if d.get("name") == "datastore-ssd-01"), None)
        if ds is None and state.get("datastores"):
            ds = state["datastores"][0]
        if ds:
            ds["free_gb"] = 5
        events.append(_event("Datastore datastore-ssd-01 critically low on free space", "critical", "datastore-ssd-01"))
        alarm("alm-ds-thin", "Datastore usage critical", "datastore-ssd-01")
        _set_validation(state, datastore="datastore-ssd-01", datastore_min_free_gb=50)
        return
    if "esxi-coredump-partition-full" in slug:
        h = state["hosts"][0]
        h["coredump_full"] = True
        events.append(_event(f"Core dump partition full on {h['name']}", "warning", h["name"]))
        _set_validation(state, require_coredump_cleared=True)
        return
    if "esxi-ntp-drift-kerberos" in slug:
        for h in state["hosts"]:
            h["ntp_synced"] = False
        events.append(_event("ESXi host time drift detected — NTP not synced", "warning", "Cluster-01"))
        _set_validation(state, require_ntp_synced=True)
        return
    if "vm-tools-outdated-blocking-quiesce" in slug:
        if web:
            web["tools"] = "toolsOld"
        events.append(_event("VMware Tools out of date on web-prod-01 — quiesced snapshots failing", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", require_tools="toolsOk")
        return
    if "vm-cpu-ready-contention" in slug:
        if web:
            web["cpu_ready_pct"] = 18
        events.append(_event("High CPU ready time on web-prod-01 — host CPU contention", "warning", "web-prod-01"))
        _set_validation(state, target_vm="web-prod-01", max_cpu_ready_pct=5)
        return
    if "vm-snapshot-chain-consolidate" in slug:
        if web:
            web["snapshots"] = [
                {"id": f"snap-{i}", "name": f"snap-{i}", "created": _now_iso()} for i in range(1, 6)
            ]
        events.append(_event("web-prod-01 has a long snapshot chain consuming datastore space", "warning", "web-prod-01"))
        alarm("alm-snap-chain", "Snapshot chain too long", "web-prod-01")
        _set_validation(state, target_vm="web-prod-01", max_snapshots=1)
        return
    if "vm-network-adapter-disconnected" in slug:
        if web:
            web["network_disconnected"] = True
        events.append(_event("web-prod-01 network adapter is disconnected", "warning", "web-prod-01"))
        alarm("alm-vm-net", "VM network disconnected", "web-prod-01")
        _set_validation(state, target_vm="web-prod-01", require_network_connected=True)
        return
    if "vsan-disk-group-unclaimed" in slug:
        state["vsan_disk_unclaimed"] = True
        events.append(_event("vSAN disks unclaimed on a host — capacity reduced", "warning", "Cluster-01"))
        alarm("alm-vsan-claim", "vSAN disks unclaimed", "Cluster-01")
        _set_validation(state, vsan_disks_claimed=True)
        return
    if "vcenter-sso-account-lockout" in slug:
        state["vcenter_sso_locked"] = True
        events.append(_event("vCenter SSO administrator account locked after failed logins", "critical", "vCenter"))
        alarm("alm-sso-lock", "SSO account locked", "vCenter")
        _set_validation(state, vcenter_sso_unlocked=True)
        return
    if "esxi-management-network-isolated" in slug:
        h = state["hosts"][0]
        h["management_network"] = "down"
        h["status"] = "disconnected"
        h["connection_state"] = "disconnected"
        events.append(_event(f"Management network isolated on {h['name']}", "critical", h["name"]))
        alarm("alm-mgmt-iso", "Management network isolated", h["name"])
        _set_validation(state, require_host_connected=h["name"])
        return

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
            disks = web.setdefault("disks", [])
            if not any(d.get("scsi_unit", 0) > 0 for d in disks):
                disks.append({
                    "id": f"{web['id']}-disk1-preset",
                    "label": "Hard disk 2",
                    "scsi_controller": 0,
                    "scsi_unit": 1,
                    "scsi_id": "0:1",
                    "controller_type": "LSI Logic SAS",
                    "capacity_gb": 20,
                    "thin_provisioned": True,
                    "datastore_id": web.get("datastore_id"),
                })
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

    elif "linked-mode" in slug or "linked-datacenter" in slug:
        state["linked_mode"] = False
        for dc in state.get("datacenters", []):
            if dc.get("site") == "recovery":
                dc["linked"] = False
        events.append(_event("DC-DR not visible — enable Enhanced Linked Mode", "warning", "vCenter"))
        _set_validation(state, linked_mode_enabled=True)

    elif "nsx" in slug or "microseg" in slug:
        state.setdefault("nsx", {})["enabled"] = False
        state["nsx"]["microseg_missing"] = True
        events.append(_event("NSX-T micro-segmentation rule missing for prod tier", "critical", "NSX"))
        _set_validation(state, nsx_microseg_configured=True)

    elif "srm" in slug or "disaster-recovery" in slug or "site-recovery" in slug:
        srm = state.setdefault("srm", {})
        srm["enabled"] = False
        srm["replication_ok"] = False
        events.append(_event("SRM replication not configured between DC-Prod and DC-DR", "critical", "SRM"))
        _set_validation(state, srm_recovery_tested=True)

    elif "vami" in slug or "vcenter-patch" in slug:
        vami = state.setdefault("vami", {})
        vami["pending_patches"] = 2
        state["vcenter_cert_expired"] = False
        events.append(_event("vCenter VAMI has pending appliance patches", "warning", "VAMI"))
        _set_validation(state, vami_patches_installed=True)

    elif "vm-wizard" in slug or ("create-vm" in slug and "do" in slug):
        events.append(_event("Create a new VM using the 14-step wizard", "info", "vCenter"))
        _set_validation(state, wizard_vm_created=True)

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
