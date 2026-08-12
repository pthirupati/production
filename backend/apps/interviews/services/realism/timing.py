"""P2.R1 — Response-timing model (100% free, deterministic with seeded RNG).

Real interviewers think ~0.6–2s before answering (longer after hard/long
answers or when about to probe). Never reply in 40ms; never identical
consecutive delays.
"""

from __future__ import annotations

import random
import time
from typing import Any


# Persona-ish base windows (seconds). Strict tech lead → shorter; warm HR → longer.
_PERSONA_BASE: dict[str, tuple[float, float]] = {
    "technical": (0.55, 1.35),
    "deep_dive": (0.85, 2.10),
    "manager": (0.70, 1.80),
    "hr": (0.75, 1.90),
    "leadership": (0.80, 2.00),
}

# Floor is the audit's ~300ms target, not the old 500ms. It only binds once
# scoring has already eaten the think-time budget below it; a fast turn still
# samples the full persona window, so the "is typing…" cue never flickers.
_MIN_MS = 300
_MAX_MS = 3500


def compute_thinking_delay_ms(
    round_type: str = "technical",
    *,
    difficulty: int = 2,
    question_kind: str = "",
    category: str = "",
    answer_text: str = "",
    next_move: str = "",
    scoring_elapsed_ms: float | None = None,
    rng: random.Random | None = None,
) -> int:
    """Return think-time in ms for the frontend 'persona is thinking…' cue.

    Parameters mirror the older ``persona_style.thinking_delay_ms`` plus P2.R1
    knobs (answer length, probe moves, scoring already spent).
    """
    r = rng or random.Random()
    lo, hi = _PERSONA_BASE.get(round_type or "technical", _PERSONA_BASE["technical"])
    # Bias sample toward the upper half of the window (humans rarely answer at floor).
    u = r.random()
    base_s = lo + (hi - lo) * (0.35 + 0.65 * u)

    # Difficulty / design stretch.
    diff = max(1, min(5, int(difficulty or 2)))
    if diff >= 4:
        base_s += 0.35
    elif diff >= 3:
        base_s += 0.18

    kind = (question_kind or "").lower()
    cat = (category or "").lower()
    if cat in ("system_design", "architecture") or "design" in kind:
        base_s += 0.45
    if kind in ("cross", "drill", "probe"):
        base_s += 0.35
    elif kind == "behavioral":
        base_s += 0.12
    elif kind in ("intro", "warmup", "framing"):
        base_s -= 0.25

    # Long / technical answers → interviewer "considers".
    words = len((answer_text or "").split())
    if words >= 120:
        base_s += 0.55
    elif words >= 60:
        base_s += 0.30
    elif words >= 30:
        base_s += 0.12

    move = (next_move or "").lower()
    if move in ("probe", "narrow", "hint", "reprompt", "clarify"):
        base_s += 0.40

    # ±15% jitter so consecutive replies never match.
    jitter = 1.0 + r.uniform(-0.15, 0.15)
    delay_ms = int(base_s * 1000 * jitter)

    # Subtract work already done, don't just scale it down.
    #
    # base_s models the interviewer's TOTAL time-to-respond, but the candidate
    # has already been waiting through scoring by the time this delay starts —
    # so the old "scale by a factor above a 1500ms threshold" rule charged them
    # twice and left 0.9–2.6s of pure dead air on every turn (measured over the
    # persona windows). Treating scoring as part of the same think-time budget
    # means a slow turn now feels no slower than a fast one, which is both more
    # honest to the model and what the audit's latency budget asks for.
    if scoring_elapsed_ms is not None and scoring_elapsed_ms > 0:
        delay_ms -= int(scoring_elapsed_ms)

    return max(_MIN_MS, min(_MAX_MS, delay_ms))


def thinking_delay_from_legacy_kwargs(
    round_type: str,
    *,
    difficulty: int = 2,
    question_kind: str = "",
    category: str = "",
    persona_voice_id: str = "",  # noqa: ARG001 — kept for call-site compat
    answer_text: str = "",
    next_move: str = "",
    scoring_elapsed_ms: float | None = None,
    rng: random.Random | None = None,
) -> int:
    """Adapter used by ``persona_style.thinking_delay_ms``."""
    return compute_thinking_delay_ms(
        round_type,
        difficulty=difficulty,
        question_kind=question_kind,
        category=category,
        answer_text=answer_text,
        next_move=next_move,
        scoring_elapsed_ms=scoring_elapsed_ms,
        rng=rng,
    )


def wall_ms() -> float:
    return time.monotonic() * 1000.0


def attach_timing_meta(payload: dict[str, Any], delay_ms: int) -> dict[str, Any]:
    """Stamp timing fields onto an API / engine result dict."""
    out = dict(payload)
    out["thinking_delay_ms"] = int(delay_ms)
    return out
