"""
Docker exec attach stream with strong references to docker-py HTTP response objects.

Without holding the API response, docker-py garbage-collects the connection and the
exec stream drops after ~1–2 seconds (terminal reconnect loop).
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from apps.labs.provisioner.exec_socket import (
    exec_close,
    exec_recv,
    exec_send,
    exec_set_timeout,
    prepare_exec_socket,
)

logger = logging.getLogger(__name__)

_TMUX_SESSION = "fixitlab"
_registry_lock = threading.Lock()
# session_id -> ExecStreamHolder (keeps streams alive for the WS consumer lifetime)
_active_holders: dict[str, "ExecStreamHolder"] = {}


class ExecStreamHolder:
    """Socket wrapper that preserves docker-py GC roots."""

    __slots__ = ("socket", "_roots", "exec_id")

    def __init__(self, socket, exec_id: str = "", *, extra_roots: tuple = ()):
        self.socket = socket
        self.exec_id = exec_id or ""
        # Strong refs: docker API response, wrapper socket, container, etc.
        self._roots = tuple(r for r in extra_roots if r is not None)

    def send(self, data: bytes) -> None:
        exec_send(self.socket, data)

    def recv(self, size: int) -> bytes:
        return exec_recv(self.socket, size)

    def set_timeout(self, seconds: float) -> None:
        exec_set_timeout(self.socket, seconds)

    def close(self) -> None:
        exec_close(self.socket)


def register_holder(session_key: str, holder: ExecStreamHolder) -> None:
    with _registry_lock:
        old = _active_holders.pop(session_key, None)
        if old and old is not holder:
            try:
                old.close()
            except Exception:
                pass
        _active_holders[session_key] = holder


def release_holder(session_key: str, holder: Optional[ExecStreamHolder] = None) -> None:
    with _registry_lock:
        current = _active_holders.get(session_key)
        if holder is not None and current is not holder:
            return
        _active_holders.pop(session_key, None)
    if holder:
        try:
            holder.close()
        except Exception:
            pass


def _collect_roots(sock) -> tuple:
    roots = [sock]
    for attr in ("_response", "_sock", "_container", "_exec"):
        val = getattr(sock, attr, None)
        if val is not None:
            roots.append(val)
    return tuple(roots)


def open_docker_exec(
    docker_client,
    container_id: str,
    *,
    session_key: str = "",
    ensure_tmux: bool = True,
) -> ExecStreamHolder:
    """
    Open an interactive shell in the container.

    Uses a detached tmux session so WebSocket reconnects attach to the same shell
    state instead of starting a fresh exec that may drop when docker-py GC runs.
    """
    container = docker_client.containers.get(container_id)

    use_tmux = ensure_tmux and _ensure_tmux_session(container)

    last_error = None
    shells = []
    if use_tmux:
        shells.append(["tmux", "attach", "-d", "-t", _TMUX_SESSION])
    shells.extend(
        [
            ["/bin/bash", "--noprofile", "--norc", "-i"],
            ["/bin/bash", "-i"],
            ["/bin/sh", "-i"],
        ]
    )
    for cmd in shells:
        try:
            exec_instance = docker_client.api.exec_create(
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
            raw_sock = docker_client.api.exec_start(
                exec_instance["Id"],
                detach=False,
                tty=True,
                socket=True,
            )
            prepared = prepare_exec_socket(raw_sock)
            roots = _collect_roots(raw_sock) + (container, exec_instance)
            holder = ExecStreamHolder(
                prepared,
                exec_instance.get("Id", ""),
                extra_roots=roots,
            )
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


def _ensure_tmux_session(container) -> bool:
    """
    Create a long-lived tmux shell when tmux is already installed in the image.

    Never apt-install tmux on connect — that blocks the terminal for minutes with no output.
    """
    script = (
        "command -v tmux >/dev/null 2>&1 || exit 1; "
        f"tmux has-session -t {_TMUX_SESSION} 2>/dev/null || "
        f"tmux new-session -d -s {_TMUX_SESSION} "
        "bash -lc 'printf \"\\n\\r\"; export PS1=\"\\u@\\h:\\w\\$ \"; exec bash --noprofile --norc -i'; "
        "exit 0"
    )
    try:
        exit_code, _ = container.exec_run(
            ["/bin/bash", "-c", script],
            user="root",
            demux=True,
        )
        return exit_code == 0
    except Exception as exc:
        logger.debug("tmux bootstrap skipped: %s", exc)
        return False


def _wake_shell_prompt(holder: ExecStreamHolder) -> None:
    """Send Enter so bash/tmux emits a prompt after attach."""
    try:
        holder.send(b"\r")
    except Exception:
        pass
