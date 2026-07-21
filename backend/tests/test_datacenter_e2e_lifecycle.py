"""End-to-end lifecycle smoke for the datacenter digital twin (Phases 1–12).

Walks login → rooms → BMC → DR → CAB freeze → burn-in → evidence →
live_tick → journal replay without requiring a browser.
"""

import uuid

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import datacenter_engine as dc


class DatacenterE2ELifecycleTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.sid = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    def _ok(self, action, payload=None):
        res = dc.apply_action(self.sid, action, payload or {})
        self.assertTrue(res.get("ok"), f"{action} failed: {res}")
        return res

    def test_full_lifecycle(self):
        state = dc.get_state(self.sid)["state"]
        self.assertTrue(state.get("rooms"))
        self.assertTrue(state.get("change_calendar"))
        self.assertTrue(state.get("burnin"))
        self.assertTrue(state.get("exporters"))

        self._ok("login", {"user": "tech"})
        self._ok("enter_room", {"room_id": "data-hall-a"})
        broken = state.get("broken") or {}
        asset = broken.get("server") or "srv-r01-u14"
        self._ok("select_asset", {"asset_id": asset})
        self._ok("open_bmc", {"asset_id": asset})
        self._ok("bmc_power", {"asset_id": asset, "mode": "cycle"})

        self._ok("enter_room", {"room_id": "noc"})
        self._ok("refresh_monitoring")
        tick = self._ok("live_tick")
        self.assertIn("environmental", tick)
        self.assertGreaterEqual((tick["environmental"] or {}).get("tick") or 0, 1)

        self._ok("change_ops", {"op": "enable_freeze", "reason": "E2E freeze"})
        blocked = dc.apply_action(self.sid, "power_cycle", {"asset_id": asset})
        self.assertFalse(blocked.get("ok"))
        self.assertIn("freeze", (blocked.get("error") or "").lower())
        self._ok("change_ops", {"op": "disable_freeze"})

        self._ok("dr_ops", {"op": "utility_fail"})
        self._ok("dr_ops", {"op": "start_generator"})
        self._ok("access_ops", {"op": "badge_in", "badge_id": "BADGE-1001"})
        self._ok("automation_ops", {"op": "run", "runbook_id": "rb-dr-tabletop"})
        self._ok("generate_ops_report")

        state = dc.get_state(self.sid)["state"]
        machines = (state.get("burnin") or {}).get("machines") or []
        mid = (machines[0] or {}).get("id") if machines else None
        self.assertTrue(mid)
        self._ok("burnin_ops", {"op": "attach_load_bank", "machine_id": mid})
        self._ok("burnin_ops", {"op": "soak", "machine_id": mid})

        self._ok("exporter_ops", {"op": "snmp_walk"})
        self._ok("generate_evidence")
        self._ok("environmental_ops", {"op": "normalize"})
        self._ok("containment_ops", {"op": "toggle_door", "aisle_id": "CA-A"})
        self._ok("cable_plant_ops", {"op": "add_fill", "tray_id": "TRAY-EW-1", "delta": 5})

        # Journal a twin action then replay (pulse_buses does not require cover)
        self._ok("motherboard_ops", {"asset_id": asset, "op": "pulse_buses"})
        replay = self._ok("replay_twin_journal")
        self.assertGreaterEqual(replay.get("replayed") or 0, 1)

        final = dc.get_state(self.sid)["state"]
        self.assertTrue(final.get("sustainability"))
        self.assertTrue(final.get("evidence_pack") or final.get("doc_library"))
        mon = final.get("monitoring") or {}
        self.assertTrue(mon.get("series") is not None or mon.get("exporters"))
