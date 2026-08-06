"""Containerised execution backend for the coding-IDE grader (SECURITY_AUDIT C-01).

The in-process grader in ``apps.labs.code_exec`` runs user-submitted code in the
same OS process as Daphne/Celery, isolated only by POSIX ``rlimits``. Those
limits bound *resource use* but provide **no network or filesystem isolation** —
user code can still open sockets (exfiltrate secrets, hit cloud metadata) and
read host files (JWT signing key, DB/Redis creds, hidden scenario tests).

This module runs each submission inside a **throwaway Docker container** with:

    --network none          no outbound or inbound network at all
    --read-only             read-only root filesystem
    a writable tmpfs /work  the ONLY place the child can write (size + noexec? no:
                            the runtime needs exec, so /work is the scratch dir)
    --user 65534:65534      runs as ``nobody`` (non-root)
    --cap-drop ALL          no Linux capabilities
    --security-opt no-new-privileges   can't regain privileges via setuid
    --pids-limit            anti fork-bomb
    --memory / --cpus       hard resource caps
    no bind mounts of app code/secrets — the harness is copied in via the API

The harness (user code + hidden tests + result-printing runner) is identical to
the one the in-process grader builds, so the verdict format is unchanged. The
harness source is streamed into the container with ``put_archive`` rather than a
bind mount, so this works even when the Docker engine is **remote**
(``DOCKER_HOST=ssh://root@labs-node`` / ``settings.DOCKER_SOCKET``) — the labs
droplet, not the web droplet, executes the code.

Integrity is preserved: this module only *runs* a program and returns
``(returncode, stdout, stderr, timed_out)`` — exactly like
``code_exec._run_program``. The pass/fail decision still lives in
``code_exec.grade_submission`` (fail-closed: a missing engine, a non-zero exit,
a timeout, or unparseable output never becomes a pass).

Enabled by ``settings.SANDBOX_DOCKER`` (default off so dev/CI keep using the
in-process fallback). When enabled but the engine is unreachable, the caller
falls back to the in-process grader so grading never hard-fails on infra.
"""

from __future__ import annotations

import io
import logging
import tarfile
import threading
import time as _time
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Tiny, ubiquitous base images that ship the interpreter we need. They are
# pulled once onto the labs Docker engine; grading never builds an image.
_DEFAULT_PYTHON_IMAGE = "python:3.12-alpine"
_DEFAULT_NODE_IMAGE = "node:20-alpine"

# Container resource caps — deliberately small. Grading one function is tiny.
_MEM_LIMIT = "256m"
_PIDS_LIMIT = 64
_NANO_CPUS = 1_000_000_000          # 1.0 CPU (docker expresses cpus as nano-cpus)
_TMPFS_WORK_BYTES = 32 * 1024 * 1024  # 32 MB writable scratch at /work
_NONROOT_UID_GID = "65534:65534"      # nobody:nogroup on alpine/debian

_WORKDIR = "/work"

# How long (on top of the program timeout) we wait for container teardown before
# giving up. Cleanup is best-effort; --rm + the kill below cover the common case.
_STOP_GRACE_SECONDS = 2

# Cache the "is Docker reachable?" probe so we don't ping the engine on every
# single submission. Re-probed after _PROBE_TTL seconds.
_PROBE_TTL = 60.0
_probe_lock = threading.Lock()
_probe_cache: dict[str, object] = {"ok": None, "ts": 0.0}

# Last-known engine health, kept so operators can *see* a Docker-socket outage
# instead of inferring it from a log line. ``docker_runtime_available`` is the
# only writer; ``sandbox_health`` is the read side (used by the grader's
# fail-closed alert and available to any ops/health surface).
#
# ``consecutive_failures`` is the useful number: a single failed probe is noise
# (a restart of the labs engine), a rising count is an outage that is making
# every coding lab ungradeable.
_health_lock = threading.Lock()
_health: dict[str, object] = {
    "last_ok": None,          # bool | None — None = never probed
    "last_error": "",         # str — reason the last probe failed
    "consecutive_failures": 0,
    "last_ok_monotonic": None,
}


def _record_probe(ok: bool, error: str = "") -> None:
    """Record a probe outcome for :func:`sandbox_health`."""
    with _health_lock:
        _health["last_ok"] = ok
        if ok:
            _health["consecutive_failures"] = 0
            _health["last_error"] = ""
            _health["last_ok_monotonic"] = _time.monotonic()
        else:
            _health["consecutive_failures"] = int(_health["consecutive_failures"]) + 1
            _health["last_error"] = error or "docker engine unreachable"


