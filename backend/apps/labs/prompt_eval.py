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

import json
import re
from dataclasses import dataclass, field


# Words that signal the user assigned a ROLE / persona to the assistant.
# NOTE: matched on WORD BOUNDARIES (see _compile_hints), not raw substrings. The
# old substring form made "as a " fire on "this was a great outage" and "has a ",
# i.e. almost any past-tense sentence satisfied require_any_role. The list is a
# superset of the original so no previously-passing prompt regresses.
_ROLE_HINTS = (
    "you are", "act as", "acting as", "you're a", "you're an", "as a", "as an",
    "imagine you", "pretend you", "your role", "role:", "persona", "system prompt",
    # Additional genuine role assignments the original list rejected outright.
    "you will be", "assume the role", "take on the role", "take on the identity",
    "respond as", "reply as", "answer as", "behave like", "speak as", "roleplay",
    "role-play", "in the voice of", "from the perspective of", "you play",
    "your job is", "your task is to act", "expert in", "acts as", "serve as",
)

# Phrases that signal a LENGTH / size constraint.
_LIMIT_HINTS = (
    "word", "sentence", "bullet", "paragraph", "character", "char", "under",
    "at most", "no more than", "max", "maximum", "limit", "concise", "brief",
    "briefly", "short", "shorter", "one line", "single line", "tl;dr", "exactly",
    # Additional real constraint phrasings the original list missed.
    "fewer", "less than", "no longer than", "cap", "token", "at maximum",
    "up to", "keep it to", "not exceed", "one-liner",
)

# A numeric length cap ("in 120 tokens", "3 bullets", "under 50 words", "<=200
# chars") is a limit even when phrased without any of the words above.
_NUMERIC_LIMIT_RE = re.compile(
    r"(?:<=?\s*\d+|\b\d+\s*(?:word|sentence|bullet|line|paragraph|char|character|token|item|point|step)s?\b)",
    flags=re.I,
)

# Phrases that signal the user asked for an EXAMPLE in the prompt.
_EXAMPLE_HINTS = (
    "example", "e.g.", "for instance", "such as", "like this", "->", "sample",
    "for example", "demonstrated by", "as shown", "here's one", "here is one",
)

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


def _compile_hints(hints) -> re.Pattern:
    """Compile a hint tuple into a word-boundary matcher.

    Plain `in` matching was the core grading bug: "short" fired on
    "shortcoming", "limit" on "limitations", "word" on "wording"/"password",
    and "persona" on "personal". We anchor on non-alphanumeric boundaries and
    allow only a trailing "s" (bullet/bullets, character/characters) — a blanket
    "ing"/"ed" suffix would re-introduce the "word" -> "wording" false positive.
    Longest hints first so "no more than" wins over "more".
    """
    parts = []
    for hint in sorted({h.strip() for h in hints if h and h.strip()}, key=len, reverse=True):
        escaped = re.escape(hint)
        # Only append the optional plural when the hint ends in a word char;
        # hints like "e.g." or "->" must stay literal.
        parts.append(rf"{escaped}s?\b" if hint[-1].isalnum() else escaped)
    return re.compile(r"(?<![A-Za-z0-9])(?:" + "|".join(parts) + r")", flags=re.I)


_ROLE_RE = _compile_hints(_ROLE_HINTS)
_LIMIT_RE = _compile_hints(_LIMIT_HINTS)
_EXAMPLE_RE = _compile_hints(_EXAMPLE_HINTS)


def _assigns_role(text: str) -> bool:
    """True when the prompt names a role/persona for the assistant."""
    return bool(_ROLE_RE.search(text))


def _states_limit(text: str) -> bool:
    """True when the prompt caps length/size, by keyword or by a number+unit."""
    return bool(_LIMIT_RE.search(text) or _NUMERIC_LIMIT_RE.search(text))


def _looks_like_word(token: str) -> bool:
    """Cheap proxy for "is this a real word" — no dictionary dependency."""
    t = re.sub(r"[^a-z]", "", token.lower())
    if len(t) < 2:
        return False
    if not re.search(r"[aeiouy]", t):    # rejects xxx / zzz / qwrt
        return False
    return len(set(t)) > 1               # rejects aaa / bbb


def _is_gibberish(text: str) -> bool:
    """Reject keyword-stuffed filler like "you are xxx yyy zzz aaa bbb ...".

    Without this, min_words + require_any_role was clearable by typing a role
    phrase followed by nonsense padding. Measured on real prompts the
    word-like ratio sits at 0.87-0.93; the gibberish above scores 0.13, so 0.6
    leaves a wide margin. JSON-shaped prompts ({"name": string}) measure 0.93,
    so structured-output answers are unaffected. Only applied to prompts long
    enough for the ratio to mean anything.
    """
    tokens = re.findall(r"\S+", text or "")
    if len(tokens) < 6:
        return False
    real = sum(1 for t in tokens if _looks_like_word(t))
    return (real / len(tokens)) < 0.6


