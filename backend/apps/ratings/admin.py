from django.contrib import admin
from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ["user", "rating_type", "scenario", "score", "created_at"]
    list_filter = ["rating_type", "score"]
    search_fields = ["user__username", "review"]
    readonly_fields = ["created_at", "updated_at"]
