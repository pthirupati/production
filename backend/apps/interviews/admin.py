"""
Interviews admin — all interview-related models.
"""
import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    AsyncVideoResponse,
    CandidateProfile,
    InterviewAdminJoinRequest,
    InterviewCampaign,
    InterviewCertificate,
    InterviewEntitlement,
    InterviewInvitation,
    InterviewMessage,
    InterviewPlanTier,
    InterviewPlatformSettings,
    InterviewQuestion,
    InterviewReport,
    InterviewRound,
    InterviewTemplate,
    InterviewVoiceOption,
)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class CampaignStatusFilter(admin.SimpleListFilter):
    title = "campaign status"
    parameter_name = "camp_status"

    def lookups(self, request, model_admin):
        return InterviewCampaign.STATUS_CHOICES

    def queryset(self, qs, value):
        if value:
            return qs.filter(status=value)
        return qs


class SampleCampaignFilter(admin.SimpleListFilter):
    title = "type"
    parameter_name = "sample"

    def lookups(self, request, model_admin):
        return [("sample", "Free sample"), ("paid", "Paid")]

    def queryset(self, qs, value):
        if value == "sample":
            return qs.filter(is_sample=True)
        if value == "paid":
            return qs.filter(is_sample=False)
        return qs


class EntitlementExpiredFilter(admin.SimpleListFilter):
    title = "entitlement validity"
    parameter_name = "ent_valid"

    def lookups(self, request, model_admin):
        return [("active", "Active"), ("expired", "Expired")]

    def queryset(self, qs, value):
        now = timezone.now()
        if value == "active":
            return qs.filter(is_active=True).filter(
                period_end__isnull=True
            ) | qs.filter(is_active=True, period_end__gt=now)
        if value == "expired":
            return qs.filter(is_active=False) | qs.filter(is_active=True, period_end__lte=now)
        return qs


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class InterviewRoundInline(admin.TabularInline):
    model = InterviewRound
    fields = (
        "round_number", "round_type", "title", "status",
        "duration_minutes", "overall_score", "started_at", "ended_at",
    )
    readonly_fields = ("round_number", "round_type", "status", "overall_score", "started_at", "ended_at")
    extra = 0
    can_delete = False
    ordering = ("round_number",)
    show_change_link = True


# ---------------------------------------------------------------------------
# Plan Tier admin
# ---------------------------------------------------------------------------

@admin.register(InterviewPlanTier)
class InterviewPlanTierAdmin(admin.ModelAdmin):
    list_display = (
        "name", "code", "price_inr", "interviews_per_month",
        "max_rounds", "voice_enabled", "practical_enabled",
        "certificate_enabled", "is_active", "order",
    )
    list_filter = ("is_active", "voice_enabled", "practical_enabled")
    search_fields = ("name", "code")
    list_editable = ("is_active", "order")
    ordering = ("order", "price_inr")


# ---------------------------------------------------------------------------
# Campaign admin
# ---------------------------------------------------------------------------

