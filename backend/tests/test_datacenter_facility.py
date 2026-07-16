"""Tests for the expanded physical datacenter facility model — rooms, the
power chain (utility -> ATS -> generator -> UPS -> floor PDU -> rack PDU),
cooling/ASHRAE, network switches, and per-server BMC — layered onto the
existing break/fix engine. Also covers ServerIdentity seeding from the
datacenter engine.
"""

import uuid

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import server_identity as si
from apps.vmware_sim import datacenter_engine as dc


class DatacenterFacilityTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    # ── Base state shape ────────────────────────────────────────────────
    def test_base_state_has_rooms(self):
        state = dc.get_state(self.session_id)["state"]
        self.assertTrue(state.get("rooms"))
        room_ids = {r["id"] for r in state["rooms"]}
        self.assertEqual(room_ids, {"data-hall-a", "mdf", "mechanical", "electrical"})
        hall = next(r for r in state["rooms"] if r["id"] == "data-hall-a")
        self.assertIn("R01", hall["racks"])
        mdf = next(r for r in state["rooms"] if r["id"] == "mdf")
        self.assertIn("R09", mdf["racks"])

    def test_base_state_has_power_chain_and_pue(self):
        state = dc.get_state(self.session_id)["state"]
        chain = state.get("power_chain")
        self.assertIsNotNone(chain)
        for key in ("utility", "ats", "generator", "ups", "floor_pdus", "rack_pdus"):
            self.assertIn(key, chain)
        self.assertTrue(chain["rack_pdus"])

        facility = state.get("facility", {})
        self.assertIn("pue", facility)
        self.assertIn("it_kw", facility)
        self.assertIn("total_kw", facility)
        self.assertGreaterEqual(facility["pue"], 1.0)
        self.assertLessEqual(facility["pue"], 2.0)
        self.assertAlmostEqual(facility["total_kw"] / facility["it_kw"], facility["pue"], places=2)

    def test_get_state_enriches_facility_with_rooms_and_current_room(self):
        state = dc.get_state(self.session_id)["state"]
        facility = state["facility"]
        self.assertEqual(facility["current_room"], "data-hall-a")
        self.assertTrue(facility["rooms"])
        self.assertIn("ashrae_ok", facility)

    def test_cooling_units_have_ashrae_flag_and_capacity(self):
        state = dc.get_state(self.session_id)["state"]
        self.assertTrue(state["cooling"])
        for crac in state["cooling"]:
            self.assertIn("ashrae_ok", crac)
            self.assertIn("capacity_kw", crac)
            self.assertIn("temp_c", crac)
            self.assertIn("humidity_pct", crac)

    def test_network_switches_have_ports(self):
        state = dc.get_state(self.session_id)["state"]
        network = state.get("network", {})
        self.assertTrue(network.get("switches"))
        sw = network["switches"][0]
        self.assertTrue(sw["ports"])
        self.assertIn("status", sw["ports"][0])
        self.assertIn("speed", sw["ports"][0])

    def test_server_has_bmc_and_role(self):
        state = dc.get_state(self.session_id)["state"]
        web = next(s for s in state["servers"] if s["hostname"] == "web-prod-01")
        self.assertEqual(web.get("role"), "esxi_host")
        self.assertIn("bmc", web)
        self.assertTrue(web["bmc"]["endpoint"].startswith("https://bmc-"))
        self.assertIn("sensors", web["bmc"])
        self.assertIn("inlet_c", web["bmc"]["sensors"])
        gpu = next(s for s in state["servers"] if s["hostname"] == "gpu-node-01")
        self.assertEqual(gpu.get("role"), "gpu_node")

    def test_existing_default_broken_server_unchanged(self):
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state["broken"].get("server"), "srv-r01-u14")
        self.assertEqual(state["broken"].get("component"), "power")

    # ── enter_room ───────────────────────────────────────────────────────
    def test_enter_room_switches_current_room(self):
        dc.get_state(self.session_id)
        result = dc.apply_action(self.session_id, "enter_room", {"room_id": "mdf"})
        self.assertTrue(result["ok"], result)
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state["current_room"], "mdf")
        self.assertEqual(state["facility"]["current_room"], "mdf")

    def test_enter_room_rejects_unknown_room(self):
        dc.get_state(self.session_id)
        result = dc.apply_action(self.session_id, "enter_room", {"room_id": "roof"})
        self.assertFalse(result["ok"])

    # ── BMC ──────────────────────────────────────────────────────────────
    def test_open_bmc_returns_bmc_and_selects_asset(self):
        dc.get_state(self.session_id)
        result = dc.apply_action(self.session_id, "open_bmc", {"asset_id": "srv-r02-u10"})
        self.assertTrue(result["ok"], result)
        self.assertIn("bmc", result)
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state["selected_asset"], "srv-r02-u10")

    def test_bmc_power_off_and_on_updates_server_and_bmc(self):
        dc.get_state(self.session_id)
        off = dc.apply_action(self.session_id, "bmc_power", {"asset_id": "srv-r01-u12", "mode": "off"})
        self.assertTrue(off["ok"], off)
        self.assertEqual(off["power_state"], "off")
        state = dc.get_state(self.session_id)["state"]
        srv = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        self.assertEqual(srv["power_state"], "off")
        self.assertEqual(srv["bmc"]["power"], "off")

        on = dc.apply_action(self.session_id, "bmc_power", {"asset_id": "srv-r01-u12", "mode": "on"})
        self.assertTrue(on["ok"], on)
        state = dc.get_state(self.session_id)["state"]
        srv = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        self.assertEqual(srv["power_state"], "on")
        self.assertEqual(srv["bmc"]["power"], "on")

    def test_bmc_power_rejects_unknown_mode(self):
        dc.get_state(self.session_id)
        result = dc.apply_action(self.session_id, "bmc_power", {"asset_id": "srv-r01-u12", "mode": "explode"})
        self.assertFalse(result["ok"])

    # ── Chaos: PDU breaker ───────────────────────────────────────────────
    def test_trip_and_restore_pdu_breaker(self):
        dc.get_state(self.session_id)
        tripped = dc.apply_action(self.session_id, "trip_pdu_breaker", {"pdu_id": "PDU-R01"})
        self.assertTrue(tripped["ok"], tripped)
        self.assertIn("srv-r01-u12", tripped["affected_servers"])

        state = dc.get_state(self.session_id)["state"]
        pdu = next(p for p in state["power_chain"]["rack_pdus"] if p["id"] == "PDU-R01")
        self.assertEqual(pdu["status"], "tripped")
        srv = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        self.assertEqual(srv["power_state"], "off")

        restored = dc.apply_action(self.session_id, "restore_pdu", {"pdu_id": "PDU-R01"})
        self.assertTrue(restored["ok"], restored)
        state = dc.get_state(self.session_id)["state"]
        pdu = next(p for p in state["power_chain"]["rack_pdus"] if p["id"] == "PDU-R01")
        self.assertEqual(pdu["status"], "online")

    def test_trip_pdu_breaker_unknown_pdu_fails(self):
        dc.get_state(self.session_id)
        result = dc.apply_action(self.session_id, "trip_pdu_breaker", {"pdu_id": "PDU-NOPE"})
        self.assertFalse(result["ok"])

    # ── Cooling failure preset + restore_crac ───────────────────────────
    def test_cooling_failure_preset_breaks_ashrae(self):
        sid = str(uuid.uuid4())
        state = dc.get_state(sid, "datacenter-cooling-failure")["state"]
        self.assertEqual(state["broken"].get("component"), "cooling")
        self.assertFalse(state["facility"]["ashrae_ok"])

        restore = dc.apply_action(sid, "restore_crac", {"crac_id": "CRAC-1"})
        self.assertTrue(restore["ok"], restore)
        ok, _ = dc.validate_datacenter_lab(sid, "datacenter-cooling-failure")
        self.assertTrue(ok)

    # ── ServerIdentity sync ──────────────────────────────────────────────
    def test_server_identity_seeded_after_get_state(self):
        si.drop_session(self.session_id)
        dc.get_state(self.session_id)
        identity = si.get_server(self.session_id, "srv-r01-u12")
        self.assertIsNotNone(identity)
        self.assertEqual(identity["hostname"], "web-prod-01")
        self.assertIsNotNone(identity.get("physical_location"))
        self.assertEqual(identity["physical_location"]["room"], "data-hall-a")
        self.assertIsNotNone(identity.get("bmc"))

    def test_server_identity_updates_on_bmc_power(self):
        dc.get_state(self.session_id)
        dc.apply_action(self.session_id, "bmc_power", {"asset_id": "srv-r02-u10", "mode": "off"})
        identity = si.get_server(self.session_id, "srv-r02-u10")
        self.assertEqual(identity["power"], "off")

    def test_server_identity_updates_on_replace(self):
        sid = str(uuid.uuid4())
        dc.get_state(sid, "datacenter-power-replace")
        dc.apply_action(sid, "replace_power", {"asset_id": "srv-r01-u14"})
        identity = si.get_server(sid, "srv-r01-u14")
        self.assertIsNotNone(identity)

    # ── Existing behaviour preserved ──────────────────────────────────────
    def test_replace_power_supply_still_clears_broken(self):
        sid = str(uuid.uuid4())
        dc.get_state(sid, "datacenter-power-replace")
        dc.apply_action(sid, "login", {})
        dc.apply_action(sid, "select_asset", {"asset_id": "srv-r01-u14"})
        dc.apply_action(sid, "replace_nic", {"asset_id": "srv-r01-u14"})
        ok, _ = dc.validate_datacenter_lab(sid, "datacenter-power-replace")
        self.assertFalse(ok)
        result = dc.apply_action(sid, "replace_power", {"asset_id": "srv-r01-u14"})
        self.assertTrue(result["ok"], result)
        dc.apply_action(sid, "power_cycle", {"asset_id": "srv-r01-u14"})
        ok, msg = dc.validate_datacenter_lab(sid, "datacenter-power-replace")
        self.assertTrue(ok, msg)
