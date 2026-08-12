"""In-memory SIEM / SOC console simulator for cybersecurity training labs.

Server-authoritative, session-cached (Django cache / Redis) mirror of a
Security Operations Center console: alerts, incidents, log search, response
playbooks, and monitored assets. Models the analyst triage workflow — an alert
is acknowledged, escalated into an incident, investigated (log search,
playbook run), remediated (quarantine host / block IP), then closed.
"""

from __future__ import annotations

import copy
import fnmatch
import json
import re
import time

from django.core.cache import cache

from .soc_v2_facades import apply_v2_action, ensure_v2, seed_v2

SESSION_TTL = 7200


def _session_key(session_id: str) -> str:
    return f"soc_session:{session_id}"


def _load(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(state: dict, message: str, severity: str = "info") -> None:
    entry = {"time": _now_iso(), "message": message, "severity": severity}
    state.setdefault("events", []).insert(0, entry)
    state.setdefault("activity_log", []).insert(0, entry)
    state["activity_log"] = state["activity_log"][:200]


# ---------------------------------------------------------------------------
# SPL-subset query language
#
# Log hunting is the one SOC skill that has to be *typed*, not clicked, so the
# search box parses a real (small) Splunk-flavoured grammar instead of doing a
# substring match over the JSON dump of each row. The two rules that matter for
# grading correctness:
#
#   1. A query that fails to parse returns ZERO rows and raises. It must never
#      degrade into "match everything", because the hunt objective is cleared by
#      inspecting the result set — a permissive fallback would auto-pass labs.
#   2. Matching is field-aware. `host=web01` only looks at the host field, so a
#      learner cannot stumble onto the answer by pasting a term that happens to
#      appear in an unrelated column.
#
# Grammar (subset):
#   pipeline := search_expr ("|" command)*
#   search_expr := or_expr
#   or_expr  := and_expr (("OR") and_expr)*
#   and_expr := unary (("AND")? unary)*        # juxtaposition is implicit AND
#   unary    := "NOT" unary | "(" or_expr ")" | comparison | term
#   comparison := field op value               # op: = != > >= < <=
#   term     := bare word or "quoted phrase"   # substring/glob over all fields
#   command  := where <or_expr> | search <or_expr> | stats count [by f]
#             | fields f,... | sort [-]f | head n | tail n | dedup f | rename a as b
# ---------------------------------------------------------------------------


class SocQueryError(ValueError):
    """Raised when a search string is not valid in the SPL subset."""


_COMPARISON_OPS = ("!=", ">=", "<=", "=", ">", "<")
# Longest-first so ">=" is never tokenized as ">" followed by "=".
_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<lparen>\()
      | (?P<rparen>\))
      | (?P<pipe>\|)
      | (?P<comma>,)
      | (?P<op>!=|>=|<=|=|>|<)
      | (?P<quoted>"[^"]*"|'[^']*')
      | (?P<word>[^\s()|,=!<>]+)
    )
    """,
    re.VERBOSE,
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
            continue
        match = _TOKEN_RE.match(text, pos)
        if not match or match.end() == pos:
            raise SocQueryError(f"unexpected character {text[pos]!r} at position {pos}")
        kind = match.lastgroup or ""
        value = match.group(kind)
        if kind == "quoted":
            value = value[1:-1]
        tokens.append((kind, value))
        pos = match.end()
    return tokens


def _row_values(row: dict) -> list[str]:
    return [str(v) for v in row.values()]


def _coerce(value: str):
    """Numeric-compare when both sides look numeric, else compare as text."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _match_scalar(actual: str, expected: str) -> bool:
    """Case-insensitive equality with glob support (`powershell*`)."""
    actual, expected = str(actual), str(expected)
    if any(ch in expected for ch in "*?"):
        return fnmatch.fnmatch(actual.lower(), expected.lower())
    return actual.lower() == expected.lower()


class _Term:
    """Bare word / quoted phrase: substring or glob across every field."""

    def __init__(self, value: str):
        self.value = value

    def matches(self, row: dict) -> bool:
        needle = self.value.lower()
        globbing = any(ch in self.value for ch in "*?")
        for raw in _row_values(row):
            hay = raw.lower()
            if globbing:
                if fnmatch.fnmatch(hay, needle):
                    return True
            elif needle in hay:
                return True
        return False

    def referenced_fields(self) -> set[str]:
        return set()


