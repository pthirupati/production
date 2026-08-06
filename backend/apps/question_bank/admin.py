"""
Question bank admin — Technology, Scenario, Tag.
"""
import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Scenario, Tag, Technology, Project, ProjectTask, UserProjectProgress, UserTaskProgress


def _clear_technology_caches():
    """Bust all technology-related API caches so changes are reflected immediately.

    Delegates to `cache_utils` (audit Z5-14). This used to keep its own list, and
    the two drifted: both deleted `technologies_list` while the view had moved to
    `technologies_list_v2`, so neither invalidator actually cleared the technologies
    list. One list, in one place, is the fix for that class of bug.
    """
    from .cache_utils import invalidate_technologies_cache

    invalidate_technologies_cache()


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class ScenarioInline(admin.TabularInline):
    model = Scenario
    fields = ("slug", "title", "difficulty", "scenario_type", "is_active")
    readonly_fields = ("slug",)
    extra = 0
    show_change_link = True
    can_delete = True


# ---------------------------------------------------------------------------
# Technology Admin
# ---------------------------------------------------------------------------

@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "price_inr",
        "scenario_count",
        "is_active",
        "coming_soon",
        "order",
        "created_at",
    )
    list_filter = ("is_active", "coming_soon")
    search_fields = ("name", "slug")
    readonly_fields = ("slug", "created_at")
    prepopulated_fields = {}  # slug is auto-generated on save
    list_editable = ("is_active", "coming_soon", "order")
    ordering = ("order", "name")
    inlines = [ScenarioInline]
    actions = ["action_activate", "action_deactivate", "action_mark_coming_soon", "action_export_csv"]

    @admin.display(description="Price (INR)")
    def price_inr(self, obj):
        return f"₹{obj.price}"

    @admin.display(description="Scenarios")
    def scenario_count(self, obj):
        total = obj.scenarios.count()
        active = obj.scenarios.filter(is_active=True).count()
        return format_html("{} <small style='color:grey'>({} active)</small>", total, active)

    @admin.action(description="Activate selected technologies")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True, coming_soon=False)
        self.message_user(request, "Technologies activated.", messages.SUCCESS)

    @admin.action(description="Deactivate selected technologies")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Technologies deactivated.", messages.WARNING)

    @admin.action(description="Mark as coming soon")
    def action_mark_coming_soon(self, request, queryset):
        queryset.update(coming_soon=True)
        self.message_user(request, "Marked as coming soon.", messages.SUCCESS)

    @admin.action(description="Export selected technologies to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="technologies.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "name", "slug", "price", "is_active", "coming_soon", "scenario_count"])
        for t in queryset.annotate_scenario_count() if hasattr(queryset, "annotate_scenario_count") else queryset:
            writer.writerow([t.id, t.name, t.slug, t.price, t.is_active, t.coming_soon, t.scenarios.count()])
        return response

    def delete_model(self, request, obj):
        """Clear API caches after a single Technology is deleted."""
        name = obj.name
        scenario_count = obj.scenarios.count()
        super().delete_model(request, obj)
        _clear_technology_caches()
        self.message_user(
            request,
            f"Technology '{name}' and its {scenario_count} scenario(s) have been deleted. "
            "API cache cleared — changes are live immediately.",
            messages.SUCCESS,
        )

    def delete_queryset(self, request, queryset):
        """Clear API caches after bulk-delete of Technologies."""
        names = list(queryset.values_list("name", flat=True))
        super().delete_queryset(request, queryset)
        _clear_technology_caches()
        self.message_user(
            request,
            f"Deleted technologies: {', '.join(names)}. API cache cleared.",
            messages.SUCCESS,
        )

    def save_model(self, request, obj, form, change):
        """Clear API caches whenever a Technology is saved (name/price/active status changed)."""
        super().save_model(request, obj, form, change)
        _clear_technology_caches()


# ---------------------------------------------------------------------------
# Tag Admin
# ---------------------------------------------------------------------------

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "scenario_count")
    search_fields = ("name", "slug")
    readonly_fields = ("slug",)

    @admin.display(description="Scenarios")
    def scenario_count(self, obj):
        return obj.scenarios.count()


# ---------------------------------------------------------------------------
# Hint Inline (used inside ScenarioAdmin)
# ---------------------------------------------------------------------------

class HintInlineForScenario(admin.TabularInline):
    # Import here to avoid circular import
    from apps.hints.models import Hint
    model = Hint
    fields = ("order", "content", "penalty", "is_active")
    extra = 1
    ordering = ("order",)


# ---------------------------------------------------------------------------
# Scenario Admin
# ---------------------------------------------------------------------------

class DifficultyFilter(admin.SimpleListFilter):
    title = "difficulty"
    parameter_name = "difficulty"

    def lookups(self, request, model_admin):
        return Scenario.DIFFICULTY_CHOICES

    def queryset(self, qs, value):
        if value:
            return qs.filter(difficulty=value)
        return qs


