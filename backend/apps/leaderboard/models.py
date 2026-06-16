from django.db import models
from django.conf import settings
from apps.question_bank.models import Scenario

class LeaderboardEntry(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Null means global leaderboard"
    )

    score = models.PositiveIntegerField()
    rank = models.PositiveIntegerField()

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "scenario")
        ordering = ["rank"]
        indexes = [
            models.Index(fields=["rank"], name="leaderboard_rank_idx"),
            models.Index(fields=["scenario", "rank"], name="leaderboard_scenario_rank_idx"),
        ]

    def __str__(self):
        return f"{self.user} - {self.score}"

