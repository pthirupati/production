from django.contrib import admin

from .models import Tutorial, TutorialSection


class TutorialSectionInline(admin.StackedInline):
    model = TutorialSection
    extra = 1
    ordering = ["order"]


@admin.register(Tutorial)
class TutorialAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "difficulty", "is_published", "order")
    list_filter = ("topic", "difficulty", "is_published")
    search_fields = ("title", "slug", "summary")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [TutorialSectionInline]


@admin.register(TutorialSection)
class TutorialSectionAdmin(admin.ModelAdmin):
    list_display = ("tutorial", "order", "heading")
    list_filter = ("tutorial",)
    search_fields = ("heading", "body")
    ordering = ["tutorial", "order"]