class InfraTypeFilter(admin.SimpleListFilter):
    title = "infrastructure"
    parameter_name = "infra"

    def lookups(self, request, model_admin):
        return Scenario.INFRA_CHOICES

    def queryset(self, qs, value):
        if value:
            return qs.filter(infrastructure_type=value)
        return qs


class LabModeFilter(admin.SimpleListFilter):
    title = "lab mode"
    parameter_name = "lab_mode"

    def lookups(self, request, model_admin):
        return Scenario.LAB_MODE_CHOICES

    def queryset(self, qs, value):
        if value:
            return qs.filter(lab_mode=value)
        return qs


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "technology",
        "difficulty_badge",
        "scenario_type",
        "lab_mode",
        "infrastructure_type",
        "is_active",
        "session_count",
        "completion_rate",
    )
    list_filter = (
        "technology",
        DifficultyFilter,
        "scenario_type",
        "is_active",
        InfraTypeFilter,
        LabModeFilter,
        "requires_companion_hosts",
        "dual_terminal",
    )
    search_fields = ("title", "slug", "category", "description")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)
    readonly_fields = ("slug",)
    list_select_related = ("technology",)
    list_per_page = 50
    date_hierarchy = None
    ordering = ("technology", "difficulty", "title")
    inlines = [HintInlineForScenario]
    actions = [
        "action_activate",
        "action_deactivate",
        "action_export_csv",
        "action_set_docker",
        "action_set_simulation",
    ]
    fieldsets = (
        ("Identity", {
            "fields": ("slug", "title", "subtitle", "technology", "category", "tags"),
        }),
        ("Difficulty & Type", {
            "fields": ("difficulty", "scenario_type", "is_active"),
        }),
        ("Content", {
            "fields": ("description", "objectives", "initial_state", "solution_explanation"),
        }),
        ("Infrastructure", {
            "fields": (
                "lab_mode", "infrastructure_type",
                "docker_image", "docker_privileged",
                "cloud_setup_script", "cloud_ami", "cloud_image",
                "requires_companion_hosts", "dual_terminal",
            ),
            "classes": ("collapse",),
        }),
        ("Simulation", {
            "fields": ("simulation_type",),
            "classes": ("collapse",),
        }),
        ("Validation", {
            "fields": ("validation_script", "blocked_commands"),
            "classes": ("collapse",),
        }),
        ("Jira", {
            "fields": ("jira_priority", "jira_issue_template"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Difficulty")
    def difficulty_badge(self, obj):
        colors = {"easy": "green", "medium": "orange", "hard": "red"}
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colors.get(obj.difficulty, "black"),
            obj.get_difficulty_display(),
        )

    @admin.display(description="Sessions")
    def session_count(self, obj):
        return obj.lab_sessions.count()

    @admin.display(description="Completion %")
    def completion_rate(self, obj):
        total = obj.lab_sessions.count()
        if not total:
            return "—"
        completed = obj.lab_sessions.filter(status="COMPLETED").count()
        pct = int(completed / total * 100)
        color = "green" if pct >= 50 else "orange" if pct >= 25 else "red"
        return format_html('<span style="color:{}">{}%</span>', color, pct)

    @admin.action(description="Activate selected scenarios")
    def action_activate(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} scenario(s).", messages.SUCCESS)

    @admin.action(description="Deactivate selected scenarios")
    def action_deactivate(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} scenario(s).", messages.WARNING)

    @admin.action(description="Set lab mode to docker")
    def action_set_docker(self, request, queryset):
        queryset.update(lab_mode="docker")
        self.message_user(request, "Lab mode set to docker.", messages.SUCCESS)

    @admin.action(description="Set lab mode to simulation")
    def action_set_simulation(self, request, queryset):
        queryset.update(lab_mode="simulation")
        self.message_user(request, "Lab mode set to simulation.", messages.SUCCESS)

    @admin.action(description="Export selected scenarios to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="scenarios.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "slug", "title", "technology", "difficulty", "scenario_type",
            "lab_mode", "infrastructure_type", "is_active", "session_count",
        ])
        for s in queryset.select_related("technology"):
            writer.writerow([
                s.slug, s.title, s.technology.name,
                s.difficulty, s.scenario_type, s.lab_mode,
                s.infrastructure_type, s.is_active,
                s.lab_sessions.count(),
            ])
        return response


# ─── Projects Admin ─────────────────────────────────────────────────────────

class ProjectTaskInline(admin.TabularInline):
    model = ProjectTask
    extra = 1
    fields = ("order", "jira_key", "title", "description", "acceptance_criteria", "hint", "depends_on")
    ordering = ("order",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "technology", "architecture_type", "difficulty", "estimated_hours", "is_active", "order")
    list_filter = ("technology", "architecture_type", "difficulty", "is_active")
    search_fields = ("title", "description")
    list_editable = ("is_active", "order")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ProjectTaskInline]


@admin.register(UserProjectProgress)
class UserProjectProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "project", "status", "started_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "project__title")
    raw_id_fields = ("user", "project")


@admin.register(UserTaskProgress)
class UserTaskProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "task", "status", "completed_at")
    list_filter = ("status",)
    search_fields = ("user__username", "task__title")
    raw_id_fields = ("user", "task")
