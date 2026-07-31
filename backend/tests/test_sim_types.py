"""normalize_sim_type must keep specialty personas (not collapse to generic)."""

from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.sim_types import (
    UNIFIED_SIM_TYPES,
    infer_sim_type,
    normalize_sim_type,
)


class NormalizeSimTypeTests(SimpleTestCase):
    def test_specialty_types_are_preserved(self):
        for key in (
            "peoplesoft",
            "nmap",
            "wireshark",
            "windows-server",
            "windows",
            "docker",
            "javascript",
            "react",
            "html",
            "shell_script",
            "data-dashboard",
            "ai-agent",
            "devops",
            "grafana",
            "aws",
        ):
            self.assertIn(key, UNIFIED_SIM_TYPES)
            self.assertEqual(normalize_sim_type(key), key)

    def test_legacy_coding_types_no_longer_map_to_rhel(self):
        self.assertEqual(normalize_sim_type("html"), "html")
        self.assertEqual(normalize_sim_type("shell_script"), "shell_script")
        self.assertEqual(normalize_sim_type("shell"), "shell_script")

    def test_docker_no_longer_maps_to_generic(self):
        self.assertEqual(normalize_sim_type("docker"), "docker")

    def test_k8s_alias_still_maps_to_kubernetes(self):
        self.assertEqual(normalize_sim_type("k8s"), "kubernetes")

    def test_infer_promotes_specialty_tech_from_generic(self):
        cases = [
            ("generic", "ps-role-missing", "peoplesoft", "peoplesoft"),
            ("generic", "academy-nmap-001-learn-scan", "nmap", "nmap"),
            ("generic", "academy-wireshark-001-learn-pcap", "wireshark", "wireshark"),
            ("generic", "academy-docker-001-learn-run", "docker", "docker"),
            ("generic", "ds-dashboard-001", "", "data-dashboard"),
            ("generic", "agent-hello-001", "", "ai-agent"),
            ("generic", "academy-javascript-001-learn-arrays", "javascript", "javascript"),
            ("generic", "academy-html-001-learn-semantic-html", "html", "html"),
        ]
        for raw, slug, tech, expected in cases:
            self.assertEqual(
                infer_sim_type(raw, slug, tech),
                expected,
                msg=f"{raw=} {slug=} {tech=}",
            )

    def test_explicit_yaml_type_wins_over_generic_promotion(self):
        self.assertEqual(
            infer_sim_type("peoplesoft", "ps-role-missing", "peoplesoft"),
            "peoplesoft",
        )
        self.assertEqual(infer_sim_type("nmap", "nmap-scan", "nmap"), "nmap")
