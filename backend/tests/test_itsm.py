"""Tests for the ITSM (ServiceNow-style) ticketing simulation.

Covers:
  * ticket lifecycle: open → state transitions (with the allowed-transition gate)
    + transfer between teams.
  * the reference cross-team disk flow: raise a Storage sub-ticket → team fulfils
    it → the disk is hot-added via the vmware_bridge and becomes VISIBLE on the
    lab server's RHEL simulation after a SCSI rescan (proving the end-to-end seam).
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.itsm import constants as C
from apps.itsm.models import ItsmTicket, ItsmWorkNote
from apps.itsm.services import (
    ensure_scenario_ticket,
    fulfil_sub_ticket,
    open_ticket,
    raise_sub_ticket,
    transfer_ticket,
    transition_ticket,
)
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()

# Use a real (local-memory) cache so the vmware_bridge, which stores pending
# disks in Django's cache, actually round-trips during the disk flow test.
_LOCMEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "itsm-tests"}
}


@override_settings(CACHES=_LOCMEM_CACHE)
class ItsmLifecycleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="itsmuser", email="itsm@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Linux ITSM", icon="terminal")
        self.scenario = Scenario.objects.create(
            title="Disk full on /var",
            slug="itsm-disk-full",
            technology=self.tech,
            description="Extend the LVM volume after Storage adds a disk.",
            is_active=True,
            is_free=True,
            itsm_enabled=True,
            itsm_ticket_type="incident",
            itsm_config={
                "priority": C.PRIORITY_HIGH,
                "assignment_group": C.TEAM_SERVICE_DESK,
                "allowed_actions": ["add_disk"],
            },
        )
        self.session = LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="RUNNING",
        )

    def test_open_ticket_sets_number_priority_and_sla(self):
        ticket, created = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        self.assertTrue(created)
        self.assertTrue(ticket.number.startswith("INC"))
        self.assertEqual(ticket.ticket_type, C.TYPE_INCIDENT)
        self.assertEqual(ticket.priority, C.PRIORITY_HIGH)
        self.assertEqual(ticket.state, C.STATE_NEW)
        self.assertIsNotNone(ticket.sla_due_at)  # SLA stamped from priority
        # Idempotent — second call returns the same ticket.
        again, created2 = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        self.assertFalse(created2)
        self.assertEqual(again.id, ticket.id)

    def test_state_transition_matrix_enforced(self):
        ticket, _ = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        # New → Resolved is NOT allowed directly.
        with self.assertRaises(ValueError):
            transition_ticket(ticket, C.STATE_RESOLVED, user=self.user)
        # New → In Progress → Resolved → Closed is the valid path.
        transition_ticket(ticket, C.STATE_IN_PROGRESS, user=self.user)
        self.assertEqual(ticket.state, C.STATE_IN_PROGRESS)
        transition_ticket(ticket, C.STATE_RESOLVED, user=self.user)
        self.assertIsNotNone(ticket.resolved_at)
        transition_ticket(ticket, C.STATE_CLOSED, user=self.user, close_code="closed_complete")
        self.assertEqual(ticket.state, C.STATE_CLOSED)
        self.assertEqual(ticket.close_code, "closed_complete")
        self.assertIsNotNone(ticket.closed_at)

    def test_transfer_between_teams(self):
        ticket, _ = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        transfer_ticket(ticket, C.TEAM_STORAGE, user=self.user, reason="needs storage")
        self.assertEqual(ticket.assignment_group, C.TEAM_STORAGE)
        # Transfer of a New ticket implicitly moves it In Progress.
        self.assertEqual(ticket.state, C.STATE_IN_PROGRESS)
        self.assertTrue(ItsmWorkNote.objects.filter(ticket=ticket, body__icontains="Transferred").exists())

    def test_cannot_resolve_parent_with_open_subticket(self):
        parent, _ = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        transition_ticket(parent, C.STATE_IN_PROGRESS, user=self.user)
        raise_sub_ticket(
            parent, user=self.user, action_kind="add_disk", action_params={"size_gb": 50},
        )
        parent.refresh_from_db()
        # Parent auto-moved to On Hold; create an UNRESOLVED sub-ticket to block close.
        sub2 = raise_sub_ticket(parent, user=self.user, team=C.TEAM_NETWORK, short_description="open port")
        # Bring parent back to In Progress to attempt resolving while a child is active.
        sub2.state = C.STATE_NEW
        sub2.save(update_fields=["state"])
        parent.state = C.STATE_IN_PROGRESS
        parent.save(update_fields=["state"])
        with self.assertRaises(ValueError):
            transition_ticket(parent, C.STATE_RESOLVED, user=self.user)


@override_settings(CACHES=_LOCMEM_CACHE)
class ItsmDiskSubTicketFlowTests(TestCase):
    """The headline flow: a Storage sub-ticket makes a disk appear in the lab."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="diskuser", email="disk@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Linux Disk", icon="hard-drive")
        self.scenario = Scenario.objects.create(
            title="LVM extend via Storage ticket",
            slug="itsm-lvm-extend",
            technology=self.tech,
            description="Raise a Storage sub-ticket for a disk, then extend the LV.",
            is_active=True,
            is_free=True,
            itsm_enabled=True,
        )
        self.session = LabSession.objects.create(
            user=self.user, scenario=self.scenario, status="RUNNING",
        )

    def test_disk_subticket_fulfilment_records_pending_disk(self):
        from apps.labs.provisioner.simulation import vmware_bridge as br

        parent, _ = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        sub = raise_sub_ticket(
            parent, user=self.user, action_kind="add_disk", action_params={"size_gb": 50},
        )
        # Routed to Storage automatically, parent placed On Hold.
        self.assertEqual(sub.assignment_group, C.TEAM_STORAGE)
        parent.refresh_from_db()
        self.assertEqual(parent.state, C.STATE_ON_HOLD)
        # No disk pending yet — the team has not actioned it.
        self.assertFalse(br.has_pending_disk(str(self.session.id)))

        # The simulated Storage team actions the ticket.
        fulfil_sub_ticket(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.state, C.STATE_RESOLVED)
        self.assertEqual(sub.action_result.get("device"), "/dev/sdc")
        # The hot-add is now recorded on the bridge for this session.
        self.assertTrue(br.has_pending_disk(str(self.session.id)))
        # Parent comes back off hold.
        parent.refresh_from_db()
        self.assertEqual(parent.state, C.STATE_IN_PROGRESS)

    def test_disk_becomes_visible_in_terminal_after_rescan(self):
        """End-to-end: fulfilment → bridge → the guest sees /dev/sdc after a rescan."""
        from apps.labs.provisioner.simulation.rhel_os import RHELOSState

        parent, _ = ensure_scenario_ticket(self.user, self.scenario, session=self.session)
        sub = raise_sub_ticket(
            parent, user=self.user, action_kind="add_disk", action_params={"size_gb": 50},
        )
        fulfil_sub_ticket(sub)

        # Stand up the lab's RHEL simulation bound to this session id (this is what
        # register_sim_session stamps onto the OS state in the running lab).
        os_state = RHELOSState(hostname="web-prod-01", scenario_slug=self.scenario.slug)
        os_state.session_id = str(self.session.id)

        # Before a rescan the guest kernel cannot see the new disk.
        self.assertNotIn("/dev/sdc", os_state.block_devices)

        # A SCSI rescan drains the bridge and reveals the disk.
        revealed = os_state.reveal_hidden_disks()
        self.assertIn("/dev/sdc", revealed)
        self.assertIn("/dev/sdc", os_state.block_devices)
        # A second rescan does not re-add it (idempotent drain).
        self.assertNotIn("/dev/sdc", os_state.reveal_hidden_disks())

    def test_available_actions_catalog(self):
        from apps.itsm.engine import available_actions

        kinds = {a["kind"] for a in available_actions()}
        self.assertIn("add_disk", kinds)
        disk = next(a for a in available_actions() if a["kind"] == "add_disk")
        self.assertEqual(disk["team"], C.TEAM_STORAGE)


