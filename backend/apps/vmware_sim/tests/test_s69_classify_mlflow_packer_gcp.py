"""Session 69 polish: llm_classify, MLflow gates, Packer bake cache, GCP images/MIG."""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim.aiml_engine import llm_classify
from apps.vmware_sim.aiml_v2_facades import apply_v2_action, seed_v2, _metrics_from_params
from apps.vmware_sim import packer_factory as pf
from apps.vmware_sim.gcp_engine import _ensure, apply_action as gcp_apply


class LlmClassifyScoreAllTests(TestCase):
    def test_billing_still_wins_on_refund_only(self):
        r = llm_classify("I need a refund on my invoice")
        self.assertEqual(r["category"], "billing")

    def test_security_beats_billing_on_overlap(self):
        r = llm_classify("urgent refund after account was hacked in a breach")
        self.assertEqual(r["category"], "security")
        self.assertEqual(r["priority"], "high")

    def test_confidence_scales_with_hits(self):
        weak = llm_classify("refund")
        strong = llm_classify("refund invoice payment billing overcharged")
        self.assertGreater(strong["confidence"], weak["confidence"])


class MlflowFacadeTests(TestCase):
    def test_metrics_deterministic_and_param_sensitive(self):
        a = _metrics_from_params({"lr": "2e-5", "epochs": 5, "bs": 32})
        b = _metrics_from_params({"lr": "2e-5", "epochs": 5, "bs": 32})
        self.assertEqual(a, b)
        bad = _metrics_from_params({"lr": "0.1", "epochs": 1, "bs": 512})
        self.assertGreater(a["acc"], bad["acc"])

    def test_log_run_uses_params_not_random(self):
        st = seed_v2()
        r1 = apply_v2_action(st, "log_run", {"params": {"lr": "2e-5", "epochs": 5, "bs": 32}})
        r2 = apply_v2_action(st, "log_run", {"params": {"lr": "2e-5", "epochs": 5, "bs": 32}})
        self.assertEqual(r1["run"]["metrics"], r2["run"]["metrics"])

    def test_stage_gate_and_rollback(self):
        st = seed_v2()
        apply_v2_action(st, "register_model", {
            "name": "gate-model", "run_id": "run_bcd456", "stage": "None",
        })
        bad = apply_v2_action(st, "transition_model_stage", {
            "name": "gate-model", "stage": "Production",
        })
        self.assertFalse(bad.get("ok"))

        ok_stage = apply_v2_action(st, "transition_model_stage", {
            "name": "gate-model", "stage": "Staging",
        })
        self.assertTrue(ok_stage.get("ok"))

        low = apply_v2_action(st, "log_run", {
            "params": {"lr": "0.5", "epochs": 1, "bs": 1024},
            "name": "low-run",
        })
        apply_v2_action(st, "register_model", {
            "name": "gate-model", "run_id": low["run"]["id"],
        })
        refuse = apply_v2_action(st, "transition_model_stage", {
            "name": "gate-model", "stage": "Production",
        })
        self.assertFalse(refuse.get("ok"))
        self.assertIn("Production gate", refuse.get("error", ""))

        high = apply_v2_action(st, "log_run", {
            "params": {"lr": "2e-5", "epochs": 8, "bs": 32},
        })
        apply_v2_action(st, "register_model", {
            "name": "gate-model", "run_id": high["run"]["id"],
        })
        model = next(m for m in st["model_registry"] if m["name"] == "gate-model")
        model["stage"] = "Staging"
        promo = apply_v2_action(st, "transition_model_stage", {
            "name": "gate-model", "stage": "Production",
        })
        self.assertTrue(promo.get("ok"), promo)

        newer = apply_v2_action(st, "log_run", {
            "params": {"lr": "2e-5", "epochs": 8, "bs": 32},
        })
        old_id = high["run"]["id"]
        apply_v2_action(st, "register_model", {
            "name": "gate-model", "run_id": newer["run"]["id"],
        })
        rb = apply_v2_action(st, "rollback_model_stage", {"name": "gate-model"})
        self.assertTrue(rb.get("ok"), rb)
        model = next(m for m in st["model_registry"] if m["name"] == "gate-model")
        self.assertEqual(model["stage"], "Staging")
        self.assertEqual(model["run_id"], old_id)


