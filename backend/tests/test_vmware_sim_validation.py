"""Tests for VMware simulator validation — scenarios must not pass without fixes."""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim.engine import (
    _ensure_session,
    apply_action,
    drop_session,
    validate_vmware_lab,
)


class VMwareValidationTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str) -> str:
        sid = f"test-{slug}"
        drop_session(sid)
        _ensure_session(sid, slug)
        return sid

    def test_guest_powered_off_fails_until_power_on(self):
        sid = self._session("vmware-guest-powered-off")
        ok, _ = validate_vmware_lab(sid, "vmware-guest-powered-off")
        self.assertFalse(ok)
        apply_action(sid, "power_on", {"vm_name": "web-prod-01"})
        ok, msg = validate_vmware_lab(sid, "vmware-guest-powered-off")
        self.assertTrue(ok, msg)

    def test_unmapped_vmware_slug_does_not_auto_pass(self):
        sid = self._session("vmware-unknown-scenario")
        ok, _ = validate_vmware_lab(sid, "vmware-unknown-scenario")
        self.assertFalse(ok)

    # --- Console boot-vs-login state (Bug #1) -------------------------------
    def _vm(self, sid, name):
        from apps.vmware_sim.engine import _load_session, _find_vm
        return _find_vm(_load_session(sid)["state"], vm_name=name)

    def test_running_vm_has_no_boot_pending_on_fresh_session(self):
        # An already-running guest (powered on in the base inventory) must NOT be
        # flagged for a boot replay — the console should open straight to login.
        sid = self._session("vmware-console-demo")
        self.assertFalse(self._vm(sid, "api-prod-01").get("boot_pending"))

    def test_power_on_sets_boot_pending_and_console_booted_clears_it(self):
        sid = self._session("vmware-console-demo")
        apply_action(sid, "power_on", {"vm_name": "web-prod-01"})
        self.assertTrue(self._vm(sid, "web-prod-01").get("boot_pending"))
        # The UI signals it has replayed the boot; flag clears -> next open = login.
        res = apply_action(sid, "console_booted", {"vm_name": "web-prod-01"})
        self.assertTrue(res["ok"])
        self.assertFalse(self._vm(sid, "web-prod-01").get("boot_pending"))

    def test_reboot_sets_boot_pending_and_power_off_clears_it(self):
        sid = self._session("vmware-console-demo")
        apply_action(sid, "reboot", {"vm_name": "api-prod-01"})
        self.assertTrue(self._vm(sid, "api-prod-01").get("boot_pending"))
        apply_action(sid, "power_off", {"vm_name": "api-prod-01"})
        self.assertFalse(self._vm(sid, "api-prod-01").get("boot_pending"))

    def test_hung_guest_requires_jira_and_customer_before_reboot(self):
        sid = self._session("vmware-guest-hung-ssh")
        ok, msg = validate_vmware_lab(sid, "vmware-guest-hung-ssh")
        self.assertFalse(ok)
        self.assertIn("Jira", msg)
        apply_action(sid, "reboot", {"vm_name": "web-prod-01"})
        ok, _ = validate_vmware_lab(sid, "vmware-guest-hung-ssh")
        self.assertFalse(ok)
        apply_action(sid, "mark_jira_updated")
        apply_action(sid, "confirm_customer_reboot")
        apply_action(sid, "reboot", {"vm_name": "web-prod-01"})
        ok, msg = validate_vmware_lab(sid, "vmware-guest-hung-ssh")
        self.assertTrue(ok, msg)

    def test_add_disk_scenario(self):
        sid = self._session("vmware-add-disk")
        ok, _ = validate_vmware_lab(sid, "vmware-add-disk")
        self.assertFalse(ok)
        apply_action(sid, "add_disk", {"vm_name": "web-prod-01", "size_gb": 80})
        ok, msg = validate_vmware_lab(sid, "vmware-add-disk")
        self.assertTrue(ok, msg)

    def test_drs_disabled_requires_enable(self):
        sid = self._session("drs-disabled")
        ok, _ = validate_vmware_lab(sid, "drs-disabled")
        self.assertFalse(ok)
        apply_action(sid, "enable_drs")
        ok, msg = validate_vmware_lab(sid, "drs-disabled")
        self.assertTrue(ok, msg)

    def test_datastore_full_requires_expand(self):
        sid = self._session("datastore-almost-full")
        ok, _ = validate_vmware_lab(sid, "datastore-almost-full")
        self.assertFalse(ok)
        apply_action(sid, "expand_datastore", {"datastore": "datastore-ssd-01", "gb": 500})
        ok, msg = validate_vmware_lab(sid, "datastore-almost-full")
        self.assertTrue(ok, msg)
