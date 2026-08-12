"""In-memory simulated terminal streams for boot/GPU/Ansible/bare-metal labs."""

from __future__ import annotations

import os
import queue
import logging
import threading
import time

import uuid
from dataclasses import dataclass, field
from typing import Callable
from .terminal_input import TerminalLineEditor

logger = logging.getLogger(__name__)


def _to_crlf(text: str) -> str:
    """Normalize line endings to CRLF for a raw (no line-discipline) terminal.

    Command handlers and editor renders build their output with bare "\\n".
    xterm.js, talking to a raw socket, needs "\\r\\n" or every new line keeps the
    previous line's column (the staircase effect). Collapse any pre-existing
    "\\r\\n" first so we never emit "\\r\\r\\n".
    """
    if not text:
        return text
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


@dataclass
class StreamedCommandResult:
    """Line-by-line paced output for ping/traceroute-style commands.

    ``run()`` / unit tests still stringify this to a single blob; the WebSocket
    stream holder emits each line with ``delay_s`` between them.
    """

    lines: list[str] = field(default_factory=list)
    delay_s: float = 0.35

    def __str__(self) -> str:
        return "\n".join(self.lines)

    def __contains__(self, item: object) -> bool:
        return item in str(self)


class SimulationStreamHolder:
    """Mimics ExecStreamHolder for WebSocket terminal consumer."""

    def __init__(
        self,
        handler: Callable[[str], str],
        *,
        prompt: str = "root@lab:~# ",
        dynamic_prompt: Callable[[], str] | None = None,
        get_editor_state: Callable[[], object | None] | None = None,
        save_editor: Callable[[str, str], None] | None = None,
        clear_editor: Callable[[], None] | None = None,
        banner: str = "Lab Server — RHEL 9",
    ):
        self._handler = handler
        self._prompt = prompt
        self._dynamic_prompt = dynamic_prompt
        self._get_editor = get_editor_state
        self._save_editor = save_editor
        self._clear_editor = clear_editor
        self._editor = TerminalLineEditor()
        self._vi_cmd_buf = ""
        self._out_q: queue.Queue[bytes] = queue.Queue()
        self._closed = False
        self._timeout = 60.0
        self._lock = threading.Lock()
        self.exec_id = f"sim-exec-{uuid.uuid4().hex[:12]}"
        # Learner-facing banner — never expose the word "Simulation".
        self._emit(f"\r\n\x1b[1;36m[{banner}]\x1b[0m\r\n")
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
        # Redraw the current input line robustly: return to column 0, repaint the
        # prompt + buffer, then erase anything left over from a longer previous
        # line with "erase to end of line" (\x1b[K). This is independent of the
        # terminal width and the prompt's printable length, so backspace and
        # mid-line edits render correctly (the old version hardcoded 80 cols and
        # an absolute column jump, which misplaced the cursor after a backspace).
        self._emit("\r")
        self._emit(self.prompt + buffer)
        self._emit("\x1b[K")
        # Place the cursor where the line editor's cursor actually is. When it's
        # not at the end of the buffer (mid-line editing), step it back left by
        # the number of trailing characters using a relative CSI move.
        trailing = len(buffer) - getattr(self._editor, "cursor", len(buffer))
        if trailing > 0:
            self._emit(f"\x1b[{trailing}D")

    def _handle_editor_input(self, chunk: str) -> None:
        session = self._get_editor() if self._get_editor else None
        if not session:
            return
        # Enter vi command mode on a ":" — handle both the char-by-char case and
        # batched input (e.g. the whole ":wq\r" arriving in one chunk).
        if session.editor_type == "vi" and not self._vi_cmd_buf.startswith(":") and chunk.startswith(":"):
            self._vi_cmd_buf = ":"
            self._emit(":")
            chunk = chunk[1:]
            if not chunk:
                return
        if self._vi_cmd_buf.startswith(":"):
            self._vi_cmd_buf += chunk
            if "\r" in self._vi_cmd_buf or "\n" in self._vi_cmd_buf:
                cmd = self._vi_cmd_buf.strip()
                self._vi_cmd_buf = ""
                out, closed = session.process_vi_command(cmd)
                if out:
                    self._emit(out)
                if closed:
                    if cmd in (":wq", ":x", "ZZ") and self._save_editor:
                        self._save_editor(session.path, session.content())
                    elif self._clear_editor:
                        self._clear_editor()
                    self._emit("\x1b[2J\x1b[H")
                    self._emit_prompt()
                else:
                    self._emit(session.render())
            return
        out, closed = session.process(chunk)
        self._emit("\x1b[2J\x1b[H")
        self._emit(out)
        if closed:
            # Persist if the buffer ever diverged from disk. `dirty` stays True
            # after Ctrl+O (which clears `modified`), so Ctrl+O then Ctrl+X no
            # longer discards the write.
            if getattr(session, "dirty", session.modified) and self._save_editor:
                self._save_editor(session.path, session.content())
            elif self._clear_editor:
                self._clear_editor()
            self._emit_prompt()

    def send(self, data: bytes) -> None:
        if self._closed:
            return
        try:
            chunk = data.decode("utf-8", errors="replace")
        except Exception:
            return

        if self._get_editor and self._get_editor():
            self._handle_editor_input(chunk)
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
                        out = f"\x1b[1;31mLab shell error: {exc}\x1b[0m"
                    if out == "__REBOOT__":
                        self._editor.reset()
                        self._emit_prompt()
                        continue
                    if out == "__EDITOR__":
                        session = self._get_editor() if self._get_editor else None
                        if session:
                            self._emit("\x1b[2J\x1b[H")
                            self._emit(session.render())
                        continue
                    if isinstance(out, StreamedCommandResult):
                        for i, line in enumerate(out.lines):
                            body = _to_crlf(line)
                            self._emit(body if body.endswith("\r\n") else body + "\r\n")
                            if i < len(out.lines) - 1 and out.delay_s > 0:
                                time.sleep(out.delay_s)
                    elif out:
                        # Command handlers build output with bare "\n" line
                        # endings. A raw terminal (no line discipline) needs
                        # CRLF, otherwise each line starts where the previous one
                        # ended — the "staircase"/out-of-order output users saw.
                        # Normalize to CRLF and guarantee a trailing newline.
                        body = _to_crlf(str(out))
                        self._emit(body if body.endswith("\r\n") else body + "\r\n")
                    text_for_prompt = str(out) if out else ""
                    if text_for_prompt and "login:" in text_for_prompt.lower():
                        self.set_prompt("")
                    elif text_for_prompt and "grub rescue" in text_for_prompt.lower():
                        self.set_prompt("grub rescue> ")
                    elif text_for_prompt and "grub>" in text_for_prompt.lower() and "GNU GRUB" in text_for_prompt:
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

    def resize_pty(self, width: int = 120, height: int = 40) -> None:
        """No-op for simulation — keeps consumer resize path from failing."""
        pass


