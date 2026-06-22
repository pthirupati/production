from django.contrib import admin

from .models import (
    CertEarnedCertificate,
    CertificationTrack,
    CertObjective,
    ExamAttempt,
    TrackScenario,
)


class CertObjectiveInline(admin.TabularInline):
    model = CertObjective
    extra = 0


@admin.register(CertificationTrack)
class CertificationTrackAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "vendor", "is_active", "order")
    list_filter = ("is_active", "vendor")
    search_fields = ("code", "name", "slug")
    prepopulated_fields = {"slug": ("code",)}
    inlines = [CertObjectiveInline]


@admin.register(CertObjective)
class CertObjectiveAdmin(admin.ModelAdmin):
    list_display = ("code", "track", "title", "weight", "order")
    list_filter = ("track",)
    search_fields = ("code", "title")


@admin.register(TrackScenario)
class TrackScenarioAdmin(admin.ModelAdmin):
    list_display = ("objective", "scenario", "order", "in_exam_pool")
    list_filter = ("objective__track", "in_exam_pool")
    search_fields = ("scenario__slug", "objective__code")
    raw_id_fields = ("scenario",)


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "track", "status", "score", "started_at", "expires_at")
    list_filter = ("status", "track")
    search_fields = ("user__email",)


@admin.register(CertEarnedCertificate)
class CertEarnedCertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_id", "user", "track", "score", "issued_at", "expires_at")
    list_filter = ("track",)
    search_fields = ("certificate_id", "user__email", "holder_name")
