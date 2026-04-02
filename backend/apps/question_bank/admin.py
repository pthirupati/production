from django.contrib import admin
from .models import Scenario, Technology


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("title", "technology", "category", "difficulty", "is_active")
    list_filter = ("technology", "category", "difficulty", "is_active")
    search_fields = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}

