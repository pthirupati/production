"""Node.js scenarios must resolve to their own persona, not the generic RHEL box.

100 scenarios ship ``simulation_type: nodejs`` but sim_types.py had no nodejs
key, so normalize_sim_type() fell through to "generic" and every Node lab booted
the plain RHEL persona while the catalog advertised Node.js.
"""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.hosting_persona import resolve_host_platform
from apps.labs.provisioner.simulation.sim_types import (
    UNIFIED_SIM_TYPES,
    boot_console_for,
    hostname_for_type,
    infer_sim_type,
    lab_server_banner,
    normalize_sim_type,
)


class NodejsSimTypeTests(SimpleTestCase):
    def test_nodejs_is_a_real_persona(self):
        self.assertIn("nodejs", UNIFIED_SIM_TYPES)
        self.assertEqual(normalize_sim_type("nodejs"), "nodejs")

    def test_explicit_yaml_nodejs_does_not_degrade_to_generic(self):
        # The exact shape of scenarios/nodejs/academy-nodejs-*/scenario.yaml.
        self.assertEqual(
            infer_sim_type("nodejs", "academy-nodejs-065-production-streams-7", "nodejs"),
            "nodejs",
        )

    def test_runtime_spelling_aliases_normalize(self):
        for alias in ("node", "node.js", "node-js", "NodeJS"):
            self.assertEqual(normalize_sim_type(alias), "nodejs", msg=alias)

    def test_generic_yaml_is_promoted_by_tech_or_slug(self):
        cases = [
            ("generic", "academy-nodejs-001-learn-modules", "", "nodejs"),
            ("generic", "node-env-port", "", "nodejs"),
            ("generic", "nodejs-lab-47", "", "nodejs"),
            ("generic", "some-unrelated-slug", "nodejs", "nodejs"),
        ]
        for raw, slug, tech, expected in cases:
            self.assertEqual(
                infer_sim_type(raw, slug, tech), expected, msg=f"{raw=} {slug=} {tech=}"
            )

    def test_nodejs_does_not_steal_javascript_or_react_labs(self):
        self.assertEqual(
            infer_sim_type("generic", "academy-javascript-001-learn-arrays", "javascript"),
            "javascript",
        )
        self.assertEqual(infer_sim_type("react", "academy-react-001", "react"), "react")

    def test_banner_and_hostname_say_node(self):
        banner = lab_server_banner("nodejs", "academy-nodejs-065-production-streams-7")
        self.assertIn("Node.js", banner)
        self.assertEqual(
            hostname_for_type("nodejs", "academy-nodejs-065-production-streams-7"),
            "dev-server",
        )

    def test_node_labs_never_get_the_rhel_boot_console(self):
        # Regression guard for the risk of adding a new persona: boot_console_for()
        # suppresses the GRUB flow via an explicit allowlist, so a persona missing
        # from it would make 100 Node coding labs boot a kernel-select menu.
        # "production" contains no boot keyword; the second slug deliberately does.
        self.assertFalse(
            boot_console_for("academy-nodejs-065-production-streams-7", "nodejs")
        )
        self.assertFalse(boot_console_for("academy-nodejs-012-boot-scripts", "nodejs"))

    def test_node_labs_do_not_rotate_onto_fake_cloud_hardware(self):
        # A Node coding lab must not report Amazon EC2 / Azure DMI.
        for slug in (
            "academy-nodejs-065-production-streams-7",
            "node-memory-leak",
            "nodejs-lab-47",
        ):
            self.assertEqual(resolve_host_platform("nodejs", slug), "linux", msg=slug)
