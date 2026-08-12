"""Session 79: G2 state assertions, serving tracks, polars shim, project YAML fill."""

from django.test import SimpleTestCase

from apps.labs.code_exec import _build_python_harness, grade_submission, resolve_runtime
from apps.labs.provisioner.simulation.state_assertions import (
    ASSERTIONS_BY_SLUG,
    evaluate_slug_assertions,
)
from apps.labs.provisioner.simulation.unified_sim import UnifiedSimulationEngine
from apps.question_bank.management.commands.project_yaml_loader import load_project_yamls
from apps.vmware_sim import netapp_engine as ne


class StateAssertionTests(SimpleTestCase):
    def test_netapp_slug_asserts_svm_world_model(self):
        self.assertIn("academy-netapp-001-learn-svm", ASSERTIONS_BY_SLUG)
        sid = "s79-netapp-assert"
        ne.drop_session(sid)
        ok, msg = evaluate_slug_assertions(sid, "academy-netapp-001-learn-svm")
        self.assertTrue(ok, msg)

        # Break the SVM — assertions must fail closed.
        payload = ne.get_state(sid)
        state = payload["state"]
        for svm in state.get("svms") or []:
            if svm.get("name") == "svm-prod":
                svm["state"] = "stopped"
                svm["protocols"] = ["cifs"]
        entry = ne._load(sid)
        entry["state"] = state
        ne._save(sid, entry)
        bad, hint = evaluate_slug_assertions(sid, "academy-netapp-001-learn-svm")
        self.assertFalse(bad, hint)
        self.assertTrue(hint)


class ServingTrackTests(SimpleTestCase):
    def test_ollama_llamacpp_sglang_trtllm(self):
        eng = UnifiedSimulationEngine(
            scenario_slug="academy-ai-infra-003-operate-dcgm",
            simulation_type="gpu",
        )
        for cmd in ("sudo modprobe nvidia", "sudo systemctl restart nvidia-persistenced"):
            eng.shell.run(cmd)
        ollama = str(eng.shell.run("ollama serve"))
        self.assertIn("11434", ollama)
        llama = str(eng.shell.run("llama-server -m model.gguf"))
        self.assertIn("listening", llama.lower())
        sgl = str(eng.shell.run("sglang serve --model meta-llama/Llama-3.1-8B"))
        self.assertIn("sglang", sgl.lower())
        trt = str(eng.shell.run("trtllm-serve"))
        self.assertIn("TensorRT-LLM", trt)


class PolarsShimTests(SimpleTestCase):
    def test_resolve_and_grade_with_shim(self):
        self.assertEqual(resolve_runtime({"language": "polars"}), "python")
        harness = _build_python_harness("df = pl.DataFrame({'a':[1,2]})", [
            {"name": "t", "code": "assert len(df) == 2", "hidden": False},
        ], inject_polars=True)
        self.assertIn("class DataFrame", harness)
        result = grade_submission(
            "python",
            "df = pl.DataFrame({'n':[1,2,3]})\nout = df.filter(pl.col('n') > 1)",
            [{"name": "rows", "code": "assert len(out) == 2", "hidden": False}],
            authoring_language="polars",
        )
        self.assertTrue(result.all_passed, result.error or result)


class MissingTechProjectsTests(SimpleTestCase):
    def test_eight_gap_techs_have_yaml_projects(self):
        needed = {
            "azure", "gcp", "soc", "rhel-linux", "datacenter",
            "netapp", "dellemc", "commvault",
        }
        yamls = load_project_yamls()
        found = {p.get("technology_slug") for p in yamls}
        self.assertTrue(needed.issubset(found), found)
