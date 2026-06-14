"""In-memory simulated terminal streams for boot/GPU/Ansible/bare-metal labs."""

from __future__ import annotations

import queue
import threading
import uuid
from typing import Callable

from .terminal_input import TerminalLineEditor


class SimulationStreamHolder:
    """Mimics ExecStreamHolder for WebSocket terminal consumer."""

    def __init__(
        self,
        handler: Callable[[str], str],
        *,
        prompt: str = "root@lab:~# ",
        dynamic_prompt: Callable[[], str] | None = None,
    ):
        self._handler = handler
        self._prompt = prompt
        self._dynamic_prompt = dynamic_prompt
        self._editor = TerminalLineEditor()
        self._out_q: queue.Queue[bytes] = queue.Queue()
        self._closed = False
        self._timeout = 60.0
        self._lock = threading.Lock()
        self.exec_id = f"sim-exec-{uuid.uuid4().hex[:12]}"
        self._emit("\r\n\x1b[1;36m[FixitLab Simulation — RHEL 9]\x1b[0m\r\n")
        self._emit_prompt()

    @property
    def prompt(self) -> str:
        if self._dynamic_prompt:
            return self._dynamic_prompt()
        return self._prompt

    def set_prompt(self, prompt: str) -> None:
        self._prompt = prompt

    def _emit(self, text: str) -> None:
        if not self._closed:
            self._out_q.put(text.encode("utf-8", errors="replace"))

    def _emit_prompt(self) -> None:
        self._emit(f"\r\n{self.prompt}")

    def _redraw_line(self, buffer: str) -> None:
        self._emit("\r")
        self._emit(self.prompt + buffer)
        # Clear tail if line got shorter
        pad = max(0, 80 - len(self.prompt) - len(buffer))
        self._emit(" " * pad + "\r")
        self._emit(self.prompt + buffer)
        if buffer:
            self._emit(f"\x1b[{len(self.prompt) + len(buffer)}G")

    def send(self, data: bytes) -> None:
        if self._closed:
            return
        try:
            chunk = data.decode("utf-8", errors="replace")
        except Exception:
            return

        for action, payload in self._editor.process(chunk):
            if action == "emit":
                self._emit(payload)
            elif action == "cursor_left":
                self._emit("\x1b[D")
            elif action == "cursor_right":
                self._emit("\x1b[C")
            elif action == "redraw_line":
                self._redraw_line(payload)
            elif action == "clear_screen":
                self._emit("\x1b[2J\x1b[H")
                self._redraw_line(self._editor.buffer)
            elif action == "interrupt":
                self._editor.reset()
                self._emit("^C\r\n")
                self._emit_prompt()
            elif action == "submit":
                line = self._editor.submit()
                self._emit("\r\n")
                if line.strip():
                    try:
                        out = self._handler(line) or ""
                    except Exception as exc:
                        out = f"\x1b[1;31mSimulation error: {exc}\x1b[0m"
                    if out == "__REBOOT__":
                        self._editor.reset()
                        self._emit_prompt()
                        continue
                    if out:
                        self._emit(out if out.endswith("\r\n") else out + "\r\n")
                    # Handler may change prompt (boot phases)
                    if out and "login:" in out.lower():
                        self.set_prompt("")
                    elif out and "grub rescue" in out.lower():
                        self.set_prompt("grub rescue> ")
                    elif out and "grub>" in out.lower() and "GNU GRUB" in out:
                        self.set_prompt("grub> ")
                self._emit_prompt()

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
