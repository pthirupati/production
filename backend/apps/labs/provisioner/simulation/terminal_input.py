"""Parse xterm keystrokes — arrows, home/end, history."""

from __future__ import annotations

import re


class TerminalLineEditor:
    """Line editor with cursor position and command history."""

    def __init__(self, history_size: int = 100):
        self.buffer = ""
        self.cursor = 0
        self.history: list[str] = []
        self.history_idx = -1
        self.history_size = history_size
        self._esc_buf = ""

    def reset(self) -> None:
        self.buffer = ""
        self.cursor = 0
        self.history_idx = -1

    def submit(self) -> str:
        line = self.buffer
        if line.strip():
            if not self.history or self.history[-1] != line:
                self.history.append(line)
                if len(self.history) > self.history_size:
                    self.history.pop(0)
        self.reset()
        return line

    def process(self, data: str) -> list[tuple[str, str]]:
        """Return list of (action, payload) where action is emit|submit|noop."""
        events: list[tuple[str, str]] = []
        i = 0
        while i < len(data):
            ch = data[i]
            if self._esc_buf:
                self._esc_buf += ch
                if self._try_escape(events):
                    self._esc_buf = ""
                elif len(self._esc_buf) > 8:
                    self._esc_buf = ""
                i += 1
                continue
            if ch == "\x1b":
                self._esc_buf = ch
                i += 1
                continue
            if ch in ("\r", "\n"):
                events.append(("submit", self.buffer))
                i += 1
                continue
            if ch == "\x7f" or ch == "\b":
                events.extend(self._backspace())
                i += 1
                continue
            if ch == "\x03":  # Ctrl+C
                events.append(("interrupt", ""))
                i += 1
                continue
            if ch == "\x15":  # Ctrl+U
                events.extend(self._clear_line())
                i += 1
                continue
            if ch == "\x0c":  # Ctrl+L
                events.append(("clear_screen", ""))
                i += 1
                continue
            if ch == "\t":
                i += 1
                continue
            events.extend(self._insert(ch))
            i += 1
        return events

    def _try_escape(self, events: list[tuple[str, str]]) -> bool:
        seq = self._esc_buf
        # Arrow keys CSI
        m = re.fullmatch(r"\x1b\[([A-D])", seq)
        if m:
            d = m.group(1)
            if d == "A":
                events.extend(self._history_up())
            elif d == "B":
                events.extend(self._history_down())
            elif d == "C":
                events.extend(self._move_right())
            elif d == "D":
                events.extend(self._move_left())
            return True
        # SS3 arrows
        m = re.fullmatch(r"\x1bO([A-D])", seq)
        if m:
            self._esc_buf = "\x1b[" + m.group(1)
            return self._try_escape(events)
        # Home / End
        if seq in ("\x1b[H", "\x1b[1~", "\x1b[7~"):
            events.extend(self._home())
            return True
        if seq in ("\x1b[F", "\x1b[4~", "\x1b[8~"):
            events.extend(self._end())
            return True
        # Incomplete CSI — wait for more
        if re.fullmatch(r"\x1b\[?\d*;?\d*[~A-D]?$", seq) and len(seq) < 8:
            return False
        return seq.startswith("\x1b") and len(seq) >= 3

    def _insert(self, ch: str) -> list[tuple[str, str]]:
        if self.cursor >= len(self.buffer):
            self.buffer += ch
            self.cursor += 1
            return [("emit", ch)]
        self.buffer = self.buffer[: self.cursor] + ch + self.buffer[self.cursor :]
        self.cursor += 1
        return [("redraw_line", self.buffer)]

    def _backspace(self) -> list[tuple[str, str]]:
        if self.cursor <= 0:
            return []
        self.buffer = self.buffer[: self.cursor - 1] + self.buffer[self.cursor :]
        self.cursor -= 1
        return [("redraw_line", self.buffer)]

    def _move_left(self) -> list[tuple[str, str]]:
        if self.cursor > 0:
            self.cursor -= 1
            return [("cursor_left", "")]
        return []

    def _move_right(self) -> list[tuple[str, str]]:
        if self.cursor < len(self.buffer):
            self.cursor += 1
            return [("cursor_right", "")]
        return []

    def _home(self) -> list[tuple[str, str]]:
        self.cursor = 0
        return [("redraw_line", self.buffer)]

    def _end(self) -> list[tuple[str, str]]:
        self.cursor = len(self.buffer)
        return [("redraw_line", self.buffer)]

    def _clear_line(self) -> list[tuple[str, str]]:
        self.buffer = ""
        self.cursor = 0
        return [("redraw_line", "")]

    def _history_up(self) -> list[tuple[str, str]]:
        if not self.history:
            return []
        if self.history_idx < 0:
            self.history_idx = len(self.history) - 1
        elif self.history_idx > 0:
            self.history_idx -= 1
        self.buffer = self.history[self.history_idx]
        self.cursor = len(self.buffer)
        return [("redraw_line", self.buffer)]

    def _history_down(self) -> list[tuple[str, str]]:
        if not self.history or self.history_idx < 0:
            return []
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            self.buffer = self.history[self.history_idx]
        else:
            self.history_idx = -1
            self.buffer = ""
        self.cursor = len(self.buffer)
        return [("redraw_line", self.buffer)]