class _Comparison:
    def __init__(self, field: str, op: str, value: str):
        self.field, self.op, self.value = field, op, value

    def matches(self, row: dict) -> bool:
        if self.field not in row:
            return False
        actual = row[self.field]
        if self.op == "=":
            return _match_scalar(actual, self.value)
        if self.op == "!=":
            return not _match_scalar(actual, self.value)
        left, right = _coerce(str(actual)), _coerce(self.value)
        if left is None or right is None:
            # Non-numeric operands fall back to lexicographic order, which is
            # what makes `time>2026-07-16T10:00:00Z` work on ISO timestamps.
            left, right = str(actual).lower(), self.value.lower()
        if self.op == ">":
            return left > right
        if self.op == ">=":
            return left >= right
        if self.op == "<":
            return left < right
        return left <= right

    def referenced_fields(self) -> set[str]:
        return {self.field}


class _Not:
    def __init__(self, child):
        self.child = child

    def matches(self, row: dict) -> bool:
        return not self.child.matches(row)

    def referenced_fields(self) -> set[str]:
        return self.child.referenced_fields()


class _BoolOp:
    def __init__(self, op: str, children: list):
        self.op, self.children = op, children

    def matches(self, row: dict) -> bool:
        if self.op == "AND":
            return all(c.matches(row) for c in self.children)
        return any(c.matches(row) for c in self.children)

    def referenced_fields(self) -> set[str]:
        fields: set[str] = set()
        for child in self.children:
            fields |= child.referenced_fields()
        return fields


class _MatchAll:
    """Only produced by an explicitly empty stage (e.g. a leading `| stats`)."""

    def matches(self, row: dict) -> bool:
        return True

    def referenced_fields(self) -> set[str]:
        return set()


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]]):
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self) -> tuple[str, str]:
        token = self._peek()
        if token is None:
            raise SocQueryError("unexpected end of query")
        self.pos += 1
        return token

    def _at_keyword(self, *words: str) -> bool:
        token = self._peek()
        return bool(token and token[0] == "word" and token[1].upper() in words)

    def parse_expr(self):
        return self._parse_or()

    def _parse_or(self):
        nodes = [self._parse_and()]
        while self._at_keyword("OR"):
            self._next()
            nodes.append(self._parse_and())
        return nodes[0] if len(nodes) == 1 else _BoolOp("OR", nodes)

    def _parse_and(self):
        nodes = [self._parse_unary()]
        while True:
            token = self._peek()
            if token is None or token[0] in ("pipe", "rparen", "comma"):
                break
            if self._at_keyword("OR"):
                break
            if self._at_keyword("AND"):
                self._next()
            nodes.append(self._parse_unary())
        return nodes[0] if len(nodes) == 1 else _BoolOp("AND", nodes)

    def _parse_unary(self):
        if self._at_keyword("NOT"):
            self._next()
            return _Not(self._parse_unary())
        token = self._peek()
        if token is None:
            raise SocQueryError("unexpected end of query")
        if token[0] == "lparen":
            self._next()
            node = self._parse_or()
            closing = self._peek()
            if not closing or closing[0] != "rparen":
                raise SocQueryError("unbalanced parenthesis")
            self._next()
            return node
        if token[0] in ("word", "quoted"):
            return self._parse_leaf()
        raise SocQueryError(f"unexpected token {token[1]!r}")

    def _parse_leaf(self):
        kind, value = self._next()
        following = self._peek()
        # `field=value` — only an unquoted left side may name a field, so
        # "203.0.113.55" stays a plain term even though it contains dots.
        if kind == "word" and following and following[0] == "op":
            _, op = self._next()
            operand = self._peek()
            if not operand or operand[0] not in ("word", "quoted"):
                raise SocQueryError(f"missing value after {value}{op}")
            self._next()
            return _Comparison(value, op, operand[1])
        return _Term(value)


