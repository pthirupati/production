"""In-editor sessions for nano/vi simulation."""

from __future__ import annotations


class EditorSession:
    """Simple line editor mimicking nano."""

    def __init__(self, path: str, content: str, editor_type: str = "nano"):
        self.path = path
        self.editor_type = editor_type
        self.lines = content.splitlines() if content else [""]
        self.row = 0
        self.col = 0
        self.modified = False
        # True once the buffer has diverged from disk (any edit OR an explicit
        # Ctrl+O write). Drives save-on-close so Ctrl+O then Ctrl+X never
        # discards edits. Stays True after Ctrl+O clears `modified`.
        self.dirty = False
        self.status = ""

    def render(self, width: int = 80) -> str:
        header = f"\x1b[7m GNU nano 5.6.1 — {self.path} {'*' if self.modified else ''}\x1b[0m\r\n"
        body_lines = []
        for i, line in enumerate(self.lines[:20]):
            body_lines.append(line[: width - 1])
        body = "\r\n".join(body_lines)
        footer = (
            "\r\n\x1b[7m^G Help  ^O Write Out  ^X Exit  ^K Cut  ^U Paste"
            f"{' (modified)' if self.modified else ''}\x1b[0m"
        )
        if self.editor_type == "vi":
            footer = "\r\n-- INSERT --  :wq to save and quit  :q! to abort"
        return header + body + footer

    def process(self, data: str) -> tuple[str, bool]:
        """Process keystrokes. Returns (output, closed)."""
        closed = False
        out_parts: list[str] = []

        for ch in data:
            if ch == "\x03":  # Ctrl+C in nano = cancel
                closed = True
                out_parts.append("^C\r\n")
                break
            if ch in ("\r", "\n"):
                self.lines.insert(self.row + 1, "")
                self.row += 1
                self.col = 0
                self.modified = True
                self.dirty = True
            elif ch == "\x7f" or ch == "\b":
                if self.col > 0:
                    line = self.lines[self.row]
                    self.lines[self.row] = line[: self.col - 1] + line[self.col :]
                    self.col -= 1
                    self.modified = True
                    self.dirty = True
                elif self.row > 0:
                    prev = self.lines[self.row - 1]
                    cur = self.lines.pop(self.row)
                    self.row -= 1
                    self.col = len(prev)
                    self.lines[self.row] = prev + cur
                    self.modified = True
                    self.dirty = True
            elif ch == "\x18":  # Ctrl+X exit
                closed = True
            elif ch == "\x0f":  # Ctrl+O write out: persists but keeps editing
                self.modified = False
                self.dirty = True  # stays True so close still flushes to VFS
                self.status = "Wrote " + str(len(self.content()))
            elif ch == "\x1b":
                continue  # ignore lone escape in nano simple mode
            else:
                line = self.lines[self.row]
                self.lines[self.row] = line[: self.col] + ch + line[self.col :]
                self.col += 1
                self.modified = True
                self.dirty = True

        out_parts.append(self.render())
        return "".join(out_parts), closed

    def process_vi_command(self, cmd: str) -> tuple[str, bool]:
        cmd = cmd.strip()
        if cmd in (":wq", ":x", "ZZ"):
            return "", True
        if cmd in (":q!", ":q"):
            return "Changes discarded\r\n", True
        if cmd.startswith(":s/"):
            return "vi: substitute applied\r\n", False
        return f"vi: unknown command {cmd}\r\n", False

    def content(self) -> str:
        return "\n".join(self.lines) + ("\n" if self.lines else "")
