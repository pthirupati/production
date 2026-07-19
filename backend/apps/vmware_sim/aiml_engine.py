"""
In-memory AGENT / WORKFLOW simulator for training labs.

Models an n8n-style automation / AI-agent NODE GRAPH so a learner can build and
fix small agentic workflows entirely free and local — there is NO network call
and NO paid LLM anywhere. The "LLM" node is a DETERMINISTIC, rule-based
classifier/extractor/summarizer: the same input text always yields the same
output (keyword + regex rules), so a lab is perfectly reproducible and gradeable.

A workflow is a graph of typed nodes connected by directed edges:

  - trigger       : the entry point. Emits a seed payload (e.g. an incoming
                    support ticket, or a webhook body) defined in its config.
  - llm           : the deterministic "LLM". Modes: classify | extract |
                    summarize. Produces structured output from the upstream
                    text using fixed keyword/regex rules (no model, no network).
  - tool          : a simulated integration. Kinds: http_get (returns canned
                    JSON for a known URL), db_query (returns canned rows for a
                    known query id), send_notification (records a message that
                    was "sent").
  - mcp_tool      : a simulated Model-Context-Protocol tool call. Servers expose
                    named tools that return canned, deterministic data (e.g. a
                    metrics MCP server answering "what is current CPU?").
  - transform     : reshapes the payload (set / pick / template / json_parse).
  - condition     : routes execution. Evaluates a field op value against the
                    incoming payload and steers downstream nodes onto the
                    "true" / "false" branch (edges carry an optional `branch`).
  - output        : a terminal sink that captures the final result of the run.

apply_action lets the learner mutate the graph (add_node / remove_node /
connect / disconnect / configure_node / set_trigger_input), run it
(run_workflow — executes nodes in topological order, producing a run_trace and a
final output), or reset it to the scenario preset.

validate_aiml_lab grades a lab purely against the scenario `goal`: it checks the
graph topology (required node types present and wired in the right order), the
node configs (e.g. the LLM is in the right mode, the right tool/MCP is called),
AND the deterministic run output (the final payload matches what the goal
expects). A fresh / broken preset fails; only the correct graph + configs + run
output flips it to pass.

Sessions live in the Django cache (Redis in production, LocMem in tests) for
multi-worker safety, mirroring the VMware / nmap / wireshark engines
(SESSION_TTL=7200, get_state / apply_action / drop_session / _ensure_session).
"""

from __future__ import annotations

import copy
import json
import re
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL matching the other simulator engines


# ---------------------------------------------------------------------------
# Cache-backed session lifecycle (mirrors nmap_engine / engine.py)
# ---------------------------------------------------------------------------

def _session_key(session_id: str) -> str:
    return f"aiml_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Node types + palette (what the UI may add)
# ---------------------------------------------------------------------------

NODE_TYPES = ("trigger", "llm", "tool", "mcp_tool", "transform", "condition", "output")

# Palette metadata surfaced to the frontend so it can render an "add node" menu
# with typed icons + a starter config for each type.
NODE_PALETTE = [
    {
        "type": "trigger",
        "label": "Trigger",
        "icon": "bolt",
        "description": "Workflow entry point. Emits the seed payload (incoming ticket / webhook body).",
        "default_config": {"kind": "manual", "input": {}},
    },
    {
        "type": "llm",
        "label": "LLM (rule-based)",
        "icon": "sparkles",
        "description": "Deterministic classify / extract / summarize. Same input -> same output, no network.",
        "default_config": {"mode": "classify", "input_field": "text"},
    },
    {
        "type": "tool",
        "label": "Tool",
        "icon": "wrench",
        "description": "Local tool integration: http_get, db_query, or send_notification.",
        "default_config": {"kind": "http_get", "url": ""},
    },
    {
        "type": "mcp_tool",
        "label": "MCP Tool",
        "icon": "plug",
        "description": "Model-Context-Protocol tool call. A canned MCP server tool returns deterministic data.",
        "default_config": {"server": "metrics", "tool": "get_cpu", "args": {}},
    },
    {
        "type": "transform",
        "label": "Transform",
        "icon": "shuffle",
        "description": "Reshape the payload: set / pick / template / json_parse.",
        "default_config": {"op": "set", "field": "", "value": ""},
    },
    {
        "type": "condition",
        "label": "Condition",
        "icon": "git-branch",
        "description": "Route execution on field op value; downstream edges carry a true/false branch.",
        "default_config": {"field": "category", "op": "equals", "value": ""},
    },
    {
        "type": "output",
        "label": "Output",
        "icon": "flag",
        "description": "Terminal sink. Captures the final result of the run.",
        "default_config": {},
    },
]


# ---------------------------------------------------------------------------
# Deterministic rule-based "LLM"
#
# These functions are pure: same input string -> same structured output, with
# NO randomness and NO I/O. That is what makes the lab reproducible + gradeable.
# ---------------------------------------------------------------------------

# Ordered keyword rules for ticket/intent classification. First matching
# category wins, so order encodes priority (billing/security before the
# generic "question"). Lowercased substring match against the input text.
_CLASSIFY_RULES = [
    ("billing", ["refund", "invoice", "charge", "charged", "payment", "billing",
                 "subscription", "credit card", "overcharged", "receipt"]),
    ("security", ["hacked", "breach", "phishing", "password reset", "compromis",
                  "unauthorized", "2fa", "security", "suspicious login"]),
    ("bug", ["error", "crash", "broken", "not working", "doesn't work",
             "doesnt work", "bug", "500", "exception", "stack trace", "fails"]),
    ("outage", ["down", "outage", "can't access", "cannot access", "unavailable",
                "503", "timeout", "everything is down"]),
    ("feature_request", ["feature request", "would be nice", "please add",
                         "can you add", "suggestion", "enhancement"]),
    ("question", ["how do i", "how to", "what is", "where is", "can i",
                  "question", "help me understand"]),
]

