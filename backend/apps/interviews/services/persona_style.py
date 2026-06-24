"""Free persona profiles — vocabulary, speech cadence, thinking delays.

100% local templates keyed on round_type (SRE technical, HR, manager, etc.).
No external LLM or paid TTS APIs. The frontend merges ``speech_profile`` with
the browser voice picker for rate/pitch/pause shaping.
"""

from __future__ import annotations

import random

# Round-type personas — how each interviewer *sounds* and *phrases* replies.
PERSONA_STYLES: dict[str, dict] = {
    "technical": {
        "title": "Senior SRE",
        "speech": {
            "rate": 0.96,
            "pitch": 1.0,
            "thinking_base_ms": 380,
            "thinking_per_difficulty": 110,
            "pause_question_ms": 360,
            "pause_period_ms": 250,
        },
        "acks": [
            "Right.",
            "Okay.",
            "Got it.",
            "Makes sense.",
            "That tracks.",
        ],
        "connectors": ["so,", "now,", "alright —"],
        "asides": ["Real-world question —", "On a live system —"],
        "vocabulary_swaps": {
            "walk me through": "walk me through",
            "tell me": "tell me",
        },
    },
    "deep_dive": {
        "title": "Staff engineer",
        "speech": {
            "rate": 0.93,
            "pitch": 0.97,
            "thinking_base_ms": 620,
            "thinking_per_difficulty": 175,
            "pause_question_ms": 420,
            "pause_period_ms": 290,
        },
        "acks": [
            "Interesting.",
            "Okay, I follow.",
            "Right — go on.",
            "That's a reasonable starting point.",
        ],
        "connectors": ["let me push on that —", "deeper question —", "trade-off wise —"],
        "asides": ["Architecturally —", "At scale —", "If we're being honest —"],
        "vocabulary_swaps": {},
    },
    "manager": {
        "title": "Engineering manager",
        "speech": {
            "rate": 0.91,
            "pitch": 0.98,
            "thinking_base_ms": 520,
            "thinking_per_difficulty": 130,
            "pause_question_ms": 400,
            "pause_period_ms": 280,
        },
        "acks": [
            "I hear you.",
            "Fair enough.",
            "Understood.",
            "That makes sense from your seat.",
        ],
        "connectors": ["from a process angle —", "stakeholder-wise —", "in an incident —"],
        "asides": ["Thinking about ownership —", "On a busy bridge call —"],
        "vocabulary_swaps": {
            "what breaks": "what's the blast radius",
            "debug": "triage",
        },
    },
    "hr": {
        "title": "People partner",
        "speech": {
            "rate": 0.94,
            "pitch": 1.05,
            "thinking_base_ms": 440,
            "thinking_per_difficulty": 70,
            "pause_question_ms": 320,
            "pause_period_ms": 260,
        },
        "acks": [
            "I appreciate that.",
            "Thanks for sharing.",
            "That's helpful.",
            "Got it — thank you.",
            "I hear you on that.",
        ],
        "connectors": ["I'm curious —", "help me understand —", "tell me more about —"],
        "asides": ["Just between us —", "Genuinely curious —"],
        "vocabulary_swaps": {},
    },
    "leadership": {
        "title": "Director",
        "speech": {
            "rate": 0.90,
            "pitch": 0.96,
            "thinking_base_ms": 580,
            "thinking_per_difficulty": 150,
            "pause_question_ms": 410,
            "pause_period_ms": 300,
        },
        "acks": [
            "Understood.",
            "That's clear.",
            "I follow your reasoning.",
            "Okay — that's useful context.",
        ],
        "connectors": ["from a leadership lens —", "when influence matters —"],
        "asides": ["Big-picture —", "Across teams —"],
        "vocabulary_swaps": {},
    },
}

# Voice-id nudges layered on top of round_type (campaign_builder personas).
_VOICE_MODIFIERS: dict[str, dict] = {
    "indian-female": {"rate": -0.02, "pitch": 0.03},
    "indian-male": {"rate": -0.03, "pitch": -0.02},
    "uk-male": {"rate": -0.04, "pitch": -0.03},
    "us-female": {"rate": 0.0, "pitch": 0.04},
    "us-male": {"rate": -0.02, "pitch": -0.04},
    "default": {},
}


def get_persona_style(round_type: str) -> dict:
    return PERSONA_STYLES.get(round_type, PERSONA_STYLES["technical"])


def speech_profile(round_type: str, persona_voice_id: str = "") -> dict:
    """Rate/pitch/pause hints for the frontend TTS layer."""
    style = get_persona_style(round_type)
    speech = dict(style["speech"])
    mod = _VOICE_MODIFIERS.get(persona_voice_id or "default", _VOICE_MODIFIERS["default"])
    speech["rate"] = round(min(1.08, max(0.88, speech["rate"] + mod.get("rate", 0))), 2)
    speech["pitch"] = round(min(1.15, max(0.88, speech["pitch"] + mod.get("pitch", 0))), 2)
    speech["persona_title"] = style.get("title", "")
    return speech


def thinking_delay_ms(
    round_type: str,
    *,
    difficulty: int = 2,
    question_kind: str = "",
    category: str = "",
    persona_voice_id: str = "",
) -> int:
    """Adaptive pre-speech pause — harder / design questions get a longer beat."""
    style = get_persona_style(round_type)
    s = style["speech"]
    base = int(s["thinking_base_ms"])
    diff = int(s["thinking_per_difficulty"]) * max(0, int(difficulty or 2) - 1)
    extra = 0
    if category == "system_design":
        extra += 220
    if question_kind in ("cross", "drill"):
        extra += 160
    elif question_kind == "behavioral":
        extra += 40
    elif question_kind == "intro":
        extra -= 120
    # Slightly longer think for staff/deep-dive personas even at same difficulty.
    if round_type in ("deep_dive", "leadership"):
        extra += 80
    delay = base + diff + extra
    return max(180, min(1400, delay))


def persona_ack(round_type: str, used: set[str], rng: random.Random) -> str:
    """Pick a persona-flavoured acknowledgement, deduped against ``used``."""
    from apps.interviews.services.interview_ai import _normalize, _pick_unused

    style = get_persona_style(round_type)
    return _pick_unused(style["acks"], used, rng) or style["acks"][0]


def persona_connectors(round_type: str) -> list[str]:
    return get_persona_style(round_type).get("connectors") or []


def persona_asides(round_type: str) -> list[str]:
    return get_persona_style(round_type).get("asides") or []


def apply_vocabulary(text: str, round_type: str, rng: random.Random) -> str:
    """Occasionally swap a phrase for persona-specific vocabulary (~12%)."""
    if not text or rng.random() > 0.12:
        return text
    swaps = get_persona_style(round_type).get("vocabulary_swaps") or {}
    low = text.lower()
    for src, dst in swaps.items():
        if src in low and src != dst:
            idx = low.find(src)
            if idx >= 0:
                return text[:idx] + dst + text[idx + len(src):]
    return text