def _parse_command(parser: _Parser) -> dict:
    token = parser._peek()
    if token is None or token[0] != "word":
        raise SocQueryError("expected a command after '|'")
    name = parser._next()[1].lower()

    if name in ("where", "search"):
        return {"name": name, "expr": parser.parse_expr()}

    if name == "stats":
        agg = parser._next()
        if agg[0] != "word" or agg[1].lower() != "count":
            raise SocQueryError("only 'stats count' is supported")
        by_fields: list[str] = []
        if parser._at_keyword("BY"):
            parser._next()
            while True:
                field = parser._peek()
                if not field or field[0] != "word":
                    raise SocQueryError("expected a field name after 'by'")
                by_fields.append(parser._next()[1])
                nxt = parser._peek()
                if nxt and nxt[0] == "comma":
                    parser._next()
                    continue
                break
        return {"name": "stats", "by": by_fields}

    if name == "fields":
        names: list[str] = []
        while True:
            field = parser._peek()
            if not field or field[0] != "word":
                break
            names.append(parser._next()[1])
            nxt = parser._peek()
            if nxt and nxt[0] == "comma":
                parser._next()
                continue
            break
        if not names:
            raise SocQueryError("'fields' needs at least one field name")
        return {"name": "fields", "names": names}

    if name == "sort":
        field = parser._peek()
        if not field or field[0] != "word":
            raise SocQueryError("'sort' needs a field name")
        raw = parser._next()[1]
        descending = raw.startswith("-")
        return {"name": "sort", "field": raw.lstrip("-+"), "desc": descending}

    if name in ("head", "tail"):
        count = parser._peek()
        limit = 10
        if count and count[0] == "word":
            try:
                limit = int(parser._next()[1])
            except ValueError:
                raise SocQueryError(f"'{name}' needs a number")
        if limit < 0:
            raise SocQueryError(f"'{name}' needs a non-negative number")
        return {"name": name, "limit": limit}

    if name == "dedup":
        field = parser._peek()
        if not field or field[0] != "word":
            raise SocQueryError("'dedup' needs a field name")
        return {"name": "dedup", "field": parser._next()[1]}

    if name == "rename":
        src = parser._peek()
        if not src or src[0] not in ("word", "quoted"):
            raise SocQueryError("'rename' needs a field name")
        source = parser._next()[1]
        if not parser._at_keyword("AS"):
            raise SocQueryError("'rename' syntax is: rename <field> as <name>")
        parser._next()
        dest = parser._peek()
        if not dest or dest[0] not in ("word", "quoted"):
            raise SocQueryError("'rename' needs a target name")
        return {"name": "rename", "src": source, "dst": parser._next()[1]}

    raise SocQueryError(f"unknown command '{name}'")


def parse_soc_query(query: str) -> dict:
    """Parse an SPL-subset query into a filter expression plus a command list.

    Raises SocQueryError on anything malformed — callers must surface the error
    rather than falling back to an unfiltered result set.
    """
    text = (query or "").strip()
    if not text:
        raise SocQueryError("empty query")
    tokens = _tokenize(text)
    if not tokens:
        raise SocQueryError("empty query")

    parser = _Parser(tokens)
    # A query may start straight at a pipe (`| stats count by host`), in which
    # case the implicit base search matches every row.
    if parser._peek() and parser._peek()[0] == "pipe":
        expr = _MatchAll()
    else:
        expr = parser.parse_expr()

    commands: list[dict] = []
    while True:
        token = parser._peek()
        if token is None:
            break
        if token[0] != "pipe":
            raise SocQueryError(f"unexpected token {token[1]!r} — expected '|'")
        parser._next()
        commands.append(_parse_command(parser))

    return {"expr": expr, "commands": commands}


