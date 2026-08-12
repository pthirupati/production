"""§X3 AMI missing ENA driver vs Nitro instance type on launch."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-ena-mismatch-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsEnaMismatchTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-ena"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_no_ena_ami_on_nitro_is_refused(self):
        sid = self._sid()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0noenalegacy00001",
            "instance_type": "t3.micro",
            "name": "no-ena-nitro",
        })
        self.assertFalse(res.get("ok"))
        self.assertIn("InvalidParameterCombination", res.get("error", ""))
        self.assertIn("ENA", res.get("error", ""))

    def test_no_ena_ami_on_classic_t2_succeeds(self):
        sid = self._sid()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0noenalegacy00001",
            "instance_type": "t2.micro",
            "name": "no-ena-classic",
        })
        self.assertTrue(res.get("ok"), res)

    def test_modern_ami_on_nitro_succeeds(self):
        sid = self._sid()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0c02fb55956c7d316",
            "instance_type": "t3.micro",
            "name": "ena-ok",
        })
        self.assertTrue(res.get("ok"), res)

    def test_imported_manifest_without_ena_refused_on_nitro(self):
        sid = self._sid()
        entry = ae._load(sid)
        entry["state"].setdefault("amis", []).append({
            "id": "ami-imported-no-ena",
            "arch": "x86_64",
            "os": "ubuntu-22.04",
            "manifest": {"ena_driver": False, "digest": "sha256:abc", "os": "ubuntu-22.04", "arch": "x86_64"},
        })
        ae._save(sid, entry)
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-imported-no-ena",
            "instance_type": "c5.large",
            "name": "imported-no-ena",
        })
        self.assertFalse(res.get("ok"))
        self.assertIn("ENA", res.get("error", ""))