# Sentiment cue words (used by classify to add an urgency/sentiment field).
_NEGATIVE_CUES = ["angry", "furious", "terrible", "worst", "unacceptable",
                  "asap", "urgent", "immediately", "frustrated", "ridiculous"]
_POSITIVE_CUES = ["thanks", "thank you", "great", "love", "awesome", "appreciate"]


def llm_classify(text: str) -> dict:
    """Deterministic intent + sentiment classifier.

    Returns {category, confidence, sentiment, priority}. Category is the first
    rule whose keyword set matches; confidence is a deterministic function of how
    many keywords hit; sentiment/priority come from cue words. Fully reproducible.
    """
    low = (text or "").lower()
    category = "general"
    hits = 0
    for cat, keywords in _CLASSIFY_RULES:
        matched = sum(1 for kw in keywords if kw in low)
        if matched:
            category = cat
            hits = matched
            break
    # Deterministic confidence: base 0.55, +0.15 per matched keyword, capped.
    confidence = round(min(0.99, 0.55 + 0.15 * hits), 2) if hits else 0.4

    neg = sum(1 for c in _NEGATIVE_CUES if c in low)
    pos = sum(1 for c in _POSITIVE_CUES if c in low)
    if neg > pos:
        sentiment = "negative"
    elif pos > neg:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    # Priority: security/outage are always high; negative sentiment bumps others.
    if category in ("security", "outage"):
        priority = "high"
    elif sentiment == "negative":
        priority = "high"
    elif category in ("billing", "bug"):
        priority = "medium"
    else:
        priority = "low"

    return {
        "category": category,
        "confidence": confidence,
        "sentiment": sentiment,
        "priority": priority,
    }


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_ORDER_RE = re.compile(r"\b(?:order|#)\s*#?\s*([A-Z]{0,3}\d{4,})\b", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"[$₹€]\s?\d[\d,]*(?:\.\d{1,2})?")


def llm_extract(text: str) -> dict:
    """Deterministic structured extraction (entities) from free text.

    Pulls out email, order id, and money amounts via fixed regexes. Same input
    -> same entities. Used by the n8n-style flow scenario to normalise a webhook
    body into structured fields before a tool call.
    """
    low_text = text or ""
    emails = _EMAIL_RE.findall(low_text)
    order_match = _ORDER_RE.search(low_text)
    amounts = _AMOUNT_RE.findall(low_text)
    return {
        "email": emails[0] if emails else "",
        "order_id": (order_match.group(1) if order_match else ""),
        "amount": amounts[0].replace(" ", "") if amounts else "",
        "all_emails": emails,
    }


def llm_summarize(text: str) -> dict:
    """Deterministic extractive summary: first + last sentence, word count.

    No model — splits on sentence punctuation and stitches a one-line summary.
    Same input always produces the same summary string.
    """
    raw = (text or "").strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw) if s.strip()]
    if not sentences:
        summary = ""
    elif len(sentences) == 1:
        summary = sentences[0]
    else:
        summary = f"{sentences[0]} … {sentences[-1]}"
    words = len(raw.split())
    return {"summary": summary, "sentence_count": len(sentences), "word_count": words}


def _run_llm_node(config: dict, payload: dict) -> dict:
    """Execute an llm node against the incoming payload, return new fields."""
    mode = (config or {}).get("mode", "classify")
    field = (config or {}).get("input_field", "text")
    text = payload.get(field)
    if text is None:
        # Fall back to common text-bearing fields so a mildly-misconfigured
        # input_field still finds the message.
        text = payload.get("text") or payload.get("body") or payload.get("message") or ""
    text = str(text)
    if mode == "extract":
        return {"llm_mode": "extract", "entities": llm_extract(text)}
    if mode == "summarize":
        return {"llm_mode": "summarize", **llm_summarize(text)}
    # default: classify
    result = llm_classify(text)
    return {"llm_mode": "classify", **result}


# ---------------------------------------------------------------------------
# Simulated tools (canned, deterministic — NO network)
# ---------------------------------------------------------------------------

# Canned HTTP responses keyed by URL. A learner "calls" an API and gets back the
# same JSON every time.
_HTTP_CANNED = {
    "https://api.fixitlab.local/orders/1042": {
        "status": 200,
        "json": {"order_id": "1042", "status": "shipped", "total": "$129.00",
                 "customer_email": "amy@example.com", "carrier": "BlueDart"},
    },
    "https://api.fixitlab.local/status": {
        "status": 200,
        "json": {"service": "checkout", "healthy": True, "region": "blr1"},
    },
    "https://api.weather.local/current": {
        "status": 200,
        "json": {"city": "Bengaluru", "temp_c": 27, "condition": "cloudy"},
    },
}

# Canned DB result sets keyed by a query id (so we don't simulate SQL parsing).
_DB_CANNED = {
    "orders_by_email": {
        "columns": ["order_id", "status", "total"],
        "rows": [["1042", "shipped", "$129.00"], ["0987", "refunded", "$40.00"]],
    },
    "open_tickets_count": {
        "columns": ["count"],
        "rows": [[7]],
    },
    "customer_tier": {
        "columns": ["tier"],
        "rows": [["gold"]],
    },
}