_SIM_SESSIONS: dict[str, dict] = {}
_SIM_LOCK = threading.Lock()

# Idle eviction bound for _SIM_SESSIONS.
#
# This dict holds live UnifiedSimulationEngine objects (full VFS, users, services,
# processes, LVM, git state) and live stream handles. It had NO ttl, NO maxsize and
# NO eviction, and there are FIVE independent copies of it: one per uvicorn worker
# (4) plus celery_provisioning.
#
# The leak is structural, not a missing cleanup call. Provisioning runs on the
# Celery worker and populates THAT process's dict. The terminal then connects to an
# arbitrary uvicorn worker whose dict is empty, so ensure_sim_session() rebuilds a
# second engine there. Teardown calls drop_sim_session() in ONE process. Celery
# children recycle at CELERY_WORKER_MAX_TASKS_PER_CHILD and self-heal; uvicorn
# workers never recycle, so their copies accumulate monotonically until the 5 GB
# cgroup OOM-kills all four and every in-flight lab dies.
#
# Eviction is keyed on IDLE TIME, not on count pressure, and deliberately so:
# evicting an ACTIVE session would force a rebuild from LabSession
# .simulation_snapshot, which (since snapshots are debounced to 15s) could lose up
# to 15 seconds of a learner's work. An entry idle for longer than a lab can
# possibly live is certainly dead, and rebuilding it is free because
# ensure_sim_session() already restores from the snapshot.
#
# The real fix is still to move engine state out of process memory — the pattern
# the 22 apps/vmware_sim/*_engine.py modules already use with SESSION_TTL=7200.
# That is a larger change because this dict also holds live stream objects, which
# genuinely must stay process-local. This bounds the damage in the meantime.
_SIM_IDLE_TTL_SECONDS = 2 * 60 * 60  # 2x LAB_MAX_DURATION_MINUTES default (60m)

# Hard ceiling on entries per process, on top of the idle TTL.
#
# The TTL alone bounds nothing inside its own window: sessions can accumulate for
# two hours before anything is reclaimed, and with an engine copy living in each of
# the ~5 processes (4 uvicorn + celery) a busy hour can exhaust memory long before
# the first eviction fires. The cap makes worst-case footprint a function of this
# number rather than of traffic.
#
# Evicting a LIVE session is safe here, which is what makes an LRU cap usable at
# all: `ensure_sim_session()` rehydrates from `LabSession.simulation_snapshot`, and
# the trailing-edge flush keeps that snapshot current to ~1.5s. So the cost of
# eviction is one rebuild on next access, not lost learner work.
#
# Default 32 = ~2.5x MAX_CONCURRENT_LABS (12), leaving room for a session to be
# resident in more than one process at once without the cap biting in normal use.
_SIM_MAX_SESSIONS = int(os.environ.get("SIM_MAX_SESSIONS_PER_PROCESS", "32") or 32)

