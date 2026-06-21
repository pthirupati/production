"""
In-memory Grafana + Prometheus monitoring simulator for training labs.

Replicates a realistic observability stack so a learner can open an in-app
Grafana-like UI (dashboards, panels, template variables, alert rules, contact
points, datasources) and a Prometheus/PromQL UI (targets, query box returning
mock series, recording/alerting rules, Alertmanager routing).

This engine renders the *UI* and lets the learner inspect/diagnose the fault.
Scenario completion is graded independently through the standard fail-closed
file-marker recipe (check.sh `grep -q FIXED-OK <file>` + scenario_presets.py),
so the simulator never auto-passes a lab. The `apply_action` hook lets the UI
re-derive panel/target/alert health from the *real* repaired config when a
scenario's fix has been applied, but health here is cosmetic — it does not feed
the validation engine.

No external Grafana/Prometheus process is required; everything is mock state in
the Django cache (Redis in production) for multi-worker safety.
"""

from __future__ import annotations

import copy
import json
import math
import random
import re
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL matching VMware/K8s/Docker sessions

# Sessions stored in Django cache. Two personas share one engine + state:
#   - "grafana"     → Grafana-first UI (dashboards/panels/alerts)
#   - "prometheus"  → Prometheus-first UI (targets/PromQL/rules)
# The state object carries BOTH so a Grafana lab can still show its datasource's
# Prometheus targets, and a Prometheus lab can still render a dashboard preview.


def _session_key(session_id: str) -> str:
    return f"monitoring_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now() -> float:
    return time.time()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Mock time-series generation + a small PromQL evaluator
# ---------------------------------------------------------------------------

# Base series families the simulated Prometheus "scrapes". Each is a function of
# (label-set, t) so the same query is stable within a session but still wiggles.
_INSTANCES = ["node-1:9100", "node-2:9100", "node-3:9100"]
_JOBS = {
    "node": _INSTANCES,
    "prometheus": ["localhost:9090"],
    "blackbox": ["https://api.example.com", "https://www.example.com"],
    "api-server": ["api-1:8080", "api-2:8080"],
}


