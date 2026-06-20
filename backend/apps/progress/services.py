from django.db import models
from django.db.models import Sum, Count, Avg, Min, Q
from django.utils import timezone
from .models import UserScenarioProgress, UserAchievement
import logging

logger = logging.getLogger(__name__)


def record_attempt(user, scenario, score, completed=False, time_seconds=None, hints_used=0):
    """Record a lab attempt and update best records."""
    progress, _ = UserScenarioProgress.objects.get_or_create(
        user=user,
        scenario=scenario,
    )

    progress.attempts += 1
    progress.last_attempt_at = timezone.now()

    if score > progress.best_score:
        progress.best_score = score
        # Update hints for best score attempt
        progress.hints_used_best = hints_used

    # Track best time (lower is better, only for completed attempts)
    if completed and time_seconds is not None:
        if progress.best_time is None or time_seconds < progress.best_time:
            progress.best_time = time_seconds

    if completed:
        progress.completed = True
        if not progress.completed_at:
            progress.completed_at = timezone.now()

    progress.save()

    # Invalidate the cached progress for this user
    from django.core.cache import cache as _cache
    _cache.delete(f"user_progress:{user.id}")

    # Check and award achievements after recording
    if completed:
        check_achievements(user, scenario, score, time_seconds, hints_used)

    return progress


def check_achievements(user, scenario, score, time_seconds, hints_used):
    """Check and award achievements based on the user's progress."""
    awarded = []

    def _award(achievement_type):
        obj, created = UserAchievement.objects.get_or_create(
            user=user, achievement=achievement_type
        )
        if created:
            awarded.append(achievement_type)
            logger.info(f"Achievement awarded: {achievement_type} to {user.username}")

    # Pre-aggregate all needed counts in 2 queries instead of N+1
    from apps.question_bank.models import Scenario as ScenarioModel
    from django.db.models import Count

    # 1 query: per-difficulty completed count for this user
    diff_done_map = {
        row["scenario__difficulty"]: row["cnt"]
        for row in UserScenarioProgress.objects.filter(user=user, completed=True)
        .values("scenario__difficulty")
        .annotate(cnt=Count("id"))
    }
    completed_count = sum(diff_done_map.values())

    # 1 query: total active scenarios per difficulty
    diff_total_map = {
        row["difficulty"]: row["cnt"]
        for row in ScenarioModel.objects.filter(is_active=True)
        .values("difficulty")
        .annotate(cnt=Count("id"))
    }

    if completed_count >= 1:
        _award("first_solve")
    if completed_count >= 10:
        _award("ten_solves")
    if completed_count >= 50:
        _award("fifty_solves")
    if completed_count >= 100:
        _award("hundred_solves")

    # Speed Demon — completed in under 5 minutes
    if time_seconds is not None and time_seconds < 300:
        _award("speed_demon")

    # No Hints Used
    if hints_used == 0:
        _award("no_hints")

    # Perfect Score (100)
    if score >= 100:
        _award("perfect_score")

    # Difficulty mastery — completed all scenarios of a difficulty level
    difficulty = getattr(scenario, "difficulty", None)
    if difficulty:
        total_of_difficulty = diff_total_map.get(difficulty, 0)
        completed_of_difficulty = diff_done_map.get(difficulty, 0)
        if total_of_difficulty > 0 and completed_of_difficulty >= total_of_difficulty:
            mastery_map = {"easy": "easy_master", "medium": "medium_master", "hard": "hard_master"}
            achievement_key = mastery_map.get(difficulty)
            if achievement_key:
                _award(achievement_key)

    # Streak tracking — check consecutive days with completed labs
    _check_streaks(user)

    # Send notification for each new achievement
    if awarded:
        _notify_achievements(user, awarded)

    return awarded


def compute_current_streak(user) -> int:
    """Return the user's current consecutive-day solving streak (today-anchored).

    A streak is the number of consecutive days, counting back from today, on
    which the user completed at least one scenario. If they haven't solved
    today *or* yesterday, the streak is 0 (a gap broke it). Pure read — no
    side effects — so it's safe to call from any endpoint.
    """
    from django.db.models.functions import TruncDate

    recent_dates = (
        UserScenarioProgress.objects.filter(
            user=user,
            completed=True,
            completed_at__gte=timezone.now() - timezone.timedelta(days=400),
        )
        .annotate(date=TruncDate("completed_at"))
        .values_list("date", flat=True)
        .distinct()
    )
    dates = set(d for d in recent_dates if d is not None)
    if not dates:
        return 0

    today = timezone.now().date()
    # Anchor: today if solved today, else yesterday (so an evening visit before
    # solving doesn't show the streak as already broken).
    if today in dates:
        anchor = today
    elif (today - timezone.timedelta(days=1)) in dates:
        anchor = today - timezone.timedelta(days=1)
    else:
        return 0

    streak = 0
    cursor = anchor
    while cursor in dates:
        streak += 1
        cursor -= timezone.timedelta(days=1)
    return streak


