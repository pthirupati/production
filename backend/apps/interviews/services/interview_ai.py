"""FixitLab native interview AI — 100% free, rule-based, no external APIs."""

from __future__ import annotations

import random


_REACTIONS_STRONG = [
    "Right — and in production, how would you prove that quickly?",
    "Okay, I hear you. What would break first if we scaled that 10x?",
    "That's a solid line of thinking. What metric would you watch after the change?",
]
_REACTIONS_WEAK = [
    "I'd want a bit more depth there — walk me through your mental checklist.",
    "Help me understand the sequence — what do you check first, second?",
    "Let's slow down — what's the failure mode you're most worried about?",
]
_REACTIONS_BRIEF = [
    "Short answer — can you expand with a real incident or example?",
    "I didn't catch the full picture — what tools or commands would you use?",
]
_REACTIONS_SKIPPED = [
    "No worries, let's keep moving —",
    "We'll come back to that theme later — for now,",
]
_CASUAL_HR = [
    "By the way, how's the team culture where you are now?",
    "What would make you say yes to an offer in the next month?",
    "Any constraints on relocation or remote work we should know?",
]
_ITIL_NUDGES = [
    "Where does that sit with change management — normal, standard, or emergency?",
    "Who owns the SLA clock when vendors are in the blast radius?",
    "How do you document the incident timeline for a postmortem?",
]


def generate_interviewer_reply(
    *,
    persona_name: str,
    round_type: str,
    question_text: str,
    candidate_answer: str,
    score_hint: dict,
    profile_snapshot: dict,
    conversation_tail: list[dict],
    strong_streak: int = 0,
) -> str:
    """Natural interviewer follow-up without any paid LLM."""
    quality = score_hint.get("quality", "adequate")
    company = profile_snapshot.get("current_company") or "your current org"
    role = profile_snapshot.get("target_role") or profile_snapshot.get("experience_level", "mid")

    if quality == "skipped":
        base = random.choice(_REACTIONS_SKIPPED)
    elif quality == "strong":
        base = random.choice(_REACTIONS_STRONG)
        if strong_streak >= 5:
            base = (
                "Let me push harder — what's the nastiest edge case you've seen with this, "
                f"especially at {company}?"
            )
    elif quality == "weak":
        base = random.choice(_REACTIONS_WEAK)
    elif quality == "brief":
        base = random.choice(_REACTIONS_BRIEF)
    else:
        base = score_hint.get("feedback", "Tell me more about how you'd validate that.")

    if round_type == "hr" and random.random() < 0.35:
        return f"{base} {random.choice(_CASUAL_HR)}"

    if round_type == "manager" and random.random() < 0.4:
        return f"{base} {random.choice(_ITIL_NUDGES)}"

    if "resume" in (candidate_answer or "").lower() or "my experience" in (candidate_answer or "").lower():
        return (
            f"{base} Your resume mentions {role} work — how does that tie to what you just described?"
        )

    if candidate_answer and "?" in candidate_answer[-80:]:
        return (
            f"Good question. Briefly: it depends on blast radius and rollback — "
            f"but back to you: how would you de-risk that in the first 15 minutes?"
        )

    follow_templates = [
        f"{base} If this happened on a Friday evening at {company}, what's step one?",
        f"{base} What would you log so the next engineer isn't guessing?",
        f"{persona_name} here — {base.lower()}",
    ]
    return random.choice(follow_templates)