def tool_http_get(url: str) -> dict:
    canned = _HTTP_CANNED.get((url or "").strip())
    if canned is None:
        return {"ok": False, "status": 404, "error": f"no canned response for {url!r}"}
    return {"ok": True, "status": canned["status"], "json": canned["json"]}


def tool_db_query(query_id: str) -> dict:
    canned = _DB_CANNED.get((query_id or "").strip())
    if canned is None:
        return {"ok": False, "error": f"unknown query id {query_id!r}"}
    return {"ok": True, "columns": canned["columns"], "rows": canned["rows"],
            "row_count": len(canned["rows"])}


def tool_send_notification(channel: str, message: str) -> dict:
    return {"ok": True, "channel": channel or "default", "message": message or "",
            "delivered": True}


def _run_tool_node(config: dict, payload: dict, run: dict) -> dict:
    """Execute a tool node; record side effects (notifications) on the run."""
    kind = (config or {}).get("kind", "http_get")
    if kind == "http_get":
        res = tool_http_get(config.get("url", ""))
        return {"tool_kind": "http_get", "tool_result": res,
                **({"http": res.get("json", {})} if res.get("ok") else {})}
    if kind == "db_query":
        res = tool_db_query(config.get("query_id", config.get("query", "")))
        return {"tool_kind": "db_query", "tool_result": res,
                **({"rows": res.get("rows", [])} if res.get("ok") else {})}
    if kind == "send_notification":
        # Allow the message to template a payload field via {field} syntax.
        message = _render_template(config.get("message", ""), payload)
        channel = config.get("channel", "default")
        res = tool_send_notification(channel, message)
        run.setdefault("notifications", []).append(
            {"channel": channel, "message": message})
        return {"tool_kind": "send_notification", "notification": res,
                "notified": True, "notify_channel": channel, "notify_message": message}
    return {"tool_kind": kind, "tool_result": {"ok": False, "error": f"unknown tool kind {kind!r}"}}


# ---------------------------------------------------------------------------
# Simulated MCP servers (canned tool catalogs + deterministic responses)
# ---------------------------------------------------------------------------

_MCP_SERVERS = {
    "metrics": {
        "description": "Infrastructure metrics MCP server",
        "tools": {
            "get_cpu": {"result": {"host": "web01", "cpu_pct": 82, "unit": "percent"}},
            "get_memory": {"result": {"host": "web01", "mem_pct": 64, "unit": "percent"}},
            "get_disk": {"result": {"host": "web01", "disk_pct": 47, "unit": "percent"}},
        },
    },
    "knowledge_base": {
        "description": "Docs/KB MCP server",
        "tools": {
            "search_docs": {"result": {"article": "Resetting your password",
                                        "url": "kb://account/password-reset"}},
            "get_sla": {"result": {"tier": "gold", "response_minutes": 30}},
        },
    },
    "orders": {
        "description": "Order-management MCP server",
        "tools": {
            "lookup_order": {"result": {"order_id": "1042", "status": "shipped",
                                         "eta_days": 2}},
            "issue_refund": {"result": {"order_id": "1042", "refunded": True,
                                         "amount": "$129.00"}},
        },
    },
}


def mcp_call(server: str, tool: str, args: dict | None = None) -> dict:
    srv = _MCP_SERVERS.get((server or "").strip())
    if srv is None:
        return {"ok": False, "error": f"unknown MCP server {server!r}"}
    spec = srv["tools"].get((tool or "").strip())
    if spec is None:
        return {"ok": False, "error": f"MCP server {server!r} has no tool {tool!r}",
                "available_tools": sorted(srv["tools"].keys())}
    return {"ok": True, "server": server, "tool": tool, "result": copy.deepcopy(spec["result"])}


def _run_mcp_node(config: dict, payload: dict) -> dict:
    server = (config or {}).get("server", "")
    tool = (config or {}).get("tool", "")
    res = mcp_call(server, tool, config.get("args"))
    out = {"mcp_server": server, "mcp_tool": tool, "mcp_result": res}
    if res.get("ok"):
        out["mcp_data"] = res.get("result", {})
    return out


# ---------------------------------------------------------------------------
# Transform + condition helpers
# ---------------------------------------------------------------------------

def _render_template(tmpl: str, payload: dict) -> str:
    """Replace {field} / {a.b} tokens in a template string with payload values."""
    def repl(m):
        path = m.group(1).strip()
        return str(_dig(payload, path))
    return re.sub(r"\{([^{}]+)\}", repl, str(tmpl or ""))


def _dig(payload: dict, path: str) -> Any:
    """Dotted-path lookup into a nested dict (a.b.c). Missing -> ''."""
    cur: Any = payload
    for part in str(path).split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return ""
    return cur


def _run_transform_node(config: dict, payload: dict) -> dict:
    op = (config or {}).get("op", "set")
    if op == "set":
        return {config.get("field", "value"): config.get("value", "")}
    if op == "template":
        rendered = _render_template(config.get("template", ""), payload)
        return {config.get("field", "text"): rendered}
    if op == "pick":
        fields = config.get("fields", [])
        return {f: _dig(payload, f) for f in fields}
    if op == "json_parse":
        src = payload.get(config.get("field", "body"))
        try:
            parsed = json.loads(src) if isinstance(src, str) else (src or {})
        except (ValueError, TypeError):
            parsed = {}
        if isinstance(parsed, dict):
            return parsed
        return {config.get("into", "parsed"): parsed}
    return {}


