"""§X3 — AMI image_manifest must seed the guest OS (packages/kernel/user/SSH)."""

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation import server_identity as si
from apps.labs.provisioner.simulation import shell as sim_shell
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine


LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "ami-guest-seed-tests",
    }
}


def _gpu_manifest(**overrides) -> dict:
    base = {
        "schema_version": 1,
        "sku": "h100",
        "os": "ubuntu-22.04",
        "arch": "x86_64",
        "kernel": "5.15.0-91-generic",
        "default_user": "ubuntu",
        "packages": [
            "cloud-init",
            "qemu-guest-agent",
            "openssh-server",
            "nvidia-driver-535",
        ],
        "services_enabled": ["cloud-init", "sshd", "nvidia-persistenced"],
        "gpu_stack": True,
        "cloud_init_enabled": True,
        "ssh_keys_baked": True,
        "gpu_sanity_failed": False,
        "digest": "sha256:guest-seed-test",
    }
    base.update(overrides)
    return base


@override_settings(CACHES=LOCMEM)
class AmiGuestSeedTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_manifest_seeds_kernel_os_user_packages(self):
        st = RHELOSState(hostname="ip-10-0-0-5")
        st.apply_image_manifest(_gpu_manifest())
        self.assertEqual(st.kernel, "5.15.0-91-generic")
        self.assertIn("Ubuntu", st.os_release)
        self.assertIn("ubuntu", st.users)
        self.assertIn("cloud-init", st.installed_packages)
        self.assertIn("nvidia-driver-535", st.installed_packages)
        self.assertEqual(st.services["sshd"].active, "active")
        self.assertTrue(st.ssh_keys_baked)
        keys = st.read_file("/home/ubuntu/.ssh/authorized_keys") or ""
        self.assertIn("ssh-ed25519", keys)

    def test_uname_and_id_reflect_manifest(self):
        engine = UnifiedSimulationEngine(scenario_slug="aws-golden-image", simulation_type="aws")
        engine.shell.state.apply_image_manifest(_gpu_manifest())
        out = str(engine.shell.run("uname -r"))
        self.assertIn("5.15.0-91-generic", out)
        out = str(engine.shell.run("id ubuntu"))
        self.assertIn("ubuntu", out)

    def test_missing_ssh_keys_refuses_ssh(self):
        sid = "ami-ssh-refuse"
        si.drop_session(sid)
        sim_shell.drop_sim_session(sid)

        man = _gpu_manifest(ssh_keys_baked=False, cloud_init_enabled=True, digest="sha256:nokeys")
        si.upsert_server(
            sid,
            {
                "id": "aws-i-nokeys",
                "hostname": "ip-10-0-1-9",
                "primary_ip": "10.0.1.9",
                "power": "on",
                "os": "ubuntu-22.04",
                "image_manifest": man,
                "tags": {"role": "primary", "appears_in": ["aws", "terminal"]},
            },
            source="aws",
        )
        engine = UnifiedSimulationEngine(scenario_slug="aws-golden-image", simulation_type="aws")
        engine.shell.state.session_id = sid
        engine.shell._host_names = {
            "ip-10-0-1-9": {"name": "ip-10-0-1-9", "ip": "10.0.1.9", "ssh_user": "ubuntu"},
        }
        engine.shell._host_ips = {"10.0.1.9": "ip-10-0-1-9"}
        out = str(engine.shell.run("ssh ubuntu@ip-10-0-1-9"))
        self.assertIn("Connection refused", out)
        blob = out.lower()
        self.assertTrue("authorized_keys" in blob or "publickey" in blob, msg=out)

    def test_gpu_sanity_failed_breaks_nvidia_smi(self):
        st = RHELOSState()
        st.apply_image_manifest(_gpu_manifest(gpu_sanity_failed=True, gpu_stack=True))
        self.assertFalse(st.gpu_healthy)

    def test_sync_aws_applies_manifest_when_engine_present(self):
        sid = "ami-sync-seed"
        si.drop_session(sid)
        sim_shell.drop_sim_session(sid)

        engine = UnifiedSimulationEngine(scenario_slug="aws-golden-image", simulation_type="aws")
        sim_shell.register_sim_session(
            sid, resource_id="r-ami-sync", sim_type="aws", state={"engine": engine},
        )

        man = _gpu_manifest(digest="sha256:sync-apply")
        inst = {
            "id": "i-0abc",
            "state": "running",
            "privateIp": "10.0.2.15",
            "publicIp": "54.1.2.3",
            "type": "g5.xlarge",
            "os": "ubuntu-22.04",
            "amiId": "ami-0golden",
            "amiDigest": man["digest"],
            "manifest": man,
        }
        si.sync_aws_instance(sid, inst)
        self.assertEqual(engine.shell.state.kernel, "5.15.0-91-generic")
        self.assertIn("ubuntu", engine.shell.state.users)
        self.assertIn("nvidia-driver-535", engine.shell.state.installed_packages)
        sim_shell.drop_sim_session(sid)
