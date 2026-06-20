"""Tests for advanced VMware simulator features — linked mode, NSX, SRM, VAMI, wizard."""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim.engine import (
    _ensure_session,
    apply_action,
    drop_session,
    get_state,
    validate_vmware_lab,
)


class VMwareAdvancedTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str) -> str:
        sid = f"test-adv-{slug}"
        drop_session(sid)
        _ensure_session(sid, slug)
        return sid

    def test_linked_mode_scenario(self):
        sid = self._session("linked-mode-datacenter")
        ok, _ = validate_vmware_lab(sid, "linked-mode-datacenter")
        self.assertFalse(ok)
        apply_action(sid, "enable_linked_mode")
        ok, msg = validate_vmware_lab(sid, "linked-mode-datacenter")
        self.assertTrue(ok, msg)

    def test_nsx_microsegmentation(self):
        sid = self._session("nsx-microsegmentation")
        ok, _ = validate_vmware_lab(sid, "nsx-microsegmentation")
        self.assertFalse(ok)
        apply_action(sid, "enable_nsx")
        apply_action(sid, "create_nsx_firewall_rule", {"name": "Prod-Tier-Allow", "source": "10.20.30.0/24", "dest": "10.20.40.0/24", "service": "HTTPS"})
        ok, msg = validate_vmware_lab(sid, "nsx-microsegmentation")
        self.assertTrue(ok, msg)

    def test_srm_recovery_test(self):
        sid = self._session("srm-disaster-recovery")
        ok, _ = validate_vmware_lab(sid, "srm-disaster-recovery")
        self.assertFalse(ok)
        apply_action(sid, "enable_linked_mode")
        apply_action(sid, "configure_srm")
        apply_action(sid, "srm_test_recovery")
        ok, msg = validate_vmware_lab(sid, "srm-disaster-recovery")
        self.assertTrue(ok, msg)

    def test_vami_patches(self):
        sid = self._session("vcenter-vami-patch")
        ok, _ = validate_vmware_lab(sid, "vcenter-vami-patch")
        self.assertFalse(ok)
        apply_action(sid, "vami_install_patches")
        ok, msg = validate_vmware_lab(sid, "vcenter-vami-patch")
        self.assertTrue(ok, msg)

    def test_create_vm_wizard(self):
        sid = self._session("create-vm-wizard-do")
        ok, _ = validate_vmware_lab(sid, "create-vm-wizard-do")
        self.assertFalse(ok)
        apply_action(sid, "create_vm_wizard", {
            "name": "lab-app-01",
            "cpu": 2,
            "memory_mb": 4096,
            "disk_gb": 40,
            "guest_os": "Ubuntu Linux (64-bit)",
        })
        ok, msg = validate_vmware_lab(sid, "create-vm-wizard-do")
        self.assertTrue(ok, msg)

    def test_srm_failover_moves_vms(self):
        sid = self._session("srm-disaster-recovery")
        apply_action(sid, "enable_linked_mode")
        apply_action(sid, "configure_srm")
        apply_action(sid, "srm_test_recovery")
        apply_action(sid, "srm_failover")
        state = get_state(sid)["inventory"]
        web = next(v for v in state["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(web.get("host_id"), "host-dr-01")

    def test_upgrade_vmware_tools_sets_status_current(self):
        sid = self._session("vmware-guest-powered-off")
        # web-prod-01 starts powered off with tools notRunning in this scenario.
        res = apply_action(sid, "upgrade_vmware_tools", {"vm_name": "web-prod-01"})
        self.assertTrue(res["ok"], res)
        state = get_state(sid)["inventory"]
        web = next(v for v in state["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(web["vmware_tools_status"], "current")
        self.assertEqual(web["tools"], "ok")

    def test_create_vcenter_user_and_assign_role(self):
        sid = self._session("vmware-guest-powered-off")
        # Reject weak password.
        bad = apply_action(sid, "create_vcenter_user", {"username": "ops_user", "password": "123", "role": "Read Only"})
        self.assertFalse(bad["ok"])
        # Create a valid user, then change its role.
        ok = apply_action(sid, "create_vcenter_user", {
            "username": "ops_user", "password": "Sup3rSecret", "role": "Read Only",
        })
        self.assertTrue(ok["ok"], ok)
        users = get_state(sid)["inventory"]["vcenter_users"]
        self.assertTrue(any(u["username"] == "ops_user" for u in users))
        # Duplicate username is rejected.
        dup = apply_action(sid, "create_vcenter_user", {"username": "ops_user", "password": "Sup3rSecret"})
        self.assertFalse(dup["ok"])
        # Role assignment + password reset succeed.
        role_res = apply_action(sid, "assign_user_role", {"username": "ops_user", "role": "Virtual Machine Administrator"})
        self.assertTrue(role_res["ok"], role_res)
        reset_res = apply_action(sid, "reset_user_password", {"username": "ops_user", "password": "An0therPass"})
        self.assertTrue(reset_res["ok"], reset_res)
        users = get_state(sid)["inventory"]["vcenter_users"]
        self.assertEqual(next(u for u in users if u["username"] == "ops_user")["role"], "Virtual Machine Administrator")

    def test_default_lab_user_present(self):
        sid = self._session("vmware-guest-powered-off")
        users = get_state(sid)["inventory"]["vcenter_users"]
        self.assertTrue(any(u["username"] == "lab_vmware" for u in users))

    def test_datastore_low_space_warning_flag(self):
        sid = self._session("datastore-almost-full")
        summary = get_state(sid)["summary"]
        inv = get_state(sid)["inventory"]
        # The almost-full scenario leaves a datastore under the 15% free threshold.
        low = summary["datastores_low_space"]
        self.assertTrue(low, "expected at least one datastore flagged low on space")
        flagged_names = {d["name"] for d in low}
        for ds in inv["datastores"]:
            if ds["name"] in flagged_names:
                self.assertIn(ds["warning"], ("warning", "critical"))
                self.assertLess(ds["free_pct"], 15)

    def test_create_alarm_definition(self):
        sid = self._session("vmware-guest-powered-off")
        before = len(get_state(sid)["inventory"]["alarm_definitions"])
        res = apply_action(sid, "create_alarm_definition", {
            "name": "Custom disk latency", "entity_type": "Datastore",
            "metric": "disk.latency", "operator": ">", "threshold": 30, "severity": "warning",
        })
        self.assertTrue(res["ok"], res)
        defs = get_state(sid)["inventory"]["alarm_definitions"]
        self.assertEqual(len(defs), before + 1)
        self.assertTrue(any(d["name"] == "Custom disk latency" for d in defs))

    def test_add_and_remove_disk(self):
        sid = self._session("vmware-guest-powered-off")
        web = next(v for v in get_state(sid)["inventory"]["vms"] if v["name"] == "web-prod-01")
        before_disks = len(web["disks"])
        # Add a thick-provisioned disk; SCSI unit should be auto-assigned 0:1.
        add = apply_action(sid, "add_disk", {"vm_name": "web-prod-01", "size_gb": 50, "thin": False})
        self.assertTrue(add["ok"], add)
        web = next(v for v in get_state(sid)["inventory"]["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(len(web["disks"]), before_disks + 1)
        new_disk = web["disks"][-1]
        self.assertEqual(new_disk["scsi_id"], "0:1")
        self.assertFalse(new_disk["thin_provisioned"])
        # Boot disk (0:0) cannot be removed.
        boot = next(d for d in web["disks"] if d["scsi_id"] == "0:0")
        bad = apply_action(sid, "remove_disk", {"vm_name": "web-prod-01", "disk_id": boot["id"]})
        self.assertFalse(bad["ok"])
        # The added disk removes cleanly.
        rem = apply_action(sid, "remove_disk", {"vm_name": "web-prod-01", "disk_id": new_disk["id"]})
        self.assertTrue(rem["ok"], rem)
        web = next(v for v in get_state(sid)["inventory"]["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(len(web["disks"]), before_disks)

    def test_add_and_remove_network_adapter(self):
        sid = self._session("vmware-guest-powered-off")
        web = next(v for v in get_state(sid)["inventory"]["vms"] if v["name"] == "web-prod-01")
        before = len(web["nics"])
        add = apply_action(sid, "add_nic", {"vm_name": "web-prod-01", "network_id": "net-03"})
        self.assertTrue(add["ok"], add)
        web = next(v for v in get_state(sid)["inventory"]["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(len(web["nics"]), before + 1)
        new_nic = web["nics"][-1]
        self.assertEqual(new_nic["network_id"], "net-03")
        rem = apply_action(sid, "remove_nic", {"vm_name": "web-prod-01", "nic_id": new_nic["id"]})
        self.assertTrue(rem["ok"], rem)
        web = next(v for v in get_state(sid)["inventory"]["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(len(web["nics"]), before)
        # Cannot remove the last adapter.
        last = web["nics"][0]
        bad = apply_action(sid, "remove_nic", {"vm_name": "web-prod-01", "nic_id": last["id"]})
        self.assertFalse(bad["ok"])

    def test_create_vswitch_and_portgroup_and_remove(self):
        sid = self._session("vmware-guest-powered-off")
        sw = apply_action(sid, "create_vswitch", {"name": "vSwitch-Lab", "type": "standard", "mtu": 9000})
        self.assertTrue(sw["ok"], sw)
        switches = get_state(sid)["inventory"]["vswitches"]
        self.assertTrue(any(v["name"] == "vSwitch-Lab" for v in switches))
        # Create a VLAN-tagged port group on the new switch.
        pg = apply_action(sid, "create_portgroup", {"name": "Lab-VLAN-300", "vlan": 300, "switch": "vSwitch-Lab"})
        self.assertTrue(pg["ok"], pg)
        nets = get_state(sid)["inventory"]["networks"]
        lab_net = next(n for n in nets if n["name"] == "Lab-VLAN-300")
        self.assertEqual(lab_net["vlan_id"], 300)
        self.assertEqual(lab_net["switch"], "vSwitch-Lab")
        # Switch with an attached port group refuses removal until the PG is gone.
        blocked = apply_action(sid, "remove_vswitch", {"name": "vSwitch-Lab"})
        self.assertFalse(blocked["ok"])
        self.assertTrue(apply_action(sid, "remove_portgroup", {"network_id": lab_net["id"]})["ok"])
        self.assertTrue(apply_action(sid, "remove_vswitch", {"name": "vSwitch-Lab"})["ok"])
        names = {v["name"] for v in get_state(sid)["inventory"]["vswitches"]}
        self.assertNotIn("vSwitch-Lab", names)

    def test_create_datastore(self):
        sid = self._session("vmware-guest-powered-off")
        before = len(get_state(sid)["inventory"]["datastores"])
        res = apply_action(sid, "create_datastore", {"name": "ds-lab-nvme", "type": "VMFS", "capacity_gb": 1024})
        self.assertTrue(res["ok"], res)
        dss = get_state(sid)["inventory"]["datastores"]
        self.assertEqual(len(dss), before + 1)
        new_ds = next(d for d in dss if d["name"] == "ds-lab-nvme")
        self.assertEqual(new_ds["capacity_gb"], 1024)
        self.assertEqual(new_ds["free_gb"], 1024)
        # Duplicate name is rejected.
        self.assertFalse(apply_action(sid, "create_datastore", {"name": "ds-lab-nvme", "capacity_gb": 100})["ok"])

    def test_create_cluster(self):
        sid = self._session("vmware-guest-powered-off")
        res = apply_action(sid, "create_cluster", {"name": "Cluster-Edge", "ha": True, "drs": True, "vsan": False})
        self.assertTrue(res["ok"], res)
        dcs = get_state(sid)["inventory"]["datacenters"]
        all_clusters = [c for dc in dcs for c in dc.get("clusters", [])]
        edge = next(c for c in all_clusters if c["name"] == "Cluster-Edge")
        self.assertTrue(edge["ha"])
        self.assertTrue(edge["drs"])
        self.assertFalse(edge["vsan"])
        # Duplicate cluster name in the same datacenter is rejected.
        dup = apply_action(sid, "create_cluster", {"name": "Cluster-Edge", "datacenter_id": dcs[0]["id"]})
        self.assertFalse(dup["ok"])

    def test_add_host(self):
        sid = self._session("vmware-guest-powered-off")
        before = len(get_state(sid)["inventory"]["hosts"])
        res = apply_action(sid, "add_host", {"name": "esxi-03.fixitlab.local", "ip": "192.168.10.13", "memory_gb": 256})
        self.assertTrue(res["ok"], res)
        hosts = get_state(sid)["inventory"]["hosts"]
        self.assertEqual(len(hosts), before + 1)
        new_host = next(h for h in hosts if h["name"] == "esxi-03.fixitlab.local")
        self.assertEqual(new_host["status"], "connected")
        self.assertEqual(new_host["memory_gb"], 256)
        # New host is attached to the datacenter's first cluster.
        dcs = get_state(sid)["inventory"]["datacenters"]
        dc_hosts = [h for dc in dcs for c in dc.get("clusters", []) for h in c.get("hosts", [])]
        self.assertIn(new_host["id"], dc_hosts)
        # Duplicate add is rejected.
        self.assertFalse(apply_action(sid, "add_host", {"name": "esxi-03.fixitlab.local"})["ok"])

    def test_new_resource_pool(self):
        sid = self._session("vmware-guest-powered-off")
        before = len(get_state(sid)["inventory"]["resource_pools"])
        res = apply_action(sid, "new_resource_pool", {
            "name": "RP-QA", "cpu_shares": "high", "mem_limit_mb": 8192,
        })
        self.assertTrue(res["ok"], res)
        pools = get_state(sid)["inventory"]["resource_pools"]
        self.assertEqual(len(pools), before + 1)
        qa = next(p for p in pools if p["name"] == "RP-QA")
        self.assertEqual(qa["cpu_shares"], "high")
        self.assertEqual(qa["mem_limit_mb"], 8192)
        # Empty name is rejected.
        self.assertFalse(apply_action(sid, "new_resource_pool", {"name": "  "})["ok"])

    def test_new_vapp_and_power(self):
        sid = self._session("vmware-guest-powered-off")
        res = apply_action(sid, "new_vapp", {"name": "vApp-Web", "vms": ["vm-api"]})
        self.assertTrue(res["ok"], res)
        vapps = get_state(sid)["inventory"]["vapps"]
        self.assertTrue(any(v["name"] == "vApp-Web" for v in vapps))
        vapp_id = next(v for v in vapps if v["name"] == "vApp-Web")["id"]
        # Powering the vApp on powers on its member VMs.
        on = apply_action(sid, "vapp_power", {"vapp_id": vapp_id, "op": "on"})
        self.assertTrue(on["ok"], on)
        inv = get_state(sid)["inventory"]
        api = next(v for v in inv["vms"] if v["id"] == "vm-api")
        self.assertEqual(api["power"], "poweredOn")
        self.assertEqual(next(v for v in inv["vapps"] if v["id"] == vapp_id)["power"], "poweredOn")
        # Duplicate name rejected.
        self.assertFalse(apply_action(sid, "new_vapp", {"name": "vApp-Web"})["ok"])

    def test_create_datastore_cluster(self):
        sid = self._session("vmware-guest-powered-off")
        res = apply_action(sid, "create_datastore_cluster", {
            "name": "DSC-Prod", "sdrs_enabled": True, "datastore_ids": ["ds-01", "ds-02"],
        })
        self.assertTrue(res["ok"], res)
        inv = get_state(sid)["inventory"]
        dsc = next(c for c in inv["datastore_clusters"] if c["name"] == "DSC-Prod")
        self.assertTrue(dsc["sdrs_enabled"])
        self.assertEqual(set(dsc["datastore_ids"]), {"ds-01", "ds-02"})
        # Member datastores are tagged with the pod id.
        ds01 = next(d for d in inv["datastores"] if d["id"] == "ds-01")
        self.assertEqual(ds01.get("datastore_cluster_id"), dsc["id"])
        # Toggle SDRS off.
        off = apply_action(sid, "toggle_datastore_sdrs", {"datastore_cluster_id": dsc["id"], "sdrs_enabled": False})
        self.assertTrue(off["ok"], off)
        self.assertFalse(next(c for c in get_state(sid)["inventory"]["datastore_clusters"] if c["id"] == dsc["id"])["sdrs_enabled"])
        # Duplicate name rejected.
        self.assertFalse(apply_action(sid, "create_datastore_cluster", {"name": "DSC-Prod"})["ok"])

    def test_assign_role_and_permission(self):
        sid = self._session("vmware-guest-powered-off")
        before = len(get_state(sid)["inventory"]["permissions"])
        # assign_role is an alias of assign_permission and mutates state.
        res = apply_action(sid, "assign_role", {
            "entity": "DC-Prod", "entity_id": "dc-prod", "entity_type": "datacenter",
            "principal": "ops_user", "role": "Virtual Machine Power User",
        })
        self.assertTrue(res["ok"], res)
        perms = get_state(sid)["inventory"]["permissions"]
        self.assertEqual(len(perms), before + 1)
        added = next(p for p in perms if p["principal"] == "ops_user")
        self.assertEqual(added["role"], "Virtual Machine Power User")
        # Revoking removes it.
        rev = apply_action(sid, "revoke_permission", {"permission_id": added["id"]})
        self.assertTrue(rev["ok"], rev)
        self.assertFalse(any(p["principal"] == "ops_user" for p in get_state(sid)["inventory"]["permissions"]))
        # Missing principal is rejected.
        self.assertFalse(apply_action(sid, "assign_role", {"entity": "DC-Prod", "principal": ""})["ok"])

    def test_add_folder(self):
        sid = self._session("vmware-guest-powered-off")
        for ftype in ("host", "vm", "storage", "network"):
            res = apply_action(sid, "add_folder", {"name": f"{ftype.capitalize()}-Folder", "folder_type": ftype})
            self.assertTrue(res["ok"], res)
        folders = get_state(sid)["inventory"]["folders"]
        self.assertEqual(len(folders), 4)
        self.assertEqual({f["folder_type"] for f in folders}, {"host", "vm", "storage", "network"})
        # Duplicate (same name + type) is rejected.
        self.assertFalse(apply_action(sid, "add_folder", {"name": "Vm-Folder", "folder_type": "vm"})["ok"])

    def test_create_custom_role(self):
        sid = self._session("vmware-guest-powered-off")
        res = apply_action(sid, "create_role", {"name": "Backup Operator", "privilege_groups": ["Datastore", "Virtual machine"]})
        self.assertTrue(res["ok"], res)
        inv = get_state(sid)["inventory"]
        self.assertIn("Backup Operator", inv["roles_catalog"])
        # The new role is usable for permission assignment immediately.
        assign = apply_action(sid, "assign_role", {"principal": "backup_svc", "role": "Backup Operator", "entity": "DC-Prod"})
        self.assertTrue(assign["ok"], assign)

    def test_licensing_key_masked_in_state(self):
        sid = self._session("vmware-guest-powered-off")
        lic = get_state(sid)["inventory"]["licensing"]
        self.assertTrue(lic["license_key_masked"].endswith(lic["license_key"].split("-")[-1]))
        self.assertIn("XXXXX", lic["license_key_masked"])
        self.assertTrue(lic["features"])

    def test_add_and_remove_host_uplink(self):
        sid = self._session("vmware-guest-powered-off")
        host0 = get_state(sid)["inventory"]["hosts"][0]
        before = [v["name"] for v in host0["vmnics"]]
        # New uplink must take the next free vmnicN (no collision with the defaults).
        add = apply_action(sid, "add_host_uplink", {"host_id": "host-01", "switch": "vSwitch0"})
        self.assertTrue(add["ok"], add)
        host0 = get_state(sid)["inventory"]["hosts"][0]
        names = [v["name"] for v in host0["vmnics"]]
        self.assertEqual(len(names), len(before) + 1)
        self.assertEqual(len(set(names)), len(names), "uplink names must be unique")
        new_name = names[-1]
        rem = apply_action(sid, "remove_host_uplink", {"host_id": "host-01", "name": new_name})
        self.assertTrue(rem["ok"], rem)
        host0 = get_state(sid)["inventory"]["hosts"][0]
        self.assertEqual([v["name"] for v in host0["vmnics"]], before)
