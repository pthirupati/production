"""Deterministic, topic-aware end-of-module quiz generator.

Produces a 5-question scored quiz for a tutorial module. Questions are built
from universally-correct ops/engineering principles with the topic/module name
substituted in, so every module gets a meaningful assessment without any
hand-authoring. Deterministic (seeded by topic+module) so the same module always
renders the same quiz and the correct-answer index is stable.
"""

from __future__ import annotations

import hashlib
import random

# Each template: (prompt, correct_option, [distractors...], explanation)
# `prompt` may use {module} / {topic}. The correct option is a safe best practice
# that matches the tutorial content; distractors are clearly wrong.
_TEMPLATES: list[tuple[str, str, list[str], str]] = [
    (
        "When {module} starts misbehaving in production, what is the safest FIRST step?",
        "Capture logs, metrics, and recent changes before modifying anything",
        [
            "Reboot the server immediately to clear the issue",
            "Delete data to free space without taking a backup",
            "Mark the task complete and skip validation",
        ],
        "Always confirm the failure mode with logs, metrics, and the change history before any invasive action — restarting blindly can destroy the evidence you need.",
    ),
    (
        "What does it mean for {module} automation to be *idempotent*?",
        "Running the same operation repeatedly produces the same end state",
        [
            "Each run executes faster than the last",
            "Each run deletes the previous run's results",
            "It can only be run once and never repeated",
        ],
        "Idempotency lets you safely re-run automation — the result converges to the desired state instead of compounding changes.",
    ),
    (
        "Which statement about recovery objectives is correct?",
        "RTO is how fast you recover; RPO is how much data you can afford to lose",
        [
            "RTO is the amount of data lost; RPO is the recovery time",
            "RTO and RPO both measure CPU utilization",
            "RTO and RPO are network security controls",
        ],
        "RTO (Recovery Time Objective) bounds downtime; RPO (Recovery Point Objective) bounds data loss. You design backups/failover around both.",
    ),
    (
        "Where should credentials and secrets for {module} be stored?",
        "In a secrets manager or vault — never in Git or shell history",
        [
            "Hard-coded directly in the application repository",
            "In plaintext .env files committed to version control",
            "In code comments so teammates can find them",
        ],
        "Secrets belong in a vault/secrets manager with rotation and audit. Anything in Git or shell history is effectively public.",
    ),
    (
        "Before changing production {module}, the right approach is to...",
        "Validate in a staging environment that mirrors production and prepare a rollback plan",
        [
            "Change production directly because it is faster",
            "Skip testing entirely if you are confident",
            "Disable monitoring first so alerts stay quiet",
        ],
        "Test in production-like staging, change incrementally, and always know how to roll back before you touch prod.",
    ),
    (
        "What does the principle of least privilege require for {topic}?",
        "Grant only the minimum access each user or service needs for its task",
        [
            "Give everyone admin so nobody is ever blocked",
            "Share a single root account across the team",
            "Disable authentication inside lab environments",
        ],
        "Least privilege limits blast radius: a compromised account or service can only reach what it strictly needs.",
    ),
    (
        "How should you confirm a {module} fix actually worked?",
        "Verify SLOs/health checks are green and run automated validation",
        [
            "Assume it works if no error is printed",
            "Ask a teammate to guess whether it looks fixed",
            "Restart the service until the screen looks normal",
        ],
        "A fix is only done when measurable signals (SLOs, health checks, automated tests) confirm recovery.",
    ),
    (
        "A well-designed alert for {module} should be...",
        "Actionable and linked to a runbook so the on-call knows what to do",
        [
            "Fired on every minor metric fluctuation",
            "Routed to a channel nobody monitors",
            "Logged silently with no notification",
        ],
        "Every page should be actionable. Noisy or unactionable alerts cause fatigue and missed real incidents.",
    ),
    (
        "When tuning {module} performance, what should you do first?",
        "Establish a baseline, then change one variable at a time",
        [
            "Change many settings at once to save time",
            "Optimize before measuring anything",
            "Remove all resource limits immediately",
        ],
        "Measure first. Changing one thing at a time against a baseline is the only way to know what actually helped.",
    ),
    (
        "During a root-cause analysis for a {module} incident, you should...",
        "Run a blameless review and add preventive actions to stop recurrence",
        [
            "Identify which individual to blame",
            "Close the incident with no follow-up",
            "Delete the logs to keep things tidy",
        ],
        "Blameless RCAs focus on systemic fixes. Corrective (fix now) and preventive (stop recurrence) actions are the goal.",
    ),
    (
        "What is the best way to roll out a risky change to {module}?",
        "Roll out gradually (canary/staged) with health gates and automatic rollback",
        [
            "Push to every host at once for consistency",
            "Roll out only on Fridays after hours",
            "Skip health checks to speed up the rollout",
        ],
        "Staged/canary rollouts limit blast radius and let you halt or roll back before a bad change reaches everyone.",
    ),
    (
        "Why keep changes to {module} small and frequent?",
        "Small changes are easier to test, review, and roll back when something breaks",
        [
            "Large rare changes are always safer",
            "It lets you skip code review",
            "Smaller changes need no testing",
        ],
        "Small, frequent, tested changes shrink risk and make it obvious which change caused a regression.",
    ),
]


