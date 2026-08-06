"""Score candidate answers and generate round reports."""

from __future__ import annotations

import re

# Correctness verdicts surfaced to the frontend (SHARED API CONTRACT). Distinct
# from "quality" (length/structure) — this is a *was-it-right* read derived from
# expected-keyword / detected-topic hit rate, all free/local.
CORRECTNESS_CORRECT = "correct"
CORRECTNESS_PARTIAL = "partial"
CORRECTNESS_OFF_BASE = "off_base"
CORRECTNESS_UNKNOWN = "unknown"

# Minimum relevance (0-100) an answer must clear before topic_detected is allowed
# to mean "correct" on the no-keywords path. A pure question-echo caps at exactly
# 35 by construction: conversation/analysis._relevance scores echo at weight 0.35
# and gives the remaining 0.65 to substance, so an answer that adds nothing of its
# own cannot exceed 0.35. Measured on the CrashLoopBackOff question, an 8-word echo
# lands on 35 while the tersest genuine answer ("kubectl logs --previous and
# kubectl describe pod ...") scores 46 — the floor sits in that gap.
CORRECTNESS_RELEVANCE_FLOOR = 40

_HEDGING = re.compile(
    r"\b(i think|maybe|probably|sort of|kind of|i guess|not sure|i'm not sure|"
    r"i believe|perhaps|might have|could be)\b",
    re.I,
)
_FILLERS = re.compile(
    r"\b(um+|uh+|er+|ah+|like|you know|basically|literally)\b",
    re.I,
)


def correctness_signal(
    *,
    answer_text: str,
    quality: str,
    keyword_hit_rate: float,
    has_keywords: bool,
    topic_detected: str | None,
    command_validated: bool = False,
    relevance_score: int | None = None,
) -> str:
    """Deterministic correctness verdict for the prior answer (WS2)."""
    if command_validated:
        return CORRECTNESS_CORRECT

    if quality in ("skipped", ""):
        return CORRECTNESS_UNKNOWN

    if has_keywords:
        if keyword_hit_rate >= 0.60:
            return CORRECTNESS_CORRECT
        if keyword_hit_rate >= 0.25:
            return CORRECTNESS_PARTIAL
        if quality == "strong" and topic_detected:
            return CORRECTNESS_PARTIAL
        return CORRECTNESS_OFF_BASE

    # No expected keywords (the generated-question path): quality is length and
    # structure driven, so "strong" alone says nothing about whether the answer was
    # RIGHT. Requiring an on-topic signal is what stops fluent, content-free prose
    # from grading correct. This is only meaningful because topic_detected is now
    # derived from the answer alone (see conversation/scorer.py) — when it was
    # detected from question+answer it was always truthy and this guard was a no-op.
    #
    # topic_detected on its own is still too weak, because _detect_topic() fires on
    # the question's OWN vocabulary handed back verbatim: "kubernetes pod stuck
    # crashloopbackoff debug how would you" detects "kubernetes" from nothing but
    # the echoed tokens and used to grade CORRECT. Relevance is what separates an
    # echo from an answer, so require it too — see CORRECTNESS_RELEVANCE_FLOOR.
    # relevance_score is None for callers that cannot supply it (the
    # interview_ai.compute_answer_scores fallback does not compute one), and those
    # keep the topic-only behaviour rather than being graded on a missing signal.
    on_topic = bool(topic_detected) and (
        relevance_score is None or relevance_score >= CORRECTNESS_RELEVANCE_FLOOR
    )
    if quality in ("strong", "adequate"):
        return CORRECTNESS_CORRECT if on_topic else CORRECTNESS_PARTIAL
    if quality == "brief":
        return CORRECTNESS_PARTIAL if topic_detected else CORRECTNESS_UNKNOWN
    return CORRECTNESS_PARTIAL if topic_detected else CORRECTNESS_OFF_BASE


def _presence_from_answers(rows: list[dict]) -> float:
    """Confidence/presence heuristic from filler density, hedging, skips, brevity."""
    if not rows:
        return 70.0
    scores: list[float] = []
    for row in rows:
        text = (row.get("content") or "").strip()
        meta = row.get("metadata") or {}
        quality = meta.get("quality") or row.get("quality") or ""
        if quality == "skipped" or meta.get("user_skip"):
            scores.append(35.0)
            continue
        if not text:
            scores.append(40.0)
            continue
        words = text.split()
        wc = max(len(words), 1)
        filler_hits = len(_FILLERS.findall(text.lower()))
        hedge_hits = len(_HEDGING.findall(text.lower()))
        filler_ratio = filler_hits / wc
        hedge_ratio = hedge_hits / wc
        base = 78.0
        base -= min(35, filler_ratio * 120)
        base -= min(25, hedge_ratio * 80)
        if quality == "strong":
            base += 8
        elif quality == "weak":
            base -= 12
        elif quality == "brief":
            base -= 6
        scores.append(max(20.0, min(100.0, base)))
    return round(sum(scores) / len(scores), 1)


def _resume_alignment_from_answers(rows: list[dict], resume_snapshot: dict | None) -> float:
    """Overlap between combined answers and resume/profile snapshot."""
    snap = resume_snapshot or {}
    combined = " ".join((row.get("content") or "") for row in rows).strip()
    if not combined or len(combined) < 20:
        return 65.0
    try:
        from apps.interviews.services.resume_parser import score_resume

        parsed = snap.get("resume_parsed") or {}
        result = score_resume(
            parsed,
            resume_text=combined,
            target_technology=snap.get("primary_technology_name") or "",
            target_role=snap.get("target_role") or "",
            experience_level=snap.get("experience_level") or "mid",
            years_experience=int(snap.get("years_experience") or 0),
        )
        if result.get("overall_score") is None:
            return 65.0
        return float(result["overall_score"])
    except Exception:  # noqa: BLE001
        return 65.0