def _check_streaks(user):
    """Award streak achievements AND persist streak/XP onto the user's Profile.

    The Profile already carries daily_streak / longest_streak /
    last_activity_date / xp fields; this is the single place that keeps them in
    sync so the dashboard streak calendar and XP/level widgets have real data.
    All Profile writes are best-effort and never block achievement awarding.
    """
    streak = compute_current_streak(user)

    if streak >= 3:
        UserAchievement.objects.get_or_create(user=user, achievement="streak_3")
    if streak >= 7:
        UserAchievement.objects.get_or_create(user=user, achievement="streak_7")
    if streak >= 30:
        UserAchievement.objects.get_or_create(user=user, achievement="streak_30")

    # Mirror streak + XP onto the Profile (dormant until now). XP is derived
    # from completions/score below in award_xp_for_completion, so here we only
    # keep the streak counters and last-activity date authoritative.
    try:
        from apps.accounts.models import Profile

        profile, _ = Profile.objects.get_or_create(user=user)
        today = timezone.now().date()
        updates = []
        if profile.daily_streak != streak:
            profile.daily_streak = streak
            updates.append("daily_streak")
        if streak > profile.longest_streak:
            profile.longest_streak = streak
            updates.append("longest_streak")
        if profile.last_activity_date != today:
            profile.last_activity_date = today
            updates.append("last_activity_date")
        if updates:
            profile.save(update_fields=updates)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Profile streak sync failed for %s: %s", user, exc)


def _level_threshold(level: int) -> int:
    """Cumulative XP required to *reach* a given level: 100 * (level-1)^2.

    lvl1=0, lvl2=100, lvl3=400, lvl4=900, lvl5=1600, ...
    """
    return 100 * ((max(1, level) - 1) ** 2)


def compute_level(xp: int) -> dict:
    """Map an XP total to a level + progress toward the next level.

    Simple, deterministic quadratic curve (see _level_threshold). Cheap to
    compute, no schema. Returns:
    {level, xp, xp_into_level, xp_for_next_level, progress_pct, next_level}.
    """
    xp = max(0, int(xp or 0))
    # Highest level whose threshold is <= xp.
    level = 1
    while _level_threshold(level + 1) <= xp:
        level += 1
    current_threshold = _level_threshold(level)
    next_threshold = _level_threshold(level + 1)
    span = max(1, next_threshold - current_threshold)
    into = max(0, xp - current_threshold)
    return {
        "level": level,
        "xp": xp,
        "xp_into_level": into,
        "xp_for_next_level": next_threshold - current_threshold,
        "progress_pct": min(100, round(into / span * 100)),
        "next_level": level + 1,
    }


def award_xp_for_completion(user, score: int, difficulty: str | None = None) -> int:
    """Add XP to the user's Profile for a completed scenario and return new total.

    Formula (FREE, deterministic): base 50 + score + difficulty bonus
    (easy 0 / medium 25 / hard 50). Best-effort; never raises.
    """
    bonus = {"easy": 0, "medium": 25, "hard": 50}.get((difficulty or "").lower(), 0)
    gained = 50 + max(0, int(score or 0)) + bonus
    try:
        from apps.accounts.models import Profile
        from django.db.models import F as _F

        Profile.objects.get_or_create(user=user)
        Profile.objects.filter(user=user).update(xp=_F("xp") + gained)
        profile = Profile.objects.filter(user=user).only("xp").first()
        return profile.xp if profile else gained
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("XP award failed for %s: %s", user, exc)
        return 0


def _notify_achievements(user, achievement_types):
    """Send in-app + email notifications for new achievements."""
    try:
        from apps.notifications.tasks import notify_achievement_earned

        ACHIEVEMENT_NAMES = dict(UserAchievement.ACHIEVEMENT_CHOICES)

        for ach_type in achievement_types:
            name = ACHIEVEMENT_NAMES.get(ach_type, ach_type.replace("_", " ").title())
            notify_achievement_earned.delay(user.id, ach_type, name)
    except Exception as e:
        logger.warning(f"Failed to notify achievements: {e}")


def get_user_stats(user):
    """Get aggregated stats for a user."""
    progress = UserScenarioProgress.objects.filter(user=user)

    stats = progress.aggregate(
        total_attempts=Sum("attempts"),
        scenarios_completed=Count("id", filter=Q(completed=True)),
        average_score=Avg("best_score", filter=Q(completed=True)),
        best_time_overall=Min("best_time"),
    )

    achievements = UserAchievement.objects.filter(user=user).count()

    return {
        "total_attempts": stats["total_attempts"] or 0,
        "scenarios_completed": stats["scenarios_completed"] or 0,
        "average_score": round(stats["average_score"] or 0, 1),
        "best_time_overall": stats["best_time_overall"],
        "achievements_earned": achievements,
    }
