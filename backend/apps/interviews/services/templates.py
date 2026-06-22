"""Interview templates / job-role library + question-set builder.

Parity with TestGorilla's job-role library and interviewai.io role templates:
a recruiter (or admin) defines a reusable template — round plan, target
tech/level, competencies, and an optional pinned question-set drawn from the
existing admin ``InterviewQuestion`` bank. Candidates can launch an interview
from a template in one click.

100% free — templates only configure the existing (free, generation-first)
engine; pinned questions seed the round and carry practical configs.
"""

from __future__ import annotations

from apps.interviews.models import InterviewCampaign, InterviewRound, InterviewTemplate
from apps.interviews.services.campaign_builder import PERSONAS, ROUND_PLAN

# Built-in starter templates so the gallery is never empty on a fresh install.
# These reference technology by NAME (resolved to a row if it exists, else left
# null — the generator still works from the name in the snapshot).
DEFAULT_TEMPLATES = [
    {
        "slug": "devops-engineer-mid",
        "name": "DevOps Engineer (Mid)",
        "role_title": "DevOps Engineer",
        "description": "CI/CD, containers, IaC, and incident response for a mid-level DevOps role.",
        "technology_name": "Docker",
        "technology_tags": ["kubernetes", "terraform", "ci_cd", "linux"],
        "experience_level": "mid",
        "round_count": 3,
        "competencies": ["Technical depth", "Problem solving", "Practical / tooling", "Communication"],
    },
    {
        "slug": "sre-senior",
        "name": "Site Reliability Engineer (Senior)",
        "role_title": "Senior SRE",
        "description": "SLOs, on-call, observability, and large-scale reliability for a senior SRE.",
        "technology_name": "Kubernetes",
        "technology_tags": ["monitoring", "kubernetes", "linux", "aws"],
        "experience_level": "senior",
        "round_count": 4,
        "competencies": ["Technical depth", "System design", "Incident response", "Communication"],
    },
    {
        "slug": "backend-engineer-mid",
        "name": "Backend Engineer (Mid)",
        "role_title": "Backend Engineer",
        "description": "APIs, databases, and system design for a mid-level backend engineer.",
        "technology_name": "Python",
        "technology_tags": ["python", "database", "ci_cd"],
        "experience_level": "mid",
        "round_count": 3,
        "competencies": ["Technical depth", "Problem solving", "System design", "Communication"],
    },
    {
        "slug": "cloud-engineer-mid",
        "name": "Cloud Engineer (Mid)",
        "role_title": "Cloud Engineer",
        "description": "AWS architecture, networking, and cost-aware design for a cloud engineer.",
        "technology_name": "AWS",
        "technology_tags": ["aws", "terraform", "networking", "security"],
        "experience_level": "mid",
        "round_count": 3,
        "competencies": ["Technical depth", "Practical / tooling", "Trade-off reasoning", "Communication"],
    },
]


def ensure_default_templates() -> int:
    """Idempotently create the built-in starter templates. Returns count created."""
    from apps.question_bank.models import Technology

    created = 0
    for order, spec in enumerate(DEFAULT_TEMPLATES):
        if InterviewTemplate.objects.filter(slug=spec["slug"]).exists():
            continue
        tech = None
        tech_name = spec.get("technology_name")
        if tech_name:
            tech = Technology.objects.filter(name__iexact=tech_name).first()
        InterviewTemplate.objects.create(
            slug=spec["slug"],
            name=spec["name"],
            role_title=spec["role_title"],
            description=spec["description"],
            primary_technology=tech,
            technology_tags=spec.get("technology_tags", []),
            experience_level=spec.get("experience_level", "mid"),
            round_count=spec.get("round_count", 3),
            competencies=spec.get("competencies", []),
            is_public=True,
            is_active=True,
            order=order,
        )
        created += 1
    return created


def _round_plan_for_template(template: InterviewTemplate):
    """The template's explicit round_plan, or the default plan for its count."""
    if template.round_plan:
        plan = []
        for entry in template.round_plan:
            if not isinstance(entry, dict):
                continue
            rtype = entry.get("round_type", "technical")
            duration = int(entry.get("duration_minutes", 30) or 30)
            title = entry.get("title") or f"{rtype.title()} round"
            plan.append((rtype, duration, title))
        if plan:
            return plan
    return ROUND_PLAN.get(template.round_count, ROUND_PLAN[3])


def create_rounds_from_template(campaign: InterviewCampaign, template: InterviewTemplate) -> list[InterviewRound]:
    """Build a campaign's rounds from a template (round plan + personas + pass
    threshold + async/live mode). Mirrors ``campaign_builder.create_campaign_rounds``
    but honours the template configuration.
    """
    plan = _round_plan_for_template(template)
    snap = campaign.profile_snapshot or {}
    profile_voice = snap.get("voice_id") if isinstance(snap, dict) else None
    rounds = []
    for idx, (rtype, duration, title) in enumerate(plan, start=1):
        persona, voice = PERSONAS.get(rtype, PERSONAS["technical"])
        if profile_voice and profile_voice not in ("default", ""):
            voice = profile_voice
        status = "schedulable" if idx == 1 else "locked"
        rounds.append(
            InterviewRound(
                campaign=campaign,
                round_number=idx,
                round_type=rtype,
                title=title,
                duration_minutes=duration,
                status=status,
                persona_name=persona,
                persona_voice_id=voice,
                pass_threshold=template.pass_threshold or 65.0,
                mode=campaign.mode or "live",
            )
        )
    created = InterviewRound.objects.bulk_create(rounds)
    InterviewTemplate.objects.filter(pk=template.pk).update(times_used=template.times_used + 1)
    return created
