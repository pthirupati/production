from django.contrib import admin
from .models import Hint

@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    list_display = ("scenario", "order", "penalty", "is_active")
    list_filter = ("scenario", "is_active")
    ordering = ("scenario", "order")

