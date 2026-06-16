"""
Admin panel models admin — PlatformSettings (singleton) and BlogPost.
Also registers a custom AdminSite subclass that adds a live metrics dashboard
to the Django admin index page.
"""
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import Group
from django.db.models import Count, Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .models import BlogPost, PlatformSettings


# ---------------------------------------------------------------------------
# Custom Admin Site with dashboard
# ---------------------------------------------------------------------------

class FixitLabAdminSite(admin.AdminSite):
    """
    Extends Django's default AdminSite to inject a live metrics panel at the
    top of the index page via a custom view, and replace the site header/title.
    """

    site_header = "FixitLab Platform Admin"
    site_title = "FixitLab Admin"
    index_title = "Platform Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("dashboard-metrics/", self.admin_view(self.dashboard_metrics_view), name="dashboard_metrics"),
        ]
        return custom + urls

    def dashboard_metrics_view(self, request):
        """
        Lightweight metrics payload consumed by the custom index template
        via an AJAX poll (or rendered server-side on load).
        """
        from django.contrib.auth.models import User
        from django.http import JsonResponse

        from apps.billing.models import PaymentTransaction
        from apps.interviews.models import InterviewCampaign
        from apps.labs.models import LabSession

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        active_labs = LabSession.objects.filter(status__in=["RUNNING", "PROVISIONING"]).count()
        stuck_labs = LabSession.objects.filter(
            status="PROVISIONING",
            started_at__lt=now - timedelta(minutes=10),
        ).count()
        labs_today = LabSession.objects.filter(started_at__gte=today_start).count()
        completions_today = LabSession.objects.filter(
            status="COMPLETED", ended_at__gte=today_start,
        ).count()
        new_users_today = User.objects.filter(date_joined__gte=today_start).count()
        new_users_week = User.objects.filter(date_joined__gte=week_ago).count()
        total_users = User.objects.count()
        revenue_week = PaymentTransaction.objects.filter(
            status="success", created_at__gte=week_ago,
        ).aggregate(total=Sum("amount"))["total"] or 0
        active_interviews = InterviewCampaign.objects.filter(status="in_progress").count()

        maintenance_active = False
        try:
            from apps.adminpanel.platform_config import get_settings_row, is_maintenance_active
            row = get_settings_row()
            maintenance_active = is_maintenance_active(row)
        except Exception:
            pass

        return JsonResponse({
            "active_labs": active_labs,
            "stuck_labs": stuck_labs,
            "labs_today": labs_today,
            "completions_today": completions_today,
            "new_users_today": new_users_today,
            "new_users_week": new_users_week,
            "total_users": total_users,
            "revenue_week_inr": float(revenue_week),
            "active_interviews": active_interviews,
            "maintenance_active": maintenance_active,
        })

    def index(self, request, extra_context=None):
        """
        Augment the standard index with pre-fetched metrics for the first render.
        Subsequent updates are done via the dashboard-metrics/ JSON endpoint
        polled every 30 seconds from an inline script.
        """
        from django.contrib.auth.models import User

        from apps.billing.models import PaymentTransaction
        from apps.interviews.models import InterviewCampaign
        from apps.labs.models import LabSession

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        extra_context = extra_context or {}

        try:
            extra_context["metrics"] = {
                "active_labs": LabSession.objects.filter(status__in=["RUNNING", "PROVISIONING"]).count(),
                "stuck_labs": LabSession.objects.filter(
                    status="PROVISIONING", started_at__lt=now - timedelta(minutes=10),
                ).count(),
                "labs_today": LabSession.objects.filter(started_at__gte=today_start).count(),
                "completions_today": LabSession.objects.filter(
                    status="COMPLETED", ended_at__gte=today_start,
                ).count(),
                "new_users_today": User.objects.filter(date_joined__gte=today_start).count(),
                "new_users_week": User.objects.filter(date_joined__gte=week_ago).count(),
                "total_users": User.objects.count(),
                "revenue_week_inr": float(
                    PaymentTransaction.objects.filter(
                        status="success", created_at__gte=week_ago,
                    ).aggregate(total=Sum("amount"))["total"] or 0
                ),
                "active_interviews": InterviewCampaign.objects.filter(status="in_progress").count(),
                "failed_labs_today": LabSession.objects.filter(
                    status="FAILED", ended_at__gte=today_start,
                ).count(),
                "top_scenarios": list(
                    LabSession.objects.filter(started_at__gte=week_ago)
                    .values("scenario__slug", "scenario__title")
                    .annotate(count=Count("id"))
                    .order_by("-count")[:5]
                ),
            }
        except Exception:
            extra_context["metrics"] = {}

        return super().index(request, extra_context)