def _eval_condition(config: dict, payload: dict) -> bool:
    field = (config or {}).get("field", "")
    op = (config or {}).get("op", "equals")
    expected = config.get("value", "")
    actual = _dig(payload, field)
    if op == "equals":
        return str(actual) == str(expected)
    if op == "not_equals":
        return str(actual) != str(expected)
    if op == "contains":
        return str(expected) in str(actual)
    if op in ("gt", "greater_than"):
        try:
            return float(actual) > float(expected)
        except (ValueError, TypeError):
            return False
    if op in ("lt", "less_than"):
        try:
            return float(actual) < float(expected)
        except (ValueError, TypeError):
            return False
    if op == "exists":
        return actual not in ("", None, [], {})
    if op == "in":
        opts = expected if isinstance(expected, (list, tuple)) else str(expected).split(",")
        return str(actual) in [str(o).strip() for o in opts]
    return False


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def _node_by_id(graph: dict, node_id: str) -> dict | None:
    for n in graph.get("nodes", []):
        if n.get("id") == node_id:
            return n
    return None


def _next_node_id(graph: dict, node_type: str) -> str:
    """Stable, deterministic id like 'llm-1', 'tool-2' (no randomness)."""
    n = 1
    existing = {x.get("id") for x in graph.get("nodes", [])}
    while f"{node_type}-{n}" in existing:
        n += 1
    return f"{node_type}-{n}"


def _edges_from(graph: dict, node_id: str, branch: str | None = None) -> list[dict]:
    out = []
    for e in graph.get("edges", []):
        if e.get("from") != node_id:
            continue
        eb = e.get("branch")
        if branch is None:
            out.append(e)
        elif eb in (None, "", branch):
            out.append(e)
    return out


def _indegree(graph: dict) -> dict:
    deg = {n["id"]: 0 for n in graph.get("nodes", [])}
    for e in graph.get("edges", []):
        if e.get("to") in deg:
            deg[e["to"]] += 1
    return deg


# ---------------------------------------------------------------------------
# Workflow execution — topological run producing a trace + final output
# ---------------------------------------------------------------------------

def _run_workflow(graph: dict) -> dict:
    """Execute the graph from its trigger node(s) in topological order.

    Returns a run dict:
      {
        "ok": bool,
        "trace": [ {node_id, type, status, input, output, note} ],
        "final_output": {...},      # payload captured at the output node(s)
        "notifications": [...],     # messages "sent" during the run
        "errors": [...],
        "visited": [node_id, ...],
      }
    Execution is deterministic: nodes are visited in a stable order, the LLM/
    tools/MCP are all pure, so the same graph always yields the same trace.
    """
    run: dict = {"ok": True, "trace": [], "final_output": {}, "notifications": [],
                 "errors": [], "visited": []}

    nodes = graph.get("nodes", [])
    triggers = [n for n in nodes if n.get("type") == "trigger"]
    if not triggers:
        run["ok"] = False
        run["errors"].append("No trigger node — the workflow has no entry point.")
        return run

    # Per-node accumulated input payload (merged from all upstream outputs).
    payloads: dict[str, dict] = {}
    outputs: dict[str, dict] = {}

    # BFS/queue walk honouring condition branches; guard against cycles by
    # capping total node executions.
    queue: list[tuple[str, dict]] = []
    for t in triggers:
        seed = copy.deepcopy((t.get("config") or {}).get("input") or {})
        queue.append((t["id"], seed))

    max_steps = max(50, len(nodes) * 4)
    steps = 0
    final_outputs: list[dict] = []

    while queue and steps < max_steps:
        node_id, incoming = queue.pop(0)
        steps += 1
        node = _node_by_id(graph, node_id)
        if node is None:
            continue
        # Merge this incoming payload into the node's accumulated payload.
        acc = payloads.setdefault(node_id, {})
        acc.update(incoming or {})
        payload = copy.deepcopy(acc)

        ntype = node.get("type")
        config = node.get("config") or {}
        produced: dict = {}
        branch_taken: str | None = None
        note = ""

        try:
            if ntype == "trigger":
                produced = {}  # seed already in payload
                note = f"emitted seed payload ({(config.get('kind') or 'manual')})"
            elif ntype == "llm":
                produced = _run_llm_node(config, payload)
                note = f"llm {produced.get('llm_mode')}"
            elif ntype == "tool":
                produced = _run_tool_node(config, payload, run)
                note = f"tool {produced.get('tool_kind')}"
            elif ntype == "mcp_tool":
                produced = _run_mcp_node(config, payload)
                note = f"mcp {config.get('server')}.{config.get('tool')}"
            elif ntype == "transform":
                produced = _run_transform_node(config, payload)
                note = f"transform {config.get('op')}"
            elif ntype == "condition":
                cond = _eval_condition(config, payload)
                branch_taken = "true" if cond else "false"
                produced = {"condition_result": cond, "branch": branch_taken}
                note = f"condition -> {branch_taken}"
            elif ntype == "output":
                produced = {}
                note = "captured final output"
            else:
                produced = {}
                note = f"unknown node type {ntype!r}"
                run["errors"].append(note)
        except Exception as exc:  # never let a node crash the run
            run["ok"] = False
            run["errors"].append(f"{node_id}: {exc}")
            note = f"error: {exc}"

        # Merge produced fields back into the running payload.
        acc.update(produced)
        out_payload = copy.deepcopy(acc)
        outputs[node_id] = out_payload

        run["visited"].append(node_id)
        run["trace"].append({
            "node_id": node_id,
            "type": ntype,
            "label": node.get("label", node_id),
            "status": "ok" if not note.startswith("error") else "error",
            "input": payload,
            "output": produced,
            "branch": branch_taken,
            "note": note,
        })

        if ntype == "output":
            final_outputs.append(out_payload)
            continue

        # Enqueue downstream nodes (respecting the chosen branch for conditions).
        for e in _edges_from(graph, node_id, branch_taken):
            queue.append((e["to"], out_payload))

    if steps >= max_steps:
        run["errors"].append("Execution step cap reached (possible cycle).")

    # Final output: prefer an explicit output node; else the last visited payload.
    if final_outputs:
        merged: dict = {}
        for fo in final_outputs:
            merged.update(fo)
        run["final_output"] = merged
    elif run["visited"]:
        run["final_output"] = outputs.get(run["visited"][-1], {})

    if run["errors"]:
        run["ok"] = False
    return run


