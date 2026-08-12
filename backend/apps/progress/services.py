from django.db import models, transaction, IntegrityError
from django.db.models import Sum, Count, Avg, Min, Q, F
from django.utils import timezone
from .models import UserScenarioProgress, UserAchievement
import logging

logger = logging.getLogger(__name__)


def record_attempt(user, scenario, score, completed=False, time_seconds=None, hints_used=0):
    """Record a lab attempt and update best records.

    The whole read-modify-write runs inside ``transaction.atomic`` with the row
    held under ``select_for_update``. Every field here is a read-modify-write on
    the in-memory instance — ``attempts += 1``, ``score > best_score``,
    ``time_seconds < best_time``, ``if not completed_at`` — so a plain
    get_or_create + save() lost updates whenever two attempts for the same
    (user, scenario) overlapped: the later save() wrote back a row snapshot taken
    before the earlier one committed, undercounting attempts and silently
    reverting a higher best_score / faster best_time / an already-set
    completed_at.

    F("attempts") + 1 alone would NOT have been enough — it fixes the counter but
    leaves best_score/best_time/completed_at on the same stale instance, so the
    clobber just moves to the fields that matter more. The lock is the only thing
    that makes the comparisons see committed state.
    """
    with transaction.atomic():
        # get_or_create first: select_for_update cannot lock a row that does not
        # exist yet. unique_together (user, scenario) makes the create side safe
        # under a race — the loser gets IntegrityError, and the winner's row is
        # what the locking get() below picks up.
        try:
            UserScenarioProgress.objects.get_or_create(user=user, scenario=scenario)
        except IntegrityError:
            pass

        progress = UserScenarioProgress.objects.select_for_update().get(
            user=user, scenario=scenario
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


def record_attempt_started(user, scenario):
    """Count a lab start as an attempt. Touches `attempts` and nothing else.

    Companion to `record_attempt`, which runs when a lab *finishes*. Both used to
    be `get_or_create` → mutate the instance → `save()`; both lost updates for the
    same reason (see record_attempt's docstring). This one is fixed with a single
    `UPDATE ... SET attempts = attempts + 1` rather than a row lock: there are no
    comparisons here, so the database can do the whole read-modify-write in one
    statement. That is atomic without holding a lock across a round trip — better
    for the lab-start path, which already sits behind the global capacity
    advisory lock. `record_attempt` needs the lock only because `score >
    best_score` / `time_seconds < best_time` have to see committed state.

    Using `.update()` also confines the write to the named columns, so a start can
    no longer clobber a best_score / best_time / hints_used_best that a completion
    committed in between — the old `save()` wrote back every field from a snapshot
    that could already be stale.

    Deliberately does NOT reset completed/completed_at. The old code set
    `completed=False, completed_at=None` on every start, which silently undid a
    prior solve: `jira_integration.completion` decides XP by checking whether a
    `completed=True` row already exists, so wiping the flag at start time made
    every replay look like a first solve and re-opened the XP grind faucet that
    apps/progress/tests/test_xp_no_replay.py exists to keep shut. It also revoked
    the completion from the leaderboard, the streak calendar, learning-path
    progress and certification eligibility, and re-hid the solution explanation —
    permanently, if the user abandoned the replay. Replaying a lab is not
    un-solving it; `completed` means "has ever been solved".

    `last_attempt_at` is `auto_now`, which only fires on `save()`, so the
    `.update()` has to set it explicitly to preserve the old behaviour.
    """
    # select_for_update / UPDATE cannot touch a row that does not exist yet.
    # unique_together (user, scenario) makes the create side race-safe: the loser
    # gets IntegrityError and the UPDATE below finds the winner's row.
    try:
        UserScenarioProgress.objects.get_or_create(user=user, scenario=scenario)
    except IntegrityError:
        pass

    UserScenarioProgress.objects.filter(user=user, scenario=scenario).update(
        attempts=F("attempts") + 1,
        last_attempt_at=timezone.now(),
    )

    # attempts feeds the cached total on UserProgressView.
    from django.core.cache import cache as _cache
    _cache.delete(f"user_progress:{user.id}")


# `compute_score` = max(10, 100 + time_bonus - hint_penalty), where time_bonus is
# `time_remaining * 100 / duration` — so 100 is the floor for a clean solve, not a
# ceiling. "Perfect" therefore has to mean base + at least half the time bonus.
PERFECT_SCORE_MIN = 150


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

    # Perfect Score.
    #
    # Was `score >= 100`, which awarded it to essentially every completion:
    # `compute_score` returns `max(10, 100 + time_bonus - hint_penalty)`, so a
    # hint-free solve is *always* ≥ 100 and the badge meant nothing. It also
    # overlapped exactly with `no_hints`, which already exists.
    #
    # A distinct, earnable definition needs both halves of the score: solved with
    # no hints AND with real time to spare. PERFECT_SCORE_MIN is 100 (the base)
    # plus half the available time bonus, i.e. finished inside half the clock.
    if hints_used == 0 and score >= PERFECT_SCORE_MIN:
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

    # Streak tracking — check consecutive days with completed labs.
    # `_award` is passed in rather than `_check_streaks` calling get_or_create
    # itself: doing it inline meant streak badges were created but never appended
    # to `awarded`, so they were the only achievements on the platform that never
    # notified the person who earned them.
    _check_streaks(user, _award)

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


def _check_streaks(user, award=None):
    """Award streak achievements AND persist streak/XP onto the user's Profile.

    The Profile already carries daily_streak / longest_streak /
    last_activity_date / xp fields; this is the single place that keeps them in
    sync so the dashboard streak calendar and XP/level widgets have real data.
    All Profile writes are best-effort and never block achievement awarding.
    """
    streak = compute_current_streak(user)

    def _default_award(key):
        UserAchievement.objects.get_or_create(user=user, achievement=key)

    award = award or _default_award
    for threshold, key in ((3, "streak_3"), (7, "streak_7"), (30, "streak_30")):
        if streak >= threshold:
            award(key)

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
    bonus = {"easy": 0, "medium": 25, "hard": 50, "expert": 75}.get((difficulty or "").lower(), 0)
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