# Instantiate — wire into urls.py (see note below)
# In backend/urls.py replace: admin.site.urls
# with:  from apps.adminpanel.admin import fixitlab_admin_site; path("admin/", fixitlab_admin_site.urls)
fixitlab_admin_site = FixitLabAdminSite(name="fixitlab_admin")


# ---------------------------------------------------------------------------
# Register default Django models on the custom site too
# ---------------------------------------------------------------------------
# (These get auto-discovered by INSTALLED_APPS registration via autodiscover_models,
# but the *custom* site needs explicit re-registration or a copy of the default
# autodiscovery. The simplest production approach: keep using admin.site and add
# the dashboard view as a separate URL.  See INTEGRATION NOTE at bottom.)


# ---------------------------------------------------------------------------
# PlatformSettings admin (singleton)
# ---------------------------------------------------------------------------

@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """Singleton settings row — block adding a second row."""

    fieldsets = (
        ("Emails", {
            "fields": ("primary_email", "payment_email", "support_email"),
        }),
        ("Currency & Display", {
            "fields": ("admin_display_currency",),
        }),
        ("Maintenance", {
            "fields": (
                "maintenance_enabled",
                "maintenance_message",
                "maintenance_banner_image",
                "maintenance_banner_style",
                "maintenance_scheduled_start",
                "maintenance_scheduled_end",
                "maintenance_notify_users",
                "maintenance_banner_enabled",
            ),
        }),
        ("Promo Banners", {
            "fields": ("promo_banners_enabled", "promo_banners"),
        }),
        ("Theme", {
            "fields": ("theme_colors",),
        }),
        ("Changelog", {
            "fields": ("changelog",),
        }),
        ("Support Bot", {
            "fields": (
                "support_bot_enabled",
                "support_bot_name",
                "support_bot_welcome_message",
                "support_bot_quick_topics",
                "support_bot_custom_faq",
                "support_bot_typing_delay_ms",
            ),
        }),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        """Redirect the list view directly to the singleton change page."""
        obj, _ = PlatformSettings.objects.get_or_create(pk=1)
        from django.shortcuts import redirect
        return redirect(f"/django-admin/adminpanel/platformsettings/{obj.pk}/change/")


# ---------------------------------------------------------------------------
# BlogPost admin
# ---------------------------------------------------------------------------

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "slug",
        "author_name",
        "category",
        "read_minutes",
        "is_published",
        "published_at",
    )
    list_filter = (
        "is_published",
        "category",
        ("published_at", admin.DateFieldListFilter),
    )
    search_fields = ("title", "slug", "excerpt", "content", "author_name")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("id", "created_at", "updated_at")
    list_editable = ("is_published",)
    date_hierarchy = "published_at"
    actions = ["action_publish", "action_unpublish"]

    @admin.action(description="Publish selected posts")
    def action_publish(self, request, queryset):
        count = queryset.update(is_published=True, published_at=timezone.now())
        self.message_user(request, f"Published {count} post(s).", admin.ModelAdmin.message_user)

    @admin.action(description="Unpublish selected posts")
    def action_unpublish(self, request, queryset):
        queryset.update(is_published=False)
        self.message_user(request, "Posts unpublished.")


# ---------------------------------------------------------------------------
# INTEGRATION NOTE
# ---------------------------------------------------------------------------
# To wire the dashboard_metrics endpoint into your existing Django admin,
# add the following to your root urls.py BEFORE the default admin include:
#
#   from apps.adminpanel.admin import fixitlab_admin_site
#   urlpatterns = [
#       path("admin/metrics/", fixitlab_admin_site.dashboard_metrics_view),
#       path("admin/", admin.site.urls),
#       ...
#   ]
#
# Or, replace the default admin site entirely:
#   In apps/adminpanel/apps.py add:
#       default_auto_field = "django.db.models.BigAutoField"
#   In settings.py add:
#       INSTALLED_APPS uses "django.contrib.admin" — it will autodiscover.
#   In urls.py:
#       path("django-admin/", fixitlab_admin_site.urls),
#       path("admin/", include("apps.adminpanel.urls")),  # your custom REST API