# Soft-evict streamless hot copies (audit Z5-1 best decision, session 92).
#
# Design: Redis/cache is the *authority* for engine snapshots (put / hydrate /
# write-through / mutated_at authority). Process-local `_SIM_SESSIONS` is a hot
# cache PLUS WebSocket stream handles — streams *must* stay process-local.
#
# When an entry has no live streams and has been idle beyond this soft TTL,
# drop the local engine object after flushing to Redis. Next access rehydrates
# from cache (same path as a cross-worker miss). This collapses multi-worker
# hot copies for idle labs without inventing a fake “streams in Redis” design.
#
# Set SIM_ENGINE_SOFT_IDLE_SECONDS=0 to disable soft-evict (hard 2h TTL remains).
_SIM_SOFT_IDLE_SECONDS = int(os.environ.get("SIM_ENGINE_SOFT_IDLE_SECONDS", "300") or 0)


def _touch(entry: dict) -> dict:
    entry["last_access"] = time.time()
    return entry


def _soft_evict_streamless_locked() -> int:
    """Drop idle, streamless hot engines; Redis remains authority. Holds _SIM_LOCK."""
    if _SIM_SOFT_IDLE_SECONDS <= 0:
        return 0
    cutoff = time.time() - _SIM_SOFT_IDLE_SECONDS
    victims = [
        sid for sid, e in _SIM_SESSIONS.items()
        if e.get("last_access", 0) < cutoff and not (e.get("streams") or {})
    ]
    for sid in victims:
        entry = _SIM_SESSIONS.pop(sid, None)
        if not entry:
            continue
        _cache_put_before_drop(sid, entry)
    if victims:
        logger.info(
            "Soft-evicted %d streamless sim engine(s) to Redis; %d remain local",
            len(victims), len(_SIM_SESSIONS),
        )
    return len(victims)


def _evict_idle_locked() -> int:
    """Drop soft-idle streamless engines, then hard-TTL entries. Holds _SIM_LOCK."""
    dropped = _soft_evict_streamless_locked()
    cutoff = time.time() - _SIM_IDLE_TTL_SECONDS
    stale = [
        sid for sid, e in _SIM_SESSIONS.items()
        if e.get("last_access", 0) < cutoff
    ]
    for sid in stale:
        entry = _SIM_SESSIONS.pop(sid, None)
        if not entry:
            continue
        _cache_put_before_drop(sid, entry)
        for stream in (entry.get("streams") or {}).values():
            try:
                stream.close()
            except Exception:
                pass
        dropped += 1
    if stale:
        logger.info(
            "Evicted %d idle simulation session(s) from this worker; %d remain",
            len(stale), len(_SIM_SESSIONS),
        )
    return dropped


def _cache_put_before_drop(sid: str, entry: dict) -> None:
    """Flush engine to shared cache before dropping the process-local copy (Z5-1)."""
    try:
        engine = (entry.get("state") or {}).get("engine")
        if engine is None:
            return
        from .sim_persistence import cache_put_engine_snapshot
        cache_put_engine_snapshot(str(sid), engine=engine)
    except Exception:
        logger.debug("cache put before drop failed for %s", sid, exc_info=True)


def _enforce_max_locked() -> int:
    """Drop least-recently-used entries until at most _SIM_MAX_SESSIONS remain.

    Caller must hold _SIM_LOCK. Streams are closed on the way out — dropping the
    dict entry alone would leak the reader thread and its socket, which is the
    failure this whole registry exists to bound.
    """
    if _SIM_MAX_SESSIONS <= 0 or len(_SIM_SESSIONS) <= _SIM_MAX_SESSIONS:
        return 0
    ordered = sorted(_SIM_SESSIONS.items(), key=lambda kv: kv[1].get("last_access", 0))
    overflow = len(_SIM_SESSIONS) - _SIM_MAX_SESSIONS
    dropped = 0
    for sid, _entry in ordered[:overflow]:
        entry = _SIM_SESSIONS.pop(sid, None)
        if not entry:
            continue
        _cache_put_before_drop(sid, entry)
        for stream in (entry.get("streams") or {}).values():
            try:
                stream.close()
            except Exception:
                pass
        dropped += 1
    if dropped:
        # WARNING, not INFO: hitting the cap means real sessions are being rebuilt
        # from snapshots. Harmless once, but a steady stream of these means the cap
        # is too low for actual concurrency, and that is worth seeing.
        logger.warning(
            "Simulation registry at capacity (%d): evicted %d least-recently-used "
            "session(s); they will rehydrate from their snapshot on next access.",
            _SIM_MAX_SESSIONS, dropped,
        )
    return dropped


