#!/usr/bin/env python3
"""Verify lab WebSocket terminal stays connected (catches docker-py exec GC bugs)."""
from __future__ import annotations

import asyncio
import json
import os
import time

HOLD_SECONDS = float(os.environ.get("E2E_TERMINAL_HOLD", "3"))
MARKER = "FIXITLAB_E2E_TERMINAL"


async def _check_terminal_async(session_id: str, token: str) -> tuple[bool, str]:
    from channels.testing import WebsocketCommunicator
    from config.asgi import application

    path = f"/ws/terminal/{session_id}/?token={token}"
    comm = WebsocketCommunicator(application, path)
    try:
        connected, code = await comm.connect()
        if not connected:
            return False, f"websocket refused code={code}"

        output = ""
        deadline = time.time() + 20
        got_prompt = False
        while time.time() < deadline:
            try:
                raw = await asyncio.wait_for(comm.receive_from(), timeout=2.0)
                data = json.loads(raw)
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

        await comm.send_to(text_data=json.dumps({"input": f"echo {MARKER}\r"}))

        saw_marker = False
        echo_deadline = time.time() + 10
        while time.time() < echo_deadline:
            try:
                raw = await asyncio.wait_for(comm.receive_from(), timeout=2.0)
                data = json.loads(raw)
                if MARKER in (data.get("output") or ""):
                    saw_marker = True
                    break
            except asyncio.TimeoutError:
                continue
        if not saw_marker:
            return False, f"echo {MARKER} not returned"

        await asyncio.sleep(HOLD_SECONDS)
        await comm.send_to(text_data=json.dumps({"input": "echo STILL_ALIVE\r"}))

        alive_deadline = time.time() + 8
        while time.time() < alive_deadline:
            try:
                raw = await asyncio.wait_for(comm.receive_from(), timeout=2.0)
                data = json.loads(raw)
                if "STILL_ALIVE" in (data.get("output") or ""):
                    return True, f"stable {HOLD_SECONDS}s"
            except asyncio.TimeoutError:
                continue
        return False, f"stream dropped after {HOLD_SECONDS}s hold"
    finally:
        await comm.disconnect()


def verify_lab_terminal(session_id: str, token: str) -> tuple[bool, str]:
    return asyncio.run(_check_terminal_async(session_id, token))
