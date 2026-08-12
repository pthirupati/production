"""§X3 AMI architecture vs instance-type architecture on launch."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.vmware_sim import aws_engine as ae


LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "aws-arch-mismatch-tests",
    }
}


@override_settings(CACHES=LOCMEM_CACHE)
class AwsArchMismatchTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _sid(self, name="test-aws-arch"):
        ae.drop_session(name)
        ae.get_state(name, "")
        return name

    def test_x86_ami_on_arm_instance_type_is_refused(self):
        sid = self._sid()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0c02fb55956c7d316",
            "instance_type": "t4g.micro",
            "name": "bad-arch",
        })
        self.assertFalse(res.get("ok"))
        self.assertIn("InvalidParameterCombination", res.get("error", ""))
        self.assertIn("x86_64", res.get("error", ""))
        self.assertIn("arm64", res.get("error", ""))

    def test_arm_ami_on_x86_instance_type_is_refused(self):
        sid = self._sid()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0arm64al2023abc01",
            "instance_type": "t2.micro",
            "name": "bad-arch-2",
        })
        self.assertFalse(res.get("ok"))
        self.assertIn("InvalidParameterCombination", res.get("error", ""))

    def test_matching_arm_launch_succeeds(self):
        sid = self._sid()
        res = ae.apply_action(sid, "launch_instance", {
            "ami_id": "ami-0arm64al2023abc01",
            "instance_type": "t4g.micro",
            "name": "good-arm",
        })
        self.assertTrue(res.get("ok"), res)
        self.assertTrue(res.get("instance_ids"))
