"""
Ratings admin — Rating model.
"""
from django.contrib import admin

from .models import Rating


class ScoreFilter(admin.SimpleListFilter):
    title = "score range"
    parameter_name = "score_range"

    def lookups(self, request, model_admin):
        return [
            ("low", "Low (1–2)"),
            ("mid", "Mid (3)"),
            ("high", "High (4–5)"),
        ]

    def queryset(self, qs, value):
        if value == "low":
            return qs.filter(score__lte=2)
        if value == "mid":
            return qs.filter(score=3)
        if value == "high":
            return qs.filter(score__gte=4)
        return qs


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "rating_type",
        "scenario",
        "score",
        "has_review",
        "created_at",
    )
    list_filter = (
        "rating_type",
        ScoreFilter,
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "review", "scenario__slug")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("user", "scenario")
    date_hierarchy = "created_at"
    list_per_page = 50

    @admin.display(description="Has review", boolean=True)
    def has_review(self, obj):
        return bool(getattr(obj, "review", ""))
