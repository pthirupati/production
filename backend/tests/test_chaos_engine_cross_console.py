"""Cross-console fault visibility: real engine actions (VMware NIC disconnect,
Windows service stop, NetApp volume near-full) must publish into the shared
chaos_engine ledger (Phase 3.2/3.4) so any OTHER open console for the same
session can see "here is what is currently broken" without polling every
engine individually — mirrors the datacenter_engine trip_pdu_breaker pattern
that already existed before this pass.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.labs.provisioner.simulation import chaos_engine as ce
from apps.vmware_sim import engine as vmware_engine
from apps.vmware_sim import windows_engine
from apps.vmware_sim import netapp_engine
from apps.vmware_sim import awx_engine
from apps.vmware_sim import soc_engine


class VmwareChaosLedgerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "chaos-cross-vmware"
        vmware_engine.drop_session(self.sid)
        self.addCleanup(vmware_engine.drop_session, self.sid)
        self.addCleanup(cache.clear)

    def _vm(self):
        inv = vmware_engine.get_state(self.sid)["inventory"]
        return inv["vms"][0]

    def test_disconnect_network_publishes_drop_nic_fault(self):
        vmware_engine.get_state(self.sid)
        vm = self._vm()
        res = vmware_engine.apply_action(self.sid, "disconnect_network", {"vm_id": vm["id"]})
        self.assertTrue(res["ok"], res)

        active = ce.list_faults(self.sid, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["fault_type"], "drop_nic")
        self.assertEqual(active[0]["target"], vm["name"])

    def test_reconnect_network_clears_drop_nic_fault(self):
        vmware_engine.get_state(self.sid)
        vm = self._vm()
        vmware_engine.apply_action(self.sid, "disconnect_network", {"vm_id": vm["id"]})
        vmware_engine.apply_action(self.sid, "connect_network", {"vm_id": vm["id"]})

        active = ce.list_faults(self.sid, active_only=True)
        self.assertEqual(active, [])
        # The historical record still shows the fault happened.
        self.assertEqual(len(ce.list_faults(self.sid)), 1)


class WindowsChaosLedgerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "chaos-cross-windows"
        windows_engine.drop_session(self.sid)
        self.addCleanup(windows_engine.drop_session, self.sid)
        self.addCleanup(cache.clear)

    def _first_service(self):
        state = windows_engine.get_state(self.sid)
        return state["services"][0]

    def test_stop_service_publishes_stop_service_fault(self):
        svc = self._first_service()
        res = windows_engine.apply_action(
            self.sid, "stop_service", {"session_id": self.sid, "service": svc["name"]},
        )
        self.assertTrue(res["ok"], res)
        active = ce.list_faults(self.sid, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["fault_type"], "stop_service")

    def test_start_service_clears_stop_service_fault(self):
        svc = self._first_service()
        windows_engine.apply_action(self.sid, "stop_service", {"session_id": self.sid, "service": svc["name"]})
        res = windows_engine.apply_action(self.sid, "start_service", {"session_id": self.sid, "service": svc["name"]})
        self.assertTrue(res["ok"], res)
        self.assertEqual(ce.list_faults(self.sid, active_only=True), [])


class NetAppChaosLedgerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "chaos-cross-netapp"
        netapp_engine.drop_session(self.sid)
        self.addCleanup(netapp_engine.drop_session, self.sid)
        self.addCleanup(cache.clear)

    def test_seeding_a_near_full_volume_publishes_fill_disk_fault(self):
        # Default preset (no slug match) leaves vol_web_data at 95% per _base_state.
        state = netapp_engine.get_state(self.sid)["state"]
        near_full = state["broken"].get("volume_near_full")
        self.assertTrue(near_full)

        active = ce.list_faults(self.sid, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["fault_type"], "fill_disk")
        self.assertEqual(active[0]["target"], near_full)

    def test_resize_volume_clears_fill_disk_fault(self):
        state = netapp_engine.get_state(self.sid)["state"]
        near_full = state["broken"]["volume_near_full"]
        netapp_engine.apply_action(self.sid, "login", {"user": "admin"})
        res = netapp_engine.apply_action(self.sid, "resize_volume", {"name": near_full})
        self.assertTrue(res["ok"], res)
        self.assertEqual(ce.list_faults(self.sid, active_only=True), [])


class AwxChaosLedgerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "chaos-cross-awx"
        awx_engine.drop_session(self.sid)
        self.addCleanup(awx_engine.drop_session, self.sid)
        self.addCleanup(cache.clear)

    def _first_host(self):
        state = awx_engine.get_state(self.sid)["inventory"]
        return state["hosts"][0]

    def test_disabling_a_host_publishes_drop_nic_fault(self):
        host = self._first_host()
        awx_engine.apply_action(self.sid, "login", {"user": "admin"})
        res = awx_engine.apply_action(self.sid, "toggle_host", {"host_id": host["id"]})
        self.assertTrue(res["ok"], res)
        active = ce.list_faults(self.sid, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["fault_type"], "drop_nic")
        self.assertEqual(active[0]["target"], host["name"])

    def test_re_enabling_a_host_clears_drop_nic_fault(self):
        host = self._first_host()
        awx_engine.apply_action(self.sid, "login", {"user": "admin"})
        r1 = awx_engine.apply_action(self.sid, "toggle_host", {"host_id": host["id"]})
        self.assertTrue(r1["ok"], r1)
        r2 = awx_engine.apply_action(self.sid, "toggle_host", {"host_id": host["id"]})
        self.assertTrue(r2["ok"], r2)
        self.assertEqual(ce.list_faults(self.sid, active_only=True), [])


class SocChaosLedgerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "chaos-cross-soc"
        soc_engine.drop_session(self.sid)
        self.addCleanup(soc_engine.drop_session, self.sid)
        self.addCleanup(cache.clear)

    def test_quarantine_host_publishes_drop_nic_fault(self):
        soc_engine.get_state(self.sid, "soc-quarantine-malware")
        soc_engine.apply_action(self.sid, "login", {"user": "analyst"})
        res = soc_engine.apply_action(self.sid, "quarantine_host", {"asset": "ws-finance-07"})
        self.assertTrue(res["ok"], res)
        active = ce.list_faults(self.sid, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["fault_type"], "drop_nic")
        self.assertEqual(active[0]["target"], "ws-finance-07")
