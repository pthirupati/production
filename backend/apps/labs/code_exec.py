"""Free, sandboxed code execution for grading coding-IDE scenarios.

Integrity philosophy (mirrors apps/labs/provisioner/simulation/validation.py):
    FAIL CLOSED. A coding scenario is solved ONLY when the user's real code,
    combined with the scenario's HIDDEN test cases, actually runs and every
    required assertion passes. We never trust a self-reported "pass" from the
    browser. Hidden tests live on the server and are executed here in a
    restricted subprocess — their source is never returned to the client.

No paid APIs / cloud services are used. Languages are graded with the
interpreters already present on the host:
    - Python      -> python3  (fully supported)
    - JavaScript  -> node      (supported when node is on PATH)
    - anything else -> "needs review" (never auto-passed)

Execution backends (selected per submission, fail-closed either way):

    1. Container (preferred, SECURITY_AUDIT C-01): when ``settings.SANDBOX_DOCKER``
       is on AND a Docker engine answers, the harness runs in a throwaway
       container with ``--network none``, a read-only rootfs, a non-root user,
       ``--cap-drop ALL``, ``--pids-limit``, and hard memory/CPU caps (see
       ``apps.labs.sandbox_runner``). This is the only backend that actually
       isolates network + host filesystem from user code.
    2. In-process subprocess (fallback / dev / CI): a fresh temp dir as cwd, a
       hard wall-clock timeout (process group killed on expiry), a scrubbed
       environment, and (on POSIX) RLIMIT_CPU / RLIMIT_AS / RLIMIT_FSIZE /
       RLIMIT_NPROC / RLIMIT_NOFILE / RLIMIT_CORE caps in a preexec hook. These
       bound *resource use* only — they do NOT provide network/FS isolation,
       which is why the container backend exists and is used in production.

The backend choice never affects the *verdict*: the harness and result parsing
are identical, so a pass in CI (in-process) is a pass in prod (container), and
a missing/failed engine falls back rather than auto-passing.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import functools
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Hard limits — deliberately conservative. Grading a single function should be
# fast and tiny; anything that needs more is treated as a failure, not a pass.
DEFAULT_TIMEOUT_SECONDS = 8
MAX_TIMEOUT_SECONDS = 20
MAX_OUTPUT_CHARS = 20_000
_CPU_SECONDS = 10          # RLIMIT_CPU (POSIX only)
_ADDRESS_SPACE_BYTES = 512 * 1024 * 1024   # 512 MB RLIMIT_AS
_FILE_SIZE_BYTES = 16 * 1024 * 1024        # 16 MB RLIMIT_FSIZE
_MAX_PROCESSES = 64        # RLIMIT_NPROC — stop fork bombs taking down the host
_MAX_OPEN_FILES = 256      # RLIMIT_NOFILE — bound fd exhaustion

SUPPORTED_LANGUAGES = {"python", "javascript"}
# Languages we recognise but cannot safely auto-grade on the backend yet.
# These return needs_review instead of ever auto-passing (fail-closed).
NEEDS_REVIEW_LANGUAGES = {"bash", "shell", "sh"}


@dataclass
class TestOutcome:
    name: str
    passed: bool
    message: str = ""
    hidden: bool = False


@dataclass
class GradeResult:
    """Outcome of grading a code submission against a set of tests."""
    ran: bool                       # did the code execute at all?
    all_passed: bool                # did every REQUIRED test pass?
    needs_review: bool = False      # language can't be auto-graded -> manual
    error: str = ""                 # compile / runtime / harness error
    stdout: str = ""
    outcomes: list[TestOutcome] = field(default_factory=list)

    def public_dict(self, reveal_hidden_names: bool = False) -> dict[str, Any]:
        """Serialise WITHOUT leaking hidden test internals.

        Hidden test *logic* never appears here (it was only ever a server-side
        string). Hidden test *names* stay masked unless the caller explicitly
        opts in (e.g. after the scenario is already solved).
        """
        tests = []
        for o in self.outcomes:
            if o.hidden and not reveal_hidden_names:
                tests.append({
                    "name": "Hidden test",
                    "passed": o.passed,
                    "hidden": True,
                    # message intentionally omitted — could leak expected values
                })
            else:
                tests.append({
                    "name": o.name,
                    "passed": o.passed,
                    "message": (o.message or "")[:500],
                    "hidden": o.hidden,
                })
        return {
            "ran": self.ran,
            "all_passed": self.all_passed,
            "needs_review": self.needs_review,
            "error": (self.error or "")[:2000],
            "stdout": (self.stdout or "")[:MAX_OUTPUT_CHARS],
            "tests": tests,
            "passed_count": sum(1 for o in self.outcomes if o.passed),
            "total_count": len(self.outcomes),
        }


def language_runtime_available(language: str) -> bool:
    lang = (language or "").lower()
    if lang == "python":
        return True  # we always have the running interpreter
    if lang == "javascript":
        if shutil.which("node") is not None:
            return True
        # Production grades JS inside the Docker sandbox (node:20-alpine) even when
        # the app host has no node binary installed.
        try:
            from apps.labs import sandbox_runner
            return (
                sandbox_runner.docker_sandbox_enabled()
                and sandbox_runner.docker_runtime_available()
            )
        except Exception:
            return False
    return False


# ── low-level: run one program in a sandbox ────────────────────────────────

def _posix_preexec(limit_address_space: bool = True):
    """Drop the child into its own process group and apply resource limits.

    Running in a new session means a timeout can kill the WHOLE group (so a
    forked grandchild can't outlive the grade). Resource limits are best-effort:
    not every platform supports every limit, and we never want limit-setting to
    crash the grader, so each is guarded.

    `limit_address_space` is skipped for runtimes like Node/V8 that reserve a
    large *virtual* address space at startup — an RLIMIT_AS that is fine for
    CPython makes node abort immediately on Linux. Node memory is instead bounded
    by --max-old-space-size plus the CPU limit and wall-clock timeout.

    SECURITY NOTE: these rlimits bound *resource use* only. They do NOT provide
    network or filesystem isolation — user code still runs as this OS user and
    can read host files / open sockets. This in-process path is the FALLBACK for
    dev/CI; production isolates network + filesystem by running the grader in a
    dedicated network-less, read-only, non-root container (see
    apps.labs.sandbox_runner, enabled via settings.SANDBOX_DOCKER) per
    docs/SECURITY_AUDIT.md finding C-01.
    """
    try:
        os.setsid()
    except OSError:
        pass
    # No core dumps (a crash could otherwise spill process memory to disk) and a
    # tight umask so any file the child writes isn't group/world readable.
    try:
        os.umask(0o077)
    except OSError:
        pass
    try:
        import resource
        limits = [
            (resource.RLIMIT_CPU, _CPU_SECONDS, _CPU_SECONDS),
            (resource.RLIMIT_FSIZE, _FILE_SIZE_BYTES, _FILE_SIZE_BYTES),
            # Anti fork-bomb: cap processes for the child. Best-effort — on a
            # shared uid the kernel counts existing processes too, so we never
            # let a failure here crash the grade (guarded below).
            (resource.RLIMIT_NPROC, _MAX_PROCESSES, _MAX_PROCESSES),
            (resource.RLIMIT_NOFILE, _MAX_OPEN_FILES, _MAX_OPEN_FILES),
            (resource.RLIMIT_CORE, 0, 0),
        ]
        if limit_address_space:
            limits.append((resource.RLIMIT_AS, _ADDRESS_SPACE_BYTES, _ADDRESS_SPACE_BYTES))
        for res, soft, hard in limits:
            try:
                resource.setrlimit(res, (soft, hard))
            except (ValueError, OSError):
                continue
    except ImportError:
        pass


def _scrubbed_env() -> dict[str, str]:
    """A minimal environment with nothing inherited that could grant access."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": tempfile.gettempdir(),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        # No network proxies, no cloud creds, no DB urls.
        "NODE_OPTIONS": "--max-old-space-size=256",
    }


