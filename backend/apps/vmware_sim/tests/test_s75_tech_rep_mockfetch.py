"""Session 75: tech tree, reputation/hall, mockFetch prelude."""

from django.test import SimpleTestCase

from apps.labs.api_client_mock import build_mock_fetch_prelude, default_collection
from apps.labs.code_exec import _build_js_harness
from apps.vmware_sim.datacenter_economy_ops import (
    apply_upgrade,
    ensure_ledger,
    ensure_reputation,
    list_upgrades,
    tick_reputation,
    unlock_second_hall,
)


class TechTreeTests(SimpleTestCase):
    def test_apply_upgrade_prereq_and_pue(self):
        state = {"facility": {"pue": 1.5}}
        ensure_ledger(state)
        blocked = apply_upgrade(state, "liquid_cooling")
        self.assertFalse(blocked["ok"])

        ok = apply_upgrade(state, "high_density")
        self.assertTrue(ok["ok"], ok)
        self.assertIn("high_density", state["upgrades"]["owned"])

        liquid = apply_upgrade(state, "liquid_cooling")
        self.assertTrue(liquid["ok"], liquid)
        self.assertLess(state["facility"]["pue"], 1.5)

        catalog = list_upgrades(state)
        owned = {u["id"] for u in catalog if u["owned"]}
        self.assertIn("liquid_cooling", owned)

        broke = {"facility": {"pue": 1.4}, "ledger": {"cash": 100.0, "capex_usd": 0, "opex_usd": 0, "history": []}}
        reject = apply_upgrade(broke, "free_cooling")
        self.assertFalse(reject["ok"])


class ReputationHallTests(SimpleTestCase):
    def test_breach_lowers_rep_and_hall_gate(self):
        state = {
            "contracts": [{"status": "active", "sla_breached": True}],
            "tickets": [],
            "ledger": {"cash": 100_000.0, "capex_usd": 0, "opex_usd": 0, "history": []},
        }
        ensure_reputation(state)
        state["reputation"]["score"] = 50
        tick_reputation(state)
        self.assertLess(state["reputation"]["score"], 50)

        low = unlock_second_hall(state)
        self.assertFalse(low["ok"])

        state["reputation"]["score"] = 80
        state["contracts"] = []
        unlocked = unlock_second_hall(state)
        self.assertTrue(unlocked["ok"], unlocked)
        self.assertIn("data-hall-b", state["reputation"]["halls"])
        again = unlock_second_hall(state)
        self.assertFalse(again["ok"])


class MockFetchPreludeTests(SimpleTestCase):
    def test_prelude_and_harness_inject(self):
        prelude = build_mock_fetch_prelude()
        self.assertIn("mockFetch", prelude)
        self.assertIn("globalThis.fetch", prelude)
        self.assertIn("/health", prelude)
        self.assertTrue(default_collection())

        harness = _build_js_harness(
            "async function ping(){ const r = await fetch('/health'); return (await r.json()).status }",
            [{"name": "t", "code": "assert(true)", "hidden": False}],
            api_client={},
        )
        self.assertIn("mockFetch", harness)
        self.assertIn("__FIXITLAB_MOCK_ROUTES__", harness)

        plain = _build_js_harness("x=1", [{"name": "t", "code": "assert(true)", "hidden": False}])
        self.assertNotIn("mockFetch", plain)
