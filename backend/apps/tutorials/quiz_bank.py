"""Deterministic, topic-aware end-of-module quiz generator.

Produces a 5-question scored quiz for a tutorial module. Questions are built
from universally-correct ops/engineering principles with the topic/module name
substituted in, so every module gets a meaningful assessment without any
hand-authoring. Deterministic (seeded by topic+module) so the same module always
renders the same quiz and the correct-answer index is stable.
"""

from __future__ import annotations

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


def build_module_quiz(topic: str, module: str, *, count: int = 5) -> dict:
    """Return a deterministic, scored multi-question quiz for a module."""
    topic = topic or "this technology"
    module = module or topic
    rng = random.Random(f"{topic}::{module}".lower())
    picks = rng.sample(_TEMPLATES, min(count, len(_TEMPLATES)))

    questions = []
    for prompt, correct, distractors, explanation in picks:
        opts = [correct, *distractors]
        rng.shuffle(opts)
        questions.append(
            {
                "question": prompt.format(module=module, topic=topic),
                "options": opts,
                "answer": opts.index(correct),
                "explanation": explanation,
            }
        )

    return {
        "title": f"{module} — module quiz",
        "pass_score": 0.6,
        "questions": questions,
    }
