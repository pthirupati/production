"""P2.R4 — Wrong/weak-answer probing state machine (free, rule-based).

narrow → hint → graceful move-on. Never tells the candidate they failed.
Stored on round.metadata["conversation"]["probe_state"][question_key].
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProbeAction(str, Enum):
    ACK_ADVANCE = "ack_advance"
    NARROW = "narrow"
    HINT = "hint"
    MOVE_ON = "move_on"


@dataclass
class ProbeDecision:
    action: ProbeAction
    attempt: int
    resolved: bool
    reason: str = ""


def _quality_bucket(quality: str, correctness: str = "") -> str:
    q = (quality or "").lower()
    c = (correctness or "").lower()
    if q in ("strong", "good") or c in ("correct", "partial_credit"):
        if q == "partial" or c == "partial":
            return "partial"
        return "strong"
    if q == "partial":
        return "partial"
    if q in ("skipped", "empty"):
        return "skipped"
    if q in ("off_topic", "off-topic"):
        return "off_topic"
    if q in ("weak", "wrong", "poor") or c in ("incorrect", "wrong"):
        return "weak"
    return q or "weak"


def next_probe_action(
    *,
    question_key: str,
    quality: str,
    correctness: str = "",
    probe_state: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> tuple[ProbeDecision, dict[str, Any]]:
    """Advance probe ladder for this question; return decision + updated state map."""
    state = dict(probe_state or {})
    entry = dict(state.get(question_key) or {"attempt": 0, "hint_used": False, "resolved": False})
    bucket = _quality_bucket(quality, correctness)

    if bucket in ("strong", "skipped"):
        entry["resolved"] = bucket == "strong"
        entry["attempt"] = int(entry.get("attempt") or 0)
        state[question_key] = entry
        return ProbeDecision(ProbeAction.ACK_ADVANCE, entry["attempt"], entry["resolved"], bucket), state

    if bucket == "partial":
        # Soft single nudge, not the full ladder.
        attempt = int(entry.get("attempt") or 0) + 1
        entry["attempt"] = attempt
        if attempt == 1 and not entry.get("hint_used"):
            entry["hint_used"] = True
            state[question_key] = entry
            return ProbeDecision(ProbeAction.HINT, attempt, False, "partial_nudge"), state
        entry["resolved"] = False
        state[question_key] = entry
        return ProbeDecision(ProbeAction.ACK_ADVANCE, attempt, False, "partial_move"), state

    # weak / wrong / off_topic
    attempt = int(entry.get("attempt") or 0) + 1
    entry["attempt"] = attempt
    if attempt >= max_attempts:
        entry["resolved"] = False
        state[question_key] = entry
        return ProbeDecision(ProbeAction.MOVE_ON, attempt, False, "max_attempts"), state
    if attempt == 1:
        state[question_key] = entry
        return ProbeDecision(ProbeAction.NARROW, attempt, False, "first_weak"), state
    if attempt == 2 and not entry.get("hint_used"):
        entry["hint_used"] = True
        state[question_key] = entry
        return ProbeDecision(ProbeAction.HINT, attempt, False, "second_weak"), state
    state[question_key] = entry
    return ProbeDecision(ProbeAction.MOVE_ON, attempt, False, "ladder_exhausted"), state


def narrow_prompt(question_text: str, follow_ups: list | None = None) -> str:
    if follow_ups:
        for fu in follow_ups:
            if isinstance(fu, str) and fu.strip():
                return f"Let's simplify — {fu.strip()}"
            if isinstance(fu, dict) and (fu.get("text") or fu.get("content")):
                return f"Let's simplify — {(fu.get('text') or fu.get('content')).strip()}"
    q = (question_text or "").strip()
    if q:
        return (
            "Let's simplify — just tell me the first concrete step or command you'd run, "
            "not the whole solution."
        )
    return "Let's simplify — what's the first thing you'd check?"


def hint_line(expected_keywords: list | None = None) -> str:
    kws = [str(k).strip() for k in (expected_keywords or []) if str(k).strip()]
    if kws:
        soft = kws[0]
        return f"Think about what role {soft} plays here — no need to recite the answer."
    return "Think about what you'd inspect first if that came back clean…"


def move_on_line() -> str:
    return "No worries — let's move to something else."
