"""P2.R7 — Phrasing variety / disfluency guard (free, rule-based).

Never repeat the same reaction opener twice in one round. Occasionally
insert mild human imperfections that also mask STT weakness.
"""

from __future__ import annotations

import random
from typing import Any


_OPENERS: dict[str, tuple[str, ...]] = {
    "strong": (
        "Right —",
        "Good instinct.",
        "Solid.",
        "Nice.",
        "That's the right call.",
        "Exactly.",
        "I like that.",
        "Yeah, that tracks.",
    ),
    "partial": (
        "Okay —",
        "Partway there —",
        "I follow some of that —",
        "Close —",
        "We're getting somewhere —",
    ),
    "weak": (
        "Help me out —",
        "Let's slow down —",
        "Talk me through it —",
        "Paint the scene —",
        "Walk me through —",
    ),
    "off_topic": (
        "Interesting, but —",
        "Let me park that —",
        "Coming back to the question —",
        "I hear you — focus though —",
    ),
    "skipped": (
        "No worries —",
        "All good —",
        "That's fine —",
        "We can move on —",
    ),
    "reprompt": (
        "One more beat —",
        "Almost —",
        "Let me nudge —",
        "Try that again —",
    ),
}

_DISFLUENCIES = (
    "Sorry — could you say that last part again?",
    "I think I missed the last piece — one more time?",
    "Let's park that and come back to it.",
    "Hold on — I want to make sure I heard you right.",
)


def pick_opener(
    reaction: str,
    used: set[str] | list[str] | None = None,
    *,
    rng: random.Random | None = None,
) -> str:
    """Return an opener for this reaction type that hasn't been used this round."""
    r = rng or random.Random()
    bank = _OPENERS.get((reaction or "weak").lower(), _OPENERS["weak"])
    used_set = {str(x) for x in (used or [])}
    choices = [o for o in bank if o not in used_set] or list(bank)
    return r.choice(choices)


def maybe_disfluency(
    *,
    stt_confidence: float | None = None,
    answer_too_long: bool = False,
    turn_index: int = 0,
    rng: random.Random | None = None,
) -> str | None:
    """~1 in 12 turns, or when STT confidence is low / answer is a long tangent."""
    r = rng or random.Random()
    if stt_confidence is not None and stt_confidence < 0.45:
        return _DISFLUENCIES[0] if r.random() < 0.7 else _DISFLUENCIES[1]
    if answer_too_long and r.random() < 0.35:
        return _DISFLUENCIES[2]
    if turn_index > 0 and r.random() < (1.0 / 12.0):
        return r.choice(_DISFLUENCIES)
    return None


def apply_variety(
    reply: str,
    *,
    reaction: str,
    used_openers: list[str] | None = None,
    stt_confidence: float | None = None,
    answer_text: str = "",
    turn_index: int = 0,
    rng: random.Random | None = None,
) -> tuple[str, list[str]]:
    """Prefix reply with a fresh opener; optionally replace with a disfluency line.

    Returns (final_reply, updated_used_openers).
    """
    r = rng or random.Random()
    used = list(used_openers or [])
    words = len((answer_text or "").split())
    dis = maybe_disfluency(
        stt_confidence=stt_confidence,
        answer_too_long=words >= 180,
        turn_index=turn_index,
        rng=r,
    )
    if dis and (stt_confidence is not None and stt_confidence < 0.45 or words >= 180):
        # Disfluency replaces the reply when hearing failed or tangent ran long.
        return dis, used

    opener = pick_opener(reaction, used, rng=r)
    used.append(opener)
    text = (reply or "").strip()
    # Avoid double-prefix if reply already starts with the opener.
    if text.lower().startswith(opener.lower().rstrip(" —.-").lower()):
        return text, used
    if not text:
        return opener.rstrip(" —"), used
    # Soft join: opener + rest
    if opener.endswith(("—", "-", ".")):
        combined = f"{opener} {text[0].lower() + text[1:] if text[0].isupper() and len(text) > 1 else text}"
    else:
        combined = f"{opener} {text}"
    if dis and r.random() < 0.3:
        # Rare: append a mild aside without replacing content.
        combined = f"{dis} {combined}"
    return combined.strip(), used[:40]


def load_used_openers(conv_meta: dict[str, Any] | None) -> list[str]:
    if not isinstance(conv_meta, dict):
        return []
    return list(conv_meta.get("used_openers") or [])


def store_used_openers(conv_meta: dict[str, Any], used: list[str]) -> dict[str, Any]:
    out = dict(conv_meta or {})
    out["used_openers"] = list(used)[:40]
    return out
