"""§X3 Packer → AMI import bridge.

Measured gap (2026-08-10): packer_factory emits a content manifest and its
docstrings name aws_engine import-image as the consumer, but aws_engine only
had CreateImage (snapshot of a running instance). These tests pin the fail-
closed contract the audit requires:

* no manifest → Disk validation failed, no AMI
* digest mismatch → Disk validation failed
* successful import → async task → registered AMI carrying the digest
* launch of unknown AMI → InvalidAMIID.NotFound
* quarantined (open CVE) AMI → launch refused
"""

from unittest import mock

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae
from apps.vmware_sim import packer_factory as pf


GPU_TEMPLATE = (
    'build {\n'
    '  sources = ["source.qemu.gpu"]\n'
    '  provisioner "shell" {\n'
    '    inline = ["apt-get install -y nvidia-driver-535"]\n'
    '  }\n'
    '}\n'
)

LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-import-image-tests",
    }
}


def _published_manifest() -> dict:
    state: dict = {}
    pf.start_pipeline(state, {"sku": "h100", "template": GPU_TEMPLATE})
    pf.publish_artifact(state, {"sku": "h100"})
    res = pf.get_manifest(state)
    assert res["ok"], res
    return res["manifest"]


@override_settings(CACHES=LOCMEM_CACHE)
class AwsImportImageTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self) -> str:
        sid = "test-aws-import"
        ae.drop_session(sid)
        ae.get_state(sid, "")
        return sid

    def test_import_without_manifest_fails_closed(self):
        sid = self._session()
        res = ae.apply_action(sid, "import_image", {})
        self.assertFalse(res["ok"])
        self.assertIn("Disk validation failed", res["error"])
        state = ae.get_state(sid)["state"]
        self.assertEqual(state.get("importImageTasks") or [], [])

    def test_import_digest_mismatch_fails(self):
        sid = self._session()
        manifest = _published_manifest()
        res = ae.apply_action(sid, "import_image", {
            "manifest": manifest,
            "digest": "sha256:deadbeef",
        })
        self.assertFalse(res["ok"])
        self.assertIn("digest mismatch", res["error"].lower())

    def test_import_registers_ami_after_lifecycle(self):
        sid = self._session()
        manifest = _published_manifest()
        res = ae.apply_action(sid, "import_image", {
            "manifest": manifest,
            "name": "gpu-golden",
        })
        self.assertTrue(res["ok"], res)
        task_id = res["import_task_id"]

        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.IMPORT_SECONDS + 1):
            state = ae.get_state(sid)["state"]

        task = next(t for t in state["importImageTasks"] if t["id"] == task_id)
        self.assertEqual(task["status"], "completed")
        self.assertEqual(task["progress"], 100)
        ami_id = task["ami_id"]
        ami = next(a for a in state["amis"] if a["id"] == ami_id)
        self.assertEqual(ami["digest"], manifest["digest"])
        self.assertEqual(ami["manifest"]["digest"], manifest["digest"])
        self.assertFalse(ami["quarantined"])

        launch = ae.apply_action(sid, "launch_instance", {
            "ami_id": ami_id,
            "instance_type": "t3.micro",
            "name": "from-golden",
        })
        self.assertTrue(launch["ok"], launch)
        iid = launch["instance_ids"][0]
        inst = ae._find_instance(ae.get_state(sid)["state"], iid)
        self.assertEqual(inst["amiId"], ami_id)
        self.assertEqual(inst["amiDigest"], manifest["digest"])
        self.assertEqual(inst["manifest"]["packages"], manifest["packages"])

    def test_unknown_ami_launch_is_not_found(self):
        sid = self._session()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0doesnotexist0001",
            "instance_type": "t3.micro",
        })
        self.assertFalse(res["ok"])
        self.assertIn("InvalidAMIID.NotFound", res["error"])

    def test_quarantined_ami_blocks_launch(self):
        sid = self._session()
        manifest = _published_manifest()
        # Open CVE → quarantined AMI (mirrors unremediated vuln-scan).
        dirty = {**manifest, "cve_open": ["CVE-2024-XXXX"], "cve_remediated": False}
        ae.apply_action(sid, "import_image", {"manifest": dirty, "name": "dirty"})
        with mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.IMPORT_SECONDS + 1):
            state = ae.get_state(sid)["state"]
        ami = next(a for a in state["amis"] if a.get("name") == "dirty")
        self.assertTrue(ami["quarantined"])
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": ami["id"],
            "instance_type": "t3.micro",
        })
        self.assertFalse(res["ok"])
        self.assertIn("quarantined", res["error"].lower())
