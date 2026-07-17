"""Unit tests for the shared in-memory chaos/fault-injection helper used by
lab consoles (physical datacenter breaker trips, NIC drops, etc)."""

import uuid

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import chaos_engine as ce


class ChaosEngineTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    def test_inject_rejects_unknown_fault_type(self):
        with self.assertRaises(ValueError):
            ce.inject(self.session_id, "nuke_datacenter", "srv-1")

    def test_inject_and_list_faults(self):
        fault = ce.inject(self.session_id, "trip_pdu", "PDU-R01", detail={"rack": "R01"})
        self.assertEqual(fault["fault_type"], "trip_pdu")
        self.assertTrue(fault["active"])
        faults = ce.list_faults(self.session_id)
        self.assertEqual(len(faults), 1)
        self.assertEqual(faults[0]["target"], "PDU-R01")

    def test_list_faults_active_only(self):
        ce.inject(self.session_id, "drop_nic", "srv-1")
        ce.inject(self.session_id, "fill_disk", "srv-2")
        ce.clear_faults(self.session_id, target="srv-1")
        active = ce.list_faults(self.session_id, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["target"], "srv-2")
        all_faults = ce.list_faults(self.session_id)
        self.assertEqual(len(all_faults), 2)

    def test_clear_faults_by_type(self):
        ce.inject(self.session_id, "stop_service", "nginx")
        ce.inject(self.session_id, "stop_service", "sshd")
        ce.inject(self.session_id, "raise_temp", "CRAC-1")
        cleared = ce.clear_faults(self.session_id, fault_type="stop_service")
        self.assertEqual(cleared, 2)
        active = ce.list_faults(self.session_id, active_only=True)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["fault_type"], "raise_temp")

    def test_clear_faults_with_no_filter_clears_all(self):
        ce.inject(self.session_id, "trip_pdu", "PDU-R01")
        ce.inject(self.session_id, "drop_nic", "srv-1")
        cleared = ce.clear_faults(self.session_id)
        self.assertEqual(cleared, 2)
        self.assertEqual(ce.list_faults(self.session_id, active_only=True), [])

    def test_drop_session_removes_faults(self):
        ce.inject(self.session_id, "trip_pdu", "PDU-R01")
        ce.drop_session(self.session_id)
        self.assertEqual(ce.list_faults(self.session_id), [])

    def test_faults_isolated_per_session(self):
        other = str(uuid.uuid4())
        ce.inject(self.session_id, "trip_pdu", "PDU-R01")
        self.assertEqual(ce.list_faults(other), [])
