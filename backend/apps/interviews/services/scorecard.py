"""Structured candidate scorecard + heuristic confidence/communication analysis.

Parity with the leading AI-interview products' deliverables:
  * aiinterviews.io / interviewai.io — per-competency ratings + overall
    hire recommendation (strong-hire / hire / maybe / no-hire).
  * TestGorilla — communication/confidence read-out from free signals.

Everything here is DETERMINISTIC and 100% FREE — derived from the already-stored
transcript (``InterviewMessage``), per-answer score metadata, and timestamps.
No paid vision/NLP/LLM. Confidence is explicitly heuristic and labelled as such.
"""

from __future__ import annotations

import re

# Default competency set when a round/template doesn't define its own. These map
# onto the dimensions the round report already computes so the scorecard stays
# consistent with the gauges the candidate already sees.
_DEFAULT_COMPETENCIES = {
    "technical": [
        ("Technical depth", "technical_score"),
        ("Problem solving", "problem_solving_score"),
        ("Practical / tooling", "practical_score"),
        ("Communication", "communication_score"),
    ],
    "manager": [
        ("Process & ownership", "problem_solving_score"),
        ("Stakeholder communication", "communication_score"),
        ("Technical judgement", "technical_score"),
        ("Presence", "presence_score"),
    ],
    "hr": [
        ("Communication", "communication_score"),
        ("Motivation & fit", "presence_score"),
        ("Clarity of narrative", "problem_solving_score"),
    ],
    "deep_dive": [
        ("Technical depth", "technical_score"),
        ("System design", "problem_solving_score"),
        ("Trade-off reasoning", "practical_score"),
    ],
    "leadership": [
        ("Leadership & influence", "presence_score"),
        ("Communication", "communication_score"),
        ("Delivery under pressure", "problem_solving_score"),
    ],
}

# Spoken filler words that signal lower verbal confidence when over-used.
_FILLER_WORDS = (
    "um", "uh", "umm", "uhh", "er", "ah", "like", "you know", "i mean",
    "basically", "actually", "literally", "sort of", "kind of", "i guess",
    "maybe", "probably", "honestly", "stuff", "things", "whatever",
)

# Hedging phrases that reduce the assertiveness read.
_HEDGES = (
    "i think", "i guess", "i'm not sure", "not really sure", "maybe",
    "kind of", "sort of", "i suppose", "perhaps", "possibly", "might be",
)


def _rating_label(score: float) -> str:
    if score >= 80:
        return "excellent"
    if score >= 68:
        return "strong"
    if score >= 55:
        return "competent"
    if score >= 40:
        return "developing"
    return "needs work"


def build_competency_ratings(report_scores: dict, round_type: str, competencies=None) -> list[dict]:
    """Map the aggregate report scores onto named, rated competency rows.

    ``competencies`` (from a template) may be a list of names or of
    {name, dimension} dicts. Falls back to a per-round default set.
    """
    rows: list[dict] = []
    pairs: list[tuple[str, str]] = []
    if competencies:
        for c in competencies:
            if isinstance(c, dict):
                name = str(c.get("name") or "").strip()
                dim = str(c.get("dimension") or "overall_score")
            else:
                name = str(c).strip()
                dim = "overall_score"
            if name:
                pairs.append((name, dim))
    if not pairs:
        pairs = _DEFAULT_COMPETENCIES.get(round_type, _DEFAULT_COMPETENCIES["technical"])

    for name, dim in pairs:
        score = round(float(report_scores.get(dim, report_scores.get("overall_score", 0)) or 0), 1)
        rows.append({
            "name": name,
            "score": score,
            "rating": _rating_label(score),
            "note": _competency_note(name, score),
        })
    return rows


def _competency_note(name: str, score: float) -> str:
    if score >= 80:
        return f"Excellent — {name.lower()} was a clear strength."
    if score >= 68:
        return f"Strong {name.lower()}; consistent across answers."
    if score >= 55:
        return f"Competent {name.lower()} with room to add depth."
    if score >= 40:
        return f"Developing — {name.lower()} needs more concrete examples."
    return f"Below bar on {name.lower()} — focus practice here."


def recommend(overall_score: float, passed: bool, *, reason: str = "completed") -> str:
    """Overall hiring recommendation, mirroring the products' 4-band rubric."""
    if reason == "av_timeout":
        return "no_hire"
    if overall_score >= 82 and passed:
        return "strong_hire"
    if overall_score >= 68 and passed:
        return "hire"
    if overall_score >= 55:
        return "maybe"
    return "no_hire"


RECOMMENDATION_LABELS = {
    "strong_hire": "Strong hire",
    "hire": "Hire",
    "maybe": "Maybe / lean hire",
    "no_hire": "No hire",
}


def _count_phrases(text: str, phrases) -> int:
    low = f" {text.lower()} "
    total = 0
    for p in phrases:
        if " " in p:
            total += low.count(f" {p} ")
        else:
            total += len(re.findall(rf"\b{re.escape(p)}\b", low))
    return total


