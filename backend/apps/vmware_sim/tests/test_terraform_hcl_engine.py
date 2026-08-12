"""Real HCL parsing, dependency graph, diffs, and state file (audit L1002/L2111).

These replace a templated plan renderer that emitted the same hardcoded
`aws_instance.web` block regardless of the learner's configuration, and a
`drift` boolean that was seeded at session start rather than derived from a
state comparison.
"""

from django.core.cache import cache
from django.test import TestCase

from apps.vmware_sim import terraform_engine as te


AMI_DRIFT_HCL = """
data "aws_ami" "app" {
  most_recent = true
  owners      = ["self"]
  filter {
    name   = "name"
    values = ["app-golden-*"]
  }
}

resource "aws_instance" "web" {
  ami           = data.aws_ami.app.id
  instance_type = "t3.medium"

  lifecycle {
    create_before_destroy = true
  }
}
"""

NAT_FIX_HCL = """
resource "aws_route" "private_default" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat.id
}
"""


class HCLParserTests(TestCase):
    def test_parses_attributes_not_just_headers(self):
        cfg = te.parse_hcl_files(te.DEFAULT_FILES)
        node = cfg["resources"]["aws_instance.web"]
        self.assertEqual(node["attributes"]["ami"], {"__ref__": "var.ami_id"})
        self.assertEqual(node["attributes"]["tags"], {"Name": "web-server"})
        self.assertEqual(cfg["variables"]["instance_type"]["default"], "t3.medium")
        self.assertIn("instance_id", cfg["outputs"])

    def test_commented_out_resources_are_not_parsed(self):
        """The VPC lab hides the answer in a comment block — it must not count."""
        cfg = te.parse_hcl_files(te.VPC_ROUTING_BROKEN_FILES)
        self.assertNotIn("aws_route.private_default", cfg["resources"])
        self.assertIn("aws_route.public_default", cfg["resources"])

    def test_heredoc_and_string_contents_are_not_code(self):
        cfg = te.parse_hcl_files({"main.tf": '''
resource "aws_s3_bucket" "notes" {
  policy = <<EOT
resource "aws_instance" "ghost" {}
EOT
}
'''})
        self.assertEqual(sorted(cfg["resources"]), ["aws_s3_bucket.notes"])

    def test_nested_blocks_and_lifecycle(self):
        cfg = te.parse_hcl_files({"main.tf": AMI_DRIFT_HCL})
        data = cfg["data"]["data.aws_ami.app"]
        self.assertEqual(data["blocks"][0]["attributes"]["values"], ["app-golden-*"])
        life = te.lifecycle_of(cfg["resources"]["aws_instance.web"])
        self.assertTrue(life["create_before_destroy"])

    def test_unparseable_hcl_raises_rather_than_returning_empty(self):
        with self.assertRaises(te.HCLParseError):
            te.parse_hcl_files({"main.tf": 'resource "aws_instance" "web" {'})
        with self.assertRaises(te.HCLParseError):
            te.parse_hcl_files({"main.tf": 'resource "aws_instance" "web" { ami = "unterminated\n}'})


class DependencyGraphTests(TestCase):
    def test_edges_follow_real_references(self):
        cfg = te.parse_hcl_files(te.VPC_ROUTING_BROKEN_FILES)
        graph = te.build_dependency_graph(cfg)
        self.assertIn("aws_eip.nat", graph["edges"]["aws_nat_gateway.nat"])
        self.assertIn("aws_subnet.public", graph["edges"]["aws_nat_gateway.nat"])
        self.assertIn("aws_vpc.lab", graph["edges"]["aws_subnet.private"])
        self.assertEqual(graph["cycles"], [])

    def test_apply_order_puts_dependencies_first(self):
        cfg = te.parse_hcl_files(te.VPC_ROUTING_BROKEN_FILES)
        order = te.build_dependency_graph(cfg)["order"]
        self.assertLess(order.index("aws_vpc.lab"), order.index("aws_subnet.public"))
        self.assertLess(order.index("aws_subnet.public"), order.index("aws_nat_gateway.nat"))

    def test_cycle_is_detected(self):
        cfg = te.parse_hcl_files({"main.tf": '''
resource "aws_instance" "a" { subnet_id = aws_instance.b.id }
resource "aws_instance" "b" { subnet_id = aws_instance.a.id }
'''})
        graph = te.build_dependency_graph(cfg)
        self.assertEqual(sorted(graph["cycles"][0]), ["aws_instance.a", "aws_instance.b"])


