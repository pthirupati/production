"""
In-memory Data Science / Analytics DASHBOARD simulator for training labs.

Models a tabular dataset (a list of row dicts, like a CSV loaded into a BI tool)
and a *dashboard* the learner builds on top of it. The learner picks a dimension
(the group-by column), a measure (the numeric column), an aggregation
(sum | avg | count | min | max), an optional filter, and a chart type
(bar | line | table | pie). The engine recomputes the resulting aggregated series
on every action and stores it in session state so the UI can render a chart +
result table without any client-side number-crunching.

Each scenario carries a `goal` describing the dashboard the learner must build
(e.g. "revenue by region, summed, as a bar chart"). `validate_datascience_lab`
passes only when the dashboard the learner actually built matches every field of
the goal (dimension, measure, aggregation, filter, chart type) AND the computed
series matches the expected aggregated numbers. A fresh session (nothing built
yet) always fails; only the intended configuration flips it to pass.

Sessions live in the Django cache (Redis in production) for multi-worker safety,
mirroring the VMware / K8s / Docker / monitoring / nmap / wireshark engines
(SESSION_TTL=7200). No pandas/numpy — pure stdlib aggregation so the grader
sandbox (and this engine) stay dependency-free.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

from .datascience_v2_facades import apply_v2_action, ensure_v2, v2_public

SESSION_TTL = 7200  # 2-hour TTL matching the other simulator engines

_AGGREGATIONS = ("sum", "avg", "count", "min", "max")
_CHART_TYPES = ("bar", "line", "table", "pie")


def _session_key(session_id: str) -> str:
    return f"datascience_session:{session_id}"


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
# Datasets + scenario presets
# ---------------------------------------------------------------------------

def _sales_rows() -> list[dict]:
    """Regional sales transactions. Used by the revenue-by-region scenario."""
    return [
        {"region": "North", "product": "Widget", "channel": "Online", "revenue": 1200, "units": 30},
        {"region": "North", "product": "Gadget", "channel": "Retail", "revenue": 800, "units": 16},
        {"region": "South", "product": "Widget", "channel": "Online", "revenue": 500, "units": 12},
        {"region": "South", "product": "Gadget", "channel": "Retail", "revenue": 300, "units": 6},
        {"region": "East", "product": "Widget", "channel": "Online", "revenue": 900, "units": 22},
        {"region": "East", "product": "Gadget", "channel": "Retail", "revenue": 1100, "units": 25},
        {"region": "West", "product": "Widget", "channel": "Online", "revenue": 700, "units": 18},
        {"region": "West", "product": "Gadget", "channel": "Online", "revenue": 400, "units": 9},
    ]


def _exam_rows() -> list[dict]:
    """Student exam scores. Used by the avg-not-sum scenario (averaging scores,
    not summing them, is the only meaningful aggregation)."""
    return [
        {"subject": "Math", "student": "Ann", "term": "Fall", "score": 90, "credits": 4},
        {"subject": "Math", "student": "Ben", "term": "Fall", "score": 70, "credits": 4},
        {"subject": "Math", "student": "Cara", "term": "Spring", "score": 80, "credits": 4},
        {"subject": "Science", "student": "Ann", "term": "Fall", "score": 60, "credits": 3},
        {"subject": "Science", "student": "Ben", "term": "Spring", "score": 100, "credits": 3},
        {"subject": "Science", "student": "Cara", "term": "Spring", "score": 80, "credits": 3},
        {"subject": "History", "student": "Ann", "term": "Spring", "score": 75, "credits": 2},
        {"subject": "History", "student": "Ben", "term": "Fall", "score": 85, "credits": 2},
    ]


def _orders_rows() -> list[dict]:
    """Order line items with a status column. Used by the filter-then-group
    scenario (count completed orders per category, ignoring cancelled ones)."""
    return [
        {"category": "Books", "status": "completed", "amount": 40, "qty": 2},
        {"category": "Books", "status": "completed", "amount": 25, "qty": 1},
        {"category": "Books", "status": "cancelled", "amount": 99, "qty": 3},
        {"category": "Electronics", "status": "completed", "amount": 300, "qty": 1},
        {"category": "Electronics", "status": "cancelled", "amount": 450, "qty": 1},
        {"category": "Electronics", "status": "completed", "amount": 120, "qty": 1},
        {"category": "Electronics", "status": "completed", "amount": 80, "qty": 2},
        {"category": "Toys", "status": "completed", "amount": 30, "qty": 5},
        {"category": "Toys", "status": "cancelled", "amount": 15, "qty": 1},
    ]


# Each preset wires a dataset + a goal. The goal fully specifies the dashboard the
# learner must build; validate_datascience_lab compares the built config + the
# computed series against it.
_PRESETS: dict[str, dict] = {
    "ds-dashboard-revenue-by-region": {
        "title": "Revenue by Region (Bar Chart)",
        "objective": (
            "Build a dashboard that shows total revenue for each region as a bar "
            "chart. Set the dimension to 'region', the measure to 'revenue', the "
            "aggregation to 'sum', and the chart type to 'bar'."
        ),
        "dataset_name": "regional_sales",
        "columns": ["region", "product", "channel", "revenue", "units"],
        "dimensions": ["region", "product", "channel"],
        "measures": ["revenue", "units"],
        "rows": _sales_rows(),
        "goal": {
            "dimension": "region",
            "measure": "revenue",
            "aggregation": "sum",
            "chart_type": "bar",
            "filter": None,
        },
    },
    "ds-dashboard-avg-not-sum": {
        "title": "Average Score by Subject (fix the wrong aggregation)",
        "objective": (
            "An analyst built 'score by subject' but used SUM, which inflates the "
            "numbers and is meaningless for exam scores. Fix the aggregation to "
            "'avg' so the bar chart shows the true average score per subject. Keep "
            "dimension 'subject', measure 'score', chart type 'bar'."
        ),
        "dataset_name": "exam_scores",
        "columns": ["subject", "student", "term", "score", "credits"],
        "dimensions": ["subject", "student", "term"],
        "measures": ["score", "credits"],
        "rows": _exam_rows(),
        # Pre-built (wrong) dashboard: correct dimension/measure/chart, wrong agg.
        "initial_dashboard": {
            "dimension": "subject",
            "measure": "score",
            "aggregation": "sum",
            "chart_type": "bar",
            "filter": None,
        },
        "goal": {
            "dimension": "subject",
            "measure": "score",
            "aggregation": "avg",
            "chart_type": "bar",
            "filter": None,
        },
    },
    "ds-dashboard-filter-then-group": {
        "title": "Completed Order Value by Category (filter then group)",
        "objective": (
            "Sales wants total revenue per product category, but cancelled orders "
            "must be excluded. Filter the data to status = 'completed', then group "
            "by 'category' summing 'amount', shown as a bar chart."
        ),
        "dataset_name": "orders",
        "columns": ["category", "status", "amount", "qty"],
        "dimensions": ["category", "status"],
        "measures": ["amount", "qty"],
        "rows": _orders_rows(),
        "goal": {
            "dimension": "category",
            "measure": "amount",
            "aggregation": "sum",
            "chart_type": "bar",
            "filter": {"column": "status", "value": "completed"},
        },
    },
}


def _default_preset() -> dict:
    """Fallback dataset/goal for an unknown slug — keeps the sim usable and
    grade-able rather than 500-ing."""
    return {
        "title": "Revenue by Region (Bar Chart)",
        "objective": (
            "Build a bar chart of total revenue by region (dimension 'region', "
            "measure 'revenue', aggregation 'sum', chart type 'bar')."
        ),
        "dataset_name": "regional_sales",
        "columns": ["region", "product", "channel", "revenue", "units"],
        "dimensions": ["region", "product", "channel"],
        "measures": ["revenue", "units"],
        "rows": _sales_rows(),
        "goal": {
            "dimension": "region",
            "measure": "revenue",
            "aggregation": "sum",
            "chart_type": "bar",
            "filter": None,
        },
    }


def _preset_for(scenario_slug: str) -> dict:
    return copy.deepcopy(_PRESETS.get(scenario_slug) or _default_preset())


# ---------------------------------------------------------------------------
# Aggregation engine (pure stdlib)
# ---------------------------------------------------------------------------

def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _apply_filter(rows: list[dict], flt: dict | None) -> list[dict]:
    if not flt or not flt.get("column"):
        return list(rows)
    col = flt["column"]
    val = flt.get("value")
    # Compare as strings so "completed" matches and numeric values still work.
    return [r for r in rows if str(r.get(col)) == str(val)]


def _aggregate(rows: list[dict], dimension: str, measure: str, aggregation: str) -> list[dict]:
    """Group `rows` by `dimension` and aggregate `measure`. Returns a list of
    {"label", "value"} buckets sorted by label for stable rendering/comparison.

    `count` ignores the measure (counts rows per group), matching BI tools.
    """
    if not dimension:
        return []
    buckets: dict[str, list[float]] = {}
    order: list[str] = []
    for r in rows:
        label = str(r.get(dimension, ""))
        if label not in buckets:
            buckets[label] = []
            order.append(label)
        if aggregation == "count":
            buckets[label].append(1.0)
        else:
            buckets[label].append(_coerce_number(r.get(measure)))

    series: list[dict] = []
    for label in sorted(order):
        vals = buckets[label]
        if not vals:
            agg_val = 0.0
        elif aggregation == "sum":
            agg_val = sum(vals)
        elif aggregation == "avg":
            agg_val = sum(vals) / len(vals)
        elif aggregation == "count":
            agg_val = float(len(vals))
        elif aggregation == "min":
            agg_val = min(vals)
        elif aggregation == "max":
            agg_val = max(vals)
        else:
            agg_val = sum(vals)
        # Round to 4 dp to avoid float noise; ints stay clean.
        agg_val = round(agg_val, 4)
        if agg_val == int(agg_val):
            agg_val = int(agg_val)
        series.append({"label": label, "value": agg_val})
    return series


def _recompute(state: dict) -> None:
    """Recompute the dashboard's filtered row count + aggregated series from the
    current builder config. Always called after a config change."""
    dash = state["dashboard"]
    rows = state["dataset"]["rows"]
    filtered = _apply_filter(rows, dash.get("filter"))
    dash["filtered_count"] = len(filtered)
    if dash.get("dimension") and (dash.get("aggregation") == "count" or dash.get("measure")):
        dash["series"] = _aggregate(
            filtered,
            dash.get("dimension", ""),
            dash.get("measure", ""),
            dash.get("aggregation") or "sum",
        )
        dash["computed"] = True
    else:
        dash["series"] = []
        dash["computed"] = False


# ---------------------------------------------------------------------------
# Session lifecycle (mirrors the other engines)
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        preset = _preset_for(scenario_slug)
        # Builder dashboard starts empty unless the preset seeds a (deliberately
        # wrong) initial dashboard for a "fix the aggregation" style lab.
        initial = preset.get("initial_dashboard") or {}
        dashboard = {
            "dimension": initial.get("dimension"),
            "measure": initial.get("measure"),
            "aggregation": initial.get("aggregation"),
            "chart_type": initial.get("chart_type") or "table",
            "filter": initial.get("filter"),
            "series": [],
            "filtered_count": 0,
            "computed": False,
        }
        state = {
            "scenario_slug": scenario_slug,
            "dataset": {
                "name": preset["dataset_name"],
                "columns": preset["columns"],
                "dimensions": preset["dimensions"],
                "measures": preset["measures"],
                "rows": preset["rows"],
            },
            "dashboard": dashboard,
            "goal": preset["goal"],
            "title": preset["title"],
            "objective": preset["objective"],
            "events": [],
        }
        _recompute(state)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    ensure_v2(entry["state"])
    _save_session(str(session_id), entry)
    state = copy.deepcopy(entry["state"])
    _recompute(state)
    ds = state["dataset"]
    dash = state["dashboard"]
    goal = state.get("goal", {})
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "title": state.get("title", ""),
        "objective": state.get("objective", ""),
        "dataset": {
            "name": ds["name"],
            "columns": ds["columns"],
            "dimensions": ds["dimensions"],
            "measures": ds["measures"],
            "row_count": len(ds["rows"]),
            # Preview the first rows so the UI can render a dataset table.
            "preview": ds["rows"][:10],
        },
        "dashboard": {
            "dimension": dash.get("dimension"),
            "measure": dash.get("measure"),
            "aggregation": dash.get("aggregation"),
            "chart_type": dash.get("chart_type"),
            "filter": dash.get("filter"),
            "series": dash.get("series", []),
            "filtered_count": dash.get("filtered_count", 0),
            "computed": dash.get("computed", False),
        },
        "aggregations": list(_AGGREGATIONS),
        "chart_types": list(_CHART_TYPES),
        # Surface the human-readable goal (never the expected numbers) so the UI
        # can show the objective without leaking the answer series.
        "goal": {
            "dimension": goal.get("dimension"),
            "measure": goal.get("measure"),
            "aggregation": goal.get("aggregation"),
            "chart_type": goal.get("chart_type"),
            "filter": goal.get("filter"),
        },
        "events": state.get("events", []),
        "summary": {
            "dataset": ds["name"],
            "rows_total": len(ds["rows"]),
            "rows_in_view": dash.get("filtered_count", 0),
            "buckets": len(dash.get("series", [])),
            "dashboard_built": dash.get("computed", False),
            "objective": state.get("objective", ""),
        },
        **v2_public(state),
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def _event(state: dict, message: str) -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message})
    state["events"] = state["events"][:50]


def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    """Build the dashboard.

    Actions:
      set_dimension   {column}   — group-by column
      set_measure     {column}   — numeric column to aggregate
      set_aggregation {aggregation} — sum|avg|count|min|max
      set_filter      {column,value} (omit/empty clears the filter)
      set_chart_type  {chart_type}  — bar|line|table|pie
      reset           — clear the dashboard back to empty

    Every change recomputes the aggregated series. Validation reads the result.
    """
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Data dashboard session not found"}
    state = entry["state"]
    ds = state["dataset"]
    dash = state["dashboard"]

    if action == "set_dimension":
        column = payload.get("column") or payload.get("dimension")
        if column is not None and column not in ds["columns"]:
            return {"ok": False, "error": f"Unknown column '{column}'"}
        dash["dimension"] = column
        _recompute(state)
        _event(state, f"Dimension set to {column or '(none)'}")
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Dimension set to {column or '(none)'}"}

    if action == "set_measure":
        column = payload.get("column") or payload.get("measure")
        if column is not None and column not in ds["columns"]:
            return {"ok": False, "error": f"Unknown column '{column}'"}
        dash["measure"] = column
        _recompute(state)
        _event(state, f"Measure set to {column or '(none)'}")
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Measure set to {column or '(none)'}"}

    if action == "set_aggregation":
        agg = (payload.get("aggregation") or payload.get("agg") or "").lower()
        if agg not in _AGGREGATIONS:
            return {"ok": False,
                    "error": f"Aggregation must be one of {', '.join(_AGGREGATIONS)}"}
        dash["aggregation"] = agg
        _recompute(state)
        _event(state, f"Aggregation set to {agg}")
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Aggregation set to {agg}"}

    if action == "set_filter":
        column = payload.get("column")
        value = payload.get("value")
        if not column or value in (None, ""):
            dash["filter"] = None
            _recompute(state)
            _event(state, "Filter cleared")
            _save_session(str(session_id), entry)
            return {"ok": True, "message": "Filter cleared"}
        if column not in ds["columns"]:
            return {"ok": False, "error": f"Unknown column '{column}'"}
        dash["filter"] = {"column": column, "value": value}
        _recompute(state)
        _event(state, f"Filter set: {column} = {value}")
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Filter set: {column} = {value}",
                "rows_in_view": dash.get("filtered_count", 0)}

    if action == "set_chart_type":
        chart = (payload.get("chart_type") or payload.get("chart") or "").lower()
        if chart not in _CHART_TYPES:
            return {"ok": False,
                    "error": f"Chart type must be one of {', '.join(_CHART_TYPES)}"}
        dash["chart_type"] = chart
        _event(state, f"Chart type set to {chart}")
        _save_session(str(session_id), entry)
        return {"ok": True, "message": f"Chart type set to {chart}"}

    if action == "reset":
        state["dashboard"] = {
            "dimension": None, "measure": None, "aggregation": None,
            "chart_type": "table", "filter": None,
            "series": [], "filtered_count": 0, "computed": False,
        }
        _recompute(state)
        _event(state, "Dashboard reset")
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Dashboard reset"}

    ensure_v2(state)
    v2 = apply_v2_action(state, action, payload)
    if v2 is not None:
        if v2.get("ok"):
            if action == "add_clean_step":
                _recompute(state)
            _event(state, v2.get("message") or action)
            _save_session(str(session_id), entry)
        return v2

    return {"ok": False, "error": f"unknown action: {action}"}


# ---------------------------------------------------------------------------
# Validation — grade on the dashboard the learner actually built
# ---------------------------------------------------------------------------

def _norm_filter(flt: dict | None) -> tuple | None:
    if not flt or not flt.get("column"):
        return None
    return (flt.get("column"), str(flt.get("value")))


def validate_datascience_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    goal = state.get("goal") or {}
    dash = state.get("dashboard") or {}
    ds = state.get("dataset") or {}

    if not goal:
        return False, "No validation goal configured for this scenario"

    # 1. The builder configuration must match the goal exactly.
    if (dash.get("dimension") or None) != (goal.get("dimension") or None):
        return False, (
            f"Dimension is '{dash.get('dimension') or '(none)'}' but the goal needs "
            f"'{goal.get('dimension')}'. Set the group-by column to "
            f"'{goal.get('dimension')}'.")

    goal_agg = goal.get("aggregation")
    if (dash.get("aggregation") or None) != (goal_agg or None):
        return False, (
            f"Aggregation is '{dash.get('aggregation') or '(none)'}' but the goal "
            f"needs '{goal_agg}'. Change the aggregation to '{goal_agg}'.")

    # `count` does not require a measure; every other aggregation does.
    if goal_agg != "count":
        if (dash.get("measure") or None) != (goal.get("measure") or None):
            return False, (
                f"Measure is '{dash.get('measure') or '(none)'}' but the goal needs "
                f"'{goal.get('measure')}'. Set the measure to "
                f"'{goal.get('measure')}'.")

    if (dash.get("chart_type") or None) != (goal.get("chart_type") or None):
        return False, (
            f"Chart type is '{dash.get('chart_type') or '(none)'}' but the goal "
            f"needs a '{goal.get('chart_type')}' chart. Switch the chart type.")

    if _norm_filter(dash.get("filter")) != _norm_filter(goal.get("filter")):
        gf = goal.get("filter")
        if gf:
            return False, (
                f"This dashboard must be filtered to {gf['column']} = "
                f"'{gf['value']}' before grouping. Apply that filter.")
        return False, "Remove the filter — the goal dashboard uses all rows."

    # 2. The computed series must match the expected aggregation of the dataset.
    # Recompute the *expected* series independently from the ground-truth dataset
    # + goal so a learner cannot pass by spoofing series numbers — validation
    # only trusts the engine's own aggregation of the real rows.
    expected = _aggregate(
        _apply_filter(ds.get("rows", []), goal.get("filter")),
        goal.get("dimension", ""),
        goal.get("measure", ""),
        goal_agg or "sum",
    )
    actual = dash.get("series") or []
    if actual != expected:
        return False, (
            "The dashboard is configured correctly but the computed series does "
            "not match the expected result — recheck the filter and aggregation.")

    if not expected:
        return False, "The dashboard produced no data — check the dataset and filter."

    return True, (
        f"Dashboard matches the goal: {goal_agg} of {goal.get('measure') or 'rows'} "
        f"by {goal.get('dimension')} as a {goal.get('chart_type')} chart "
        f"({len(expected)} buckets) — validation passed")