def _apply_commands(rows: list[dict], commands: list[dict]) -> list[dict]:
    for command in commands:
        name = command["name"]
        if name in ("where", "search"):
            rows = [r for r in rows if command["expr"].matches(r)]
        elif name == "stats":
            by = command["by"]
            if not by:
                rows = [{"count": len(rows)}]
            else:
                buckets: dict[tuple, int] = {}
                for row in rows:
                    key = tuple(str(row.get(f, "")) for f in by)
                    buckets[key] = buckets.get(key, 0) + 1
                rows = [
                    {**dict(zip(by, key)), "count": count}
                    for key, count in sorted(buckets.items(), key=lambda kv: (-kv[1], kv[0]))
                ]
        elif name == "fields":
            names = command["names"]
            rows = [{k: v for k, v in row.items() if k in names} for row in rows]
        elif name == "sort":
            field = command["field"]
            rows = sorted(rows, key=lambda r: str(r.get(field, "")), reverse=command["desc"])
        elif name == "head":
            rows = rows[: command["limit"]]
        elif name == "tail":
            rows = rows[-command["limit"]:] if command["limit"] else []
        elif name == "dedup":
            field = command["field"]
            seen: set[str] = set()
            deduped = []
            for row in rows:
                key = str(row.get(field, ""))
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(row)
            rows = deduped
        elif name == "rename":
            src, dst = command["src"], command["dst"]
            rows = [
                {(dst if k == src else k): v for k, v in row.items()}
                for row in rows
            ]
    return rows


def run_soc_query(rows: list[dict], query: str) -> list[dict]:
    """Run an SPL-subset query over log rows. Raises SocQueryError if invalid."""
    plan = parse_soc_query(query)
    matched = [r for r in rows if plan["expr"].matches(r)]
    return _apply_commands(matched, plan["commands"])


def _hunt_query_isolates_target(rows: list[dict], results: list[dict], target: str) -> bool:
    """Did this query actually isolate the hunted indicator?

    Result-driven on purpose: the old check was string equality against two IP
    literals, so `host=web01 AND "198.51.100.23"` — a better query than the
    literal — failed while pasting the bare IP passed. The objective is met when
    the query narrowed the index (it did not just return everything) and every
    row it returned is one of the rows that genuinely mentions the target.
    """
    if not results:
        return False
    target_rows = [r for r in rows if target.lower() in json.dumps(r, default=str).lower()]
    if not target_rows:
        return False
    # Must be a real narrowing, not `*` or a term that matches the whole index.
    if len(results) >= len(rows) and len(target_rows) < len(rows):
        return False
    # `stats`/`fields` reshape rows, so compare on the projected content: every
    # returned row has to be derived from a row that mentions the target.
    for row in results:
        blob = json.dumps(row, default=str).lower()
        if target.lower() in blob:
            continue
        if any(
            all(str(v).lower() in json.dumps(tr, default=str).lower() for v in row.values())
            for tr in target_rows
        ):
            continue
        return False
    return True


def _base_state() -> dict:
    return {
        "session": {"logged_in": False, "user": ""},
        "summary": {"platform": "FixItLab SIEM", "version": "2.4"},
        "assets": [
            {"name": "web01", "ip": "10.0.0.11", "risk": "medium", "quarantined": False},
            {"name": "db01", "ip": "10.0.0.12", "risk": "high", "quarantined": False},
            {"name": "ws-finance-07", "ip": "10.0.5.42", "risk": "critical", "quarantined": False},
        ],
        "alerts": [
            {"id": "AL-1001", "title": "Suspicious PowerShell execution", "severity": "high",
             "asset": "ws-finance-07", "status": "new", "acknowledged": False, "source_ip": "203.0.113.55"},
            {"id": "AL-1002", "title": "Multiple failed SSH logins", "severity": "medium",
             "asset": "web01", "status": "new", "acknowledged": False, "source_ip": "198.51.100.23"},
            {"id": "AL-1003", "title": "Outbound connection to known C2 domain", "severity": "critical",
             "asset": "ws-finance-07", "status": "new", "acknowledged": False, "source_ip": "203.0.113.55"},
        ],
        "incidents": [],
        "playbooks": [
            {"id": "pb-malware-contain", "name": "Malware Containment", "steps": ["Isolate host", "Collect forensics", "Remove artifact"]},
            {"id": "pb-brute-force", "name": "Brute Force Response", "steps": ["Block source IP", "Force password reset", "Review auth logs"]},
            {"id": "pb-phishing", "name": "Phishing Response", "steps": ["Disable mailbox", "Purge messages", "Reset credentials"]},
        ],
        "blocked_ips": [],
        "iocs": [
            {"type": "ip", "value": "203.0.113.55", "threat": "C2", "confidence": "high"},
            {"type": "domain", "value": "evil-c2.example", "threat": "C2", "confidence": "high"},
            {"type": "hash", "value": "a1b2c3d4e5f67890", "threat": "malware", "confidence": "medium"},
        ],
        "detection_rules": [
            {"id": "rule-ps1", "name": "Encoded PowerShell", "enabled": True, "severity": "high"},
            {"id": "rule-ssh-bf", "name": "SSH Brute Force", "enabled": True, "severity": "medium"},
            {"id": "rule-dns-tunnel", "name": "DNS Tunneling", "enabled": False, "severity": "high"},
        ],
        "cases": [],
        "log_index": [
            {"time": "2026-07-16T10:02:11Z", "host": "ws-finance-07", "message": "powershell.exe -enc <base64> spawned by winword.exe", "source": "EDR"},
            {"time": "2026-07-16T10:02:15Z", "host": "ws-finance-07", "message": "Outbound TCP 443 to 203.0.113.55 (known C2)", "source": "Firewall"},
            {"time": "2026-07-16T09:58:02Z", "host": "web01", "message": "Failed password for root from 198.51.100.23", "source": "sshd"},
            {"time": "2026-07-16T09:58:03Z", "host": "web01", "message": "Failed password for root from 198.51.100.23", "source": "sshd"},
            {"time": "2026-07-16T09:58:04Z", "host": "web01", "message": "Failed password for admin from 198.51.100.23", "source": "sshd"},
        ],
        "activity_log": [],
        "goal": {"title": "SOC triage lab", "objective": "Triage the critical C2 alert: acknowledge it, escalate to an incident, quarantine the host, and close it."},
        "broken": {"open_critical_alert": "AL-1003"},
        "events": [],
        **seed_v2(),
    }


