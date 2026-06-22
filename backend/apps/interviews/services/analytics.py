"""Performance analytics for candidates and recruiters.

Parity with the products' dashboards:
  * Candidate view — score trend across attempts + a skill/competency radar
    (interviewai.io progress tracking).
  * Recruiter view — compare & rank candidates on a role/template
    (aiinterviews.io / TestGorilla candidate comparison).

Reuses the EXISTING interview result models (``InterviewRound`` / ``InterviewReport``
/ ``InterviewCampaign``). 100% local aggregation — no paid analytics service.
"""

from __future__ import annotations

from apps.interviews.models import InterviewCampaign, InterviewReport, InterviewRound

# The radar axes — the six dimensions every report already scores.
RADAR_DIMENSIONS = [
    ("technical_score", "Technical"),
    ("communication_score", "Communication"),
    ("problem_solving_score", "Problem solving"),
    ("practical_score", "Practical"),
    ("presence_score", "Presence"),
    ("resume_alignment_score", "Resume fit"),
]


def candidate_dashboard(user) -> dict:
    """Trend + radar + headline stats for one candidate across all their rounds."""
    reports = list(
        InterviewReport.objects.filter(round__campaign__user=user)
        .select_related("round", "round__campaign")
        .order_by("generated_at")
    )

    trend = []
    radar_acc = {key: [] for key, _ in RADAR_DIMENSIONS}
    recommendation_counts: dict[str, int] = {}
    for rep in reports:
        rnd = rep.round
        trend.append({
            "round_id": str(rnd.id),
            "campaign_id": str(rnd.campaign_id),
            "round_type": rnd.round_type,
            "title": rnd.title,
            "overall_score": round(rep.overall_score or 0, 1),
            "passed": rep.passed,
            "recommendation": rep.recommendation,
            "date": rep.generated_at.isoformat(),
        })
        for key, _ in RADAR_DIMENSIONS:
            radar_acc[key].append(float(getattr(rep, key, 0) or 0))
        if rep.recommendation:
            recommendation_counts[rep.recommendation] = recommendation_counts.get(rep.recommendation, 0) + 1

    radar = []
    for key, label in RADAR_DIMENSIONS:
        vals = radar_acc[key]
        radar.append({
            "dimension": label,
            "key": key,
            "score": round(sum(vals) / len(vals), 1) if vals else 0,
        })

    scores = [t["overall_score"] for t in trend]
    campaigns_total = InterviewCampaign.objects.filter(user=user, is_sample=False).count()
    campaigns_completed = InterviewCampaign.objects.filter(
        user=user, is_sample=False, status="completed"
    ).count()

    # Improvement = latest vs first attempt (positive = getting better).
    improvement = round(scores[-1] - scores[0], 1) if len(scores) >= 2 else 0.0

    return {
        "attempts": len(trend),
        "rounds_total": len(trend),
        "campaigns_total": campaigns_total,
        "campaigns_completed": campaigns_completed,
        "best_score": round(max(scores), 1) if scores else 0,
        "latest_score": scores[-1] if scores else 0,
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "pass_rate": round(100 * sum(1 for t in trend if t["passed"]) / len(trend), 1) if trend else 0,
        "improvement": improvement,
        "trend": trend,
        "radar": radar,
        "recommendation_breakdown": recommendation_counts,
    }


def _campaign_dimension_avgs(campaign: InterviewCampaign) -> dict:
    reports = InterviewReport.objects.filter(round__campaign=campaign)
    out = {}
    for key, _ in RADAR_DIMENSIONS:
        vals = [float(getattr(r, key, 0) or 0) for r in reports]
        out[key] = round(sum(vals) / len(vals), 1) if vals else 0
    return out


def recruiter_comparison(*, template_id=None, technology_id=None, limit: int = 100) -> dict:
    """Rank completed campaigns (candidates) for a role/template so a recruiter
    can compare them side by side. Reuses overall_score + the report dimensions.
    """
    qs = (
        InterviewCampaign.objects.filter(status="completed", is_sample=False)
        .select_related("user", "primary_technology", "template")
        .order_by("-overall_score")
    )
    if template_id:
        qs = qs.filter(template_id=template_id)
    if technology_id:
        qs = qs.filter(primary_technology_id=technology_id)
    qs = qs[:limit]

    rows = []
    for c in qs:
        dims = _campaign_dimension_avgs(c)
        # Most recent report's recommendation is the headline verdict.
        last_report = (
            InterviewReport.objects.filter(round__campaign=c)
            .order_by("-generated_at")
            .first()
        )
        rows.append({
            "campaign_id": str(c.id),
            "candidate": {
                "id": c.user_id,
                "name": (c.user.get_full_name() or c.user.username or c.user.email),
                "email": c.user.email,
            },
            "title": c.title,
            "technology": c.primary_technology.name if c.primary_technology else "",
            "template": c.template.name if c.template else "",
            "experience_level": c.experience_level,
            "overall_score": round(c.overall_score or 0, 1),
            "recommendation": last_report.recommendation if last_report else "",
            "round_count": c.round_count,
            "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            "dimensions": dims,
        })

    # Stable rank index (already ordered by score desc).
    for i, row in enumerate(rows, start=1):
        row["rank"] = i

    return {
        "count": len(rows),
        "dimensions": [{"key": k, "label": label} for k, label in RADAR_DIMENSIONS],
        "candidates": rows,
    }
