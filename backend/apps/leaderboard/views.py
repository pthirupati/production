from .models import LeaderboardEntry


def get_global_leaderboard(limit=50):
    return LeaderboardEntry.objects.filter(
        scenario__isnull=True
    ).order_by("rank")[:limit]


def get_scenario_leaderboard(scenario, limit=50):
    return LeaderboardEntry.objects.filter(
        scenario=scenario
    ).order_by("rank")[:limit]

