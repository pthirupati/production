"""Real-time coaching / practice mode — instant tips after each answer.

Parity with interviewai.io practice mode: actionable tips after every answer.
Post-round phrase coaching references the candidate's own words — 100% free,
derived from the same phrase extractor the interviewer uses. No paid API.
"""

from __future__ import annotations

from apps.interviews.services.interview_ai import (
    _extract_quote_phrase,
    _score_star_coverage,
)
from apps.interviews.services.scorecard import _FILLER_WORDS, _count_phrases
from apps.interviews.services.system_design import detect_covered_dimensions as sd_dimensions


def coaching_tip(score_result: dict, *, round_type: str = "technical", answer_text: str = "") -> dict:
    """Return a single, prioritized coaching tip + headline signals for one answer."""
    quality = score_result.get("quality", "")
    score = score_result.get("score", 0)
    depth = score_result.get("depth_score", 0)
    concrete = score_result.get("concrete_score", 0)
    star = score_result.get("star_coverage") or {}
    word_count = score_result.get("word_count", 0)
    phrase = _extract_quote_phrase(answer_text or "")
    category = score_result.get("question_category") or ""

    tips: list[str] = []

    if quality == "skipped":
        tips.append("You skipped that — even a short structured attempt scores better than silence.")
    else:
        if phrase and quality in ("brief", "weak"):
            tips.append(
                f'You mentioned "{phrase}" — expand on that with concrete steps, tools, or a metric.'
            )
        elif phrase and score >= 70:
            tips.append(
                f'Strong thread on "{phrase}" — next time add a quantified outcome tied to it.'
            )

        if word_count and word_count < 30:
            tips.append("Too brief — aim for 4–6 sentences with a concrete example.")
        if depth < 40:
            tips.append("Add the 'why': explain trade-offs, root cause, or how it works under the hood.")
        if concrete < 30:
            tips.append("Make it concrete — name the tool, command, metric, or number you'd use.")

        if category == "system_design":
            covered = sd_dimensions(answer_text or "")
            missing = [d for d in ("capacity", "data", "cache", "reliability") if d not in covered]
            if missing:
                tips.append(
                    "System design — you haven't covered yet: "
                    + ", ".join(m.replace("_", " ") for m in missing[:3])
                    + ". Add estimates or trade-offs."
                )

        if round_type in ("behavioral", "hr"):
            missing = [k for k, v in star.items() if not v]
            if missing:
                tips.append(
                    "Use STAR — you're missing: " + ", ".join(m.capitalize() for m in missing) + "."
                )

        tone = score_result.get("memory_tone") or ""
        if tone == "nervous":
            tips.insert(0, "You sound a bit hesitant — pause, breathe, then give one clear sentence per point.")
        elif tone == "confident" and score >= 70:
            tips.append("Strong delivery — keep the same pace and add one metric per answer.")

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
        "quoted_phrase": phrase,
        "score": score,
        "quality": quality,
        "signals": {
            "depth": depth,
            "concrete": concrete,
            "word_count": word_count,
            "star_coverage": star,
        },
    }


def build_phrase_coaching(messages: list[dict], *, round_type: str = "technical") -> dict:
    """Post-round coaching that references phrases the candidate actually used.

    ``messages`` is a list of dicts with keys: content, score, metadata, role.
    """
    candidate_rows = [m for m in messages if m.get("role") == "candidate" and (m.get("content") or "").strip()]
    strengths: list[str] = []
    improvements: list[str] = []
    phrases_used: list[str] = []

    for row in candidate_rows:
        text = (row.get("content") or "").strip()
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        score = float(row.get("score") or meta.get("score") or 0)
        phrase = _extract_quote_phrase(text)
        if not phrase or phrase in phrases_used:
            continue
        phrases_used.append(phrase)
        quality = meta.get("quality", "")
        if score >= 75 or quality in ("strong", "adequate"):
            strengths.append(
                f'You explained "{phrase}" clearly — that read as a genuine strength.'
            )
        elif score < 55 or quality in ("weak", "brief"):
            improvements.append(
                f'When you said "{phrase}", the interviewer wanted more depth — '
                "add steps, tools, or a metric next time."
            )

    # STAR gaps across behavioral answers.
    if round_type in ("behavioral", "hr", "manager"):
        star_gaps = {"situation": 0, "task": 0, "action": 0, "result": 0}
        for row in candidate_rows:
            cov = _score_star_coverage(row.get("content") or "")
            for k, v in cov.items():
                if not v:
                    star_gaps[k] += 1
        worst = max(star_gaps, key=star_gaps.get)
        if star_gaps[worst] >= 2:
            improvements.append(
                f"Several answers skipped the {worst.capitalize()} in STAR — "
                "practice opening with context before jumping to the fix."
            )

    if round_type == "deep_dive":
        all_text = " ".join(r.get("content") or "" for r in candidate_rows)
        covered = sd_dimensions(all_text)
        for dim in ("capacity", "reliability", "data"):
            if dim not in covered:
                improvements.append(
                    f"System design practice: your answers rarely covered {dim.replace('_', ' ')} — "
                    "add estimates or failure modes explicitly."
                )

    return {
        "strengths": strengths[:4],
        "improvements": improvements[:5],
        "phrases_referenced": phrases_used[:8],
        "summary_line": _coaching_summary(strengths, improvements, phrases_used),
    }


def _coaching_summary(strengths: list, improvements: list, phrases: list) -> str:
    if phrases and improvements:
        return (
            f"We referenced {len(phrases)} phrase(s) from your answers — "
            f"{len(strengths)} landed well, {len(improvements)} need more depth."
        )
    if strengths:
        return "Your answers had clear technical threads — keep anchoring them with metrics."
    return "Practice adding concrete commands, numbers, and outcomes to each story."