@admin.register(InterviewCampaign)
class InterviewCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "user",
        "primary_technology",
        "experience_level",
        "status_badge",
        "is_sample",
        "round_count",
        "current_round_number",
        "overall_score",
        "created_at",
    )
    list_filter = (
        CampaignStatusFilter,
        SampleCampaignFilter,
        "experience_level",
        ("created_at", admin.DateFieldListFilter),
        ("primary_technology", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "title")
    readonly_fields = (
        "id", "user", "status", "profile_snapshot",
        "created_at", "updated_at", "completed_at",
        "current_round_number", "overall_score",
    )
    list_select_related = ("user", "primary_technology")
    date_hierarchy = "created_at"
    inlines = [InterviewRoundInline]
    actions = ["action_cancel", "action_export_csv"]

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.id)[:8] + "..."

    @admin.display(description="Status")
    def status_badge(self, obj):
        colors = {
            "in_progress": "blue",
            "completed": "green",
            "failed": "red",
            "cancelled": "grey",
            "scheduled": "orange",
            "draft": "grey",
        }
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>',
            colors.get(obj.status, "black"),
            obj.status,
        )

    @admin.action(description="Cancel selected campaigns")
    def action_cancel(self, request, queryset):
        active = queryset.filter(status__in=["draft", "scheduled", "in_progress"])
        count = active.update(status="cancelled")
        self.message_user(request, f"Cancelled {count} campaign(s).", messages.WARNING)

    @admin.action(description="Export selected campaigns to CSV")
    def action_export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="campaigns.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "id", "user", "email", "technology", "experience_level",
            "status", "is_sample", "round_count", "overall_score",
            "created_at", "completed_at",
        ])
        for c in queryset.select_related("user", "primary_technology"):
            writer.writerow([
                str(c.id), c.user.username, c.user.email,
                c.primary_technology.name if c.primary_technology else "",
                c.experience_level, c.status, c.is_sample, c.round_count,
                c.overall_score or "",
                c.created_at.isoformat() if c.created_at else "",
                c.completed_at.isoformat() if c.completed_at else "",
            ])
        return response


# ---------------------------------------------------------------------------
# Round admin
# ---------------------------------------------------------------------------

class InterviewMessageInline(admin.TabularInline):
    model = InterviewMessage
    fields = ("role", "content_preview", "created_at")
    readonly_fields = ("role", "content_preview", "created_at")
    extra = 0
    can_delete = False
    ordering = ("created_at",)

    @admin.display(description="Content")
    def content_preview(self, obj):
        content = getattr(obj, "content", "") or ""
        return content[:120]


@admin.register(InterviewRound)
class InterviewRoundAdmin(admin.ModelAdmin):
    list_display = (
        "short_id",
        "campaign_user",
        "round_number",
        "round_type",
        "status",
        "overall_score",
        "duration_minutes",
        "started_at",
        "ended_at",
    )
    list_filter = (
        "status",
        "round_type",
        ("started_at", admin.DateFieldListFilter),
    )
    search_fields = ("campaign__user__username", "campaign__user__email", "title")
    readonly_fields = (
        "id", "campaign", "round_number", "round_type",
        "invite_token", "started_at", "ended_at", "ends_at",
        "overall_score", "questions_asked", "strong_answers_streak",
        "created_at",
    )
    list_select_related = ("campaign__user",)
    date_hierarchy = "created_at"
    inlines = [InterviewMessageInline]

    @admin.display(description="ID")
    def short_id(self, obj):
        return str(obj.id)[:8] + "..."

    @admin.display(description="User")
    def campaign_user(self, obj):
        return obj.campaign.user.username


# ---------------------------------------------------------------------------
# Question Bank admin
# ---------------------------------------------------------------------------

