"""Vendor & dependency reality injects — outages you cannot locally fix.

Four primitives for ops labs: upstream outage, deprecation deadline, breaking
minor bump, expiring license. Correct remediation is escalate / migrate / renew
— not restarting a local service.
"""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


INJECT_KINDS = (
    "upstream_outage",
    "deprecation_deadline",
    "breaking_minor",
    "license_expiry",
)

CORRECT_ACTIONS = {
    "upstream_outage": {"escalate", "failover", "workaround"},
    "deprecation_deadline": {"migrate", "upgrade"},
    "breaking_minor": {"migrate", "pin", "upgrade"},
    "license_expiry": {"renew", "purchase"},
}

WRONG_LOCAL = {"restart", "reboot", "restart-nginx", "systemctl restart", "clear-cache"}


def inject_vendor_event(state: dict, *, kind: str, detail: str | None = None) -> dict:
    kind = (kind or "").strip().lower()
    if kind not in INJECT_KINDS:
        return {"ok": False, "error": f"Unknown kind {kind}", "kinds": list(INJECT_KINDS)}
    event = {
        "id": f"VND-{kind[:3].upper()}-{int(time.time()) % 100000:05d}",
        "kind": kind,
        "detail": detail or {
            "upstream_outage": "Cloud DNS provider 5xx — local nginx healthy",
            "deprecation_deadline": "API v1 sunset in 14 days",
            "breaking_minor": "SDK 3.2 removes Client.do(); use Client.execute()",
            "license_expiry": "Enterprise license expires in 48h",
        }[kind],
        "status": "open",
        "injected_at": _now(),
        "resolved_by": None,
    }
    events = state.setdefault("vendor_events", [])
    events.insert(0, event)
    state.setdefault("broken", {})["vendor_dependency"] = kind
    return {"ok": True, "event": event}


def remediate_vendor_event(state: dict, *, event_id: str, action: str) -> dict:
    action_l = (action or "").strip().lower()
    events = state.get("vendor_events") or []
    event = next((e for e in events if e.get("id") == event_id), None)
    if not event:
        return {"ok": False, "error": f"Event {event_id} not found"}
    if event.get("status") == "resolved":
        return {"ok": False, "error": "Already resolved"}
    kind = event.get("kind")
    if action_l in WRONG_LOCAL or action_l.replace("_", " ") in WRONG_LOCAL:
        return {
            "ok": False,
            "error": "Local restart cannot fix an upstream vendor issue — escalate, migrate, or renew",
            "event": event,
        }
    allowed = CORRECT_ACTIONS.get(kind) or set()
    if action_l not in allowed and action_l.replace("-", "_") not in allowed:
        return {
            "ok": False,
            "error": f"Action {action!r} is not valid for {kind}; try one of {sorted(allowed)}",
            "event": event,
        }
    event["status"] = "resolved"
    event["resolved_by"] = action_l
    event["resolved_at"] = _now()
    broken = state.get("broken") or {}
    if broken.get("vendor_dependency") == kind:
        broken.pop("vendor_dependency", None)
    return {"ok": True, "event": event, "message": f"Resolved via {action_l}"}
