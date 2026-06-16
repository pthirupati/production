"""Build multi-round interview campaigns."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.interviews.models import InterviewCampaign, InterviewRound

ROUND_PLAN = {
    3: [
        ("technical", 45, "Round 1 — Technical Deep Dive"),
        ("manager", 30, "Round 2 — Techno-Manager"),
        ("hr", 20, "Round 3 — HR & Culture"),
    ],
    4: [
        ("technical", 45, "Round 1 — Technical"),
        ("manager", 30, "Round 2 — Techno-Manager"),
        ("deep_dive", 30, "Round 3 — Deep Dive"),
        ("hr", 20, "Round 4 — HR"),
    ],
    5: [
        ("technical", 45, "Round 1 — Technical"),
        ("manager", 30, "Round 2 — Techno-Manager"),
        ("deep_dive", 30, "Round 3 — Deep Dive"),
        ("leadership", 20, "Round 4 — Leadership"),
        ("hr", 20, "Round 5 — HR"),
    ],
}

PERSONAS = {
    "technical": ("Alex Chen", "indian-female"),
    "manager": ("Priya Sharma", "indian-male"),
    "hr": ("Jordan Blake", "us-female"),
    "deep_dive": ("Sam Okonkwo", "uk-male"),
    "leadership": ("Maria Santos", "us-female"),
}


def create_campaign_rounds(campaign: InterviewCampaign) -> list[InterviewRound]:
    plan = ROUND_PLAN.get(campaign.round_count, ROUND_PLAN[3])
    rounds = []
    for idx, (rtype, duration, title) in enumerate(plan, start=1):
        persona, voice = PERSONAS.get(rtype, PERSONAS["technical"])
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
            )
        )
    return InterviewRound.objects.bulk_create(rounds)


def unlock_next_round(campaign: InterviewCampaign, passed_round: InterviewRound) -> InterviewRound | None:
    nxt = (
        InterviewRound.objects.filter(
            campaign=campaign,
            round_number=passed_round.round_number + 1,
        ).first()
    )
    if not nxt:
        return None
    deadline = timezone.now() + timedelta(hours=48)
    nxt.status = "schedulable"
    nxt.schedule_deadline = deadline
    nxt.save(update_fields=["status", "schedule_deadline"])
    return nxt
