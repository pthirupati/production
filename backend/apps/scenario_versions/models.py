from django.db import models
from apps.question_bank.models import Scenario

class ScenarioVersion(models.Model):
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        related_name="versions"
    )

    version = models.PositiveIntegerField()
    changelog = models.TextField(blank=True)

    # Path to version-specific definition file
    definition_path = models.CharField(max_length=255)

    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("scenario", "version")
        ordering = ["-version"]

    def __str__(self):
        return f"{self.scenario.slug} v{self.version}"

