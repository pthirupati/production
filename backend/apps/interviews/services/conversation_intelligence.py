"""Round-level conversation intelligence — 100% free, no external APIs.

Tracks what the candidate has said across the interview (topics, phrases, claims,
tone) so follow-ups reference EARLIER answers, adapt to nervousness, redirect
off-topic responses, and pace based on time remaining.

All deterministic heuristics — keyword banks, regex claim extraction, rolling
stats on round.metadata["conversation"]["memory"]. No LLM/embeddings.
"""

from __future__ import annotations

import re
from typing import Any

from apps.interviews.services.interview_ai import (
    _detect_topic,
    _extract_quote_phrase,
    _normalize,
    _pick_unused,
    _score_star_coverage,
)

# ---------------------------------------------------------------------------
# Claim / stance extraction (free regex — captures reusable interview memory)
# ---------------------------------------------------------------------------

_CLAIM_PATTERNS = (
    re.compile(r"\b(?:i|we)\s+(?:would|will|always|never|usually|typically)\s+(.{8,80})", re.I),
    re.compile(r"\b(?:my approach|the way i|what i do)\s+(?:is|was)\s+(.{8,80})", re.I),
    re.compile(r"\b(?:we use|we used|we run|we deploy)\s+(.{6,70})", re.I),
    re.compile(r"\b(?:first i|then i|i start by)\s+(.{8,80})", re.I),
)

_TONE_FILLERS = (
    "um", "uh", "like", "you know", "sort of", "kind of", "i guess", "maybe",
    "basically", "honestly", "i think", "i'm not sure", "not sure",
)

_SUPPORTIVE_ACKS = [
    "Take your time — no rush.",
    "You're doing fine — let's keep going.",
    "No worries at all — happens on a live call.",
    "All good — I'm following you.",
]

_CHALLENGE_ACKS = [
    "Good — let's pressure-test that.",
    "Alright, I'm going to push a little harder here.",
    "Let me challenge that assumption.",
]

_THREAD_TEMPLATES = [
    "Earlier you mentioned “{earlier}” — how does that connect to what you're saying now?",
    "You talked about “{earlier}” a few minutes back — does that still hold here?",
    "Pulling a thread from before — you said “{earlier}”. How does that inform this?",
    "Connecting the dots: “{earlier}” from earlier and this answer — walk me through the link.",
]

_REDIRECT_TEMPLATES = [
    "I want to stay on {topic} for a moment — can you bring it back to that?",
    "That's useful context, but let's anchor on {topic} — what's your direct take?",
    "Fair point — still, for {topic} specifically, what would you do hands-on?",
]

_TIME_PRESSURE_STITCHES = [
    "We're running short on time —",
    "Quick one before we wrap —",
    "Keeping us on pace —",
]

_OFF_TOPIC_TOPICS = frozenset({"hr", "personal", "casual"})


def empty_memory() -> dict[str, Any]:
    return {
        "phrases": [],           # notable phrases quoted across the round
        "claims": [],            # extracted stance/approach snippets
        "topics_hit": {},        # topic -> count
        "qualities": [],         # last N answer qualities
        "scores": [],            # last N scores
        "strong_streak": 0,
        "brief_streak": 0,
        "skipped_count": 0,
        "tone": "neutral",       # neutral | nervous | confident | frustrated
        "star_gaps": {"situation": 0, "task": 0, "action": 0, "result": 0},
        "admin_rated_count": 0,
    }


def _word_count(text: str) -> int:
    return len((text or "").split())


def _filler_ratio(text: str) -> float:
    words = (text or "").lower().split()
    if not words:
        return 0.0
    hits = sum(1 for w in words if w.strip(".,!?") in _TONE_FILLERS)
    hits += sum(1 for p in _TONE_FILLERS if " " in p and p in (text or "").lower())
    return hits / max(len(words), 1)


def extract_claims(text: str, limit: int = 3) -> list[str]:
    """Pull short, reusable claims from an answer for cross-turn memory."""
    claims: list[str] = []
    for pat in _CLAIM_PATTERNS:
        for m in pat.finditer(text or ""):
            chunk = m.group(1).strip().rstrip(".,;")
            if 8 <= len(chunk) <= 90 and chunk.lower() not in {c.lower() for c in claims}:
                claims.append(chunk[:90])
            if len(claims) >= limit:
                return claims
    return claims


def infer_tone(
    *,
    answer_text: str,
    quality: str,
    brief_streak: int,
    skipped_count: int,
) -> str:
    """Heuristic candidate tone — drives supportive vs challenging interviewer mode."""
    if skipped_count >= 2 or brief_streak >= 3:
        return "frustrated"
    ratio = _filler_ratio(answer_text)
    words = _word_count(answer_text)
    if ratio > 0.08 and words < 40:
        return "nervous"
    if quality == "strong" and ratio < 0.03 and words >= 25:
        return "confident"
    return "neutral"


