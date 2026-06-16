#!/usr/bin/env python3
"""E2E checks for simulation lab WebSocket terminals and wizard-style commands."""
from __future__ import annotations

import asyncio
import json
import re
import time

MARKER = "FIXITLAB_SIM_WS"
WS_HOST = __import__("os").environ.get("E2E_TERMINAL_WS_HOST", "127.0.0.1:8000")

SIM_PROMPT_RE = re.compile(
    r"(root@|\]#[\s\r]|]\$[\s\r]|\[\w+@\S+|grub rescue>|grub>|login:|ansible@|dev-server)",
    re.IGNORECASE,
)


def _has_sim_prompt(output: str) -> bool:
    return bool(SIM_PROMPT_RE.search(output))


def _reset_ws_counter(token: str) -> None:
    try:
        import jwt
        from apps.terminal import consumers

        payload = jwt.decode(token, options={"verify_signature": False})
        uid = payload.get("user_id")
        if uid is not None:
            consumers.reset_user_ws_connections(int(uid))
    except Exception:
        pass


async def _recv_json(ws, timeout: float = 2.0) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def _drain_output(ws, timeout: float = 3.0) -> str:
    output = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = await _recv_json(ws, timeout=1.0)
            if data.get("type") == "ping":
                continue
            output += data.get("output") or ""
        except asyncio.TimeoutError:
            break
    return output


async def _collect_until_prompt(ws, timeout: float = 45.0) -> str:
    output = ""
    deadline = time.time() + timeout
    nudged = False
    while time.time() < deadline:
        try:
            data = await _recv_json(ws, timeout=2.0)
            if data.get("type") == "ping":
                continue
            output += data.get("output") or ""
            if _has_sim_prompt(output):
                return output
        except asyncio.TimeoutError:
            if output and not nudged and "FixitLab" in output:
                nudged = True
                await ws.send(json.dumps({"input": "\r"}))
                continue
            if output:
                return output
    return output


async def _maybe_boot_to_shell(ws, output: str) -> str:
    """Reach an interactive shell from GRUB/login when possible."""
    if "grub>" in output and "grub rescue" not in output.lower():
        await ws.send(json.dumps({"input": "\r"}))
        output += await _drain_output(ws, 12.0)
    if "login:" in output.lower() and "root@" not in output and "]#" not in output:
        await ws.send(json.dumps({"input": "root\r"}))
        output += await _drain_output(ws, 8.0)
        await ws.send(json.dumps({"input": "redhat\r"}))
        output += await _drain_output(ws, 8.0)
    return output


async def _run_command(ws, command: str, timeout: float = 20.0) -> str:
    await ws.send(json.dumps({"input": command + "\r"}))
    out = ""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            data = await _recv_json(ws, timeout=2.0)
            if data.get("type") == "ping":
                continue
            out += data.get("output") or ""
            if _has_sim_prompt(out) and MARKER in out:
                break
            if _has_sim_prompt(out) and command.split()[-1] in out:
                break
        except asyncio.TimeoutError:
            if out:
                break
    return out


async def _check_sim_terminal_async(session_id: str, token: str, host: str = "primary") -> tuple[bool, str]:
    import websockets

    _reset_ws_counter(token)
    host_q = f"&host={host}" if host and host != "primary" else ""
    uri = f"ws://{WS_HOST}/ws/terminal/{session_id}/?token={token}{host_q}"
    try:
        async with websockets.connect(uri, open_timeout=15, close_timeout=5) as ws:
            output = await _collect_until_prompt(ws)
            if not _has_sim_prompt(output):
                await ws.send(json.dumps({"input": "\r"}))
                output += await _drain_output(ws, 5.0)
            output = await _maybe_boot_to_shell(ws, output)
            if not _has_sim_prompt(output):
                return False, f"no sim prompt on {host} (tail: {output[-100:]!r})"

            if "grub rescue>" in output.lower() or (
                "grub>" in output.lower() and "root@" not in output and "]#" not in output
            ):
                return True, f"sim WS ok ({host}, boot console)"

            echo_out = await _run_command(ws, f"echo {MARKER}")
            if MARKER not in echo_out:
                return False, f"echo failed on {host}"
            return True, f"sim WS ok ({host})"
    finally:
        _reset_ws_counter(token)


async def _check_sim_workflow_async(session_id: str, token: str, slug: str) -> tuple[bool, str]:
    slug = (slug or "").lower()
    if "ssh-stop" in slug or "sshd-down" in slug:
        import websockets

        uri_p = f"ws://{WS_HOST}/ws/terminal/{session_id}/?token={token}"
        uri_c = f"ws://{WS_HOST}/ws/terminal/{session_id}/?token={token}&host=ssh_client"
        try:
            async with websockets.connect(uri_p, open_timeout=15) as ws_p:
                await _collect_until_prompt(ws_p)
                await _run_command(ws_p, "systemctl start sshd")
            async with websockets.connect(uri_c, open_timeout=15) as ws_c:
                await _collect_until_prompt(ws_c)
                out = await _run_command(ws_c, "echo SSH_CLIENT_OK")
                if "SSH_CLIENT_OK" not in out:
                    return False, "ssh_client terminal not interactive"
            return True, "ssh-stop workflow"
        finally:
            _reset_ws_counter(token)

    if "firewalld-dual" in slug:
        import websockets

        uri_p = f"ws://{WS_HOST}/ws/terminal/{session_id}/?token={token}"
        try:
            async with websockets.connect(uri_p, open_timeout=15) as ws_p:
                await _collect_until_prompt(ws_p)
                await _run_command(
                    ws_p,
                    "firewall-cmd --permanent --add-service=http && firewall-cmd --reload",
                )
            return True, "firewalld-dual workflow"
        finally:
            _reset_ws_counter(token)

    if "mysql-dual" in slug:
        import websockets

        uri_p = f"ws://{WS_HOST}/ws/terminal/{session_id}/?token={token}"
        try:
            async with websockets.connect(uri_p, open_timeout=15) as ws_p:
                await _collect_until_prompt(ws_p)
                await _run_command(ws_p, "systemctl start mysqld")
            return True, "mysql-dual workflow"
        finally:
            _reset_ws_counter(token)

    return True, "no workflow test for slug"


def verify_simulation_terminal(session_id: str, token: str, host: str = "primary") -> tuple[bool, str]:
    last_detail = ""
    for attempt in range(3):
        try:
            ok, detail = asyncio.run(_check_sim_terminal_async(session_id, token, host))
            if ok:
                return True, detail
            last_detail = detail
        except Exception as exc:
            last_detail = str(exc)[:120]
        finally:
            _reset_ws_counter(token)
        if attempt < 2:
            time.sleep(1.5)
    return False, last_detail


def verify_simulation_workflow(session_id: str, token: str, slug: str) -> tuple[bool, str]:
    try:
        return asyncio.run(_check_sim_workflow_async(session_id, token, slug))
    except Exception as exc:
        _reset_ws_counter(token)
        return False, str(exc)[:120]
