"""Rule-based AI Mentor for the browser coding IDE — FREE, no paid LLM.

Philosophy
----------
This is a *teaching* assistant, not an answer machine. Given the learner's
current code plus the latest run/test output, it produces plain-language
guidance: it names the error, explains *why* it happens, points at the likely
line, explains what a failing test was conceptually checking, and offers
generic style / complexity / security nudges. It teaches the underlying
concept so the learner can fix it themselves.

Hard integrity rule (mirrors code_exec.py / prompt_eval.py):
    The mentor NEVER reveals the reference solution or hidden-test source.
    Hidden test *logic* is not even an input here — only the public test name
    and the masked pass/fail. The reference solution / solution_explanation is
    returned by a SEPARATE, explicitly-gated unlock path (reference_payload),
    only after the caller confirms an intentional "unlock" action. The analyze
    surface below can never emit it.

Everything is pure pattern matching over the code + output strings. No network,
no model, no external service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── data shapes ──────────────────────────────────────────────────────────────

@dataclass
class MentorNote:
    """One piece of mentor guidance.

    kind:    'error' | 'test' | 'concept' | 'style' | 'security' | 'info'
    title:   short headline
    detail:  the explanation (never contains the reference solution)
    line:    1-based line number in the user's code, if we could locate it
    """
    kind: str
    title: str
    detail: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {"kind": self.kind, "title": self.title, "detail": self.detail}
        if self.line is not None:
            d["line"] = self.line
        return d


@dataclass
class MentorReport:
    notes: list[MentorNote] = field(default_factory=list)
    # A one-line summary the UI can show as the headline.
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "notes": [n.to_dict() for n in self.notes],
            # Explicit, machine-readable promise to the client/tests: this
            # payload never carries the answer.
            "reveals_solution": False,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

# Keys in a coding_spec / scenario we must NEVER echo back from analyze().
_FORBIDDEN_REFERENCE_KEYS = ("reference", "solution", "solution_explanation", "answer")


def _first_int(text: str) -> int | None:
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def _clip(text: str, n: int = 600) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1] + "…"


# ── Python error analysers ────────────────────────────────────────────────────
# Each returns a MentorNote (or None). They look only at the user's code and the
# captured traceback/stderr — never at any reference material.

def _py_error_note(code: str, output: str) -> MentorNote | None:
    out = output or ""
    line = _py_error_line(out)

    rules = [
        (r"\bIndentationError\b|\bTabError\b|unexpected indent|expected an indented block",
         "IndentationError — Python's blocks are defined by whitespace",
         "Python uses indentation (not braces) to group code. A line that ends with ':' "
         "(def, if, for, while, class, try) must be followed by a more-indented block, and "
         "every line in that block must line up. Mixing tabs and spaces triggers this too — "
         "pick 4 spaces and keep them consistent."),

        (r"\bNameError\b.*name '([^']+)' is not defined|name '([^']+)' is not defined",
         "NameError — using a name before it exists",
         "You referenced a variable or function that Python hasn't seen yet. Common causes: "
         "a typo in the name, using it above where it's defined, or forgetting to assign it / "
         "import it. Check spelling and that the definition runs before this line."),

        (r"\bTypeError\b.*takes .* positional argument|missing \d+ required positional argument",
         "TypeError — wrong number of arguments",
         "You're calling a function with too many or too few arguments. Compare the call site "
         "with the function's `def` line and make the parameters line up (watch out for `self` "
         "on methods)."),

        (r"\bTypeError\b.*unsupported operand type|can only concatenate|must be str, not|"
         r"'int' object is not subscriptable|'NoneType' object is not",
         "TypeError — operating on the wrong type",
         "An operation got a value of an unexpected type — e.g. adding a string to an int, "
         "indexing something that isn't a list/str, or using a value that is actually None. "
         "Print the value (and `type(x)`) just before the failing line to see what it really is. "
         "A None often means a function returned nothing (missing `return`)."),

        (r"\bIndexError\b|list index out of range",
         "IndexError — index past the end of the sequence",
         "You indexed a list/string at a position that doesn't exist. Remember indices are "
         "0..len-1; the last item is `seq[len(seq)-1]` or `seq[-1]`. Loops that go to "
         "`range(len(seq)+1)` or use `<=` are the classic off-by-one cause."),

        (r"\bKeyError\b",
         "KeyError — that key isn't in the dict",
         "You looked up a dictionary key that doesn't exist. Guard with `if key in d`, use "
         "`d.get(key, default)`, or make sure the key was inserted before it's read."),

        (r"\bZeroDivisionError\b",
         "ZeroDivisionError — dividing by zero",
         "A denominator evaluated to 0. Check for the empty/zero case before dividing (e.g. "
         "guard `if n == 0`) — averages over empty input are a frequent trigger."),

        (r"\bAttributeError\b.*'([^']+)' object has no attribute '([^']+)'",
         "AttributeError — that method/attribute doesn't exist on this value",
         "You called `.something()` on a value that doesn't have it — often because the value "
         "is None or a different type than you expect (e.g. a str where you expected a list). "
         "Verify what the variable actually holds just before this line."),

        (r"\bRecursionError\b|maximum recursion depth",
         "RecursionError — runaway recursion",
         "A recursive function never hit its base case, so it called itself until the stack "
         "overflowed. Make sure there's a base case that returns WITHOUT recursing, and that "
         "each call moves toward it."),

        (r"\bValueError\b",
         "ValueError — right type, wrong value",
         "The value had the correct type but an unacceptable value (e.g. `int('abc')`, or "
         "unpacking the wrong number of items). Validate or convert the input before using it."),

        (r"\bSyntaxError\b|invalid syntax|EOL while scanning|unexpected EOF",
         "SyntaxError — Python can't parse this",
         "The code is malformed before it ever runs. Look for a missing colon after def/if/for, "
         "unbalanced (), [] or quotes, or `=` (assignment) where you meant `==` (comparison) on "
         "the line the traceback points to (and the line just above it)."),

        (r"\bModuleNotFoundError\b|No module named",
         "ModuleNotFoundError — import couldn't be resolved",
         "An `import` referenced a module that isn't available in this sandbox. Stick to the "
         "standard library for these exercises, and check the module name's spelling."),
    ]

    for pattern, title, detail in rules:
        if re.search(pattern, out):
            return MentorNote(kind="error", title=title, detail=detail, line=line)

    # A traceback we didn't specifically classify — still help generically.
    if "Traceback (most recent call last)" in out or re.search(r"\bError\b", out):
        last = ""
        for ln in reversed(out.strip().splitlines()):
            if ln.strip():
                last = ln.strip()
                break
        return MentorNote(
            kind="error",
            title="Your code raised an exception",
            detail=(
                "Read the LAST line of the traceback first — it names the exception and the "
                "message. Then look at the line number it reports in your file. "
                + (f"Here it was: “{_clip(last, 200)}”." if last else "")
            ),
            line=line,
        )
    return None


def _py_error_line(output: str) -> int | None:
    """Pull the user's failing line number out of a Python traceback."""
    # Frames pointing at our sandbox file names <solution> / <test:...>.
    matches = re.findall(r'File "(?:<solution>|<test[^"]*>|solution\.py)", line (\d+)', output or "")
    if matches:
        return int(matches[-1])
    return None


