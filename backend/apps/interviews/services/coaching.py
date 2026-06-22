"""Real-time coaching / practice mode — instant tips after each answer.

Parity with interviewai.io's practice mode and aiinterview.in's feedback: in
practice mode the candidate gets an immediate, actionable coaching tip after
every answer (alongside the interviewer's reply) instead of only an end-of-round
report. 100% free — derived from the same free score breakdown the engine already
computes (depth, concreteness, STAR, length, filler words). No paid API.
"""

from __future__ import annotations

from apps.interviews.services.scorecard import _FILLER_WORDS, _count_phrases


def coaching_tip(score_result: dict, *, round_type: str = "technical", answer_text: str = "") -> dict:
    """Return a single, prioritized coaching tip + the headline signals for one
    answer. ``score_result`` is the dict returned by ``scoring.score_answer``.
    """
    quality = score_result.get("quality", "")
    score = score_result.get("score", 0)
    depth = score_result.get("depth_score", 0)
    concrete = score_result.get("concrete_score", 0)
    star = score_result.get("star_coverage") or {}
    word_count = score_result.get("word_count", 0)

    tips: list[str] = []

    if quality == "skipped":
        tips.append("You skipped that — even a short structured attempt scores better than silence.")
    else:
        if word_count and word_count < 30:
            tips.append("Too brief — aim for 4–6 sentences with a concrete example.")
        if depth < 40:
            tips.append("Add the 'why': explain trade-offs, root cause, or how it works under the hood.")
        if concrete < 30:
            tips.append("Make it concrete — name the tool, command, metric, or number you'd use.")
        if round_type in ("behavioral", "hr"):
            missing = [k for k, v in star.items() if not v]
            if missing:
                tips.append(
                    "Use STAR — you're missing: " + ", ".join(m.capitalize() for m in missing) + "."
                )
        filler = _count_phrases(answer_text or "", _FILLER_WORDS)
        if word_count and filler and (filler / max(word_count, 1)) > 0.04:
            tips.append("Cut filler words ('um', 'like', 'basically') to sound more confident.")

    if not tips:
        if score >= 80:
            tips.append("Excellent answer — strong depth and specifics. Keep that structure.")
        else:
            tips.append("Solid — add one quantified outcome (%, time saved, scale) to push it higher.")

    return {
        "tip": tips[0],
        "all_tips": tips[:3],
        "score": score,
        "quality": quality,
        "signals": {
            "depth": depth,
            "concrete": concrete,
            "word_count": word_count,
            "star_coverage": star,
        },
    }
