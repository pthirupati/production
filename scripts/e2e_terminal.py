#!/usr/bin/env python3
"""Verify lab WebSocket terminal via local daphne (real WS, not in-process ASGI test)."""
from __future__ import annotations

import asyncio
import json
import os
import time

HOLD_SECONDS = float(os.environ.get("E2E_TERMINAL_HOLD", "3"))
MARKER = "FIXITLAB_E2E_TERMINAL"
WS_HOST = os.environ.get("E2E_TERMINAL_WS_HOST", "127.0.0.1:8000")


def _reset_ws_counter(token: str) -> None:
    """Ensure per-user WS slot is released after E2E (safety net)."""
    try:
        import jwt
        from apps.terminal import consumers

        payload = jwt.decode(token, options={"verify_signature": False})
        uid = payload.get("user_id")
        if uid is not None:
            consumers.reset_user_ws_connections(int(uid))
    except Exception:
        pass


def _release_exec(session_id: str) -> None:
    try:
        from apps.labs.provisioner.exec_stream import release_holder

        release_holder(session_id)
    except Exception:
        pass


async def _recv_json(ws, timeout: float = 2.0) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def _check_terminal_async(session_id: str, token: str) -> tuple[bool, str]:
    import websockets

    _reset_ws_counter(token)
    uri = f"ws://{WS_HOST}/ws/terminal/{session_id}/?token={token}"
    try:
        async with websockets.connect(uri, open_timeout=15, close_timeout=5) as ws:
            output = ""
            deadline = time.time() + 20
            got_prompt = False
            while time.time() < deadline:
                try:
                    data = await _recv_json(ws, timeout=2.0)
                    if data.get("type") == "ping":
                        continue
                    chunk = data.get("output") or ""
                    output += chunk
                    if "root@" in output or "FixitLab Terminal Ready" in output:
                        got_prompt = True
                        if "root@" in output:
                            break
                except asyncio.TimeoutError:
                    if got_prompt:
                        break
                    continue

            if "root@" not in output:
                return False, f"no shell prompt (tail: {output[-120:]!r})"

            await ws.send(json.dumps({"input": f"echo {MARKER}\r"}))

            saw_marker = False
            echo_deadline = time.time() + 10
            while time.time() < echo_deadline:
                try:
                    data = await _recv_json(ws, timeout=2.0)
                    if MARKER in (data.get("output") or ""):
                        saw_marker = True
                        break
                except asyncio.TimeoutError:
                    continue
            if not saw_marker:
                return False, f"echo {MARKER} not returned"

            await asyncio.sleep(HOLD_SECONDS)
            await ws.send(json.dumps({"input": "echo STILL_ALIVE\r"}))

            alive_deadline = time.time() + 8
            while time.time() < alive_deadline:
                try:
                    data = await _recv_json(ws, timeout=2.0)
                    if "STILL_ALIVE" in (data.get("output") or ""):
                        return True, f"stable {HOLD_SECONDS}s"
                except asyncio.TimeoutError:
                    continue
            return False, f"stream dropped after {HOLD_SECONDS}s hold"
    finally:
        _release_exec(session_id)
        _reset_ws_counter(token)


def verify_lab_terminal(session_id: str, token: str) -> tuple[bool, str]:
    try:
        return asyncio.run(_check_terminal_async(session_id, token))
    except Exception as exc:
        _release_exec(session_id)
        _reset_ws_counter(token)
        return False, str(exc)[:120]
