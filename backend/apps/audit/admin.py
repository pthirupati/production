"""
Audit admin — AuditLog with full filter, search, and export support.
Audit logs are immutable; no editing actions are provided.
"""
import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import AuditLog


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class ActionCategoryFilter(admin.SimpleListFilter):
    title = "action category"
    parameter_name = "action_cat"

    def lookups(self, request, model_admin):
        return [
            ("auth", "Authentication (login/logout/failed)"),
            ("lab", "Lab activity (start/stop/reset/validate)"),
            ("admin", "Admin actions"),
            ("payment", "Payment failures"),
            ("security", "Security alerts"),
        ]

    def queryset(self, qs, value):
        mapping = {
            "auth": ["login", "login_failed", "logout"],
            "lab": ["lab_start", "lab_stop", "lab_reset", "validate"],
            "admin": ["admin_action"],
            "payment": ["payment_failed"],
            "security": ["security_alert"],
        }
        if value in mapping:
            return qs.filter(action__in=mapping[value])
        return qs


class HasIPFilter(admin.SimpleListFilter):
    title = "has IP"
    parameter_name = "has_ip"

    def lookups(self, request, model_admin):
        return [("yes", "With IP address"), ("no", "No IP recorded")]

    def queryset(self, qs, value):
        if value == "yes":
            return qs.exclude(ip_address__isnull=True).exclude(ip_address="")
        if value == "no":
            return qs.filter(ip_address__isnull=True)
        return qs


# ---------------------------------------------------------------------------
# Admin class
# ---------------------------------------------------------------------------

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action_badge",
        "user",
        "resource_truncated",
        "ip_address",
    )
    list_filter = (
        "action",
        ActionCategoryFilter,
        HasIPFilter,
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__email",
        "resource",
        "ip_address",
        "metadata",
    )
    readonly_fields = ("user", "action", "resource", "metadata", "ip_address", "user_agent", "created_at")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    list_per_page = 100
    ordering = ("-created_at",)
    actions = ["action_export_csv"]

    # Disable add/change/delete from the UI — logs are append-only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # only superusers can purge

    @admin.display(description="Action")
    def action_badge(self, obj):
        colors = {
            "login_failed": "red",
            "security_alert": "red",
            "payment_failed": "red",
            "admin_action": "purple",
            "lab_start": "blue",
            "lab_stop": "grey",
            "login": "green",
            "logout": "grey",
            "error": "red",
        }
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colors.get(obj.action, "black"),
            obj.action,
        )

    @admin.display(description="Resource")
    def resource_truncated(self, obj):
        if not obj.resource:
            return "—"
        return obj.resource[:60]

    @admin.action(description="Export selected audit logs to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'
        writer = csv.writer(response)
        writer.writerow(["created_at", "action", "user", "email", "resource", "ip_address", "user_agent"])
        for log in queryset.select_related("user"):
            writer.writerow([
                log.created_at.isoformat() if log.created_at else "",
                log.action,
                log.user.username if log.user else "",
                log.user.email if log.user else "",
                log.resource,
                log.ip_address or "",
                (log.user_agent or "")[:200],
            ])
        return response