def _build_star_analysis(star_coverage: dict | None) -> dict:
    """STAR 0–4 badge payload for AIScorecard.jsx."""
    if not star_coverage:
        return {}
    score = sum(1 for v in star_coverage.values() if v)
    labels = {"situation": "Situation", "task": "Task", "action": "Action", "result": "Result"}
    missing = [labels[k] for k, v in star_coverage.items() if not v]
    note = ""
    if missing:
        note = f"Strengthen your answer by adding {' and '.join(missing[:2])}."
    return {
        "star_score": score,
        "missing_components": missing,
        "coaching_note": note,
    }


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

    try:
        from apps.interviews.services.conversation.scorer import compute_semantic_scores

        breakdown = compute_semantic_scores(
            candidate_answer=text,
            question_text=meta.get("question_text") or (question.question_text if question else ""),
            round_type=round_type,
            expected_keywords=keywords or None,
        )
    except Exception:  # noqa: BLE001
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
        relevance_score=breakdown.get("relevance_score"),
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
        relevance_score=breakdown.get("relevance_score"),
    )

    star_coverage = breakdown["star_coverage"]
    return {
        "score": round(score, 1),
        "quality": quality,
        "correctness": correctness,
        "feedback": breakdown.get("feedback") or _generate_feedback(
            quality, star_coverage, breakdown["topic_detected"], round_type
        ),
        "keyword_hits": round(breakdown["keyword_hit_rate"] * len(keywords)) if keywords else 0,
        "keyword_hit_rate": breakdown["keyword_hit_rate"],
        "word_count": breakdown["word_count"],
        "depth_score": breakdown["depth_score"],
        "concrete_score": breakdown["concrete_score"],
        "star_score": breakdown["star_score"],
        "star_coverage": star_coverage,
        "star_analysis": _build_star_analysis(star_coverage),
        "topic_detected": breakdown["topic_detected"],
        "relevance_score": breakdown.get("relevance_score"),
    }


def aggregate_round_scores(
    message_scores: list[float] | None = None,
    *,
    round_type: str = "technical",
    answer_rows: list[dict] | None = None,
    resume_snapshot: dict | None = None,
) -> dict:
    """Aggregate per-answer signals into independent dimension scores."""
    rows = answer_rows or []
    scores = message_scores or [float(r.get("score") or 0) for r in rows if r.get("score") is not None]

    if not scores and not rows:
        return {
            "technical_score": 0,
            "communication_score": 0,
            "problem_solving_score": 0,
            "practical_score": 0,
            "presence_score": 0,
            "resume_alignment_score": 0,
            "overall_score": 0,
        }

    def _avg(key: str, fallback_scores: list[float]) -> float:
        vals = [float(r.get(key)) for r in rows if r.get(key) is not None]
        if vals:
            return sum(vals) / len(vals)
        return sum(fallback_scores) / len(fallback_scores) if fallback_scores else 0.0

    technical_vals = []
    comm_vals = []
    problem_vals = []
    practical_vals = []
    for row in rows:
        meta = row.get("metadata") or {}
        depth = float(row.get("depth_score") or meta.get("depth_score") or 0)
        concrete = float(row.get("concrete_score") or meta.get("concrete_score") or 0)
        star = float(row.get("star_score") or meta.get("star_score") or 0)
        rel = float(row.get("relevance_score") or meta.get("relevance_score") or row.get("score") or 0)
        kw = float(row.get("keyword_hit_rate") or meta.get("keyword_hit_rate") or 0) * 100
        technical_vals.append(0.45 * depth + 0.35 * rel + 0.20 * kw)
        comm_vals.append(0.55 * star + 0.45 * rel)
        problem_vals.append(0.60 * concrete + 0.40 * rel)
        if meta.get("command_validated") or row.get("command_validated"):
            practical_vals.append(min(100.0, float(row.get("score") or 80) + 10))
        elif round_type in ("live_coding", "devops_debug", "sre_oncall", "technical"):
            practical_vals.append(0.50 * concrete + 0.50 * rel)

    fallback = scores or [0.0]
    dims = {
        "technical_score": round(min(100, _avg("depth_score", technical_vals or fallback)), 1),
        "communication_score": round(min(100, _avg("star_score", comm_vals or fallback)), 1),
        "problem_solving_score": round(min(100, _avg("concrete_score", problem_vals or fallback)), 1),
        "practical_score": round(
            min(100, sum(practical_vals) / len(practical_vals) if practical_vals else _avg("score", fallback)),
            1,
        ),
        "presence_score": _presence_from_answers(rows),
        "resume_alignment_score": _resume_alignment_from_answers(rows, resume_snapshot),
    }
    try:
        from apps.interviews.services.interview_types import get_eval_weights

        weights = get_eval_weights(round_type)
        w_sum = sum(weights.values()) or 1.0
        overall = sum(dims.get(k, 0) * weights.get(k, 0) for k in weights) / w_sum
    except Exception:  # noqa: BLE001
        overall = sum(scores) / len(scores) if scores else 0
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
