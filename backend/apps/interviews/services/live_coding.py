"""Live coding interview engine — free, no LLM/API.

Opens coding problems from interview_types, grades via expected_signals or
inline sandbox tests, and drills edge cases / complexity / failure modes.
"""

from __future__ import annotations

import random
import re

from apps.interviews.services.interview_ai import _normalize, _pick_unused

# Rich problem specs: prompt metadata + optional sandbox tests + signal keywords.
PROBLEM_SPECS: dict[str, dict] = {
    "Prometheus exporter": {
        "language": "python",
        "expected_signals": ["prometheus_client", "Gauge", "start_http_server", "statvfs"],
        "code": {
            "language": "python",
            "timeout": 10,
            "tests": [
                {
                    "name": "uses prometheus client",
                    "code": "assert 'prometheus' in open('_submission.py').read().lower() or 'gauge' in open('_submission.py').read().lower()",
                },
                {
                    "name": "defines a gauge or metric",
                    "code": "src = open('_submission.py').read().lower(); assert 'gauge' in src or 'counter' in src",
                },
            ],
        },
    },
    "K8s health sidecar": {
        "language": "python",
        "expected_signals": ["HTTP", "200", "503", "ready", "file"],
        "code": {
            "language": "python",
            "timeout": 8,
            "tests": [
                {
                    "name": "checks readiness file or path",
                    "code": "src = open('_submission.py').read().lower(); assert 'ready' in src or '/tmp/ready' in src",
                },
                {
                    "name": "returns status codes",
                    "code": "src = open('_submission.py').read(); assert '200' in src or '503' in src",
                },
            ],
        },
    },
    "Log parser": {
        "language": "python",
        "expected_signals": ["stdin", "split", "Counter", "try", "except"],
        "code": {
            "language": "python",
            "timeout": 8,
            "tests": [
                {
                    "name": "reads input",
                    "code": "src = open('_submission.py').read().lower(); assert 'stdin' in src or 'read' in src or 'input' in src",
                },
                {
                    "name": "handles bad lines",
                    "code": "src = open('_submission.py').read().lower(); assert 'try' in src or 'except' in src",
                },
            ],
        },
    },
}

_PHASES = ("edge_case", "complexity", "failure", "test", "readability")

_FOLLOWUPS: dict[str, list[str]] = {
    "edge_case": [
        "What happens if input is empty or malformed — walk me through your handling.",
        "What edge case would break your first draft, and how would you harden it?",
        "If the filesystem list is empty, what does your exporter return?",
    ],
    "complexity": [
        "What's the time and space complexity of your approach?",
        "How would this behave at 10x traffic — any bottlenecks?",
        "Could you simplify this without losing correctness?",
    ],
    "failure": [
        "What would you log or alert on if this fails silently in production?",
        "How would you roll this back safely if the deploy misbehaved?",
        "What happens if the dependency (disk, API, file) is unavailable?",
    ],
    "test": [
        "What unit test would you add first to lock this behavior in?",
        "How would you test the failure path without flaking in CI?",
        "Show me how you'd mock the external dependency in a test.",
    ],
    "readability": [
        "If a junior on your team reads this in six months — what would you rename or comment?",
        "What would you extract into a helper to make this easier to review?",
    ],
}

_OPENERS = [
    "Let's do a live coding exercise — {title}. {prompt} Paste code or talk through your approach.",
    "Hands-on time — {title}. {prompt} Share code when you're ready and we'll iterate.",
]


def _signals_in_text(text: str, signals: list[str]) -> list[str]:
    low = (text or "").lower()
    hits: list[str] = []
    for sig in signals or []:
        s = (sig or "").lower().strip()
        if s and s in low:
            hits.append(sig)
    return hits


def signal_hit_rate(text: str, signals: list[str]) -> float:
    if not signals:
        return 0.0
    return len(_signals_in_text(text, signals)) / len(signals)


def build_practical_config(problem: dict) -> dict:
    title = problem.get("title") or "Coding exercise"
    spec = PROBLEM_SPECS.get(title, {})
    signals = problem.get("expected_signals") or spec.get("expected_signals") or []
    code = spec.get("code") or {}
    return {
        "kind": "code",
        "language": spec.get("language") or "python",
        "expected_signals": signals,
        "coding_title": title,
        "code": code if code.get("tests") else None,
        "validate_commands": [],
    }


