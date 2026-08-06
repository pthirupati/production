"""AI-vertical topic faults must plant REAL broken GPU/serving state.

Before this family existed, every ai-infra/GPU slug fell past apply_topic_fault
(measured: gpu_healthy=True and dmesg_extra=[] for all 8 gpu-* families), so the
only thing making the lab fail-closed was the generic broken-config sentinel
text file. The learner ran `nvidia-smi` / `dmesg | grep Xid` and saw a perfectly
healthy node while the brief described an ECC fault — the narrative and the
machine disagreed.
"""
from django.test import SimpleTestCase

from apps.labs.provisioner.simulation.rhel_os import RHELOSState
from apps.labs.provisioner.simulation.topic_faults import apply_topic_fault


class AiTopicFaultTest(SimpleTestCase):
    def _apply(self, slug):
        state = RHELOSState()
        state.scenario_slug = slug
        applied = apply_topic_fault(slug, state)
        return applied, state

    def test_gpu_ecc_slug_marks_gpu_unhealthy_with_xid_in_dmesg(self):
        applied, state = self._apply("gpu-h100-hbm3-ecc-uncorrectable")
        self.assertTrue(applied)
        # The hardware itself must be broken, not just a sentinel text file.
        self.assertFalse(state.gpu_healthy)
        self.assertTrue(
            any("Xid" in line for line in state.dmesg_extra),
            f"expected an Xid line in dmesg, got {state.dmesg_extra}",
        )

    def test_all_gpu_fault_families_break_real_gpu_state(self):
        for slug in (
            "gpu-xid-48-dbe-ecc",
            "gpu-h100-fallen-off-bus-pcie",
            "gpu-thermal-throttle-hbm-overheat",
            "gpu-nvlink-lane-down-h100",
            "gpu-nccl-allreduce-hang",
            "gpu-nvidia-smi-driver-not-loaded",
        ):
            with self.subTest(slug=slug):
                applied, state = self._apply(slug)
                self.assertTrue(applied)
                self.assertFalse(state.gpu_healthy)
                self.assertTrue(state.dmesg_extra)

    def test_llm_serving_slug_plants_broken_inference_service(self):
        applied, state = self._apply("llm-vllm-inference-oom")
        self.assertTrue(applied)
        svc = state.services.get("vllm")
        self.assertIsNotNone(svc, "expected a vllm unit to exist")
        self.assertEqual(svc.active, "failed")

    # ── Anti-hijack guards ────────────────────────────────────────────────
    # The keyword families are deliberately narrow. A bare "agent"/"model"
    # family would steal these unrelated slugs into AI faults and change the
    # seeded world for labs that are already written and graded.
    def test_non_ai_agent_and_model_slugs_are_not_hijacked(self):
        for slug in ("awx-agent-node", "data-model-migration"):
            with self.subTest(slug=slug):
                state = RHELOSState()
                state.scenario_slug = slug
                apply_topic_fault(slug, state)
                # Whatever happens, it must not be the GPU/AI fault.
                self.assertTrue(state.gpu_healthy)

    def test_postgres_checkpoint_lab_keeps_its_db_fault(self):
        # "checkpoint-" as a training keyword collided with this real Postgres
        # WAL lab and planted a training-job unit on it. Keyword is now
        # "model-checkpoint" so the DB family still wins.
        applied, state = self._apply("db-postgres-checkpoint-spikes")
        self.assertTrue(applied)
        self.assertNotIn("training-job", state.services)

    def test_academy_ai_ml_keeps_only_its_own_service_break(self):
        # academy-ai-ml-* has a dedicated model-server unit with a registered
        # E2E fix; a second failed unit from the LLM family would leave the lab
        # still failing after the documented remediation.
        _, state = self._apply("academy-ai-ml-007-automation-inference")
        self.assertNotIn("vllm", state.services)

    def test_jenkins_agent_lab_still_gets_ci_fault(self):
        applied, state = self._apply("jenkins-pipeline-agent")
        self.assertTrue(applied)
        # CI family must still win — it plants a failed gitlab-runner.
        self.assertIn("gitlab-runner", state.services)
        self.assertTrue(state.gpu_healthy)
