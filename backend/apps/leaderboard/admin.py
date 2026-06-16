"""
Leaderboard admin — LeaderboardEntry.
"""
from django.contrib import admin

from .models import LeaderboardEntry


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ("rank", "user", "scenario", "score", "updated_at")
    list_filter = (
        ("scenario", admin.RelatedOnlyFieldListFilter),
        ("updated_at", admin.DateFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "scenario__slug")
    readonly_fields = ("user", "scenario", "score", "rank", "updated_at")
    ordering = ("rank",)
    list_select_related = ("user", "scenario")
    list_per_page = 100

    def has_add_permission(self, request):
        # Leaderboard is computed, not hand-entered
        return False
