"""
Public-facing scenario text — symptoms and incident context only.

Fix instructions belong in hints (revealed in the lab runner), not in descriptions,
objectives, or Jira ticket bodies.
"""
from __future__ import annotations

import re

# Leading verbs that turn an objective into a fix step (moved to hints in YAML).
_FIX_VERBS = re.compile(
    r"^\s*(fix|repair|restore|correct|update|edit|change|replace|remove|delete|"
    r"extend|grow|resize|remount|rebuild|add|create|run|execute|use|set|point|"
    r"mount|enable|disable|start|stop|restart|configure|install|apply|chmod|chown|"
    r"uncomment|comment|adjust|reset|clear|free|rebuild|verify|confirm|test with|inspect|compare)\b",
    re.IGNORECASE,
)


def is_fix_instruction(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip()
    if _FIX_VERBS.search(stripped):
        return True
    if "`" in stripped and any(
        kw in stripped.lower()
        for kw in ("run ", "use ", "then ", "command", "chmod", "systemctl", "mount -")
    ):
        return True
    return False


def public_objectives(objectives) -> list[str]:
    """Return objectives that describe outcomes/symptoms, not remediation steps."""
    if not objectives:
        return []
    items = objectives if isinstance(objectives, list) else [objectives]
    return [o for o in items if isinstance(o, str) and o.strip() and not is_fix_instruction(o)]


def incident_summary(scenario) -> str:
    """Single block for Jira / instructions: description + environment context."""
    parts = []
    desc = (getattr(scenario, "description", "") or "").strip()
    if desc:
        parts.append(desc)
    initial = (getattr(scenario, "initial_state", "") or "").strip()
    if initial and initial not in desc:
        parts.append(initial)
    return "\n\n".join(parts).strip() or "See the FixitLab scenario page for incident details."
