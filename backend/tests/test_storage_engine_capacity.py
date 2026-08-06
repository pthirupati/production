"""Tests for storage-pool capacity enforcement and per-key grader feedback in
the NetApp ONTAP and Dell EMC Unisphere console simulators.

Covers the two behaviours the 2026-08 audit flagged as missing: volume
create/resize/expand must respect the aggregate/array free space they display
(and charge it on success), and the fail-closed graders must name the specific
unmet objective instead of a generic "still has unresolved issues" string.
"""

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import dellemc_engine as de
from apps.vmware_sim import netapp_engine as ne
from apps.vmware_sim import soc_engine as se


class NetAppCapacityTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "netapp-capacity-session"
        ne.drop_session(self.sid)
        self.addCleanup(ne.drop_session, self.sid)
        ne._ensure(self.sid, "")
        ne.apply_action(self.sid, "login", {"user": "admin"})

    def _aggr(self, name="aggr1"):
        state = ne.get_state(self.sid)["state"]
        return next(a for a in state["aggregates"] if a["name"] == name)

    def test_create_volume_rejected_when_larger_than_aggregate_free_space(self):
        # aggr1 ships 5000GB size / 1800GB used -> 3200GB free.
        res = ne.apply_action(self.sid, "create_volume", {
            "name": "vol_huge", "aggregate": "aggr1", "size_gb": 4000,
        })
        self.assertFalse(res["ok"])
        self.assertIn("3200GB free", res["error"])
        state = ne.get_state(self.sid)["state"]
        self.assertIsNone(ne._find_volume(state, "vol_huge"))
        self.assertEqual(self._aggr()["used_gb"], 1800)

    def test_create_volume_charges_the_aggregate(self):
        res = ne.apply_action(self.sid, "create_volume", {
            "name": "vol_app", "aggregate": "aggr1", "size_gb": 400,
        })
        self.assertTrue(res["ok"])
        self.assertEqual(self._aggr()["used_gb"], 2200)

    def test_create_volume_on_unknown_aggregate_is_rejected(self):
        res = ne.apply_action(self.sid, "create_volume", {
            "name": "vol_nowhere", "aggregate": "aggr99", "size_gb": 10,
        })
        self.assertFalse(res["ok"])
        self.assertIn("aggr99", res["error"])

    def test_free_space_does_not_drift_across_repeated_creates(self):
        # Two 1600GB volumes exactly consume aggr1's 3200GB of free space; a
        # third must fail, which only holds if used_gb is updated each time.
        for i in range(2):
            res = ne.apply_action(self.sid, "create_volume", {
                "name": f"vol_fill{i}", "aggregate": "aggr1", "size_gb": 1600,
            })
            self.assertTrue(res["ok"], res)
        self.assertEqual(self._aggr()["used_gb"], 5000)
        res = ne.apply_action(self.sid, "create_volume", {
            "name": "vol_overflow", "aggregate": "aggr1", "size_gb": 1,
        })
        self.assertFalse(res["ok"])
        self.assertIn("0GB free", res["error"])

    def test_resize_beyond_aggregate_free_space_is_rejected(self):
        res = ne.apply_action(self.sid, "resize_volume", {
            "name": "vol_web_data", "size_gb": 5000,
        })
        self.assertFalse(res["ok"])
        self.assertIn("free", res["error"])
        state = ne.get_state(self.sid)["state"]
        self.assertEqual(ne._find_volume(state, "vol_web_data")["size_gb"], 100)

    def test_resize_charges_only_the_delta(self):
        res = ne.apply_action(self.sid, "resize_volume", {
            "name": "vol_web_data", "size_gb": 300,
        })
        self.assertTrue(res["ok"], res)
        # 100GB -> 300GB is a 200GB delta, not a 300GB charge.
        self.assertEqual(self._aggr()["used_gb"], 2000)

    def test_shipped_resize_scenario_remains_solvable(self):
        """The 'grow vol_web_data' preset must still pass under enforcement."""
        ne.drop_session(self.sid)
        ne._ensure(self.sid, "netapp-resize-volume")
        ne.apply_action(self.sid, "login", {"user": "admin"})
        # No explicit size -> engine doubles 100GB to 200GB.
        res = ne.apply_action(self.sid, "resize_volume", {"name": "vol_web_data"})
        self.assertTrue(res["ok"], res)
        ok, message = ne.validate_netapp_lab(self.sid, "netapp-resize-volume")
        self.assertTrue(ok, message)


class DellEMCCapacityTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "dellemc-capacity-session"
        de.drop_session(self.sid)
        self.addCleanup(de.drop_session, self.sid)
        de._ensure(self.sid, "")
        de.apply_action(self.sid, "login", {"user": "admin"})

    def _array(self):
        return de.get_state(self.sid)["state"]["arrays"][0]

    def test_create_volume_beyond_array_capacity_is_rejected(self):
        # 500TB capacity / 180TB used -> 327680GB free.
        res = de.apply_action(self.sid, "create_volume", {"size_gb": 400000})
        self.assertFalse(res["ok"])
        self.assertIn("327680GB free", res["error"])
        self.assertEqual(self._array()["used_tb"], 180)
        self.assertEqual(len(de.get_state(self.sid)["state"]["volumes"]), 4)

    def test_create_volume_charges_the_array_pool(self):
        res = de.apply_action(self.sid, "create_volume", {"size_gb": 1024})
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._array()["used_tb"], 181)

    def test_expand_volume_beyond_capacity_is_rejected(self):
        res = de.apply_action(self.sid, "expand_volume", {
            "volume_id": "0001", "size_gb": 400000,
        })
        self.assertFalse(res["ok"])
        self.assertIn("free", res["error"])
        state = de.get_state(self.sid)["state"]
        self.assertEqual(de._find_volume(state, "0001")["size_gb"], 100)

    def test_expand_charges_only_the_delta(self):
        res = de.apply_action(self.sid, "expand_volume", {
            "volume_id": "0001", "size_gb": 100 + 2048,
        })
        self.assertTrue(res["ok"], res)
        self.assertEqual(self._array()["used_tb"], 182)

    def test_shipped_provisioning_scenario_remains_solvable(self):
        de.drop_session(self.sid)
        de._ensure(self.sid, "dellemc-provision-volume")
        de.apply_action(self.sid, "login", {"user": "admin"})
        res = de.apply_action(self.sid, "map_volume", {
            "volume_id": "0004", "storage_group": "SG_db_prod",
        })
        self.assertTrue(res["ok"], res)
        ok, message = de.validate_dellemc_lab(self.sid, "dellemc-provision-volume")
        self.assertTrue(ok, message)


class GraderMessageTests(SimpleTestCase):
    """The grader must name the unmet objective, not just say 'issues'."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_netapp_names_the_specific_objective(self):
        sid = "netapp-msg-session"
        ne.drop_session(sid)
        self.addCleanup(ne.drop_session, sid)
        ne._ensure(sid, "netapp-lun-iscsi")
        ok, message = ne.validate_netapp_lab(sid, "netapp-lun-iscsi")
        self.assertFalse(ok)
        self.assertIn("/vol/vol_db_data/lun0", message)
        self.assertNotIn("still has unresolved issues", message)

    def test_netapp_boolean_target_does_not_leak_true(self):
        sid = "netapp-bool-session"
        ne.drop_session(sid)
        self.addCleanup(ne.drop_session, sid)
        ne._ensure(sid, "netapp-volume-create")
        ok, message = ne.validate_netapp_lab(sid, "netapp-volume-create")
        self.assertFalse(ok)
        self.assertNotIn("True", message)
        self.assertIn("volume", message)

    def test_dellemc_names_the_specific_objective(self):
        sid = "dellemc-msg-session"
        de.drop_session(sid)
        self.addCleanup(de.drop_session, sid)
        de._ensure(sid, "dellemc-masking-view")
        ok, message = de.validate_dellemc_lab(sid, "dellemc-masking-view")
        self.assertFalse(ok)
        self.assertIn("SG_db_prod", message)
        self.assertNotIn("still has unresolved issues", message)

    def test_dellemc_boolean_target_does_not_leak_true(self):
        sid = "dellemc-bool-session"
        de.drop_session(sid)
        self.addCleanup(de.drop_session, sid)
        de._ensure(sid, "dellemc-host-register")
        ok, message = de.validate_dellemc_lab(sid, "dellemc-host-register")
        self.assertFalse(ok)
        self.assertNotIn("True", message)
        self.assertIn("host", message)

    def test_soc_lists_every_outstanding_objective(self):
        sid = "soc-msg-session"
        se.drop_session(sid)
        self.addCleanup(se.drop_session, sid)
        # The red-vs-blue preset seeds quarantine AND block-IP at once, so a
        # next(iter(...)) formatter would hide half the remaining work.
        se._ensure(sid, "soc-red-vs-blue")
        state = se._load(sid)["state"]
        self.assertEqual(len(state["broken"]), 2)
        ok, message = se.validate_soc_lab(sid, "soc-red-vs-blue")
        self.assertFalse(ok)
        self.assertIn("ws-finance-07", message)
        self.assertIn("198.51.100.23", message)
        self.assertNotIn("still has unresolved issues", message)

    def test_unknown_broken_key_still_fails_closed(self):
        sid = "netapp-unknown-key-session"
        ne.drop_session(sid)
        self.addCleanup(ne.drop_session, sid)
        entry = ne._ensure(sid, "")
        entry["state"]["broken"] = {"some_future_key": "widget"}
        ne._save(sid, entry)
        ok, message = ne.validate_netapp_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("some_future_key", message)
