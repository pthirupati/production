from django.apps import AppConfig


class InterviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.interviews"
    verbose_name = "AI Interview Studio"

    def ready(self):
        # Resumes and interview video are the most sensitive blobs on the
        # platform; without this they survived user.delete() on disk (Z4-3).
        from common.file_cleanup import register_file_cleanup

        from apps.interviews.models import AsyncVideoResponse, CandidateProfile

        register_file_cleanup(CandidateProfile, "resume_file")
        register_file_cleanup(AsyncVideoResponse, "video_file")
