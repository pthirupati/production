from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index, sitemap as sitemap_section
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.permissions import IsAdminUser
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.public_api.sitemaps import SITEMAPS

from apps.accounts.views import (
    RegisterView, LoginView, UserProfileView, ChangePasswordView,
    ForgotPasswordView, ResetPasswordView, LogoutView, DeleteAccountView,
    SendOTPView, VerifyOTPView,
    SocialAuthConfigView, SocialOAuthStartView, GitHubCallbackView, GoogleCallbackView,
    GitHubLinkView, GoogleLinkView,
    LabHistoryView, SearchView, ContactView,
    CookieTokenRefreshView,
)
from apps.billing.sales_views import SalesInquiryView

urlpatterns = [
    # Public SEO sitemap (AllowAny). The index at /sitemap.xml links to one
    # /sitemap-<section>.xml per catalog section (scenarios, tutorials, projects,
    # technologies, static). Served through the nginx gateway; not under an
    # admin-IP-restricted or auth-gated prefix.
    path(
        "sitemap.xml",
        sitemap_index,
        {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap_section"},
        name="sitemap_index",
    ),
    path(
        "sitemap-<section>.xml",
        sitemap_section,
        {"sitemaps": SITEMAPS},
        name="sitemap_section",
    ),

    # Django admin (accessible at /django-admin/ to avoid conflict with frontend /admin/*)
    path("django-admin/", admin.site.urls),

    # AUTH API
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/auth/send-otp/", SendOTPView.as_view(), name="send_otp"),
    path("api/auth/verify-otp/", VerifyOTPView.as_view(), name="verify_otp"),
    path("api/auth/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/profile/", UserProfileView.as_view(), name="profile"),
    path("api/auth/account/delete/", DeleteAccountView.as_view(), name="delete_account"),
    path("api/auth/change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("api/auth/forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("api/auth/reset-password/", ResetPasswordView.as_view(), name="reset_password"),

    # Social OAuth
    path("api/auth/social/config/", SocialAuthConfigView.as_view(), name="social_config"),
    path("api/auth/social/start/<str:provider>/", SocialOAuthStartView.as_view(), name="social_oauth_start"),
    path("api/auth/social/github/", GitHubCallbackView.as_view(), name="github_callback"),
    path("api/auth/social/google/", GoogleCallbackView.as_view(), name="google_callback"),
    path("api/auth/social/link/github/", GitHubLinkView.as_view(), name="github_link"),
    path("api/auth/social/link/google/", GoogleLinkView.as_view(), name="google_link"),

    # Search
    path("api/search/", SearchView.as_view(), name="search"),

    # Contact form
    path("api/contact/", ContactView.as_view(), name="contact"),

    # Teams/Org "Contact Sales" inquiry (public, AllowAny)
    path("api/sales/inquiry/", SalesInquiryView.as_view(), name="sales_inquiry"),

    # Lab history
    path("api/labs/history/", LabHistoryView.as_view(), name="lab_history"),

    # Live Incident Director + public postmortem artifact (apps.labs)
    path("api/labs/", include("apps.labs.incident_urls")),

    # Organization / team self-service
    path("api/org/", include("apps.accounts.org_urls")),

    # Public health check (for load balancers / orchestrators)
    path("api/health/", include("apps.accounts.health")),

    # Public API (scenarios, labs, progress, leaderboard)
    path("api/", include("apps.public_api.urls")),

    # Public Tutorials (free written content)
    path("api/tutorials/", include("apps.tutorials.urls")),
    # Certification tracks (objective-mapped views over existing scenarios)
    path("api/certifications/", include("apps.certifications.urls")),

    # Public Playgrounds (free, ephemeral try-instantly sandboxes)
    path("api/playgrounds/", include("apps.labs.playground_urls")),

    # Notifications API
    path("api/notifications/", include("apps.notifications.urls")),

    # Admin Panel API
    path("api/admin/", include("apps.adminpanel.urls")),

    # Billing / Stripe
    path("api/billing/", include("apps.billing.urls")),

    # Question Bank API (technologies, scenarios CRUD)
    path("api/question_bank/", include("apps.question_bank.urls")),

    # Learning Journeys (read-only, AllowAny — role-based guided tracks over
    # existing tutorial courses, scenarios, projects, and certification tracks)
    path("api/journeys/", include("apps.question_bank.journeys_urls")),

    # Community Threads
    path("api/community/", include("apps.community.urls")),

    # Ratings
    path("api/ratings/", include("apps.ratings.urls")),

    # Jira integration (webhooks + ticket status)
    path("api/jira/", include("apps.jira_integration.urls")),

    # Floating support assistant
    path("api/support/", include("apps.support.urls")),

    # AI Interview Studio
    path("api/interviews/", include("apps.interviews.urls")),

    # VMware vCenter Simulator
    path("api/vmware/", include("apps.vmware_sim.urls")),

    # ITSM (ServiceNow-style ticketing simulation)
    path("api/itsm/", include("apps.itsm.urls")),

    # OpenAPI schema + Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[IsAdminUser]), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[IsAdminUser]), name="swagger-ui"),
]

if settings.DEBUG or getattr(settings, "SERVE_MEDIA", False):
    # NOTE: django.conf.urls.static.static() short-circuits to [] whenever
    # DEBUG is False, so it CANNOT serve media in production even with
    # SERVE_MEDIA=True. In the 4-droplet cluster the App node (D2) runs with
    # DEBUG=False but must still answer /media/ (the edge gateway proxies
    # /media/ to it — see gateway/nginx.cluster.conf.template). Wire the static
    # serve view directly so it works regardless of DEBUG.
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    else:
        from django.urls import re_path
        from django.views.static import serve as _serve_media

        _media_prefix = settings.MEDIA_URL.lstrip("/")
        urlpatterns += [
            re_path(
                rf"^{_media_prefix}(?P<path>.*)$",
                _serve_media,
                {"document_root": settings.MEDIA_ROOT},
            ),
        ]

