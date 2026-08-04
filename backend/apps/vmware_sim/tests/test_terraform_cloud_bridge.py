"""Terraform apply → AWS/Azure/GCP console mirror (S1.5 / TODO 134, 231)."""
from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import aws_engine as ae
from apps.vmware_sim import azure_engine as aze
from apps.vmware_sim import gcp_engine as gce
from apps.vmware_sim import engine as ve
from apps.vmware_sim import terraform_engine as te


MULTI_CLOUD_MAIN = """
provider "aws" { region = "us-east-1" }
provider "azurerm" { features {} }
provider "google" { project = "lab" }

resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.micro"
  tags = { Name = "web-server" }
}

resource "azurerm_linux_virtual_machine" "app" {
  name = "app-vm"
  size = "Standard_B2s"
}

resource "google_compute_instance" "batch" {
  name         = "batch-1"
  machine_type = "e2-medium"
  zone         = "us-central1-a"
}
"""

VSPHERE_MAIN = """
provider "vsphere" {}

resource "vsphere_virtual_machine" "web01" {
  name = "web01"
}
"""

MAAS_LXD_MAIN = """
provider "maas" {}
provider "lxd" {}

resource "maas_machine" "gpu_node" {
  hostname = "gpu_node"
}

resource "lxd_instance" "batch" {
  name  = "batch"
  image = "ubuntu:22.04"
}
"""


class TerraformCloudBridgeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "test-tf-cloud-bridge"
        for drop in (te.drop_session, ae.drop_session, aze.drop_session, gce.drop_session, ve.drop_session):
            drop(self.sid)
        from apps.vmware_sim import baremetal_engine as be
        be.drop_session(self.sid)

    def tearDown(self):
        cache.clear()

    def _boot(self, main_tf: str):
        te.get_state(self.sid, "tf-cloud-bridge")
        te.apply_action(self.sid, "save_files", {
            "files": {
                "main.tf": main_tf,
                "variables.tf": 'variable "ami_id" { default = "ami-0c55b159cbfafe1f0" }\n',
                "outputs.tf": "",
            },
            "active_file": "main.tf",
        })
        te.apply_action(self.sid, "terraform_init", {})
        plan = te.apply_action(self.sid, "terraform_plan", {})
        self.assertTrue(plan.get("ok"), plan)
        return plan

    def test_parse_tf_resources(self):
        parsed = te._parse_tf_resources(MULTI_CLOUD_MAIN)
        types = {r["type"] for r in parsed}
        self.assertEqual(types, {
            "aws_instance",
            "azurerm_linux_virtual_machine",
            "google_compute_instance",
        })
        links = te._cloud_links_from_resources(parsed)
        self.assertTrue(links["aws"])
        self.assertTrue(links["azure"])
        self.assertTrue(links["gcp"])

    def test_apply_mirrors_into_aws_azure_gcp(self):
        self._boot(MULTI_CLOUD_MAIN)
        res = te.apply_action(self.sid, "terraform_apply", {})
        self.assertTrue(res.get("ok"), res)
        self.assertTrue(res.get("cloud_links", {}).get("aws"))
        self.assertTrue(res.get("cloud_links", {}).get("azure"))
        self.assertTrue(res.get("cloud_links", {}).get("gcp"))
        self.assertIn("Cloud consoles updated", res.get("output") or "")

        aws_inst = ae.get_state(self.sid)["state"].get("instances") or []
        live = [i for i in aws_inst if (i.get("state") or "") != "terminated"]
        self.assertTrue(any(
            i.get("name") == "web-server" or (i.get("tags") or {}).get("Name") == "web-server"
            for i in live
        ), aws_inst)

        azure_vms = aze.get_state(self.sid)["state"].get("vms") or []
        self.assertTrue(any(v.get("name") == "app" for v in azure_vms), azure_vms)

        gcp_inst = gce.get_state(self.sid)["state"].get("instances") or []
        self.assertTrue(any(i.get("name") == "batch" for i in gcp_inst), gcp_inst)

    def test_apply_idempotent_no_duplicate_aws(self):
        self._boot(MULTI_CLOUD_MAIN)
        te.apply_action(self.sid, "terraform_apply", {})
        n1 = len([
            i for i in (ae.get_state(self.sid)["state"].get("instances") or [])
            if (i.get("state") or "") != "terminated"
        ])
        # Re-plan + re-apply (same names) must not spawn another EC2.
        te.apply_action(self.sid, "terraform_plan", {})
        te.apply_action(self.sid, "terraform_apply", {})
        n2 = len([
            i for i in (ae.get_state(self.sid)["state"].get("instances") or [])
            if (i.get("state") or "") != "terminated"
        ])
        self.assertEqual(n1, n2)

        azure_vms = aze.get_state(self.sid)["state"].get("vms") or []
        self.assertEqual(sum(1 for v in azure_vms if v.get("name") == "app"), 1)
        gcp_inst = gce.get_state(self.sid)["state"].get("instances") or []
        self.assertEqual(sum(1 for i in gcp_inst if i.get("name") == "batch"), 1)

    def test_plan_includes_cloud_links(self):
        plan = self._boot(MULTI_CLOUD_MAIN)
        links = (plan.get("plan") or {}).get("cloud_links") or {}
        self.assertTrue(links.get("aws"))
        self.assertTrue(links.get("azure"))
        self.assertTrue(links.get("gcp"))
        self.assertGreaterEqual((plan.get("plan") or {}).get("add", 0), 3)

    def test_apply_mirrors_vsphere_into_vmware(self):
        self._boot(VSPHERE_MAIN)
        res = te.apply_action(self.sid, "terraform_apply", {})
        self.assertTrue(res.get("ok"), res)
        self.assertTrue(res.get("cloud_links", {}).get("vmware"))
        vms = (ve.get_state(self.sid).get("inventory") or {}).get("vms") or []
        self.assertTrue(any(v.get("name") == "web01" for v in vms), vms)
        # Idempotent re-apply
        te.apply_action(self.sid, "terraform_plan", {})
        te.apply_action(self.sid, "terraform_apply", {})
        vms2 = (ve.get_state(self.sid).get("inventory") or {}).get("vms") or []
        self.assertEqual(sum(1 for v in vms2 if v.get("name") == "web01"), 1)

    def test_destroy_removes_mirrored_cloud_resources(self):
        self._boot(MULTI_CLOUD_MAIN)
        te.apply_action(self.sid, "terraform_apply", {})
        res = te.apply_action(self.sid, "terraform_destroy", {})
        self.assertTrue(res.get("ok"), res)
        self.assertIn("Destroy complete", res.get("output") or "")
        self.assertGreaterEqual(res.get("destroyed") or 0, 3)

        aws_live = [
            i for i in (ae.get_state(self.sid)["state"].get("instances") or [])
            if (i.get("state") or "") not in ("terminated", "shutting-down")
            and (
                i.get("name") == "web-server"
                or (i.get("tags") or {}).get("Name") == "web-server"
            )
        ]
        self.assertEqual(aws_live, [], aws_live)

        azure_vms = aze.get_state(self.sid)["state"].get("vms") or []
        self.assertFalse(any(v.get("name") == "app" for v in azure_vms), azure_vms)

        gcp_inst = gce.get_state(self.sid)["state"].get("instances") or []
        self.assertFalse(any(i.get("name") == "batch" for i in gcp_inst), gcp_inst)

    def test_destroy_removes_vsphere_vm(self):
        self._boot(VSPHERE_MAIN)
        te.apply_action(self.sid, "terraform_apply", {})
        res = te.apply_action(self.sid, "terraform_destroy", {})
        self.assertTrue(res.get("ok"), res)
        vms = (ve.get_state(self.sid).get("inventory") or {}).get("vms") or []
        self.assertFalse(any(v.get("name") == "web01" for v in vms), vms)

    def test_apply_mirrors_maas_and_lxd(self):
        from apps.vmware_sim import baremetal_engine as be

        self._boot(MAAS_LXD_MAIN)
        res = te.apply_action(self.sid, "terraform_apply", {})
        self.assertTrue(res.get("ok"), res)
        self.assertTrue(res.get("cloud_links", {}).get("maas"))
        self.assertTrue(res.get("cloud_links", {}).get("lxd"))

        st = (be.get_state(self.sid).get("state") or {})
        machines = (st.get("maas") or {}).get("machines") or []
        self.assertTrue(any(m.get("hostname") == "gpu_node" for m in machines), machines)
        containers = (st.get("lxd") or {}).get("containers") or []
        self.assertTrue(any(c.get("name") == "batch" for c in containers), containers)

        # Idempotent re-apply
        te.apply_action(self.sid, "terraform_plan", {})
        te.apply_action(self.sid, "terraform_apply", {})
        st2 = (be.get_state(self.sid).get("state") or {})
        self.assertEqual(
            sum(1 for m in ((st2.get("maas") or {}).get("machines") or []) if m.get("hostname") == "gpu_node"),
            1,
        )
        self.assertEqual(
            sum(1 for c in ((st2.get("lxd") or {}).get("containers") or []) if c.get("name") == "batch"),
            1,
        )

    def test_destroy_removes_maas_and_lxd(self):
        from apps.vmware_sim import baremetal_engine as be

        self._boot(MAAS_LXD_MAIN)
        te.apply_action(self.sid, "terraform_apply", {})
        res = te.apply_action(self.sid, "terraform_destroy", {})
        self.assertTrue(res.get("ok"), res)
        st = (be.get_state(self.sid).get("state") or {})
        machines = (st.get("maas") or {}).get("machines") or []
        self.assertFalse(any(m.get("hostname") == "gpu_node" for m in machines), machines)
        containers = (st.get("lxd") or {}).get("containers") or []
        self.assertFalse(any(c.get("name") == "batch" for c in containers), containers)
