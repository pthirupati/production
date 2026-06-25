"""Anti-gaming semantic scorer — TF-IDF relevance, capped length reward."""

from __future__ import annotations

from apps.interviews.services.interview_ai import (
    _assess_quality,
    _count_keyword_hits,
    _detect_topic,
    _generate_feedback,
    _normalize_answer_for_scoring,
    _refine_quality,
    _score_star_coverage,
    _TECHNICAL_DEPTH,
    _CONCRETE_EVIDENCE,
)


def compute_semantic_scores(
    *,
    candidate_answer: str,
    question_text: str,
    round_type: str,
    expected_keywords: list[str] | None = None,
) -> dict:
    """Score from content relevance, not length + buzzwords alone."""
    from apps.interviews.services.conversation.analysis import analyze_answer

    analysis = analyze_answer(
        answer_text=candidate_answer,
        question_text=question_text,
    )
    quality = _assess_quality(candidate_answer, question_text)
    star = _score_star_coverage(candidate_answer)
    topic = _detect_topic(f"{question_text} {candidate_answer}")
    scored_text = _normalize_answer_for_scoring(candidate_answer)
    low = scored_text
    word_count = analysis.word_count

    depth_score = min(100, sum(1 for k in _TECHNICAL_DEPTH if k in low) * 12)
    concrete_score = min(100, sum(1 for k in _CONCRETE_EVIDENCE if k in low) * 15)
    star_score = round(sum(star.values()) / 4 * 100)

    # Cap length reward — long irrelevant answers must not win.
    length_score = min(55, word_count * 1.2) if word_count < 70 else min(55, word_count * 0.35)
    relevance_score = round(analysis.relevance * 100)

    expected_hit_rate = 0.0
    if expected_keywords:
        clean_keywords = [str(k).lower() for k in expected_keywords if k not in (None, "")]
        if clean_keywords:
            _, expected_hit_rate = _count_keyword_hits(candidate_answer, clean_keywords)
        else:
            expected_keywords = None

    if round_type in ("behavioral", "hr"):
        composite = (
            depth_score * 0.15 + concrete_score * 0.10 + star_score * 0.40
            + length_score * 0.10 + relevance_score * 0.25
        )
    elif round_type in ("system_design", "live_coding"):
        composite = (
            depth_score * 0.30 + concrete_score * 0.30 + star_score * 0.05
            + length_score * 0.10 + relevance_score * 0.25
        )
    else:
        composite = (
            depth_score * 0.25 + concrete_score * 0.25 + star_score * 0.10
            + length_score * 0.10 + relevance_score * 0.30
        )

    if expected_keywords:
        composite = composite * 0.65 + expected_hit_rate * 100 * 0.35

    # Anti-gaming: irrelevant wall of text scores LOW.
    if word_count > 80 and relevance_score < 35:
        composite *= 0.55
    if analysis.vagueness > 0.5:
        composite *= 0.85

    has_keywords = bool(expected_keywords)
    quality = _refine_quality(
        quality,
        keyword_hit_rate=expected_hit_rate,
        topic=topic,
        word_count=word_count,
        has_keywords=has_keywords,
    )

    return {
        "quality": quality,
        "composite_score": round(min(100, max(0, composite))),
        "depth_score": depth_score,
        "concrete_score": concrete_score,
        "star_score": star_score,
        "star_coverage": star,
        "word_count": word_count,
        "topic_detected": topic,
        "keyword_hit_rate": round(expected_hit_rate, 2),
        "relevance_score": relevance_score,
        "feedback": _generate_feedback(quality, star, topic, round_type),
    }
