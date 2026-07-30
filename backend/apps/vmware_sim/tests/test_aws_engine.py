"""Tests for the server-authoritative AWS console engine.

Covers: EC2 launch -> pending -> running lifecycle, dependency-violation errors on
delete (DependencyViolation / BucketNotEmpty), and a passing + failing
validate_aws_lab per seeded scenario objective.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import aws_engine as ae


class AwsEngineBaseTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "") -> str:
        sid = f"test-aws-{slug or 'plain'}"
        ae.drop_session(sid)
        ae.get_state(sid, slug)
        return sid


class LifecycleTests(AwsEngineBaseTest):
    def test_launch_pending_then_running(self):
        sid = self._session("aws-ec2-launch")
        # Launch with the objective's expected type/name.
        res = ae.apply_action(sid, "launch_instance", {"instance_type": "t3.micro", "name": "app-web-01"})
        self.assertTrue(res["ok"], res)
        iid = res["instance_ids"][0]

        # Freshly launched: pending (transition scheduled in the future).
        state = ae.get_state(sid, "aws-ec2-launch")["state"]
        inst = next(i for i in state["instances"] if i["id"] == iid)
        self.assertEqual(inst["state"], "pending")

        # After the pending window elapses, get_state advances it to running.
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            state = ae.get_state(sid, "aws-ec2-launch")["state"]
            inst = next(i for i in state["instances"] if i["id"] == iid)
        self.assertEqual(inst["state"], "running")
        self.assertEqual(inst["statusChecks"], "2/2")
        self.assertEqual(inst["type"], "t3.micro")

    def test_stop_transitions_to_stopped(self):
        sid = self._session()
        res = ae.apply_action(sid, "stop_instance", {"instance_id": "web-server-01"})
        self.assertTrue(res["ok"], res)
        state = ae.get_state(sid)["state"]
        inst = ae._find_instance(state, "web-server-01")
        self.assertEqual(inst["state"], "stopping")
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.STOPPING_SECONDS + 1):
            state = ae.get_state(sid)["state"]
            inst = ae._find_instance(state, "web-server-01")
        self.assertEqual(inst["state"], "stopped")

    def test_launch_unknown_type_rejected(self):
        sid = self._session()
        res = ae.apply_action(sid, "launch_instance", {"instance_type": "z9.mega"})
        self.assertFalse(res["ok"])
        self.assertIn("does not exist", res["error"])

    def test_ids_and_arn_shapes(self):
        self.assertTrue(ae.new_instance_id().startswith("i-0"))
        self.assertEqual(len(ae.new_instance_id()), len("i-0") + 16)
        self.assertTrue(ae.new_iam_user_id().startswith("AIDA"))
        self.assertEqual(ae.arn("s3", "us-east-1", ae.ACCOUNT_ID, "my-bucket"), "arn:aws:s3:::my-bucket")
        self.assertEqual(ae.arn("iam", "us-east-1", "123456789012", "user/bob"), "arn:aws:iam::123456789012:user/bob")


class DependencyViolationTests(AwsEngineBaseTest):
    def test_delete_security_group_with_attached_instance_violates(self):
        sid = self._session()
        # web-sg (sg-0a1b2c3web00001) is attached to web-server-01 + app-server-01.
        res = ae.apply_action(sid, "delete_security_group", {"group_id": "sg-0a1b2c3web00001"})
        self.assertFalse(res["ok"])
        self.assertIn("DependencyViolation", res["error"])

    def test_delete_subnet_with_instance_violates(self):
        sid = self._session()
        res = ae.apply_action(sid, "delete_subnet", {"subnet_id": "subnet-0a1b2c3d4e5f10001"})
        self.assertFalse(res["ok"])
        self.assertIn("DependencyViolation", res["error"])

    def test_delete_vpc_with_subnets_violates(self):
        sid = self._session()
        res = ae.apply_action(sid, "delete_vpc", {"vpc_id": "vpc-0a1b2c3d4e5f67890"})
        self.assertFalse(res["ok"])
        self.assertIn("DependencyViolation", res["error"])

    def test_delete_nonempty_bucket_violates(self):
        sid = self._session()
        res = ae.apply_action(sid, "delete_bucket", {"name": "my-web-assets-demo-123456"})
        self.assertFalse(res["ok"])
        self.assertIn("BucketNotEmpty", res["error"])

    def test_delete_empty_bucket_succeeds(self):
        sid = self._session()
        # my-logs-demo-123456 seeds with zero objects.
        res = ae.apply_action(sid, "delete_bucket", {"name": "my-logs-demo-123456"})
        self.assertTrue(res["ok"], res)
        state = ae.get_state(sid)["state"]
        self.assertFalse(any(b["name"] == "my-logs-demo-123456" for b in state["s3Buckets"]))

    def test_delete_unattached_sg_succeeds(self):
        sid = self._session()
        # The default SG is not attached to any instance in the base world.
        res = ae.apply_action(sid, "delete_security_group", {"group_id": "sg-0a1b2c3default03"})
        self.assertTrue(res["ok"], res)
        state = ae.get_state(sid)["state"]
        self.assertFalse(any(g["id"] == "sg-0a1b2c3default03" for g in state["securityGroups"]))


class ValidationTests(AwsEngineBaseTest):
    def test_launch_objective_fail_then_pass(self):
        slug = "aws-ec2-launch-web"
        sid = self._session(slug)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok, reason)

        ae.apply_action(sid, "launch_instance", {"instance_type": "t3.micro", "name": "app-web-01"})
        # Still pending -> not yet running -> still fails.
        ok, _ = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)

        # Advance past the pending window; now running -> passes.
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            ae.get_state(sid, slug)  # fold the transition in
            ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_sg_restrict_ingress_fail_then_pass(self):
        slug = "aws-sg-restrict-ssh"
        sid = self._session(slug)
        # web-sg seeds with SSH open to 0.0.0.0/0 -> fails.
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok, reason)
        # Remove the open SSH rule (port 22, 0.0.0.0/0).
        res = ae.apply_action(sid, "remove_sg_rule", {"group_name": "web-sg", "port": 22, "source": "0.0.0.0/0"})
        self.assertTrue(res["ok"], res)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_bucket_encryption_fail_then_pass(self):
        slug = "aws-s3-encrypt-logs"
        sid = self._session(slug)
        ok, _ = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)
        res = ae.apply_action(sid, "update_bucket", {"name": "my-logs-demo-123456", "patch": {"encryption": "SSE-KMS"}})
        self.assertTrue(res["ok"], res)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_stop_objective(self):
        slug = "aws-stop-instance"
        sid = self._session(slug)
        ok, _ = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)
        ae.apply_action(sid, "stop_instance", {"instance_id": "web-server-01"})
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.STOPPING_SECONDS + 1):
            ae.get_state(sid, slug)
            ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_tag_objective(self):
        slug = "aws-tag-instance"
        sid = self._session(slug)
        ok, _ = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)
        ae.apply_action(sid, "set_tags", {"instance_id": "db-server-01", "tags": {"Environment": "production"}})
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_unmapped_slug_fails_closed_until_activity(self):
        slug = "aws-freeform-explore"
        sid = self._session(slug)
        # No broken markers + no events -> must not auto-pass.
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)
        self.assertEqual(reason, "NO_VALIDATION_SCRIPT")

    def test_validation_script_checks(self):
        slug = "aws-scripted"
        sid = self._session(slug)
        entry = ae._load(sid)
        entry["state"]["validation_script"] = [
            {"check": "instance_running", "instance": "web-server-01"},
            {"check": "bucket_private", "bucket": "my-backups-demo-123456"},
        ]
        ae._save(sid, entry)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

        # Break a check: require the (public) web-assets bucket to be private.
        entry = ae._load(sid)
        entry["state"]["validation_script"] = [{"check": "bucket_private", "bucket": "my-web-assets-demo-123456"}]
        ae._save(sid, entry)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok, reason)


class GuiSyncContractTests(AwsEngineBaseTest):
    """Lock the action-name / payload contract the frontend awsStore mirror sends.

    These exercise the exact engine action names + payload keys that
    awsStore.js `_syncAction(...)` emits when a graded AWS lab is active, so a
    console GUI click (or an `aws ...` terminal command that funnels through the
    same store methods) lands in the server-side world the grader reads.
    """

    def test_launch_via_gui_payload_grades_pass(self):
        # awsStore.launchInstances -> _syncAction('launch_instance', {...}).
        slug = "aws-ec2-launch-web"
        sid = self._session(slug)
        self.assertFalse(ae.validate_aws_lab(sid, slug)[0])
        res = ae.apply_action(sid, "launch_instance", {
            "name": "app-web-01",
            "instance_type": "t3.micro",
            "ami_id": "ami-0c02fb55956c7d316",
            "count": 1,
            "subnet_id": "",
            "security_groups": ["sg-0a1b2c3web00001"],
            "key_name": "demo-key-pair",
            "volume_size": 8,
            "volume_type": "gp3",
            "monitoring": False,
            "tags": {"Name": "app-web-01"},
        })
        self.assertTrue(res["ok"], res)
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            ae.get_state(sid, slug)
            ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_launch_wizard_default_t3_micro_grades_pass(self):
        """Launch Wizard / CLI default instance type must satisfy require_launch."""
        slug = "aws-ec2-launch-web"
        sid = self._session(slug)
        res = ae.apply_action(sid, "launch_instance", {
            "name": "app-web-01",
            "instance_type": "t3.micro",
            "count": 1,
            "tags": {"Name": "app-web-01"},
        })
        self.assertTrue(res["ok"], res)
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            ae.get_state(sid, slug)
            ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_launch_free_tier_cousin_t2_micro_also_passes(self):
        """t2.micro remains accepted as a free-tier cousin of t3.micro objectives."""
        slug = "aws-ec2-launch-web"
        sid = self._session(slug)
        ae.apply_action(sid, "launch_instance", {
            "name": "app-web-01", "instance_type": "t2.micro", "count": 1,
            "tags": {"Name": "app-web-01"},
        })
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            ae.get_state(sid, slug)
            ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_launch_wrong_type_grades_fail(self):
        # Correct name but wrong instance type must NOT satisfy the objective.
        slug = "aws-ec2-launch-web"
        sid = self._session(slug)
        ae.apply_action(sid, "launch_instance", {
            "name": "app-web-01", "instance_type": "t3.large", "count": 1,
            "tags": {"Name": "app-web-01"},
        })
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            ae.get_state(sid, slug)
            ok, _ = ae.validate_aws_lab(sid, slug)
        self.assertFalse(ok)

    def test_sg_add_then_remove_via_gui_payload(self):
        # awsStore.setSgRules diffs by (port, source): a removed open-SSH rule is
        # mirrored as remove_sg_rule{port, source}; an added rule as
        # add_sg_rule{from_port, to_port, source}. Verify both shapes work and
        # the restrict-SSH objective flips fail -> pass.
        slug = "aws-sg-restrict-ssh"
        sid = self._session(slug)
        self.assertFalse(ae.validate_aws_lab(sid, slug)[0])
        # Remove the seeded 0.0.0.0/0:22 rule (GUI "Save" diff -> remove_sg_rule).
        res = ae.apply_action(sid, "remove_sg_rule", {
            "group_id": "sg-0a1b2c3web00001", "direction": "inbound", "port": 22, "source": "0.0.0.0/0",
        })
        self.assertTrue(res["ok"], res)
        # Re-add SSH but scoped to a bastion CIDR (add_sg_rule with from_port/to_port).
        res = ae.apply_action(sid, "add_sg_rule", {
            "group_id": "sg-0a1b2c3web00001", "direction": "inbound", "type": "SSH",
            "protocol": "TCP", "from_port": 22, "to_port": 22, "source": "10.0.0.0/8", "description": "bastion",
        })
        self.assertTrue(res["ok"], res)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_bucket_encryption_via_gui_update_payload(self):
        # awsStore.updateBucket -> _syncAction('update_bucket', {name, patch}).
        slug = "aws-s3-encrypt-logs"
        sid = self._session(slug)
        self.assertFalse(ae.validate_aws_lab(sid, slug)[0])
        res = ae.apply_action(sid, "update_bucket", {
            "name": "my-logs-demo-123456", "patch": {"encryption": "SSE-S3"},
        })
        self.assertTrue(res["ok"], res)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_stop_via_gui_instance_action_payload(self):
        # awsStore.instanceAction -> _syncAction('instance_action', {op, instance_ids})
        # identifying by Name tag ("web-server-01").
        slug = "aws-stop-instance"
        sid = self._session(slug)
        self.assertFalse(ae.validate_aws_lab(sid, slug)[0])
        res = ae.apply_action(sid, "instance_action", {"op": "stop", "instance_ids": ["web-server-01"]})
        self.assertTrue(res["ok"], res)
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.STOPPING_SECONDS + 1):
            ae.get_state(sid, slug)
            ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)

    def test_tag_via_gui_set_tags_payload(self):
        # awsStore.setInstanceTags -> _syncAction('set_tags', {instance_id, tags}).
        slug = "aws-tag-instance"
        sid = self._session(slug)
        self.assertFalse(ae.validate_aws_lab(sid, slug)[0])
        res = ae.apply_action(sid, "set_tags", {
            "instance_id": "db-server-01", "tags": {"Environment": "production"},
        })
        self.assertTrue(res["ok"], res)
        ok, reason = ae.validate_aws_lab(sid, slug)
        self.assertTrue(ok, reason)


class SessionContractTests(AwsEngineBaseTest):
    def test_drop_session_clears_state(self):
        sid = self._session()
        self.assertIsNotNone(ae._load(sid))
        ae.drop_session(sid)
        self.assertIsNone(ae._load(sid))

    def test_action_on_missing_session_errors(self):
        res = ae.apply_action("no-such-session", "launch_instance", {})
        self.assertFalse(res["ok"])
        self.assertIn("not found", res["error"])