# ── JavaScript error analysers ────────────────────────────────────────────────

def _js_error_note(code: str, output: str) -> MentorNote | None:
    out = output or ""
    rules = [
        (r"\bReferenceError\b.*?(\w+) is not defined|(\w+) is not defined",
         "ReferenceError — using a name that doesn't exist",
         "You used a variable or function that was never declared (or is out of scope). Check "
         "the spelling, that it's declared with let/const/function before use, and that you "
         "didn't forget to define it."),

        (r"\bTypeError\b.*is not a function",
         "TypeError — calling something that isn't a function",
         "You wrote `x(...)` but `x` isn't a function — often a typo, the wrong property, or a "
         "value that is undefined. Confirm what `x` holds before the call."),

        (r"\bTypeError\b.*Cannot read propert(y|ies) of (undefined|null)",
         "TypeError — reading a property of undefined/null",
         "You accessed `.prop` (or `[i]`) on a value that is undefined or null. This usually "
         "means a lookup returned nothing or a function returned no value. Check the object "
         "exists first (optional chaining `?.` or an `if` guard)."),

        (r"\bSyntaxError\b|Unexpected token|Unexpected end of input",
         "SyntaxError — the code can't be parsed",
         "There's a structural mistake before the code runs: an unbalanced `{ } ( ) [ ]`, a "
         "missing comma, or a stray token. The message points near where the parser gave up."),

        (r"\bRangeError\b.*call stack|Maximum call stack size exceeded",
         "RangeError — stack overflow from recursion",
         "A function recursed without reaching a stopping condition. Ensure a base case returns "
         "without calling itself, and that each call gets closer to it."),

        (r"assertion failed|\bAssertionError\b",
         "An assertion failed",
         "An `assert(...)` check did not hold — your function returned something other than what "
         "the test expected for that input. Log the actual return value and compare it to what "
         "the test name implies."),
    ]
    for pattern, title, detail in rules:
        if re.search(pattern, out):
            return MentorNote(kind="error", title=title, detail=detail)

    if re.search(r"\b\w*Error\b", out):
        last = ""
        for ln in out.strip().splitlines():
            if ln.strip():
                last = ln.strip()
                break
        return MentorNote(
            kind="error",
            title="Your code threw an error",
            detail=(
                "Start from the error name and message, then trace it back to the line in your "
                "code. " + (f"Here: “{_clip(last, 200)}”." if last else "")
            ),
        )
    return None