# ---------------------------------------------------------------------------
# Scenario presets — partial/broken graph + a goal per scenario
#
# Each preset returns a graph (nodes+edges) and a `goal`. validate_aiml_lab
# reads ONLY the goal + the learner's graph + a fresh run; a preset is designed
# to FAIL until the learner builds/fixes it correctly.
# ---------------------------------------------------------------------------

def _node(node_id: str, ntype: str, label: str, config: dict,
          x: int = 0, y: int = 0) -> dict:
    return {"id": node_id, "type": ntype, "label": label,
            "config": config, "x": x, "y": y}


def _empty_graph() -> dict:
    return {"nodes": [], "edges": []}


def _preset_support_triage() -> tuple[dict, dict]:
    """Scenario 1: build a support-ticket triage agent.

    Preset ships ONLY the trigger (seed ticket) + an output node, unconnected.
    The learner must add an llm(classify) node and a condition node, then wire
    trigger -> llm -> condition -> (high priority) send_notification, so an
    urgent security/outage ticket gets escalated.
    """
    graph = {
        "nodes": [
            _node("trigger-1", "trigger", "New Support Ticket",
                  {"kind": "ticket", "input": {
                      "text": "URGENT: our account was hacked, we see unauthorized "
                              "logins and suspicious activity. Please help immediately!",
                      "ticket_id": "T-5521",
                  }}, x=40, y=160),
            _node("output-1", "output", "Triaged Result", {}, x=620, y=160),
        ],
        "edges": [],
    }
    goal = {
        "kind": "support_triage",
        "title": "Build a support-ticket triage agent",
        "objective": (
            "Wire trigger -> LLM(classify) -> condition -> notification. The "
            "incoming ticket is a security incident, so the classifier must tag "
            "it and the condition must route a high-priority ticket to a "
            "send_notification tool that escalates it."),
        # Topology requirements (node types that must exist + be on the path).
        "require_path": ["trigger", "llm", "condition", "tool"],
        "require_llm_mode": "classify",
        "require_tool_kind": "send_notification",
        # Run-output requirements (deterministic): the seed ticket classifies as
        # security/high and a notification must have actually been sent.
        "require_output": {"category": "security", "priority": "high"},
        "require_notification": True,
    }
    return graph, goal


def _preset_n8n_flow() -> tuple[dict, dict]:
    """Scenario 2: wire an n8n-style flow.

    webhook trigger -> transform(json_parse) -> llm(extract) -> tool(http_get) ->
    output. Preset ships the trigger + a disconnected http_get tool + output; the
    learner adds the parse/extract steps and connects everything so the order is
    looked up via the API.
    """
    graph = {
        "nodes": [
            _node("trigger-1", "trigger", "Webhook",
                  {"kind": "webhook", "input": {
                      "body": '{"text": "Where is my order #1042? Email amy@example.com"}',
                  }}, x=40, y=160),
            _node("tool-1", "tool", "Order API",
                  {"kind": "http_get", "url": "https://api.fixitlab.local/orders/1042"},
                  x=620, y=160),
            _node("output-1", "output", "Response", {}, x=860, y=160),
        ],
        "edges": [],
    }
    goal = {
        "kind": "n8n_flow",
        "title": "Wire an n8n-style order-lookup flow",
        "objective": (
            "Connect webhook -> transform(json_parse) -> LLM(extract) -> "
            "tool(http_get) -> output. Parse the raw webhook JSON body, extract "
            "the customer's order id + email, then call the Order API and return "
            "the order status."),
        "require_path": ["trigger", "transform", "llm", "tool", "output"],
        "require_llm_mode": "extract",
        "require_tool_kind": "http_get",
        "require_transform_op": "json_parse",
        # The http_get tool must return the shipped order from the canned API.
        "require_output": {"http.status": "shipped", "entities.order_id": "1042"},
    }
    return graph, goal


