from django.db.models import Sum, Max
from apps.progress.models import UserScenarioProgress
from .models import LeaderboardEntry


def compute_global_leaderboard():
    """
    Compute leaderboard across all scenarios.
    """
    scores = (
        UserScenarioProgress.objects
        .filter(completed=True)
        .values("user")
        .annotate(total_score=Sum("best_score"))
        .order_by("-total_score")
    )

    LeaderboardEntry.objects.filter(scenario__isnull=True).delete()

    for rank, row in enumerate(scores, start=1):
        LeaderboardEntry.objects.create(
            user_id=row["user"],
            scenario=None,
            score=row["total_score"],
            rank=rank,
        )


def compute_scenario_leaderboard(scenario):
    """
    Compute leaderboard for a single scenario.
    """
    scores = (
        UserScenarioProgress.objects
        .filter(scenario=scenario, completed=True)
        .values("user")
        .annotate(score=Max("best_score"))
        .order_by("-score")
    )

    LeaderboardEntry.objects.filter(scenario=scenario).delete()

    for rank, row in enumerate(scores, start=1):
        LeaderboardEntry.objects.create(
            user_id=row["user"],
            scenario=scenario,
            score=row["score"],
            rank=rank,
        )

