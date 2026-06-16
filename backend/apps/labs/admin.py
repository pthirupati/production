"""
Lab session admin — LabSession, CommandHistory, SessionRecording.
"""
import csv
from datetime import timedelta

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import CommandHistory, LabSession, SessionRecording


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class StuckSessionFilter(admin.SimpleListFilter):
    """Highlight PROVISIONING sessions older than 10 minutes."""
    title = "stuck sessions"
    parameter_name = "stuck"

    def lookups(self, request, model_admin):
        return [("yes", "Stuck (provisioning > 10 min)")]

    def queryset(self, qs, value):
        if value == "yes":
            cutoff = timezone.now() - timedelta(minutes=10)
            return qs.filter(status="PROVISIONING", started_at__lt=cutoff)
        return qs


class ExpiredRunningFilter(admin.SimpleListFilter):
    """RUNNING sessions that have exceeded their duration_limit."""
    title = "expired running"
    parameter_name = "expired"

    def lookups(self, request, model_admin):
        return [("yes", "Running but expired")]

    def queryset(self, qs, value):
        if value == "yes":
            # We cannot push the is_expired property into SQL easily, so we
            # approximate: started_at older than MAX(duration_limit) seconds.
            # This over-selects slightly; the UI can sort out the rest.
            return qs.filter(
                status="RUNNING",
                started_at__lt=timezone.now() - timedelta(hours=2),
            )
        return qs


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class CommandHistoryInline(admin.TabularInline):
    model = CommandHistory
    fields = ("timestamp", "command", "exit_code")
    readonly_fields = ("timestamp", "command", "exit_code")
    extra = 0
    max_num = 50
    ordering = ("-timestamp",)
    can_delete = False
    verbose_name = "command"
    verbose_name_plural = "last 50 commands"

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("-timestamp")[:50]


class SessionRecordingInline(admin.StackedInline):
    model = SessionRecording
    fields = ("total_duration", "created_at")
    readonly_fields = ("total_duration", "created_at")
    extra = 0
    can_delete = False


# ---------------------------------------------------------------------------
# Main admin
# ---------------------------------------------------------------------------

@admin.register(LabSession)
class LabSessionAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "user_link",
        "scenario_link",
        "status_badge",
        "provider",
        "score",
        "hints_used",
        "validation_passed",
        "duration_display",
        "started_at",
    )
    list_filter = (
        "status",
        "provider",
        "validation_passed",
        StuckSessionFilter,
        ExpiredRunningFilter,
        ("started_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "user__email",
        "scenario__slug",
        "scenario__title",
        "container_id",
        "instance_id",
        "jira_issue_key",
    )
    readonly_fields = (
        "id",
        "user",
        "scenario",
        "container_id",
        "container_name",
        "instance_id",
        "started_at",
        "ended_at",
        "score",
        "hints_used",
        "validation_passed",
        "completion_finalized",
        "jira_issue_key",
        "jira_issue_url",
        "lab_hosts",
        "time_remaining_display",
    )
    date_hierarchy = "started_at"
    list_select_related = ("user", "scenario", "scenario__technology")
    list_per_page = 50
    ordering = ("-started_at",)
    inlines = [CommandHistoryInline, SessionRecordingInline]
    actions = [
        "action_terminate",
        "action_mark_failed",
        "action_export_csv",
    ]

    # ---- display helpers ----

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.id)[:8] + "..."

    @admin.display(description="User", ordering="user__username")
    def user_link(self, obj):
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user_id,
            obj.user.username,
        )

    @admin.display(description="Scenario", ordering="scenario__title")
    def scenario_link(self, obj):
        return format_html(
            '<a href="/admin/question_bank/scenario/{}/change/">{}</a>',
            obj.scenario_id,
            obj.scenario.slug,
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "RUNNING": "green",
            "PROVISIONING": "orange",
            "COMPLETED": "blue",
            "FAILED": "red",
            "TERMINATED": "grey",
            "EXPIRED": "brown",
        }
        color = colors.get(obj.status, "black")
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            color,
            obj.status,
        )

    @admin.display(description="Duration")
    def duration_display(self, obj):
        if obj.ended_at:
            delta = obj.ended_at - obj.started_at
            total = int(delta.total_seconds())
        elif obj.status == "RUNNING":
            total = int((timezone.now() - obj.started_at).total_seconds())
        else:
            return "—"
        m, s = divmod(total, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m}m"
        return f"{m}m {s}s"

    @admin.display(description="Time remaining")
    def time_remaining_display(self, obj):
        if obj.status != "RUNNING":
            return "—"
        remaining = obj.time_remaining
        m, s = divmod(remaining, 60)
        return f"{m}m {s}s"

    # ---- actions ----

    @admin.action(description="Terminate selected lab sessions")
    def action_terminate(self, request, queryset):
        active = queryset.filter(status__in=["RUNNING", "PROVISIONING"])
        count = 0
        for session in active:
            session.mark_terminated()
            count += 1
        self.message_user(
            request,
            f"{count} session(s) terminated.",
            messages.SUCCESS,
        )

    @admin.action(description="Mark selected sessions as FAILED")
    def action_mark_failed(self, request, queryset):
        active = queryset.filter(status__in=["RUNNING", "PROVISIONING"])
        count = active.update(status="FAILED", ended_at=timezone.now())
        self.message_user(request, f"{count} session(s) marked as FAILED.", messages.WARNING)

    @admin.action(description="Export selected sessions to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="lab_sessions.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "id", "user", "email", "scenario", "technology",
            "status", "provider", "score", "hints_used",
            "validation_passed", "started_at", "ended_at",
        ])
        for s in queryset.select_related("user", "scenario__technology"):
            writer.writerow([
                str(s.id),
                s.user.username,
                s.user.email,
                s.scenario.slug,
                s.scenario.technology.name,
                s.status,
                s.provider,
                s.score,
                s.hints_used,
                s.validation_passed,
                s.started_at.isoformat() if s.started_at else "",
                s.ended_at.isoformat() if s.ended_at else "",
            ])
        return response


@admin.register(CommandHistory)
class CommandHistoryAdmin(admin.ModelAdmin):
    list_display = ("session_short", "command_preview", "exit_code", "timestamp")
    list_filter = ("exit_code",)
    search_fields = ("session__user__username", "command")
    readonly_fields = ("session", "command", "output", "exit_code", "timestamp")
    date_hierarchy = "timestamp"
    list_select_related = ("session__user",)

    @admin.display(description="Session")
    def session_short(self, obj):
        return f"{obj.session.user.username}/{str(obj.session_id)[:8]}"

    @admin.display(description="Command")
    def command_preview(self, obj):
        return obj.command[:80]


@admin.register(SessionRecording)
class SessionRecordingAdmin(admin.ModelAdmin):
    list_display = ("session", "total_duration", "created_at")
    readonly_fields = ("session", "events", "total_duration", "created_at")
    list_select_related = ("session__user",)