def _run_program(
    argv: list[str],
    cwd: str,
    timeout: int,
    stdin_data: str = "",
    limit_address_space: bool = True,
) -> tuple[int | None, str, str, bool]:
    """Run argv in cwd. Returns (returncode, stdout, stderr, timed_out)."""
    preexec = (
        functools.partial(_posix_preexec, limit_address_space=limit_address_space)
        if os.name == "posix" else None
    )
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_scrubbed_env(),
            text=True,
            preexec_fn=preexec,
            start_new_session=(os.name == "posix"),
        )
    except (OSError, ValueError) as exc:
        return None, "", f"failed to start runtime: {exc}", False

    timed_out = False
    try:
        stdout, stderr = proc.communicate(input=stdin_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc)
        try:
            stdout, stderr = proc.communicate(timeout=3)
        except Exception:
            stdout, stderr = "", ""
    except Exception as exc:  # pragma: no cover - defensive
        _kill_process_tree(proc)
        return None, "", f"runtime error: {exc}", False

    return proc.returncode, stdout or "", stderr or "", timed_out


def _kill_process_tree(proc: "subprocess.Popen") -> None:
    try:
        if os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass


# ── harness builders ────────────────────────────────────────────────────────
# We build a single self-contained program: the user's code + the test cases +
# a tiny runner that prints a machine-readable result line. This keeps grading
# to ONE sandboxed process per submission and avoids importing user modules in
# our own interpreter (which would be unsafe and could pollute state).