class PackerBakeCacheTests(TestCase):
    def test_warm_rebuild_hits_cache_and_reorder_regresses(self):
        state = {}
        tmpl = (
            'provisioner "shell" {\n  inline = ["apt-get update"]\n}\n'
            'provisioner "shell" {\n  inline = ["nvidia-driver install"]\n}\n'
        )
        files = {"scripts/install.sh": "echo ok\n"}
        cold = pf.start_pipeline(state, {"sku": "h100", "template": tmpl, "files": files})
        self.assertTrue(cold.get("ok"), cold)
        self.assertEqual(cold.get("cache_hits"), 0)
        cold_bake = cold.get("bake_seconds")
        self.assertGreater(cold_bake, 30)

        warm = pf.start_pipeline(state, {"sku": "h100", "template": tmpl, "files": files})
        self.assertTrue(warm.get("ok"), warm)
        self.assertGreater(warm.get("cache_hits"), 0)
        self.assertLess(warm.get("bake_seconds"), cold_bake)

        reordered = (
            'provisioner "shell" {\n  inline = ["nvidia-driver install"]\n}\n'
            'provisioner "shell" {\n  inline = ["apt-get update"]\n}\n'
        )
        regress = pf.start_pipeline(state, {
            "sku": "h100",
            "template": reordered,
            "files": files,
        })
        self.assertTrue(regress.get("ok"), regress)
        self.assertLess(regress.get("cache_hits"), warm.get("cache_hits"))


class GcpImageMigTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "s69-gcp-img"

    def test_import_family_shielded_and_mig_roll(self):
        cache.clear()
        _ensure(self.sid, "")
        gcp_apply(self.sid, "login", {})

        bad = gcp_apply(self.sid, "import_image", {"name": "bad"})
        self.assertFalse(bad.get("ok"))

        manifest = {
            "schema_version": 1,
            "digest": "sha256:abc123deadbeef",
            "sku": "h100",
            "arch": "x86_64",
        }
        imp = gcp_apply(self.sid, "import_image", {
            "name": "golden-v1",
            "family": "fixitlab-golden",
            "manifest": manifest,
            "signed": True,
        })
        self.assertTrue(imp.get("ok"), imp)

        unsigned = gcp_apply(self.sid, "create_image", {
            "name": "unsigned-v1", "family": "other-family", "signed": False,
        })
        self.assertTrue(unsigned.get("ok"))

        refuse = gcp_apply(self.sid, "create_instance", {
            "name": "secure-vm",
            "image": "unsigned-v1",
            "shielded_secure_boot": True,
        })
        self.assertFalse(refuse.get("ok"))
        self.assertIn("Secure Boot", refuse.get("error", ""))

        ok_vm = gcp_apply(self.sid, "create_instance", {
            "name": "secure-vm2",
            "image": "golden-v1",
            "shielded_secure_boot": True,
        })
        self.assertTrue(ok_vm.get("ok"), ok_vm)
        self.assertEqual(ok_vm["instance"].get("source_image"), "golden-v1")

        tmpl = gcp_apply(self.sid, "create_instance_template", {
            "name": "tmpl-v1", "image": "golden-v1",
        })
        self.assertTrue(tmpl.get("ok"), tmpl)
        mig = gcp_apply(self.sid, "create_mig", {
            "name": "web-mig", "template": "tmpl-v1", "size": 2,
        })
        self.assertTrue(mig.get("ok"), mig)

        gcp_apply(self.sid, "import_image", {
            "name": "golden-v2",
            "family": "fixitlab-golden",
            "manifest": {**manifest, "digest": "sha256:newdigest99"},
            "signed": True,
        })
        gcp_apply(self.sid, "create_instance_template", {
            "name": "tmpl-v2", "image": "golden-v2",
        })
        roll = gcp_apply(self.sid, "rolling_update_mig", {
            "name": "web-mig", "template": "tmpl-v2", "batch": 1,
        })
        self.assertTrue(roll.get("ok"), roll)
        self.assertEqual(roll.get("updated"), 1)
        digests = {i.get("image_digest") for i in roll["mig"]["instances"]}
        self.assertEqual(len(digests), 2)
