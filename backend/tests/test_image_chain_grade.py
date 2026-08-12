"""§X3 / §G2 — Packer → AMI → EC2 → guest chain grading."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation import shell as sim_shell
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.vmware_sim import aws_engine as ae
from apps.vmware_sim import packer_factory as pf
from apps.vmware_sim.image_chain import slug_wants_image_chain, validate_image_chain


GPU_TEMPLATE = (
    'build {\n'
    '  sources = ["source.qemu.gpu"]\n'
    '  provisioner "shell" {\n'
    '    inline = ["apt-get install -y nvidia-driver-535"]\n'
    '  }\n'
    '}\n'
)

LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "image-chain-grade-tests",
    }
}


def _published_manifest() -> dict:
    state: dict = {}
    pf.start_pipeline(state, {"sku": "h100", "template": GPU_TEMPLATE})
    pf.publish_artifact(state, {"sku": "h100"})
    res = pf.get_manifest(state)
    assert res["ok"], res
    return res["manifest"]


@override_settings(CACHES=LOCMEM)
class ImageChainGradeTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _aws(self) -> str:
        sid = "img-chain"
        ae.drop_session(sid)
        ae.get_state(sid, "aws-golden-image-lab")
        return sid

    def test_slug_heuristic(self):
        self.assertTrue(slug_wants_image_chain("aws-golden-image-to-ec2"))
        self.assertTrue(slug_wants_image_chain("academy-aws-import-image-gpu"))
        self.assertFalse(slug_wants_image_chain("academy-aws-001-learn-ec2"))

    def test_fails_without_imported_ami(self):
        ok, reason = validate_image_chain({"amis": [], "instances": [], "region": "us-east-1"}, require={"require_guest": False})
        self.assertFalse(ok)
        self.assertIn("imported ami", reason.lower())

    def test_full_chain_passes_with_guest(self):
        sid = self._aws()
        # Seed packer factory onto the AWS session so digest matching works.
        entry = ae._load(sid)
        pf.start_pipeline(entry["state"], {"sku": "h100", "template": GPU_TEMPLATE})
        pf.publish_artifact(entry["state"], {"sku": "h100"})
        ae._save(sid, entry)
        mres = pf.get_manifest(entry["state"])
        self.assertTrue(mres["ok"], mres)
        manifest = mres["manifest"]

        ae.apply_action(sid, "import_image", {"manifest": manifest, "name": "golden"})
        with __import__("unittest").mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.IMPORT_SECONDS + 1):
            state = ae.get_state(sid)["state"]
        ami = next(a for a in state["amis"] if a.get("name") == "golden")

        launch = ae.apply_action(sid, "launch_instance", {
            "ami_id": ami["id"],
            "instance_type": "t3.micro",
            "name": "from-golden",
        })
        self.assertTrue(launch["ok"], launch)
        with __import__("unittest").mock.patch.object(ae, "_now", return_value=ae.time.time() + ae.PENDING_SECONDS + 1):
            state = ae.get_state(sid)["state"]

        engine = UnifiedSimulationEngine(scenario_slug="aws-golden-image-lab", simulation_type="aws")
        engine.shell.state.apply_image_manifest(manifest)
        sim_shell.drop_sim_session(sid)
        sim_shell.register_sim_session(
            sid, resource_id="r-chain", sim_type="aws", state={"engine": engine},
        )

        ok, reason = validate_image_chain(
            state,
            session_id=sid,
            require={"packages": ["nvidia-driver-535"], "require_gpu_stack": True},
        )
        self.assertTrue(ok, reason)
        sim_shell.drop_sim_session(sid)

    def test_fails_when_guest_missing_package(self):
        st = RHELOSState()
        man = _published_manifest()
        # Apply then strip a required package to simulate drift.
        st.apply_image_manifest(man)
        st.installed_packages.pop("nvidia-driver-535", None)

        aws_state = {
            "region": "us-east-1",
            "amis": [{
                "id": "ami-0test",
                "region": "us-east-1",
                "digest": man["digest"],
                "manifest": man,
                "created": "2024-01-01T00:00:00Z",
            }],
            "instances": [{
                "id": "i-0test",
                "state": "running",
                "amiId": "ami-0test",
                "amiDigest": man["digest"],
            }],
        }
        ok, reason = validate_image_chain(
            aws_state,
            guest_state=st,
            require={"packages": ["nvidia-driver-535"]},
        )
        self.assertFalse(ok)
        self.assertIn("nvidia-driver-535", reason)

    def test_validate_aws_lab_uses_chain_for_golden_slug(self):
        sid = self._aws()
        # Empty world — golden slug should fail closed on chain, not NO_VALIDATION_SCRIPT.
        ok, reason = ae.validate_aws_lab(sid, "aws-golden-image-lab")
        self.assertFalse(ok)
        self.assertNotEqual(reason, "NO_VALIDATION_SCRIPT")
        self.assertIn("AMI", reason)