def _preset_fix_wrong_tool() -> tuple[dict, dict]:
    """Scenario 3: fix a broken agent that calls the WRONG tool / misroutes.

    The graph is fully built but BROKEN in two ways:
      (a) the LLM node is in 'summarize' mode (should be 'classify'), and
      (b) the condition compares the wrong field/value AND routes the 'true'
          branch to a db_query tool instead of the send_notification escalation;
          the escalation tool is wired on the wrong branch.
    The learner must fix the llm mode, the condition, and re-route the edge so a
    refund/billing ticket is escalated correctly.
    """
    graph = {
        "nodes": [
            _node("trigger-1", "trigger", "New Ticket",
                  {"kind": "ticket", "input": {
                      "text": "I was charged twice for my subscription and want a "
                              "refund on the duplicate invoice. This is unacceptable.",
                      "ticket_id": "T-7700",
                  }}, x=40, y=180),
            # BUG (a): wrong mode — summarize instead of classify.
            _node("llm-1", "llm", "Classifier",
                  {"mode": "summarize", "input_field": "text"}, x=280, y=180),
            # BUG (b): wrong field/value — checks sentiment==positive.
            _node("cond-1", "condition", "Route",
                  {"field": "sentiment", "op": "equals", "value": "positive"},
                  x=520, y=180),
            _node("tool-notify", "tool", "Escalate",
                  {"kind": "send_notification", "channel": "billing-team",
                   "message": "Escalating billing ticket {ticket_id}"}, x=780, y=80),
            _node("tool-db", "tool", "Log Query",
                  {"kind": "db_query", "query_id": "open_tickets_count"}, x=780, y=300),
            _node("output-1", "output", "Result", {}, x=1020, y=180),
        ],
        "edges": [
            {"from": "trigger-1", "to": "llm-1"},
            {"from": "llm-1", "to": "cond-1"},
            # BUG: notify is on the 'false' branch, db on 'true' — swapped.
            {"from": "cond-1", "to": "tool-db", "branch": "true"},
            {"from": "cond-1", "to": "tool-notify", "branch": "false"},
            {"from": "tool-notify", "to": "output-1"},
            {"from": "tool-db", "to": "output-1"},
        ],
    }
    goal = {
        "kind": "fix_misroute",
        "title": "Fix the misrouting billing-escalation agent",
        "objective": (
            "This agent should escalate high-priority billing tickets, but it is "
            "broken: the LLM is summarising instead of classifying, and the "
            "condition checks the wrong field and routes to the wrong tool. Fix "
            "the LLM mode to classify, fix the condition to detect a high "
            "priority ticket, and route the high-priority branch into the "
            "send_notification escalation so the refund ticket is escalated."),
        "require_path": ["trigger", "llm", "condition", "tool"],
        "require_llm_mode": "classify",
        "require_tool_kind": "send_notification",
        "require_output": {"category": "billing", "priority": "high"},
        "require_notification": True,
        # The send_notification must be the tool that actually fired (not db).
        "require_notification_channel_not": "",
    }
    return graph, goal


def _preset_mcp_data_question() -> tuple[dict, dict]:
    """Scenario 4: add an MCP tool node so the agent can answer a data question.

    The agent classifies an infra question but currently has NO way to fetch the
    live metric — it just outputs a guess. The learner must add an mcp_tool node
    (metrics server, get_cpu tool) and wire it in so the final output carries the
    real CPU figure from the MCP server, then notify ops if it's high.
    """
    graph = {
        "nodes": [
            _node("trigger-1", "trigger", "Ops Question",
                  {"kind": "chat", "input": {
                      "text": "What is the current CPU usage on web01? It feels slow.",
                      "host": "web01",
                  }}, x=40, y=160),
            _node("llm-1", "llm", "Intent",
                  {"mode": "classify", "input_field": "text"}, x=300, y=160),
            _node("output-1", "output", "Answer", {}, x=820, y=160),
        ],
        "edges": [
            {"from": "trigger-1", "to": "llm-1"},
            # Note: llm is NOT connected to output yet, and there is no MCP node.
        ],
    }
    goal = {
        "kind": "mcp_answer",
        "title": "Add an MCP tool so the agent can answer a data question",
        "objective": (
            "The agent recognises an infra question but cannot fetch the live "
            "metric. Add an MCP tool node (server 'metrics', tool 'get_cpu') and "
            "wire trigger -> LLM -> mcp_tool -> output so the final answer "
            "includes the real CPU percentage from the MCP server."),
        "require_path": ["trigger", "llm", "mcp_tool", "output"],
        "require_mcp": {"server": "metrics", "tool": "get_cpu"},
        # The MCP result (cpu_pct=82) must surface in the final output.
        "require_output": {"mcp_data.cpu_pct": 82},
    }
    return graph, goal


_PRESETS = {
    "agent-support-ticket-triage": _preset_support_triage,
    "agent-n8n-order-lookup-flow": _preset_n8n_flow,
    "agent-fix-misrouted-escalation": _preset_fix_wrong_tool,
    "agent-mcp-metrics-answer": _preset_mcp_data_question,
}


