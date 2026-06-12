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
# exec_id -> strong refs that must outlive the holder (docker-py GC guard)
_gc_roots: dict[str, tuple] = {}


class ExecStreamHolder:
    """Socket wrapper that preserves docker-py GC roots."""

    __slots__ = ("socket", "_roots", "exec_id", "_session_key")

    def __init__(
        self,
        socket,
        exec_id: str = "",
        *,
        extra_roots: tuple = (),
        session_key: str = "",
    ):
        self.socket = socket
        self.exec_id = exec_id or ""
        self._session_key = session_key or ""
        # Strong refs: docker API response, wrapper socket, container, client, etc.
        self._roots = tuple(r for r in extra_roots if r is not None)

    def send(self, data: bytes) -> None:
        exec_send(self.socket, data)

    def recv(self, size: int) -> bytes:
        return exec_recv(self.socket, size)

    def set_timeout(self, seconds: float) -> None:
        exec_set_timeout(self.socket, seconds)

    def close(self) -> None:
        exec_close(self.socket)

    def is_alive(self) -> bool:
        try:
            return self.socket.fileno() >= 0
        except Exception:
            return False


def get_registered_holder(session_key: str) -> Optional["ExecStreamHolder"]:
    if not session_key:
        return None
    with _registry_lock:
        holder = _active_holders.get(session_key)
    if holder and holder.is_alive():
        return holder
    if holder:
        release_holder(session_key, holder)
    return None


def register_holder(session_key: str, holder: ExecStreamHolder) -> None:
    with _registry_lock:
        old = _active_holders.pop(session_key, None)
        if old and old is not holder:
            _drop_gc_roots(old.exec_id)
            try:
                old.close()
            except Exception:
                pass
        _active_holders[session_key] = holder
        if holder.exec_id:
            _gc_roots[holder.exec_id] = holder._roots


def release_holder(session_key: str, holder: Optional[ExecStreamHolder] = None) -> None:
    with _registry_lock:
        current = _active_holders.get(session_key)
        if holder is not None and current is not holder:
            return
        removed = _active_holders.pop(session_key, None)
    if removed:
        _drop_gc_roots(removed.exec_id)
        try:
            removed.close()
        except Exception:
            pass


def _drop_gc_roots(exec_id: str) -> None:
    if exec_id:
        _gc_roots.pop(exec_id, None)


def _collect_roots(sock, *extra: Any) -> tuple:
    roots: list[Any] = [sock]
    for attr in ("_response", "_sock", "_container", "_exec", "_c", "_http_response"):
        val = getattr(sock, attr, None)
        if val is not None:
            roots.append(val)
    for item in extra:
        if item is not None:
            roots.append(item)
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

    Reuses an existing live holder for the same session when possible so WebSocket
    reconnects do not spawn competing exec streams.
    """
    if session_key:
        existing = get_registered_holder(session_key)
        if existing:
            _wake_shell_prompt(existing)
            return existing

    container = docker_client.containers.get(container_id)
    api = docker_client.api

    use_tmux = ensure_tmux and _ensure_tmux_session(container)

    last_error = None
    shells: list[list[str]] = [
        ["/bin/bash", "--noprofile", "--norc", "-i"],
        ["/bin/bash", "-i"],
        ["/bin/sh", "-i"],
    ]
    if use_tmux:
        shells.insert(0, ["tmux", "attach", "-d", "-t", _TMUX_SESSION])

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
            raw_sock = api.exec_start(
                exec_id,
                detach=False,
                tty=True,
                socket=True,
            )
            prepared = prepare_exec_socket(raw_sock)
            roots = _collect_roots(raw_sock, prepared, api, docker_client, container, exec_instance)
            holder = ExecStreamHolder(
                prepared,
                exec_id,
                extra_roots=roots,
                session_key=session_key,
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
