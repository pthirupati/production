"""Apply VMware simulator fixes for E2E validation."""
from __future__ import annotations

from apps.vmware_sim.engine import _ensure_session, apply_action, validate_vmware_lab


def apply_vmware_simulation_fix(session) -> tuple[bool, str]:
    sid = str(session.id)
    slug = (session.scenario.slug or "").lower()
    _ensure_session(sid, slug)

    def act(action: str, **payload) -> None:
        apply_action(sid, action, payload or None)

    if "guest-hung" in slug or "hung-guest" in slug or "hung" in slug:
        act("mark_jira_updated")
        act("confirm_customer_reboot")
        act("reboot", vm_name="web-prod-01")
    elif "guest-powered-off" in slug or ("guest" in slug and "power" in slug):
        act("power_on", vm_name="web-prod-01")
    elif "host-disconnected" in slug or "management-network" in slug:
        act("reconnect_host", host_name="esxi-01.fixitlab.local")
    elif "ha-admission" in slug or "admission-control" in slug:
        act("fix_admission_control")
    elif "ha-failure" in slug:
        act("enable_ha")
        act("power_on", vm_name="web-prod-01")
    elif "enable-ha" in slug or "ha-drs" in slug:
        act("enable_ha")
        act("enable_drs")
        act("run_drs")
    elif "drs-disabled" in slug:
        act("enable_drs")
        act("run_drs")
    elif "datastore" in slug and ("full" in slug or "almost" in slug):
        act("expand_datastore", datastore="datastore-ssd-01", gb=500)
    elif "add-disk" in slug or "disk-expand" in slug or "extend-disk" in slug:
        act("add_disk", vm_name="web-prod-01", size_gb=80)
    elif "vsan" in slug:
        act("claim_vsan_disk")
    elif "storage-vmotion" in slug or "vmotion-stuck" in slug:
        act("complete_storage_vmotion")
    elif "network-disconnected" in slug or "vm-network" in slug:
        act("connect_network", vm_name="web-prod-01")
    elif "distributed-switch" in slug or "mtu" in slug:
        act("fix_dv_switch_mtu")
    elif "portgroup" in slug or "create-network" in slug:
        act("create_portgroup")
    elif "tools-outdated" in slug:
        act("upgrade_tools", vm_name="web-prod-01")
    elif "cpu-ready" in slug:
        act("reduce_cpu_contention", vm_name="web-prod-01")
    elif "snapshot" in slug:
        from apps.vmware_sim.engine import _load_session, _save_session

        entry = _load_session(sid)
        if entry:
            vm = next((v for v in entry["state"]["vms"] if v["name"] == "web-prod-01"), None)
            if vm and len(vm.get("snapshots", [])) > 1:
                for snap in vm["snapshots"][1:]:
                    act("delete_snapshot", vm_name="web-prod-01", snapshot_id=snap["id"])
    elif "vmotion-failed" in slug:
        act("resolve_vmotion")
    elif "template-convert" in slug or "clone-from-template" in slug:
        act("convert_template")
    elif "vcenter-certificate" in slug or "certificate-expired" in slug:
        act("renew_vcenter_cert")
    elif "vcenter-db-full" in slug or "db-full" in slug:
        act("expand_vcenter_db")
    elif "vcenter-sso" in slug or "sso-locked" in slug:
        act("unlock_sso")
    elif "ntp" in slug:
        act("sync_ntp")
    elif "coredump" in slug:
        act("clear_coredump", host_name="esxi-01.fixitlab.local")
    elif "question-pending" in slug:
        act("answer_question", vm_name="web-prod-01")
    elif "vmware" in slug:
        act("power_on", vm_name="web-prod-01")
    else:
        return False, f"no vmware fix map for {slug}"

    return validate_vmware_lab(sid, slug)