def _apply_preset(state: dict, slug: str) -> None:
    s = (slug or "").lower()
    builder = _PRESETS.get(s)
    if builder is None:
        # Substring fallback so close slugs still map to the right preset.
        if "triage" in s or "support-ticket" in s:
            builder = _preset_support_triage
        elif "n8n" in s or "order-lookup" in s or "flow" in s:
            builder = _preset_n8n_flow
        elif "misroute" in s or "fix" in s or "wrong-tool" in s or "escalation" in s:
            builder = _preset_fix_wrong_tool
        elif "mcp" in s or "metrics" in s or "data-question" in s:
            builder = _preset_mcp_data_question
        else:
            builder = _preset_support_triage
    graph, goal = builder()
    state["graph"] = graph
    state["goal"] = goal
    state["last_run"] = None


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state: dict = {}
        _apply_preset(state, scenario_slug)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    graph = state.get("graph", _empty_graph())
    goal = state.get("goal", {})
    last_run = state.get("last_run")

    ok, msg = _grade(state)

    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "graph": graph,
        "palette": NODE_PALETTE,
        "node_types": list(NODE_TYPES),
        # Catalogs the UI surfaces in the config panel (which tools/MCP exist).
        "catalog": {
            "tool_kinds": ["http_get", "db_query", "send_notification"],
            "http_urls": sorted(_HTTP_CANNED.keys()),
            "db_queries": sorted(_DB_CANNED.keys()),
            "mcp_servers": {
                name: {"description": srv["description"],
                       "tools": sorted(srv["tools"].keys())}
                for name, srv in _MCP_SERVERS.items()
            },
            "llm_modes": ["classify", "extract", "summarize"],
            "transform_ops": ["set", "template", "pick", "json_parse"],
            "condition_ops": ["equals", "not_equals", "contains", "gt", "lt",
                              "exists", "in"],
        },
        "goal": goal,
        "last_run": last_run,
        # Mirror the other engines' {events} activity feed: the last run trace.
        "events": (last_run or {}).get("trace", []) if last_run else [],
        "summary": {
            "node_count": len(graph.get("nodes", [])),
            "edge_count": len(graph.get("edges", [])),
            "has_run": last_run is not None,
            "last_run_ok": bool(last_run and last_run.get("ok")),
            "goal_title": goal.get("title", ""),
            "objective": goal.get("objective", ""),
            "validation_passed": ok,
            "validation_message": msg,
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Actions — mutate the graph, run it, or reset
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Agent session not found"}
    state = entry["state"]
    graph = state.setdefault("graph", _empty_graph())

    if action == "add_node":
        ntype = payload.get("type") or payload.get("node_type")
        if ntype not in NODE_TYPES:
            return {"ok": False, "error": f"unknown node type {ntype!r}"}
        config = payload.get("config") or {}
        label = payload.get("label") or ntype.replace("_", " ").title()
        node_id = payload.get("id") or _next_node_id(graph, ntype)
        if _node_by_id(graph, node_id):
            return {"ok": False, "error": f"node id {node_id!r} already exists"}
        node = _node(node_id, ntype, label, config,
                     x=int(payload.get("x", 0) or 0), y=int(payload.get("y", 0) or 0))
        graph.setdefault("nodes", []).append(node)
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Added {ntype} node {node_id}", "node": node}

    if action == "remove_node":
        node_id = payload.get("id") or payload.get("node_id")
        if not _node_by_id(graph, node_id):
            return {"ok": False, "error": "node not found"}
        graph["nodes"] = [n for n in graph.get("nodes", []) if n.get("id") != node_id]
        graph["edges"] = [e for e in graph.get("edges", [])
                          if e.get("from") != node_id and e.get("to") != node_id]
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Removed node {node_id}"}

    if action == "connect":
        src = payload.get("from") or payload.get("from_id") or payload.get("source")
        dst = payload.get("to") or payload.get("to_id") or payload.get("target")
        if not _node_by_id(graph, src) or not _node_by_id(graph, dst):
            return {"ok": False, "error": "both from and to nodes must exist"}
        if src == dst:
            return {"ok": False, "error": "cannot connect a node to itself"}
        branch = payload.get("branch")  # None | "true" | "false"
        edge = {"from": src, "to": dst}
        if branch in ("true", "false"):
            edge["branch"] = branch
        # De-dupe identical edges (same from/to/branch).
        for e in graph.get("edges", []):
            if (e.get("from") == src and e.get("to") == dst
                    and e.get("branch") == edge.get("branch")):
                return {"ok": False, "error": "edge already exists"}
        graph.setdefault("edges", []).append(edge)
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Connected {src} -> {dst}", "edge": edge}

    if action == "disconnect":
        src = payload.get("from") or payload.get("from_id") or payload.get("source")
        dst = payload.get("to") or payload.get("to_id") or payload.get("target")
        branch = payload.get("branch")
        before = len(graph.get("edges", []))
        graph["edges"] = [
            e for e in graph.get("edges", [])
            if not (e.get("from") == src and e.get("to") == dst
                    and (branch is None or e.get("branch") in (None, "", branch)))
        ]
        if len(graph["edges"]) == before:
            return {"ok": False, "error": "edge not found"}
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Disconnected {src} -> {dst}"}

    if action == "configure_node":
        node_id = payload.get("id") or payload.get("node_id")
        node = _node_by_id(graph, node_id)
        if not node:
            return {"ok": False, "error": "node not found"}
        new_config = payload.get("config")
        if not isinstance(new_config, dict):
            return {"ok": False, "error": "config must be an object"}
        if payload.get("merge"):
            node.setdefault("config", {}).update(new_config)
        else:
            node["config"] = new_config
        if payload.get("label"):
            node["label"] = payload["label"]
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Configured node {node_id}", "node": node}

    if action == "set_trigger_input":
        # Convenience: override the seed payload of a trigger node.
        node_id = payload.get("id") or payload.get("node_id")
        node = _node_by_id(graph, node_id) if node_id else next(
            (n for n in graph.get("nodes", []) if n.get("type") == "trigger"), None)
        if not node or node.get("type") != "trigger":
            return {"ok": False, "error": "trigger node not found"}
        node.setdefault("config", {})["input"] = payload.get("input") or {}
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Trigger input updated"}

    if action == "run_workflow":
        run = _run_workflow(graph)
        state["last_run"] = run
        _save_session(str(session_id), entry)
        ok, msg = _grade(state)
        return {"ok": True, "message": run.get("ok") and "Workflow ran"
                or "Workflow ran with errors", "run": run,
                "validation_passed": ok, "validation_message": msg}

    if action == "reset":
        _apply_preset(state, entry.get("scenario_slug", ""))
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Workflow reset to scenario starting point"}

    return {"ok": False, "error": f"unknown action: {action}"}


# ---------------------------------------------------------------------------
# Validation — grade topology + configs + deterministic run output vs the goal
# ---------------------------------------------------------------------------

def _path_types_present(graph: dict, required_types: list[str]) -> tuple[bool, str]:
    """Check that there is a directed path that visits the required node TYPES
    in order, starting from a trigger. We don't require *only* those nodes — just
    that a chain exists hitting each required type in sequence."""
    if not required_types:
        return True, ""
    # Build adjacency (ignoring branch — any wired edge counts for topology).
    adj: dict[str, list[str]] = {}
    for e in graph.get("edges", []):
        adj.setdefault(e["from"], []).append(e["to"])
    type_of = {n["id"]: n.get("type") for n in graph.get("nodes", [])}

    starts = [n["id"] for n in graph.get("nodes", [])
              if n.get("type") == required_types[0]]
    if not starts:
        return False, f"missing a {required_types[0]} node"

    # DFS: from each start, try to match the required type sequence.
    def dfs(node_id: str, idx: int, seen: set) -> bool:
        if idx >= len(required_types):
            return True
        if type_of.get(node_id) != required_types[idx]:
            return False
        if idx == len(required_types) - 1:
            return True
        for nxt in adj.get(node_id, []):
            if nxt in seen:
                continue
            if dfs(nxt, idx + 1, seen | {nxt}):
                return True
        return False

    for s in starts:
        if dfs(s, 0, {s}):
            return True, ""
    return False, ("required node chain not wired in order: "
                   + " -> ".join(required_types))


def _output_matches(final_output: dict, requirements: dict) -> tuple[bool, str]:
    """Every required dotted-path key in final_output must equal the expected
    value (string-compared, except numbers compared numerically)."""
    for path, expected in (requirements or {}).items():
        actual = _dig(final_output or {}, path)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            try:
                if float(actual) != float(expected):
                    return False, f"output {path}={actual!r} (expected {expected})"
            except (ValueError, TypeError):
                return False, f"output {path}={actual!r} (expected {expected})"
        else:
            if str(actual) != str(expected):
                return False, f"output {path}={actual!r} (expected {expected!r})"
    return True, ""


def _has_node_config(graph: dict, ntype: str, key: str, value: Any) -> bool:
    for n in graph.get("nodes", []):
        if n.get("type") == ntype and (n.get("config") or {}).get(key) == value:
            return True
    return False


def _grade(state: dict) -> tuple[bool, str]:
    """Pure grader over the current state (graph + last_run vs goal).

    Validation runs a FRESH execution of the current graph (it does not trust a
    stale last_run), so the verdict always reflects the graph as it stands.
    """
    goal = state.get("goal") or {}
    graph = state.get("graph") or _empty_graph()
    kind = goal.get("kind")
    if not kind:
        return False, "No validation goal configured for this scenario"

    # 1) Topology: required node-type chain wired in order.
    ok, msg = _path_types_present(graph, goal.get("require_path", []))
    if not ok:
        return False, f"Graph not complete — {msg}."

    # 2) Config checks.
    if goal.get("require_llm_mode") is not None:
        if not _has_node_config(graph, "llm", "mode", goal["require_llm_mode"]):
            return False, (f"LLM node must be in '{goal['require_llm_mode']}' mode.")
    if goal.get("require_tool_kind") is not None:
        if not _has_node_config(graph, "tool", "kind", goal["require_tool_kind"]):
            return False, (f"A tool node of kind '{goal['require_tool_kind']}' "
                           "must be present.")
    if goal.get("require_transform_op") is not None:
        if not _has_node_config(graph, "transform", "op", goal["require_transform_op"]):
            return False, (f"A transform node with op '{goal['require_transform_op']}' "
                           "must be present.")
    if goal.get("require_mcp") is not None:
        want = goal["require_mcp"]
        match = any(
            n.get("type") == "mcp_tool"
            and (n.get("config") or {}).get("server") == want.get("server")
            and (n.get("config") or {}).get("tool") == want.get("tool")
            for n in graph.get("nodes", [])
        )
        if not match:
            return False, (f"An MCP tool node calling {want.get('server')}."
                           f"{want.get('tool')} must be present.")

    # 3) Deterministic run output. Execute the current graph fresh.
    run = _run_workflow(graph)
    if not run.get("ok") and run.get("errors"):
        return False, "Workflow run errored: " + "; ".join(run["errors"][:2])

    if goal.get("require_notification"):
        notifs = run.get("notifications", [])
        if not notifs:
            return False, ("No notification was sent on this run — the "
                           "send_notification tool must fire on the taken branch.")

    ok, msg = _output_matches(run.get("final_output", {}), goal.get("require_output", {}))
    if not ok:
        return False, f"Run output does not yet meet the goal — {msg}."

    return True, f"Validation passed — {goal.get('title', 'goal met')}."


def validate_aiml_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    """Public validation entry point (mirrors validate_nmap_lab).

    Returns (passed, message). A fresh preset fails; only the correct graph +
    configs + deterministic run output flips it to pass.
    """
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    return _grade(entry["state"])
