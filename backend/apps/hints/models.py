from django.db import models
from apps.question_bank.models import Scenario

class Hint(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="hints"
    )

    order = models.PositiveIntegerField(
        help_text="Hint order (1, 2, 3...)"
    )

    content = models.TextField()
    penalty = models.PositiveIntegerField(
        default=0,
        help_text="Penalty points for using this hint"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scenario", "order")
        ordering = ["order"]

    def __str__(self):
        return f"{self.scenario.slug} - Hint {self.order}"

