"""Tests for per-key grader feedback in the datacenter, bare metal, AWX and
Commvault console simulators.

These four graders previously returned a generic "<vendor> environment still
has unresolved issues" string, which told a learner nothing about which
objective was still unmet. Each engine now maps its broken-state keys to a
specific message. The engines store bare targets (a hostname, a machine id, a
template id) and frequently just ``True``, so these tests also pin the two
failure modes a naive formatter would introduce: leaking ``True`` as a target,
and hiding half the remaining work when a preset seeds several keys at once.

Unknown keys must keep failing CLOSED while naming the key, so a preset added
without a matching template shows up as a reportable gap rather than either a
silent pass or an opaque message.
"""

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.vmware_sim import awx_engine as awx
from apps.vmware_sim import baremetal_engine as bm
from apps.vmware_sim import commvault_engine as cv
from apps.vmware_sim import datacenter_engine as dc

GENERIC = "still has unresolved issues"


class DatacenterGraderMessageTests(SimpleTestCase):
    """The datacenter broken dict is a single fault RECORD, not a bag of keys.

    It looks like {"server": ..., "component": ..., "target": ...}, so the
    reason is keyed on the component and the target is resolved from whichever
    of server/cable_id/target the injector filled in.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _validate(self, slug):
        sid = f"dc-msg-{slug}"
        dc.drop_session(sid)
        self.addCleanup(dc.drop_session, sid)
        dc._ensure(sid, slug)
        return dc.validate_datacenter_lab(sid, slug)

    def test_names_the_failed_component_and_server(self):
        ok, message = self._validate("datacenter-replace-psu")
        self.assertFalse(ok)
        self.assertIn("power supply", message)
        self.assertIn("srv-r01-u14", message)
        self.assertNotIn(GENERIC, message)

    def test_cable_fault_names_both_cable_and_server(self):
        # The cable record carries server AND cable_id; naming only the server
        # would leave the learner hunting for which cable to reseat.
        ok, message = self._validate("datacenter-cable-reseat")
        self.assertFalse(ok)
        self.assertIn("NIC0-front", message)
        self.assertIn("srv-r02-u10", message)
        self.assertNotIn(GENERIC, message)

    def test_facility_fault_uses_target_when_server_is_none(self):
        # Facility faults set server=None and carry "target" instead, so a
        # formatter that reached for "server" would render "None".
        ok, message = self._validate("datacenter-cooling-crac")
        self.assertFalse(ok)
        self.assertIn("CRAC-1", message)
        self.assertNotIn("None", message)
        self.assertNotIn(GENERIC, message)

    def test_pdu_fault_names_the_pdu(self):
        ok, message = self._validate("datacenter-pdu-breaker")
        self.assertFalse(ok)
        self.assertIn("PDU-R01", message)
        self.assertNotIn("None", message)

    def test_unknown_component_still_fails_closed(self):
        sid = "dc-unknown-component"
        dc.drop_session(sid)
        self.addCleanup(dc.drop_session, sid)
        entry = dc._ensure(sid, "")
        entry["state"]["broken"] = {"server": "srv-r01-u14", "component": "flux_capacitor"}
        dc._save(sid, entry)
        ok, message = dc.validate_datacenter_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("flux_capacitor", message)

    def test_fault_record_without_component_still_fails_closed(self):
        sid = "dc-no-component"
        dc.drop_session(sid)
        self.addCleanup(dc.drop_session, sid)
        entry = dc._ensure(sid, "")
        entry["state"]["broken"] = {"some_future_field": "widget"}
        dc._save(sid, entry)
        ok, message = dc.validate_datacenter_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("some_future_field", message)


class BareMetalGraderMessageTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_lists_every_outstanding_objective(self):
        sid = "bm-msg-commission"
        bm.drop_session(sid)
        self.addCleanup(bm.drop_session, sid)
        bm._ensure(sid, "baremetal-maas-commission")
        # This preset seeds commissioning AND an unreachable BMC, so a
        # next(iter(...)) formatter would hide half the remaining work.
        self.assertEqual(len(bm._load(sid)["state"]["broken"]), 2)
        ok, message = bm.validate_baremetal_lab(sid, "baremetal-maas-commission")
        self.assertFalse(ok)
        self.assertIn("commissioning", message)
        self.assertIn("BMC", message)
        # machine_needs_commission holds a machine id; bmc_unreachable is bare
        # True and must not be echoed as a target.
        self.assertIn("2", message)
        self.assertNotIn("True", message)
        self.assertNotIn(GENERIC, message)

    def test_single_key_preset_names_its_target(self):
        sid = "bm-msg-lxd"
        bm.drop_session(sid)
        self.addCleanup(bm.drop_session, sid)
        bm._ensure(sid, "baremetal-lxd-container")
        ok, message = bm.validate_baremetal_lab(sid, "baremetal-lxd-container")
        self.assertFalse(ok)
        self.assertIn("batch-job", message)
        self.assertNotIn(GENERIC, message)

    def test_list_valued_target_is_rendered_readably(self):
        sid = "bm-msg-matrix"
        bm.drop_session(sid)
        self.addCleanup(bm.drop_session, sid)
        bm._ensure(sid, "baremetal-imagedev-matrix")
        ok, message = bm.validate_baremetal_lab(sid, "baremetal-imagedev-matrix")
        self.assertFalse(ok)
        # missing_boot_resources holds a list; str.format would emit a Python
        # repr with brackets and quotes.
        for image in ("custom/h100-jammy", "custom/h200-jammy",
                      "custom/b300-jammy", "custom/mi300-jammy"):
            self.assertIn(image, message)
        self.assertNotIn("[", message)
        self.assertNotIn("'", message)
        self.assertNotIn(GENERIC, message)

    def test_unknown_broken_key_still_fails_closed(self):
        sid = "bm-unknown-key"
        bm.drop_session(sid)
        self.addCleanup(bm.drop_session, sid)
        entry = bm._ensure(sid, "")
        entry["state"]["broken"] = {"some_future_key": "widget"}
        bm._save(sid, entry)
        ok, message = bm.validate_baremetal_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("some_future_key", message)


class AwxGraderMessageTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _validate(self, slug):
        sid = f"awx-msg-{slug}"
        awx.drop_session(sid)
        self.addCleanup(awx.drop_session, sid)
        awx._ensure(sid, slug)
        return awx.validate_awx_lab(sid, slug)

    def test_names_the_failed_template(self):
        ok, message = self._validate("awx-job-launch")
        self.assertFalse(ok)
        self.assertIn("11", message)
        self.assertIn("job template", message)
        self.assertNotIn(GENERIC, message)

    def test_boolean_target_does_not_leak_true(self):
        ok, message = self._validate("awx-install-tower")
        self.assertFalse(ok)
        self.assertIn("AWX has not been installed", message)
        self.assertNotIn("True", message)
        self.assertNotIn(GENERIC, message)

    def test_project_sync_names_the_objective(self):
        ok, message = self._validate("awx-project-sync")
        self.assertFalse(ok)
        self.assertIn("sync", message)
        self.assertNotIn("True", message)

    def test_lists_every_outstanding_objective(self):
        sid = "awx-msg-multi"
        awx.drop_session(sid)
        self.addCleanup(awx.drop_session, sid)
        entry = awx._ensure(sid, "")
        # The AI-infra presets seed a failed template plus a stale canary
        # driver together; both must be reported.
        entry["state"]["broken"] = {"failed_template_id": 12, "canary_driver_stale": True}
        awx._save(sid, entry)
        ok, message = awx.validate_awx_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("12", message)
        self.assertIn("canary", message)
        self.assertNotIn("True", message)

    def test_unknown_broken_key_still_fails_closed(self):
        sid = "awx-unknown-key"
        awx.drop_session(sid)
        self.addCleanup(awx.drop_session, sid)
        entry = awx._ensure(sid, "")
        entry["state"]["broken"] = {"some_future_key": "widget"}
        awx._save(sid, entry)
        ok, message = awx.validate_awx_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("some_future_key", message)


class CommvaultGraderMessageTests(SimpleTestCase):
    """Only slugs that fall through the scenario-specific branches in
    validate_commvault_lab reach the generic message, so these use schedule /
    aux-copy / overdue presets rather than restore / policy / subclient."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _validate(self, slug):
        sid = f"cv-msg-{slug}"
        cv.drop_session(sid)
        self.addCleanup(cv.drop_session, sid)
        cv._ensure(sid, slug)
        return cv.validate_commvault_lab(sid, slug)

    def test_names_the_disabled_schedule(self):
        ok, message = self._validate("commvault-schedule-enable")
        self.assertFalse(ok)
        self.assertIn("Incremental-db01", message)
        self.assertNotIn(GENERIC, message)

    def test_names_the_pending_aux_copy(self):
        ok, message = self._validate("commvault-aux-copy")
        self.assertFalse(ok)
        self.assertIn("Gold-to-Cloud", message)
        self.assertNotIn(GENERIC, message)

    def test_names_the_overdue_client(self):
        ok, message = self._validate("commvault-overdue-backup")
        self.assertFalse(ok)
        self.assertIn("db01", message)
        self.assertNotIn(GENERIC, message)

    def test_boolean_target_does_not_leak_true(self):
        sid = "cv-bool-session"
        cv.drop_session(sid)
        self.addCleanup(cv.drop_session, sid)
        entry = cv._ensure(sid, "")
        # missing_client is bare True; its own slug short-circuits earlier in
        # the grader, so seed it against a neutral slug to reach the generic
        # branch.
        entry["state"]["broken"] = {"missing_client": True}
        cv._save(sid, entry)
        ok, message = cv.validate_commvault_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("registered", message)
        self.assertNotIn("True", message)
        self.assertNotIn(GENERIC, message)

    def test_unknown_broken_key_still_fails_closed(self):
        sid = "cv-unknown-key"
        cv.drop_session(sid)
        self.addCleanup(cv.drop_session, sid)
        entry = cv._ensure(sid, "")
        entry["state"]["broken"] = {"some_future_key": "widget"}
        cv._save(sid, entry)
        ok, message = cv.validate_commvault_lab(sid, "")
        self.assertFalse(ok)
        self.assertIn("some_future_key", message)