def sim_session_count() -> int:
    """Live entries in THIS process's registry.

    Exported for monitoring: without it an OOM caused by this leak is
    indistinguishable from a random worker restart (audit Z5-17).
    """
    with _SIM_LOCK:
        return len(_SIM_SESSIONS)


def register_sim_session(session_id: str, resource_id: str, sim_type: str, state: dict) -> None:
    with _SIM_LOCK:
        _evict_idle_locked()
        _SIM_SESSIONS[str(session_id)] = _touch({
            "resource_id": resource_id,
            "sim_type": sim_type,
            "state": state,
            "streams": {},
            "engine_mutated_at": time.time(),
        })
        # After inserting, so the session just registered is the most recently used
        # and can never be the one evicted by its own registration.
        _enforce_max_locked()
    # Stamp the lab session id onto the OS state so the cross-technology VMware
    # bridge (keyed by session id in the shared cache) can be consulted from the
    # terminal engine — even though the two simulators run in different workers.
    engine = state.get("engine") if isinstance(state, dict) else None
    os_state = getattr(getattr(engine, "shell", None), "state", None)
    if os_state is not None:
        os_state.session_id = str(session_id)
    # Shared-cache mirror for cross-worker rehydrate (audit Z5-1 partial).
    if engine is not None:
        try:
            from .sim_persistence import cache_put_engine_snapshot

            cache_put_engine_snapshot(str(session_id), engine=engine)
        except Exception:
            pass


def get_sim_session(session_id: str) -> dict | None:
    """Return the process-local session entry, or hydrate from shared cache.

    Cross-worker miss path (audit Z5-1): when this uvicorn worker never saw the
    session, try the Redis/cache engine blob before forcing a full
    ``ensure_sim_session`` rebuild from Postgres. Live streams are still empty
    here — the websocket reattaches on the worker that owns them.

    Cache-authority path (``SIM_ENGINE_CACHE_AUTHORITY``, default on): if this
    worker already has a hot copy but Redis holds a *newer* ``mutated_at``
    snapshot (another worker wrote through), replace the local engine so the
    two workers do not diverge indefinitely. Streams stay process-local.
    """
    sid = str(session_id)
    with _SIM_LOCK:
        entry = _SIM_SESSIONS.get(sid)
        if entry is not None:
            entry = _touch(entry)
            # Fall through outside the lock for optional cache refresh.
        else:
            entry = None

    if entry is not None:
        if os.environ.get("SIM_ENGINE_CACHE_AUTHORITY", "1") != "0":
            try:
                from .sim_persistence import cache_get_snapshot, restore_engine

                snap = cache_get_snapshot(sid)
                local_ts = float(entry.get("engine_mutated_at") or 0)
                remote_ts = float((snap or {}).get("mutated_at") or 0)
                if snap is not None and remote_ts > local_ts + 0.001:
                    engine = restore_engine(snap)
                    with _SIM_LOCK:
                        cur = _SIM_SESSIONS.get(sid)
                        if cur is not None:
                            cur["state"] = {**(cur.get("state") or {}), "engine": engine}
                            cur["engine_mutated_at"] = remote_ts
                            return _touch(cur)
            except Exception:
                logger.debug("cache authority refresh failed for %s", sid, exc_info=True)
        return entry

    if os.environ.get("SIM_ENGINE_CACHE_HYDRATE", "1") == "0":
        return None

    try:
        from .sim_persistence import cache_get_engine, cache_get_snapshot

        engine = cache_get_engine(sid)
        snap = cache_get_snapshot(sid) if engine is not None else None
    except Exception:
        return None
    if engine is None:
        return None

    sim_type = getattr(engine, "simulation_type", None) or "generic"
    register_sim_session(
        sid,
        resource_id=f"cache-hydrate:{sid}",
        sim_type=str(sim_type),
        state={"engine": engine},
    )
    with _SIM_LOCK:
        entry = _SIM_SESSIONS.get(sid)
        if entry is not None and snap is not None:
            entry["engine_mutated_at"] = float(snap.get("mutated_at") or time.time())
        return _touch(entry) if entry is not None else None


def mark_sim_engine_mutated(session_id: str) -> None:
    """Bump local ``engine_mutated_at`` after a write-through (keeps authority honest)."""
    sid = str(session_id)
    now = time.time()
    with _SIM_LOCK:
        entry = _SIM_SESSIONS.get(sid)
        if entry is not None:
            entry["engine_mutated_at"] = now
            _touch(entry)


def get_sim_session_by_resource(resource_id: str) -> dict | None:
    with _SIM_LOCK:
        for entry in _SIM_SESSIONS.values():
            if entry.get("resource_id") == resource_id:
                return _touch(entry)
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
    try:
        from .sim_persistence import cache_drop_engine

        cache_drop_engine(str(session_id))
    except Exception:
        pass
