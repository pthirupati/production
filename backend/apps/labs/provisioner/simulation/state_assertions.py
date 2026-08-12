"""Per-scenario engine state assertions — replace FIXED-OK-only grading (audit G2).

Assertions read the engine's own world model (NetApp SVMs, volumes, etc.) instead
of a planted marker file. Registered by scenario slug; unknown slugs return None
so existing validation paths keep working.
"""

from __future__ import annotations

from typing import Any


# Minimal starter set — expand per-tech as CONTENT migrates check.sh off FIXED-OK.
ASSERTIONS_BY_SLUG: dict[str, list[dict[str, Any]]] = {
    "academy-netapp-001-learn-svm": [
        {
            "engine": "netapp",
            "collection": "svms",
            "match": {"name": "svm-prod"},
            "field": "state",
            "equals": "running",
            "hint": "Ensure svm-prod is running (vserver start / SVM online)",
        },
        {
            "engine": "netapp",
            "collection": "svms",
            "match": {"name": "svm-prod"},
            "field": "protocols",
            "contains": "nfs",
            "hint": "svm-prod must expose NFS among protocols",
        },
    ],
}


def _get_netapp_state(session_id: str) -> dict | None:
    try:
        from apps.vmware_sim import netapp_engine as ne

        payload = ne.get_state(session_id)
        if isinstance(payload, dict):
            return payload.get("state") if "state" in payload else payload
        return None
    except Exception:
        return None


def _collection_rows(state: dict, collection: str) -> list[dict]:
    rows = state.get(collection) or []
    return [r for r in rows if isinstance(r, dict)]


def _match_row(rows: list[dict], match: dict | None) -> dict | None:
    if not match:
        return rows[0] if rows else None
    for row in rows:
        if all(row.get(k) == v for k, v in match.items()):
            return row
    return None


def evaluate_slug_assertions(session_id: str, slug: str) -> tuple[bool, str] | None:
    """Return (ok, message) when slug is registered; else None (caller keeps legacy path)."""
    assertions = ASSERTIONS_BY_SLUG.get((slug or "").strip())
    if not assertions:
        return None

    netapp_state = None
    for raw in assertions:
        engine = (raw.get("engine") or "").lower()
        if engine == "netapp":
            if netapp_state is None:
                netapp_state = _get_netapp_state(session_id)
            if not netapp_state:
                return False, "NetApp engine state unavailable — open the NetApp console first"
            rows = _collection_rows(netapp_state, str(raw.get("collection") or ""))
            row = _match_row(rows, raw.get("match") if isinstance(raw.get("match"), dict) else None)
            if not row:
                return False, raw.get("hint") or f"No matching {raw.get('collection')} row"
            field = raw.get("field") or ""
            actual = row.get(field)
            if "equals" in raw and actual != raw["equals"]:
                return False, raw.get("hint") or f"{field}={actual!r} != {raw['equals']!r}"
            if "contains" in raw:
                needle = raw["contains"]
                if isinstance(actual, (list, tuple, set)):
                    ok = needle in actual
                else:
                    ok = needle in str(actual or "")
                if not ok:
                    return False, raw.get("hint") or f"{field} missing {needle!r}"
        else:
            return False, f"Unknown assertion engine {engine!r}"
    return True, "Lab validation passed (engine state assertions)"