def sandbox_health() -> dict:
    """Snapshot of container-sandbox reachability for monitoring.

    Returns a plain dict (safe to JSON-encode) so an ops endpoint or an alert
    payload can report *why* coding labs are being deferred to review. Keys:
    ``enabled``, ``last_ok``, ``last_error``, ``consecutive_failures``,
    ``seconds_since_ok`` (None when never seen healthy this process).
    """
    with _health_lock:
        snapshot = dict(_health)
    last_ok_mono = snapshot.pop("last_ok_monotonic", None)
    snapshot["enabled"] = docker_sandbox_enabled()
    snapshot["seconds_since_ok"] = (
        None if last_ok_mono is None else round(_time.monotonic() - float(last_ok_mono), 1)
    )
    return snapshot


def reset_sandbox_health() -> None:
    """Clear probe + health caches. Test-only helper (module state is global)."""
    with _probe_lock:
        _probe_cache["ok"] = None
        _probe_cache["ts"] = 0.0
    with _health_lock:
        _health.update(
            last_ok=None, last_error="", consecutive_failures=0, last_ok_monotonic=None,
        )


def _image_for(language: str) -> Optional[str]:
    lang = (language or "").lower()
    # "sql" is graded by a Python harness driving stdlib sqlite3, so it runs in
    # the python image — no extra image to pull onto the labs engine.
    if lang in ("python", "sql"):
        return getattr(settings, "SANDBOX_PYTHON_IMAGE", None) or _DEFAULT_PYTHON_IMAGE
    if lang == "javascript":
        return getattr(settings, "SANDBOX_NODE_IMAGE", None) or _DEFAULT_NODE_IMAGE
    return None


def _runtime_argv(language: str, script_name: str) -> Optional[list[str]]:
    """Argv to run the harness *inside* the container (cwd is _WORKDIR)."""
    lang = (language or "").lower()
    if lang in ("python", "sql"):
        # -I isolated mode (ignore env/user site), -B no .pyc writes.
        return ["python3", "-I", "-B", script_name]
    if lang == "javascript":
        return ["node", script_name]
    return None


def _get_client():
    """Return a docker client bound to the configured engine, or None.

    Mirrors apps.labs.provisioner.docker_provisioner: uses settings.DOCKER_SOCKET
    (which may be a local unix socket OR a remote ssh:// engine — the dedicated
    labs Docker host). Import is local so a missing ``docker`` SDK never breaks
    import of this module in environments that don't use the container path.
    """
    try:
        import docker  # noqa: WPS433 — optional dependency, only needed here
    except Exception:  # pragma: no cover - docker SDK absent
        return None
    base_url = getattr(settings, "DOCKER_SOCKET", None)
    try:
        if base_url:
            return docker.DockerClient(base_url=base_url)
        return docker.from_env()
    except Exception as exc:  # pragma: no cover - engine misconfigured
        logger.debug("sandbox_runner: cannot construct docker client: %s", exc)
        return None


def docker_sandbox_enabled() -> bool:
    """True when the operator has opted into container-isolated grading."""
    return bool(getattr(settings, "SANDBOX_DOCKER", False))


def docker_runtime_available(force: bool = False) -> bool:
    """True when container grading is enabled AND the engine answers a ping.

    Result is cached briefly (probing a remote ssh engine is not free). The
    caller treats False as "use the in-process fallback".
    """
    if not docker_sandbox_enabled():
        return False
    now = _time.monotonic()
    with _probe_lock:
        cached = _probe_cache.get("ok")
        ts = float(_probe_cache.get("ts") or 0.0)
        if not force and cached is not None and (now - ts) < _PROBE_TTL:
            return bool(cached)

    client = _get_client()
    ok = False
    error = "docker client unavailable (SDK missing or engine misconfigured)"
    if client is not None:
        try:
            ok = bool(client.ping())
            if not ok:
                error = "docker ping returned falsy"
        except Exception as exc:
            logger.warning("sandbox_runner: docker ping failed (%s); using fallback", exc)
            ok = False
            error = f"docker ping failed: {exc}"
        finally:
            _close(client)

    _record_probe(ok, error)
    with _probe_lock:
        _probe_cache["ok"] = ok
        _probe_cache["ts"] = now
    return ok


def _close(client) -> None:
    try:
        client.close()
    except Exception:
        pass


