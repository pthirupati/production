"""Session 63: AssumeRole/ExternalId, AMI snapshot orphans, org encryption, dual-key."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-ops-polish-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsOpsPolishTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-ops"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_assume_role_requires_external_id(self):
        sid = self._sid()
        bad = ae.apply_action(sid, "assume_role", {
            "role": "CrossAccountReadRole",
            "principal": "arn:aws:iam::999999999999:root",
        })
        self.assertFalse(bad.get("ok"), bad)
        self.assertIn("ExternalId", bad.get("error", ""))

        wrong = ae.apply_action(sid, "assume_role", {
            "role": "CrossAccountReadRole",
            "principal": "arn:aws:iam::999999999999:root",
            "external_id": "nope",
        })
        self.assertFalse(wrong.get("ok"), wrong)

        ok = ae.apply_action(sid, "assume_role", {
            "role": "CrossAccountReadRole",
            "principal": "arn:aws:iam::999999999999:root",
            "external_id": "fixitlab-ext-42",
            "session_name": "lab",
        })
        self.assertTrue(ok.get("ok"), ok)
        self.assertEqual(ok["sts"]["role"], "CrossAccountReadRole")

    def test_assume_role_rejects_untrusted_principal(self):
        sid = self._sid()
        res = ae.apply_action(sid, "assume_role", {
            "role": "CrossAccountReadRole",
            "principal": "arn:aws:iam::111111111111:root",
            "external_id": "fixitlab-ext-42",
        })
        self.assertFalse(res.get("ok"), res)
        self.assertIn("trust policy", res.get("error", "").lower())

    def test_service_role_still_assumable_without_principal(self):
        sid = self._sid()
        res = ae.apply_action(sid, "assume_role", {"role": "EC2InstanceRole"})
        self.assertTrue(res.get("ok"), res)

    def test_deregister_orphans_snapshots_unless_deleted(self):
        sid = self._sid()
        # Seed has instances; create AMI from first.
        state = ae.get_state(sid, "")["state"]
        inst = (state.get("instances") or [None])[0]
        self.assertIsNotNone(inst)
        created = ae.apply_action(sid, "create_image", {
            "instance_id": inst["id"],
            "name": "orphan-test-ami",
        })
        self.assertTrue(created.get("ok"), created)
        ami_id = created["ami_id"]
        snap_ids = created["snapshot_ids"]
        self.assertTrue(snap_ids)

        dereg = ae.apply_action(sid, "deregister_image", {"ami_id": ami_id})
        self.assertTrue(dereg.get("ok"), dereg)
        self.assertEqual(dereg.get("orphaned_snapshots"), snap_ids)

        orphaned = ae.apply_action(sid, "list_orphaned_resources", {})
        self.assertTrue(orphaned.get("ok"))
        orphan_ids = [s["id"] for s in orphaned["orphaned"]["snapshots"]]
        self.assertEqual(set(orphan_ids), set(snap_ids))

        # Clean path: recreate + delete_snapshots
        created2 = ae.apply_action(sid, "create_image", {
            "instance_id": inst["id"],
            "name": "clean-ami",
        })
        ami2 = created2["ami_id"]
        snaps2 = created2["snapshot_ids"]
        clean = ae.apply_action(sid, "deregister_image", {
            "ami_id": ami2,
            "delete_snapshots": True,
        })
        self.assertTrue(clean.get("ok"), clean)
        self.assertEqual(clean.get("deleted_snapshots"), snaps2)
        state = ae.get_state(sid, "")["state"]
        remaining = {s["id"] for s in state.get("snapshots") or []}
        for sid_snap in snaps2:
            self.assertNotIn(sid_snap, remaining)

    def test_org_encryption_blocks_unencrypted_copy(self):
        sid = self._sid()
        vol = next(
            v for v in ae.get_state(sid, "")["state"].get("volumes") or []
            if not v.get("encrypted")
        )
        snap = ae.apply_action(sid, "create_snapshot", {"volume_id": vol["id"]})
        self.assertTrue(snap.get("ok"), snap)

        ae.apply_action(sid, "set_org_policy", {"require_ebs_encryption": True})
        blocked = ae.apply_action(sid, "copy_snapshot", {
            "snapshot_id": snap["snapshot_id"],
            "encrypted": False,
        })
        self.assertFalse(blocked.get("ok"), blocked)
        self.assertIn("encryption", blocked.get("error", "").lower())

        ok = ae.apply_action(sid, "copy_snapshot", {
            "snapshot_id": snap["snapshot_id"],
            "encrypted": True,
            "kms_key_id": "arn:aws:kms:us-east-1:123456789012:key/lab",
        })
        self.assertTrue(ok.get("ok"), ok)
        self.assertTrue(ok["snapshot"]["encrypted"])

    def test_dual_key_rotation_overlap(self):
        sid = self._sid()
        # developer-user already has one Active key
        rot = ae.apply_action(sid, "rotate_access_key", {"name": "developer-user"})
        self.assertTrue(rot.get("ok"), rot)
        self.assertEqual(len(rot["access_keys"]), 2)
        self.assertTrue(all(k["status"] == "Active" for k in rot["access_keys"]))

        third = ae.apply_action(sid, "create_access_key", {"name": "developer-user"})
        self.assertFalse(third.get("ok"))
        self.assertIn("LimitExceeded", third.get("error", ""))

        old = rot["old_access_key_id"]
        new = rot["new_access_key_id"]
        ae.apply_action(sid, "use_access_key", {
            "name": "developer-user",
            "access_key_id": new,
        })
        deact = ae.apply_action(sid, "deactivate_access_key", {
            "name": "developer-user",
            "access_key_id": old,
        })
        self.assertTrue(deact.get("ok"), deact)
        deleted = ae.apply_action(sid, "delete_access_key", {
            "name": "developer-user",
            "access_key_id": old,
        })
        self.assertTrue(deleted.get("ok"), deleted)
        state = ae.get_state(sid, "")["state"]
        user = next(u for u in state["iamUsers"] if u["name"] == "developer-user")
        self.assertEqual(len(user["accessKeys"]), 1)
        self.assertEqual(user["accessKeys"][0]["id"], new)