_PY_RESULT_PREFIX = "__FIXITLAB_RESULT__:"
_JS_RESULT_PREFIX = "__FIXITLAB_RESULT__:"


def _build_python_harness(user_code: str, tests: list[dict]) -> str:
    """Compose a Python program that runs each test and emits a JSON verdict.

    Each test dict has {name, code, hidden}. `code` runs inside a function with
    the user's globals in scope; raising (e.g. via assert) marks it failed.
    """
    payload = json.dumps(
        [{"name": t.get("name", f"test_{i}"),
          "code": t.get("code", ""),
          "hidden": bool(t.get("hidden"))}
         for i, t in enumerate(tests)]
    )
    # The user's code and the tests are embedded as data and exec'd inside the
    # sandboxed child only — never in our process.
    return (
        "import json, sys, io, traceback\n"
        "_USER_SRC = " + repr(user_code) + "\n"
        "_TESTS = json.loads(" + repr(payload) + ")\n"
        "_g = {'__name__': '__fixitlab__'}\n"
        "_results = []\n"
        "_compile_error = None\n"
        "try:\n"
        "    exec(compile(_USER_SRC, '<solution>', 'exec'), _g)\n"
        "except Exception:\n"
        "    _compile_error = traceback.format_exc(limit=3)\n"
        "for _t in _TESTS:\n"
        "    if _compile_error is not None:\n"
        "        _results.append({'name': _t['name'], 'passed': False, 'hidden': _t['hidden'], 'message': 'solution failed to load'})\n"
        "        continue\n"
        "    _local = dict(_g)\n"
        "    try:\n"
        "        exec(compile(_t['code'], '<test:'+_t['name']+'>', 'exec'), _local)\n"
        "        _results.append({'name': _t['name'], 'passed': True, 'hidden': _t['hidden'], 'message': ''})\n"
        "    except AssertionError as _e:\n"
        "        _results.append({'name': _t['name'], 'passed': False, 'hidden': _t['hidden'], 'message': (str(_e) or 'assertion failed')})\n"
        "    except Exception:\n"
        "        _results.append({'name': _t['name'], 'passed': False, 'hidden': _t['hidden'], 'message': traceback.format_exc(limit=2).splitlines()[-1] if traceback.format_exc(limit=2).strip() else 'error'})\n"
        "sys.stdout.write('\\n" + _PY_RESULT_PREFIX + "' + json.dumps({'compile_error': _compile_error, 'results': _results}))\n"
    )


def _build_js_harness(user_code: str, tests: list[dict]) -> str:
    """Compose a Node program that runs each test and emits a JSON verdict.

    Each test runs in a fresh Function whose body is `user_code` immediately
    followed by the test snippet, so the test sees the user's declarations
    (functions, consts, classes) through normal lexical scope. assert() throws
    on failure. A standalone compile of the user code first surfaces syntax
    errors as a single compile_error rather than N identical test failures.
    """
    payload = json.dumps(
        [{"name": t.get("name", f"test_{i}"),
          "code": t.get("code", ""),
          "hidden": bool(t.get("hidden"))}
         for i, t in enumerate(tests)]
    )
    user_src_json = json.dumps(user_code)
    return (
        "const TESTS = " + payload + ";\n"
        "const USER_SRC = " + user_src_json + ";\n"
        "const assert = (c, m) => { if (!c) throw new Error(m || 'assertion failed'); };\n"
        "const results = [];\n"
        "let compileError = null;\n"
        "try { new Function('assert', USER_SRC); }\n"
        "catch (e) { compileError = String(e && e.stack ? e.stack : e); }\n"
        "for (const t of TESTS) {\n"
        "  if (compileError !== null) { results.push({name:t.name, passed:false, hidden:t.hidden, message:'solution failed to load'}); continue; }\n"
        "  try {\n"
        "    const fn = new Function('assert', USER_SRC + '\\n;(function(){\\n' + t.code + '\\n})();');\n"
        "    fn(assert);\n"
        "    results.push({name:t.name, passed:true, hidden:t.hidden, message:''});\n"
        "  } catch (e) { results.push({name:t.name, passed:false, hidden:t.hidden, message:String(e && e.message ? e.message : e)}); }\n"
        "}\n"
        "process.stdout.write('\\n" + _JS_RESULT_PREFIX + "' + JSON.stringify({compile_error: compileError, results}));\n"
    )


