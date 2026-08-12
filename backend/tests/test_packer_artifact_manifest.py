"""Packer artifact manifest — the content identity a built image carries forward.

Before this, the only thing a completed build produced was the boolean
`build_succeeded` plus a `has_nvidia_marker` flag derived from grepping the
template. Nothing recorded what was actually installed, so nothing downstream
(AMI import, EC2 guest state, grading) could assert that a specific package,
kernel or driver stack came from a specific build.

These tests pin the two properties the manifest exists to provide:

1. It fails CLOSED. `get_manifest` on a session with no completed build returns
   an error, never an empty dict — a consumer doing `.get("packages", [])` on a
   fabricated default would pass a learner who never built the image, which is
   exactly the fail-open mode the audit flagged.
2. Its content is derived, not asserted. The GPU driver stack appears only when
   the template genuinely provisions it, and the digest changes when the inputs
   change, so "this AMI came from that build" is checkable rather than trusted.
"""

from django.test import SimpleTestCase

from apps.vmware_sim import packer_factory as pf

GPU_TEMPLATE = (
    'build {\n'
    '  sources = ["source.qemu.gpu"]\n'
    '  provisioner "shell" {\n'
    '    inline = ["apt-get install -y nvidia-driver-535"]\n'
    '  }\n'
    '}\n'
)

PLAIN_TEMPLATE = (
    'build {\n'
    '  sources = ["source.qemu.gpu"]\n'
    '  provisioner "shell" {\n'
    '    inline = ["apt-get install -y curl"]\n'
    '  }\n'
    '}\n'
)


def _run_for(template: str, sku: str = "h100") -> dict:
    """Start a pipeline and hand back its active run."""
    state: dict = {}
    pf.start_pipeline(state, {"sku": sku, "template": template})
    return pf._active_run(pf.ensure_factory(state))


class ManifestFailsClosedTests(SimpleTestCase):
    def test_no_build_returns_error_not_empty_manifest(self):
        # A brand-new session has produced no artifact. The caller must be told
        # so, not handed a manifest-shaped blank it can read defaults out of.
        res = pf.get_manifest({})
        self.assertFalse(res["ok"])
        self.assertNotIn("manifest", res)
        self.assertIn("Image Factory", res["error"])

    def test_started_but_unpublished_run_has_no_manifest(self):
        # Starting the pipeline is not building it. Until publish succeeds there
        # is no artifact, so there must be no manifest to grade against.
        state: dict = {}
        pf.start_pipeline(state, {"sku": "h100", "template": GPU_TEMPLATE})
        self.assertFalse(pf.get_manifest(state)["ok"])

    def test_publish_produces_a_versioned_manifest(self):
        state: dict = {}
        pf.start_pipeline(state, {"sku": "h100", "template": GPU_TEMPLATE})
        pf.publish_artifact(state, {"sku": "h100"})

        res = pf.get_manifest(state)
        self.assertTrue(res["ok"], res)
        manifest = res["manifest"]
        # Schema is versioned from day one so a later field addition is
        # detectable rather than silently absent on old session blobs.
        self.assertEqual(manifest["schema_version"], pf.MANIFEST_SCHEMA_VERSION)
        self.assertEqual(res["schema_version"], pf.MANIFEST_SCHEMA_VERSION)


class ManifestContentIsDerivedTests(SimpleTestCase):
    def test_gpu_stack_only_when_template_provisions_it(self):
        gpu = pf.build_manifest(_run_for(GPU_TEMPLATE))
        plain = pf.build_manifest(_run_for(PLAIN_TEMPLATE))

        self.assertTrue(gpu["gpu_stack"])
        self.assertIn("nvidia-driver-535", gpu["packages"])
        self.assertIn("nvidia-persistenced", gpu["services_enabled"])

        # The claim that matters: a template that never installs the driver must
        # not yield a manifest advertising one.
        self.assertFalse(plain["gpu_stack"])
        self.assertNotIn("nvidia-driver-535", plain["packages"])
        self.assertNotIn("nvidia-persistenced", plain["services_enabled"])

    def test_base_packages_always_present(self):
        manifest = pf.build_manifest(_run_for(PLAIN_TEMPLATE))
        for pkg in pf.BASE_PACKAGES:
            self.assertIn(pkg, manifest["packages"])
        self.assertTrue(manifest["cloud_init_enabled"])

    def test_rhel_sku_carries_its_own_base_image_and_kernel(self):
        jammy = pf.build_manifest(_run_for(GPU_TEMPLATE, sku="h100"))
        rhel = pf.build_manifest(_run_for(GPU_TEMPLATE, sku="rhel-gpu"))

        self.assertEqual(jammy["os"], "ubuntu-22.04")
        self.assertEqual(jammy["default_user"], "ubuntu")
        self.assertEqual(rhel["os"], "rhel-9")
        self.assertEqual(rhel["default_user"], "ec2-user")
        self.assertNotEqual(jammy["kernel"], rhel["kernel"])


class ManifestDigestTests(SimpleTestCase):
    def test_digest_is_deterministic_for_identical_inputs(self):
        run = _run_for(GPU_TEMPLATE)
        self.assertEqual(pf.build_manifest(run)["digest"], pf.build_manifest(run)["digest"])

    def test_digest_changes_when_build_content_changes(self):
        # Digest is the artifact's identity. If two genuinely different images
        # shared a digest, "this AMI came from that build" would be unassertable.
        gpu = pf.build_manifest(_run_for(GPU_TEMPLATE))["digest"]
        plain = pf.build_manifest(_run_for(PLAIN_TEMPLATE))["digest"]
        self.assertNotEqual(gpu, plain)

    def test_remediated_build_differs_from_vulnerable_one(self):
        vulnerable = _run_for(GPU_TEMPLATE)
        vulnerable["cve_failed"] = True
        vulnerable["cve_remediated"] = False
        before = pf.build_manifest(vulnerable)

        remediated = dict(vulnerable, cve_failed=True, cve_remediated=True)
        after = pf.build_manifest(remediated)

        # A remediated image is different content, so it must not be mistakable
        # for the one that failed the CVE gate.
        self.assertNotEqual(before["digest"], after["digest"])
        self.assertEqual(before["cve_open"], ["CVE-2024-XXXX"])
        self.assertEqual(after["cve_open"], [])
