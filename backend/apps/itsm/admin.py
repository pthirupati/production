from django.contrib import admin

from .models import ItsmTicket, ItsmWorkNote


class ItsmWorkNoteInline(admin.TabularInline):
    model = ItsmWorkNote
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("kind", "author", "body", "created_at")


@admin.register(ItsmTicket)
class ItsmTicketAdmin(admin.ModelAdmin):
    list_display = (
        "number", "ticket_type", "state", "priority", "assignment_group",
        "user", "scenario", "parent", "opened_at",
    )
    list_filter = ("ticket_type", "state", "assignment_group", "priority")
    search_fields = ("number", "short_description", "user__email", "user__username")
    raw_id_fields = ("user", "scenario", "session", "parent")
    readonly_fields = ("opened_at", "updated_at", "resolved_at", "closed_at", "sla_due_at")
    inlines = [ItsmWorkNoteInline]


@admin.register(ItsmWorkNote)
class ItsmWorkNoteAdmin(admin.ModelAdmin):
    list_display = ("ticket", "kind", "author", "created_at")
    list_filter = ("kind",)
    search_fields = ("ticket__number", "body")
    raw_id_fields = ("ticket", "author_user")
