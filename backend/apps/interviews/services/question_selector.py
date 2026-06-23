"""Select adaptive interview questions."""

from __future__ import annotations

import random

from django.db.models import Q
from django.db.utils import NotSupportedError

from apps.interviews.models import InterviewQuestion


def _materialize(qs, limit):
    """Evaluate a queryset, falling back gracefully when the DB backend does not
    support JSON ``__contains`` lookups (e.g. sqlite in tests/CI). On Postgres
    (dev/prod) the lookup is native and this just returns the rows."""
    try:
        return list(qs.order_by("?")[:limit])
    except NotSupportedError:
        return None


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
        try:
            if cat_qs.exists():
                qs = cat_qs
        except NotSupportedError:
            pass

    qs = qs.filter(difficulty__gte=max(1, eff_difficulty - 1), difficulty__lte=min(5, eff_difficulty + 1))
    candidates = _materialize(qs, 20)
    if not candidates:
        # Backend lacks JSON contains support, or the narrow filter matched
        # nothing — fall back to any active question so the bot always has a
        # question to ask (never silently returns None on a healthy bank).
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
    """Rotate categories through a round for variety.

    WS4 — real interviews OPEN human, not with a drill. The first one or two
    slots map to a warm-up: ``intro`` ("tell me about yourself") then
    ``experience`` (most-recent-role) for EVERY round type, so the question
    generator serves an opener before any technical cross-questioning. HR rounds
    additionally get a ``personal`` / fun slot up front. After the opening slots,
    the per-round rotation below takes over as before.
    """
    # Opening warm-up slots, served before the regular rotation (WS4).
    if round_type == "hr":
        opening = ["intro", "experience", "personal"]
    else:
        opening = ["intro", "experience"]
    if questions_asked < len(opening):
        return opening[questions_asked]

    # Index into the regular rotation *after* the opening slots are consumed.
    idx = questions_asked - len(opening)
    if round_type == "hr":
        mix = ["casual", "behavioral", "behavioral", "casual"]
    elif round_type == "manager":
        mix = ["behavioral", "itil", "sla", "scenario", "tricky"]
    else:
        mix = ["casual", "technical", "troubleshooting", "technical", "scenario", "practical", "tricky"]
    return mix[idx % len(mix)]
