"""Backup/restore provenance for the Commvault CommCell simulator.

The engine previously constructed every restore with will_fail=False and popped
the objective at launch, so a restore that never materialised a single file
still reported success and still satisfied the grader. These tests pin the
properties that make restore a real outcome: a restore is verified against the
manifest its backup recorded, corrupt or incomplete backups fail that
verification, and retention / aux-copy placement decide what is restorable.
"""

import uuid

from django.core.cache import cache
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation import commvault_bridge
from apps.vmware_sim import commvault_engine as cv

RESTORE_SLUG = "commvault-restore-web01"


class CommvaultRestoreProvenanceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.session_id = str(uuid.uuid4())

    # -- helpers ---------------------------------------------------------
    def _open(self, slug=RESTORE_SLUG):
        cv.get_state(self.session_id, slug)
        cv.apply_action(self.session_id, "login", {})

    def _finish(self, job_id, seconds=10):
        """Push a job past the wall-clock finish threshold and re-poll."""
        entry = cv._load(self.session_id)
        job = next(j for j in entry["state"]["jobs"] if j["id"] == job_id)
        job["started_ts"] -= seconds
        cv._save(self.session_id, entry)
        cv.get_state(self.session_id)

    def _job(self, job_id):
        return next(j for j in cv._load(self.session_id)["state"]["jobs"] if j["id"] == job_id)

    def _points(self, client="web01"):
        return [p for p in cv._load(self.session_id)["state"]["recovery_points"]
                if p["client"] == client]

    # -- backup produces provenance --------------------------------------
    def test_completed_backup_writes_a_recovery_point_with_checksums(self):
        self._open("commvault-backup-overdue")
        result = cv.apply_action(self.session_id, "run_backup", {"client": "db01"})
        self._finish(result["job_id"])

        point = self._points("db01")[0]
        self.assertEqual(point["job_id"], result["job_id"])
        self.assertTrue(point["manifest"])
        for entry in point["manifest"]:
            self.assertEqual(len(entry["sha256"]), 64)

    def test_backup_still_running_has_no_recovery_point(self):
        """Provenance is settled at completion, not at launch."""
        self._open("commvault-backup-overdue")
        cv.apply_action(self.session_id, "run_backup", {"client": "db01"})
        self.assertEqual(self._points("db01"), [])

    # -- the happy path ---------------------------------------------------
    def test_restore_verifies_against_manifest_and_passes_grader(self):
        self._open()
        result = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["recovery_point"])
        self._finish(result["job_id"])

        job = self._job(result["job_id"])
        self.assertEqual(job["status"], "completed")
        self.assertIs(job["verified"], True)

        ok, msg = cv.validate_commvault_lab(self.session_id, RESTORE_SLUG)
        self.assertTrue(ok, msg)

    def test_restore_records_materialised_files_on_the_bridge(self):
        """The guest must actually receive the manifest's paths and bytes."""
        self._open()
        result = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self._finish(result["job_id"])

        landed = commvault_bridge.get_restored(self.session_id, result["job_id"])
        self.assertIsNotNone(landed)
        point = next(p for p in self._points() if p["id"] == result["recovery_point"])
        self.assertEqual(sorted(landed["paths"]), sorted(e["path"] for e in point["manifest"]))
        for entry in point["manifest"]:
            self.assertEqual(cv._sha256(landed["contents"][entry["path"]]), entry["sha256"])

    def test_client_state_hides_verification_internals(self):
        """The learner sees the verdict, not the answer key."""
        self._open("commvault-restore-verify-corrupt")
        result = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self._finish(result["job_id"])

        state = cv.get_state(self.session_id, "commvault-restore-verify-corrupt")["state"]
        job = next(j for j in state["jobs"] if j["id"] == result["job_id"])
        self.assertNotIn("materialised", job)
        self.assertIn("verify_message", job)
        for point in state["recovery_points"]:
            self.assertNotIn("corrupt", point)

    # -- restore must be able to fail -------------------------------------
    def test_restore_with_no_backup_is_refused(self):
        self._open("commvault-restore-app01")
        result = cv.apply_action(self.session_id, "run_restore", {"client": "app01"})
        self.assertFalse(result["ok"])
        self.assertIn("No backup", result["error"])

    def test_corrupt_backup_fails_restore_verification(self):
        self._open("commvault-backup-overdue")
        backup = cv.apply_action(self.session_id, "run_backup",
                                 {"client": "db01", "corrupt": True})
        self._finish(backup["job_id"])

        restore = cv.apply_action(self.session_id, "run_restore", {"client": "db01"})
        self._finish(restore["job_id"])

        job = self._job(restore["job_id"])
        self.assertEqual(job["status"], "failed")
        self.assertIs(job["verified"], False)
        self.assertIn("checksum mismatch", job["verify_message"])

    def test_incomplete_backup_fails_restore_verification(self):
        """Media holds fewer files than the manifest advertises."""
        self._open("commvault-backup-overdue")
        backup = cv.apply_action(self.session_id, "run_backup",
                                 {"client": "db01", "incomplete": True})
        self._finish(backup["job_id"])

        point = self._points("db01")[0]
        self.assertLess(len(point["stored_paths"]), len(point["manifest"]))

        restore = cv.apply_action(self.session_id, "run_restore", {"client": "db01"})
        self._finish(restore["job_id"])

        job = self._job(restore["job_id"])
        self.assertEqual(job["status"], "failed")
        self.assertIn("missing", job["verify_message"])

    def test_grader_fails_closed_when_restore_did_not_verify(self):
        """The regression that mattered: a run restore is not a passed restore."""
        self._open("commvault-restore-verify-corrupt")
        restore = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self._finish(restore["job_id"])

        ok, msg = cv.validate_commvault_lab(self.session_id, "commvault-restore-verify-corrupt")
        self.assertFalse(ok, msg)
        self.assertIn("did not verify", msg)

    def test_launching_a_restore_does_not_clear_the_objective(self):
        """`needs_restore` must survive until verification, not be popped at launch.

        Checked through the generic grader branch (a slug without "restore",
        which is how cross-tech scenarios reach the console), because that
        branch is the one that reads `broken` directly.
        """
        cv.get_state(self.session_id, "")
        cv.apply_action(self.session_id, "login", {})
        entry = cv._load(self.session_id)
        entry["state"]["broken"] = {"needs_restore": "web01"}
        cv._save(self.session_id, entry)

        started = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self.assertTrue(started["ok"], started)
        ok, msg = cv.validate_commvault_lab(self.session_id, "")
        self.assertFalse(ok, "a restore that has not verified yet must not pass")
        self.assertIn("restore", msg)

        self._finish(started["job_id"])
        self.assertIs(self._job(started["job_id"])["verified"], True)
        self.assertNotIn("needs_restore", cv._load(self.session_id)["state"]["broken"])

    def test_corrupt_preset_is_solvable_from_the_older_recovery_point(self):
        """A lab that cannot be solved is worse than one that is too easy."""
        self._open("commvault-restore-verify-corrupt")
        good = min(self._points(), key=lambda p: p["created_ts"])
        self.assertFalse(good["corrupt"])

        restore = cv.apply_action(self.session_id, "run_restore",
                                  {"client": "web01", "recovery_point": good["id"]})
        self.assertTrue(restore["ok"], restore)
        self._finish(restore["job_id"])

        self.assertIs(self._job(restore["job_id"])["verified"], True)
        ok, msg = cv.validate_commvault_lab(self.session_id, "commvault-restore-verify-corrupt")
        self.assertTrue(ok, msg)

    # -- retention / aux-copy govern what is restorable --------------------
    def test_retention_expiry_removes_a_point_from_restore(self):
        """Same recovery point, same age — only the policy's retention differs."""
        self._open()
        entry = cv._load(self.session_id)
        entry["state"]["recovery_points"][0]["created_ts"] -= 5 * 86400
        cv._save(self.session_id, entry)
        self.assertTrue(cv.apply_action(self.session_id, "run_restore", {"client": "web01"})["ok"])

        cache.clear()
        self.session_id = str(uuid.uuid4())
        self._open()
        entry = cv._load(self.session_id)
        entry["state"]["recovery_points"][0]["created_ts"] -= 5 * 86400
        for policy in entry["state"]["storage_policies"]:
            if policy["name"] == "Gold-Retention-30d":
                policy["retention_days"] = 1
        cv._save(self.session_id, entry)

        result = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self.assertFalse(result["ok"])
        self.assertIn("expired", result["error"])

    def test_restore_from_secondary_copy_requires_the_aux_copy_to_have_run(self):
        self._open()
        before = cv.apply_action(self.session_id, "run_restore",
                                 {"client": "web01", "copy": "CloudLib-S3"})
        self.assertFalse(before["ok"])

        cv.apply_action(self.session_id, "run_aux_copy", {"name": "Gold-to-Cloud"})
        after = cv.apply_action(self.session_id, "run_restore",
                                {"client": "web01", "copy": "CloudLib-S3"})
        self.assertTrue(after["ok"], after)
        self._finish(after["job_id"])
        self.assertIs(self._job(after["job_id"])["verified"], True)

    # -- point in time -----------------------------------------------------
    def test_point_in_time_selects_the_newest_point_at_or_before_the_instant(self):
        self._open()
        second = cv.apply_action(self.session_id, "run_backup", {"client": "web01"})
        self._finish(second["job_id"])

        points = self._points()
        self.assertEqual(len(points), 2)
        older = min(points, key=lambda p: p["created_ts"])

        latest = cv.apply_action(self.session_id, "run_restore", {"client": "web01"})
        self.assertNotEqual(latest["recovery_point"], older["id"])

        pit = cv.apply_action(self.session_id, "run_restore",
                              {"client": "web01", "before_ts": older["created_ts"] + 1})
        self.assertEqual(pit["recovery_point"], older["id"])