def _apply_preset(state: dict, slug: str) -> None:
    slug = (slug or "").lower()
    if "red-vs-blue" in slug or "red-blue" in slug or "dual-containment" in slug or "multi-vector" in slug:
        # Checked FIRST so a red-vs-blue slug never gets misrouted into the
        # single-fix quarantine/block branches below.
        state["goal"] = {
            "title": "Contain the multi-vector intrusion",
            "objective": "The attacker used two footholds at once: quarantine ws-finance-07 AND block "
                         "the brute-force source IP 198.51.100.23 — clearing only one leaves the other "
                         "vector open.",
        }
        state["broken"] = {"needs_quarantine": "ws-finance-07", "needs_block_ip": "198.51.100.23"}
    elif "quarantine" in slug or "malware" in slug or "c2" in slug:
        state["goal"] = {"title": "Contain malware", "objective": "Acknowledge AL-1003, run the containment playbook, and quarantine ws-finance-07."}
        state["broken"] = {"open_critical_alert": "AL-1003", "needs_quarantine": "ws-finance-07"}
    elif "brute" in slug or "ssh" in slug or "block" in slug:
        state["goal"] = {"title": "Stop brute force", "objective": "Acknowledge AL-1002 and block the attacking source IP."}
        state["broken"] = {"open_alert": "AL-1002", "needs_block_ip": "198.51.100.23"}
    elif "escalate" in slug or "incident" in slug:
        state["goal"] = {"title": "Escalate incident", "objective": "Escalate AL-1003 into a formal incident for tracking."}
        state["broken"] = {"needs_escalation": "AL-1003"}
    elif "playbook" in slug or "respond" in slug:
        state["goal"] = {"title": "Run response playbook", "objective": "Run the malware containment playbook against ws-finance-07."}
        state["broken"] = {"needs_playbook": "pb-malware-contain"}
    elif "search" in slug or "hunt" in slug or "log" in slug:
        state["goal"] = {"title": "Threat hunt", "objective": "Search the logs for the attacker source IP and confirm activity."}
        state["broken"] = {"needs_log_search": "203.0.113.55"}
    elif "close" in slug or "resolve" in slug:
        state["goal"] = {"title": "Close incident", "objective": "Close out the open incident after remediation."}
        state["broken"] = {"open_critical_alert": "AL-1003"}


