from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Rating(models.Model):
    """User rating for a scenario or the platform overall."""
    RATING_TYPE_CHOICES = [
        ("scenario", "Scenario Rating"),
        ("platform", "Platform Rating"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rating_type = models.CharField(max_length=20, choices=RATING_TYPE_CHOICES)
    scenario = models.ForeignKey(
        "question_bank.Scenario",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ratings",
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars",
    )
    review = models.TextField(blank=True, help_text="Optional review text")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scenario"],
                name="unique_scenario_rating",
                condition=models.Q(rating_type="scenario"),
            ),
            models.UniqueConstraint(
                fields=["user", "rating_type"],
                name="unique_platform_rating",
                condition=models.Q(rating_type="platform"),
            ),
        ]
        indexes = [
            models.Index(fields=["rating_type", "-created_at"]),
            models.Index(fields=["scenario", "-created_at"]),
        ]

    def __str__(self):
        target = self.scenario.title if self.scenario else "Platform"
        return f"{self.user.username}: {self.score}/5 for {target}"
