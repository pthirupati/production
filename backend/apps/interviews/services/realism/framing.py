"""P2.R6 — Small-talk / framing beats (scripted, free).

Turns the persona intro from a monologue into a short 2–3 turn open, and
provides a human sign-off line before the report screen.
"""

from __future__ import annotations

import random


_OPENERS = (
    "Thanks for joining — can you hear me okay?",
    "Hey — thanks for hopping on. Audio coming through alright on your side?",
    "Appreciate you making the time. Quick check — can you hear me clearly?",
)

_FRAMES = (
    "This'll be about {mins} minutes — mostly conversation and a bit of hands-on. Nothing scripted, just how you'd think through it.",
    "We'll keep it conversational for roughly {mins} minutes — troubleshooting and judgment more than trivia.",
    "Plan is ~{mins} minutes. I'll ask you to walk through situations; interrupt anytime if something's unclear.",
)

_CLOSERS = (
    "That's everything I wanted to cover — nice talking through this with you. You'll get the write-up shortly.",
    "I think we're good. Thanks for walking me through your thinking — the report will land in a moment.",
    "That's all from my side. Appreciate the conversation — you'll see the summary shortly.",
)


def framing_opener(*, rng: random.Random | None = None) -> str:
    r = rng or random.Random()
    return r.choice(_OPENERS)


def framing_round_brief(*, duration_minutes: int = 45, rng: random.Random | None = None) -> str:
    r = rng or random.Random()
    mins = max(10, min(90, int(duration_minutes or 45)))
    return r.choice(_FRAMES).format(mins=mins)


def framing_signoff(*, rng: random.Random | None = None) -> str:
    r = rng or random.Random()
    return r.choice(_CLOSERS)


def framing_beat_sequence(*, duration_minutes: int = 45, rng: random.Random | None = None) -> list[dict]:
    """Ordered open beats for start_round (UI advances after each candidate reply)."""
    r = rng or random.Random()
    return [
        {"kind": "framing_checkin", "content": framing_opener(rng=r)},
        {"kind": "framing_brief", "content": framing_round_brief(duration_minutes=duration_minutes, rng=r)},
    ]
