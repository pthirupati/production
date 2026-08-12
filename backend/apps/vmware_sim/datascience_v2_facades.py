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


def _row_matches_where(row: dict, col: str, op: str, lit: str, num_lit: float | None) -> bool:
    val = row.get(col)
    if num_lit is not None:
        try:
            v = float(val)
        except (TypeError, ValueError):
            return False
        if op == "=":
            return v == num_lit
        if op in ("!=", "<>"):
            return v != num_lit
        if op == ">":
            return v > num_lit
        if op == "<":
            return v < num_lit
        if op == ">=":
            return v >= num_lit
        if op == "<=":
            return v <= num_lit
        return False
    sval = "" if val is None else str(val)
    if op == "=":
        return sval == str(lit)
    if op in ("!=", "<>"):
        return sval != str(lit)
    return False


def _parse_where(sql: str) -> tuple[str, str, str, float | None] | None:
    import re

    wh = re.search(
        r"\bWHERE\s+(\w+)\s*(=|!=|<>|>=|<=|>|<)\s*(?:'([^']*)'|\"([^\"]*)\"|(-?\d+(?:\.\d+)?))",
        sql,
        re.I,
    )
    if not wh:
        return None
    col, op = wh.group(1), wh.group(2)
    lit = wh.group(3) if wh.group(3) is not None else (
        wh.group(4) if wh.group(4) is not None else wh.group(5)
    )
    num_lit = None
    try:
        num_lit = float(lit)
    except (TypeError, ValueError):
        pass
    return col, op, lit, num_lit


def _apply_join(sql: str, cols: list, rows: list, tables: dict | None) -> tuple[list, list] | None:
    """INNER JOIN primary rows with dataset.tables[name] (or self-join).

    Supports: FROM t [a] JOIN other [b] ON a.col = b.col
    Output columns are prefixed with left_/right_ aliases when both sides share names.
    """
    import re

    tables = tables or {}
    jm = re.search(
        r"\bJOIN\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?\s+ON\s+"
        r"(?:(\w+)\.)?(\w+)\s*=\s*(?:(\w+)\.)?(\w+)",
        sql,
        re.I,
    )
    if not jm:
        return None
    right_name = jm.group(1)
    right_alias = (jm.group(2) or right_name).lower()
    left_col, right_col = jm.group(4), jm.group(6)

    if right_name in tables:
        r_meta = tables[right_name] or {}
        right_rows = list(r_meta.get("rows") or [])
        right_cols = list(r_meta.get("columns") or (right_rows[0].keys() if right_rows else []))
    else:
        # Self-join against the primary dataset
        right_rows = list(rows)
        right_cols = list(cols)

    joined: list[dict] = []
    for left in rows:
        lv = left.get(left_col)
        for right in right_rows:
            if right.get(right_col) != lv:
                continue
            out: dict = {}
            for c in cols:
                out[f"left_{c}" if c in right_cols else c] = left.get(c)
            for c in right_cols:
                out[f"{right_alias}_{c}" if c in cols else c] = right.get(c)
            joined.append(out)
    if joined:
        out_cols = list(joined[0].keys())
    else:
        out_cols = [
            *(f"left_{c}" if c in right_cols else c for c in cols),
            *(f"{right_alias}_{c}" if c in cols else c for c in right_cols),
        ]
    return joined, out_cols


