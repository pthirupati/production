"""§X3 upstream image checksum/GPG mismatch refuses Packer build."""

from django.test import SimpleTestCase

from apps.vmware_sim.packer_factory import (
    BASE_IMAGES,
    start_pipeline,
    verify_upstream_image,
)


class UpstreamVerifyTests(SimpleTestCase):
    def test_good_checksum_passes(self):
        ok, msg = verify_upstream_image({
            "checksum": BASE_IMAGES["jammy"]["sha256"],
            "gpg_ok": True,
        }, sku="h100")
        self.assertTrue(ok)
        self.assertIn("verified", msg)

    def test_bad_checksum_refuses(self):
        ok, msg = verify_upstream_image({
            "checksum": "sha256:deadbeef",
        }, sku="h100")
        self.assertFalse(ok)
        self.assertIn("checksum mismatch", msg)

    def test_gpg_fail_refuses(self):
        ok, msg = verify_upstream_image({
            "checksum": BASE_IMAGES["jammy"]["sha256"],
            "gpg_ok": False,
        }, sku="h100")
        self.assertFalse(ok)
        self.assertIn("GPG", msg)

    def test_start_pipeline_refuses_on_mismatch(self):
        state = {"broken": {}}
        res = start_pipeline(state, {"sku": "h100", "checksum": "sha256:bad"})
        self.assertFalse(res.get("ok"))
        self.assertIn("checksum mismatch", res.get("error", ""))
        self.assertFalse(state.get("packer_factory", {}).get("artifact_ready"))

    def test_start_pipeline_force_verify_when_broken(self):
        state = {"broken": {"upstream_checksum_mismatch": True}}
        # No checksum supplied → refuse.
        res = start_pipeline(state, {"sku": "h100"})
        self.assertFalse(res.get("ok"))
        self.assertIn("checksum required", res.get("error", ""))
        # Correct checksum clears the gate.
        res2 = start_pipeline(state, {
            "sku": "h100",
            "checksum": BASE_IMAGES["jammy"]["sha256"],
            "gpg_ok": True,
        })
        self.assertTrue(res2.get("ok"), res2)
