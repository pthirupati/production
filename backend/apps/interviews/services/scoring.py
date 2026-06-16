"""Score candidate answers and generate round reports."""

from __future__ import annotations


def score_answer(question, answer_text: str, metadata: dict | None = None) -> dict:
    """Richer scoring using interview_ai.compute_answer_scores — 100% free, no APIs."""
    from apps.interviews.services.interview_ai import compute_answer_scores

    text = (answer_text or "").strip()
    meta = metadata or {}

    if not text:
        return {
            "score": 0,
            "quality": "skipped",
            "feedback": "No response recorded — we moved on to keep the interview on schedule.",
        }

    round_type = meta.get("round_type", "technical")
    keywords = list(question.expected_keywords) if question and question.expected_keywords else []

    breakdown = compute_answer_scores(
        candidate_answer=text,
        question_text=(question.question_text if question else ""),
        round_type=round_type,
        expected_keywords=keywords or None,
    )

    score = breakdown["composite_score"]
    if meta.get("command_validated"):
        score = min(100, score + 15)

    return {
        "score": round(score, 1),
        "quality": breakdown["quality"],
        "feedback": breakdown["feedback"],
        "keyword_hits": round(breakdown["keyword_hit_rate"] * len(keywords)) if keywords else 0,
        "word_count": breakdown["word_count"],
        "depth_score": breakdown["depth_score"],
        "concrete_score": breakdown["concrete_score"],
        "star_score": breakdown["star_score"],
        "star_coverage": breakdown["star_coverage"],
        "topic_detected": breakdown["topic_detected"],
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