def _parse_verdict(stdout: str) -> dict | None:
    idx = stdout.rfind(_PY_RESULT_PREFIX)
    if idx == -1:
        return None
    try:
        return json.loads(stdout[idx + len(_PY_RESULT_PREFIX):])
    except (ValueError, json.JSONDecodeError):
        return None


# ── execution backend dispatch ──────────────────────────────────────────────

class InProcessExecutionForbidden(RuntimeError):
    """Raised when in-process grading is refused (production fail-closed).

    SECURITY_AUDIT S-01: in production we must never execute untrusted user code
    in the backend process (the container bind-mounts the Docker socket; an
    in-process escape could reach the daemon → host root). When the container
    sandbox is enabled but unavailable, we refuse rather than fall back, and
    ``grade_submission`` turns this into a ``needs_review`` verdict.
    """


def _inprocess_grading_allowed() -> bool:
    """Whether running user code in THIS process is permitted.

    The signal is ``SANDBOX_DOCKER``: when the operator has turned the container
    sandbox ON (production default — see settings.SANDBOX_DOCKER, which defaults
    True when DEBUG is False), in-process grading is a host-isolation hole and is
    FORBIDDEN — grading must use the container or fail closed. When the sandbox is
    OFF (dev/CI, and Django's test runner which forces DEBUG=False), the
    in-process rlimit subprocess is the accepted backend so grading works without
    a Docker engine.

    We key on SANDBOX_DOCKER rather than DEBUG because Django's test runner sets
    ``settings.DEBUG = False`` for every test; keying on DEBUG would forbid
    in-process grading during the test suite (and the green pipeline) even though
    no container engine is present there. SANDBOX_DOCKER is the operator's
    explicit "I have a sandbox, use it" switch and stays False in dev/CI/tests.
    """
    from django.conf import settings
    return not bool(getattr(settings, "SANDBOX_DOCKER", False))


def _execute(
    language: str,
    harness_source: str,
    script_name: str,
    argv: list[str],
    workdir: str,
    timeout: int,
    *,
    limit_address_space: bool,
) -> tuple[int | None, str, str, bool]:
    """Run the harness via the best available backend.

    Returns (returncode, stdout, stderr, timed_out). Prefers the isolated
    Docker container (network-less, read-only, non-root — SECURITY_AUDIT C-01/
    S-01) when SANDBOX_DOCKER is on and the engine is reachable.

    SECURITY_AUDIT S-01 — FAIL CLOSED in production. If the container backend is
    unavailable we fall back to the in-process subprocess ONLY in dev/CI
    (DEBUG=True). In production we refuse: running untrusted user code in the
    backend process — which bind-mounts the Docker socket for trusted monitoring
    — could let a sandbox escape reach the daemon and root the host. Instead we
    raise ``InProcessExecutionForbidden`` and ``grade_submission`` returns a safe
    ``needs_review`` verdict (never a silent on-host execution, never an
    auto-pass).
    """
    try:
        from apps.labs import sandbox_runner
        use_container = sandbox_runner.docker_runtime_available()
        sandbox_enabled = sandbox_runner.docker_sandbox_enabled()
    except Exception:  # pragma: no cover - settings/SDK issue
        use_container = False
        sandbox_enabled = False

    if use_container:
        try:
            return sandbox_runner.run_in_container(
                language, script_name, harness_source, timeout,
            )
        except sandbox_runner.SandboxUnavailable as exc:
            logger.warning(
                "code_exec: container sandbox unavailable (%s).", exc,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "code_exec: container sandbox raised %r.", exc,
            )

    # Container backend not used or it failed. Decide whether the in-process
    # fallback is permitted.
    if not _inprocess_grading_allowed():
        logger.error(
            "code_exec: refusing in-process grading in production "
            "(SANDBOX_DOCKER=%s, container reachable=%s). Failing closed.",
            sandbox_enabled, use_container,
        )
        raise InProcessExecutionForbidden(
            "container sandbox required in production; in-process grading refused"
        )

    return _run_program(
        argv, workdir, timeout, limit_address_space=limit_address_space,
    )


# ── public entry point ──────────────────────────────────────────────────────