def update_memory(
    memory: dict[str, Any],
    *,
    answer_text: str,
    score_result: dict,
    question_topic: str | None = None,
) -> dict[str, Any]:
    """Merge one answer turn into rolling round memory (mutates and returns)."""
    mem = memory if isinstance(memory, dict) else empty_memory()
    for key, default in empty_memory().items():
        mem.setdefault(key, default if not isinstance(default, dict) else dict(default))

    quality = score_result.get("quality") or ""
    score = float(score_result.get("score") or 0)
    text = (answer_text or "").strip()

    mem["qualities"] = (mem["qualities"] + [quality])[-12:]
    mem["scores"] = (mem["scores"] + [score])[-12:]

    if quality == "skipped":
        mem["skipped_count"] = int(mem.get("skipped_count", 0)) + 1
        mem["brief_streak"] = 0
    elif quality in ("brief", "weak"):
        mem["brief_streak"] = int(mem.get("brief_streak", 0)) + 1
        mem["strong_streak"] = 0
    elif quality == "strong":
        mem["strong_streak"] = int(mem.get("strong_streak", 0)) + 1
        mem["brief_streak"] = 0
    else:
        mem["brief_streak"] = max(0, int(mem.get("brief_streak", 0)) - 1)

    topic = _detect_topic(text) or question_topic
    if topic:
        hits = mem["topics_hit"]
        hits[topic] = int(hits.get(topic, 0)) + 1

    phrase = _extract_quote_phrase(text)
    if phrase and phrase not in mem["phrases"]:
        mem["phrases"] = (mem["phrases"] + [phrase])[-10:]

    for claim in extract_claims(text):
        if claim not in mem["claims"]:
            mem["claims"] = (mem["claims"] + [claim])[-8:]

    star = _score_star_coverage(text)
    for k, v in star.items():
        if not v:
            mem["star_gaps"][k] = int(mem["star_gaps"].get(k, 0)) + 1

    mem["tone"] = infer_tone(
        answer_text=text,
        quality=quality,
        brief_streak=int(mem.get("brief_streak", 0)),
        skipped_count=int(mem.get("skipped_count", 0)),
    )
    if score_result.get("admin_rated"):
        mem["admin_rated_count"] = int(mem.get("admin_rated_count", 0)) + 1
    return mem


def weakest_topic(memory: dict[str, Any], agenda: list[str]) -> str | None:
    """Topic from the agenda least explored so far."""
    hits = memory.get("topics_hit") or {}
    if not agenda:
        return None
    return min(agenda, key=lambda t: hits.get(t, 0))


def underexplored_phrase(memory: dict[str, Any]) -> str | None:
    """A phrase from earlier in the round worth threading back in."""
    phrases = memory.get("phrases") or []
    if len(phrases) < 2:
        return None
    # Prefer an earlier phrase (not the one they just used).
    return phrases[-2] if len(phrases) >= 2 else phrases[0]


def generate_thread_callback(
    memory: dict[str, Any],
    used: set[str],
    rng,
) -> str | None:
    """Reference an earlier phrase to simulate multi-turn memory."""
    earlier = underexplored_phrase(memory)
    if not earlier:
        return None
    templates = [t.format(earlier=earlier) for t in _THREAD_TEMPLATES]
    line = _pick_unused(templates, used, rng)
    return line or None


def generate_off_topic_redirect(
    *,
    answer_text: str,
    question_text: str,
    question_topic: str | None,
    used: set[str],
    rng,
) -> str | None:
    """When the answer topic clearly diverges from the question, gently redirect."""
    if not question_topic or question_topic in _OFF_TOPIC_TOPICS:
        return None
    ans_topic = _detect_topic(answer_text)
    if not ans_topic or ans_topic == question_topic:
        return None
    # Only redirect when answer is short/off-base on the asked topic.
    if _word_count(answer_text) > 60:
        return None
    label = question_topic.replace("_", " ")
    templates = [t.format(topic=label) for t in _REDIRECT_TEMPLATES]
    return _pick_unused(templates, used, rng)


def tone_adaptive_opener(memory: dict[str, Any], used: set[str], rng) -> str | None:
    """Supportive opener when candidate sounds nervous or frustrated."""
    tone = memory.get("tone") or "neutral"
    if tone == "nervous":
        return _pick_unused(_SUPPORTIVE_ACKS, used, rng)
    if tone == "frustrated" and int(memory.get("skipped_count", 0)) >= 1:
        return _pick_unused(_SUPPORTIVE_ACKS, used, rng)
    if tone == "confident" and int(memory.get("strong_streak", 0)) >= 2:
        return _pick_unused(_CHALLENGE_ACKS, used, rng)
    return None


