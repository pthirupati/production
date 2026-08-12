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
        self.assertIn("data-hall-a", room_ids)
        self.assertIn("mdf", room_ids)
        self.assertIn("mechanical", room_ids)
        self.assertIn("electrical", room_ids)
        self.assertIn("campus", room_ids)
        self.assertIn("generator-yard", room_ids)
        self.assertGreaterEqual(len(room_ids), 15)
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

    def test_enter_reception_repair_warehouse_walkable_stubs(self):
        state = dc.get_state(self.session_id)["state"]
        room_ids = {r["id"] for r in state.get("rooms") or []}
        self.assertIn("reception", room_ids)
        self.assertIn("repair", room_ids)
        self.assertIn("warehouse", room_ids)
        for rid in ("reception", "repair", "warehouse"):
            result = dc.apply_action(self.session_id, "enter_room", {"room_id": rid})
            self.assertTrue(result["ok"], result)
            cur = dc.get_state(self.session_id)["state"]
            self.assertEqual(cur["current_room"], rid)
            room = next(r for r in cur["rooms"] if r["id"] == rid)
            self.assertTrue(room.get("exits"), f"{rid} should list adjacent exits")

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

    # ── Digital twin: motherboard / RAID / BIOS / BMC ─────────────────────
    def test_server_has_motherboard_raid_bios(self):
        state = dc.get_state(self.session_id)["state"]
        web = next(s for s in state["servers"] if s["hostname"] == "web-prod-01")
        self.assertIn("motherboard", web)
        self.assertTrue(web["motherboard"]["cpu_sockets"])
        self.assertTrue(web["motherboard"]["dimm_slots"])
        self.assertIn("raid", web)
        self.assertTrue(web["raid"]["physical_disks"])
        self.assertIn("bios", web)
        self.assertEqual(web["bios"]["mode"], "UEFI")
        self.assertTrue(web["bmc"].get("product"))
        self.assertIn("Redfish", web["bmc"].get("protocols_enabled") or [])
        self.assertTrue(state.get("campus", {}).get("generators"))

    def test_raid_fail_and_rebuild(self):
        dc.get_state(self.session_id)
        r = dc.apply_action(self.session_id, "raid_fail_disk", {"asset_id": "srv-r01-u12", "disk_id": "PD0"})
        self.assertTrue(r["ok"], r)
        state = dc.get_state(self.session_id)["state"]
        web = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        pd0 = next(d for d in web["raid"]["physical_disks"] if d["id"] == "PD0")
        self.assertEqual(pd0["status"], "failed")
        r2 = dc.apply_action(self.session_id, "raid_rebuild", {"asset_id": "srv-r01-u12", "vd_id": "VD0"})
        self.assertTrue(r2["ok"], r2)
        state = dc.get_state(self.session_id)["state"]
        web = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        vd0 = next(v for v in web["raid"]["virtual_disks"] if v["id"] == "VD0")
        self.assertEqual(vd0["status"], "rebuilding")
        self.assertGreater(int(vd0.get("rebuild_pct") or 0), 0)
        self.assertLess(int(vd0.get("rebuild_pct") or 0), 100)

        # Progressive advance via live tick / explicit advance
        pct_before = int(vd0["rebuild_pct"])
        r3 = dc.apply_action(self.session_id, "raid_advance_rebuild", {"asset_id": "srv-r01-u12"})
        self.assertTrue(r3["ok"], r3)
        state = dc.get_state(self.session_id)["state"]
        web = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
        vd0 = next(v for v in web["raid"]["virtual_disks"] if v["id"] == "VD0")
        self.assertGreaterEqual(int(vd0["rebuild_pct"]), pct_before)
        self.assertIn(vd0["status"], ("rebuilding", "optimal"))

        # Drive to completion
        for _ in range(12):
            dc.apply_action(self.session_id, "raid_advance_rebuild", {"asset_id": "srv-r01-u12"})
            state = dc.get_state(self.session_id)["state"]
            web = next(s for s in state["servers"] if s["id"] == "srv-r01-u12")
            vd0 = next(v for v in web["raid"]["virtual_disks"] if v["id"] == "VD0")
            if vd0["status"] == "optimal":
                break
        self.assertEqual(vd0["status"], "optimal")
        self.assertEqual(int(vd0.get("rebuild_pct") or 0), 100)

    def test_bios_setup_and_bmc_virtual_media(self):
        dc.get_state(self.session_id)
        r = dc.apply_action(self.session_id, "bios_enter_setup", {"asset_id": "srv-r01-u12"})
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["bios"]["setup_open"])
        r2 = dc.apply_action(
            self.session_id, "bmc_mount_virtual_media",
            {"asset_id": "srv-r01-u12", "image": "ubuntu-22.04.iso"},
        )
        self.assertTrue(r2["ok"], r2)
        self.assertTrue(r2["bmc"]["virtual_media"]["mounted"])
        self.assertEqual(r2["bmc"]["virtual_media"]["image"], "ubuntu-22.04.iso")