@admin.register(InterviewQuestion)
class InterviewQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "content_preview",
        "category",
        "difficulty",
        "technology",
        "round_types_preview",
        "is_active",
        "created_at",
    )
    list_filter = (
        "category",
        "difficulty",
        "is_active",
        ("technology", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("question_text", "slug", "expected_keywords")
    list_per_page = 50
    actions = ["action_activate", "action_deactivate"]

    @admin.display(description="Question")
    def content_preview(self, obj):
        return obj.question_text[:80]

    @admin.display(description="Round types")
    def round_types_preview(self, obj):
        types = obj.round_types or []
        return ", ".join(types) if types else "—"

    @admin.action(description="Activate selected questions")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "Questions activated.", messages.SUCCESS)

    @admin.action(description="Deactivate selected questions")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Questions deactivated.", messages.WARNING)


# ---------------------------------------------------------------------------
# Entitlement admin
# ---------------------------------------------------------------------------

@admin.register(InterviewEntitlement)
class InterviewEntitlementAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan_tier",
        "interviews_remaining",
        "is_active",
        "is_admin_granted_free",
        "period_end",
        "updated_at",
    )
    list_filter = (
        "is_active",
        "is_admin_granted_free",
        EntitlementExpiredFilter,
        ("plan_tier", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "updated_at")
    list_select_related = ("user", "plan_tier")
    date_hierarchy = "updated_at"
    actions = ["action_revoke"]

    @admin.action(description="Revoke selected entitlements")
    def action_revoke(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Revoked {count} entitlement(s).", messages.WARNING)


# ---------------------------------------------------------------------------
# Candidate profile admin
# ---------------------------------------------------------------------------

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "experience_level",
        "years_experience",
        "primary_technology",
        "current_company",
        "target_role",
        "location",
        "updated_at",
    )
    list_filter = (
        "experience_level",
        ("primary_technology", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("user__username", "user__email", "current_company", "target_role", "location")
    readonly_fields = ("user", "created_at", "updated_at", "resume_parsed")
    list_select_related = ("user", "primary_technology")


# ---------------------------------------------------------------------------
# Certificate admin
# ---------------------------------------------------------------------------

@admin.register(InterviewCertificate)
class InterviewCertificateAdmin(admin.ModelAdmin):
    list_display = ("user", "campaign", "issued_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "campaign", "issued_at")
    list_select_related = ("user", "campaign")
    date_hierarchy = "issued_at"


# ---------------------------------------------------------------------------
# Report admin
# ---------------------------------------------------------------------------

@admin.register(InterviewReport)
class InterviewReportAdmin(admin.ModelAdmin):
    list_display = ("round", "overall_score", "passed", "generated_at")
    list_filter = ("passed",)
    readonly_fields = (
        "round", "overall_score", "passed", "strengths",
        "improvements", "summary",
        "question_breakdown", "study_plan", "generated_at",
    )
    list_select_related = ("round__campaign__user",)
    date_hierarchy = "generated_at"


# ---------------------------------------------------------------------------
# Voice options admin
# ---------------------------------------------------------------------------

@admin.register(InterviewVoiceOption)
class InterviewVoiceOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "locale", "is_active")
    list_filter = ("is_active", "locale")
    search_fields = ("label", "code", "browser_voice_hint")
    list_editable = ("is_active",)


# ---------------------------------------------------------------------------
# Admin join requests
# ---------------------------------------------------------------------------

@admin.register(InterviewAdminJoinRequest)
class InterviewAdminJoinRequestAdmin(admin.ModelAdmin):
    list_display = ("round", "admin_user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("admin_user__username",)
    readonly_fields = ("round", "admin_user", "observer_token", "created_at")
    list_select_related = ("admin_user", "round")


# ---------------------------------------------------------------------------
# Platform settings (singleton)
# ---------------------------------------------------------------------------

@admin.register(InterviewPlatformSettings)
class InterviewPlatformSettingsAdmin(admin.ModelAdmin):
    """Singleton settings — prevent add and show only one change view."""

    def has_add_permission(self, request):
        return not InterviewPlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Templates / invitations / async video (parity features)
# ---------------------------------------------------------------------------

@admin.register(InterviewTemplate)
class InterviewTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name", "role_title", "primary_technology", "experience_level",
        "round_count", "is_public", "is_active", "times_used", "order",
    )
    list_filter = ("is_public", "is_active", "experience_level")
    search_fields = ("name", "slug", "role_title")
    list_editable = ("is_public", "is_active", "order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(InterviewInvitation)
class InterviewInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "candidate_email", "role_title", "mode", "status",
        "created_by", "email_sent", "created_at",
    )
    list_filter = ("status", "mode", "email_sent")
    search_fields = ("candidate_email", "candidate_name", "role_title")
    readonly_fields = ("token", "campaign", "accepted_by", "created_at")
    list_select_related = ("created_by", "template")


@admin.register(AsyncVideoResponse)
class AsyncVideoResponseAdmin(admin.ModelAdmin):
    list_display = ("round", "question_index", "score", "duration_seconds", "created_at")
    search_fields = ("round__campaign__user__email",)
    readonly_fields = ("round", "created_at", "analysis")
    list_select_related = ("round__campaign__user",)