# Generic, wrong-but-plausible answers used as distractors for the topic-specific
# concept questions. They read like real definitions so the correct concept
# description is not trivially identifiable, but none of them is ever correct.
_CONCEPT_DISTRACTORS: list[str] = [
    "A deprecated legacy setting that should always be disabled in production",
    "A billing tier that unlocks additional cloud quota",
    "A cosmetic UI theme with no effect on runtime behaviour",
    "A one-time installer step that never applies after setup",
    "An optional marketing label with no technical meaning",
    "A hardware requirement unrelated to how the system is operated",
]


def _stable_index(*parts: str) -> int:
    """Deterministic non-negative int from the given parts (no RNG/date state)."""
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _load_concepts(topic: str) -> dict:
    """Return the topic's {concept: description} dict, or {} on any failure.

    Guarded so a missing profile module / attribute never breaks quiz generation.
    """
    try:
        from apps.tutorials.management.commands.curriculum.topic_profiles import (
            get_profile,
        )

        profile = get_profile(topic) or {}
        concepts = profile.get("concepts") or {}
        if isinstance(concepts, dict):
            # Only keep string concept/description pairs.
            return {
                str(k): str(v)
                for k, v in concepts.items()
                if isinstance(k, str) and isinstance(v, str) and v.strip()
            }
    except Exception:
        pass
    return {}


def _concept_questions(topic: str, module: str, n: int) -> list[dict]:
    """Build up to ``n`` deterministic topic-specific multiple-choice questions.

    Each question asks "In <topic>, what is <concept>?" with the concept's real
    description as the correct answer and 3 generic distractors. Determinism
    comes from a stable hash of topic+module+index (no random/date state).
    """
    concepts = _load_concepts(topic)
    if not concepts:
        return []

    # Deterministic concept order and selection: hash on topic+module so the same
    # module always renders the same concept questions in the same order.
    ordered = sorted(
        concepts.items(),
        key=lambda kv: _stable_index(topic, module, kv[0]),
    )

    questions: list[dict] = []
    for idx, (concept, description) in enumerate(ordered):
        if len(questions) >= n:
            break
        # Pick 3 distractors deterministically without repeats.
        pool = list(_CONCEPT_DISTRACTORS)
        start = _stable_index(topic, module, concept, str(idx)) % len(pool)
        distractors = [pool[(start + j) % len(pool)] for j in range(3)]
        opts = [description, *distractors]
        # Stable shuffle: rotate by a per-question offset so the correct index
        # varies but is fully determined by topic+module+concept.
        rot = _stable_index(topic, module, concept, "opt") % len(opts)
        opts = opts[rot:] + opts[:rot]
        questions.append(
            {
                "question": f"In {topic}, what is {concept}?",
                "options": opts,
                "answer": opts.index(description),
                "explanation": f"{concept}: {description}",
            }
        )
    return questions


def build_module_quiz(topic: str, module: str, *, count: int = 5) -> dict:
    """Return a deterministic, scored multi-question quiz for a module.

    Draws 2-3 topic-specific concept questions first (when concept data is
    available), then backfills from the universal templates so the total is
    always exactly ``count`` (5) at pass_score 0.8. Any failure in the
    concept layer falls back to 100%-template behaviour.
    """
    topic = topic or "this technology"
    module = module or topic
    rng = random.Random(f"{topic}::{module}".lower())

    questions: list[dict] = []
    used_prompts: set[str] = set()

    # ── Topic-specific concept questions FIRST (guarded) ──
    try:
        # Aim for 2-3 concept questions, deterministically chosen by topic+module.
        desired_concepts = 2 + (_stable_index(topic, module, "n") % 2)  # 2 or 3
        desired_concepts = min(desired_concepts, max(0, count))
        concept_qs = _concept_questions(topic, module, desired_concepts)
    except Exception:
        concept_qs = []
    questions.extend(concept_qs)
    for q in concept_qs:
        used_prompts.add(q["question"])

    # ── Backfill from universal templates to reach exactly ``count`` ──
    remaining = count - len(questions)
    if remaining > 0:
        picks = rng.sample(_TEMPLATES, min(remaining, len(_TEMPLATES)))
        for prompt, correct, distractors, explanation in picks:
            rendered = prompt.format(module=module, topic=topic)
            if rendered in used_prompts:
                continue
            opts = [correct, *distractors]
            rng.shuffle(opts)
            questions.append(
                {
                    "question": rendered,
                    "options": opts,
                    "answer": opts.index(correct),
                    "explanation": explanation,
                }
            )
            used_prompts.add(rendered)
            if len(questions) >= count:
                break

    # Safety net: if (extremely unlikely) we still fell short, top up from the
    # remaining templates so the count invariant holds exactly.
    if len(questions) < count:
        for prompt, correct, distractors, explanation in _TEMPLATES:
            rendered = prompt.format(module=module, topic=topic)
            if rendered in used_prompts:
                continue
            opts = [correct, *distractors]
            rng.shuffle(opts)
            questions.append(
                {
                    "question": rendered,
                    "options": opts,
                    "answer": opts.index(correct),
                    "explanation": explanation,
                }
            )
            used_prompts.add(rendered)
            if len(questions) >= count:
                break

    questions = questions[:count]

    return {
        "title": f"{module} — module quiz",
        "pass_score": 0.8,
        "questions": questions,
    }