class PlanDiffAndStateTests(TestCase):
    def test_plan_then_apply_converges_to_no_op(self):
        """A second plan against unchanged config must report zero changes."""
        cfg = te.parse_hcl_files(te.VPC_ROUTING_BROKEN_FILES)
        state = te.empty_state()
        first = te.compute_plan(cfg, state)
        self.assertEqual(first["add"], 11)
        self.assertEqual((first["change"], first["destroy"]), (0, 0))

        state = te.apply_plan_to_state(cfg, state, first)
        self.assertEqual(state["serial"], 1)
        self.assertEqual(len(state["resources"]), 11)

        second = te.compute_plan(cfg, state)
        self.assertEqual((second["add"], second["change"], second["destroy"]), (0, 0, 0))

    def test_editing_an_attribute_produces_a_targeted_update(self):
        cfg = te.parse_hcl_files({"main.tf": '''
resource "aws_instance" "web" {
  ami           = "ami-1111111111111111"
  instance_type = "t3.medium"
}
'''})
        state = te.apply_plan_to_state(cfg, te.empty_state(), te.compute_plan(cfg, te.empty_state()))
        cfg2 = te.parse_hcl_files({"main.tf": '''
resource "aws_instance" "web" {
  ami           = "ami-1111111111111111"
  instance_type = "t3.large"
}
'''})
        plan = te.compute_plan(cfg2, state)
        act = [a for a in plan["actions"] if a["address"] == "aws_instance.web"][0]
        self.assertEqual(act["action"], "update")
        self.assertEqual(
            act["changes"]["instance_type"],
            {"action": "update", "before": "t3.medium", "after": "t3.large"},
        )
        self.assertEqual((plan["add"], plan["change"], plan["destroy"]), (0, 1, 0))

    def test_removing_a_resource_plans_a_destroy(self):
        cfg = te.parse_hcl_files({"main.tf": '''
resource "aws_instance" "a" {  ami = "ami-1" }
resource "aws_instance" "b" {  ami = "ami-2" }
'''})
        state = te.apply_plan_to_state(cfg, te.empty_state(), te.compute_plan(cfg, te.empty_state()))
        cfg2 = te.parse_hcl_files({"main.tf": 'resource "aws_instance" "a" { ami = "ami-1" }'})
        plan = te.compute_plan(cfg2, state)
        self.assertEqual((plan["add"], plan["destroy"]), (0, 1))
        self.assertEqual(
            [a["address"] for a in plan["actions"] if a["action"] == "destroy"],
            ["aws_instance.b"],
        )

    def test_computed_attributes_never_register_as_changes(self):
        prior = {"id": "i-123", "public_ip": "203.0.113.9", "instance_type": "t3.medium"}
        desired = {"instance_type": "t3.medium"}
        self.assertEqual(te.diff_attributes(prior, desired), {})

    def test_plan_output_reflects_the_actual_config(self):
        """The old renderer printed aws_instance.web for any config at all."""
        cfg = te.parse_hcl_files({"main.tf": '''
resource "google_compute_instance" "batch" {
  machine_type = "e2-medium"
  zone         = "us-central1-a"
}
'''})
        plan = te.compute_plan(cfg, te.empty_state())
        out = te._format_plan_output("Terraform", {}, plan, "")
        self.assertIn("google_compute_instance.batch will be created", out)
        self.assertIn('+ machine_type = "e2-medium"', out)
        self.assertNotIn("aws_instance", out)
        self.assertIn("Plan: 1 to add, 0 to change, 0 to destroy.", out)


