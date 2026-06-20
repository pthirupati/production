"""Rule-based evaluation for Prompt Engineering ("prompt") scenarios.

These scenarios teach prompting against a FREE, fully rule-based simulator — there
is no LLM call and no paid API anywhere in this path. The browser component
(PromptPlayground) gives the user live, rule-based feedback as they type; this
module is the SERVER-SIDE re-check that gates completion.

Integrity (mirrors apps.labs.code_exec): we never trust the browser's verdict.
When the user asks to complete the lesson, the backend re-evaluates each
submitted prompt against the SAME rules embedded in the scenario's
`coding_spec.prompt_config.exercises[*].success`, and the lesson is marked solved
only when every exercise genuinely satisfies its rule. The checks are simple
lexical heuristics (does the prompt name a role? a length cap? an output format?
the right keywords?) — they are intentionally generous teaching aids, not a real
language model, and the code is honest about that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Words that signal the user assigned a ROLE / persona to the assistant.
_ROLE_HINTS = (
    "you are", "act as", "you're a", "you are a", "as a ", "imagine you",
    "pretend you", "your role", "role:", "persona", "system prompt",
)

# Phrases that signal a LENGTH / size constraint.
_LIMIT_HINTS = (
    "word", "words", "sentence", "sentences", "bullet", "bullets", "paragraph",
    "characters", "chars", "under ", "at most", "no more than", "max ", "maximum",
    "limit", "concise", "brief", "short", "one line", "tl;dr", "in 1", "in 2",
    "in 3", "exactly",
)

# Phrases that signal the user asked for an EXAMPLE in the prompt.
_EXAMPLE_HINTS = ("example", "e.g.", "for instance", "such as", "like this", "->", "sample")

# Delimiters that fence reference material from the instruction.
_DELIMITER_HINTS = ('"""', "```", "<document>", "</document>", "<context>", "<<<", "###", "'''")

# Contradictory pairs — used by the debugging lesson's no_contradiction check.
_CONTRADICTION_PAIRS = (
    ("one sentence", "paragraph"),
    ("one sentence", "multi-paragraph"),
    ("single sentence", "detailed"),
    ("brief", "comprehensive"),
    ("one word", "explain in detail"),
)


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _has_any(text: str, needles) -> bool:
    return any(n in text for n in needles)


