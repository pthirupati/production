"""Session 65: cost model, IRSA/OIDC, tag policy, budget kill switch."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-finops-irsa-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsFinOpsIrsaTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-finops"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_cost_model_flags_gpu_spend(self):
        sid = self._sid()
        before = ae.apply_action(sid, "get_cost_and_usage", {"hours": 24})
        self.assertTrue(before.get("ok"), before)
        baseline = before["total"]

        gpu = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0c02fb55956c7d316",
            "instance_type": "p3.2xlarge",
            "name": "training-job",
            "tags": {"Environment": "dev", "Owner": "ml"},
        })
        self.assertTrue(gpu.get("ok"), gpu)

        after = ae.apply_action(sid, "get_cost_and_usage", {"hours": 24})
        self.assertGreater(after["total"], baseline)
        self.assertGreater(after["gpu_spend"], 0)
        self.assertTrue(after["anomaly_hints"])

    def test_required_tags_block_untagged_launch(self):
        sid = self._sid()
        ae.apply_action(sid, "set_org_policy", {
            "required_tags": ["Environment", "Owner"],
        })
        denied = ae.apply_action(sid, "launch_instance", {
            "instance_type": "t2.micro",
            "name": "untagged",
            "tags": {"Environment": "dev"},
        })
        self.assertFalse(denied.get("ok"), denied)
        self.assertIn("TagPolicyViolation", denied.get("error", ""))

        ok = ae.apply_action(sid, "launch_instance", {
            "instance_type": "t2.micro",
            "name": "tagged",
            "tags": {"Environment": "dev", "Owner": "platform"},
        })
        self.assertTrue(ok.get("ok"), ok)

    def test_irsa_web_identity_then_deactivate_static_keys(self):
        sid = self._sid()
        # Without OIDC provider → fail
        denied = ae.apply_action(sid, "assume_role_with_web_identity", {
            "role": "AppIRSARole",
            "sub": "system:serviceaccount:default:app",
        })
        self.assertFalse(denied.get("ok"), denied)

        ae.apply_action(sid, "create_oidc_provider", {
            "url": "oidc.eks.us-east-1.amazonaws.com/id/EXAMPLED429",
        })
        wrong = ae.apply_action(sid, "assume_role_with_web_identity", {
            "role": "AppIRSARole",
            "sub": "system:serviceaccount:default:other",
        })
        self.assertFalse(wrong.get("ok"), wrong)

        ok = ae.apply_action(sid, "assume_role_with_web_identity", {
            "role": "AppIRSARole",
            "sub": "system:serviceaccount:default:app",
        })
        self.assertTrue(ok.get("ok"), ok)
        self.assertTrue(ok["sts"]["web_identity"])

        migrated = ae.apply_action(sid, "migrate_user_to_irsa", {
            "name": "developer-user",
        })
        self.assertTrue(migrated.get("ok"), migrated)
        self.assertTrue(migrated["deactivated_keys"])
        user = next(
            u for u in ae.get_state(sid, "")["state"]["iamUsers"]
            if u["name"] == "developer-user"
        )
        self.assertTrue(all(k["status"] == "Inactive" for k in user["accessKeys"]))

    def test_budget_kill_switch_spares_production(self):
        sid = self._sid()
        # Launch expensive GPU as non-prod + a prod host
        ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0c02fb55956c7d316",
            "instance_type": "p3.2xlarge",
            "name": "gpu-dev",
            "tags": {"Environment": "dev"},
        })
        # Seeded web-server-01 is Environment=demo — will be stopped
        # Tag db as production so kill switch preserves it
        state = ae.get_state(sid, "")["state"]
        db = next(i for i in state["instances"] if i["name"] == "db-server-01")
        db["tags"] = {**(db.get("tags") or {}), "Environment": "production"}
        # Persist tag via apply_action? mutate then save through a no-op — use set via tag action if any
        # Force save by launching nothing — get_state may not write back. Use update via stop/start cycle.
        # Direct cache write through apply create_budget after patching via engine _load
        entry = ae._load(sid)
        for inst in entry["state"]["instances"]:
            if inst.get("name") == "db-server-01":
                inst.setdefault("tags", {})["Environment"] = "production"
        ae._save(sid, entry)

        ae.apply_action(sid, "create_budget", {
            "name": "monthly",
            "amount": 1.0,  # tiny — will exceed with GPU
            "kill_switch": True,
        })
        result = ae.apply_action(sid, "trigger_budget_kill_switch", {
            "name": "monthly",
            "hours": 24,
        })
        self.assertTrue(result.get("ok"), result)
        self.assertTrue(result["stopped"])
        self.assertIn(db["id"], result["skipped_prod"])

        state = ae.get_state(sid, "")["state"]
        db2 = next(i for i in state["instances"] if i["id"] == db["id"])
        self.assertEqual(db2["state"], "running")
        gpu = next(i for i in state["instances"] if i.get("name") == "gpu-dev")
        self.assertIn(gpu["state"], ("stopping", "stopped"))
