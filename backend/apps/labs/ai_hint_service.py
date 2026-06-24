"""Shared FREE rule-based AI hint / coaching service.

Used by BOTH the lab "Ask AI" button (any scenario) and the interview studio.
100% local — no OpenAI / paid APIs. Hints are progressive coaching nudges that
guide the troubleshooting method without revealing the stored answer.

Public API:
    generate_lab_hint(scenario, order, recent_commands=None) -> dict
    answer_lab_question(scenario, question, recent_commands=None) -> dict

Both return a dict shaped for the API response:
    {"content": str, "ai_generated": True, "order": int}
"""

from __future__ import annotations

import re

# A generic, method-driven coaching ladder. Each step pushes the candidate one
# rung up the troubleshooting method without giving away the fix. Used as the
# spine for every scenario; the leading clause is personalized with the
# scenario's category/technology so it never reads as boilerplate.
_METHOD_LADDER = [
    "Start by reproducing and observing — check service status and the most recent logs for {focus}. What is actually failing, and what does the error say verbatim?",
    "Validate configuration and syntax before changing anything for {focus}. Read-only inspection first: confirm the config is what you think it is.",
    "Trace the path end to end for {focus} — listeners/ports, upstreams/dependencies, permissions, and name resolution. Where does the chain break?",
    "Compare expected vs actual state. Form one hypothesis, then run the single command that confirms or kills it before you touch anything.",
    "Apply the smallest fix that restores health for {focus}, then re-run your check to prove it worked. State the root cause in one sentence.",
]

# Coding scenarios get a debugging-focused ladder instead of an ops ladder.
_CODING_LADDER = [
    "Read the failing test or error output carefully for {focus}. What exact input produces the wrong output, and what was expected?",
    "Trace the data through your function for {focus} — add a print/log or step through the smallest failing case by hand.",
    "Check edge cases for {focus}: empty input, off-by-one boundaries, types, and null/None. Which one is your code not handling?",
    "Isolate the bug to one block. Comment out or simplify until the failing case passes, then reintroduce complexity.",
    "Make the minimal change that turns the test green for {focus}, then re-run the full suite to confirm nothing else broke.",
]

# Topic-specific opening nudges layered on top of the ladder for extra realism.
_TOPIC_HINTS = {
    "nginx": "For nginx, `nginx -t` validates config and `systemctl status nginx` plus the error log usually point straight at a 502/permission/upstream issue.",
    "linux": "On Linux, start with `systemctl status`, `journalctl -xe`, `df -h`/`df -i`, and `ps`/`top` to separate disk, memory, and process problems.",
    "kubernetes": "In Kubernetes, `kubectl get pods`, `kubectl describe pod`, and `kubectl logs` (plus `--previous`) almost always reveal CrashLoopBackOff / image / probe causes.",
    "docker": "With Docker, `docker ps -a`, `docker logs`, and `docker inspect` tell you why a container exits or can't reach a dependency.",
    "database": "For databases, check connectivity and auth first, then slow-query/error logs, then locks and replication lag.",
    "terraform": "With Terraform, run `terraform validate` then `terraform plan` and read the diff before any apply; watch for state lock/drift.",
    "aws": "On AWS, check the resource's health/status, IAM permissions, security groups, and CloudWatch logs in that order.",
    "git": "For Git, `git status`, `git log --oneline`, and `git diff` clarify state before you reset/rebase anything.",
    "python": "In Python, read the full traceback bottom-up, then reproduce in a REPL with the smallest failing input.",
}

# Keyword map to detect a topic from scenario metadata.
_TOPIC_KEYWORDS = {
    "kubernetes": ["kubernetes", "k8s", "kubectl", "pod", "helm"],
    "docker": ["docker", "container", "compose", "image"],
    "nginx": ["nginx", "reverse proxy", "upstream", "web server"],
    "database": ["database", "postgres", "mysql", "mariadb", "mongo", "redis", "sql"],
    "terraform": ["terraform", "iac", "tfstate"],
    "aws": ["aws", "ec2", "s3", "iam", "cloud"],
    "git": ["git", "version control", "commit", "branch"],
    "python": ["python", "django", "flask", "fastapi"],
    "linux": ["linux", "systemd", "bash", "shell", "kernel", "process", "disk", "permission"],
}

MAX_HINTS = 12


def _detect_topic(scenario) -> str | None:
    haystack = " ".join(
        str(x or "").lower()
        for x in (
            getattr(scenario, "title", ""),
            getattr(scenario, "category", ""),
            getattr(scenario, "description", ""),
            getattr(getattr(scenario, "technology", None), "name", ""),
            getattr(getattr(scenario, "simulation_type", None), "__str__", lambda: "")()
            if getattr(scenario, "simulation_type", None) else "",
        )
    )
    # Tags are a M2M; pull names defensively.
    try:
        haystack += " " + " ".join(t.name.lower() for t in scenario.tags.all())
    except Exception:
        pass
    best, best_score = None, 0
    for topic, kws in _TOPIC_KEYWORDS.items():
        score = sum(1 for k in kws if k in haystack)
        if score > best_score:
            best, best_score = topic, score
    return best if best_score >= 1 else None


