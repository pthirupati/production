from django.db import models
from django.conf import settings
from apps.question_bank.models import Scenario


class UserScenarioProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scenario_progress",
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="user_progress",
    )

    attempts = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    best_score = models.PositiveIntegerField(default=0)
    best_time = models.PositiveIntegerField(null=True, blank=True, help_text="Best completion time in seconds")
    hints_used_best = models.PositiveIntegerField(default=0, help_text="Hints used in best attempt")

    last_attempt_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "scenario")
        indexes = [
            models.Index(fields=["user", "completed"], name="progress_user_completed_idx"),
            models.Index(fields=["scenario", "completed"], name="progress_scen_completed_idx"),
            models.Index(fields=["completed", "best_score"], name="progress_completed_score_idx"),
        ]

    def __str__(self):
        return f"{self.user} - {self.scenario.slug}"


class UserAchievement(models.Model):
    """Tracks user badges and achievements"""
    ACHIEVEMENT_CHOICES = [
        ("first_solve", "First Solve"),
        ("speed_demon", "Speed Demon"),
        ("no_hints", "No Hints Used"),
        ("perfect_score", "Perfect Score"),
        ("streak_3", "3-Day Streak"),
        ("streak_7", "7-Day Streak"),
        ("streak_30", "30-Day Streak"),
        ("easy_master", "Easy Master"),
        ("medium_master", "Medium Master"),
        ("hard_master", "Hard Master"),
        ("ten_solves", "10 Scenarios Solved"),
        ("fifty_solves", "50 Scenarios Solved"),
        ("hundred_solves", "100 Scenarios Solved"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    achievement = models.CharField(max_length=30, choices=ACHIEVEMENT_CHOICES)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "achievement")
        ordering = ["-earned_at"]

    def __str__(self):
        return f"{self.user} - {self.achievement}"


class LearningPathProgress(models.Model):
    """Tracks which learning-path scenario slugs a user completed per technology."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_path_progress",
    )
    technology = models.ForeignKey(
        "question_bank.Technology",
        on_delete=models.CASCADE,
        related_name="learning_path_progress",
    )
    completed_slugs = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "technology")

    def __str__(self):
        return f"{self.user} — {self.technology.slug} ({len(self.completed_slugs)} steps)"

