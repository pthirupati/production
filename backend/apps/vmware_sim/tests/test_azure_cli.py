"""Tests for the `az` CLI surface over the Azure engine.

Asserts the graded outcome rather than the printed text: an `az` layer that
renders convincingly but never moves the engine's `broken` flags would leave
labs ungradeable, which is the specific hazard this surface exists to avoid.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import azure_engine as ae


class AzureCliBaseTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _session(self, slug: str = "", *, login: bool = True) -> str:
        sid = f"test-az-cli-{slug or 'plain'}"
        ae.drop_session(sid)
        ae.get_state(sid, slug)
        if login:
            ae.apply_action(sid, "login", {"user": "admin@fixitlab.onmicrosoft.com"})
        return sid


class CliContractTests(AzureCliBaseTest):
    def test_unknown_group_is_a_nonzero_error(self):
        sid = self._session()
        res = ae.run_command(sid, "az frobnicate list")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)
        self.assertIn("frobnicate", res["stderr"])

    def test_unknown_subcommand_is_a_nonzero_error(self):
        sid = self._session()
        res = ae.run_command(sid, "az vm frobnicate --name vm-web01")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_non_az_binary_rejected(self):
        sid = self._session()
        res = ae.run_command(sid, "gcloud compute instances list")
        self.assertFalse(res["ok"])
        self.assertNotEqual(res["rc"], 0)

    def test_requires_login(self):
        sid = self._session(login=False)
        res = ae.run_command(sid, "az vm list")
        self.assertFalse(res["ok"])
        self.assertIn("az login", res["stderr"])

    def test_short_flag_aliases_map_to_long_names(self):
        _, opts = ae._az_parse(["create", "-n", "vm1", "-g", "rg-a", "-l", "westus"])
        self.assertEqual(opts["name"], "vm1")
        self.assertEqual(opts["resource_group"], "rg-a")
        self.assertEqual(opts["location"], "westus")

    def test_equals_form_parses(self):
        _, opts = ae._az_parse(["resize", "--size=Standard_D2s_v5"])
        self.assertEqual(opts["size"], "Standard_D2s_v5")

    def test_missing_required_flag_errors(self):
        sid = self._session()
        res = ae.run_command(sid, "az vm resize --name vm-web01")
        self.assertFalse(res["ok"])
        self.assertIn("--size", res["stderr"])


class CliReadTests(AzureCliBaseTest):
    def test_vm_list_reflects_engine_state(self):
        sid = self._session()
        res = ae.run_command(sid, "az vm list --output table")
        self.assertTrue(res["ok"])
        self.assertIn("vm-web01", res["stdout"])
        self.assertIn("rg-fixitlab-prod", res["stdout"])

    def test_vm_show_unknown_vm_errors(self):
        sid = self._session()
        res = ae.run_command(sid, "az vm show --name nope-99")
        self.assertFalse(res["ok"])
        self.assertIn("was not found", res["stderr"])

    def test_resource_listings(self):
        sid = self._session()
        self.assertIn("disk-data-unattached", ae.run_command(sid, "az disk list")["stdout"])
        self.assertIn("nsg-web", ae.run_command(sid, "az network nsg list")["stdout"])
        self.assertIn("vnet-prod", ae.run_command(sid, "az network vnet list")["stdout"])
        self.assertIn("stfixitlabprod", ae.run_command(sid, "az storage account list")["stdout"])
        self.assertIn("rg-fixitlab-prod", ae.run_command(sid, "az group list")["stdout"])

    def test_nsg_rule_list_shows_seeded_rules(self):
        sid = self._session()
        out = ae.run_command(sid, "az network nsg rule list --nsg-name nsg-web")["stdout"]
        self.assertIn("AllowHTTP", out)
        self.assertIn("DenyAllInbound", out)


class CliGradedOutcomeTests(AzureCliBaseTest):
    def test_nsg_rule_via_cli_clears_ssh_block(self):
        sid = self._session("azure-nsg-ssh-blocked")
        self.assertFalse(ae.validate_azure_lab(sid)[0])

        res = ae.run_command(
            sid,
            "az network nsg rule create --nsg-name nsg-web --name AllowSSH "
            "--priority 110 --destination-port-range 22 --access Allow --protocol TCP",
        )
        self.assertTrue(res["ok"], res)

        ok, reason = ae.validate_azure_lab(sid)
        self.assertTrue(ok, reason)

    def test_attach_disk_via_cli_clears_disk_flag(self):
        sid = self._session("azure-disk-attach")
        self.assertFalse(ae.validate_azure_lab(sid)[0])

        res = ae.run_command(
            sid, "az vm disk attach --vm-name vm-web01 --disk disk-data-unattached")
        self.assertTrue(res["ok"], res)

        ok, reason = ae.validate_azure_lab(sid)
        self.assertTrue(ok, reason)

    def test_double_attach_is_rejected(self):
        sid = self._session("azure-disk-attach")
        ae.run_command(sid, "az vm disk attach --vm-name vm-web01 --disk disk-data-unattached")
        second = ae.run_command(sid, "az vm disk attach --vm-name vm-web01 --disk disk-data-unattached")
        self.assertFalse(second["ok"])

    def test_start_vm_via_cli_clears_stopped_flag(self):
        sid = self._session("azure-vm-power-start")
        state = ae.get_state(sid, "azure-vm-power-start")["state"]
        self.assertEqual(state["broken"].get("vm_stopped"), "vm-web01")

        res = ae.run_command(sid, "az vm start --name vm-web01")
        self.assertTrue(res["ok"], res)
        self.assertNotIn("vm_stopped", ae.get_state(sid)["state"]["broken"])

    def test_resize_via_cli_clears_undersized_flag(self):
        sid = self._session("azure-vm-undersized")
        res = ae.run_command(sid, "az vm resize --name vm-web01 --size Standard_D2s_v5")
        self.assertTrue(res["ok"], res)
        self.assertNotIn("vm_undersized", ae.get_state(sid)["state"]["broken"])

    def test_resize_rejects_unknown_size(self):
        sid = self._session("azure-vm-undersized")
        res = ae.run_command(sid, "az vm resize --name vm-web01 --size Standard_Enormous")
        self.assertFalse(res["ok"])

    def test_keyvault_secret_set_via_cli(self):
        sid = self._session()
        res = ae.run_command(
            sid, "az keyvault secret set --vault-name kv-fixitlab-prod --name db-password")
        self.assertTrue(res["ok"], res)
        self.assertIn("db-password", ae.run_command(sid, "az keyvault secret list")["stdout"])

    def test_keyvault_secret_set_unknown_vault_errors(self):
        sid = self._session()
        res = ae.run_command(sid, "az keyvault secret set --vault-name kv-nope --name x")
        self.assertFalse(res["ok"])

    def test_resource_group_and_storage_create(self):
        sid = self._session()
        self.assertTrue(ae.run_command(sid, "az group create --name rg-lab2 --location westus")["ok"])
        self.assertIn("rg-lab2", ae.run_command(sid, "az group list")["stdout"])

        sa = ae.run_command(sid, "az storage account create --name stlab2 --sku Standard_LRS")
        self.assertTrue(sa["ok"], sa)
        cont = ae.run_command(sid, "az storage container create --name data --account-name stlab2")
        self.assertTrue(cont["ok"], cont)

    def test_role_assignment_create_via_cli(self):
        sid = self._session()
        res = ae.run_command(
            sid, "az role assignment create --assignee dev@fixitlab.onmicrosoft.com --role Reader")
        self.assertTrue(res["ok"], res)
        self.assertIn("dev@fixitlab.onmicrosoft.com",
                      ae.run_command(sid, "az role assignment list")["stdout"])

    def test_nsg_rule_delete_via_cli(self):
        sid = self._session()
        res = ae.run_command(sid, "az network nsg rule delete --nsg-name nsg-web --name AllowHTTP")
        self.assertTrue(res["ok"], res)
        self.assertNotIn("AllowHTTP", ae.run_command(sid, "az network nsg rule list")["stdout"])

    def test_subnet_create_via_cli(self):
        sid = self._session()
        res = ae.run_command(
            sid, "az network vnet subnet create --name snet-app --vnet-name vnet-prod "
                 "--address-prefixes 10.10.2.0/24")
        self.assertTrue(res["ok"], res)
        self.assertIn("snet-app", ae.run_command(sid, "az network vnet subnet list")["stdout"])