@override_settings(CACHES=_LOCMEM_CACHE)
class ItsmApiTests(TestCase):
    """HTTP-level coverage of the ITSM endpoints (auth + the disk flow over REST)."""

    def setUp(self):
        from rest_framework.test import APIClient

        cache.clear()
        self.user = User.objects.create_user(username="apiuser", email="api@t.com", password="pass12345")
        self.tech = Technology.objects.create(name="Linux API", icon="terminal")
        self.scenario = Scenario.objects.create(
            title="API disk extend", slug="itsm-api-disk", technology=self.tech,
            description="x", is_active=True, is_free=True, itsm_enabled=True,
        )
        self.session = LabSession.objects.create(user=self.user, scenario=self.scenario, status="RUNNING")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_requires_auth(self):
        from rest_framework.test import APIClient

        anon = APIClient()
        self.assertEqual(anon.get("/api/itsm/meta/").status_code, 401)

    def test_meta_lists_teams_and_actions(self):
        res = self.client.get("/api/itsm/meta/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(any(t["value"] == "storage" for t in res.data["teams"]))
        self.assertTrue(any(a["kind"] == "add_disk" for a in res.data["actions"]))

    def test_open_then_raise_disk_subticket_over_http(self):
        from apps.labs.provisioner.simulation import vmware_bridge as br

        # Open the parent ticket (bound to the running session).
        res = self.client.post(f"/api/itsm/scenario/{self.scenario.id}/", {"session_id": str(self.session.id)}, format="json")
        self.assertEqual(res.status_code, 201)
        ticket = res.data["ticket"]
        self.assertTrue(ticket["number"].startswith("INC"))

        # Raise a Storage sub-ticket (auto-fulfilled) — disk should hot-add.
        res = self.client.post(
            f"/api/itsm/tickets/{ticket['id']}/sub-tickets/",
            {"action_kind": "add_disk", "action_params": {"size_gb": 50}, "auto_fulfil": True},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        sub = res.data["sub_ticket"]
        self.assertEqual(sub["state"], C.STATE_RESOLVED)
        self.assertEqual(sub["action_result"]["device"], "/dev/sdc")
        self.assertTrue(br.has_pending_disk(str(self.session.id)))
        # Parent is back In Progress and now lists the child.
        self.assertEqual(res.data["parent"]["state"], C.STATE_IN_PROGRESS)
        self.assertEqual(len(res.data["parent"]["children"]), 1)

    def test_transition_rejects_illegal_state_over_http(self):
        res = self.client.post(f"/api/itsm/scenario/{self.scenario.id}/", {"session_id": str(self.session.id)}, format="json")
        ticket_id = res.data["ticket"]["id"]
        # New → Closed directly is illegal.
        bad = self.client.post(f"/api/itsm/tickets/{ticket_id}/transition/", {"state": "closed"}, format="json")
        self.assertEqual(bad.status_code, 400)
        # New → In Progress is fine.
        ok = self.client.post(f"/api/itsm/tickets/{ticket_id}/transition/", {"state": "in_progress"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["state"], C.STATE_IN_PROGRESS)

    def test_other_users_ticket_is_not_accessible(self):
        from rest_framework.test import APIClient

        res = self.client.post(f"/api/itsm/scenario/{self.scenario.id}/", {"session_id": str(self.session.id)}, format="json")
        ticket_id = res.data["ticket"]["id"]
        other = User.objects.create_user(username="intruder", email="x@t.com", password="pass12345")
        oc = APIClient()
        oc.force_authenticate(other)
        self.assertEqual(oc.get(f"/api/itsm/tickets/{ticket_id}/").status_code, 404)