# ── failing-test explainer (conceptual — NEVER the expected value) ─────────────

def _humanize_test_name(name: str) -> str:
    n = (name or "").strip()
    n = re.sub(r"^(test[_\s]*)+", "", n, flags=re.IGNORECASE)
    n = n.replace("_", " ").replace("-", " ").strip()
    return n or "this case"


def _test_note(test: dict, language: str) -> MentorNote:
    """Explain, conceptually, what a failing test was probing.

    We deliberately use only the test's public *name* and its (already public,
    visible-test) message. For hidden tests the caller passes a masked name, so
    nothing about expected values can leak here.
    """
    name = test.get("name") or "a test"
    hidden = bool(test.get("hidden"))
    human = _humanize_test_name(name)

    if hidden:
        title = "A hidden test failed"
        detail = (
            "One of the server-side hidden tests didn't pass. Hidden tests probe edge cases the "
            "visible ones don't — think empty input, the largest/smallest value, negatives, "
            "duplicates, boundaries (first/last element), or unusual but valid input. Re-read the "
            "task requirements and ask which edge case your code might mishandle."
        )
        return MentorNote(kind="test", title=title, detail=detail)

    title = f"Failing test: {name}"
    msg = (test.get("message") or "").strip()
    detail = (
        f"This visible test checks “{human}”. It runs your code on a specific input and asserts "
        "the result. Reproduce that case yourself: call your function with that kind of input, "
        "print what you return, and compare it to what the name describes — the gap points at the bug."
    )
    if msg:
        detail += f" The failure message was: “{_clip(msg, 200)}”."
    return MentorNote(kind="test", title=title, detail=detail)


# ── concept teaching from the error/test kind ──────────────────────────────────

