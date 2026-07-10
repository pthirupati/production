"""Tests for the browser coding-IDE validation flow.

Integrity is the point of these tests: clicking Check / code-validate must NEVER
mark a scenario complete unless the user's real code passes EVERY visible and
hidden test. Wrong code must fail and leave the session RUNNING; correct code
must pass all hidden tests and mark the session validated/COMPLETED through the
shared completion path.
"""

import shutil
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
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

    def test_mentor_blocks_reference_unlock_on_running_session(self):
        self.scenario.solution_explanation = "Return a + b; addition is commutative."
        self.scenario.save()
        session = self._running_session()
        resp = self.client.post(
            f"/api/labs/{session.id}/mentor/",
            {"language": "python", "code": "def add(a,b): return 0",
             "unlock_reference": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_mentor_reveals_reference_when_session_completed(self):
        self.scenario.solution_explanation = "Return a + b; addition is commutative."
        self.scenario.save()
        session = self._running_session()
        session.status = "COMPLETED"
        session.validation_passed = True
        session.save(update_fields=["status", "validation_passed"])
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


# ── Docker sandbox backend (SECURITY_AUDIT C-01) ─────────────────────────────


class _FakeExecResult(dict):
    """Mimics docker-py container.wait() return (a dict with StatusCode)."""


class _FakeContainer:
    """A fake container that *actually runs* the staged harness locally.

    This proves the full container round-trip (build harness -> stage via
    put_archive -> start -> wait -> read logs -> parse verdict) without a real
    Docker engine: the harness the runner would have executed in the container
    is executed here instead, and its real stdout is returned from logs().
    """

    def __init__(self, image, command, **kwargs):
        self.image = image
        self.command = command
        self.kwargs = kwargs
        self.id = "fake-container-id"
        self.started = False
        self.removed = False
        self._staged_source = None  # set by put_archive
        self._stdout = ""
        self._returncode = 0

    def start(self):
        self.started = True
        # Run the staged harness through the SAME interpreter the container
        # would use, capturing genuine stdout (incl. the verdict line).
        import subprocess as _sp
        import sys as _sys
        if not self._staged_source:
            self._stdout, self._returncode = "", 1
            return
        argv = (
            [_sys.executable, "-I", "-B", "-c", self._staged_source]
            if self.command and "python3" in self.command[0]
            else None
        )
        if argv is None:  # JS path not exercised in this fake
            self._stdout, self._returncode = "", 1
            return
        proc = _sp.run(argv, capture_output=True, text=True, timeout=20)
        self._stdout = proc.stdout
        self._returncode = proc.returncode

    def wait(self, timeout=None):
        return _FakeExecResult(StatusCode=self._returncode)

    def logs(self, stdout=True, stderr=False):
        if stdout and not stderr:
            return self._stdout.encode("utf-8")
        return b""

    def remove(self, force=False, v=False):
        self.removed = True

    def kill(self):
        pass


class _FakeContainers:
    def __init__(self, holder):
        self._holder = holder

    def create(self, image, command, **kwargs):
        c = _FakeContainer(image, command, **kwargs)
        self._holder["container"] = c
        self._holder["create_kwargs"] = kwargs
        return c


class _FakeAPI:
    def __init__(self, holder):
        self._holder = holder

    def put_archive(self, cid, path, tar_bytes):
        # Recover the harness source from the tar the runner built and hand it
        # to the fake container so start() can actually run it.
        import io as _io
        import tarfile as _tarfile
        with _tarfile.open(fileobj=_io.BytesIO(tar_bytes)) as tar:
            member = tar.getmembers()[0]
            src = tar.extractfile(member).read().decode("utf-8")
        self._holder["container"]._staged_source = src
        self._holder["put_archive_path"] = path
        return True


class _FakeImages:
    """Pretend the sandbox base image is already present so _ensure_image() is a no-op."""
    def __init__(self, holder):
        self._holder = holder

    def get(self, image):
        return {"image": image}

    def pull(self, image):  # pragma: no cover - only reached if get() fails
        self._holder["pulled"] = image
        return {"image": image}


class _FakeDockerClient:
    def __init__(self, holder):
        self._holder = holder
        self.containers = _FakeContainers(holder)
        self.api = _FakeAPI(holder)
        self.images = _FakeImages(holder)

    def ping(self):
        return True

    def close(self):
        pass


@override_settings(SANDBOX_DOCKER=True)
class DockerSandboxBackendTests(TestCase):
    """Prove grading routes through the locked-down container when enabled."""

    def setUp(self):
        # Reset the runner's reachability probe cache between tests.
        from apps.labs import sandbox_runner
        sandbox_runner._probe_cache.update({"ok": None, "ts": 0.0})
        self.holder = {}

    def _patch_client(self):
        from apps.labs import sandbox_runner
        return mock.patch.object(
            sandbox_runner, "_get_client",
            return_value=_FakeDockerClient(self.holder),
        )

    def test_grade_runs_in_container_with_lockdown_flags(self):
        tests = [
            {"name": "adds", "code": "assert add(2, 3) == 5", "hidden": False},
            {"name": "neg", "code": "assert add(-1, -1) == -2", "hidden": True},
        ]
        with self._patch_client():
            res = grade_submission("python", "def add(a,b): return a+b", tests)

        # It actually used the container path (a fake container was created).
        self.assertIn("container", self.holder)
        kw = self.holder["create_kwargs"]
        # The core C-01 isolation guarantees are all present.
        self.assertEqual(kw["network_mode"], "none")
        self.assertTrue(kw["network_disabled"])
        self.assertTrue(kw["read_only"])
        self.assertEqual(kw["user"], "65534:65534")
        self.assertEqual(kw["cap_drop"], ["ALL"])
        self.assertIn("no-new-privileges:true", kw["security_opt"])
        self.assertFalse(kw["privileged"])
        self.assertTrue(kw["pids_limit"] and kw["pids_limit"] <= 256)
        self.assertTrue(kw["mem_limit"])
        # No bind mounts of host code/secrets.
        self.assertNotIn("volumes", kw)
        self.assertNotIn("mounts", kw)
        # writable scratch is a tmpfs at /work only
        self.assertIn("/work", kw["tmpfs"])
        # And the verdict came back correct + container was cleaned up.
        self.assertTrue(res.all_passed)
        self.assertTrue(self.holder["container"].removed)

    def test_container_wrong_code_fails_closed(self):
        tests = [{"name": "neg", "code": "assert add(-1, -1) == -2", "hidden": True}]
        with self._patch_client():
            res = grade_submission("python", "def add(a,b): return a-b", tests)
        self.assertFalse(res.all_passed)
        self.assertTrue(res.ran)  # it ran, it just didn't pass

    def test_fails_closed_when_engine_unreachable(self):
        from apps.labs import sandbox_runner
        tests = [{"name": "adds", "code": "assert add(2, 3) == 5", "hidden": True}]
        # SECURITY_AUDIT S-01: sandbox ENABLED but unreachable must NOT silently
        # run user code in-process on the host. It fails closed to needs_review.
        with mock.patch.object(sandbox_runner, "_get_client", return_value=None):
            res = grade_submission("python", "def add(a,b): return a+b", tests)
        self.assertFalse(res.all_passed)
        self.assertTrue(res.needs_review)
        self.assertNotIn("container", self.holder)  # never created one

    def test_fails_closed_when_sandbox_unavailable_mid_run(self):
        from apps.labs import sandbox_runner
        tests = [{"name": "adds", "code": "assert add(2, 3) == 5", "hidden": True}]

        # Engine pings OK, but creating the container raises SandboxUnavailable.
        client = _FakeDockerClient(self.holder)

        def _boom(*a, **k):
            raise sandbox_runner.SandboxUnavailable("create failed")

        client.containers.create = _boom
        with mock.patch.object(sandbox_runner, "_get_client", return_value=client):
            res = grade_submission("python", "def add(a,b): return a+b", tests)
        # SECURITY_AUDIT S-01: must fail closed, NOT fall back to in-process.
        self.assertFalse(res.all_passed)
        self.assertTrue(res.needs_review)

    @override_settings(SANDBOX_DOCKER=False)
    def test_disabled_never_touches_docker(self):
        from apps.labs import sandbox_runner
        sandbox_runner._probe_cache.update({"ok": None, "ts": 0.0})
        tests = [{"name": "adds", "code": "assert add(2, 3) == 5", "hidden": True}]
        with mock.patch.object(sandbox_runner, "_get_client") as get_client:
            res = grade_submission("python", "def add(a,b): return a+b", tests)
        get_client.assert_not_called()  # gate off -> never probes docker
        self.assertTrue(res.all_passed)

    def test_http_validate_through_container_completes_via_finalize(self):
        """End-to-end: code-validate routes through the container backend and
        still completes ONLY via finalize_validated_session (never auto-pass)."""
        from apps.labs import sandbox_runner

        user = User.objects.create_user(
            username="dcoder", email="dcoder@test.com", password="Pass123!x"
        )
        client = APIClient()
        client.force_authenticate(user=user)
        tech = Technology.objects.create(
            name="Py-D", slug="py-d", description="d", price=0, is_active=True
        )
        scenario = Scenario.objects.create(
            title="add", description="add", technology=tech, slug="d-add",
            category="Python", difficulty="easy", is_free=True, is_active=True,
            lab_mode="simulation", simulation_type="python",
            coding_mode=True, coding_spec=PY_SPEC, time_limit=1200, max_score=100,
        )
        session = LabSession.objects.create(
            user=user, scenario=scenario, status="RUNNING",
            provider="simulation", duration_limit=1200,
        )
        with mock.patch.object(
            sandbox_runner, "_get_client",
            return_value=_FakeDockerClient(self.holder),
        ):
            resp = client.post(
                f"/api/labs/{session.id}/code-validate/",
                {"language": "python", "files": {"solution.py": CORRECT_PY},
                 "entrypoint": "solution.py"},
                format="json",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["passed"], resp.json())
        # Proves it actually used the container path...
        self.assertIn("container", self.holder)
        # ...and completed through the shared finalize path.
        session.refresh_from_db()
        self.assertTrue(session.validation_passed)
        self.assertEqual(session.status, "COMPLETED")
