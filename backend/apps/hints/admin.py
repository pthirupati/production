"""
Hints admin — Hint model with improved list_filter and scenario linkage.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Hint


@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    list_display = ("scenario_link", "order", "content_preview", "penalty", "is_active")
    # Use RelatedOnlyFieldListFilter instead of a raw FK dropdown which loads every scenario
    list_filter = (
        ("scenario", admin.RelatedOnlyFieldListFilter),
        "is_active",
    )
    search_fields = ("scenario__slug", "scenario__title", "content")
    ordering = ("scenario", "order")
    list_select_related = ("scenario",)
    readonly_fields = ("scenario",)
    actions = ["action_activate", "action_deactivate"]

    @admin.display(description="Scenario")
    def scenario_link(self, obj):
        return format_html(
            '<a href="/admin/question_bank/scenario/{}/change/">{}</a>',
            obj.scenario_id,
            obj.scenario.slug,
        )

    @admin.display(description="Content")
    def content_preview(self, obj):
        return obj.content[:80] if hasattr(obj, "content") else "—"

    @admin.action(description="Activate selected hints")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected hints")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