def _has_any(text: str, needles) -> bool:
    """Substring match — kept for AUTHOR-supplied `require`/`any_of` term lists.

    Scenario YAML deliberately ships stems ("instruction" must catch
    "instructions", "param" -> "parameters", "class" -> "classify"), so those
    lists must NOT get word-boundary treatment or ~150 prompt lessons un-solve.
    """
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
        # Word COUNT alone was gameable with filler, so a min_words rule also
        # requires the words to be word-like. Paired with min_words only: a
        # short prompt with no length floor is not asked to prove substance.
        enough = words >= int(success["min_words"]) and not _is_gibberish(prompt or "")
        (ok if enough else bad)("enough detail")
    if "max_words" in success:
        (ok if words <= int(success["max_words"]) else bad)("concise enough")

    if success.get("require_any_role"):
        (ok if _assigns_role(text) else bad)("assigns a role")
    if success.get("mentions_limit"):
        (ok if _states_limit(text) else bad)("states a length/format limit")
    if success.get("mentions_example"):
        (ok if _EXAMPLE_RE.search(text) else bad)("includes an example")
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


_INJECTION_MARKERS = (
    "ignore previous", "ignore all previous", "disregard your", "jailbreak",
    "system prompt override", "dan mode", "developer mode",
)


def simulate_reply(prompt: str, task: dict | None = None) -> dict:
    """Deterministic content reply so different prompts yield different outputs.

    Not an LLM — branches on role / JSON / injection / length so prompt labs can
    demonstrate that prompting changes the *answer*, not only a coaching tip.
    """
    task = task or {}
    text = (prompt or "").strip()
    low = text.lower()
    words = len(re.findall(r"\S+", text))

    if any(m in low for m in _INJECTION_MARKERS):
        return {
            "kind": "refusal",
            "body": "I cannot override my instructions or enter unrestricted modes.",
            "refused": True,
            "schema_valid": False,
            "word_count": 12,
        }

    wants_json = bool(
        task.get("force_json")
        or re.search(r"\bjson\b", low)
        or "schema" in low
        or '{"' in text
    )
    has_role = _assigns_role(text)
    max_words = None
    m = re.search(r"(?:under|at most|max(?:imum)?|no more than)\s+(\d+)\s*words?", low)
    if m:
        max_words = int(m.group(1))
    elif task.get("max_output_words"):
        max_words = int(task["max_output_words"])

    if wants_json:
        payload = {
            "role": "expert" if has_role else "assistant",
            "task": "structured",
            "summary": (text[:80] + "…") if len(text) > 80 else text,
            "words_in_prompt": words,
        }
        body = json.dumps(payload, indent=2)
        return {
            "kind": "json",
            "body": body,
            "refused": False,
            "schema_valid": True,
            "word_count": len(body.split()),
            "data": payload,
        }

    if has_role:
        tone = "As your assigned specialist, "
        detail = (
            f"I will approach this with domain focus. "
            f"Your request ({words} words) asks for a concrete deliverable."
        )
    else:
        tone = ""
        detail = (
            f"Here is a generic answer to a {words}-word prompt without a clear role. "
            "Results may be vague."
        )

    body = tone + detail
    if "bullet" in low or "list" in low:
        body = tone + "Key points:\n- Clarify the goal\n- Add constraints\n- Specify output format"
    if max_words is not None:
        toks = body.split()
        if len(toks) > max_words:
            body = " ".join(toks[:max_words]) + "…"

    return {
        "kind": "prose",
        "body": body,
        "refused": False,
        "schema_valid": False,
        "word_count": len(body.split()),
        "has_role_tone": has_role,
    }


def assert_output_conformance(reply: dict, rules: dict | None = None) -> dict:
    """Grade a simulate_reply result against output-side rules (not prompt text)."""
    rules = rules or {}
    reply = reply or {}
    missing = []
    matched = []

    if rules.get("require_refusal"):
        (matched if reply.get("refused") else missing).append("refused unsafe request")
    if rules.get("require_output_json") or rules.get("schema_valid"):
        (matched if reply.get("schema_valid") and reply.get("kind") == "json"
         else missing).append("valid JSON output")
    if "max_output_words" in rules:
        cap = int(rules["max_output_words"])
        wc = int(reply.get("word_count") or 0)
        (matched if wc <= cap else missing).append(f"output ≤ {cap} words")
    if rules.get("contains"):
        body = (reply.get("body") or "").lower()
        needle = str(rules["contains"]).lower()
        (matched if needle in body else missing).append(f"contains {rules['contains']!r}")

    total = len(matched) + len(missing)
    passed = len(missing) == 0 and total > 0
    score = 100 if total == 0 else round(len(matched) * 100 / total)
    return {"passed": passed, "score": score, "matched": matched, "missing": missing}
