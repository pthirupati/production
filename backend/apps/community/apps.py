from django.apps import AppConfig


class CommunityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.community"
    verbose_name = "Community Threads"

    def ready(self):
        # A deleted/moderated attachment must leave the disk too, or removing
        # abusive content only hides it from the UI (Z4-3).
        from common.file_cleanup import register_file_cleanup

        from apps.community.models import ThreadAttachment

        register_file_cleanup(ThreadAttachment, "file")