def _apply_group_by(sql: str, work: list, cols: list) -> tuple[list, list] | None:
    """GROUP BY col with COUNT(*) / SUM(col) / AVG(col)."""
    import re

    gb = re.search(r"\bGROUP\s+BY\s+(\w+)", sql, re.I)
    if not gb:
        return None
    gcol = gb.group(1)
    buckets: dict[Any, list] = {}
    for r in work:
        buckets.setdefault(r.get(gcol), []).append(r)

    sel = re.search(r"\bSELECT\s+(.+?)\s+FROM\b", sql, re.I | re.S)
    if not sel:
        sel = re.search(r"\bSELECT\s+(.+?)(?:\s+GROUP\s+BY|\s+ORDER\s+BY|\s+LIMIT|$)", sql, re.I | re.S)
    raw = (sel.group(1) if sel else "*").strip()
    parts = [p.strip() for p in raw.split(",")]

    result = []
    for key, group in buckets.items():
        row: dict = {gcol: key}
        for part in parts:
            low = part.lower()
            if low in ("*", gcol.lower()) or part.strip("`'\"") == gcol:
                row[gcol] = key
                continue
            cm = re.match(r"count\s*\(\s*\*\s*\)(?:\s+as\s+(\w+))?", low)
            if cm:
                row[cm.group(1) or "count"] = len(group)
                continue
            sm = re.match(r"(sum|avg|min|max)\s*\(\s*(\w+)\s*\)(?:\s+as\s+(\w+))?", low)
            if sm:
                fn, col, alias = sm.group(1), sm.group(2), sm.group(3)
                nums = []
                for g in group:
                    try:
                        nums.append(float(g.get(col)))
                    except (TypeError, ValueError):
                        pass
                label = alias or f"{fn}_{col}"
                if not nums:
                    row[label] = None
                elif fn == "sum":
                    row[label] = sum(nums)
                elif fn == "avg":
                    row[label] = sum(nums) / len(nums)
                elif fn == "min":
                    row[label] = min(nums)
                elif fn == "max":
                    row[label] = max(nums)
                continue
            # bare column — take first in group
            col = part.strip("`'\"").split()[0]
            if col.lower() != gcol.lower() and col in (cols or []):
                row[col] = group[0].get(col)
        if len(row) == 1 and gcol in row:
            row["count"] = len(group)
        result.append(row)
    out_cols = list(result[0].keys()) if result else [gcol, "count"]
    return result, out_cols


def _safe_ident(name: str, fallback: str = "col") -> str:
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", str(name or fallback))
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned[:64]


def _run_sql_sqlite(
    sql: str, cols: list, rows: list, tables: dict | None = None,
) -> tuple[list, str]:
    """Execute learner SQL via stdlib sqlite3 over the in-memory dataset.

    Primary table is registered as ``t`` (and ``dataset``). Extra tables from
    ``dataset.tables`` are created by name. Falls through to the façade parser
    on sqlite errors so labs keep working for the supported mini-dialect.
    """
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row

    def _load(name: str, columns: list, data: list) -> None:
        cols_local = list(columns) or (
            list(data[0].keys()) if data and isinstance(data[0], dict) else []
        )
        if not cols_local:
            con.execute(f'CREATE TABLE "{_safe_ident(name)}" (id INTEGER)')
            return
        idents = [_safe_ident(c, f"c{i}") for i, c in enumerate(cols_local)]
        # Keep original→ident map for inserts
        colmap = list(zip(cols_local, idents))
        ddl = ", ".join(f'"{i}" TEXT' for i in idents)
        tname = _safe_ident(name)
        con.execute(f'CREATE TABLE "{tname}" ({ddl})')
        placeholders = ", ".join("?" for _ in idents)
        insert = f'INSERT INTO "{tname}" VALUES ({placeholders})'
        for row in data:
            con.execute(insert, [None if row.get(c) is None else str(row.get(c)) for c, _ in colmap])

    _load("t", cols, rows)
    _load("dataset", cols, rows)
    for tname, meta in (tables or {}).items():
        meta = meta or {}
        _load(str(tname), meta.get("columns") or [], meta.get("rows") or [])

    cur = con.execute(sql)
    fetched = cur.fetchmany(50)
    if not fetched:
        # DDL / empty SELECT
        if cur.description is None:
            return [], "ok (no rows)"
        return [], "0 row(s) returned"
    keys = [d[0] for d in cur.description]
    result = [dict(zip(keys, row)) for row in fetched]
    # Prefer native types where values look numeric
    for row in result:
        for k, v in list(row.items()):
            if isinstance(v, str):
                try:
                    if "." in v:
                        row[k] = float(v)
                    else:
                        row[k] = int(v)
                except ValueError:
                    pass
    return result, f"{len(result)} row(s) returned"