class ThermalLoadCouplingTests(SimpleTestCase):
    """Load must actually drive power and temperature (audit L2263).

    Before this coupling every rack PDU was a hardcoded 4.2 kW and sensor
    drift was a sine wave around a constant, so a cooling failure could not
    make the hall hot and PUE never moved.
    """

    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    def test_rack_load_varies_by_what_is_racked(self):
        state = dc.get_state(self.session_id)["state"]
        # Dual-feed lists A then B (B often 0); take max so B does not zero the rack.
        pdus = {}
        for p in state["power_chain"]["rack_pdus"]:
            rack = p["rack"]
            pdus[rack] = max(pdus.get(rack, 0.0), float(p.get("load_kw") or 0))
        # R03 holds the GPU node; R06 holds a single cache node.
        self.assertGreater(pdus["R03"], pdus["R06"])
        # Empty data-hall racks draw nothing at all.
        self.assertEqual(pdus["R07"], 0.0)
        self.assertGreater(len({round(v, 2) for v in pdus.values()}), 1)

    def test_powering_off_a_server_lowers_it_load(self):
        state = dc.get_state(self.session_id)["state"]
        before = state["facility"]["it_kw"]
        r = dc.apply_action(self.session_id, "bmc_power", {"asset_id": "srv-r03-u08", "mode": "off"})
        self.assertTrue(r["ok"], r)
        after = dc.get_state(self.session_id)["state"]["facility"]["it_kw"]
        self.assertLess(after, before)

    def test_pue_stays_in_band_and_cooling_tracks_load(self):
        state = dc.get_state(self.session_id)["state"]
        facility = state["facility"]
        self.assertGreaterEqual(facility["pue"], 1.0)
        self.assertLessEqual(facility["pue"], 2.0)
        self.assertGreater(facility["cooling_kw"], 0)

    def test_cooling_loss_raises_hall_temperature(self):
        from apps.vmware_sim.datacenter_facility_ops import thermal_baseline, tick_live

        state = dc.get_state(self.session_id)["state"]
        baseline = thermal_baseline(state)
        self.assertEqual(baseline["deficit_kw"], 0.0)

        # Kill all cooling: every IT kW is now unrejected heat.
        for c in state["cooling"]:
            c["status"] = "off"
        hot = thermal_baseline(state)
        self.assertGreater(hot["deficit_kw"], 0.0)
        self.assertGreater(hot["cold_aisle_c"], baseline["cold_aisle_c"] + 5)

        # The sensors must follow, and an inlet over ASHRAE A1 must alarm.
        env = tick_live(state)
        cold = next(s for s in env["sensors"] if s["location"] == "Cold aisle A")
        self.assertGreater(cold["temp_c"], 32.0)
        self.assertEqual(cold["status"], "alarm")

    def test_alarmed_sensor_keeps_escalating(self):
        """A hotspot in alarm must not freeze at the value that tripped it."""
        from apps.vmware_sim.datacenter_facility_ops import tick_live

        state = dc.get_state(self.session_id)["state"]
        for c in state["cooling"]:
            c["status"] = "off"
        env = tick_live(state)
        cold = next(s for s in env["sensors"] if s["location"] == "Cold aisle A")
        self.assertEqual(cold["status"], "alarm")
        first = cold["temp_c"]

        # Rack more load while the sensor is already alarming.
        for srv in state["servers"]:
            srv["power_state"] = "on"
        dc._recompute_facility(state)
        env = tick_live(state)
        cold = next(s for s in env["sensors"] if s["location"] == "Cold aisle A")
        self.assertGreater(cold["temp_c"], first)

    def test_bmc_inlet_follows_the_hall_not_its_own_last_value(self):
        from apps.vmware_sim.datacenter_facility_ops import tick_live

        state = dc.get_state(self.session_id)["state"]
        tick_live(state)
        srv = next(s for s in state["servers"] if s["power_state"] == "on")
        cool_inlet = srv["bmc"]["sensors"]["inlet_c"]

        for c in state["cooling"]:
            c["status"] = "off"
        tick_live(state)
        srv = next(s for s in state["servers"] if s["id"] == srv["id"])
        self.assertGreater(srv["bmc"]["sensors"]["inlet_c"], cool_inlet + 5)
        # Fans ramp against the hot inlet.
        self.assertGreater(srv["bmc"]["sensors"]["fans_rpm"], 7300)


class CampusPlantOpsTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    def test_campus_has_dock_battery_and_ops(self):
        state = dc.get_state(self.session_id)["state"]
        campus = state["campus"]
        self.assertTrue(campus.get("loading_dock", {}).get("queue"))
        self.assertTrue(campus.get("battery_strings"))
        self.assertIn("chillers", campus)

        r = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "receive_dock"})
        self.assertTrue(r["ok"], r)
        dock = dc.get_state(self.session_id)["state"]["campus"]["loading_dock"]
        self.assertGreaterEqual(int(dock.get("received_today") or 0), 1)
        self.assertTrue(any(q.get("status") == "received" for q in dock.get("queue") or []))

        r2 = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "start_chiller", "chiller_id": "CH-2"})
        self.assertTrue(r2["ok"], r2)
        chillers = {c["id"]: c for c in dc.get_state(self.session_id)["state"]["campus"]["chillers"]}
        self.assertEqual(chillers["CH-2"]["status"], "running")

        r3 = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "sync_battery"})
        self.assertTrue(r3["ok"], r3)
        strings = dc.get_state(self.session_id)["state"]["campus"]["battery_strings"]
        self.assertTrue(all("soc_pct" in s for s in strings))

        before = int(dc.get_state(self.session_id)["state"]["campus"]["parking"]["occupied"])
        r4 = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "parking_in"})
        self.assertTrue(r4["ok"], r4)
        after = int(dc.get_state(self.session_id)["state"]["campus"]["parking"]["occupied"])
        self.assertEqual(after, before + 1)

    def test_spares_issue_restock_and_dock_restock(self):
        state = dc.get_state(self.session_id)["state"]
        bins = {b["id"]: b for b in state["campus"]["spares"]["bins"]}
        self.assertIn("BIN-PSU", bins)
        before = int(bins["BIN-PSU"]["qty"])

        r = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "issue_spare", "bin_id": "BIN-PSU"})
        self.assertTrue(r["ok"], r)
        after_issue = int(
            next(b["qty"] for b in dc.get_state(self.session_id)["state"]["campus"]["spares"]["bins"] if b["id"] == "BIN-PSU")
        )
        self.assertEqual(after_issue, before - 1)

        r2 = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "restock_spare", "bin_id": "BIN-PSU"})
        self.assertTrue(r2["ok"], r2)

        dc.apply_action(self.session_id, "campus_plant_ops", {
            "op": "arrive_dock", "contents": "R760 PSU FRU spare", "carrier": "Dell",
        })
        qty_before = int(
            next(b["qty"] for b in dc.get_state(self.session_id)["state"]["campus"]["spares"]["bins"] if b["id"] == "BIN-PSU")
        )
        r3 = dc.apply_action(self.session_id, "campus_plant_ops", {"op": "receive_dock"})
        self.assertTrue(r3["ok"], r3)
        qty_after = int(
            next(b["qty"] for b in dc.get_state(self.session_id)["state"]["campus"]["spares"]["bins"] if b["id"] == "BIN-PSU")
        )
        self.assertEqual(qty_after, qty_before + 1)

    def test_rma_part_is_unavailable_until_lead_time_elapses(self):
        """An RMA part must not be receivable the instant it is ordered (L2269)."""
        dc.get_state(self.session_id)
        opened = dc.apply_action(self.session_id, "ops_ticket", {
            "asset_id": "srv-r01-u14", "component": "power", "summary": "PSU dead",
        })
        self.assertTrue(opened["ok"], opened)
        tid = opened["ticket"]["id"]
        shipped = dc.apply_action(self.session_id, "ops_ticket", {
            "op": "advance", "ticket_id": tid, "advance": "ship_rma",
            "part": "PSU-R760", "eta_days": 2,
        })
        self.assertTrue(shipped["ok"], shipped)

        state = dc.get_state(self.session_id)["state"]
        asn = next(q for q in state["campus"]["loading_dock"]["queue"] if q["id"].startswith("ASN-RMA-"))
        self.assertEqual(asn["status"], "inbound")
        self.assertGreater(asn["ticks_remaining"], 0)

        # The part is genuinely not here yet.
        early = dc.apply_action(self.session_id, "campus_plant_ops", {
            "op": "receive_dock", "asn_id": asn["id"],
        })
        self.assertFalse(early["ok"])
        self.assertIn("transit", early["error"])

        # Ticking the sim clock brings it in.
        for _ in range(asn["ticks_remaining"]):
            dc.apply_action(self.session_id, "live_tick", {})
        state = dc.get_state(self.session_id)["state"]
        asn = next(q for q in state["campus"]["loading_dock"]["queue"] if q["id"] == asn["id"])
        self.assertEqual(asn["status"], "at_bay")
        late = dc.apply_action(self.session_id, "campus_plant_ops", {
            "op": "receive_dock", "asn_id": asn["id"],
        })
        self.assertTrue(late["ok"], late)

    def test_expedite_shortens_lead_time(self):
        dc.get_state(self.session_id)
        opened = dc.apply_action(self.session_id, "ops_ticket", {
            "asset_id": "srv-r01-u14", "component": "power", "summary": "PSU dead",
        })
        dc.apply_action(self.session_id, "ops_ticket", {
            "op": "advance", "ticket_id": opened["ticket"]["id"],
            "advance": "ship_rma", "eta_days": 3,
        })
        state = dc.get_state(self.session_id)["state"]
        asn = next(q for q in state["campus"]["loading_dock"]["queue"] if q["id"].startswith("ASN-RMA-"))
        before = asn["ticks_remaining"]

        r = dc.apply_action(self.session_id, "campus_plant_ops", {
            "op": "expedite_asn", "asn_id": asn["id"],
        })
        self.assertTrue(r["ok"], r)
        state = dc.get_state(self.session_id)["state"]
        asn = next(q for q in state["campus"]["loading_dock"]["queue"] if q["id"] == asn["id"])
        self.assertLess(asn["ticks_remaining"], before)

    def test_maintenance_window_flags_a_hot_rack(self):
        """Scheduling onto a near-breaker rack must say so (audit L2267)."""
        dc.get_state(self.session_id)
        # srv-r03-u08 is the GPU node — its rack runs closest to the breaker.
        opened = dc.apply_action(self.session_id, "ops_ticket", {
            "asset_id": "srv-r03-u08", "component": "gpu", "summary": "GPU fault",
        })
        r = dc.apply_action(self.session_id, "ops_ticket", {
            "op": "advance", "ticket_id": opened["ticket"]["id"],
            "advance": "schedule_visit", "duration_min": 90,
        })
        self.assertTrue(r["ok"], r)
        window = r["ticket"]["maintenance_window"]
        self.assertEqual(window["rack"], "R03")
        self.assertGreater(window["rack_load_pct"], 70)
        self.assertIn(window["load_verdict"], ("caution", "conflict"))
        self.assertTrue(window["load_reason"])

    def test_maintenance_window_clear_on_quiet_rack(self):
        dc.get_state(self.session_id)
        opened = dc.apply_action(self.session_id, "ops_ticket", {
            "asset_id": "srv-r06-u08", "component": "nic", "summary": "NIC flap",
        })
        r = dc.apply_action(self.session_id, "ops_ticket", {
            "op": "advance", "ticket_id": opened["ticket"]["id"], "advance": "schedule_visit",
        })
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["ticket"]["maintenance_window"]["load_verdict"], "clear")

    def test_window_load_advice_is_advisory_not_blocking(self):
        """Load conflicts must never silently make ops actions unavailable."""
        from apps.vmware_sim.datacenter_phase12 import change_freeze_blocks, window_load_advice

        state = dc.get_state(self.session_id)["state"]
        advice = {a["rack"]: a for a in window_load_advice(state)}
        self.assertIn(advice["R03"]["verdict"], ("caution", "conflict"))
        # No freeze is active, so nothing is blocked regardless of load.
        self.assertIsNone(change_freeze_blocks(state, "replace_power"))
        r = dc.apply_action(self.session_id, "bmc_power", {"asset_id": "srv-r03-u08", "mode": "off"})
        self.assertTrue(r["ok"], r)

    def test_legacy_asn_without_lead_time_still_receivable(self):
        """Seeded ASNs predate lead times; existing FRU labs must not break."""
        dc.get_state(self.session_id)
        r = dc.apply_action(self.session_id, "campus_plant_ops", {
            "op": "receive_dock", "asn_id": "ASN-1048",
        })
        self.assertTrue(r["ok"], r)

    def test_idf_patch_and_uplink(self):
        state = dc.get_state(self.session_id)["state"]
        self.assertTrue(state.get("optical", {}).get("idf"))
        populated = int(state["optical"]["idf"]["patch_panels"][0]["populated"])
        r = dc.apply_action(self.session_id, "optical_ops", {"op": "idf_patch", "delta": 1})
        self.assertTrue(r["ok"], r)
        after = int(dc.get_state(self.session_id)["state"]["optical"]["idf"]["patch_panels"][0]["populated"])
        self.assertEqual(after, populated + 1)
        r2 = dc.apply_action(self.session_id, "optical_ops", {"op": "idf_uplink_toggle"})
        self.assertTrue(r2["ok"], r2)
        ul = dc.get_state(self.session_id)["state"]["optical"]["idf"]["uplinks"][0]
        self.assertEqual(ul["status"], "down")


