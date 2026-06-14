"""Learning path progress helpers."""

from __future__ import annotations

from apps.progress.models import LearningPathProgress, UserScenarioProgress


def _path_slugs(technology) -> list[str]:
    path = getattr(technology, "learning_path", None) or []
    return [s.get("scenario_slug") for s in path if s.get("scenario_slug")]


def get_learning_path_progress(user, technology) -> dict:
    """Return completed slugs and counts for a technology learning path."""
    slugs = _path_slugs(technology)
    if not slugs:
        return {"completed_slugs": [], "steps_total": 0, "steps_completed": 0, "percent": 0}

    record, _ = LearningPathProgress.objects.get_or_create(
        user=user,
        technology=technology,
        defaults={"completed_slugs": []},
    )
    completed = set(record.completed_slugs or [])
    # Reconcile with scenario progress (source of truth)
    done_in_db = set(
        UserScenarioProgress.objects.filter(
            user=user,
            scenario__technology=technology,
            scenario__slug__in=slugs,
            completed=True,
        ).values_list("scenario__slug", flat=True)
    )
    merged = sorted(completed | done_in_db)
    if merged != list(record.completed_slugs or []):
        record.completed_slugs = merged
        record.save(update_fields=["completed_slugs", "updated_at"])

    total = len(slugs)
    done = len(merged)
    return {
        "completed_slugs": merged,
        "steps_total": total,
        "steps_completed": done,
        "percent": round(done / total * 100, 1) if total else 0,
    }


def sync_learning_path_on_completion(user, scenario) -> None:
    """Mark learning-path step when user completes a scenario."""
    tech = scenario.technology
    slugs = _path_slugs(tech)
    if scenario.slug not in slugs:
        return
    record, _ = LearningPathProgress.objects.get_or_create(
        user=user,
        technology=tech,
        defaults={"completed_slugs": []},
    )
    completed = list(record.completed_slugs or [])
    if scenario.slug not in completed:
        completed.append(scenario.slug)
        record.completed_slugs = completed
        record.save(update_fields=["completed_slugs", "updated_at"])
