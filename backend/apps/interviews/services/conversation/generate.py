"""Grounded follow-up question generation from candidate content."""

from __future__ import annotations

import random

from apps.interviews.services.conversation.analysis import AnswerAnalysis
from apps.interviews.services.conversation.policy import NextMove, PolicyDecision

_TEMPLATES: dict[NextMove, list[str]] = {
    NextMove.DRILL_DOWN: [
        "You used {tool} for {claim} — how'd you confirm it actually held up under load?",
        "Walk me through what you did with {tool} when {claim} — what was the first check?",
        "On {claim} — what metric told you {tool} was doing the right thing?",
    ],
    NextMove.CLARIFY: [
        "You said '{phrase}' — walk me through exactly how you checked that.",
        "So if I follow you: {phrase}. Is that right? What step proved it?",
        "Help me picture it — when you say '{phrase}', what did you actually run or observe?",
    ],
    NextMove.CHALLENGE: [
        "Earlier you said {claim_a}, but just now {claim_b} — help me square those?",
        "I'm trying to connect the dots — you mentioned {claim_a} before. How does {claim_b} fit?",
        "You told me {claim_a} earlier — what changed in your thinking since then?",
    ],
    NextMove.SCENARIO_ESCALATE: [
        "Good depth — what if {tool} fails mid-incident? What's plan B?",
        "Let's crank it up: {claim} but at 10x traffic — what breaks first?",
        "Assume {tool} is misconfigured in prod — how do you detect and contain it fast?",
    ],
    NextMove.EASE_REDIRECT: [
        "No worries — take your time. Let's simplify: what's the first command you'd run?",
        "All good — happens on live calls. In plain terms, how would you approach {topic}?",
        "You're fine — let me rephrase. For {topic}, what's one concrete step you'd take?",
    ],
    NextMove.HINT_THEN_MOVE: [
        "That's okay — hint: think about logs and the last change. Even a partial approach helps.",
        "No problem — I'd start with observability around {topic}. Want to take a quick stab?",
        "Honesty's fine — if you had to guess the first check for {topic}, what would it be?",
    ],
    NextMove.ANSWER_CANDIDATE: [
        "Good question — we use a structured technical loop with hands-on scenarios. Back to you: {bridge}",
        "Happy to clarify — I'm looking for how you'd troubleshoot in production. So, {bridge}",
    ],
    NextMove.THREAD_BACK: [
        "Earlier you mentioned {earlier} — how does that connect to what you're saying now?",
        "Pulling a thread from before — you said {earlier}. Walk me through that again with more detail.",
    ],
    NextMove.NEW_TOPIC: [],
}

_ACK_STRONG = [
    "Nice — that's exactly the kind of specificity I was looking for.",
    "Good — you're clearly hands-on with this.",
    "Solid — I like the concrete detail there.",
]
_ACK_NEUTRAL = [
    "Got it — thanks for walking through that.",
    "Okay — I'm with you so far.",
    "Alright — let's keep going.",
]


def _pick_unused(pool: list[str], used: set[str], rng: random.Random) -> str:
    for _ in range(len(pool) * 2):
        choice = pool[rng.randrange(len(pool))]
        if choice.lower() not in used:
            return choice
    return pool[rng.randrange(len(pool))]


def _slot_values(analysis: AnswerAnalysis, decision: PolicyDecision) -> dict[str, str]:
    tool = analysis.entities[0] if analysis.entities else (analysis.evidence[0].split()[0] if analysis.evidence else "that tool")
    claim = analysis.noun_phrases[0] if analysis.noun_phrases else analysis.normalized_text[:60]
    phrase = analysis.normalized_text[:70] if analysis.normalized_text else claim
    prior = decision.prior_claim or (analysis.normalized_text[:50])
    return {
        "tool": tool,
        "claim": claim,
        "phrase": phrase,
        "claim_a": prior[:70],
        "claim_b": phrase[:70],
        "topic": decision.thread_key or "this area",
        "earlier": prior[:70],
        "bridge": "what's your go-to first step when something's on fire?",
    }


def generate_acknowledgement(analysis: AnswerAnalysis, rng: random.Random) -> str:
    if analysis.depth >= 0.5 and analysis.confidence >= 0.6:
        return _pick_unused(_ACK_STRONG, set(), rng)
    return _pick_unused(_ACK_NEUTRAL, set(), rng)


def generate_follow_up_question(
    *,
    analysis: AnswerAnalysis,
    decision: PolicyDecision,
    used_texts: set[str],
    rng: random.Random | None = None,
    bridge_question: str = "",
) -> tuple[str, str]:
    """Return (acknowledgement, question). Question is empty for NEW_TOPIC (caller picks bank)."""
    rng = rng or random.Random()
    ack = generate_acknowledgement(analysis, rng)

    if decision.move == NextMove.NEW_TOPIC:
        return ack, ""

    pool = _TEMPLATES.get(decision.move, _TEMPLATES[NextMove.DRILL_DOWN])
    if not pool:
        return ack, bridge_question

    template = _pick_unused(pool, used_texts, rng)
    slots = _slot_values(analysis, decision)
    try:
        question = template.format(**slots)
    except KeyError:
        question = template

    if decision.move == NextMove.ANSWER_CANDIDATE and bridge_question:
        question = question.replace("{bridge}", bridge_question[:120])

    return ack, question
