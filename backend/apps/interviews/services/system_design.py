"""Free system-design interview intelligence — no LLM/API.

Progressive dimension drilling (requirements → capacity → API → data → cache →
reliability → scale) with trade-off probes. Used for ``deep_dive`` rounds and
``system_design`` category slots.
"""

from __future__ import annotations

import random
import re

from apps.interviews.services.interview_ai import _extract_quote_phrase, _normalize, _pick_unused
from apps.interviews.services.interview_types import get_type_config

# Opening prompts — seeded from interview_types + extras.
_OPENING_PROMPTS: list[str] = [
    "Design a URL shortener that handles 1 billion URLs and 100K reads per second.",
    "Design a distributed job scheduler for a cloud platform.",
    "Design the monitoring stack for a 500-node Kubernetes cluster.",
    "Design a notification service that sends 10 million push notifications per hour.",
    "Design a real-time chat system for 50 million daily active users.",
    "Design a video streaming platform like a simplified YouTube.",
    "Design an e-commerce checkout that must stay consistent during flash sales.",
]

# Each design dimension: keywords that signal coverage + follow-up probes.
_DESIGN_DIMENSIONS: dict[str, dict] = {
    "requirements": {
        "keywords": [
            "requirement", "scope", "constraint", "assumption", "feature", "user story",
            "functional", "non-functional", "latency", "availability",
        ],
        "probes": [
            "Before we go deeper — what are the top three functional requirements you'd lock first?",
            "What assumptions are you making about read vs write ratio and peak traffic?",
            "What would you explicitly defer to a v2 so v1 ships safely?",
        ],
    },
    "capacity": {
        # NOTE: keep these specific to capacity ESTIMATION. Generic words like
        # "storage", "users", "requests" over-match normal answers (e.g. "Postgres
        # for storage" is a data-layer choice, not a capacity estimate).
        "keywords": [
            "rps", "qps", "tps", "gb", "tb", "bandwidth", "peak traffic",
            "estimate", "back-of-envelope", "million", "billion", "throughput",
        ],
        "probes": [
            "Walk me through a back-of-envelope estimate — storage, QPS, and bandwidth.",
            "Where does your design break first if traffic 10x's overnight?",
            "What numbers would you put in front of a skeptical principal engineer?",
        ],
    },
    "api": {
        "keywords": [
            "api", "endpoint", "rest", "grpc", "graphql", "idempotent", "request", "response",
            "version", "contract",
        ],
        "probes": [
            "Sketch the core API surface — what are the critical endpoints and why?",
            "How do you keep the API idempotent where it matters?",
            "What versioning strategy would you use before you have a breaking change?",
        ],
    },
    "data": {
        "keywords": [
            "database", "sql", "nosql", "postgres", "mysql", "mongo", "dynamodb", "shard",
            "partition", "replicate", "schema", "index", "primary key",
        ],
        "probes": [
            "SQL or NoSQL here — what's the trade-off you're accepting?",
            "How would you partition or shard as data grows?",
            "What's your migration story if the schema needs to change under load?",
        ],
    },
    "cache": {
        "keywords": [
            "cache", "redis", "memcached", "cdn", "ttl", "evict", "invalidate", "hot key",
        ],
        "probes": [
            "Where does caching live in your design, and what's the invalidation strategy?",
            "How do you handle hot keys or cache stampedes?",
            "When would you skip caching entirely for correctness?",
        ],
    },
    "reliability": {
        "keywords": [
            "failover", "replication", "backup", "rto", "rpo", "redundan", "multi-region",
            "availability", "slo", "disaster", "outage",
        ],
        "probes": [
            "What's your failure mode — single AZ, single region, or single service?",
            "Walk me through failover: who detects, who decides, who executes?",
            "What RTO/RPO would you commit to and how does the design meet it?",
        ],
    },
    "messaging": {
        "keywords": [
            "queue", "kafka", "sqs", "pubsub", "async", "event", "stream", "worker", "consumer",
        ],
        "probes": [
            "What needs to be synchronous vs async in this design?",
            "How do you handle poison messages or a stuck consumer?",
            "Where would you use an event log vs a task queue?",
        ],
    },
    "scale": {
        "keywords": [
            "horizontal", "vertical", "autoscale", "load balance", "cdn", "multi-region",
            "bottleneck", "100x", "global",
        ],
        "probes": [
            "How does this design scale horizontally — what state do you shed first?",
            "What's the first bottleneck at 100x load and how would you relieve it?",
            "Would you go multi-region on day one — why or why not?",
        ],
    },
}

_PHASE_ORDER = [
    "requirements", "capacity", "api", "data", "cache", "reliability", "messaging", "scale",
]

