"""Select adaptive interview questions."""

from __future__ import annotations

import random

from django.db.models import Q

from apps.interviews.models import InterviewQuestion


def select_next_question(
    *,
    round_type: str,
    experience_level: str,
    technology_id=None,
    technology_tags: list | None = None,
    difficulty: int = 2,
    exclude_ids: list | None = None,
    category_preference: str | None = None,
    strong_streak: int = 0,
) -> InterviewQuestion | None:
    """Pick next question with adaptive difficulty."""
    exclude_ids = exclude_ids or []
    tags = technology_tags or []

    eff_difficulty = difficulty
    if strong_streak >= 5:
        eff_difficulty = min(5, difficulty + 2)
    elif strong_streak >= 3:
        eff_difficulty = min(5, difficulty + 1)

    qs = InterviewQuestion.objects.filter(is_active=True).exclude(id__in=exclude_ids)

    type_q = Q(round_types__contains=[round_type]) | Q(round_types=[])
    level_q = Q(experience_levels__contains=[experience_level]) | Q(experience_levels=[])
    qs = qs.filter(type_q, level_q)

    if technology_id:
        qs = qs.filter(Q(technology_id=technology_id) | Q(technology_id__isnull=True))
    if tags:
        for tag in tags[:3]:
            qs = qs.filter(Q(technology_tags__contains=[tag]) | Q(technology_tags=[]))

    if category_preference:
        cat_qs = qs.filter(category=category_preference, difficulty__gte=eff_difficulty - 1)
        if cat_qs.exists():
            qs = cat_qs

    qs = qs.filter(difficulty__gte=max(1, eff_difficulty - 1), difficulty__lte=min(5, eff_difficulty + 1))
    candidates = list(qs.order_by("?")[:20])
    if not candidates:
        candidates = list(
            InterviewQuestion.objects.filter(is_active=True)
            .exclude(id__in=exclude_ids)
            .order_by("?")[:10]
        )
    if not candidates:
        return None

    q = random.choice(candidates)
    InterviewQuestion.objects.filter(pk=q.pk).update(times_asked=q.times_asked + 1)
    return q


def round_category_mix(round_type: str, questions_asked: int) -> str | None:
    """Rotate categories through a round for variety."""
    if round_type == "hr":
        mix = ["casual", "behavioral", "behavioral", "casual"]
    elif round_type == "manager":
        mix = ["behavioral", "itil", "sla", "scenario", "tricky"]
    else:
        mix = ["casual", "technical", "troubleshooting", "technical", "scenario", "practical", "tricky"]
    return mix[questions_asked % len(mix)]
