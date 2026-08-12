"""
Docker exec attach stream with strong references to docker-py HTTP response objects.

Without holding the HTTP response, docker-py garbage-collects the connection on Unix
sockets and the exec stream drops after ~1–2 seconds (terminal reconnect loop).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Optional

from apps.labs.provisioner.exec_socket import (
    DockerExecSocket,
    exec_close,
    exec_recv,
    exec_send,
    exec_set_timeout,
    start_exec_stream,
)

logger = logging.getLogger(__name__)

_registry_lock = threading.Lock()
# OrderedDict so the ceiling evicts least-recently-registered first.
_active_holders: "OrderedDict[str, ExecStreamHolder]" = OrderedDict()

# Audit Z5-7. This registry is process-local, but `release_holder(session_key)` is
# also called from `terminate_lab_session` — which runs in whatever process handled
# the termination (an HTTP request or a Celery worker), not the uvicorn worker that
# registered the holder. In that process the pop is a no-op, and the entry survives
# in the holding worker forever.
#
# That is worse than an ordinary memory leak. Each orphaned holder deliberately pins
# the docker-py client and the underlying HTTP response as GC roots (see
# `extra_roots` below — the exec stream drops after a second or two without them),
# so every orphan holds **a live socket to the D4 docker daemon**. The leak is in
# file descriptors against another host.
#
# The WebSocket disconnect path stays the primary release. These bounds are the
# backstop for the cases where it cannot run: a worker restart, an ungraceful close,
# or a release issued from the wrong process. Same shape as the Z5-1 playground
# session cap (`labs/playground_engine.py`).
MAX_HOLDERS = 500          # hard ceiling on concurrently-tracked exec streams
HOLDER_TTL_SECONDS = 4 * 60 * 60   # comfortably beyond the longest lab duration


class ExecStreamHolder:
    """Socket wrapper that preserves docker-py GC roots."""

    __slots__ = ("socket", "_roots", "exec_id", "registered_at")

    def __init__(
        self,
        socket: DockerExecSocket,
        exec_id: str = "",
        *,
        extra_roots: tuple = (),
    ):
        self.socket = socket
        self.exec_id = exec_id or ""
        self._roots = tuple(r for r in extra_roots if r is not None)
        self.registered_at = time.monotonic()

    def send(self, data: bytes) -> None:
        exec_send(self.socket, data)

    def recv(self, size: int) -> bytes:
        return exec_recv(self.socket, size)

    def set_timeout(self, seconds: float) -> None:
        exec_set_timeout(self.socket, seconds)

    def close(self) -> None:
        exec_close(self.socket)


def _holder_key(session_key: str, holder: ExecStreamHolder) -> str:
    suffix = holder.exec_id or id(holder)
    return f"{session_key}:{suffix}"


def _evict_stale_locked(now: float) -> list["ExecStreamHolder"]:
    """Drop expired holders and enforce the ceiling. Caller must hold the lock.

    Returns the evicted holders so the caller can close them *outside* the lock —
    `close()` touches a socket and can block, and holding the registry lock across
    that would stall every other terminal connection in this worker.
    """
    evicted: list[ExecStreamHolder] = []
    for key in [
        k for k, h in _active_holders.items()
        if now - h.registered_at > HOLDER_TTL_SECONDS
    ]:
        evicted.append(_active_holders.pop(key))
    while len(_active_holders) > MAX_HOLDERS:
        _, victim = _active_holders.popitem(last=False)
        evicted.append(victim)
    return evicted


def _close_quietly(holders) -> None:
    for holder in holders:
        try:
            holder.close()
        except Exception:
            # Best-effort: the point of eviction is to release the descriptor, and a
            # socket that is already broken has done that for us.
            logger.debug("Evicted exec holder %s failed to close", holder.exec_id[:12])


def register_holder(session_key: str, holder: ExecStreamHolder) -> None:
    """Track holder without closing other active exec streams for the same lab session."""
    if not session_key:
        return
    with _registry_lock:
        _active_holders[_holder_key(session_key, holder)] = holder
        stale = _evict_stale_locked(time.monotonic())
    if stale:
        logger.warning(
            "exec_stream: evicted %d orphaned holder(s); %d tracked. Orphans mean a "
            "disconnect path did not run — each was pinning a docker client and a "
            "live socket to the D4 daemon (audit Z5-7).",
            len(stale), len(_active_holders),
        )
    _close_quietly(stale)


def tracked_holder_count() -> int:
    """Number of exec streams this process is holding open. Test/ops introspection."""
    with _registry_lock:
        return len(_active_holders)


def release_holder(session_key: str, holder: Optional[ExecStreamHolder] = None) -> None:
    with _registry_lock:
        if holder is not None and session_key:
            _active_holders.pop(_holder_key(session_key, holder), None)
        elif session_key:
            prefix = f"{session_key}:"
            for key in list(_active_holders.keys()):
                if key.startswith(prefix) or key == session_key:
                    _active_holders.pop(key, None)
    if holder:
        try:
            holder.close()
        except Exception:
            pass


def open_docker_exec(
    docker_client,
    container_id: str,
    *,
    session_key: str = "",
    ensure_tmux: bool = False,
) -> ExecStreamHolder:
    """
    Open an interactive shell in the container.

    Each WebSocket connection gets its own exec attach. The HTTP response from
    exec_start is kept on DockerExecSocket so Unix-socket Docker hosts stay connected.
    """
    container = docker_client.containers.get(container_id)
    api = docker_client.api

    last_error = None
    shells: list[list[str]] = [
        ["/bin/bash", "--noprofile", "--norc", "-i"],
        ["/bin/bash", "-i"],
        ["/bin/sh", "-i"],
    ]

    for cmd in shells:
        try:
            exec_instance = api.exec_create(
                container.id,
                cmd=cmd,
                stdin=True,
                tty=True,
                stderr=True,
                stdout=True,
                user="root",
                workdir="/root",
                environment={
                    "TERM": "xterm-256color",
                    "COLUMNS": "120",
                    "LINES": "40",
                    "PS1": r"\u@\h:\w\$ ",
                },
            )
            exec_id = exec_instance.get("Id", "")
            wrapped = start_exec_stream(api, exec_id, tty=True)
            roots = (wrapped, wrapped._response, api, docker_client, container, exec_instance)
            holder = ExecStreamHolder(wrapped, exec_id, extra_roots=roots)
            if session_key:
                register_holder(session_key, holder)
            _wake_shell_prompt(holder)
            return holder
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Exec attach %s failed for %s: %s",
                " ".join(cmd),
                container_id[:12],
                exc,
            )
    raise last_error or RuntimeError("Failed to open docker exec stream")


def _wake_shell_prompt(holder: ExecStreamHolder) -> None:
    """Send Enter so bash emits a prompt after attach."""
    try:
        holder.send(b"\r")
    except Exception:
        pass
