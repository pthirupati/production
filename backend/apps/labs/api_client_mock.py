"""In-process API client mock router — never opens a real socket.

Supports graded / interactive REST labs behind network_mode=none sandboxes.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import urlparse


# Seeded collection the IDE / labs can call without inventing hosts.
_DEFAULT_ROUTES: list[dict[str, Any]] = [
    {
        "method": "GET",
        "path": "/health",
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": {"status": "ok", "service": "fixitlab-mock"},
    },
    {
        "method": "GET",
        "path": "/api/v1/pods",
        "status": 200,
        "headers": {"content-type": "application/json"},
        "body": {
            "apiVersion": "v1",
            "kind": "PodList",
            "items": [
                {"metadata": {"name": "web-0", "namespace": "default"}, "status": {"phase": "Running"}},
                {"metadata": {"name": "db-0", "namespace": "default"}, "status": {"phase": "Running"}},
            ],
        },
    },
    {
        "method": "POST",
        "path": "/api/v1/echo",
        "status": 201,
        "headers": {"content-type": "application/json"},
        "body": None,  # filled with request body
        "echo": True,
    },
]


_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def interpolate(text: str, variables: dict | None = None) -> str:
    vars_ = {str(k): str(v) for k, v in (variables or {}).items()}

    def repl(m: re.Match) -> str:
        return vars_.get(m.group(1), m.group(0))

    return _VAR_RE.sub(repl, text or "")


def _match_route(method: str, path: str, routes: list[dict]) -> dict | None:
    method = (method or "GET").upper()
    for route in routes:
        if (route.get("method") or "GET").upper() != method:
            continue
        if route.get("path") == path:
            return route
    return None


def dispatch_mock_request(
    *,
    method: str = "GET",
    url: str = "",
    headers: dict | None = None,
    body: Any = None,
    variables: dict | None = None,
    routes: list[dict] | None = None,
) -> dict:
    """Return a Postman-like response dict. Never performs network I/O."""
    t0 = time.perf_counter()
    raw_url = interpolate(url or "", variables)
    parsed = urlparse(raw_url if "://" in raw_url else f"mock://local{raw_url if raw_url.startswith('/') else '/' + raw_url}")
    path = parsed.path or "/"
    method_u = interpolate(method or "GET", variables).upper()
    route = _match_route(method_u, path, routes or _DEFAULT_ROUTES)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

    if not route:
        payload = {"error": "mock route not found", "method": method_u, "path": path}
        raw = json.dumps(payload)
        return {
            "ok": False,
            "status": 404,
            "reason": "Not Found",
            "headers": {"content-type": "application/json"},
            "body": payload,
            "body_text": raw,
            "bytes": len(raw.encode()),
            "elapsed_ms": elapsed_ms,
            "request": {"method": method_u, "url": raw_url, "path": path, "headers": headers or {}},
            "mock": True,
        }

    resp_body = route.get("body")
    if route.get("echo"):
        resp_body = body if body is not None else {"echo": True}
    if isinstance(resp_body, (dict, list)):
        body_text = json.dumps(resp_body)
    else:
        body_text = "" if resp_body is None else str(resp_body)
        try:
            resp_body = json.loads(body_text)
        except Exception:
            pass

    status = int(route.get("status") or 200)
    return {
        "ok": 200 <= status < 400,
        "status": status,
        "reason": "OK" if status < 400 else "Error",
        "headers": dict(route.get("headers") or {"content-type": "application/json"}),
        "body": resp_body,
        "body_text": body_text,
        "bytes": len(body_text.encode()),
        "elapsed_ms": elapsed_ms,
        "request": {
            "method": method_u,
            "url": raw_url,
            "path": path,
            "headers": headers or {},
        },
        "mock": True,
    }


def _json_path_get(data, path: str):
    """Minimal dotted/bracket-free path: a.b.0.c"""
    cur = data
    for part in (path or "").split("."):
        if part == "":
            continue
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def evaluate_assertions(response: dict, assertions: list[dict] | None) -> dict:
    """Grade declarative api_client assertions against a mock response.

    Supported ops: status equals, header matches, json path equals, timing max_ms.
    """
    results = []
    all_ok = True
    for i, raw in enumerate(assertions or []):
        if not isinstance(raw, dict):
            continue
        op_raw = str(raw.get("op") or raw.get("type") or "").strip().lower()
        op = re.sub(r"[\s_\-]+", "", op_raw)  # "timing max_ms" / "status equals" → keys
        name = raw.get("name") or f"assert_{i}"
        hidden = bool(raw.get("hidden"))
        passed = False
        message = ""
        try:
            if op in ("statusequals", "status"):
                expected = int(raw.get("value") if "value" in raw else raw.get("expected"))
                actual = int(response.get("status") or 0)
                passed = actual == expected
                message = "" if passed else f"status {actual} != {expected}"
            elif op in ("headermatches", "header"):
                key = str(raw.get("header") or raw.get("key") or "").lower()
                expected = str(raw.get("value") if "value" in raw else raw.get("expected") or "")
                headers = {str(k).lower(): str(v) for k, v in (response.get("headers") or {}).items()}
                actual = headers.get(key, "")
                passed = expected.lower() in actual.lower() if expected else key in headers
                message = "" if passed else f"header {key}={actual!r} missing {expected!r}"
            elif op in ("jsonpathequals", "jsonpath", "jsonpath"):
                path = str(raw.get("path") or raw.get("json_path") or "")
                expected = raw.get("value") if "value" in raw else raw.get("expected")
                actual = _json_path_get(response.get("body"), path)
                passed = actual == expected
                message = "" if passed else f"{path}={actual!r} != {expected!r}"
            elif op in ("timingmaxms", "timing", "maxms"):
                max_ms = float(raw.get("value") if "value" in raw else raw.get("max_ms") or raw.get("expected") or 0)
                elapsed = float(response.get("elapsed_ms") or 0)
                passed = elapsed <= max_ms
                message = "" if passed else f"{elapsed}ms > {max_ms}ms"
            else:
                message = f"unknown assertion op {op_raw!r}"
                passed = False
        except Exception as exc:  # noqa: BLE001
            passed = False
            message = str(exc)
        if not passed:
            all_ok = False
        results.append({"name": name, "op": op_raw, "passed": passed, "message": message, "hidden": hidden})
    return {"ok": all_ok and bool(results), "passed": all_ok and bool(assertions), "results": results}


def public_api_client_spec(api_client: dict | None) -> dict | None:
    """Strip hidden assertions from coding_spec.api_client for the browser."""
    if not isinstance(api_client, dict):
        return None
    out = {
        "environments": api_client.get("environments") or {"default": api_client.get("variables") or {}},
        "variables": api_client.get("variables") or {},
        "collection": api_client.get("collection") or default_collection(),
        "routes": api_client.get("routes") or None,
    }
    visible = []
    hidden_n = 0
    for a in api_client.get("assertions") or []:
        if not isinstance(a, dict):
            continue
        if a.get("hidden"):
            hidden_n += 1
            continue
        visible.append({k: v for k, v in a.items() if k != "hidden"})
    out["assertions"] = visible
    out["hidden_assertion_count"] = hidden_n
    return out


def default_collection() -> list[dict]:
    """Seeded routes for IDE collection dropdown / coding_spec defaults."""
    return [
        {"method": r.get("method", "GET"), "path": r.get("path"), "label": r.get("path")}
        for r in _DEFAULT_ROUTES
    ]


def build_mock_fetch_prelude(routes: list[dict] | None = None) -> str:
    """JS source that installs globalThis.fetch = mockFetch from the same routes.

    Injected ahead of learner code in the Node grading harness so assertions
    share one definition with the interactive send mock — zero sockets.
    """
    route_payload = json.dumps(routes if routes is not None else _DEFAULT_ROUTES)
    return (
        "globalThis.__FIXITLAB_MOCK_ROUTES__ = " + route_payload + ";\n"
        "globalThis.mockFetch = async function mockFetch(input, init) {\n"
        "  const url = typeof input === 'string' ? input : (input && input.url) || '';\n"
        "  const method = String((init && init.method) || 'GET').toUpperCase();\n"
        "  let path = url;\n"
        "  try { path = new URL(url, 'http://mock.local').pathname; } catch (_) {}\n"
        "  const routes = globalThis.__FIXITLAB_MOCK_ROUTES__ || [];\n"
        "  const route = routes.find(r => String(r.method||'GET').toUpperCase() === method && r.path === path);\n"
        "  if (!route) {\n"
        "    return { ok: false, status: 404, statusText: 'Not Found',\n"
        "      headers: { get: (k) => null },\n"
        "      async json() { return { error: 'mock route not found', method, path }; },\n"
        "      async text() { return JSON.stringify({ error: 'mock route not found' }); },\n"
        "      mock: true };\n"
        "  }\n"
        "  let body = route.body;\n"
        "  if (route.echo) {\n"
        "    try { body = init && init.body ? JSON.parse(init.body) : { echo: true }; } catch (_) { body = init && init.body; }\n"
        "  }\n"
        "  const text = typeof body === 'string' ? body : JSON.stringify(body ?? null);\n"
        "  const headersMap = Object.assign({'content-type':'application/json'}, route.headers || {});\n"
        "  return {\n"
        "    ok: (route.status||200) >= 200 && (route.status||200) < 400,\n"
        "    status: route.status || 200,\n"
        "    statusText: (route.status||200) < 400 ? 'OK' : 'Error',\n"
        "    headers: { get: (k) => headersMap[String(k).toLowerCase()] || headersMap[k] || null },\n"
        "    async json() { try { return JSON.parse(text); } catch (_) { return body; } },\n"
        "    async text() { return text; },\n"
        "    mock: true,\n"
        "  };\n"
        "};\n"
        "globalThis.fetch = globalThis.mockFetch;\n"
    )
