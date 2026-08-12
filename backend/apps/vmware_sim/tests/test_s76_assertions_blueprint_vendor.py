"""Session 76: api_client assertions, blueprint undo, vendor injects."""

from django.test import SimpleTestCase

from apps.labs.api_client_mock import (
    dispatch_mock_request,
    evaluate_assertions,
    public_api_client_spec,
)
from apps.labs.vendor_dependency_ops import inject_vendor_event, remediate_vendor_event
from apps.vmware_sim.datacenter_economy_ops import (
    copy_rack_row,
    load_blueprint,
    place_rack,
    redo_blueprint,
    remove_rack,
    save_blueprint,
    undo_blueprint,
)


class ApiClientAssertionTests(SimpleTestCase):
    def test_status_header_json_timing(self):
        resp = dispatch_mock_request(method="GET", url="/health")
        grade = evaluate_assertions(
            resp,
            [
                {"op": "status equals", "value": 200, "name": "st"},
                {"op": "header matches", "header": "content-type", "value": "json", "name": "ct"},
                {"op": "json path equals", "path": "status", "value": "ok", "name": "body"},
                {"op": "timing max_ms", "value": 5000, "name": "fast"},
                {"op": "status equals", "value": 500, "name": "hidden_fail", "hidden": True},
            ],
        )
        self.assertFalse(grade["passed"])
        by_name = {r["name"]: r for r in grade["results"]}
        self.assertTrue(by_name["st"]["passed"])
        self.assertTrue(by_name["ct"]["passed"])
        self.assertTrue(by_name["body"]["passed"])
        self.assertTrue(by_name["fast"]["passed"])
        self.assertFalse(by_name["hidden_fail"]["passed"])

        pub = public_api_client_spec(
            {
                "variables": {"host": "x"},
                "assertions": [
                    {"op": "status equals", "value": 200},
                    {"op": "status equals", "value": 200, "hidden": True},
                ],
            }
        )
        self.assertEqual(len(pub["assertions"]), 1)
        self.assertEqual(pub["hidden_assertion_count"], 1)


class BlueprintUndoTests(SimpleTestCase):
    def test_undo_redo_save_copy_row(self):
        state = {"racks": []}
        p = place_rack(state, rack_id="R1", grid_x=0, grid_z=0)
        self.assertTrue(p["ok"], p)
        self.assertEqual(len(state["blueprint"]["undo"]), 1)

        u = undo_blueprint(state)
        self.assertTrue(u["ok"], u)
        self.assertEqual(len(state["racks"]), 0)

        r = redo_blueprint(state)
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(state["racks"]), 1)

        s = save_blueprint(state, "alpha")
        self.assertTrue(s["ok"], s)
        remove_rack(state, "R1")
        self.assertEqual(len(state["racks"]), 0)
        loaded = load_blueprint(state, "alpha")
        self.assertTrue(loaded["ok"], loaded)
        self.assertEqual(len(state["racks"]), 1)

        # Fresh place for copy-row (load clears undo)
        state = {"racks": []}
        place_rack(state, rack_id="A", grid_x=0, grid_z=0)
        place_rack(state, rack_id="B", grid_x=2, grid_z=0)
        copied = copy_rack_row(state, source_z=0, dest_z=2)
        self.assertTrue(copied["ok"], copied)
        self.assertEqual(len(copied["created"]), 2)
        self.assertEqual(len(state["racks"]), 4)


class VendorDependencyTests(SimpleTestCase):
    def test_restart_wrong_escalate_right(self):
        state = {}
        inj = inject_vendor_event(state, kind="upstream_outage")
        self.assertTrue(inj["ok"], inj)
        eid = inj["event"]["id"]

        wrong = remediate_vendor_event(state, event_id=eid, action="restart")
        self.assertFalse(wrong["ok"])

        ok = remediate_vendor_event(state, event_id=eid, action="escalate")
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(state["vendor_events"][0]["status"], "resolved")
        self.assertNotIn("vendor_dependency", state.get("broken") or {})
