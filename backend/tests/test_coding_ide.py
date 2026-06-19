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
