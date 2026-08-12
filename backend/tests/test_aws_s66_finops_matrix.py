"""Session 66: S3 lifecycle/MPU, cross-AZ transfer, ASG runaway, multi-SKU matrix."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae
from apps.vmware_sim import packer_factory as pf


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-s66-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsS3LifecycleCrossAzAsgTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-s66"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_lifecycle_and_incomplete_multipart_cost(self):
        sid = self._sid()
        # Seed has buckets; pick first or create
        buckets = ae.get_state(sid, "")["state"].get("s3Buckets") or []
        bname = buckets[0]["name"] if buckets else "logs-archive"
        if not buckets:
            self.assertTrue(ae.apply_action(sid, "create_bucket", {"name": bname}).get("ok"))

        # 1 TB Standard blob (size in bytes)
        tb = 1024 ** 4
        ae.apply_action(sid, "put_object", {
            "bucket": bname, "key": "cold/data.bin", "size": tb,
        })
        mpu = ae.apply_action(sid, "create_multipart_upload", {
            "bucket": bname, "key": "partial/big.bin", "size": tb // 2,
        })
        self.assertTrue(mpu.get("ok"), mpu)

        before = ae.apply_action(sid, "estimate_s3_storage_cost", {"bucket": bname})
        self.assertTrue(before.get("ok"), before)
        self.assertGreater(before["total"], 0)
        self.assertTrue(any(
            l.get("storageClass") == "INCOMPLETE_MULTIPART" for l in before["lines"]
        ))
        self.assertTrue(any(l.get("warning") for l in before["lines"]))

        # Lifecycle → Glacier + abort incomplete MPU rule
        lc = ae.apply_action(sid, "put_bucket_lifecycle", {
            "bucket": bname,
            "transition_days": 30,
            "storage_class": "GLACIER",
            "abort_multipart_days": 7,
            "object_age_days": 60,
        })
        self.assertTrue(lc.get("ok"), lc)

        abort = ae.apply_action(sid, "abort_multipart_upload", {
            "bucket": bname,
            "upload_id": mpu["upload_id"],
        })
        self.assertTrue(abort.get("ok"), abort)

        after = ae.apply_action(sid, "estimate_s3_storage_cost", {"bucket": bname})
        self.assertTrue(after.get("ok"), after)
        self.assertLess(after["total"], before["total"])
        self.assertTrue(any(l.get("storageClass") == "GLACIER" for l in after["lines"]))
        self.assertFalse(any(
            l.get("storageClass") == "INCOMPLETE_MULTIPART" for l in after["lines"]
        ))

    def test_cross_az_transfer_charges(self):
        sid = self._sid()
        # Seeded instances span us-east-1a/b/c
        costly = ae.apply_action(sid, "estimate_cross_az_transfer", {
            "source_instance": "web-server-01",
            "dest_instance": "db-server-01",
            "gb": 200,
        })
        self.assertTrue(costly.get("ok"), costly)
        self.assertFalse(costly["same_az"])
        self.assertGreater(costly["cross_az_usd"], 0)

        # Same AZ pair → $0
        free = ae.apply_action(sid, "estimate_cross_az_transfer", {
            "source_instance": "web-server-01",
            "dest_instance": "web-server-01",
            "gb": 200,
        })
        self.assertTrue(free.get("ok"), free)
        self.assertTrue(free["same_az"])
        self.assertEqual(free["cross_az_usd"], 0.0)

    def test_asg_runaway_then_fix(self):
        sid = self._sid()
        # Ensure v2 ASG exists via ensure path
        runaway = ae.apply_action(sid, "simulate_asg_runaway", {
            "name": "web-asg",
            "runaway": True,
            "ticks": 10,
        })
        self.assertTrue(runaway.get("ok"), runaway)
        self.assertEqual(runaway["asg"]["desired"], runaway["asg"]["max"])
        self.assertTrue(runaway["runaway"])

        fixed = ae.apply_action(sid, "fix_asg_scaling_policy", {
            "name": "web-asg",
            "threshold": 70,
            "cooldown_seconds": 300,
            "desired": 2,
        })
        self.assertTrue(fixed.get("ok"), fixed)
        self.assertFalse(fixed["asg"]["scaling_policy"]["runaway"])
        self.assertEqual(fixed["asg"]["desired"], 2)

        # With cooldown + sensible threshold, ticks should not climb to max
        tick = ae.apply_action(sid, "tick_asg_scaling", {
            "name": "web-asg",
            "ticks": 5,
            "metric_value": 50,
        })
        self.assertTrue(tick.get("ok"), tick)
        self.assertLess(tick["asg"]["desired"], tick["asg"]["max"])


@override_settings(CACHES=LOCMEM_CACHE)
class PackerMatrixTests(SimpleTestCase):
    def test_one_sku_failure_does_not_block_others(self):
        state = {"factory": {}, "maas": {"boot_resources": []}}
        started = pf.start_matrix_pipeline(state, {"skus": ["h100", "h200", "b300"]})
        self.assertTrue(started.get("ok"), started)
        self.assertEqual(len(started["matrix_run"]["tracks"]), 3)

        failed = pf.fail_matrix_sku(state, {"sku": "h200", "error": "gpu-sanity failed"})
        self.assertTrue(failed.get("ok"), failed)
        h200 = next(t for t in failed["matrix_run"]["tracks"] if t["sku"] == "h200")
        self.assertEqual(h200["status"], "failure")

        published = pf.publish_matrix(state, {})
        self.assertTrue(published.get("ok"), published)
        self.assertIn("h100", published["published"])
        self.assertIn("b300", published["published"])
        self.assertNotIn("h200", published["published"])
        self.assertTrue(any(s["sku"] == "h200" for s in published["skipped"]))
