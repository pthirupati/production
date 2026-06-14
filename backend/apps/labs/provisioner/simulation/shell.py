"""In-memory simulated terminal streams for boot/GPU/Ansible/bare-metal labs."""

from __future__ import annotations

import queue
import threading
import time
import uuid
from typing import Callable


class SimulationStreamHolder:
    """Mimics ExecStreamHolder for WebSocket terminal consumer."""

    def __init__(self, handler: Callable[[str], str], *, prompt: str = "root@lab:~# "):
        self._handler = handler
        self._prompt = prompt
        self._input_buf = ""
        self._out_q: queue.Queue[bytes] = queue.Queue()
        self._closed = False
        self._timeout = 60.0
        self._lock = threading.Lock()
        self.exec_id = f"sim-exec-{uuid.uuid4().hex[:12]}"
        # Initial banner + prompt
        self._emit("\r\n\x1b[1;36m[FixitLab Simulation]\x1b[0m\r\n")
        self._emit_prompt()

    def _emit(self, text: str) -> None:
        if not self._closed:
            self._out_q.put(text.encode("utf-8", errors="replace"))

    def _emit_prompt(self) -> None:
        self._emit(f"\r\n{self._prompt}")

    def send(self, data: bytes) -> None:
        if self._closed:
            return
        try:
            chunk = data.decode("utf-8", errors="replace")
        except Exception:
            return

        for ch in chunk:
            if ch in ("\r", "\n"):
                line = self._input_buf.strip()
                self._input_buf = ""
                self._emit("\r\n")
                if line:
                    try:
                        out = self._handler(line) or ""
                    except Exception as exc:
                        out = f"\x1b[1;31mSimulation error: {exc}\x1b[0m"
                    if out:
                        self._emit(out if out.endswith("\r\n") else out + "\r\n")
                self._emit_prompt()
            elif ch == "\x7f" or ch == "\b":
                if self._input_buf:
                    self._input_buf = self._input_buf[:-1]
                    self._emit("\b \b")
            elif ch == "\x03":
                self._input_buf = ""
                self._emit("^C\r\n")
                self._emit_prompt()
            elif ch == "\x15":
                self._input_buf = ""
                self._emit("\r")
                self._emit_prompt()
            else:
                self._input_buf += ch
                self._emit(ch)

    def recv(self, size: int = 4096) -> bytes:
        if self._closed:
            return b""
        try:
            return self._out_q.get(timeout=self._timeout)
        except queue.Empty:
            raise TimeoutError()

    def set_timeout(self, seconds: float) -> None:
        self._timeout = max(0.1, float(seconds))

    def close(self) -> None:
        self._closed = True

    def setblocking(self, flag: bool) -> None:
        pass


# Session registry: session_id -> {resource_id, sim_type, state, streams}
_SIM_SESSIONS: dict[str, dict] = {}
_SIM_LOCK = threading.Lock()


def register_sim_session(session_id: str, resource_id: str, sim_type: str, state: dict) -> None:
    with _SIM_LOCK:
        _SIM_SESSIONS[str(session_id)] = {
            "resource_id": resource_id,
            "sim_type": sim_type,
            "state": state,
            "streams": {},
        }


def get_sim_session(session_id: str) -> dict | None:
    with _SIM_LOCK:
        return _SIM_SESSIONS.get(str(session_id))


def get_sim_session_by_resource(resource_id: str) -> dict | None:
    with _SIM_LOCK:
        for entry in _SIM_SESSIONS.values():
            if entry.get("resource_id") == resource_id:
                return entry
        return None


def drop_sim_session(session_id: str) -> None:
    with _SIM_LOCK:
        entry = _SIM_SESSIONS.pop(str(session_id), None)
        if entry:
            for stream in entry.get("streams", {}).values():
                try:
                    stream.close()
                except Exception:
                    pass