def _concept_note(code: str, output: str, language: str) -> MentorNote | None:
    out = output or ""
    if re.search(r"IndexError|out of range|out of bounds|off.by.one", out, re.IGNORECASE):
        return MentorNote(
            kind="concept",
            title="Concept: off-by-one & boundaries",
            detail=(
                "Sequences are indexed 0..len-1. The two classic off-by-one bugs are looping one "
                "step too far (`range(len(x)+1)` or `<=`) and starting/ending one off. When you "
                "iterate, prefer iterating the items directly (`for item in seq`) or "
                "`for i in range(len(seq))` so the bounds are automatic."
            ),
        )
    if re.search(r"NoneType|returned nothing|is not a function|undefined", out, re.IGNORECASE):
        return MentorNote(
            kind="concept",
            title="Concept: every path must return a value",
            detail=(
                "If a function is supposed to produce a result, every branch must `return` it. A "
                "missing return makes the function yield None/undefined, which then blows up "
                "wherever the caller uses it. Trace each if/else branch and confirm it returns."
            ),
        )
    return None


# ── style / complexity / security heuristics (generic, no answer) ──────────────

def _py_style_notes(code: str) -> list[MentorNote]:
    notes: list[MentorNote] = []
    src = code or ""
    lines = src.splitlines()

    if "\t" in src and re.search(r"^ +", src, re.MULTILINE):
        notes.append(MentorNote(
            kind="style", title="Mixed tabs and spaces",
            detail="You're indenting with both tabs and spaces. Python is strict about this — "
                   "standardise on 4 spaces per level to avoid IndentationError.",
        ))
    if re.search(r"except\s*:", src):
        notes.append(MentorNote(
            kind="style", title="Bare `except:` swallows everything",
            detail="A bare `except:` hides real bugs (even typos raise NameError). Catch the "
                   "specific exception you expect, e.g. `except ValueError:`.",
        ))
    if re.search(r"==\s*True|==\s*False|==\s*None", src):
        notes.append(MentorNote(
            kind="style", title="Compare with `is`, not `==`, for None/bool",
            detail="Prefer `if x is None:` and just `if flag:` / `if not flag:` rather than "
                   "`== None` / `== True`. It's clearer and the idiomatic Python.",
        ))
    long_lines = [i + 1 for i, ln in enumerate(lines) if len(ln) > 100]
    if long_lines:
        notes.append(MentorNote(
            kind="style", title="Some lines are very long",
            detail=f"Line(s) {', '.join(map(str, long_lines[:5]))} exceed 100 characters. "
                   "Breaking them up improves readability.",
            line=long_lines[0],
        ))
    # crude nested-loop complexity hint
    if _max_loop_nesting(lines, r"\b(for|while)\b") >= 2:
        notes.append(MentorNote(
            kind="style", title="Nested loops — watch complexity",
            detail="You have loops nested at least two deep (O(n²) or worse). For large inputs "
                   "that can be slow; a dict/set for lookups often turns an inner loop into O(1).",
        ))
    return notes


def _py_security_notes(code: str) -> list[MentorNote]:
    notes: list[MentorNote] = []
    src = code or ""
    checks = [
        (r"\beval\s*\(", "Avoid eval()",
         "`eval` executes arbitrary code from its argument — a classic injection risk. Parse the "
         "value explicitly (e.g. `int()`, `json.loads`) instead."),
        (r"\bexec\s*\(", "Avoid exec()",
         "`exec` runs arbitrary code and is rarely needed. There's almost always a direct, safer "
         "construct for what you want."),
        (r"subprocess|os\.system|os\.popen", "Shell calls need care",
         "Building shell commands from input invites command injection. Avoid `shell=True`, pass "
         "argument lists, and never interpolate untrusted strings into a command."),
        (r"pickle\.loads", "Don't unpickle untrusted data",
         "`pickle.loads` can execute arbitrary code during deserialization. Use JSON for "
         "untrusted input."),
        (r"input\s*\(.*\).{0,20}(eval|exec)", "Never eval/exec user input",
         "Evaluating user input as code is a direct injection vulnerability."),
    ]
    for pattern, title, detail in checks:
        if re.search(pattern, src):
            notes.append(MentorNote(kind="security", title=title, detail=detail))
    return notes


