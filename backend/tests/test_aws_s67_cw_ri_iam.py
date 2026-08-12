"""Session 67: CW log cost, RI/SP coverage, IAM least privilege."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-s67-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsCwRiIamTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-s67"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_debug_log_ingestion_cost_drops_after_info(self):
        sid = self._sid()
        before = ae.apply_action(sid, "estimate_log_ingestion_cost", {"days": 30})
        self.assertTrue(before.get("ok"), before)
        self.assertGreater(before["total"], 0)
        self.assertTrue(any(l.get("warning") for l in before["lines"]))

        fixed = ae.apply_action(sid, "set_log_level", {
            "name": "/aws/lambda/checkout",
            "level": "INFO",
        })
        self.assertTrue(fixed.get("ok"), fixed)
        self.assertEqual(fixed["log_group"]["logLevel"], "INFO")

        after = ae.apply_action(sid, "estimate_log_ingestion_cost", {"days": 30})
        self.assertLess(after["total"], before["total"])
        self.assertFalse(any(l.get("warning") for l in after["lines"]))

    def test_ri_sp_coverage_reduces_effective_spend(self):
        sid = self._sid()
        # Launch several t3.medium so coverage math has room
        for i in range(3):
            ae.apply_action(sid, "launch_instance", {
                "instance_type": "t3.medium",
                "name": f"web-{i}",
                "tags": {"Environment": "prod", "Owner": "ops"},
            })
        baseline = ae.apply_action(sid, "analyze_ri_sp_coverage", {"hours": 24})
        self.assertTrue(baseline.get("ok"), baseline)
        self.assertGreater(baseline["on_demand_usd"], 0)
        self.assertLess(baseline["coverage_percent"], 50)

        ae.apply_action(sid, "purchase_reserved_instance", {
            "instance_type": "t3.medium",
            "count": 2,
        })
        ae.apply_action(sid, "purchase_savings_plan", {
            "hourly_commitment": 0.05,
            "discount": 0.28,
        })
        covered = ae.apply_action(sid, "analyze_ri_sp_coverage", {"hours": 24})
        self.assertTrue(covered.get("ok"), covered)
        self.assertGreater(covered["coverage_percent"], baseline["coverage_percent"])
        self.assertLess(covered["effective_usd"], baseline["on_demand_usd"])

    def test_tighten_policy_keeps_required_caller_actions(self):
        sid = self._sid()
        analysis = ae.apply_action(sid, "analyze_policy_scope", {
            "name": "OverpoweredDeployPolicy",
        })
        self.assertTrue(analysis.get("ok"), analysis)
        self.assertTrue(analysis["excessive"])

        tight = ae.apply_action(sid, "tighten_policy", {
            "name": "OverpoweredDeployPolicy",
            "actions": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
            "resource": [
                "arn:aws:s3:::my-web-assets-demo-123456",
                "arn:aws:s3:::my-web-assets-demo-123456/*",
            ],
        })
        self.assertTrue(tight.get("ok"), tight)
        after = ae.apply_action(sid, "analyze_policy_scope", {
            "name": "OverpoweredDeployPolicy",
        })
        self.assertFalse(after["excessive"])

        ok = ae.apply_action(sid, "invoke_with_policy", {
            "name": "OverpoweredDeployPolicy",
            "required_actions": ["s3:GetObject", "s3:PutObject"],
        })
        self.assertTrue(ok.get("ok"), ok)

        denied = ae.apply_action(sid, "invoke_with_policy", {
            "name": "OverpoweredDeployPolicy",
            "required_actions": ["iam:CreateUser"],
        })
        self.assertFalse(denied.get("ok"), denied)
        self.assertIn("AccessDenied", denied.get("error", ""))
