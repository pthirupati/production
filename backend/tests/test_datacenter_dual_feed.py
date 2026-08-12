"""D14 dual-feed A/B + overcurrent breaker physics."""

import uuid

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import datacenter_engine as dc


LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "dc-dual-feed-tests",
    }
}


@override_settings(CACHES=LOCMEM)
class DualFeedBreakerTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.sid = str(uuid.uuid4())

    def tearDown(self):
        cache.clear()

    def test_rack_has_a_and_b_feeds(self):
        state = dc.get_state(self.sid)["state"]
        feeds = {(p["rack"], p.get("feed")) for p in state["power_chain"]["rack_pdus"]}
        self.assertIn(("R01", "A"), feeds)
        self.assertIn(("R01", "B"), feeds)

    def test_single_corded_trip_still_kills_servers(self):
        dc.get_state(self.sid)
        res = dc.apply_action(self.sid, "trip_pdu_breaker", {"pdu_id": "PDU-R01"})
        self.assertTrue(res["ok"], res)
        self.assertIn("srv-r01-u12", res["affected_servers"])
        state = dc.get_state(self.sid)["state"]
        srv = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        self.assertEqual(srv["power_state"], "off")

    def test_dual_corded_survives_a_feed_loss(self):
        dc.get_state(self.sid)
        dc.apply_action(self.sid, "set_server_power_feeds", {
            "asset_id": "srv-r01-u12", "power_feeds": ["A", "B"],
        })
        res = dc.apply_action(self.sid, "trip_pdu_breaker", {"pdu_id": "PDU-R01"})
        self.assertTrue(res["ok"], res)
        self.assertNotIn("srv-r01-u12", res.get("affected_servers") or [])
        state = dc.get_state(self.sid)["state"]
        srv = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        self.assertEqual(srv["power_state"], "on")
        b = next(p for p in state["power_chain"]["rack_pdus"] if p["id"] == "PDU-R01-B")
        self.assertGreater(b["load_kw"], 0)

    def test_overcurrent_auto_trips(self):
        state = dc.get_state(self.sid)["state"]
        pdu = next(p for p in state["power_chain"]["rack_pdus"] if p["id"] == "PDU-R01")
        pdu["rating_kw"] = 0.01  # force overcurrent on next recompute
        entry = dc._load(self.sid)
        entry["state"] = state
        dc._save(self.sid, entry)
        dc.apply_action(self.sid, "bmc_power", {"asset_id": "srv-r01-u12", "mode": "on"})
        state = dc.get_state(self.sid)["state"]
        pdu = next(p for p in state["power_chain"]["rack_pdus"] if p["id"] == "PDU-R01")
        self.assertEqual(pdu["breaker"], "open")
        self.assertEqual(pdu.get("trip_reason"), "overcurrent")
