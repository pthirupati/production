"""P2.R2 — Backchannel layer (free, client/rule-side).

While the candidate is still speaking, inject short non-interrupting
acknowledgements ("mm-hmm", "okay") throttled so they feel human, not twitchy.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


BACKCHANNEL_CUES = (
    "mm-hmm",
    "okay",
    "right",
    "sure",
    "got it",
    "uh-huh",
    "yeah",
    "I see",
)

# Minimum continuous speech (seconds) before first backchannel may fire.
MIN_SPEECH_S = 4.0
# Minimum gap between backchannels during continuous speech.
THROTTLE_S = 15.0


@dataclass
class BackchannelState:
    last_cue: str = ""
    last_fired_at_ms: float = 0.0
    speech_started_at_ms: float = 0.0


def pick_backchannel(
    state: BackchannelState | None,
    *,
    now_ms: float,
    speech_active: bool,
    speech_started_at_ms: float | None = None,
    rng: random.Random | None = None,
) -> tuple[str | None, BackchannelState]:
    """Return (cue_or_None, updated_state).

    Fires at most once per THROTTLE_S while speech has been sustained for
    MIN_SPEECH_S. Never repeats the same cue back-to-back.
    """
    r = rng or random.Random()
    st = state or BackchannelState()
    if speech_started_at_ms is not None:
        st.speech_started_at_ms = float(speech_started_at_ms)

    if not speech_active:
        st.speech_started_at_ms = 0.0
        return None, st

    if st.speech_started_at_ms <= 0:
        st.speech_started_at_ms = now_ms
        return None, st

    sustained = (now_ms - st.speech_started_at_ms) / 1000.0
    if sustained < MIN_SPEECH_S:
        return None, st

    since_last = (now_ms - st.last_fired_at_ms) / 1000.0 if st.last_fired_at_ms else 1e9
    if since_last < THROTTLE_S:
        return None, st

    choices = [c for c in BACKCHANNEL_CUES if c != st.last_cue] or list(BACKCHANNEL_CUES)
    cue = r.choice(choices)
    st.last_cue = cue
    st.last_fired_at_ms = now_ms
    return cue, st


def backchannel_as_message(cue: str) -> dict:
    """Shape for transcript UI — greyed micro-line, not a full bot turn."""
    return {
        "role": "interviewer",
        "message_type": "backchannel",
        "content": cue,
        "metadata": {"backchannel": True, "volume": "low"},
    }