class PhysicalSecurityTests(SimpleTestCase):
    """Tailgating, propped doors, and unescorted visitors (audit L2272)."""

    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    def test_tailgate_alarm_does_not_evict_an_open_hardware_fault(self):
        """`broken` is a single-fault slot shared with hardware chaos."""
        state = dc.get_state(self.session_id)["state"]
        # The base scenario ships with a failed PSU a lab may be grading on.
        self.assertEqual(state["broken"]["component"], "power")

        r = dc.apply_action(self.session_id, "access_ops", {"op": "tailgate_alarm"})
        self.assertTrue(r["ok"], r)
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state["broken"]["component"], "power")
        self.assertEqual(state["broken"]["server"], "srv-r01-u14")
        # The alarm is still raised, just not in the fault slot.
        self.assertTrue(state["access_control"]["gate"]["tailgate_alarm"])

    def test_tailgate_claims_the_fault_slot_when_it_is_free(self):
        dc.get_state(self.session_id)
        dc.apply_action(self.session_id, "clear_failure", {})
        dc.apply_action(self.session_id, "access_ops", {"op": "tailgate_alarm"})
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state["broken"]["component"], "security")

    def test_propped_door_escalates_on_tick_and_clears_on_close(self):
        from apps.vmware_sim.datacenter_facility_ops import PROPPED_DOOR_TICKS

        dc.get_state(self.session_id)
        dc.apply_action(self.session_id, "environmental_ops", {"op": "open_door", "sensor_id": "DOOR-DH"})

        def door():
            state = dc.get_state(self.session_id)["state"]
            return next(s for s in state["environmental"]["sensors"] if s["id"] == "DOOR-DH")

        # Briefly open is not yet a violation.
        dc.apply_action(self.session_id, "live_tick", {})
        self.assertFalse(door().get("propped"))

        for _ in range(PROPPED_DOOR_TICKS):
            dc.apply_action(self.session_id, "live_tick", {})
        d = door()
        self.assertTrue(d["propped"])
        self.assertEqual(d["status"], "alarm")
        alarms = dc.get_state(self.session_id)["state"]["access_control"]["active_alarms"]
        self.assertTrue(any("propped" in a["message"] for a in alarms))

        dc.apply_action(self.session_id, "environmental_ops", {"op": "close_door", "sensor_id": "DOOR-DH"})
        d = door()
        self.assertFalse(d["open"])
        self.assertIsNone(d.get("propped"))

    def test_unescorted_visitor_is_flagged_then_resolved_by_escort(self):
        from apps.vmware_sim.datacenter_facility_ops import UNESCORTED_VISITOR_TICKS

        dc.get_state(self.session_id)
        r = dc.apply_action(self.session_id, "access_ops", {
            "op": "sign_in_visitor", "name": "visitor.acme", "zone": "data-hall-a",
        })
        self.assertTrue(r["ok"], r)
        for _ in range(UNESCORTED_VISITOR_TICKS):
            dc.apply_action(self.session_id, "live_tick", {})

        state = dc.get_state(self.session_id)["state"]
        vis = state["access_control"]["visitors"][0]
        self.assertTrue(vis["flagged"])
        self.assertTrue(any("unescorted" in a["message"] for a in state["access_control"]["active_alarms"]))

        esc = dc.apply_action(self.session_id, "access_ops", {
            "op": "assign_escort", "visitor_id": vis["id"], "escort": "tech.oncall",
        })
        self.assertTrue(esc["ok"], esc)
        state = dc.get_state(self.session_id)["state"]
        vis = next(v for v in state["access_control"]["visitors"] if v["id"] == vis["id"])
        self.assertEqual(vis["escort"], "tech.oncall")
        self.assertFalse(vis.get("flagged"))
        self.assertFalse(any("unescorted" in a["message"] for a in state["access_control"]["active_alarms"]))

    def test_escorted_visitor_never_trips(self):
        dc.get_state(self.session_id)
        dc.apply_action(self.session_id, "access_ops", {
            "op": "sign_in_visitor", "name": "visitor.bob", "escort": "tech.oncall",
        })
        for _ in range(6):
            dc.apply_action(self.session_id, "live_tick", {})
        state = dc.get_state(self.session_id)["state"]
        self.assertFalse(state["access_control"]["visitors"][0].get("flagged"))


class FailureTrainingTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())
        self.addCleanup(cache.clear)

    def test_training_inject_and_clear_failure(self):
        dc.get_state(self.session_id)
        r = dc.apply_action(self.session_id, "training_start", {"scenario_id": "ts-psu"})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r.get("injected"), "psu")
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state.get("broken", {}).get("component"), "power")
        self.assertEqual(state.get("training", {}).get("active"), "ts-psu")

        r2 = dc.apply_action(self.session_id, "clear_failure", {})
        self.assertTrue(r2["ok"], r2)
        state = dc.get_state(self.session_id)["state"]
        self.assertFalse(state.get("broken"))
        self.assertIn("Clear fault", state.get("training", {}).get("progress") or [])

    def test_inject_cooling_and_clear(self):
        dc.get_state(self.session_id)
        r = dc.apply_action(self.session_id, "inject_failure", {"preset": "cooling"})
        self.assertTrue(r["ok"], r)
        state = dc.get_state(self.session_id)["state"]
        self.assertEqual(state["broken"]["component"], "cooling")
        r2 = dc.apply_action(self.session_id, "clear_failure", {})
        self.assertTrue(r2["ok"], r2)
        self.assertFalse(dc.get_state(self.session_id)["state"].get("broken"))
