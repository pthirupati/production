"""Tests for the browser coding-IDE validation flow.

Integrity is the point of these tests: clicking Check / code-validate must NEVER
mark a scenario complete unless the user's real code passes EVERY visible and
hidden test. Wrong code must fail and leave the session RUNNING; correct code
must pass all hidden tests and mark the session validated/COMPLETED through the
shared completion path.
"""

import shutil

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.code_exec import grade_submission
from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology

User = get_user_model()


PY_SPEC = {
    "language": "python",
    "entrypoint": "solution.py",
    "files": [
        {"path": "solution.py", "content": "def add(a, b):\n    return 0\n"},
    ],
    "visible_tests": [
        {"name": "adds 2+3", "code": "assert add(2, 3) == 5"},
    ],
    "hidden_tests": [
        {"name": "adds negatives", "code": "assert add(-1, -1) == -2"},
        {"name": "adds zero", "code": "assert add(0, 0) == 0"},
    ],
}

CORRECT_PY = "def add(a, b):\n    return a + b\n"
WRONG_PY = "def add(a, b):\n    return a - b\n"


class CodingIDEValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="coder", email="coder@test.com", password="Pass123!"
        )
        self.client.force_authenticate(user=self.user)

        self.tech = Technology.objects.create(
            name="Python-Coding", slug="python-coding",
            description="Coding labs", price=0, is_active=True,
        )
        self.scenario = Scenario.objects.create(
            title="Implement add()", description="Implement add(a, b).",
            technology=self.tech, slug="coding-add-fn", category="Python",
            difficulty="easy", is_free=True, is_active=True,
            lab_mode="simulation", simulation_type="python",
            coding_mode=True, coding_spec=PY_SPEC,
            time_limit=1200, max_score=100,
        )

    def _running_session(self):
        return LabSession.objects.create(
            user=self.user, scenario=self.scenario,
            status="RUNNING", provider="simulation", duration_limit=1200,
        )

    # ── the core integrity guarantees ──────────────────────────────────────

    def test_wrong_code_fails_and_does_not_complete(self):
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/code-validate/",
            {"language": "python", "files": {"solution.py": WRONG_PY},
             "entrypoint": "solution.py"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["passed"], body)

        session.refresh_from_db()
        self.assertFalse(session.validation_passed)
        self.assertEqual(session.status, "RUNNING")  # still open, not completed

    def test_correct_code_passes_all_hidden_and_completes(self):
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/code-validate/",
            {"language": "python", "files": {"solution.py": CORRECT_PY},
             "entrypoint": "solution.py"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["passed"], body)
        self.assertIn("score", body)
        self.assertGreaterEqual(body["score"], 10)

        session.refresh_from_db()
        # Completed through the SAME path as ValidateLabView.
        self.assertTrue(session.validation_passed)
        self.assertEqual(session.status, "COMPLETED")
        self.assertGreater(session.score, 0)

    def test_empty_code_is_rejected_not_passed(self):
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/code-validate/",
            {"language": "python", "files": {"solution.py": "   "},
             "entrypoint": "solution.py"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        session.refresh_from_db()
        self.assertFalse(session.validation_passed)

    def test_passing_only_visible_but_failing_hidden_does_not_complete(self):
        # Code that satisfies the visible test (2+3==5) but not the hidden ones.
        sneaky = (
            "def add(a, b):\n"
            "    if a == 2 and b == 3:\n"
            "        return 5\n"
            "    return 999\n"
        )
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/code-validate/",
            {"language": "python", "files": {"solution.py": sneaky},
             "entrypoint": "solution.py"},
            format="json",
        )
        body = resp.json()
        self.assertFalse(body["passed"], body)
        session.refresh_from_db()
        self.assertFalse(session.validation_passed)
        self.assertEqual(session.status, "RUNNING")

    # ── spec endpoint must not leak hidden test logic ───────────────────────

    def test_coding_spec_strips_hidden_tests(self):
        session = self._running_session()
        resp = self.client.get(f"/api/labs/{session.id}/coding-spec/")
        self.assertEqual(resp.status_code, 200)
        spec = resp.json()["spec"]
        # Visible tests are sent (they run client-side); hidden tests are NOT.
        self.assertEqual(len(spec["visible_tests"]), 1)
        self.assertEqual(spec["hidden_test_count"], 2)
        self.assertNotIn("hidden_tests", spec)
        serialized = str(resp.json())
        self.assertNotIn("adds negatives", serialized)  # hidden test name absent
        self.assertNotIn("== -2", serialized)           # hidden test logic absent

    # ── AI Mentor: explains errors WITHOUT leaking the reference solution ────

    def test_mentor_explains_error_without_revealing_solution(self):
        # Give the scenario a distinctive solution explanation so we can prove it
        # never appears in the mentor's (locked) response.
        self.scenario.solution_explanation = "ZZSECRETSOLUTIONZZ: just return a plus b."
        self.scenario.save()
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/mentor/",
            {
                "language": "python",
                "code": "def add(a, b):\n    return a + c\n",  # NameError: c
                "error": "NameError: name 'c' is not defined",
                "test_results": [
                    {"name": "adds negatives", "passed": False, "hidden": True},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        # It produced guidance and explicitly promises no solution leak.
        self.assertTrue(body["notes"])
        self.assertFalse(body["reveals_solution"])
        kinds = {n["kind"] for n in body["notes"]}
        self.assertIn("error", kinds)
        blob = str(body).lower()
        self.assertIn("nameerror", blob)  # it actually named the error

        # Reference stays LOCKED — the answer/explanation is NOT in the response.
        self.assertFalse(body["reference"]["unlocked"])
        self.assertNotIn("solution_explanation", body["reference"])
        self.assertNotIn("zzsecretsolutionzz", blob)  # the answer never leaks
        # Hidden-test name must not leak through the mentor either.
        self.assertNotIn("adds negatives", blob)
        self.assertNotIn("== -2", str(body))

    def test_mentor_reveals_reference_only_when_unlocked(self):
        self.scenario.solution_explanation = "Return a + b; addition is commutative."
        self.scenario.save()
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/mentor/",
            {"language": "python", "code": "def add(a,b): return 0",
             "unlock_reference": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        ref = resp.json()["reference"]
        self.assertTrue(ref["unlocked"])
        self.assertIn("commutative", ref["solution_explanation"])

    def test_completed_session_cannot_be_revalidated(self):
        session = self._running_session()
        # First, solve it.
        self.client.post(
            f"/api/labs/{session.id}/code-validate/",
            {"language": "python", "files": {"solution.py": CORRECT_PY},
             "entrypoint": "solution.py"},
            format="json",
        )
        session.refresh_from_db()
        self.assertEqual(session.status, "COMPLETED")
        # A second submission must 404 — the view only matches RUNNING sessions,
        # so there is no way to re-trigger completion side-effects.
        resp = self.client.post(
            f"/api/labs/{session.id}/code-validate/",
            {"language": "python", "files": {"solution.py": WRONG_PY},
             "entrypoint": "solution.py"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)


class CodeExecSandboxTests(TestCase):
    """Unit tests for the sandbox grader itself (no HTTP layer)."""

    def test_infinite_loop_times_out_and_fails(self):
        tests = [{"name": "t", "code": "assert f() == 1", "hidden": True}]
        result = grade_submission(
            "python", "def f():\n    while True:\n        pass\n", tests, timeout=3
        )
        self.assertFalse(result.all_passed)
        self.assertIn("timed out", result.error.lower())

    def test_no_tests_never_auto_passes(self):
        result = grade_submission("python", "x = 1", [])
        self.assertFalse(result.all_passed)
        self.assertFalse(result.ran)

    def test_bash_needs_review_not_pass(self):
        result = grade_submission(
            "bash", "echo hi", [{"name": "t", "code": "true", "hidden": True}]
        )
        self.assertTrue(result.needs_review)
        self.assertFalse(result.all_passed)

    def test_syntax_error_fails_closed(self):
        tests = [{"name": "t", "code": "assert add(1, 2) == 3", "hidden": True}]
        result = grade_submission("python", "def add(a, b)\n    return a+b", tests)
        self.assertFalse(result.all_passed)
        self.assertFalse(result.ran)

    def test_public_dict_masks_hidden_names(self):
        tests = [{"name": "secret_edge_case", "code": "assert add(1,1)==2", "hidden": True}]
        result = grade_submission("python", "def add(a,b): return a-b", tests)
        public = result.public_dict(reveal_hidden_names=False)
        self.assertNotIn("secret_edge_case", str(public))
        self.assertEqual(public["tests"][0]["name"], "Hidden test")

    def test_javascript_grading(self):
        if not shutil.which("node"):
            self.skipTest("node not available")
        tests = [{"name": "reverses", "code": "assert(rev('abc')==='cba')", "hidden": True}]
        good = grade_submission(
            "javascript", "function rev(s){return s.split('').reverse().join('')}", tests
        )
        bad = grade_submission("javascript", "function rev(s){return s}", tests)
        self.assertTrue(good.all_passed)
        self.assertFalse(bad.all_passed)


# ── generated-scenario integrity (fail-before / pass-after) ──────────────────

import glob
import os
import sys

import yaml

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_SCEN_ROOT = os.path.join(_REPO_ROOT, "scenarios")
_GEN_DIR = os.path.join(_REPO_ROOT, "scripts", "coding_gen")


def _load_generated_yaml_scenarios():
    """Load every generated coding scenario YAML (slugs py-* / js-*) from disk.

    These are the authored coding scenarios; pre-existing infra scenarios and
    the original sim-coding-* samples are skipped so this test pins exactly the
    batch produced by scripts/coding_gen.
    """
    out = []
    patterns = [
        os.path.join(_SCEN_ROOT, "python", "**", "scenario.yaml"),
        os.path.join(_SCEN_ROOT, "javascript", "**", "scenario.yaml"),
    ]
    for pat in patterns:
        for path in glob.glob(pat, recursive=True):
            slug = os.path.basename(os.path.dirname(path))
            if not (slug.startswith("py-") or slug.startswith("js-")):
                continue
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            out.append((slug, path, data))
    out.sort(key=lambda t: t[0])
    return out


def _graded_source_from_spec(spec, body_for_entrypoint=None):
    """Recreate the backend's grading source: non-entry files first, entry last.

    Mirrors apps.public_api.views' multi-file concatenation. If
    body_for_entrypoint is provided it replaces the entrypoint file's content
    (used to substitute the reference solution); otherwise the YAML's starter
    content (the broken/stub code) is used.
    """
    entry = spec.get("entrypoint", "")
    files = spec.get("files", []) or []
    parts = []
    entry_body = None
    for f in files:
        path = f.get("path")
        content = f.get("content", "")
        if path == entry:
            entry_body = content
        else:
            parts.append(content)
    if body_for_entrypoint is not None:
        entry_body = body_for_entrypoint
    if entry_body is not None:
        parts.append(entry_body)
    return "\n".join(parts)


def _spec_tests(spec):
    visible = [
        {"name": t.get("name", ""), "code": t.get("code", ""), "hidden": False}
        for t in (spec.get("visible_tests") or [])
    ]
    hidden = [
        {"name": t.get("name", ""), "code": t.get("code", ""), "hidden": True}
        for t in (spec.get("hidden_tests") or [])
    ]
    return visible + hidden


def _reference_solutions_by_slug():
    """Import the generator scenario banks to recover reference solutions.

    The reference (correct) code lives only in the generator data — never in the
    shipped YAML. Importing the banks lets the test prove pass-after without
    leaking solutions into scenario files.
    """
    if _GEN_DIR not in sys.path:
        sys.path.insert(0, _GEN_DIR)
    import scenarios_python  # noqa: WPS433 (local import is intentional)
    import scenarios_javascript  # noqa: WPS433
    refs = {}
    for scn in list(scenarios_python.S) + list(scenarios_javascript.S):
        refs[scn.slug] = scn.reference
    return refs


class GeneratedCodingScenarioIntegrityTests(TestCase):
    """Prove every generated coding scenario fails before and passes after.

    For each scenario.yaml on disk:
      * the SHIPPED starter (broken/stub) must FAIL its own visible+hidden tests
      * the REFERENCE solution must PASS every visible+hidden test
    This is the fail-closed integrity contract from code_exec.py, enforced on
    the actual files that get seeded.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scenarios = _load_generated_yaml_scenarios()
        cls.refs = _reference_solutions_by_slug()

    def test_generated_scenarios_were_written(self):
        # Sanity: the batch exists on disk and was discovered.
        self.assertGreaterEqual(
            len(self.scenarios), 80,
            "expected the generated coding batch on disk",
        )
        py = [s for s in self.scenarios if s[0].startswith("py-")]
        js = [s for s in self.scenarios if s[0].startswith("js-")]
        self.assertGreaterEqual(len(py), 40)
        self.assertGreaterEqual(len(js), 30)

    def test_every_yaml_has_a_reference_solution(self):
        # Each shipped scenario must have a recoverable reference (so the
        # pass-after gate below can actually run for all of them).
        missing = [slug for slug, _p, _d in self.scenarios if slug not in self.refs]
        self.assertEqual(missing, [], f"no reference solution for: {missing}")

    def test_broken_starters_fail_before(self):
        """The shipped starter code must NOT pass — proving fail-before."""
        node = shutil.which("node")
        offenders = []
        for slug, path, data in self.scenarios:
            spec = data.get("coding_spec") or {}
            lang = spec.get("language")
            if lang == "javascript" and not node:
                continue  # can't grade JS without node; covered where available
            tests = _spec_tests(spec)
            broken_src = _graded_source_from_spec(spec)
            res = grade_submission(lang, broken_src, tests,
                                   timeout=int(spec.get("timeout", 8)))
            if res.all_passed:
                offenders.append(slug)
        self.assertEqual(
            offenders, [],
            f"these starters PASS without being solved (integrity violation): {offenders}",
        )

    def test_reference_solutions_pass_after(self):
        """The reference solution must pass EVERY visible + hidden test."""
        node = shutil.which("node")
        failures = []
        for slug, path, data in self.scenarios:
            spec = data.get("coding_spec") or {}
            lang = spec.get("language")
            if lang == "javascript" and not node:
                continue
            ref = self.refs.get(slug)
            if ref is None:
                failures.append((slug, "no reference solution"))
                continue
            tests = _spec_tests(spec)
            ref_src = _graded_source_from_spec(spec, body_for_entrypoint=ref)
            res = grade_submission(lang, ref_src, tests,
                                   timeout=int(spec.get("timeout", 8)))
            if not res.all_passed:
                bad = [o.name for o in res.outcomes if not o.passed]
                failures.append((slug, f"ran={res.ran} err={res.error[:120]!r} failing={bad}"))
        self.assertEqual(
            failures, [],
            f"reference solutions failed their own tests: {failures}",
        )

    def test_shipped_yaml_uses_broken_not_reference(self):
        """Defense-in-depth: the entrypoint content on disk is the BROKEN
        starter, never the reference solution (no accidental answer leak)."""
        leaked = []
        for slug, path, data in self.scenarios:
            spec = data.get("coding_spec") or {}
            entry = spec.get("entrypoint", "")
            ref = self.refs.get(slug)
            if ref is None:
                continue
            for f in spec.get("files", []) or []:
                if f.get("path") == entry:
                    shipped = (f.get("content") or "").strip()
                    if shipped == ref.strip():
                        leaked.append(slug)
        self.assertEqual(leaked, [], f"reference solution shipped as starter: {leaked}")
