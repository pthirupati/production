"""Score candidate answers and generate round reports."""

from __future__ import annotations

import re


def score_answer(question, answer_text: str, metadata: dict | None = None) -> dict:
    """Heuristic scoring 0–100 with feedback hints."""
    text = (answer_text or "").strip()
    meta = metadata or {}
    if not text:
        return {
            "score": 0,
            "quality": "skipped",
            "feedback": "No response recorded — we moved on to keep the interview on schedule.",
        }

    low = text.lower()
    word_count = len(text.split())
    keywords = question.expected_keywords if question else []
    keyword_hits = sum(1 for kw in keywords if kw.lower() in low)

    base = min(40, word_count * 2)
    keyword_score = min(35, keyword_hits * 12)
    structure_bonus = 10 if any(x in low for x in ("first", "then", "because", "for example")) else 0
    command_bonus = 0
    if meta.get("command_validated"):
        command_bonus = 15

    score = min(100, base + keyword_score + structure_bonus + command_bonus)

    if word_count < 8:
        quality = "brief"
        feedback = "You answered quickly — I'd want more depth on approach and trade-offs in a real panel."
    elif score >= 75:
        quality = "strong"
        feedback = "Solid structure. A senior interviewer might still probe edge cases or failure modes next."
    elif score >= 50:
        quality = "adequate"
        feedback = "Reasonable direction. Sharpen with specifics: metrics, commands, or past incident examples."
    else:
        quality = "weak"
        feedback = "The answer missed key signals we'd expect at this level — revisit fundamentals and real examples."

    return {
        "score": round(score, 1),
        "quality": quality,
        "feedback": feedback,
        "keyword_hits": keyword_hits,
        "word_count": word_count,
    }


def aggregate_round_scores(message_scores: list[float]) -> dict:
    if not message_scores:
        return {
            "technical_score": 0,
            "communication_score": 0,
            "problem_solving_score": 0,
            "practical_score": 0,
            "presence_score": 70,
            "resume_alignment_score": 65,
            "overall_score": 0,
        }
    avg = sum(message_scores) / len(message_scores)
    return {
        "technical_score": round(min(100, avg * 1.05), 1),
        "communication_score": round(min(100, avg * 0.95 + 5), 1),
        "problem_solving_score": round(min(100, avg), 1),
        "practical_score": round(min(100, avg * 1.1), 1),
        "presence_score": 72.0,
        "resume_alignment_score": 68.0,
        "overall_score": round(avg, 1),
    }


def build_strengths_and_improvements(scores: list[dict], round_type: str) -> tuple[list, list]:
    strengths = []
    improvements = []
    strong = [s for s in scores if s.get("score", 0) >= 75]
    weak = [s for s in scores if s.get("score", 0) < 55]

    if strong:
        strengths.append(f"Strong answers on {len(strong)} question(s) — clear reasoning under pressure.")
    if round_type == "technical":
        strengths.append("Engaged with troubleshooting and technical follow-ups.")
    if round_type == "manager":
        strengths.append("Discussed process, ownership, and stakeholder angles.")
    if round_type == "hr":
        strengths.append("Communicated motivation and career narrative.")

    if weak:
        improvements.append(f"Deepen answers where you scored below 55 — {len(weak)} area(s) flagged.")
    improvements.append("Add quantified outcomes (MTTR, uptime, cost) when describing past work.")
    improvements.append("Practice concise STAR format for behavioral prompts.")
    if round_type == "technical":
        improvements.append("Run FixitLab scenario labs for hands-on muscle memory.")

    return strengths[:5], improvements[:5]
