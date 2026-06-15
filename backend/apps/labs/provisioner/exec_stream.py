"""
Docker exec attach stream with strong references to docker-py HTTP response objects.

Without holding the HTTP response, docker-py garbage-collects the connection on Unix
sockets and the exec stream drops after ~1–2 seconds (terminal reconnect loop).
"""
from __future__ import annotations

import logging
import threading
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
_active_holders: dict[str, "ExecStreamHolder"] = {}


class ExecStreamHolder:
    """Socket wrapper that preserves docker-py GC roots."""

    __slots__ = ("socket", "_roots", "exec_id")

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


def register_holder(session_key: str, holder: ExecStreamHolder) -> None:
    """Track holder without closing other active exec streams for the same lab session."""
    if not session_key:
        return
    with _registry_lock:
        _active_holders[_holder_key(session_key, holder)] = holder


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