def pick_opening_problem(used: set[str], rng: random.Random) -> dict | None:
    from apps.interviews.services.interview_types import get_type_config

    problems = get_type_config("live_coding").get("starter_problems") or []
    pool = [
        p for p in problems
        if _normalize(p.get("title", "")) not in used and _normalize(p.get("prompt", "")) not in used
    ]
    if not pool:
        pool = problems
    if not pool:
        return None
    return rng.choice(pool)


def generate_opening(
    *,
    used: set[str],
    rng: random.Random,
    difficulty: int,
) -> tuple[str, dict] | None:
    pick = pick_opening_problem(used, rng)
    if not pick:
        return None
    title = pick.get("title") or "Coding exercise"
    prompt = (pick.get("prompt") or "").strip()
    tpl = _pick_unused(_OPENERS, used, rng) or _OPENERS[0]
    text = tpl.format(title=title, prompt=prompt)
    config = build_practical_config(pick)
    config["live_coding_phase"] = "edge_case"
    config["difficulty"] = difficulty
    return text, config


def _next_phase(current: str) -> str:
    order = list(_PHASES)
    if current not in order:
        return order[0]
    idx = order.index(current)
    return order[(idx + 1) % len(order)]


def generate_followup(
    *,
    last_answer: str,
    coding_title: str,
    expected_signals: list[str],
    phase: str,
    used: set[str],
    rng: random.Random,
) -> tuple[str, str, dict] | None:
    """Return (question_text, next_phase, practical_config_patch) or None to advance topic."""
    hits = _signals_in_text(last_answer, expected_signals)
    rate = signal_hit_rate(last_answer, expected_signals)
    next_phase = _next_phase(phase or "edge_case")

    if rate < 0.2 and len((last_answer or "").split()) < 25:
        text = (
            f"I didn't see much of the core pieces yet for {coding_title} — "
            f"can you paste or describe code that touches {expected_signals[0] if expected_signals else 'the main API'}?"
        )
        return text, phase or "edge_case", {"live_coding_phase": phase or "edge_case"}

    if (phase or "") == "readability":
        return None

    bank = _FOLLOWUPS.get(next_phase, _FOLLOWUPS["edge_case"])
    probe = _pick_unused(bank, used, rng) or bank[0]
    if hits:
        probe = f"You used {', '.join(hits[:2])} — {probe}"
    text = probe
    return text, next_phase, {"live_coding_phase": next_phase, "coding_title": coding_title}


def grade_by_signals(answer: str, expected_signals: list[str]) -> dict:
    hits = _signals_in_text(answer, expected_signals)
    rate = signal_hit_rate(answer, expected_signals)
    if rate >= 0.5:
        return {
            "validated": True,
            "method": "code_signals",
            "feedback": (
                f"Nice — I see the right building blocks ({', '.join(hits[:4])}). "
                "Let's pressure-test it further."
            ),
        }
    if rate >= 0.25:
        missing = [s for s in expected_signals if s not in hits][:2]
        return {
            "validated": False,
            "method": "code_signals",
            "feedback": (
                f"Partially there — I'd also expect {', '.join(missing)}. "
                "Tighten the implementation and check again."
            ),
        }
    hint = expected_signals[0] if expected_signals else "the core API"
    return {
        "validated": False,
        "method": "code_signals",
        "feedback": (
            f"Not seeing {hint} yet — paste working code or describe the exact functions you'd call."
        ),
    }


def live_coding_reply_probe(
    *,
    candidate_answer: str,
    expected_signals: list[str],
    phase: str,
) -> str | None:
    """Short interviewer reaction after a coding answer."""
    rate = signal_hit_rate(candidate_answer, expected_signals)
    if rate >= 0.55:
        return "Good — that covers the main pieces. Let's stress-test it."
    if rate >= 0.3:
        return "You're on the right track — tighten the implementation a bit."
    if re.search(r"```|def |class |function |import ", candidate_answer or "", re.I):
        return "Thanks for the code — walk me through how you'd test it."
    return None
