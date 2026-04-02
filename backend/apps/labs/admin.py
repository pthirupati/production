from django.contrib import admin
from .models import LabSession

@admin.register(LabSession)
class LabSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "scenario",
        "status",
        "provider",
        "started_at",
    )
    list_filter = ("status", "provider")