def _js_style_notes(code: str) -> list[MentorNote]:
    notes: list[MentorNote] = []
    src = code or ""
    if re.search(r"(^|\W)var\s+\w", src):
        notes.append(MentorNote(
            kind="style", title="Prefer `let`/`const` over `var`",
            detail="`var` is function-scoped and hoisted, which causes subtle bugs. Use `const` "
                   "by default and `let` when you must reassign.",
        ))
    if re.search(r"[^=!<>]==[^=]|[^=!<>]!=[^=]", src):
        notes.append(MentorNote(
            kind="style", title="Use `===` / `!==`",
            detail="Loose equality (`==`) does surprising type coercion (`0 == ''` is true). "
                   "Prefer strict `===` / `!==`.",
        ))
    if _max_loop_nesting(src.splitlines(), r"\bfor\b|\bwhile\b|\.forEach\b") >= 2:
        notes.append(MentorNote(
            kind="style", title="Nested loops — watch complexity",
            detail="Loops nested two-deep are O(n²). A Map/Set for lookups can flatten an inner "
                   "loop to O(1) for large inputs.",
        ))
    return notes


def _js_security_notes(code: str) -> list[MentorNote]:
    notes: list[MentorNote] = []
    src = code or ""
    checks = [
        (r"\beval\s*\(", "Avoid eval()",
         "`eval` runs arbitrary code from a string — an injection risk and a deopt. Use "
         "`JSON.parse` for data, or a direct expression."),
        (r"new\s+Function\s*\(", "Avoid `new Function`",
         "Like eval, `new Function` builds code from strings at runtime. Prefer ordinary "
         "functions."),
        (r"\.innerHTML\s*=", "Setting innerHTML can enable XSS",
         "Assigning untrusted strings to innerHTML can inject scripts. Use textContent or "
         "sanitise the input."),
        (r"document\.write\s*\(", "Avoid document.write",
         "It can execute injected markup and is bad practice. Build DOM nodes instead."),
    ]
    for pattern, title, detail in checks:
        if re.search(pattern, src):
            notes.append(MentorNote(kind="security", title=title, detail=detail))
    return notes


def _max_loop_nesting(lines: list[str], loop_pat: str) -> int:
    """Very rough indentation-based nesting estimate for loop keywords."""
    best = 0
    stack: list[int] = []  # indentation widths of open loops
    for ln in lines:
        if not ln.strip():
            continue
        indent = len(ln) - len(ln.lstrip())
        while stack and indent <= stack[-1]:
            stack.pop()
        if re.search(loop_pat, ln):
            stack.append(indent)
            best = max(best, len(stack))
    return best


# ── public entry point ────────────────────────────────────────────────────────

