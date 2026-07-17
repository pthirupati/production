"""Cross-engine correlation trace IDs on LabServer events (Phase 3.4).

A single logical learner action that fans out across multiple engines (a
console's own event log, its cross-tech bridge, ServerIdentity, and the
terminal that eventually applies a hardware change) should carry ONE
trace_id through every hop, so `events_for_trace(session_id, trace_id)` can
reconstruct the whole cross-engine story for a single debug question:
"what actually happened when the learner clicked this button?"

Proven end-to-end for both new cloud packs (Azure/GCP) since those are the
freshest, most consistent bridge implementations, plus direct unit coverage
of the trace_id primitives themselves.
"""

from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import server_identity as si
from apps.vmware_sim import azure_engine as ae
from apps.vmware_sim import gcp_engine as ge
from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.rhel_shell import RHELShell


class TraceIdPrimitiveTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "trace-primitive-session"

    def test_new_trace_id_is_unique_each_call(self):
        a, b = si.new_trace_id(), si.new_trace_id()
        self.assertNotEqual(a, b)
        self.assertTrue(a)
        self.assertTrue(b)

    def test_publish_event_uses_explicit_trace_id_over_payload(self):
        ev = si.publish_event(self.sid, "test.event", {"trace_id": "payload-trace"}, trace_id="explicit-trace")
        self.assertEqual(ev["trace_id"], "explicit-trace")

    def test_publish_event_falls_back_to_payload_trace_id(self):
        ev = si.publish_event(self.sid, "test.event", {"trace_id": "payload-trace"})
        self.assertEqual(ev["trace_id"], "payload-trace")

    def test_publish_event_generates_trace_id_when_none_given(self):
        ev = si.publish_event(self.sid, "test.event", {})
        self.assertTrue(ev["trace_id"])

    def test_events_for_trace_returns_only_matching_events_oldest_first(self):
        si.publish_event(self.sid, "test.a", {}, trace_id="trace-1")
        si.publish_event(self.sid, "test.unrelated", {}, trace_id="trace-2")
        si.publish_event(self.sid, "test.b", {}, trace_id="trace-1")

        matched = si.events_for_trace(self.sid, "trace-1")
        self.assertEqual([e["type"] for e in matched], ["test.a", "test.b"])

    def test_upsert_server_and_set_power_share_a_thread_trace_id(self):
        trace = si.new_trace_id()
        server = si.upsert_server(self.sid, {"hostname": "srv1"}, source="test", trace_id=trace)
        si.set_power(self.sid, server["id"], "off", source="test", trace_id=trace)

        matched = si.events_for_trace(self.sid, trace)
        types = [e["type"] for e in matched]
        self.assertIn("server.upserted", types)
        self.assertIn("server.power", types)
        self.assertEqual(len(matched), 2)


class AzureResizeTraceCorrelationTests(SimpleTestCase):
    """The console click, the bridge queue, and the terminal apply all share
    one trace_id end-to-end for the master-prompt canonical resize example."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "trace-azure-session"
        ae.drop_session(self.sid)
        self.addCleanup(ae.drop_session, self.sid)

    def test_resize_action_correlates_engine_bridge_and_terminal_events(self):
        ae.get_state(self.sid)
        ae.apply_action(self.sid, "login", {"user": "admin"})
        res = ae.apply_action(self.sid, "resize_vm", {"vm_name": "vm-web01", "size": "Standard_D2s_v5"})
        self.assertTrue(res["ok"], res)

        # The engine's OWN event log entry carries a trace_id.
        state = ae.get_state(self.sid)["state"]
        engine_event = state["events"][0]
        trace_id = engine_event.get("trace_id")
        self.assertTrue(trace_id)

        # The terminal applies the pending resize and publishes a correlated
        # ServerIdentity event under the SAME trace_id.
        rhel_state = RHELOSState(hostname="vm-web01")
        rhel_state.session_id = self.sid
        shell = RHELShell(state=rhel_state)
        shell.run("nproc")

        matched = si.events_for_trace(self.sid, trace_id)
        self.assertTrue(any(e["type"] == "server.hardware_resized" for e in matched))


class GcpResizeTraceCorrelationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "trace-gcp-session"
        ge.drop_session(self.sid)
        self.addCleanup(ge.drop_session, self.sid)

    def test_resize_action_correlates_engine_bridge_and_terminal_events(self):
        ge.get_state(self.sid)
        ge.apply_action(self.sid, "login", {"user": "admin"})
        ge.apply_action(self.sid, "stop_instance", {"instance_name": "web01"})
        with mock.patch.object(ge, "_now", return_value=ge.time.time() + ge.PENDING_SECONDS + 1):
            ge.get_state(self.sid)
        res = ge.apply_action(self.sid, "set_machine_type", {"instance_name": "web01", "machine_type": "e2-standard-2"})
        self.assertTrue(res["ok"], res)

        state = ge.get_state(self.sid)["state"]
        engine_event = state["events"][0]
        trace_id = engine_event.get("trace_id")
        self.assertTrue(trace_id)

        rhel_state = RHELOSState(hostname="web01")
        rhel_state.session_id = self.sid
        shell = RHELShell(state=rhel_state)
        shell.run("nproc")

        matched = si.events_for_trace(self.sid, trace_id)
        self.assertTrue(any(e["type"] == "server.hardware_resized" for e in matched))


class DiskAttachTraceCorrelationTests(SimpleTestCase):
    """A disk-attach action's engine event and its ServerIdentity mirror
    share the same trace_id (no terminal hop needed for this one)."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.sid = "trace-disk-session"
        ae.drop_session(self.sid)
        self.addCleanup(ae.drop_session, self.sid)

    def test_attach_disk_correlates_engine_and_server_identity_events(self):
        ae.get_state(self.sid)
        ae.apply_action(self.sid, "login", {"user": "admin"})
        res = ae.apply_action(self.sid, "attach_disk", {"vm_name": "vm-web01", "disk_name": "disk-data-unattached"})
        self.assertTrue(res["ok"], res)

        state = ae.get_state(self.sid)["state"]
        trace_id = state["events"][0].get("trace_id")
        self.assertTrue(trace_id)

        matched = si.events_for_trace(self.sid, trace_id)
        self.assertTrue(any(e["type"] == "server.disk_attached" for e in matched))