def _parse_sql(sql: str, cols: list, rows: list, tables: dict | None = None) -> tuple[list, str]:
    """Minimal SQL-over-dataset evaluator (SELECT / WHERE / JOIN / GROUP BY / ORDER / LIMIT).

    Not a full SQL engine — enough that different queries yield different outputs
    so the SQL editor is gradeable teaching surface rather than a COUNT stub.
    """
    import re

    upper = sql.upper()
    work = list(rows)
    project = list(cols)

    joined = _apply_join(sql, cols, rows, tables)
    if joined is not None:
        work, project = joined

    wh = _parse_where(sql)
    if wh:
        col, op, lit, num_lit = wh
        work = [r for r in work if _row_matches_where(r, col, op, lit, num_lit)]

    grouped = _apply_group_by(sql, work, project)
    if grouped is not None:
        work, project = grouped
    elif re.search(r"\bCOUNT\s*\(", upper) or re.search(r"\bCOUNT\s+\*", upper):
        return [{"count": len(work)}], f"count = {len(work)}"
    else:
        sel = re.search(r"\bSELECT\s+(.+?)\s+FROM\b", sql, re.I | re.S)
        if not sel:
            sel = re.search(r"\bSELECT\s+(.+)$", sql, re.I | re.S)
        if sel:
            raw = sel.group(1).strip()
            if "*" not in raw and "COUNT" not in raw.upper():
                wanted = [c.strip().strip("`'\"") for c in raw.split(",")]
                project = [c for c in wanted if c in project] or list(project)

    ob = re.search(r"\bORDER\s+BY\s+(\w+)(?:\s+(ASC|DESC))?", sql, re.I)
    if ob:
        col, direction = ob.group(1), (ob.group(2) or "ASC").upper()
        reverse = direction == "DESC"

        def _key(row: dict):
            v = row.get(col)
            return (v is None, v)

        try:
            work = sorted(work, key=_key, reverse=reverse)
        except TypeError:
            work = sorted(work, key=lambda r: str(r.get(col) or ""), reverse=reverse)

    lim = re.search(r"\bLIMIT\s+(\d+)", sql, re.I)
    if lim:
        work = work[: int(lim.group(1))]
    else:
        work = work[:50]

    result = [{c: r.get(c) for c in project} for r in work]
    return result, f"{len(result)} row(s) returned"


def execute_dataset_sql(
    sql: str, cols: list, rows: list, tables: dict | None = None,
) -> tuple[list, str]:
    """Prefer real sqlite3; fall back to the mini façade parser."""
    try:
        return _run_sql_sqlite(sql, cols, rows, tables=tables)
    except Exception:  # noqa: BLE001 — façade covers teaching dialect
        return _parse_sql(sql, cols, rows, tables=tables)


def _looks_like_pandas(src: str) -> bool:
    low = (src or "").lower()
    return (
        "import pandas" in low
        or "from pandas" in low
        or "pd." in (src or "")
        or "dataframe" in low
    )


