"""Score candidate answers and generate round reports."""

from __future__ import annotations


# Correctness verdicts surfaced to the frontend (SHARED API CONTRACT). Distinct
# from "quality" (length/structure) — this is a *was-it-right* read derived from
# expected-keyword / detected-topic hit rate, all free/local.
CORRECTNESS_CORRECT = "correct"
CORRECTNESS_PARTIAL = "partial"
CORRECTNESS_OFF_BASE = "off_base"
CORRECTNESS_UNKNOWN = "unknown"


def correctness_signal(
    *,
    answer_text: str,
    quality: str,
    keyword_hit_rate: float,
    has_keywords: bool,
    topic_detected: str | None,
    command_validated: bool = False,
) -> str:
    """Deterministic correctness verdict for the prior answer (WS2).

    Returns one of ``correct | partial | off_base | unknown``. All free/local —
    derived from the same signals the scorer already computes:

      * A validated practical command/code is always ``correct``.
      * When the question carries ``expected_keywords`` we read the *hit rate*:
        >=60% correct, >=25% partial, otherwise off_base.
      * With no keywords we fall back to answer quality + whether a real topic was
        detected (so a substantive, on-topic answer still reads as correct/partial
        rather than always "unknown").
      * A skipped/empty answer is ``unknown`` (nothing to judge).
    """
    if command_validated:
        return CORRECTNESS_CORRECT

    if quality in ("skipped", ""):
        return CORRECTNESS_UNKNOWN

    if has_keywords:
        if keyword_hit_rate >= 0.60:
            return CORRECTNESS_CORRECT
        if keyword_hit_rate >= 0.25:
            return CORRECTNESS_PARTIAL
        # Some keywords expected but barely any landed → likely off-base, unless
        # the answer is clearly strong+on-topic (banks may be sparse), which we
        # soften to partial below.
        if quality == "strong" and topic_detected:
            return CORRECTNESS_PARTIAL
        return CORRECTNESS_OFF_BASE

    # No expected keywords to grade against — lean on quality + topic signal.
    if quality == "strong":
        return CORRECTNESS_CORRECT
    if quality == "adequate":
        return CORRECTNESS_CORRECT if topic_detected else CORRECTNESS_PARTIAL
    if quality == "brief":
        return CORRECTNESS_PARTIAL if topic_detected else CORRECTNESS_UNKNOWN
    # weak
    return CORRECTNESS_PARTIAL if topic_detected else CORRECTNESS_OFF_BASE


def score_answer(question, answer_text: str, metadata: dict | None = None) -> dict:
    """Richer scoring using interview_ai.compute_answer_scores — 100% free, no APIs."""
    from apps.interviews.services.interview_ai import _generate_feedback, _refine_quality, compute_answer_scores

    text = (answer_text or "").strip()
    meta = metadata or {}

    if not text:
        return {
            "score": 0,
            "quality": "skipped",
            "correctness": CORRECTNESS_UNKNOWN,
            "feedback": "No response recorded — we moved on to keep the interview on schedule.",
        }

    round_type = meta.get("round_type", "technical")
    keywords = list(question.expected_keywords) if question and question.expected_keywords else []
    if not keywords:
        keywords = list(meta.get("expected_keywords") or [])
    if question and question.technology_id:
        from apps.interviews.services.answer_corpus import corpus_keywords_for_technology

        corpus_kw = corpus_keywords_for_technology(question.technology_id)
        if corpus_kw:
            merged = list(dict.fromkeys([*(keywords or []), *corpus_kw]))
            keywords = merged

    breakdown = compute_answer_scores(
        candidate_answer=text,
        question_text=meta.get("question_text") or (question.question_text if question else ""),
        round_type=round_type,
        expected_keywords=keywords or None,
    )

    correctness = correctness_signal(
        answer_text=text,
        quality=breakdown["quality"],
        keyword_hit_rate=breakdown["keyword_hit_rate"],
        has_keywords=bool(keywords),
        topic_detected=breakdown["topic_detected"],
        command_validated=bool(meta.get("command_validated")),
    )

    quality = _refine_quality(
        breakdown["quality"],
        correctness=correctness,
        keyword_hit_rate=breakdown["keyword_hit_rate"],
        topic=breakdown["topic_detected"],
        word_count=breakdown["word_count"],
        has_keywords=bool(keywords),
    )

    score = breakdown["composite_score"]
    if meta.get("command_validated"):
        score = min(100, score + 15)

    correctness = correctness_signal(
        answer_text=text,
        quality=quality,
        keyword_hit_rate=breakdown["keyword_hit_rate"],
        has_keywords=bool(keywords),
        topic_detected=breakdown["topic_detected"],
        command_validated=bool(meta.get("command_validated")),
    )

    return {
        "score": round(score, 1),
        "quality": quality,
        "correctness": correctness,
        "feedback": _generate_feedback(quality, breakdown["star_coverage"], breakdown["topic_detected"], round_type),
        "keyword_hits": round(breakdown["keyword_hit_rate"] * len(keywords)) if keywords else 0,
        "keyword_hit_rate": breakdown["keyword_hit_rate"],
        "word_count": breakdown["word_count"],
        "depth_score": breakdown["depth_score"],
        "concrete_score": breakdown["concrete_score"],
        "star_score": breakdown["star_score"],
        "star_coverage": breakdown["star_coverage"],
        "topic_detected": breakdown["topic_detected"],
    }


def aggregate_round_scores(message_scores: list[float], round_type: str = "technical") -> dict:
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
    dims = {
        "technical_score": round(min(100, avg * 1.05), 1),
        "communication_score": round(min(100, avg * 0.95 + 5), 1),
        "problem_solving_score": round(min(100, avg), 1),
        "practical_score": round(min(100, avg * 1.1), 1),
        "presence_score": 72.0,
        "resume_alignment_score": 68.0,
    }
    try:
        from apps.interviews.services.interview_types import get_eval_weights

        weights = get_eval_weights(round_type)
        w_sum = sum(weights.values()) or 1.0
        overall = sum(dims.get(k, avg) * weights.get(k, 0) for k in weights) / w_sum
    except Exception:  # noqa: BLE001
        overall = avg
    return {
        **dims,
        "overall_score": round(overall, 1),
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
    if round_type in ("devops_debug", "sre_oncall"):
        strengths.append("Worked through incident methodology and on-call communication.")
    if round_type == "system_design":
        strengths.append("Discussed architecture trade-offs and scaling dimensions.")
    if round_type == "live_coding":
        strengths.append("Engaged with hands-on coding and implementation details.")

    if weak:
        improvements.append(f"Deepen answers where you scored below 55 — {len(weak)} area(s) flagged.")
    improvements.append("Add quantified outcomes (MTTR, uptime, cost) when describing past work.")
    improvements.append("Practice concise STAR format for behavioral prompts.")
    if round_type == "technical":
        improvements.append("Run FixitLab scenario labs for hands-on muscle memory.")

    return strengths[:5], improvements[:5]