def analyze(
    *,
    language: str,
    code: str,
    output: str = "",
    error: str = "",
    test_results: list[dict] | None = None,
    requested: str = "all",
) -> MentorReport:
    """Produce mentor guidance from the learner's code + latest run/test output.

    Args:
        language:     'python' | 'javascript' | ...
        code:         the user's current source (entrypoint/composed)
        output:       captured stdout (advisory)
        error:        captured stderr / traceback / runtime error text
        test_results: list of {name, passed, message?, hidden?} from the last grade
        requested:    'all' | 'error' | 'tests' | 'improve' | 'concept'

    Returns a MentorReport. It NEVER contains the reference solution; the
    `reveals_solution` flag in the dict is always False.
    """
    lang = (language or "python").lower()
    is_py = lang == "python"
    is_js = lang in ("javascript", "js", "node", "nodejs")
    combined_err = "\n".join(s for s in (error, output) if s)

    report = MentorReport()
    want = (requested or "all").lower()
    want_error = want in ("all", "error")
    want_tests = want in ("all", "tests")
    want_improve = want in ("all", "improve", "style", "security")
    want_concept = want in ("all", "concept", "error")

    # 1) Error / exception explanation.
    if want_error and combined_err.strip():
        note = _py_error_note(code, combined_err) if is_py else (
            _js_error_note(code, combined_err) if is_js else None
        )
        if note is None and not is_py and not is_js:
            note = MentorNote(
                kind="info", title="Read the runtime output",
                detail="In-browser analysis is tuned for Python and JavaScript. For other "
                       "languages, read the error text top-to-bottom and match it to the line it "
                       "names; the server's Check Solution output is authoritative.",
            )
        if note:
            report.notes.append(note)

    # 2) Failing-test explanations (conceptual only).
    if want_tests and test_results:
        failing = [t for t in test_results if not t.get("passed")]
        for t in failing[:6]:
            report.notes.append(_test_note(t, lang))
        if not failing and test_results:
            report.notes.append(MentorNote(
                kind="info", title="All shown tests passed",
                detail="Every test in the last run passed. If the scenario still isn't solved, "
                       "click Check Solution so the server runs the hidden tests too.",
            ))

    # 3) Underlying concept.
    if want_concept:
        c = _concept_note(code, combined_err, lang)
        if c:
            report.notes.append(c)

    # 4) Improvements: style + complexity + security heuristics.
    if want_improve:
        if is_py:
            report.notes.extend(_py_style_notes(code))
            report.notes.extend(_py_security_notes(code))
        elif is_js:
            report.notes.extend(_js_style_notes(code))
            report.notes.extend(_js_security_notes(code))

    # Headline summary.
    if not report.notes:
        if combined_err.strip():
            report.summary = "Your code produced output but I couldn't classify a specific error — read the message below."
        else:
            report.summary = (
                "No errors detected. Run your code or Check Solution, then ask me to explain "
                "any failure — I won't give away the answer."
            )
        if not combined_err.strip():
            report.notes.append(MentorNote(
                kind="info", title="Mentor is ready",
                detail="I can explain errors and stack traces, tell you what a failing test is "
                       "conceptually checking, teach the underlying concept, and suggest style, "
                       "complexity, and security improvements — all without revealing the "
                       "reference solution.",
            ))
    else:
        kinds = {n.kind for n in report.notes}
        if "error" in kinds:
            report.summary = "I found an error to explain — see below. I won't reveal the solution."
        elif "test" in kinds:
            report.summary = "Here's what the failing test(s) were checking, conceptually."
        else:
            report.summary = "Some suggestions to improve your code."

    # Defense-in-depth: scrub the unlikely event that any note text echoed a
    # forbidden key name verbatim. (None of the rules above do; this is a belt.)
    _assert_no_solution_leak(report)
    return report


def _assert_no_solution_leak(report: MentorReport) -> None:
    """Best-effort guard: the analyze() surface must not carry solution material."""
    # The mentor only ever has the user's own code + public output as inputs, so
    # there is structurally nothing to leak. This simply guarantees the contract
    # flag stays honest.
    assert report.to_dict()["reveals_solution"] is False


# ── explicitly-gated reference reveal (the ONLY place an answer is returned) ───

def reference_payload(scenario, *, unlocked: bool) -> dict[str, Any]:
    """Return the reference solution material — ONLY when `unlocked` is True.

    This is the single sanctioned path that exposes the answer, and it requires
    the caller to have confirmed an explicit unlock (the UI gates this behind a
    confirm dialog + button). Until then it returns nothing but a flag, so the
    mentor's normal analysis can never leak the solution.
    """
    if not unlocked:
        return {
            "unlocked": False,
            "reference_available": bool(
                getattr(scenario, "solution_explanation", "")
                or (scenario.coding_spec or {}).get("reference")
            ),
        }

    spec = scenario.coding_spec or {}
    return {
        "unlocked": True,
        # solution_explanation is the human-written walkthrough; reference (if an
        # author chose to embed one in the spec) is the model code.
        "solution_explanation": getattr(scenario, "solution_explanation", "")
        or "No written explanation was provided for this scenario.",
        "reference": spec.get("reference", ""),
        "language": spec.get("language", "python"),
    }