def _count_example_pairs(text: str) -> int:
    """Count "Input ... -> Output ..." style example pairs (few-shot signal)."""
    arrows = len(re.findall(r"->|=>|➞|→", text))
    labeled = len(re.findall(r"\b(input|output|example)\b\s*[:\-]", text, flags=re.I))
    return max(arrows, labeled // 2)


def _count_list_items(text: str) -> int:
    """Count numbered / bulleted list items (batching signal)."""
    numbered = len(re.findall(r"(?m)^\s*\d+[.)]\s+\S", text))
    bullets = len(re.findall(r"(?m)^\s*[-*•]\s+\S", text))
    return max(numbered, bullets)


def _requests_json(text: str) -> bool:
    return "json" in text or ("{" in text and "}" in text and ":" in text)


@dataclass
class PromptCheck:
    """Result of evaluating one prompt against one exercise's rule set."""
    passed: bool
    score: int                       # 0–100 prompt-quality score (teaching aid)
    matched: list = field(default_factory=list)
    missing: list = field(default_factory=list)


def evaluate_prompt(prompt: str, success: dict | None) -> PromptCheck:
    """Evaluate a single user prompt against one exercise's `success` rules.

    `success` keys (all optional):
      min_words / max_words      int
      require_any_role           bool   — prompt must assign a role
      mentions_limit             bool   — prompt must state a length/size cap
      mentions_example           bool   — prompt must include an example
      has_delimiter              bool   — prompt must fence reference text
      requires_json_request      bool   — prompt must ask for JSON
      no_contradiction           bool   — prompt must not contradict itself
      min_example_pairs / max_example_pairs   int
      min_list_items             int
      require                    list[list[str]] — each inner list: satisfy ANY
      any_of                     list[list[str]] — each inner list: satisfy ANY
      must_contain_all           list[list[str]] — every inner list must match
    """
    success = success or {}
    text = _normalize(prompt)
    words = len(text.split())
    matched: list[str] = []
    missing: list[str] = []

    def ok(label):
        matched.append(label)

    def bad(label):
        missing.append(label)

    if "min_words" in success:
        (ok if words >= int(success["min_words"]) else bad)("enough detail")
    if "max_words" in success:
        (ok if words <= int(success["max_words"]) else bad)("concise enough")

    if success.get("require_any_role"):
        (ok if _has_any(text, _ROLE_HINTS) else bad)("assigns a role")
    if success.get("mentions_limit"):
        (ok if _has_any(text, _LIMIT_HINTS) else bad)("states a length/format limit")
    if success.get("mentions_example"):
        (ok if _has_any(text, _EXAMPLE_HINTS) else bad)("includes an example")
    if success.get("has_delimiter"):
        (ok if _has_any(prompt or "", _DELIMITER_HINTS) else bad)("delimits the reference text")
    if success.get("requires_json_request"):
        (ok if _requests_json(text) else bad)("asks for JSON")
    if success.get("no_contradiction"):
        contradicts = any(a in text and b in text for a, b in _CONTRADICTION_PAIRS)
        (bad if contradicts else ok)("instructions are consistent")

    if "min_example_pairs" in success:
        (ok if _count_example_pairs(prompt or "") >= int(success["min_example_pairs"]) else bad)(
            "includes worked examples"
        )
    if "max_example_pairs" in success:
        (ok if _count_example_pairs(prompt or "") <= int(success["max_example_pairs"]) else bad)(
            "stays zero-shot"
        )
    if "min_list_items" in success:
        (ok if _count_list_items(prompt or "") >= int(success["min_list_items"]) else bad)(
            "batches multiple items"
        )

    # require / any_of: each inner group is satisfied when ANY of its terms hit.
    for group in success.get("require", []) or []:
        terms = [t.lower() for t in group]
        (ok if any(t in text for t in terms) else bad)(f"mentions one of: {', '.join(group[:3])}")
    for group in success.get("any_of", []) or []:
        terms = [t.lower() for t in group]
        (ok if any(t in text for t in terms) else bad)(f"uses one of: {', '.join(group[:3])}")

    # must_contain_all: every inner group must match (used for command exercises).
    for group in success.get("must_contain_all", []) or []:
        terms = [t.lower() for t in group]
        (ok if all(t in text for t in terms) else bad)(f"contains: {', '.join(group[:3])}")

    total = len(matched) + len(missing)
    score = 100 if total == 0 else round(len(matched) * 100 / total)
    passed = len(missing) == 0 and words > 0
    return PromptCheck(passed=passed, score=score, matched=matched, missing=missing)


def evaluate_course(prompt_config: dict, submissions: dict) -> dict:
    """Re-check every exercise's submitted prompt; return an authoritative verdict.

    `submissions` maps exercise id -> the user's final prompt text.
    Returns {all_passed, results:[{id, passed, score, missing}], passed_count, total}.
    The lesson is solved only when EVERY exercise passes — fail closed if an
    exercise is unanswered.
    """
    exercises = (prompt_config or {}).get("exercises", []) or []
    results = []
    passed_count = 0
    for ex in exercises:
        ex_id = ex.get("id", "")
        prompt = (submissions or {}).get(ex_id, "")
        check = evaluate_prompt(prompt, ex.get("success"))
        if check.passed:
            passed_count += 1
        results.append({
            "id": ex_id,
            "title": ex.get("title", ex_id),
            "passed": check.passed,
            "score": check.score,
            "missing": check.missing,
        })
    total = len(exercises)
    return {
        "all_passed": total > 0 and passed_count == total,
        "passed_count": passed_count,
        "total": total,
        "results": results,
    }