def _ensure(session_id: str, slug: str = "") -> dict:
    entry = _load(session_id)
    if entry is None:
        state = _base_state()
        _apply_preset(state, slug)
        entry = {"session_id": str(session_id), "scenario_slug": slug, "state": state}
        _save(session_id, entry)
    return entry


_ensure_session = _ensure


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure(session_id, scenario_slug)
    keys_before = set(entry["state"].keys())
    ensure_v2(entry["state"])
    if set(entry["state"].keys()) != keys_before:
        _save(session_id, entry)
    state = copy.deepcopy(entry["state"])
    try:
        from apps.labs.provisioner.simulation.server_identity import sync_soc_assets
        sync_soc_assets(session_id, state.get("assets") or [])
    except Exception:
        pass
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "state": state,
        "goal": state.get("goal", {}),
        "events": state.get("events", []),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def _find_alert(state: dict, alert_id: str) -> dict | None:
    return next((a for a in state.get("alerts", []) if a.get("id") == alert_id), None)


def _find_incident(state: dict, incident_id: str) -> dict | None:
    return next((i for i in state.get("incidents", []) if i.get("id") == incident_id), None)


def _find_asset(state: dict, name: str) -> dict | None:
    return next((a for a in state.get("assets", []) if a.get("name") == name), None)


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load(session_id)
    if not entry:
        return {"ok": False, "error": "SOC session not found"}
    state = entry["state"]
    broken = state.get("broken") or {}

    if action == "login":
        state["session"] = {"logged_in": True, "user": payload.get("user") or "analyst"}
        _event(state, "Signed in to SOC console", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Logged in"}

    if not state.get("session", {}).get("logged_in"):
        return {"ok": False, "error": "Sign in to the SOC console first"}

    if action == "acknowledge_alert":
        alert_id = payload.get("alert_id") or broken.get("open_critical_alert") or broken.get("open_alert") or ""
        alert = _find_alert(state, alert_id)
        if not alert:
            return {"ok": False, "error": f"Alert {alert_id} not found"}
        alert["acknowledged"] = True
        alert["status"] = "acknowledged"
        _event(state, f"Alert {alert_id} acknowledged", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Alert acknowledged"}

    if action == "escalate_incident":
        alert_id = payload.get("alert_id") or broken.get("needs_escalation") or broken.get("open_critical_alert") or ""
        alert = _find_alert(state, alert_id)
        if not alert:
            return {"ok": False, "error": f"Alert {alert_id} not found"}
        inc_id = f"INC-{len(state.get('incidents', [])) + 1001}"
        state.setdefault("incidents", []).append({
            "id": inc_id, "title": alert.get("title"), "alert_id": alert_id,
            "asset": alert.get("asset"), "severity": alert.get("severity"), "status": "open",
        })
        alert["status"] = "escalated"
        broken.pop("needs_escalation", None)
        _event(state, f"Alert {alert_id} escalated to incident {inc_id}", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Escalated to incident", "incident_id": inc_id}

    if action == "run_playbook":
        pb_id = payload.get("playbook_id") or broken.get("needs_playbook") or "pb-malware-contain"
        playbook = next((p for p in state.get("playbooks", []) if p.get("id") == pb_id), None)
        if not playbook:
            return {"ok": False, "error": f"Playbook {pb_id} not found"}
        broken.pop("needs_playbook", None)
        _event(state, f"Playbook {playbook['name']} executed", "success")
        _save(session_id, entry)
        return {"ok": True, "message": f"Playbook {playbook['name']} executed", "steps": playbook.get("steps", [])}

    if action == "quarantine_host":
        name = payload.get("asset") or broken.get("needs_quarantine") or "ws-finance-07"
        asset = _find_asset(state, name)
        if not asset:
            return {"ok": False, "error": f"Asset {name} not found"}
        asset["quarantined"] = True
        broken.pop("needs_quarantine", None)
        _event(state, f"Host {name} quarantined from network", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.chaos_engine import inject as _chaos_inject
            _chaos_inject(session_id, "drop_nic", name, detail={"console": "soc", "reason": "quarantined"})
        except Exception:  # pragma: no cover
            pass
        try:
            from apps.labs.provisioner.simulation import soc_bridge
            soc_bridge.record_quarantine(str(session_id), name)
        except Exception:
            pass
        return {"ok": True, "message": "Host quarantined"}

    if action == "block_ip":
        ip = payload.get("ip") or broken.get("needs_block_ip") or ""
        if not ip:
            return {"ok": False, "error": "IP address is required"}
        if ip not in state.setdefault("blocked_ips", []):
            state["blocked_ips"].append(ip)
        broken.pop("needs_block_ip", None)
        _event(state, f"IP {ip} blocked at the firewall", "success")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation import soc_bridge
            soc_bridge.record_block_ip(str(session_id), ip)
        except Exception:
            pass
        return {"ok": True, "message": f"IP {ip} blocked"}

    if action == "search_logs":
        query = (payload.get("query") or "").strip()
        rows = state.get("log_index", []) or []
        if not query:
            return {"ok": False, "error": "Enter a search query", "results": []}
        try:
            results = run_soc_query(rows, query)
        except SocQueryError as exc:
            # Fail closed: a malformed query returns nothing and cannot clear
            # the hunt objective, otherwise garbage input would pass the lab.
            _event(state, f"Log search rejected: '{query}' ({exc})", "warning")
            _save(session_id, entry)
            return {
                "ok": False,
                "error": f"Search syntax error: {exc}",
                "results": [],
                "query": query,
            }
        target = broken.get("needs_log_search")
        if target and _hunt_query_isolates_target(rows, results, str(target)):
            broken.pop("needs_log_search", None)
        _event(state, f"Log search: '{query}' ({len(results)} results)", "info")
        _save(session_id, entry)
        return {
            "ok": True,
            "message": f"{len(results)} log entries found",
            "results": results,
            "query": query,
        }

    if action == "close_incident":
        inc_id = payload.get("incident_id") or ""
        alert_id = payload.get("alert_id") or broken.get("open_critical_alert") or broken.get("open_alert") or ""
        incident = _find_incident(state, inc_id) if inc_id else next(
            (i for i in state.get("incidents", []) if i.get("alert_id") == alert_id), None
        )
        alert = _find_alert(state, alert_id) if alert_id else None
        if incident:
            incident["status"] = "closed"
        if alert:
            alert["status"] = "closed"
            if broken.get("open_critical_alert") == alert_id:
                broken.pop("open_critical_alert", None)
            if broken.get("open_alert") == alert_id:
                broken.pop("open_alert", None)
        if not incident and not alert:
            return {"ok": False, "error": "Incident or alert not found"}
        _event(state, f"Incident/alert {inc_id or alert_id} closed", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Closed"}

    if action == "add_ioc":
        ioc_type = payload.get("type") or "ip"
        value = (payload.get("value") or "").strip()
        if not value:
            return {"ok": False, "error": "IOC value required"}
        state.setdefault("iocs", []).insert(0, {
            "type": ioc_type, "value": value,
            "threat": payload.get("threat") or "custom", "confidence": payload.get("confidence") or "medium",
        })
        _event(state, f"IOC added: {ioc_type}={value}", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "IOC added"}

    if action == "enable_rule":
        rule_id = payload.get("rule_id") or "rule-dns-tunnel"
        rule = next((r for r in state.get("detection_rules", []) if r.get("id") == rule_id), None)
        if not rule:
            return {"ok": False, "error": f"Rule {rule_id} not found"}
        rule["enabled"] = True
        _event(state, f"Detection rule {rule['name']} enabled", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Rule enabled"}

    if action == "disable_rule":
        rule_id = payload.get("rule_id") or ""
        rule = next((r for r in state.get("detection_rules", []) if r.get("id") == rule_id), None)
        if not rule:
            return {"ok": False, "error": f"Rule {rule_id} not found"}
        rule["enabled"] = False
        _event(state, f"Detection rule {rule['name']} disabled", "warning")
        _save(session_id, entry)
        return {"ok": True, "message": "Rule disabled"}

    if action == "enrich_alert":
        alert_id = payload.get("alert_id") or ""
        alert = _find_alert(state, alert_id)
        if not alert:
            return {"ok": False, "error": f"Alert {alert_id} not found"}
        matched = [i for i in state.get("iocs", []) if i.get("value") == alert.get("source_ip")]
        alert["enriched"] = True
        alert["ioc_matches"] = matched
        _event(state, f"Alert {alert_id} enriched ({len(matched)} IOC matches)", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Alert enriched", "matches": matched}

    if action == "unquarantine_host":
        name = payload.get("asset") or ""
        asset = _find_asset(state, name)
        if not asset:
            return {"ok": False, "error": f"Asset {name} not found"}
        asset["quarantined"] = False
        _event(state, f"Host {name} released from quarantine", "info")
        _save(session_id, entry)
        try:
            from apps.labs.provisioner.simulation.chaos_engine import clear_faults as _chaos_clear
            _chaos_clear(session_id, fault_type="drop_nic", target=name)
        except Exception:  # pragma: no cover
            pass
        return {"ok": True, "message": "Host unquarantined"}

    if action == "create_case":
        title = payload.get("title") or "Investigation case"
        case_id = f"CASE-{len(state.get('cases', [])) + 1001}"
        state.setdefault("cases", []).append({
            "id": case_id, "title": title, "status": "open",
            "alert_id": payload.get("alert_id") or "", "created": _now_iso(),
        })
        _event(state, f"Case {case_id} opened", "info")
        _save(session_id, entry)
        return {"ok": True, "message": "Case created", "case_id": case_id}

    if action == "create_detection_rule":
        name = (payload.get("name") or f"Custom Rule {len(state.get('detection_rules') or []) + 1}").strip()
        rule_id = payload.get("id") or f"rule-{name.lower().replace(' ', '-')[:24]}"
        if any(r.get("id") == rule_id or r.get("name") == name for r in state.get("detection_rules") or []):
            return {"ok": False, "error": f"Rule '{name}' already exists"}
        rule = {
            "id": rule_id,
            "name": name,
            "enabled": bool(payload.get("enabled", True)),
            "severity": payload.get("severity") or "medium",
        }
        state.setdefault("detection_rules", []).append(rule)
        _event(state, f"Detection rule {name} created", "success")
        _save(session_id, entry)
        return {"ok": True, "message": "Rule created", "rule": rule}

    if action == "unblock_ip":
        ip = payload.get("ip") or ""
        if ip in state.get("blocked_ips", []):
            state["blocked_ips"] = [x for x in state["blocked_ips"] if x != ip]
            _event(state, f"IP {ip} unblocked", "info")
            _save(session_id, entry)
            return {"ok": True, "message": f"IP {ip} unblocked"}
        return {"ok": False, "error": f"IP {ip} is not blocked"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or action, "success")
            _save(session_id, entry)
        return v2

    return {"ok": False, "error": f"Unknown action: {action}"}


# Per-key grader feedback. The broken dict stores bare targets (an alert id, a
# hostname, an IP), not the human-readable reasons azure_engine stores, so each
# template names the unmet objective and interpolates only the target.
_BROKEN_REASONS: dict[str, str] = {
    "open_critical_alert": "critical alert {target} is still open — triage and close it",
    "open_alert": "alert {target} is still open — triage and close it",
    "needs_escalation": "alert {target} has not been escalated yet",
    "needs_quarantine": "host {target} has not been quarantined yet",
    "needs_block_ip": "IP {target} has not been blocked yet",
    "needs_playbook": "playbook {target} has not been run yet",
    "needs_log_search": "the logs have not been searched for {target} yet",
}


def _describe_broken(broken: dict) -> str:
    """Name every outstanding objective, not just the first.

    Several SOC presets seed two keys at once (quarantine + block IP), so
    reporting only next(iter(...)) would hide half the work still remaining.
    """
    parts = []
    for kind, target in broken.items():
        template = _BROKEN_REASONS.get(kind)
        if template is None:
            # Unknown key: still fail CLOSED, and name the key so a missing
            # template surfaces as a reportable gap rather than a silent pass.
            parts.append(f"unresolved objective ({kind})")
        else:
            parts.append(template.format(target=target))
    return "; ".join(parts)


def validate_soc_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load(session_id)
    if not entry:
        return False, "No SOC session"
    broken = entry["state"].get("broken") or {}
    if broken:
        return False, f"SOC lab not complete: {_describe_broken(broken)}"
    return True, "SOC lab objectives met"
