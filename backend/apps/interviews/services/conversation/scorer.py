"""Anti-gaming semantic scorer — substance-weighted relevance, capped length reward."""

from __future__ import annotations

from apps.interviews.services.interview_ai import (
    _assess_quality,
    _count_keyword_hits,
    _detect_topic,
    _generate_feedback,
    _refine_quality,
    _score_star_coverage,
)


def compute_semantic_scores(
    *,
    candidate_answer: str,
    question_text: str,
    round_type: str,
    expected_keywords: list[str] | None = None,
    reference_text: str = "",
    technology_id: int | None = None,
) -> dict:
    """Score from content relevance, not length + buzzwords alone."""
    from apps.interviews.services.conversation.analysis import (
        analyze_answer,
        score_concrete_evidence,
        score_technical_depth,
    )

    ref = (reference_text or "").strip()
    if not ref and technology_id:
        from apps.interviews.services.answer_corpus import best_reference_answer

        ref = best_reference_answer(question_text, technology_id=technology_id)

    analysis = analyze_answer(
        answer_text=candidate_answer,
        question_text=question_text,
        reference_text=ref,
    )
    quality = _assess_quality(candidate_answer, question_text)
    star = _score_star_coverage(candidate_answer)
    # Detect the topic from the ANSWER ONLY. Concatenating question_text made
    # topic_detected non-null for essentially every answer (the question always
    # names its own subject), which vacuously upgraded quality in _refine_quality
    # and graded content-free answers as "correct" in scoring.correctness_signal.
    # The question's topic is still useful for feedback phrasing, so keep it
    # separately rather than folding it into the grading signal.
    topic = _detect_topic(candidate_answer)
    question_topic = _detect_topic(question_text)
    word_count = analysis.word_count

    # I1: depth/concrete used to be substring hits on generic English
    # ("because", "second", "request"). Stuffing topped the scale; real
    # explanations that avoided those words scored near zero.
    depth_score = score_technical_depth(candidate_answer)
    concrete_score = score_concrete_evidence(candidate_answer)
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

    # Anti-gaming: penalise on RELEVANCE, not on length. The old rule was
    # `word_count > 80 and relevance_score < 35`, which had both failure modes:
    # under the degenerate 2-doc TF-IDF a long genuine paraphrase scored ~3
    # relevance and ate the penalty, while a short keyword dump scored ~100 and
    # never tripped the word_count leg at all. Relevance is now a real signal
    # (analysis._relevance), so length is no longer part of the condition.
    if relevance_score < 20:
        composite *= 0.55
    elif relevance_score < 35:
        composite *= 0.75
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
        # Feedback wording ("expand on the <topic> aspect") should reference what
        # was ASKED, so it still works when the answer itself is off-topic.
        "feedback": _generate_feedback(quality, star, topic or question_topic, round_type),
    }