_TRADEOFF_PROBES = [
    "You mentioned “{phrase}” — what's the main trade-off you're accepting there?",
    "On “{phrase}” — what would you choose differently if consistency mattered more than latency?",
    "Picking up “{phrase}” — how does that choice fail, and how would you detect it early?",
    "If a principal pushed back on “{phrase}”, what evidence would you use to defend it?",
]

_NARRATION_NUDGES = [
    "As you sketch this out, narrate your diagram — what boxes are you drawing first?",
    "Talk me through what you'd put on the whiteboard before any deep dive.",
    "If you were sharing your screen, what component would you label first and why?",
]


def opening_prompt(used: set[str], rng: random.Random) -> str:
    cfg = get_type_config("system_design")
    pool = list(cfg.get("opening_prompts") or []) + _OPENING_PROMPTS
    return _pick_unused(pool, used, rng) or pool[0]


def detect_covered_dimensions(text: str) -> set[str]:
    low = (text or "").lower()
    covered: set[str] = set()
    for dim, spec in _DESIGN_DIMENSIONS.items():
        if any(k in low for k in spec["keywords"]):
            covered.add(dim)
    return covered


def next_missing_dimension(covered: set[str]) -> str | None:
    for dim in _PHASE_ORDER:
        if dim not in covered:
            return dim
    return None


def generate_system_design_question(
    *,
    last_answer: str = "",
    active_prompt: str = "",
    phase: str | None = None,
    difficulty: int = 2,
    used: set[str],
    rng: random.Random,
    questions_asked: int = 0,
) -> tuple[str, str, str]:
    """Return (question_text, phase, kind).

    ``phase`` is persisted on the message metadata so the next turn knows where
    we are in the design drill."""
    prompt = (active_prompt or "").strip()

    # First system-design turn — open with a broad prompt + narration nudge.
    if not prompt:
        text = opening_prompt(used, rng)
        nudge = _pick_unused(_NARRATION_NUDGES, used, rng)
        if nudge and rng.random() < 0.7:
            text = f"{text} {nudge}"
        return text, "requirements", "system_design_open"

    covered = detect_covered_dimensions(last_answer) if last_answer else set()
    if phase:
        covered.add(phase)

    # Advance from the CURRENT phase forward — never drill back to an earlier
    # dimension (e.g. don't ask about "requirements" once we're deep in the API).
    if phase and phase in _PHASE_ORDER:
        _start = _PHASE_ORDER.index(phase)
        _ordered = _PHASE_ORDER[_start:] + _PHASE_ORDER[:_start]
    else:
        _ordered = list(_PHASE_ORDER)
    missing = next((d for d in _ordered if d not in covered), None)
    phrase = _extract_quote_phrase(last_answer) if last_answer else None

    # Quote their architecture choice and probe trade-offs when we have a phrase.
    if phrase and rng.random() < 0.45:
        tpl = _pick_unused(_TRADEOFF_PROBES, used, rng) or _TRADEOFF_PROBES[0]
        text = tpl.format(phrase=phrase)
        return text, missing or phase or "scale", "system_design_tradeoff"

    # Drill the next uncovered dimension.
    if missing:
        probes = _DESIGN_DIMENSIONS[missing]["probes"]
        probe = _pick_unused(probes, used, rng) or probes[0]
        # Anchor back to the original prompt so the thread stays coherent.
        short = prompt.split(".")[0][:120]
        text = f"Staying on {short} — {probe}"
        return text, missing, "system_design_drill"

    # All dimensions touched — escalate with scale / edge-case stress tests.
    hard = [
        "Stress-test your design — what's the nastiest edge case you haven't addressed yet?",
        "If you had to cut one component to ship in two weeks, what goes and what breaks?",
        "How would you validate this design in a load test before production traffic?",
        "Where is your design over-engineered for v1 — what would you simplify?",
    ]
    if difficulty >= 4:
        hard.append(
            "A regional outage takes out your primary database — walk me through the next 15 minutes."
        )
    text = _pick_unused(hard, used, rng) or hard[0]
    return text, "scale", "system_design_stress"


def system_design_reply_probe(
    *,
    candidate_answer: str,
    question_text: str,
    conversation_tail: list[dict] | None,
) -> str | None:
    """Optional short interviewer reaction specialised for design answers."""
    used = {_normalize(m.get("content", "")) for m in (conversation_tail or []) if m.get("role") == "interviewer"}
    rng = random.Random()
    covered = detect_covered_dimensions(candidate_answer)
    phrase = _extract_quote_phrase(candidate_answer)

    if len(covered) >= 4:
        opts = [
            "Good — you're covering the major pieces.",
            "Okay, the architecture is taking shape.",
            "Right — I can see the system coming together.",
        ]
        return _pick_unused(opts, used, rng)

    if phrase:
        opts = [
            f"You brought up “{phrase}” — let's pressure-test that choice.",
            f"On “{phrase}” — I want to hear the trade-off explicitly.",
        ]
        return _pick_unused(opts, used, rng)

    return None
