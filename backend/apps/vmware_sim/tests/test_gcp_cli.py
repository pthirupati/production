"""Tests for the `gcloud` / `gsutil` CLI surface over the GCP engine.

The CLI is an alias for the Cloud Console click actions, so the tests assert on
the graded outcome (`broken` cleared, validate_gcp_lab passing) rather than on
the printed text — a CLI that renders nicely but does not move state is exactly
the failure mode this surface exists to avoid.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import gcp_engine as ge


class GcpCliBaseTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "", *, login: bool = True) -> str:
        sid = f"test-gcp-cli-{slug or 'plain'}"
        ge.drop_session(sid)
        ge.get_state(sid, slug)
        if login:
            ge.apply_action(sid, "login", {"user": "admin@fixitlab.io"})
        return sid


class CliContractTests(GcpCliBaseTest):
    def test_unknown_group_is_a_nonzero_error(self):
        sid = self._session()
        res = ge.run_command(sid, "gcloud frobnicate list")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)
        self.assertIn("frobnicate", res["stderr"])

    def test_unknown_subcommand_is_a_nonzero_error(self):
        sid = self._session()
        res = ge.run_command(sid, "gcloud compute instances frobnicate web01")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_unknown_binary_rejected(self):
        sid = self._session()
        res = ge.run_command(sid, "kubectl get pods")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_requires_authentication(self):
        sid = self._session(login=False)
        res = ge.run_command(sid, "gcloud compute instances list")
        self.assertFalse(res["ok"])
        self.assertIn("active account", res["stderr"])

    def test_missing_required_flag_errors(self):
        sid = self._session()
        res = ge.run_command(sid, "gcloud compute instances set-machine-type web01")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_equals_and_space_flag_forms_are_equivalent(self):
        _, opts_a = ge._gc_parse(["create", "vm1", "--machine-type=e2-standard-2"])
        _, opts_b = ge._gc_parse(["create", "vm1", "--machine-type", "e2-standard-2"])
        self.assertEqual(opts_a["machine_type"], "e2-standard-2")
        self.assertEqual(opts_a, opts_b)


class CliReadTests(GcpCliBaseTest):
    def test_instances_list_reflects_engine_state(self):
        sid = self._session()
        res = ge.run_command(sid, "gcloud compute instances list")
        self.assertTrue(res["ok"])
        self.assertIn("web01", res["stdout"])
        self.assertIn("us-central1-a", res["stdout"])

    def test_describe_unknown_instance_errors(self):
        sid = self._session()
        res = ge.run_command(sid, "gcloud compute instances describe nope-99")
        self.assertFalse(res["ok"])
        self.assertIn("was not found", res["stderr"])

    def test_firewall_and_disk_listings(self):
        sid = self._session()
        self.assertIn("allow-http", ge.run_command(sid, "gcloud compute firewall-rules list")["stdout"])
        self.assertIn("disk-data-unattached", ge.run_command(sid, "gcloud compute disks list")["stdout"])
        self.assertIn("vpc-prod", ge.run_command(sid, "gcloud compute networks list")["stdout"])

    def test_gsutil_ls_lists_buckets_and_objects(self):
        sid = self._session()
        self.assertIn("gs://fixitlab-prod-assets/", ge.run_command(sid, "gsutil ls")["stdout"])
        listing = ge.run_command(sid, "gsutil ls gs://fixitlab-prod-assets")
        self.assertIn("app/config.json", listing["stdout"])

    def test_gsutil_ls_missing_bucket_errors(self):
        sid = self._session()
        res = ge.run_command(sid, "gsutil ls gs://no-such-bucket")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)


class CliGradedOutcomeTests(GcpCliBaseTest):
    """Solving via CLI must clear the same flags the console clears."""

    def test_firewall_rule_via_cli_clears_ssh_block(self):
        sid = self._session("gcp-firewall-ssh-blocked")
        self.assertFalse(ge.validate_gcp_lab(sid)[0])

        res = ge.run_command(
            sid,
            "gcloud compute firewall-rules create allow-ssh --allow tcp:22 "
            "--source-ranges 0.0.0.0/0 --target-tags web",
        )
        self.assertTrue(res["ok"], res)

        ok, reason = ge.validate_gcp_lab(sid)
        self.assertTrue(ok, reason)

    def test_attach_disk_via_cli_clears_disk_flag(self):
        sid = self._session("gcp-disk-attach")
        self.assertFalse(ge.validate_gcp_lab(sid)[0])

        res = ge.run_command(
            sid, "gcloud compute instances attach-disk web01 --disk=disk-data-unattached")
        self.assertTrue(res["ok"], res)

        ok, reason = ge.validate_gcp_lab(sid)
        self.assertTrue(ok, reason)

    def test_start_instance_via_cli_clears_stopped_flag(self):
        sid = self._session("gcp-vm-power-start")
        state = ge.get_state(sid, "gcp-vm-power-start")["state"]
        self.assertEqual(state["broken"].get("vm_stopped"), "web01")

        res = ge.run_command(sid, "gcloud compute instances start web01")
        self.assertTrue(res["ok"], res)

        after = ge.get_state(sid)["state"]
        self.assertNotIn("vm_stopped", after["broken"])

    def test_set_machine_type_via_cli_requires_stopped_instance(self):
        sid = self._session("gcp-vm-undersized")
        # Real gcloud refuses this while the VM runs; the CLI must not soften it.
        running = ge.run_command(
            sid, "gcloud compute instances set-machine-type web01 --machine-type=e2-standard-2")
        self.assertFalse(running["ok"])

        ge.apply_action(sid, "stop_instance", {"instance_name": "web01"})
        res = ge.run_command(
            sid, "gcloud compute instances set-machine-type web01 --machine-type=e2-standard-2")
        self.assertTrue(res["ok"], res)
        self.assertNotIn("vm_undersized", ge.get_state(sid)["state"]["broken"])

    def test_set_machine_type_rejects_unknown_type(self):
        sid = self._session("gcp-vm-undersized")
        ge.apply_action(sid, "stop_instance", {"instance_name": "web01"})
        res = ge.run_command(
            sid, "gcloud compute instances set-machine-type web01 --machine-type=e2-enormous")
        self.assertFalse(res["ok"])

    def test_bucket_create_and_delete_via_gsutil(self):
        sid = self._session()
        self.assertTrue(ge.run_command(sid, "gsutil mb gs://lab-scratch")["ok"])
        self.assertIn("gs://lab-scratch/", ge.run_command(sid, "gsutil ls")["stdout"])
        self.assertTrue(ge.run_command(sid, "gsutil rb gs://lab-scratch")["ok"])
        self.assertNotIn("lab-scratch", ge.run_command(sid, "gsutil ls")["stdout"])

    def test_iam_binding_add_and_remove_via_cli(self):
        sid = self._session()
        add = ge.run_command(
            sid,
            "gcloud projects add-iam-policy-binding fixitlab-prod "
            "--member=user:new@fixitlab.io --role=roles/viewer",
        )
        self.assertTrue(add["ok"], add)
        self.assertIn("new@fixitlab.io", ge.run_command(sid, "gcloud projects get-iam-policy")["stdout"])

        rm = ge.run_command(
            sid,
            "gcloud projects remove-iam-policy-binding fixitlab-prod "
            "--member=user:new@fixitlab.io --role=roles/viewer",
        )
        self.assertTrue(rm["ok"], rm)

    def test_firewall_delete_refuses_system_rule(self):
        sid = self._session()
        res = ge.run_command(sid, "gcloud compute firewall-rules delete default-deny-ingress")
        self.assertFalse(res["ok"])
