"""Session 64: AMI copy/share/deprecate, image drift, NAT VPC endpoint charges."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-ami-finops-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsAmiShareDriftTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-ami-share"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_foreign_ami_launch_requires_permission(self):
        sid = self._sid()
        reg = ae.apply_action(sid, "register_image", {
            "ami_id": "ami-0foreignprivate01",
            "name": "partner-golden",
            "owner": "999999999999",
            "visibility": "private",
            "arch": "x86_64",
        })
        self.assertTrue(reg.get("ok"), reg)

        denied = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0foreignprivate01",
            "instance_type": "t2.micro",
            "name": "no-perm",
        })
        self.assertFalse(denied.get("ok"), denied)
        self.assertIn("launch permission", denied.get("error", "").lower())

        # Owner share is simulated by modify as if we own it — re-register with share,
        # or mutate via share after registering as self then changing owner is hard.
        # Use register with user_ids instead for the allow path.
        ae.apply_action(sid, "register_image", {
            "ami_id": "ami-0foreignshared001",
            "name": "partner-shared",
            "owner": "999999999999",
            "visibility": "private",
            "user_ids": [ae.ACCOUNT_ID],
        })
        ok = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0foreignshared001",
            "instance_type": "t2.micro",
            "name": "with-perm",
        })
        self.assertTrue(ok.get("ok"), ok)

    def test_copy_image_cross_region_then_share(self):
        sid = self._sid()
        inst = ae.get_state(sid, "")["state"]["instances"][0]
        created = ae.apply_action(sid, "create_image", {
            "instance_id": inst["id"],
            "name": "src-ami",
        })
        self.assertTrue(created.get("ok"), created)
        copied = ae.apply_action(sid, "copy_image", {
            "ami_id": created["ami_id"],
            "destination_region": "us-west-2",
            "name": "src-ami-west",
        })
        self.assertTrue(copied.get("ok"), copied)
        self.assertEqual(copied["ami"]["region"], "us-west-2")
        self.assertEqual(copied["ami"]["sourceAmiId"], created["ami_id"])

        share = ae.apply_action(sid, "share_image", {
            "ami_id": copied["ami_id"],
            "user_ids": ["888888888888"],
        })
        self.assertTrue(share.get("ok"), share)
        self.assertIn("888888888888", share["launchPermissions"]["UserIds"])

    def test_deprecated_ami_blocks_launch_and_lists_drift(self):
        sid = self._sid()
        inst = ae.get_state(sid, "")["state"]["instances"][0]
        created = ae.apply_action(sid, "create_image", {
            "instance_id": inst["id"],
            "name": "n-ami",
        })
        ami_id = created["ami_id"]
        # Launch one on N, then deprecate.
        launch = ae.apply_action(sid, "launch_instance", {
            "ami_id": ami_id,
            "instance_type": "t2.micro",
            "name": "drifted-host",
        })
        self.assertTrue(launch.get("ok"), launch)

        dep = ae.apply_action(sid, "deprecate_image", {"ami_id": ami_id})
        self.assertTrue(dep.get("ok"), dep)

        blocked = ae.apply_action(sid, "launch_instance", {
            "ami_id": ami_id,
            "instance_type": "t2.micro",
            "name": "should-fail",
        })
        self.assertFalse(blocked.get("ok"), blocked)
        self.assertIn("deprecated", blocked.get("error", "").lower())

        drift = ae.apply_action(sid, "list_image_drift", {})
        self.assertTrue(drift.get("ok"))
        self.assertGreaterEqual(drift["count"], 1)
        ids = {d["instance_id"] for d in drift["drifted_instances"]}
        self.assertTrue(ids.intersection(set(launch["instance_ids"])))

        # N+1 without orphaning: create new image, deregister N with delete_snapshots
        created2 = ae.apply_action(sid, "create_image", {
            "instance_id": inst["id"],
            "name": "n-plus-1",
        })
        clean = ae.apply_action(sid, "deregister_image", {
            "ami_id": ami_id,
            "delete_snapshots": True,
        })
        self.assertTrue(clean.get("ok"), clean)
        self.assertTrue(clean.get("deleted_snapshots"))
        # New AMI still launchable
        ok = ae.apply_action(sid, "launch_instance", {
            "ami_id": created2["ami_id"],
            "instance_type": "t2.micro",
            "name": "canary",
        })
        self.assertTrue(ok.get("ok"), ok)


@override_settings(CACHES=LOCMEM_CACHE)
class AwsNatVpceCostTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-nat-vpce"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_s3_via_nat_charges_until_vpc_endpoint(self):
        sid = self._sid()
        subnet = ae.get_state(sid, "")["state"]["subnets"][0]["id"]
        nat = ae.apply_action(sid, "create_nat_gateway", {"subnet_id": subnet})
        self.assertTrue(nat.get("ok"), nat)

        costly = ae.apply_action(sid, "estimate_nat_s3_charges", {"gb": 100})
        self.assertTrue(costly.get("ok"), costly)
        self.assertGreater(costly["nat_processing_usd"], 0)
        self.assertFalse(costly["via_vpc_endpoint"])

        ep = ae.apply_action(sid, "create_vpc_endpoint", {
            "service": "com.amazonaws.us-east-1.s3",
            "vpc_endpoint_type": "Gateway",
        })
        self.assertTrue(ep.get("ok"), ep)

        free = ae.apply_action(sid, "estimate_nat_s3_charges", {"gb": 100})
        self.assertTrue(free.get("ok"), free)
        self.assertEqual(free["nat_processing_usd"], 0.0)
        self.assertTrue(free["via_vpc_endpoint"])