def _ensure_image(client, image: str) -> None:
    """Pull the sandbox base image if the engine doesn't already have it.

    ``containers.create()`` (unlike ``run()``) NEVER pulls, so a freshly
    provisioned labs engine would raise ImageNotFound on the very first grade —
    which, under the production fail-closed policy (S-01), becomes a
    ``needs_review`` instead of a real grade and breaks coding scenarios. Pulling
    if-missing makes the sandbox self-sufficient (no deploy-time pre-pull
    dependency). The pull runs on the labs host, which has network; the grading
    container itself still runs ``network_mode="none"`` so user code never gets
    network. Raises ``SandboxUnavailable`` (the caller's normal unavailable path)
    if the pull fails.
    """
    try:
        client.images.get(image)
        return
    except Exception:
        pass  # not present locally — pull it below
    try:
        client.images.pull(image)
    except Exception as exc:
        raise SandboxUnavailable(f"could not pull sandbox image {image!r}: {exc}") from exc


def _harness_tar(script_name: str, source: str) -> bytes:
    """Pack the harness file into an in-memory tar for put_archive()."""
    data = source.encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=script_name)
        info.size = len(data)
        info.mode = 0o600
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def run_in_container(
    language: str,
    script_name: str,
    harness_source: str,
    timeout: int,
) -> tuple[Optional[int], str, str, bool]:
    """Run ``harness_source`` in a locked-down container.

    Returns ``(returncode, stdout, stderr, timed_out)`` — the SAME shape as
    ``code_exec._run_program`` so the grader can treat both backends uniformly.

    Raises ``SandboxUnavailable`` if the engine/image can't be used; the caller
    is expected to fall back to the in-process grader in that case (so grading
    degrades gracefully rather than hard-failing).
    """
    image = _image_for(language)
    argv = _runtime_argv(language, script_name)
    if image is None or argv is None:
        raise SandboxUnavailable(f"no container runtime mapping for language {language!r}")

    client = _get_client()
    if client is None:
        raise SandboxUnavailable("docker client unavailable")

    # Ensure the base image is present before create() (which never pulls).
    _ensure_image(client, image)

    container = None
    try:
        try:
            container = client.containers.create(
                image=image,
                command=argv,
                working_dir=_WORKDIR,
                # ── isolation ────────────────────────────────────────────────
                network_mode="none",          # no network at all
                network_disabled=True,
                read_only=True,               # read-only root fs
                user=_NONROOT_UID_GID,        # non-root (nobody)
                cap_drop=["ALL"],             # drop every capability
                security_opt=["no-new-privileges:true"],
                privileged=False,
                # writable scratch ONLY — small, in-memory, where the harness lives
                tmpfs={_WORKDIR: f"rw,size={_TMPFS_WORK_BYTES},mode=1777"},
                # ── resource caps ────────────────────────────────────────────
                mem_limit=_MEM_LIMIT,
                memswap_limit=_MEM_LIMIT,     # disallow swap beyond mem_limit
                pids_limit=_PIDS_LIMIT,       # anti fork-bomb
                nano_cpus=_NANO_CPUS,
                # ── env: nothing inherited ──────────────────────────────────
                environment={
                    "HOME": _WORKDIR,
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "NODE_OPTIONS": "--max-old-space-size=192",
                },
                stdin_open=False,
                detach=True,
                # No bind mounts: app source + secrets are never visible inside.
            )
        except Exception as exc:
            raise SandboxUnavailable(f"could not create sandbox container: {exc}") from exc

        # Stream the harness into the writable /work dir (works for remote engines).
        try:
            client.api.put_archive(container.id, _WORKDIR, _harness_tar(script_name, harness_source))
        except Exception as exc:
            raise SandboxUnavailable(f"could not stage harness into sandbox: {exc}") from exc

        timed_out = False
        try:
            container.start()
        except Exception as exc:
            raise SandboxUnavailable(f"could not start sandbox container: {exc}") from exc

        try:
            result = container.wait(timeout=timeout)
            returncode = int(result.get("StatusCode", 1)) if isinstance(result, dict) else 1
        except Exception:
            # Timeout (or a connection read-timeout against the engine): kill it.
            timed_out = True
            returncode = None
            _force_remove(container)
            container = None  # already removed
            return returncode, "", "", timed_out

        stdout = _logs(container, stdout=True, stderr=False)
        stderr = _logs(container, stdout=False, stderr=True)
        return returncode, stdout, stderr, timed_out
    finally:
        if container is not None:
            _force_remove(container)
        _close(client)


def _logs(container, *, stdout: bool, stderr: bool) -> str:
    try:
        raw = container.logs(stdout=stdout, stderr=stderr)
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw or "")
    except Exception:
        return ""


def _force_remove(container) -> None:
    try:
        container.remove(force=True, v=True)
    except Exception:
        try:
            container.kill()
        except Exception:
            pass


class SandboxUnavailable(RuntimeError):
    """Raised when the container backend can't run a submission.

    The grader catches this and falls back to the in-process sandbox so a
    transient engine problem degrades gracefully instead of failing the grade.
    """
