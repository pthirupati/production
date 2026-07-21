"""Data Science V2 facades — notebooks, SQL queries, cleaning pipeline.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "notebooks": [
            {
                "id": "nb-main",
                "title": "Lab notebook",
                "cells": [
                    {"id": "c1", "type": "markdown", "source": "# Lab Environment notebook\nExplore the dataset, then build the dashboard."},
                    {"id": "c2", "type": "code", "source": "df.head()", "output": None},
                ],
            }
        ],
        "sql_history": [],
        "cleaning_steps": [],
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, list) else list(value)


def _preview_rows(state: dict, limit: int = 5) -> list[dict]:
    ds = state.get("dataset") or {}
    rows = ds.get("rows") or []
    return rows[:limit]


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action == "run_sql":
        sql = (payload.get("sql") or payload.get("query") or "").strip()
        if not sql:
            return {"ok": False, "error": "SQL query required"}
        ds = state.get("dataset") or {}
        cols = ds.get("columns") or []
        rows = ds.get("rows") or []
        # Minimal SELECT * / COUNT(*) lab stub — enough for UI feedback
        upper = sql.upper()
        result_rows = []
        message = "Query executed"
        if "COUNT" in upper:
            result_rows = [{"count": len(rows)}]
            message = f"count = {len(rows)}"
        else:
            # Project first N columns if SELECT lists them, else all
            result_rows = [{c: r.get(c) for c in cols} for r in rows[:20]]
            message = f"{len(result_rows)} row(s) returned"
        entry = {"id": f"sql-{len(state.get('sql_history') or []) + 1}", "sql": sql, "at": _now(), "rows": len(result_rows), "preview": result_rows[:5]}
        state.setdefault("sql_history", []).append(entry)
        state["sql_history"] = state["sql_history"][-30:]
        return {"ok": True, "message": message, "result": entry, "preview": result_rows[:10]}

    if action == "add_clean_step":
        op = (payload.get("op") or payload.get("operation") or "drop_nulls").strip()
        column = payload.get("column") or ""
        step = {
            "id": f"cl-{len(state.get('cleaning_steps') or []) + 1}",
            "op": op,
            "column": column,
            "at": _now(),
            "status": "applied",
        }
        state.setdefault("cleaning_steps", []).append(step)
        # Soft-mutate preview: drop nulls in column if present
        ds = state.get("dataset") or {}
        rows = ds.get("rows") or []
        if op == "drop_nulls" and column:
            before = len(rows)
            ds["rows"] = [r for r in rows if r.get(column) not in (None, "", "null")]
            step["rows_removed"] = before - len(ds["rows"])
        elif op == "fill_nulls" and column:
            fill = payload.get("value") or "0"
            for r in rows:
                if r.get(column) in (None, "", "null"):
                    r[column] = fill
            step["filled"] = True
        elif op == "rename_column" and column and payload.get("to"):
            new = payload["to"]
            cols = ds.get("columns") or []
            if column in cols:
                ds["columns"] = [new if c == column else c for c in cols]
                for r in rows:
                    if column in r:
                        r[new] = r.pop(column)
            step["to"] = new
        return {"ok": True, "message": f"Cleaning step '{op}' applied", "step": step}

    if action == "add_notebook_cell":
        nb_id = payload.get("notebook_id") or "nb-main"
        nb = next((n for n in state.get("notebooks") or [] if n.get("id") == nb_id), None)
        if not nb:
            return {"ok": False, "error": "Notebook not found"}
        cell = {
            "id": f"c{len(nb.get('cells') or []) + 1}",
            "type": payload.get("type") or "code",
            "source": payload.get("source") or "# new cell",
            "output": None,
        }
        nb.setdefault("cells", []).append(cell)
        return {"ok": True, "message": "Cell added", "cell": cell}

    if action == "run_notebook_cell":
        nb_id = payload.get("notebook_id") or "nb-main"
        cell_id = payload.get("cell_id") or ""
        nb = next((n for n in state.get("notebooks") or [] if n.get("id") == nb_id), None)
        if not nb:
            return {"ok": False, "error": "Notebook not found"}
        cell = next((c for c in nb.get("cells") or [] if c.get("id") == cell_id), None)
        if not cell:
            return {"ok": False, "error": "Cell not found"}
        src = (cell.get("source") or "").strip()
        preview = _preview_rows(state, 5)
        if "head" in src or "preview" in src.lower():
            cell["output"] = {"type": "table", "rows": preview}
        elif "shape" in src or "len" in src:
            n = len((state.get("dataset") or {}).get("rows") or [])
            cell["output"] = {"type": "text", "text": f"({n}, {len((state.get('dataset') or {}).get('columns') or [])})"}
        elif cell.get("type") == "markdown":
            cell["output"] = None
        else:
            cell["output"] = {"type": "text", "text": f"Executed in Lab Environment · {len(preview)} sample rows"}
        cell["ran_at"] = _now()
        return {"ok": True, "message": "Cell executed", "cell": cell}

    return None


def v2_public(state: dict) -> dict:
    ensure_v2(state)
    return {
        "notebooks": state.get("notebooks") or [],
        "sql_history": (state.get("sql_history") or [])[-10:],
        "cleaning_steps": state.get("cleaning_steps") or [],
    }