def _focus(scenario, topic: str | None) -> str:
    """A short, human focus phrase for the {focus} slot."""
    cat = (getattr(scenario, "category", "") or "").strip()
    if cat:
        return cat
    if topic:
        return topic
    tech = getattr(getattr(scenario, "technology", None), "name", "") or ""
    return tech or "this scenario"


def _is_coding(scenario) -> bool:
    return bool(getattr(scenario, "coding_mode", False))


def _progress_note(recent_commands: list[str] | None) -> str:
    """Acknowledge what the learner already tried so the hint feels responsive."""
    if not recent_commands:
        return ""
    cmds = [c.strip() for c in recent_commands if c and c.strip()]
    if not cmds:
        return ""
    last = cmds[-1]
    verbs = " ".join(cmds).lower()
    if any(v in verbs for v in ("status", "logs", "journalctl", "describe", "ps ", "top")):
        return " You've already inspected state — good; now act on what it showed."
    if any(v in verbs for v in ("restart", "apply", "edit", "vi ", "nano ", "systemctl start")):
        return " You've changed something — re-run your verification command to confirm it took effect."
    return f" You last ran `{last[:60]}` — build on that rather than starting over."


def generate_lab_hint(scenario, order: int, recent_commands: list[str] | None = None) -> dict:
    """Return the next progressive coaching hint for any scenario.

    `order` is 1-based (the Nth hint the user has requested this session).
    Never reveals the stored solution; escalates specificity with order.
    """
    topic = _detect_topic(scenario)
    focus = _focus(scenario, topic)
    ladder = _CODING_LADDER if _is_coding(scenario) else _METHOD_LADDER
    idx = max(0, min(int(order) - 1, len(ladder) - 1))
    content = ladder[idx].format(focus=focus)

    # Layer a topic-specific concrete pointer on the first two hints.
    if topic and idx <= 1 and topic in _TOPIC_HINTS:
        content = f"{content} {_TOPIC_HINTS[topic]}"

    content += _progress_note(recent_commands)

    return {"content": content, "ai_generated": True, "order": int(order)}


# --- Free Q&A: answer a typed question about the scenario without spoilers ----

_QA_INTENTS = [
    (re.compile(r"\b(stuck|don'?t know|no idea|where.*start|how.*begin|help)\b", re.I),
     "Start methodically: confirm the symptom, read the most recent logs for {focus}, then form one hypothesis and test it with a single read-only command before changing anything."),
    (re.compile(r"\b(log|error|message|output)\b", re.I),
     "Read the error verbatim and search for the first failure, not the last line. For {focus}, the earliest error in the log is usually the real cause; later ones are side effects."),
    (re.compile(r"\b(config|configuration|file|setting|yaml|conf)\b", re.I),
     "Validate the config before reloading. For {focus}, use the tool's own validator (e.g. `nginx -t`, `terraform validate`, a dry-run) and diff against a known-good example."),
    (re.compile(r"\b(restart|reload|apply|fix|change)\b", re.I),
     "Make the smallest possible change, then immediately re-run your check for {focus} to prove it worked. Avoid changing several things at once — you'll lose the signal."),
    (re.compile(r"\b(slow|performance|latency|timeout|hang)\b", re.I),
     "Localize the bottleneck for {focus}: is it CPU, memory, disk I/O, or a downstream dependency? Measure each before optimizing — one signal will dominate."),
    (re.compile(r"\b(permission|denied|access|forbidden|auth)\b", re.I),
     "This looks like a permissions/auth issue for {focus}. Check the owner, mode, and the effective user of the process, plus any RBAC/IAM/SELinux/AppArmor layer in the path."),
]

_QA_DEFAULT = (
    "Good question. Without giving away the answer for {focus}: reproduce the issue, "
    "inspect state read-only first, isolate the failing component, then apply the "
    "smallest fix and verify. What does your latest command actually show?"
)


def answer_lab_question(scenario, question: str, recent_commands: list[str] | None = None) -> dict:
    """Answer a free-text learner question with a coaching reply (no spoilers)."""
    topic = _detect_topic(scenario)
    focus = _focus(scenario, topic)
    q = (question or "").strip()

    template = _QA_DEFAULT
    for pattern, reply in _QA_INTENTS:
        if pattern.search(q):
            template = reply
            break

    content = template.format(focus=focus)
    if topic and topic in _TOPIC_HINTS:
        content = f"{content} {_TOPIC_HINTS[topic]}"
    content += _progress_note(recent_commands)

    return {"content": content, "ai_generated": True}
