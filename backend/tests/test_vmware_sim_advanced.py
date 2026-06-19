"""Tests for advanced VMware simulator features — linked mode, NSX, SRM, VAMI, wizard."""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim.engine import (
    _ensure_session,
    apply_action,
    drop_session,
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
        from apps.vmware_sim.engine import get_state
        state = get_state(sid)["inventory"]
        web = next(v for v in state["vms"] if v["name"] == "web-prod-01")
        self.assertEqual(web.get("host_id"), "host-dr-01")
