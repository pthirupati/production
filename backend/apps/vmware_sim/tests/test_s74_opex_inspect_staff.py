"""Session 74: opex ledger, inspect/energize gate, staff dispatch."""

from django.test import SimpleTestCase

from apps.vmware_sim.datacenter_economy_ops import (
    buy_hardware,
    dispatch_staff,
    energize_floor,
    ensure_ledger,
    hire_staff,
    inspect_before_energize,
    tick_fatigue,
    tick_opex,
)
from apps.vmware_sim.datacenter_physics_ops import build_ops_ticket


class OpexLedgerTests(SimpleTestCase):
    def test_buy_and_tick_opex_scales_with_pue(self):
        state = {"facility": {"it_kw": 10.0, "pue": 1.2}, "staff": []}
        ensure_ledger(state)
        cash0 = state["ledger"]["cash"]
        low = tick_opex(state, hours=1)
        self.assertTrue(low["ok"])
        opex_low = low["opex"]["usd"]

        state2 = {"facility": {"it_kw": 10.0, "pue": 2.0}, "staff": [], "ledger": {"cash": cash0, "capex_usd": 0, "opex_usd": 0, "power_kwh": 0, "history": []}}
        high = tick_opex(state2, hours=1)
        self.assertGreater(high["opex"]["power_usd"], low["opex"]["power_usd"])
        self.assertGreater(high["opex"]["usd"], opex_low)

        bought = buy_hardware(state, sku="server_1u", qty=1)
        self.assertTrue(bought["ok"])
        self.assertLess(state["ledger"]["cash"], cash0 - opex_low)

        broke = {"ledger": {"cash": 10.0, "capex_usd": 0, "opex_usd": 0, "history": []}}
        reject = buy_hardware(broke, sku="gpu", qty=1)
        self.assertFalse(reject["ok"])


class InspectEnergizeTests(SimpleTestCase):
    def test_clean_hall_energizes_dirty_blocks(self):
        clean = {
            "racks": [{"id": "R01", "grid_z": 0, "aisle": "hot_cold", "physics": {"floor_loading_ok": True}}],
            "cooling": [{"id": "CRAC-1", "status": "running", "ashrae_ok": True}],
            "containment": {"doors_open": False},
        }
        report = inspect_before_energize(clean)
        self.assertTrue(report["ok"], report)
        result = energize_floor(clean)
        self.assertTrue(result["ok"])
        self.assertTrue(clean.get("floor_energized"))

        dirty = {
            "racks": [{"id": "R02", "grid_z": 1, "aisle": "hot_cold", "physics": {"floor_loading_ok": True}}],
            "cooling": [{"id": "CRAC-1", "status": "running", "ashrae_ok": False}],
            "containment": {"doors_open": True},
        }
        blocked = energize_floor(dirty)
        self.assertFalse(blocked["ok"])
        self.assertFalse(dirty.get("floor_energized"))
        codes = {v["code"] for v in blocked["inspection"]["violations"]}
        self.assertIn("aisle_facing", codes)
        self.assertIn("ashrae", codes)
        self.assertIn("containment", codes)


class StaffDispatchTests(SimpleTestCase):
    def test_hire_dispatch_and_fatigue_gate(self):
        state = {"tickets": [], "staff": []}
        ticket = build_ops_ticket(
            vendor="Dell", ticket_type="incident", asset_id="a1",
            hostname="h", component="psu", summary="PSU down", priority="medium",
        )
        state["tickets"] = [ticket]
        hired = hire_staff(state, name="Alex", role="field-tech", shift="day")
        self.assertTrue(hired["ok"])
        sid = hired["staff"]["id"]

        bad = dispatch_staff(state, ticket_id=ticket["id"], staff_id=sid)
        # field-tech has psu skill — should succeed
        self.assertTrue(bad["ok"], bad)
        self.assertEqual(ticket["assignee"], "Alex")

        net = hire_staff(state, name="Sam", role="network-eng", shift="day")
        mismatch = dispatch_staff(state, ticket_id=ticket["id"], staff_id=net["staff"]["id"])
        self.assertFalse(mismatch["ok"])

        person = hired["staff"]
        person["fatigue"] = 90
        person["assigned_ticket"] = None
        tired = dispatch_staff(state, ticket_id=ticket["id"], staff_id=sid)
        self.assertFalse(tired["ok"])

        person["fatigue"] = 10
        person["assigned_ticket"] = ticket["id"]
        tick_fatigue(state, hours=2)
        self.assertGreater(person["fatigue"], 10)
