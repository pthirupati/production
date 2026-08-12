from django.apps import AppConfig


class QuestionBankConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.question_bank"

    def ready(self):
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        from apps.question_bank.models import Scenario

        # User-uploaded project screenshots must not outlive their row (Z4-3).
        from common.file_cleanup import register_file_cleanup

        from apps.question_bank.models import UserTaskProgress

        register_file_cleanup(UserTaskProgress, "screenshot")

        @receiver(post_save, sender=Scenario)
        def capture_scenario_version(sender, instance, created, **kwargs):
            import json
            import logging

            from django.db import transaction
            from django.db.models import Max

            from apps.scenario_versions.models import ScenarioVersion

            try:
                definition_path = (
                    instance.definition_path
                    or f"scenarios/{instance.slug}/scenario.yaml"
                )
                snapshot = {
                    "slug": instance.slug,
                    "title": instance.title,
                    "difficulty": instance.difficulty,
                    "description": instance.description,
                    "objectives": instance.objectives,
                    "time_limit": instance.time_limit,
                    "max_score": instance.max_score,
                }
                # sort_keys so an unchanged definition always serialises
                # identically and the no-op check below is stable.
                changelog = json.dumps(snapshot, sort_keys=True)

                # Skip no-op saves. A Scenario is re-saved by plenty of paths that
                # touch unrelated fields (admin actions, catalog re-imports), and
                # versioning every one of those grew this table without recording
                # any actual change. Only snapshot a real definition change.
                previous = (
                    ScenarioVersion.objects.filter(scenario=instance)
                    .order_by("-version")
                    .first()
                )
                if previous is not None and previous.changelog == changelog:
                    return

                with transaction.atomic():
                    # count()+1 reuses a number after any row is deleted, and the
                    # unique_together then raises — losing the version silently.
                    # Max()+1 stays monotonic across deletes.
                    highest = ScenarioVersion.objects.filter(
                        scenario=instance
                    ).aggregate(top=Max("version"))["top"]
                    next_version = (highest or 0) + 1

                    # Exactly one active version per scenario. Without this every
                    # row stayed is_active=True and get_active_version() returned
                    # an arbitrary row out of the whole history.
                    ScenarioVersion.objects.filter(
                        scenario=instance, is_active=True
                    ).update(is_active=False)

                    ScenarioVersion.objects.create(
                        scenario=instance,
                        version=next_version,
                        changelog=changelog,
                        definition_path=definition_path,
                        is_active=True,
                    )
            except Exception:
                # Never fail the save over versioning, but the bare `pass` this
                # replaces left no trace that history had a hole in it.
                logging.getLogger(__name__).warning(
                    "Failed to capture ScenarioVersion for scenario id=%s",
                    getattr(instance, "pk", None),
                    exc_info=True,
                )