class AmiDriftTests(TestCase):
    """Audit L2111 — drift from an upstream-produced AMI id."""

    def _applied(self):
        cfg = te.parse_hcl_files({"main.tf": AMI_DRIFT_HCL})
        state = te.apply_plan_to_state(cfg, te.empty_state(), te.compute_plan(cfg, te.empty_state()))
        return cfg, state

    def test_data_aws_ami_selects_most_recent_matching_image(self):
        cfg, state = self._applied()
        self.assertEqual(
            state["resources"]["aws_instance.web"]["attributes"]["ami"],
            "ami-0a1b2c3d4e5f60011",
        )
        self.assertEqual((te.compute_plan(cfg, state)["change"]), 0)

    def test_deregistering_the_image_out_of_band_forces_replacement(self):
        cfg, state = self._applied()
        registry = [dict(i) for i in te.default_ami_registry()]
        registry[0]["state"] = "deregistered"
        state["ami_registry"] = registry

        plan = te.compute_plan(cfg, state)
        act = [a for a in plan["actions"] if a["address"] == "aws_instance.web"][0]
        self.assertEqual(act["action"], "replace")
        self.assertIn("ami forces replacement", act["replace_reason"])
        self.assertTrue(act["create_before_destroy"])
        self.assertEqual(act["changes"]["ami"]["after"], "ami-0a1b2c3d4e5f60010")
        self.assertEqual((plan["add"], plan["destroy"]), (1, 1))

    def test_owner_filter_excludes_foreign_images(self):
        """owners = ["self"] must not select the amazon-owned AMI."""
        cfg, state = self._applied()
        registry = [i for i in te.default_ami_registry() if i["owner"] == "amazon"]
        state["ami_registry"] = registry
        errors = te.data_source_errors(cfg, state)
        self.assertTrue(errors)
        self.assertIn("returned no results", errors[0])

    def test_no_matching_ami_fails_closed(self):
        cfg, state = self._applied()
        state["ami_registry"] = []
        state["ami_registry"] = [{
            "id": "ami-zzz", "name": "unrelated", "owner": "self",
            "state": "available", "creation_date": "2026-01-01T00:00:00Z",
        }]
        self.assertTrue(te.data_source_errors(cfg, state))


class NatRouteGradingTests(TestCase):
    """The grader must accept the documented fix and reject lookalikes."""

    def _files(self, extra: str) -> dict:
        files = dict(te.VPC_ROUTING_BROKEN_FILES)
        files["network.tf"] = files["network.tf"] + extra
        return files

    def test_unfixed_lab_does_not_pass(self):
        self.assertFalse(te._hcl_has_private_nat_route(te.VPC_ROUTING_BROKEN_FILES))

    def test_documented_fix_passes(self):
        self.assertTrue(te._hcl_has_private_nat_route(self._files(NAT_FIX_HCL)))

    def test_route_on_the_public_table_does_not_pass(self):
        cheat = NAT_FIX_HCL.replace("aws_route_table.private.id", "aws_route_table.public.id")
        self.assertFalse(te._hcl_has_private_nat_route(self._files(cheat)))

    def test_attributes_split_across_two_routes_do_not_pass(self):
        cheat = '''
resource "aws_route" "a" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
}
resource "aws_route" "b" {
  nat_gateway_id = aws_nat_gateway.nat.id
}
'''
        self.assertFalse(te._hcl_has_private_nat_route(self._files(cheat)))

    def test_answer_inside_a_heredoc_does_not_pass(self):
        cheat = '''
resource "aws_s3_bucket" "notes" {
  tags = { doc = <<EOT
nat_gateway_id = aws_nat_gateway.nat.id
destination_cidr_block = "0.0.0.0/0"
EOT
  }
}
'''
        self.assertFalse(te._hcl_has_private_nat_route(self._files(cheat)))

    def test_unparseable_config_fails_closed(self):
        self.assertFalse(te._hcl_has_private_nat_route({"main.tf": 'resource "aws_route" "x" {'}))


class EngineActionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.sid = "test-tf-hcl-engine"
        te.drop_session(self.sid)

    def tearDown(self):
        cache.clear()

    def test_vpc_routing_lab_is_solvable_end_to_end(self):
        """Guards against shipping an unsolvable lab."""
        slug = "terraform-vpc-routing"
        te.get_state(self.sid, slug)
        self.assertFalse(te.validate_terraform_lab(self.sid, slug)[0])

        te.apply_action(self.sid, "terraform_init", {})
        self.assertTrue(te.apply_action(self.sid, "terraform_plan", {})["ok"])
        te.apply_action(self.sid, "terraform_apply", {})
        self.assertFalse(te.validate_terraform_lab(self.sid, slug)[0])

        files = te.get_state(self.sid)["state"]["files"]
        te.apply_action(self.sid, "save_files", {
            "files": {"network.tf": files["network.tf"] + NAT_FIX_HCL},
        })
        plan = te.apply_action(self.sid, "terraform_plan", {})
        self.assertTrue(plan["ok"], plan)
        self.assertEqual(plan["plan"]["add"], 1)
        self.assertTrue(te.apply_action(self.sid, "terraform_apply", {})["ok"])

        ok, msg = te.validate_terraform_lab(self.sid, slug)
        self.assertTrue(ok, msg)

    def test_plan_fails_closed_on_invalid_hcl(self):
        te.get_state(self.sid, "terraform-basic")
        te.apply_action(self.sid, "terraform_init", {})
        te.apply_action(self.sid, "save_files", {
            "files": {"main.tf": 'resource "aws_instance" "web" {'},
        })
        res = te.apply_action(self.sid, "terraform_plan", {})
        self.assertFalse(res["ok"], res)
        self.assertIn("Invalid configuration", res.get("output") or "")
        # A failed plan must not leave a stale plan that apply could ride on.
        self.assertIsNone(te.get_state(self.sid)["state"]["terraform"]["last_plan"])

    def test_validate_rejects_dependency_cycle(self):
        te.get_state(self.sid, "terraform-basic")
        te.apply_action(self.sid, "save_files", {"files": {"main.tf": '''
resource "aws_instance" "a" { subnet_id = aws_instance.b.id }
resource "aws_instance" "b" { subnet_id = aws_instance.a.id }
'''}})
        res = te.apply_action(self.sid, "terraform_validate", {})
        self.assertFalse(res["ok"])
        self.assertIn("Cycle", res.get("output") or "")

    def test_apply_writes_state_file_and_outputs(self):
        te.get_state(self.sid, "terraform-basic")
        te.apply_action(self.sid, "terraform_init", {})
        te.apply_action(self.sid, "terraform_plan", {})
        res = te.apply_action(self.sid, "terraform_apply", {})
        self.assertTrue(res["ok"])
        tf = te.get_state(self.sid)["state"]["terraform"]
        self.assertEqual(tf["state_file"]["serial"], 1)
        self.assertIn("aws_instance.web", tf["state_file"]["resources"])
        # outputs.tf resolves instance_id off the applied resource.
        self.assertTrue(tf["outputs"]["instance_id"].startswith("i-0"))
        self.assertIn("Apply complete! Resources: 1 added", res["output"])

    def test_change_count_comes_from_the_diff_not_a_preset_flag(self):
        """The default session seeds broken['drift']=True.

        The old engine reported "2 to change" off that boolean alone, naming a
        security group the learner never declared. The first plan of a fresh
        workspace creates resources — it changes nothing.
        """
        te.get_state(self.sid, "terraform-basic")
        self.assertTrue(te.get_state(self.sid)["state"]["broken"].get("drift"))
        te.apply_action(self.sid, "terraform_init", {})
        res = te.apply_action(self.sid, "terraform_plan", {})
        self.assertEqual(res["plan"]["change"], 0)
        self.assertEqual(res["plan"]["summary"], "Plan: 1 to add, 0 to change, 0 to destroy.")
        self.assertNotIn("aws_security_group", res["output"])

    def test_replan_after_apply_reports_no_changes(self):
        te.get_state(self.sid, "terraform-basic")
        te.apply_action(self.sid, "terraform_init", {})
        te.apply_action(self.sid, "terraform_plan", {})
        te.apply_action(self.sid, "terraform_apply", {})
        res = te.apply_action(self.sid, "terraform_plan", {})
        self.assertEqual(res["plan"]["summary"], "Plan: 0 to add, 0 to change, 0 to destroy.")
        self.assertIn("No changes.", res["output"])
        self.assertFalse(te.get_state(self.sid)["state"]["terraform"]["drift_detected"])

    def test_destroy_clears_state_file(self):
        te.get_state(self.sid, "terraform-basic")
        te.apply_action(self.sid, "terraform_init", {})
        te.apply_action(self.sid, "terraform_plan", {})
        te.apply_action(self.sid, "terraform_apply", {})
        res = te.apply_action(self.sid, "terraform_destroy", {})
        self.assertTrue(res["ok"])
        tf = te.get_state(self.sid)["state"]["terraform"]
        self.assertEqual(tf["state_file"]["resources"], {})

    def test_prevent_destroy_blocks_destroy(self):
        te.get_state(self.sid, "terraform-basic")
        te.apply_action(self.sid, "terraform_init", {})
        te.apply_action(self.sid, "save_files", {"files": {"main.tf": '''
resource "aws_instance" "web" {
  ami = "ami-1111111111111111"
  lifecycle { prevent_destroy = true }
}
'''}})
        te.apply_action(self.sid, "terraform_plan", {})
        te.apply_action(self.sid, "terraform_apply", {})
        res = te.apply_action(self.sid, "terraform_destroy", {})
        self.assertFalse(res["ok"])
        self.assertIn("prevent_destroy", res.get("output") or "")