def grade_submission(
    language: str,
    user_code: str,
    tests: list[dict],
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> GradeResult:
    """Run user_code against `tests` in a sandbox and return a GradeResult.

    `tests` is a list of {name, code, hidden}. A test passes if its snippet runs
    without raising. all_passed is True ONLY when every test ran and passed —
    an empty test list, a missing runtime, a compile error, or a timeout all
    fail closed (all_passed=False).
    """
    lang = (language or "").lower()
    timeout = max(1, min(int(timeout or DEFAULT_TIMEOUT_SECONDS), MAX_TIMEOUT_SECONDS))

    if lang in NEEDS_REVIEW_LANGUAGES:
        return GradeResult(
            ran=False, all_passed=False, needs_review=True,
            error=f"{lang} submissions need manual review — not auto-graded.",
        )
    if lang not in SUPPORTED_LANGUAGES:
        return GradeResult(
            ran=False, all_passed=False, needs_review=True,
            error=f"Unsupported language '{language}' — needs review.",
        )
    if not language_runtime_available(lang):
        # Fail closed: if we can't run it, we never call it a pass.
        return GradeResult(
            ran=False, all_passed=False, needs_review=True,
            error=f"Runtime for '{lang}' is not available on the server — needs review.",
        )
    if not tests:
        # No tests means we cannot prove correctness. Never auto-pass.
        return GradeResult(
            ran=False, all_passed=False,
            error="No tests defined for this scenario — cannot validate.",
        )

    workdir = tempfile.mkdtemp(prefix="fixitlab_grade_")
    try:
        if lang == "python":
            harness = _build_python_harness(user_code, tests)
            script_name = "_runner.py"
            script = os.path.join(workdir, script_name)
            with open(script, "w", encoding="utf-8") as fh:
                fh.write(harness)
            argv = [sys.executable, "-I", "-B", script]
        else:  # javascript
            harness = _build_js_harness(user_code, tests)
            script_name = "_runner.js"
            script = os.path.join(workdir, script_name)
            with open(script, "w", encoding="utf-8") as fh:
                fh.write(harness)
            node = shutil.which("node") or "node"
            argv = [node, script]

        # Pick the execution backend. Container isolation (network-less,
        # read-only, non-root) is preferred when enabled+reachable; otherwise we
        # fall back to the in-process subprocess. The verdict is identical either
        # way — only the isolation differs.
        #
        # Node/V8 reserves a huge virtual address space at startup, so RLIMIT_AS
        # (sized for CPython) would make it abort on Linux. Skip the AS limit for
        # node in the in-process path; --max-old-space-size + RLIMIT_CPU + the
        # timeout still bound it.
        try:
            rc, stdout, stderr, timed_out = _execute(
                lang, harness, script_name, argv, workdir, timeout,
                limit_address_space=(lang != "javascript"),
            )
        except InProcessExecutionForbidden as exc:
            # SECURITY_AUDIT S-01: production has no usable container sandbox and
            # in-process grading is forbidden. Fail closed: never auto-pass,
            # never run on the host — route to manual review.
            logger.error("code_exec: grading deferred to review (fail-closed): %s", exc)
            return GradeResult(
                ran=False, all_passed=False, needs_review=True,
                error="Code grading is temporarily unavailable. Your submission was "
                      "saved for review — it was not auto-graded.",
            )

        if timed_out:
            return GradeResult(
                ran=True, all_passed=False,
                error=f"Execution timed out after {timeout}s (possible infinite loop).",
                stdout=stdout,
            )

        verdict = _parse_verdict(stdout)
        if verdict is None:
            # The harness never printed a verdict — treat as a hard failure.
            err = (stderr or "").strip() or "Code did not produce a result."
            return GradeResult(ran=False, all_passed=False, error=err, stdout=stdout)

        if verdict.get("compile_error"):
            outcomes = [
                TestOutcome(t.get("name", f"test_{i}"), False,
                            "solution failed to load", bool(t.get("hidden")))
                for i, t in enumerate(tests)
            ]
            return GradeResult(
                ran=False, all_passed=False,
                error=str(verdict["compile_error"])[:2000],
                stdout=stdout, outcomes=outcomes,
            )

        outcomes = [
            TestOutcome(
                name=r.get("name", "test"),
                passed=bool(r.get("passed")),
                message=str(r.get("message", "")),
                hidden=bool(r.get("hidden")),
            )
            for r in verdict.get("results", [])
        ]
        # Strip the machine verdict line from the user-visible stdout.
        clean_stdout = stdout.split("\n" + _PY_RESULT_PREFIX, 1)[0]
        all_passed = bool(outcomes) and all(o.passed for o in outcomes)
        return GradeResult(
            ran=True, all_passed=all_passed,
            stdout=clean_stdout, outcomes=outcomes,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
