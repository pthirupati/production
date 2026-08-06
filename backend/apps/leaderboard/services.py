"""Leaderboard snapshot table.

IMPORTANT — read before wiring anything to this: `LeaderboardEntry` is currently a
cache **nobody reads**. The live endpoint (`public_api.views.LeaderboardView`)
aggregates from `UserScenarioProgress` directly, `apps/leaderboard/` has no
`urls.py` so its own views are unreachable, and `adminpanel` imports the model
without querying it (audit Z3-7).

Both recompute functions used to do a bare `.delete()` followed by N individual
`.create()` calls with **no transaction**. Nothing reads the table today, so that was
harmless — but it left a loaded gun: the moment anyone switched a real endpoint over
to it, every reader in the recompute window would see a partially-populated or empty
leaderboard, and a mid-loop failure would leave it permanently truncated. Both are
now atomic, and build the rows with `bulk_create` instead of one INSERT per user.
"""
from django.db import transaction
from django.db.models import Max, Sum

from apps.progress.models import UserScenarioProgress

from .models import LeaderboardEntry

# Chunk size for bulk_create. Large enough that a full recompute is a handful of
# round-trips, small enough not to build one giant query.
_BATCH = 500


@transaction.atomic
def compute_global_leaderboard():
    """Recompute the all-scenario leaderboard snapshot.

    Atomic: readers see either the previous snapshot or the new one, never the empty
    window between the delete and the inserts.
    """
    scores = (
        UserScenarioProgress.objects
        .filter(completed=True)
        .values("user")
        .annotate(total_score=Sum("best_score"))
        .order_by("-total_score")
    )

    LeaderboardEntry.objects.filter(scenario__isnull=True).delete()
    LeaderboardEntry.objects.bulk_create(
        [
            LeaderboardEntry(
                user_id=row["user"], scenario=None,
                score=row["total_score"], rank=rank,
            )
            for rank, row in enumerate(scores, start=1)
        ],
        batch_size=_BATCH,
    )


@transaction.atomic
def compute_scenario_leaderboard(scenario):
    """Recompute one scenario's leaderboard snapshot. Atomic, as above."""
    scores = (
        UserScenarioProgress.objects
        .filter(scenario=scenario, completed=True)
        .values("user")
        .annotate(score=Max("best_score"))
        .order_by("-score")
    )

    LeaderboardEntry.objects.filter(scenario=scenario).delete()
    LeaderboardEntry.objects.bulk_create(
        [
            LeaderboardEntry(
                user_id=row["user"], scenario=scenario,
                score=row["score"], rank=rank,
            )
            for rank, row in enumerate(scores, start=1)
        ],
        batch_size=_BATCH,
    )