def analyze_confidence(messages, *, started_at=None, ended_at=None) -> dict:
    """Heuristic confidence/communication read-out from FREE signals only.

    Signals (all already captured, no paid API):
      * total words spoken + average answer length (verbosity / engagement),
      * filler-word and hedging density (verbal confidence),
      * answer pace = words per minute over the session clock,
      * how many questions were actually attempted vs skipped,
      * voice vs text input ratio (spoken answers read as more confident).

    Returns a 0–100 ``confidence_score`` plus the raw signals and a short,
    clearly-heuristic ``summary`` the UI labels as an estimate.
    """
    candidate_msgs = [m for m in messages if getattr(m, "role", "") == "candidate"]
    answers = [(m.content or "") for m in candidate_msgs]
    full_text = " ".join(answers)
    total_words = len(full_text.split())
    answered = [a for a in answers if len(a.strip()) >= 20]
    skipped = len(answers) - len(answered)
    avg_words = round(total_words / len(answered)) if answered else 0

    filler_count = _count_phrases(full_text, _FILLER_WORDS)
    hedge_count = _count_phrases(full_text, _HEDGES)
    filler_per_100 = round(100 * filler_count / total_words, 1) if total_words else 0.0

    voice_answers = sum(
        1 for m in candidate_msgs if getattr(m, "message_type", "") in ("voice", "audio")
    )
    voice_ratio = round(voice_answers / len(candidate_msgs), 2) if candidate_msgs else 0.0

    # Pace: words per minute across the session (when timing is available).
    wpm = None
    if started_at and ended_at:
        minutes = max(1.0, (ended_at - started_at).total_seconds() / 60.0)
        wpm = round(total_words / minutes, 1)

    # --- Compose a 0–100 confidence estimate from the signals. ---
    score = 62.0  # neutral baseline
    if avg_words >= 90:
        score += 14
    elif avg_words >= 55:
        score += 8
    elif avg_words >= 30:
        score += 2
    elif avg_words > 0:
        score -= 8
    # Filler / hedging penalties (capped).
    score -= min(18, filler_per_100 * 2.2)
    score -= min(8, hedge_count * 1.0)
    # Engagement: skipping a lot reads as low confidence.
    if answers:
        score -= min(16, skipped * 4)
    # Speaking answers aloud reads as more confident than typing.
    score += round(6 * voice_ratio)
    score = max(0, min(100, round(score)))

    summary = _confidence_summary(score, filler_per_100, avg_words, skipped, voice_ratio)

    return {
        "confidence_score": score,
        "is_heuristic": True,
        "total_words": total_words,
        "answers_attempted": len(answered),
        "answers_skipped": skipped,
        "avg_answer_words": avg_words,
        "filler_word_count": filler_count,
        "filler_per_100_words": filler_per_100,
        "hedging_count": hedge_count,
        "words_per_minute": wpm,
        "voice_answer_ratio": voice_ratio,
        "summary": summary,
    }


def _confidence_summary(score, filler_per_100, avg_words, skipped, voice_ratio) -> str:
    parts: list[str] = []
    if score >= 75:
        parts.append("Confident, articulate delivery overall.")
    elif score >= 58:
        parts.append("Generally steady communication with some hesitation.")
    else:
        parts.append("Communication read as tentative — work on assertiveness.")
    if filler_per_100 >= 4:
        parts.append(f"High filler-word use ({filler_per_100}/100 words) — tighten phrasing.")
    elif filler_per_100 > 0:
        parts.append(f"Filler-word use was low ({filler_per_100}/100 words).")
    if avg_words and avg_words < 30:
        parts.append("Answers were short — expand with specifics and examples.")
    elif avg_words >= 90:
        parts.append("Answers were thorough and well-developed.")
    if skipped:
        parts.append(f"Skipped {skipped} question(s).")
    if voice_ratio >= 0.5:
        parts.append("Answered aloud (good interview presence).")
    parts.append("(Heuristic estimate from text + timing — not a clinical measure.)")
    return " ".join(parts)


def build_scorecard_fields(round_obj, report_scores: dict, *, passed: bool, reason: str = "completed") -> dict:
    """One call the engine uses to compute every parity scorecard field for a
    round: recommendation, per-competency ratings, and confidence analysis.

    Best-effort and never raises — a malformed transcript degrades to empty
    fields rather than breaking ``end_round``.
    """
    overall = float(report_scores.get("overall_score", 0) or 0)
    try:
        template = getattr(round_obj.campaign, "template", None)
        competencies = list(getattr(template, "competencies", []) or []) if template else None
    except Exception:  # noqa: BLE001
        competencies = None
    try:
        ratings = build_competency_ratings(report_scores, round_obj.round_type, competencies)
    except Exception:  # noqa: BLE001
        ratings = []
    try:
        messages = list(round_obj.messages.all())
        confidence = analyze_confidence(
            messages,
            started_at=getattr(round_obj, "started_at", None),
            ended_at=getattr(round_obj, "ended_at", None),
        )
    except Exception:  # noqa: BLE001
        confidence = {}
    return {
        "recommendation": recommend(overall, passed, reason=reason),
        "competency_ratings": ratings,
        "confidence_analysis": confidence,
    }