def _run_pandas_notebook_cell(src: str, cols: list, rows: list) -> dict:
    """Execute a notebook cell against a pandas shim seeded with the dataset."""
    import re
    from apps.labs.pandas_shim import PANDAS_SHIM_SOURCE

    g: dict = {"__name__": "__notebook__"}
    exec(PANDAS_SHIM_SOURCE, g)  # noqa: S102 — shim source is ours
    pd = g["pd"]
    data = {c: [r.get(c) for r in rows] for c in cols}
    df = pd.DataFrame(data)
    g["pd"] = pd
    g["df"] = df
    cleaned_lines = []
    for ln in (src or "").splitlines():
        if re.match(r"^\s*import\s+pandas\b", ln):
            continue
        if re.match(r"^\s*from\s+pandas\b", ln):
            continue
        cleaned_lines.append(ln)
    cleaned = "\n".join(cleaned_lines).strip() or "df.head()"
    # Capture trailing expression result when present.
    lines = cleaned.splitlines()
    result_obj = None
    if lines:
        body, last = "\n".join(lines[:-1]), lines[-1]
        if body.strip():
            exec(compile(body, "<notebook>", "exec"), g)  # noqa: S102
        try:
            result_obj = eval(compile(last, "<notebook>", "eval"), g)  # noqa: S307
        except SyntaxError:
            exec(compile(last, "<notebook>", "exec"), g)  # noqa: S102
            result_obj = g.get("df")
    if hasattr(result_obj, "to_dicts"):
        return {"type": "table", "rows": result_obj.to_dicts()[:20]}
    if hasattr(result_obj, "shape") and not isinstance(result_obj, (str, bytes)):
        return {"type": "text", "text": str(result_obj.shape)}
    if isinstance(result_obj, str):
        return {"type": "text", "text": result_obj}
    if result_obj is None:
        return {"type": "text", "text": f"ok · df{getattr(g.get('df'), 'shape', '')}"}
    return {"type": "text", "text": str(result_obj)[:500]}


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
        tables = ds.get("tables") or {}
        try:
            result_rows, message = execute_dataset_sql(sql, cols, rows, tables=tables)
        except Exception as exc:  # noqa: BLE001 — surface as query error
            return {"ok": False, "error": f"SQL error: {exc}"}
        entry = {
            "id": f"sql-{len(state.get('sql_history') or []) + 1}",
            "sql": sql,
            "at": _now(),
            "rows": len(result_rows),
            "preview": result_rows[:5],
        }
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
        ds = state.get("dataset") or {}
        rows = ds.get("rows") or []
        cols = ds.get("columns") or []
        low = src.lower()
        if _looks_like_pandas(src) and cell.get("type") != "markdown":
            try:
                cell["output"] = _run_pandas_notebook_cell(src, cols, rows)
            except Exception as exc:  # noqa: BLE001
                cell["output"] = {"type": "text", "text": f"pandas error: {exc}"}
        elif "head" in low or "preview" in low:
            cell["output"] = {"type": "table", "rows": preview}
        elif "tail" in low:
            cell["output"] = {"type": "table", "rows": rows[-5:]}
        elif "shape" in low or ("len(" in low and "df" in low):
            cell["output"] = {
                "type": "text",
                "text": f"({len(rows)}, {len(cols)})",
            }
        elif "columns" in low or "dtypes" in low:
            cell["output"] = {"type": "text", "text": ", ".join(str(c) for c in cols)}
        elif "describe" in low or "mean(" in low or "median(" in low:
            stats = []
            for c in cols:
                nums = []
                for r in rows:
                    try:
                        nums.append(float(r.get(c)))
                    except (TypeError, ValueError):
                        pass
                if nums:
                    avg = sum(nums) / len(nums)
                    stats.append(f"{c}: mean={avg:.3g} n={len(nums)}")
            cell["output"] = {
                "type": "text",
                "text": "\n".join(stats) if stats else "No numeric columns",
            }
        elif "value_counts" in low:
            # value_counts on first categorical-ish column mentioned, else first col
            target = cols[0] if cols else None
            for c in cols:
                if c in src:
                    target = c
                    break
            counts: dict[str, int] = {}
            if target:
                for r in rows:
                    k = str(r.get(target))
                    counts[k] = counts.get(k, 0) + 1
            cell["output"] = {
                "type": "table",
                "rows": [{"value": k, "count": v} for k, v in list(counts.items())[:20]],
            }
        elif "iloc" in low or "loc[" in low:
            cell["output"] = {"type": "table", "rows": preview[:1]}
        elif cell.get("type") == "markdown":
            cell["output"] = None
        else:
            cell["output"] = {
                "type": "text",
                "text": f"Executed in Lab Environment · {len(preview)} sample rows",
            }
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
