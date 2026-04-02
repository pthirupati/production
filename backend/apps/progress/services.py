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

    # First Solve
    completed_count = UserScenarioProgress.objects.filter(
        user=user, completed=True
    ).count()

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
        from apps.question_bank.models import Scenario as ScenarioModel
        total_of_difficulty = ScenarioModel.objects.filter(
            difficulty=difficulty, is_active=True
        ).count()
        completed_of_difficulty = UserScenarioProgress.objects.filter(
            user=user,
            completed=True,
            scenario__difficulty=difficulty,
            scenario__is_active=True,
        ).count()
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


def _check_streaks(user):
    """Check if user has earned streak achievements."""
    from django.db.models import DateField
    from django.db.models.functions import TruncDate

    # Get distinct dates when user completed scenarios (last 31 days)
    recent_dates = (
        UserScenarioProgress.objects.filter(
            user=user,
            completed=True,
            completed_at__gte=timezone.now() - timezone.timedelta(days=31),
        )
        .annotate(date=TruncDate("completed_at"))
        .values_list("date", flat=True)
        .distinct()
        .order_by("-date")
    )
    dates = sorted(set(recent_dates), reverse=True)

    if not dates:
        return

    # Count consecutive days from today
    streak = 0
    today = timezone.now().date()
    for i, d in enumerate(dates):
        expected = today - timezone.timedelta(days=i)
        if d == expected:
            streak += 1
        else:
            break

    if streak >= 3:
        UserAchievement.objects.get_or_create(user=user, achievement="streak_3")
    if streak >= 7:
        UserAchievement.objects.get_or_create(user=user, achievement="streak_7")
    if streak >= 30:
        UserAchievement.objects.get_or_create(user=user, achievement="streak_30")


def _notify_achievements(user, achievement_types):
    """Send in-app + email notifications for new achievements."""
    try:
        from apps.notifications.tasks import create_in_app_notification, send_notification_email
        from django.conf import settings

        ACHIEVEMENT_ICONS = {
            "first_solve": "🎯", "speed_demon": "⚡", "no_hints": "🧠",
            "perfect_score": "💯", "streak_3": "🔥", "streak_7": "🔥",
            "streak_30": "🔥", "easy_master": "🥉", "medium_master": "🥈",
            "hard_master": "🥇", "ten_solves": "🏅", "fifty_solves": "🏆",
            "hundred_solves": "👑",
        }
        ACHIEVEMENT_NAMES = dict(UserAchievement.ACHIEVEMENT_CHOICES)

        for ach_type in achievement_types:
            name = ACHIEVEMENT_NAMES.get(ach_type, ach_type.replace("_", " ").title())
            icon = ACHIEVEMENT_ICONS.get(ach_type, "🏆")

            create_in_app_notification.delay(
                user_id=user.id,
                notification_type="achievement",
                title=f"Achievement Unlocked: {name}",
                message=f"You earned the {name} badge!",
                metadata={"achievement": ach_type, "icon": icon},
            )

            send_notification_email.delay(
                subject=f"🏆 Achievement Unlocked: {name} — FixitLab",
                to_email=user.email,
                template="emails/achievement.html",
                context={
                    "username": user.username,
                    "achievement_icon": icon,
                    "achievement_name": name,
                    "achievement_description": f"You earned this badge on FixitLab. Keep going!",
                    "dashboard_url": f"{settings.FRONTEND_URL}/achievements",
                },
            )
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
