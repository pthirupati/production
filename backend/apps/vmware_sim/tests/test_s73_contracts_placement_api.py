"""Session 73: contracts SLA, rack placement, api_client mock send."""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.labs.api_client_mock import dispatch_mock_request, interpolate
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology
from apps.vmware_sim.datacenter_economy_ops import (
    accept_contract,
    evaluate_contracts,
    place_rack,
    remove_rack,
    validate_rack_placement,
)
from apps.vmware_sim.datacenter_physics_ops import build_ops_ticket, refresh_ticket_sla

User = get_user_model()


class ContractSlaTests(SimpleTestCase):
    def test_accept_and_clear_when_capacity_ok(self):
        state = {
            "facility": {"it_kw": 8.0, "capacity_kw": 80.0},
            "capacity": {"power": {"capacity_kw": 80.0}},
            "racks": [{"id": "R01"}, {"id": "R02"}],
            "servers": [{"id": "s1", "rack": "R01", "u_height": 2}],
            "tickets": [],
            "contracts": [],
        }
        c = accept_contract(state, tenant="acme", kw=12, u_slots=24)
        self.assertEqual(c["status"], "active")
        newly = evaluate_contracts(state)
        self.assertEqual(newly, [])
        self.assertFalse(c["sla_breached"])
        self.assertEqual(c["credits_owed"], 0.0)

    def test_overcommit_and_ticket_breach_accrue_credits(self):
        state = {
            "facility": {"it_kw": 40.0},
            "capacity": {"power": {"capacity_kw": 50.0}},
            "racks": [{"id": "R01"}],
            "servers": [{"id": "s1", "rack": "R01", "u_height": 40}],
            "tickets": [],
            "contracts": [],
        }
        c = accept_contract(state, tenant="globex", kw=60, u_slots=90, credit_usd=100)
        newly = evaluate_contracts(state)
        self.assertEqual(len(newly), 1)
        self.assertTrue(c["sla_breached"])
        self.assertEqual(c["credits_owed"], 100.0)

        # Idempotent: second eval does not double-credit while still breached
        evaluate_contracts(state)
        self.assertEqual(c["credits_owed"], 100.0)
        self.assertEqual(c["breach_count"], 1)

        # Ticket SLA also keeps stakes hot after capacity is restored
        c["kw"] = 5
        c["u_slots"] = 5
        state["capacity"]["power"]["capacity_kw"] = 200
        state["facility"]["it_kw"] = 10
        state["servers"] = []
        ticket = build_ops_ticket(
            vendor="Dell", ticket_type="incident", asset_id="a1",
            hostname="h", component="psu", summary="x", priority="critical",
            now_ts=1_700_000_000.0,
        )
        refresh_ticket_sla(ticket, now_ts=1_700_000_000.0 + 3600 * 2)
        state["tickets"] = [ticket]
        self.assertTrue(ticket["sla_breached"])
        # Clear previous breach flag to observe a fresh ticket-driven breach event
        c["sla_breached"] = False
        newly2 = evaluate_contracts(state)
        self.assertEqual(len(newly2), 1)
        self.assertTrue(c["sla_breached"])
        self.assertEqual(c["credits_owed"], 200.0)


class RackPlacementTests(SimpleTestCase):
    def test_valid_place_and_remove(self):
        state = {"racks": [], "servers": []}
        ok = validate_rack_placement(state, grid_x=2, grid_z=0, orientation="hot_cold", mass_kg=300)
        self.assertTrue(ok["ok"], ok)
        placed = place_rack(state, rack_id="R99", grid_x=2, grid_z=0, mass_kg=300)
        self.assertTrue(placed["ok"], placed)
        self.assertEqual(len(state["racks"]), 1)

        # Collision
        bad = place_rack(state, rack_id="R98", grid_x=2, grid_z=0)
        self.assertFalse(bad["ok"])

        # Wrong orientation on even Z
        bad_orient = validate_rack_placement(state, grid_x=3, grid_z=0, orientation="cold_hot")
        self.assertFalse(bad_orient["ok"])

        # Overweight
        heavy = validate_rack_placement(state, grid_x=4, grid_z=0, mass_kg=950)
        self.assertFalse(heavy["ok"])

        removed = remove_rack(state, "R99")
        self.assertTrue(removed["ok"])
        self.assertEqual(state["racks"], [])

    def test_remove_blocked_when_servers_present(self):
        state = {
            "racks": [{"id": "R01", "grid_x": 0, "grid_z": 0}],
            "servers": [{"id": "s1", "rack": "R01"}],
        }
        blocked = remove_rack(state, "R01")
        self.assertFalse(blocked["ok"])


class ApiClientMockTests(SimpleTestCase):
    def test_interpolate_and_health_route(self):
        self.assertEqual(interpolate("https://{{host}}/health", {"host": "api.local"}), "https://api.local/health")
        res = dispatch_mock_request(method="GET", url="/health")
        self.assertTrue(res["ok"])
        self.assertEqual(res["status"], 200)
        self.assertTrue(res["mock"])
        self.assertEqual(res["body"]["status"], "ok")

    def test_echo_and_404(self):
        res = dispatch_mock_request(method="POST", url="/api/v1/echo", body={"hi": 1})
        self.assertEqual(res["status"], 201)
        self.assertEqual(res["body"], {"hi": 1})
        missing = dispatch_mock_request(method="GET", url="/nope")
        self.assertEqual(missing["status"], 404)
        self.assertFalse(missing["ok"])


class ApiClientSendViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="apiu", email="a@t.com", password="Pass123!")
        self.client.force_authenticate(user=self.user)
        tech = Technology.objects.create(name="Linux", slug="linux-apiu", description="x", price=0, is_active=True)
        self.scenario = Scenario.objects.create(
            title="API client",
            slug="api-client-s73",
            technology=tech,
            difficulty=1,
            is_active=True,
            coding_mode=True,
            coding_spec={"language": "javascript"},
        )
        self.session = LabSession.objects.create(
            user=self.user,
            scenario=self.scenario,
            status="RUNNING",
        )

    def test_send_mock_health(self):
        resp = self.client.post(
            f"/api/labs/{self.session.id}/api-client/send/",
            {"method": "GET", "url": "/health"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["mock"])
        self.assertEqual(resp.data["status"], 200)
