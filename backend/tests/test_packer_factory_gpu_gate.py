"""gpu-sanity gate must require a real provisioner, not a substring anywhere.

The gate used to be a substring scan (`_has_nvidia_marker`) over the template
blob plus every value of the files dict. The gpu-sanity failure log names the
exact tokens it looks for ("add nvidia-persistenced / install-gpu script"), so a
learner could paste `# nvidia-smi` into a comment and clear the gate without
provisioning a driver at all — trivially fail-open.

These tests pin both directions: the cheat vectors must fail, and the templates
that real packer labs ship (including the IDE's DEFAULT_MAIN seed) must still
pass, since a parser that rejects those would make every packer lab unsolvable.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.vmware_sim.packer_factory import _has_nvidia_marker, start_pipeline

REPO_ROOT = Path(settings.BASE_DIR).parent
PACKER_IDE = REPO_ROOT / "frontend/src/components/packer/PackerWorkspaceIde.jsx"

REAL_TEMPLATE = (
    'build {\n'
    '  sources = ["source.qemu.gpu"]\n'
    '  provisioner "shell" {\n'
    '    inline = ["apt-get install -y nvidia-driver-535"]\n'
    '  }\n'
    '}\n'
)


class PackerNvidiaMarkerTests(SimpleTestCase):
    def test_marker_in_comment_does_not_satisfy_gate(self):
        """The exact paste the failure log invites must not clear the gate."""
        for cheat in (
            "# nvidia-smi",
            "// install-gpu",
            "/* provisioner \"shell\" { inline = [\"nvidia-driver\"] } */",
            'build {\n  # provisioner "shell" { inline = ["nvidia-driver"] }\n}',
        ):
            with self.subTest(cheat=cheat):
                self.assertFalse(
                    _has_nvidia_marker({}, cheat),
                    f"commented-out marker cleared the gpu-sanity gate: {cheat!r}",
                )

    def test_marker_outside_a_provisioner_does_not_satisfy_gate(self):
        """A variable name or prose mentioning a marker is not a driver install."""
        for cheat in (
            'variable "cuda-toolkit" { default = "x" }',
            "this template mentions dcgm somewhere",
            'description = "installs nvidia-driver eventually"',
        ):
            with self.subTest(cheat=cheat):
                self.assertFalse(_has_nvidia_marker({}, cheat))

    def test_marker_in_heredoc_prose_does_not_satisfy_gate(self):
        """Heredoc payload is literal text, not a provisioner body."""
        self.assertFalse(_has_nvidia_marker({}, "foo = <<-EOF\n  nvidia-smi\nEOF"))

    def test_real_provisioner_satisfies_gate(self):
        self.assertTrue(_has_nvidia_marker({}, REAL_TEMPLATE))

    def test_bare_provisioner_block_satisfies_gate(self):
        """Existing labs ship provisioners without a build{} wrapper — keep them solvable."""
        self.assertTrue(
            _has_nvidia_marker(
                {}, 'provisioner "shell" { script = "scripts/install-gpu-h100.sh" }'
            )
        )

    def test_provisioner_marker_after_nested_block_is_found(self):
        """Brace counting, not a non-greedy regex: markers past a nested block count."""
        self.assertTrue(
            _has_nvidia_marker(
                {},
                'provisioner "shell" {\n'
                '  environment_vars = ["A=1"]\n'
                '  inline = ["install-gpu.sh"]\n'
                '}\n',
            )
        )

    def test_shipped_ide_seed_template_still_passes(self):
        """DEFAULT_MAIN is what every packer lab starts from — it must stay valid."""
        if not PACKER_IDE.exists():
            self.skipTest("packer IDE source not present in this environment")
        src = PACKER_IDE.read_text()
        m = re.search(r"const DEFAULT_MAIN = `(.*?)`\n", src, re.S)
        self.assertIsNotNone(m, "DEFAULT_MAIN seed template not found in the IDE")
        seed = m.group(1).replace("\\${", "${")
        self.assertTrue(
            _has_nvidia_marker({}, seed),
            "the shipped seed template no longer clears gpu-sanity — packer labs "
            "would be unsolvable",
        )

    def test_files_dict_is_still_scanned(self):
        """Templates arrive as files{} from the IDE, not only as the template blob."""
        self.assertTrue(_has_nvidia_marker({"gpu-h100.pkr.hcl": REAL_TEMPLATE}, ""))
        self.assertFalse(_has_nvidia_marker({"notes.md": "# nvidia-smi"}, ""))


class PackerRunStateTests(SimpleTestCase):
    def test_run_records_has_nvidia_marker_flag(self):
        """Downstream state readers depend on run['has_nvidia_marker'] existing."""
        state: dict = {}
        run = start_pipeline(state, {"sku": "h100", "template": REAL_TEMPLATE})["run"]
        self.assertTrue(run["has_nvidia_marker"])

        state2: dict = {}
        run2 = start_pipeline(state2, {"sku": "h100", "template": "# nvidia-smi"})["run"]
        self.assertFalse(run2["has_nvidia_marker"])