def _seeded(label: str, base: float, spread: float, t: float, period: float = 300.0) -> float:
    """Deterministic-ish sample for a label at time t."""
    phase = (abs(hash(label)) % 1000) / 1000.0 * math.tau
    wobble = math.sin(t / period + phase) * spread
    jitter = (((int(t) // 15 + abs(hash(label))) % 17) - 8) / 8.0 * (spread * 0.3)
    return round(base + wobble + jitter, 4)


def _series_for_metric(metric: str, broken: dict, t: float) -> list[dict]:
    """Return a list of {metric:{...labels}, value:[t, "v"]} for a base metric."""
    out: list[dict] = []
    no_data_metrics = set(broken.get("no_data_metrics") or [])
    high_card = broken.get("high_cardinality_metric")

    def emit(labels: dict, value: float) -> None:
        out.append({"metric": {"__name__": metric, **labels}, "value": [t, str(value)]})

    if metric in no_data_metrics:
        return []  # scenario: this metric returns no data

    if metric == "up":
        down = set(broken.get("targets_down") or [])
        for job, instances in _JOBS.items():
            for inst in instances:
                val = 0 if inst in down else 1
                emit({"job": job, "instance": inst}, val)
    elif metric == "node_cpu_seconds_total":
        for inst in _INSTANCES:
            for mode in ("idle", "user", "system", "iowait"):
                emit({"instance": inst, "job": "node", "mode": mode},
                     _seeded(f"{inst}{mode}", 1000 + 200, 50, t) + t / 10)
    elif metric == "node_memory_MemAvailable_bytes":
        for inst in _INSTANCES:
            emit({"instance": inst, "job": "node"},
                 _seeded(inst + "mem", 4.2e9, 4e8, t))
    elif metric == "node_memory_MemTotal_bytes":
        for inst in _INSTANCES:
            emit({"instance": inst, "job": "node"}, 8.0e9)
    elif metric == "node_filesystem_avail_bytes":
        for inst in _INSTANCES:
            for mp in ("/", "/var"):
                base = 5e9 if mp == "/" else 2e9
                emit({"instance": inst, "job": "node", "mountpoint": mp, "fstype": "ext4"},
                     _seeded(inst + mp, base, 3e8, t))
    elif metric == "node_filesystem_size_bytes":
        for inst in _INSTANCES:
            for mp in ("/", "/var"):
                emit({"instance": inst, "job": "node", "mountpoint": mp, "fstype": "ext4"},
                     50e9 if mp == "/" else 20e9)
    elif metric in ("http_requests_total", "http_request_duration_seconds_count"):
        codes = ["200", "200", "200", "500", "404"]
        for inst in _JOBS["api-server"]:
            for code in set(codes):
                emit({"instance": inst, "job": "api-server", "code": code,
                      "handler": "/api/v1/orders"},
                     _seeded(f"{inst}{code}", 5000 if code == "200" else 120, 80, t) + t / 4)
        if high_card == metric:
            # Scenario: an unbounded label (user_id) explodes the series count.
            for i in range(40):
                emit({"instance": "api-1:8080", "job": "api-server", "code": "200",
                      "user_id": f"u{10000 + i}"}, _seeded(f"u{i}", 3, 2, t))
    elif metric == "probe_success":
        down = set(broken.get("targets_down") or [])
        for inst in _JOBS["blackbox"]:
            emit({"instance": inst, "job": "blackbox"}, 0 if inst in down else 1)
    elif metric == "probe_duration_seconds":
        for inst in _JOBS["blackbox"]:
            emit({"instance": inst, "job": "blackbox"}, _seeded(inst + "probe", 0.35, 0.1, t))
    elif metric == "prometheus_tsdb_head_series":
        base = 1.2e6 if high_card else 2.4e5
        emit({"instance": "localhost:9090", "job": "prometheus"}, base + t)
    elif metric == "scrape_duration_seconds":
        for job, instances in _JOBS.items():
            for inst in instances:
                emit({"job": job, "instance": inst}, _seeded(inst + "scrape", 0.08, 0.03, t))
    else:
        # Unknown metric — emit a single generic series so panels still draw.
        emit({"instance": "node-1:9100", "job": "node"}, _seeded(metric, 42, 8, t))
    return out


_RANGE_RE = re.compile(r"\[(\d+)([smhd])\]")
_FUNC_RE = re.compile(r"^(\w+)\((.*)\)$", re.DOTALL)
_AGG_RE = re.compile(r"^(sum|avg|min|max|count|topk|bottomk)\s*(?:by\s*\(([^)]*)\))?\s*\((.*)\)$", re.DOTALL)
_SELECTOR_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?")


def _parse_selector_labels(label_str: str) -> dict:
    labels: dict[str, str] = {}
    for part in re.findall(r'(\w+)\s*=~?\s*"([^"]*)"', label_str or ""):
        labels[part[0]] = part[1]
    return labels


def _matches(series_labels: dict, want: dict) -> bool:
    for k, v in want.items():
        if k == "__name__":
            continue
        if series_labels.get(k) != v:
            return False
    return True


def _strip_outer_parens(q: str) -> str:
    q = q.strip()
    while q.startswith("(") and q.endswith(")"):
        depth = 0
        balanced = True
        for i, ch in enumerate(q):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(q) - 1:
                    balanced = False
                    break
        if balanced:
            q = q[1:-1].strip()
        else:
            break
    return q


def _split_top_binop(q: str):
    """Find the last top-level binary operator (lowest precedence first:
    +,- then *,/ then comparisons). Returns (left, op, right) or None.
    Quotes and brackets are respected so labels/ranges aren't split."""
    # Operator groups from lowest to highest binding so we split lowest first.
    for ops in (("==", "!=", ">=", "<=", ">", "<"), ("+", "-"), ("*", "/", "%")):
        depth = 0
        in_str = False
        i = len(q) - 1
        while i >= 0:
            ch = q[i]
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch in ")}]":
                    depth += 1
                elif ch in "({[":
                    depth -= 1
                elif depth == 0:
                    for op in ops:
                        if q[i:i + len(op)] == op and i + len(op) <= len(q):
                            # Avoid matching '-' inside a metric/label or a unary minus at start.
                            left = q[:i].strip()
                            right = q[i + len(op):].strip()
                            if left and right and not left.endswith(tuple("=!<>+*/%-")):
                                return left, op, right
            i -= 1
    return None


def _as_scalar(s: str):
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def eval_promql(query: str, broken: dict, t: float | None = None) -> dict:
    """A pragmatic PromQL evaluator: instant vectors, label filters, a few
    functions (rate/irate/increase pass-through, histogram-free), the common
    aggregations (sum/avg/min/max/count, optional `by`), scalar arithmetic
    (expr +-*/ scalar) and comparison filters (expr > N → keep matching samples).
    Returns Prometheus-style result JSON. This is intentionally a teaching
    approximation, not a real engine."""
    t = t if t is not None else _now()
    q = _strip_outer_parens((query or "").strip())
    if not q:
        return {"status": "error", "error": "empty query", "data": {"resultType": "vector", "result": []}}

    # Binary operations: scalar arithmetic and comparison filters. Handled before
    # functions/aggregations so dashboard exprs like
    #   100 - (avg by(instance)(rate(...)) * 100)
    #   sum(rate(http_requests_total{code="500"}[5m])) / sum(rate(...[5m])) > 0.05
    # evaluate instead of erroring.
    binop = _split_top_binop(q)
    if binop:
        left, op, right = binop
        lscalar = _as_scalar(left)
        rscalar = _as_scalar(right)
        comparators = {">": (lambda a, b: a > b), "<": (lambda a, b: a < b),
                       ">=": (lambda a, b: a >= b), "<=": (lambda a, b: a <= b),
                       "==": (lambda a, b: a == b), "!=": (lambda a, b: a != b)}
        arith = {"+": (lambda a, b: a + b), "-": (lambda a, b: a - b),
                 "*": (lambda a, b: a * b), "/": (lambda a, b: a / b if b else 0.0),
                 "%": (lambda a, b: a % b if b else 0.0)}

        # vector OP scalar (most common) — apply elementwise.
        if rscalar is not None and lscalar is None:
            res = eval_promql(left, broken, t)
            rows = res.get("data", {}).get("result", [])
            out = []
            for r in rows:
                v = float(r["value"][1])
                if op in comparators:
                    if comparators[op](v, rscalar):
                        out.append(r)  # comparison keeps matching samples
                else:
                    out.append({"metric": r["metric"], "value": [t, str(round(arith[op](v, rscalar), 4))]})
            return {"status": "success", "data": {"resultType": "vector", "result": out}}

        # scalar OP vector — e.g. 100 - (...).
        if lscalar is not None and rscalar is None:
            res = eval_promql(right, broken, t)
            rows = res.get("data", {}).get("result", [])
            out = []
            for r in rows:
                v = float(r["value"][1])
                if op in arith:
                    out.append({"metric": r["metric"], "value": [t, str(round(arith[op](lscalar, v), 4))]})
                elif comparators[op](lscalar, v):
                    out.append(r)
            return {"status": "success", "data": {"resultType": "vector", "result": out}}

        # vector OP vector — align by identical label sets, ignoring __name__
        # (so node_filesystem_avail_bytes{...} / node_filesystem_size_bytes{...}
        # matches on instance/mountpoint/fstype).
        def _match_key(labels: dict) -> tuple:
            return tuple(sorted((k, v) for k, v in labels.items() if k != "__name__"))
        lres = eval_promql(left, broken, t).get("data", {}).get("result", [])
        rres = eval_promql(right, broken, t).get("data", {}).get("result", [])
        rindex = {_match_key(r["metric"]): float(r["value"][1]) for r in rres}
        out = []
        for lr in lres:
            key = _match_key(lr["metric"])
            rv = rindex.get(key)
            if rv is None and len(rres) == 1:
                rv = float(rres[0]["value"][1])  # broadcast single right-hand scalar-vector
            if rv is None:
                continue
            lv = float(lr["value"][1])
            if op in arith:
                out.append({"metric": lr["metric"], "value": [t, str(round(arith[op](lv, rv), 4))]})
            elif comparators[op](lv, rv):
                out.append(lr)
        return {"status": "success", "data": {"resultType": "vector", "result": out}}

    # Strip an outer function call we treat as identity over the inner selector
    # (rate, irate, increase, sum_over_time, avg_over_time, rate of counters…).
    m = _AGG_RE.match(q)
    if m:
        agg, by_labels, inner = m.group(1), m.group(2), m.group(3)
        inner_res = eval_promql(inner, broken, t)
        rows = inner_res.get("data", {}).get("result", [])
        by = [b.strip() for b in (by_labels or "").split(",") if b.strip()]
        groups: dict[tuple, list[float]] = {}
        group_labels: dict[tuple, dict] = {}
        for r in rows:
            labels = r["metric"]
            key = tuple(labels.get(b, "") for b in by) if by else ("__all__",)
            groups.setdefault(key, []).append(float(r["value"][1]))
            if key not in group_labels:
                group_labels[key] = {b: labels.get(b, "") for b in by}
        result = []
        for key, vals in groups.items():
            if agg == "sum":
                v = sum(vals)
            elif agg == "avg":
                v = sum(vals) / len(vals)
            elif agg == "min":
                v = min(vals)
            elif agg == "max":
                v = max(vals)
            else:  # count / topk / bottomk → count-ish
                v = len(vals)
            result.append({"metric": group_labels[key], "value": [t, str(round(v, 4))]})
        return {"status": "success", "data": {"resultType": "vector", "result": result}}

    fm = _FUNC_RE.match(q)
    if fm and fm.group(1) in (
        "rate", "irate", "increase", "sum_over_time", "avg_over_time",
        "max_over_time", "min_over_time", "delta", "deriv", "histogram_quantile",
        "abs", "ceil", "floor", "round",
    ):
        inner = fm.group(2)
        # histogram_quantile(0.95, ...) — drop the quantile arg.
        if fm.group(1) == "histogram_quantile" and "," in inner:
            inner = inner.split(",", 1)[1]
        inner = _RANGE_RE.sub("", inner).strip()
        res = eval_promql(inner, broken, t)
        # rate() of a counter → scale down so values look like per-second rates.
        if fm.group(1) in ("rate", "irate", "deriv", "delta"):
            for r in res.get("data", {}).get("result", []):
                r["value"][1] = str(round(float(r["value"][1]) / 60.0, 4))
        return res

    # Plain selector: metric{labels}
    sm = _SELECTOR_RE.match(q)
    if not sm:
        return {"status": "error", "error": f"could not parse query: {q}",
                "data": {"resultType": "vector", "result": []}}
    metric = sm.group(1)
    want = _parse_selector_labels(sm.group(2) or "")
    series = _series_for_metric(metric, broken, t)
    result = [s for s in series if _matches(s["metric"], want)]
    return {"status": "success", "data": {"resultType": "vector", "result": result}}


# ---------------------------------------------------------------------------
# Base inventory (Grafana + Prometheus)
# ---------------------------------------------------------------------------

def _panel(pid: int, title: str, ptype: str, expr: str, unit: str = "short", **kw) -> dict:
    return {"id": pid, "title": title, "type": ptype, "datasource": "Prometheus",
            "expr": expr, "unit": unit, "gridPos": kw.get("gridPos", {"w": 12, "h": 8}),
            "thresholds": kw.get("thresholds", [])}


def _base_inventory() -> dict:
    return {
        "grafana": {
            "version": "10.4.2",
            "org": "FixitLab",
            "datasources": [
                {"uid": "prom-default", "name": "Prometheus", "type": "prometheus",
                 "url": "http://prometheus:9090", "access": "proxy", "is_default": True,
                 "status": "ok", "message": "Data source is working"},
                {"uid": "loki-default", "name": "Loki", "type": "loki",
                 "url": "http://loki:3100", "access": "proxy", "is_default": False,
                 "status": "ok", "message": "Data source is working"},
            ],
            "folders": [
                {"uid": "fldr-infra", "title": "Infrastructure"},
                {"uid": "fldr-apps", "title": "Applications"},
            ],
            "dashboards": [
                {
                    "uid": "node-overview", "title": "Node Exporter / Overview",
                    "folder": "Infrastructure", "tags": ["node", "infra"],
                    "templating": [
                        {"name": "instance", "type": "query", "label": "Instance",
                         "query": "label_values(node_cpu_seconds_total, instance)",
                         "current": "node-1:9100",
                         "options": _INSTANCES, "multi": False},
                        {"name": "job", "type": "query", "label": "Job",
                         "query": "label_values(up, job)", "current": "node",
                         "options": list(_JOBS.keys()), "multi": False},
                    ],
                    "panels": [
                        _panel(1, "CPU Busy", "timeseries",
                               '100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle",instance="$instance"}[5m])) * 100)',
                               unit="percent"),
                        _panel(2, "Memory Available", "timeseries",
                               'node_memory_MemAvailable_bytes{instance="$instance"}', unit="bytes"),
                        _panel(3, "Root FS Available", "stat",
                               'node_filesystem_avail_bytes{instance="$instance",mountpoint="/"}', unit="bytes"),
                        _panel(4, "Targets Up", "stat", 'sum(up{job="$job"})', unit="short"),
                    ],
                },
                {
                    "uid": "api-slo", "title": "API / SLO",
                    "folder": "Applications", "tags": ["api", "slo"],
                    "templating": [
                        {"name": "handler", "type": "custom", "label": "Handler",
                         "query": "/api/v1/orders", "current": "/api/v1/orders",
                         "options": ["/api/v1/orders"], "multi": False},
                    ],
                    "panels": [
                        _panel(1, "Request Rate", "timeseries",
                               'sum by(code)(rate(http_requests_total[5m]))', unit="reqps"),
                        _panel(2, "Error Ratio", "gauge",
                               'sum(rate(http_requests_total{code="500"}[5m])) / sum(rate(http_requests_total[5m]))',
                               unit="percentunit",
                               thresholds=[{"value": 0.01, "color": "yellow"},
                                           {"value": 0.05, "color": "red"}]),
                        _panel(3, "p95 Latency", "timeseries",
                               'histogram_quantile(0.95, sum by(le)(rate(http_request_duration_seconds_bucket[5m])))',
                               unit="s"),
                    ],
                },
            ],
            "alert_rules": [
                {"uid": "rule-target-down", "title": "TargetDown",
                 "folder": "Infrastructure", "group": "availability",
                 "condition": 'up == 0', "for": "5m", "severity": "critical",
                 "state": "Normal", "contact_point": "ops-pager",
                 "datasource": "Prometheus", "no_data_state": "NoData"},
                {"uid": "rule-high-error", "title": "HighErrorRate",
                 "folder": "Applications", "group": "slo",
                 "condition": 'sum(rate(http_requests_total{code="500"}[5m])) / sum(rate(http_requests_total[5m])) > 0.05',
                 "for": "10m", "severity": "warning", "state": "Normal",
                 "contact_point": "slack-alerts", "datasource": "Prometheus",
                 "no_data_state": "NoData"},
            ],
            "contact_points": [
                {"name": "ops-pager", "type": "pagerduty", "configured": True,
                 "address": "routing-key-***"},
                {"name": "slack-alerts", "type": "slack", "configured": True,
                 "address": "https://hooks.slack.com/services/***"},
                {"name": "grafana-default-email", "type": "email", "configured": True,
                 "address": "oncall@example.com"},
            ],
            "notification_policies": {
                "root": {"receiver": "grafana-default-email", "group_by": ["alertname"],
                         "routes": [
                             {"match": {"severity": "critical"}, "receiver": "ops-pager"},
                             {"match": {"severity": "warning"}, "receiver": "slack-alerts"},
                         ]},
            },
        },
        "prometheus": {
            "version": "2.51.0",
            "scrape_interval": "15s",
            "evaluation_interval": "15s",
            "targets": [
                {"job": "node", "instance": i, "health": "up", "scrape_url": f"http://{i}/metrics",
                 "last_scrape": _now_iso(), "scrape_duration_ms": 42, "labels": {"job": "node"}}
                for i in _INSTANCES
            ] + [
                {"job": "prometheus", "instance": "localhost:9090", "health": "up",
                 "scrape_url": "http://localhost:9090/metrics", "last_scrape": _now_iso(),
                 "scrape_duration_ms": 8, "labels": {"job": "prometheus"}},
                {"job": "blackbox", "instance": "https://api.example.com", "health": "up",
                 "scrape_url": "http://blackbox:9115/probe?target=https://api.example.com",
                 "last_scrape": _now_iso(), "scrape_duration_ms": 310, "labels": {"job": "blackbox"}},
                {"job": "api-server", "instance": "api-1:8080", "health": "up",
                 "scrape_url": "http://api-1:8080/metrics", "last_scrape": _now_iso(),
                 "scrape_duration_ms": 21, "labels": {"job": "api-server"}},
                {"job": "api-server", "instance": "api-2:8080", "health": "up",
                 "scrape_url": "http://api-2:8080/metrics", "last_scrape": _now_iso(),
                 "scrape_duration_ms": 23, "labels": {"job": "api-server"}},
            ],
            "recording_rules": [
                {"group": "node.rules", "name": "instance:node_cpu:rate5m",
                 "expr": 'sum by(instance)(rate(node_cpu_seconds_total{mode!="idle"}[5m]))',
                 "health": "ok", "interval": "15s"},
                {"group": "api.rules", "name": "job:http_requests:rate5m",
                 "expr": 'sum by(job)(rate(http_requests_total[5m]))',
                 "health": "ok", "interval": "15s"},
            ],
            "alerting_rules": [
                {"group": "availability", "name": "TargetDown", "expr": "up == 0",
                 "for": "5m", "labels": {"severity": "critical"},
                 "annotations": {"summary": "{{ $labels.instance }} is down"},
                 "state": "inactive", "health": "ok"},
                {"group": "slo", "name": "HighErrorRate",
                 "expr": 'sum(rate(http_requests_total{code="500"}[5m])) / sum(rate(http_requests_total[5m])) > 0.05',
                 "for": "10m", "labels": {"severity": "warning"},
                 "annotations": {"summary": "Error budget burning"},
                 "state": "inactive", "health": "ok"},
            ],
            "alertmanager": {
                "url": "http://alertmanager:9093",
                "route": {"receiver": "team-pager", "group_by": ["alertname", "cluster"],
                          "group_wait": "30s", "group_interval": "5m", "repeat_interval": "4h",
                          "routes": [
                              {"match": {"severity": "critical"}, "receiver": "team-pager"},
                              {"match": {"severity": "warning"}, "receiver": "team-slack"},
                          ]},
                "receivers": [
                    {"name": "team-pager", "type": "pagerduty", "configured": True},
                    {"name": "team-slack", "type": "slack", "configured": True},
                ],
                "silences": [],
                "inhibit_rules": [],
            },
            "remote_write": [],
            "federation": {"enabled": False, "match": []},
            "tsdb": {"head_series": 240000, "wal_corruptions": 0, "retention": "15d"},
        },
        # Scenario-driven broken state (consumed by the mock series generator and
        # surfaced as banners/badges in the UI). Cosmetic — completion is graded
        # by check.sh, NOT by clearing these flags.
        "broken": {
            "summary": "",
            "targets_down": [],
            "no_data_metrics": [],
            "high_cardinality_metric": None,
            "panels_no_data": [],
            "alert_misrouted": False,
        },
        "fix_applied": False,
    }


# ---------------------------------------------------------------------------
# Scenario presets (cosmetic broken state for the UI). Keyed by token in slug.
# ---------------------------------------------------------------------------

def _apply_preset(state: dict, slug: str) -> None:
    s = (slug or "").lower()
    broken = state["broken"]
    graf = state["grafana"]
    prom = state["prometheus"]

    # Datasource misconfig — Grafana datasource fails the health check.
    if "datasource" in s or "no-data" in s or "nodata" in s:
        broken["summary"] = "Prometheus datasource health check failing; panels show 'No data'."
        ds = next((d for d in graf["datasources"] if d["type"] == "prometheus"), None)
        if ds and ("datasource" in s):
            ds["status"] = "error"
            ds["message"] = "Error reading Prometheus: dial tcp: lookup prometheus-wrong on 10.0.0.10:53: no such host"
        broken["no_data_metrics"] = ["node_cpu_seconds_total", "node_memory_MemAvailable_bytes",
                                     "http_requests_total", "up"]
        broken["panels_no_data"] = [1, 2, 3, 4]

    # Target/exporter down.
    if "target-down" in s or "exporter-down" in s or "node-exporter" in s or "scrape-fail" in s:
        broken["summary"] = "A scrape target is DOWN (up == 0); dependent panels and alerts affected."
        broken["targets_down"] = ["node-2:9100"]
        for tgt in prom["targets"]:
            if tgt["instance"] == "node-2:9100":
                tgt["health"] = "down"
                tgt["last_error"] = "connection refused"

    if "blackbox" in s or "probe" in s:
        broken["summary"] = broken["summary"] or "Blackbox probe failing (probe_success == 0)."
        broken["targets_down"] = list(set(broken["targets_down"]) | {"https://api.example.com"})
        for tgt in prom["targets"]:
            if tgt["instance"] == "https://api.example.com":
                tgt["health"] = "down"
                tgt["last_error"] = "probe failed: 500"

    # High cardinality / TSDB pressure.
    if "cardinality" in s or "high-card" in s or "label-explosion" in s:
        broken["summary"] = "High cardinality: an unbounded label is exploding the series count."
        broken["high_cardinality_metric"] = "http_requests_total"
        prom["tsdb"]["head_series"] = 1_200_000

    # Alert flapping / misrouted / wrong contact point.
    if "flap" in s or "alert" in s or "contact-point" in s or "routing" in s or "silence" in s:
        broken["summary"] = broken["summary"] or "Alert misconfigured — wrong contact point / route / for-duration."
        broken["alert_misrouted"] = True
        if "contact-point" in s:
            cp = next((c for c in graf["contact_points"] if c["name"] == "slack-alerts"), None)
            if cp:
                cp["configured"] = False
                cp["address"] = ""
        for r in graf["alert_rules"]:
            if "flap" in s and r["uid"] == "rule-high-error":
                r["for"] = "0s"  # no for-duration → flapping
                r["state"] = "Alerting"

    # Recording rule broken.
    if "recording-rule" in s or "recording" in s:
        broken["summary"] = broken["summary"] or "Recording rule failing to evaluate."
        for rr in prom["recording_rules"]:
            if rr["name"] == "instance:node_cpu:rate5m":
                rr["health"] = "err"
                rr["last_error"] = "parse error: unexpected character"

    # Remote-write / federation.
    if "remote-write" in s or "remote_write" in s:
        broken["summary"] = broken["summary"] or "remote_write endpoint unreachable; samples backing up."
        prom["remote_write"] = [{"url": "https://mimir:8080/api/v1/push", "health": "down",
                                 "last_error": "context deadline exceeded", "queue_pending": 84210}]
    if "federation" in s or "federate" in s:
        broken["summary"] = broken["summary"] or "Federation scrape misconfigured (match[] empty)."
        prom["federation"] = {"enabled": True, "match": []}

    # Default catch-all so a slug we didn't special-case still presents a fault.
    if not broken["summary"]:
        broken["summary"] = "Investigate the monitoring stack: inspect datasources, targets, panels, and alert rules to find the misconfiguration."


def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = _base_inventory()
        _apply_preset(state, scenario_slug)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    state = copy.deepcopy(entry["state"])
    graf = state["grafana"]
    prom = state["prometheus"]
    broken = state["broken"]
    summary = {
        "datasources_total": len(graf["datasources"]),
        "datasources_failing": sum(1 for d in graf["datasources"] if d.get("status") == "error"),
        "dashboards_total": len(graf["dashboards"]),
        "alert_rules_total": len(graf["alert_rules"]),
        "alerts_firing": sum(1 for r in graf["alert_rules"] if r.get("state") == "Alerting"),
        "targets_total": len(prom["targets"]),
        "targets_down": sum(1 for t in prom["targets"] if t.get("health") == "down"),
        "recording_rules_total": len(prom["recording_rules"]),
        "alerting_rules_total": len(prom["alerting_rules"]),
        "head_series": prom["tsdb"]["head_series"],
        "high_cardinality": bool(broken.get("high_cardinality_metric")),
        "fix_applied": state.get("fix_applied", False),
        "fault_summary": broken.get("summary", ""),
    }
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "grafana": graf,
        "prometheus": prom,
        "broken": broken,
        "summary": summary,
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    """Interactive UI actions. The headline action is `query` (PromQL). Other
    actions let the learner toggle inspection state. None of these grade the
    lab — completion is gated by check.sh — but they make the simulator feel real."""
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Monitoring simulation session not found"}
    state = entry["state"]
    broken = state["broken"]

    if action == "query":
        expr = payload.get("expr", "") or payload.get("query", "")
        res = eval_promql(expr, broken)
        return {"ok": True, "query": expr, "result": res}

    if action == "test_datasource":
        uid = payload.get("uid")
        ds = next((d for d in state["grafana"]["datasources"] if d["uid"] == uid), None)
        if not ds:
            return {"ok": False, "error": "datasource not found"}
        return {"ok": True, "status": ds.get("status", "ok"), "message": ds.get("message", "")}

    if action == "silence_alert":
        # Add an Alertmanager silence (cosmetic — alerts still defined).
        am = state["prometheus"]["alertmanager"]
        am.setdefault("silences", []).append({
            "id": f"sil-{int(_now())}", "matchers": payload.get("matchers", []),
            "comment": payload.get("comment", "silenced from sim"),
            "created_by": "lab_grafana", "ends_at": _now_iso(),
        })
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Silence created"}

    if action == "mark_fix_applied":
        # The Linux/terminal fix step (rewriting the broken config + FIXED-OK)
        # is what actually grades the lab. The UI may call this so panels redraw
        # healthy AFTER the learner reports they fixed the config — purely visual.
        state["fix_applied"] = True
        broken["targets_down"] = []
        broken["no_data_metrics"] = []
        broken["high_cardinality_metric"] = None
        broken["panels_no_data"] = []
        broken["alert_misrouted"] = False
        for d in state["grafana"]["datasources"]:
            d["status"] = "ok"
            d["message"] = "Data source is working"
        for t in state["prometheus"]["targets"]:
            t["health"] = "up"
            t.pop("last_error", None)
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Simulator refreshed to healthy state"}

    return {"ok": False, "error": f"unknown action: {action}"}
