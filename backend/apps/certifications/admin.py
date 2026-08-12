from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    CertEarnedCertificate,
    CertificationTrack,
    CertificationTrackSubscription,
    CertObjective,
    ExamAttempt,
    TrackScenario,
)


class CertObjectiveInline(admin.TabularInline):
    model = CertObjective
    extra = 0


@admin.register(CertificationTrack)
class CertificationTrackAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "vendor", "price", "addon_price", "is_free",
        "is_active", "coming_soon", "maintenance_enabled", "order",
    )
    list_filter = ("is_active", "is_free", "coming_soon", "maintenance_enabled", "vendor")
    list_editable = ("price", "addon_price", "is_free", "is_active", "coming_soon")
    search_fields = ("code", "name", "slug")
    prepopulated_fields = {"slug": ("code",)}
    inlines = [CertObjectiveInline]


@admin.register(CertificationTrackSubscription)
class CertificationTrackSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("subscription_id", "user", "track", "is_active", "expires_at", "created_at")
    list_filter = ("is_active", "track")
    search_fields = ("subscription_id", "user__email", "track__code")


@admin.register(CertObjective)
class CertObjectiveAdmin(admin.ModelAdmin):
    list_display = ("code", "track", "title", "weight", "order")
    list_filter = ("track",)
    search_fields = ("code", "title")


@admin.register(TrackScenario)
class TrackScenarioAdmin(admin.ModelAdmin):
    list_display = ("objective", "scenario", "order", "in_exam_pool")
    list_filter = ("objective__track", "in_exam_pool")
    search_fields = ("scenario__slug", "objective__code")
    raw_id_fields = ("scenario",)


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "track", "status", "score", "started_at", "expires_at")
    list_filter = ("status", "track")
    search_fields = ("user__email",)


@admin.register(CertEarnedCertificate)
class CertEarnedCertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_id", "user", "track", "score",
        "validity", "issued_at", "expires_at",
    )
    list_filter = ("track", "revoked")
    search_fields = ("certificate_id", "user__email", "holder_name")
    readonly_fields = ("revoked_at",)
    actions = ("action_revoke_grader_defect", "action_revoke", "action_reinstate")

    @admin.display(description="Status", ordering="revoked")
    def validity(self, obj):
        if obj.revoked:
            return format_html(
                '<b style="color:#b91c1c">REVOKED</b><br><small>{}</small>',
                (obj.revoked_reason or "no reason recorded")[:60],
            )
        if obj.is_expired:
            return format_html('<span style="color:#d97706">expired</span>')
        return format_html('<span style="color:#15803d">valid</span>')

    @admin.action(description="Revoke — issued against a defective grader")
    def action_revoke_grader_defect(self, request, queryset):
        """The reason this feature exists.

        A number of certificates were earned against fail-open graders (audit
        section G). Pre-filling the reason keeps the public verification message
        honest and consistent instead of leaving revoked_reason blank.
        """
        n = 0
        for cert in queryset.filter(revoked=False):
            cert.revoke("Issued against a scenario grader later found defective; "
                        "re-take the exam to earn it again.")
            n += 1
        messages.success(request, f"{n} certificate(s) revoked (grader defect).")

    @admin.action(description="Revoke selected certificates")
    def action_revoke(self, request, queryset):
        n = 0
        for cert in queryset.filter(revoked=False):
            cert.revoke("Revoked by an administrator.")
            n += 1
        messages.success(request, f"{n} certificate(s) revoked.")

    @admin.action(description="Reinstate selected certificates")
    def action_reinstate(self, request, queryset):
        """Revocation must be reversible — an operator mistake should not be
        permanent, and deleting was never a real option (see the model comment)."""
        n = queryset.filter(revoked=True).update(
            revoked=False, revoked_at=None, revoked_reason="",
        )
        messages.success(request, f"{n} certificate(s) reinstated.")