def time_pressure_stitch(seconds_left: float | None, used: set[str], rng) -> str:
    """Prefix when the round clock is running low."""
    if seconds_left is None or seconds_left > 900:
        return ""
    if seconds_left < 300:
        return _pick_unused(_TIME_PRESSURE_STITCHES, used, rng) or _TIME_PRESSURE_STITCHES[0]
    return ""


def suggest_answer_mode(memory: dict[str, Any]) -> str:
    """Hint for question generator: narrow vs open vs behavioral."""
    if int(memory.get("brief_streak", 0)) >= 2:
        return "narrow"  # ask yes/no or single-step questions
    if int(memory.get("strong_streak", 0)) >= 3:
        return "deep"
    if int(memory.get("skipped_count", 0)) >= 2:
        return "encouraging"
    return "normal"


def build_round_narrative(memory: dict[str, Any], round_type: str) -> str:
    """One-paragraph free summary for the end-of-round report."""
    phrases = memory.get("phrases") or []
    topics = memory.get("topics_hit") or {}
    tone = memory.get("tone") or "neutral"
    scores = memory.get("scores") or []
    avg = round(sum(scores) / len(scores), 1) if scores else 0

    top_topics = sorted(topics, key=lambda t: topics[t], reverse=True)[:3]
    topic_str = ", ".join(t.replace("_", " ") for t in top_topics) if top_topics else "general topics"

    parts = [f"Across the round you averaged {avg}/100 on scored answers."]
    if top_topics:
        parts.append(f"Most depth showed up on {topic_str}.")
    if phrases:
        parts.append(
            f'Recurring threads included "{phrases[0]}"'
            + (f' and "{phrases[1]}"' if len(phrases) > 1 else "")
            + "."
        )
    if tone == "nervous":
        parts.append("Delivery had some hesitation — shorter structured answers would land cleaner.")
    elif tone == "confident":
        parts.append("You sounded confident and direct — keep anchoring with metrics.")
    if round_type in ("behavioral", "hr", "manager"):
        gaps = memory.get("star_gaps") or {}
        worst = max(gaps, key=gaps.get) if gaps else None
        if worst and gaps.get(worst, 0) >= 2:
            parts.append(f"STAR practice: several answers skipped the {worst} component.")
    if round_type in ("devops_debug", "sre_oncall"):
        parts.append(
            "Incident rounds reward triage order, blast-radius checks, and clear stakeholder updates — "
            "practice narrating those out loud."
        )
    admin_scores = [
        s for s in (memory.get("scores") or [])
        if isinstance(s, (int, float)) and s > 0
    ]
    if memory.get("admin_rated_count", 0) >= 1:
        parts.append("A live host also scored part of this round — those ratings count toward your report.")
    if round_type == "system_design":
        parts.append("System design rounds benefit from capacity estimates and explicit trade-off calls.")
    return " ".join(parts)


def claim_cross_question(memory: dict[str, Any], used: set[str], rng) -> str | None:
    """Probe a prior claim for consistency / depth."""
    claims = memory.get("claims") or []
    if not claims:
        return None
    claim = claims[-1]
    if _normalize(claim) in used:
        claim = claims[-2] if len(claims) > 1 else claim
    templates = [
        f"You said you'd {claim.rstrip('.')} — walk me through that on a real system.",
        f"Earlier you mentioned {claim.rstrip('.')} — what would break if that assumption was wrong?",
        f"On '{claim[:60]}…' — how would you prove that worked in production?",
    ]
    return _pick_unused(templates, used, rng)


_OPPOSITE_PAIRS = (
    ("always", "never"),
    ("must", "avoid"),
    ("only", "never"),
    ("require", "skip"),
)


def detect_contradiction(memory: dict[str, Any], new_answer: str) -> str | None:
    """Return a prior claim phrase that contradicts the new answer, if any."""
    new_low = (new_answer or "").lower()
    for claim in memory.get("claims") or []:
        c_low = claim.lower()
        for pos, neg in _OPPOSITE_PAIRS:
            if pos in c_low and neg in new_low:
                # Same topic stem overlap (rough).
                stem = c_low.split(pos)[0].strip()[-30:]
                if stem and stem in new_low:
                    return claim[:80]
            if neg in c_low and pos in new_low:
                stem = c_low.split(neg)[0].strip()[-30:]
                if stem and stem in new_low:
                    return claim[:80]
    return None


def generate_contradiction_probe(prior_claim: str, used: set[str], rng) -> str:
    templates = [
        f"Earlier you said '{prior_claim[:70]}' — help me reconcile that with what you just said.",
        f"I'm trying to connect the dots — before you mentioned {prior_claim[:60]}. How does that fit now?",
        f"You told me {prior_claim[:60]} earlier. Walk me through what changed in your thinking.",
    ]
    return _pick_unused(templates, used, rng) or templates[0]
