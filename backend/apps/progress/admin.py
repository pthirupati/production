"""
Progress admin — UserScenarioProgress, UserAchievement, LearningPathProgress.
"""
import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html

from .models import LearningPathProgress, UserAchievement, UserScenarioProgress


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class CompletionFilter(admin.SimpleListFilter):
    title = "completion"
    parameter_name = "completed"

    def lookups(self, request, model_admin):
        return [("yes", "Completed"), ("no", "Not completed")]

    def queryset(self, qs, value):
        if value == "yes":
            return qs.filter(completed=True)
        if value == "no":
            return qs.filter(completed=False)
        return qs


class AttemptsFilter(admin.SimpleListFilter):
    title = "attempts"
    parameter_name = "attempts_range"

    def lookups(self, request, model_admin):
        return [
            ("1", "First try"),
            ("2-5", "2–5 attempts"),
            ("5+", "5+ attempts"),
        ]

    def queryset(self, qs, value):
        if value == "1":
            return qs.filter(attempts=1)
        if value == "2-5":
            return qs.filter(attempts__gte=2, attempts__lte=5)
        if value == "5+":
            return qs.filter(attempts__gt=5)
        return qs


# ---------------------------------------------------------------------------
# Scenario Progress admin
# ---------------------------------------------------------------------------

@admin.register(UserScenarioProgress)
class UserScenarioProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "scenario",
        "attempts",
        "completed",
        "best_score",
        "best_time_display",
        "hints_used_best",
        "last_attempt_at",
    )
    list_filter = (
        CompletionFilter,
        AttemptsFilter,
        ("last_attempt_at", admin.DateFieldListFilter),
        ("scenario__technology", admin.RelatedOnlyFieldListFilter),
        ("scenario__difficulty", admin.ChoicesFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "scenario__slug", "scenario__title")
    readonly_fields = (
        "user", "scenario", "attempts", "completed",
        "best_score", "best_time", "hints_used_best",
        "last_attempt_at", "completed_at",
    )
    list_select_related = ("user", "scenario", "scenario__technology")
    date_hierarchy = "last_attempt_at"
    list_per_page = 100
    actions = ["action_export_csv"]

    @admin.display(description="Best time")
    def best_time_display(self, obj):
        if not obj.best_time:
            return "—"
        m, s = divmod(obj.best_time, 60)
        return f"{m}m {s}s"

    @admin.action(description="Export selected progress records to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="progress.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "user", "email", "scenario", "technology", "difficulty",
            "attempts", "completed", "best_score", "best_time_seconds",
            "hints_used_best", "last_attempt_at", "completed_at",
        ])
        for p in queryset.select_related("user", "scenario__technology"):
            writer.writerow([
                p.user.username, p.user.email,
                p.scenario.slug, p.scenario.technology.name,
                p.scenario.difficulty,
                p.attempts, p.completed, p.best_score, p.best_time or "",
                p.hints_used_best,
                p.last_attempt_at.isoformat() if p.last_attempt_at else "",
                p.completed_at.isoformat() if p.completed_at else "",
            ])
        return response


# ---------------------------------------------------------------------------
# Achievement admin
# ---------------------------------------------------------------------------

@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "achievement_badge", "earned_at")
    list_filter = (
        "achievement",
        ("earned_at", admin.DateFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "achievement")
    readonly_fields = ("user", "achievement", "earned_at")
    list_select_related = ("user",)
    date_hierarchy = "earned_at"
    list_per_page = 100
    actions = ["action_export_csv"]

    @admin.display(description="Achievement")
    def achievement_badge(self, obj):
        return obj.get_achievement_display()

    @admin.action(description="Export achievements to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="achievements.csv"'
        writer = csv.writer(response)
        writer.writerow(["user", "email", "achievement", "earned_at"])
        for a in queryset.select_related("user"):
            writer.writerow([
                a.user.username, a.user.email,
                a.achievement,
                a.earned_at.isoformat() if a.earned_at else "",
            ])
        return response


# ---------------------------------------------------------------------------
# Learning path progress admin
# ---------------------------------------------------------------------------

@admin.register(LearningPathProgress)
class LearningPathProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "technology", "steps_completed", "updated_at")
    list_filter = (
        ("technology", admin.RelatedOnlyFieldListFilter),
        ("updated_at", admin.DateFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "technology__name")
    readonly_fields = ("user", "technology", "completed_slugs", "updated_at")
    list_select_related = ("user", "technology")

    @admin.display(description="Steps completed")
    def steps_completed(self, obj):
        return len(obj.completed_slugs)
