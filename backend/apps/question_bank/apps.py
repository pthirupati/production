from django.apps import AppConfig


class QuestionBankConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.question_bank"

    def ready(self):
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        from apps.question_bank.models import Scenario

        @receiver(post_save, sender=Scenario)
        def capture_scenario_version(sender, instance, created, **kwargs):
            from apps.scenario_versions.models import ScenarioVersion
            try:
                next_version = ScenarioVersion.objects.filter(scenario=instance).count() + 1
                definition_path = (
                    instance.definition_path
                    or f"scenarios/{instance.slug}/scenario.yaml"
                )
                ScenarioVersion.objects.create(
                    scenario=instance,
                    version=next_version,
                    changelog="Auto-snapshot on save" if not created else "Initial version",
                    definition_path=definition_path,
                    is_active=True,
                )
            except Exception:
                pass  # never fail the save due to versioning errors

