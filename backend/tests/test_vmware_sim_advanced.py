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
