from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import (
    RegisterView, LoginView, UserProfileView, ChangePasswordView,
    ForgotPasswordView, ResetPasswordView, LogoutView,
    SendOTPView, VerifyOTPView,
    SocialAuthConfigView, GitHubCallbackView, GoogleCallbackView,
    GitHubLinkView, GoogleLinkView,
    LabHistoryView, SearchView, ContactView,
)

urlpatterns = [
    # Django admin (accessible at /django-admin/ to avoid conflict with frontend /admin/*)
    path("django-admin/", admin.site.urls),

    # AUTH API
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", LoginView.as_view(), name="login"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/auth/send-otp/", SendOTPView.as_view(), name="send_otp"),
    path("api/auth/verify-otp/", VerifyOTPView.as_view(), name="verify_otp"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/profile/", UserProfileView.as_view(), name="profile"),
    path("api/auth/change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("api/auth/forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("api/auth/reset-password/", ResetPasswordView.as_view(), name="reset_password"),

    # Social OAuth
    path("api/auth/social/config/", SocialAuthConfigView.as_view(), name="social_config"),
    path("api/auth/social/github/", GitHubCallbackView.as_view(), name="github_callback"),
    path("api/auth/social/google/", GoogleCallbackView.as_view(), name="google_callback"),
    path("api/auth/social/link/github/", GitHubLinkView.as_view(), name="github_link"),
    path("api/auth/social/link/google/", GoogleLinkView.as_view(), name="google_link"),

    # Search
    path("api/search/", SearchView.as_view(), name="search"),

    # Contact form
    path("api/contact/", ContactView.as_view(), name="contact"),

    # Lab history
    path("api/labs/history/", LabHistoryView.as_view(), name="lab_history"),

    # Organization / team self-service
    path("api/org/", include("apps.accounts.org_urls")),

    # Public health check (for load balancers / orchestrators)
    path("api/health/", include("apps.accounts.health")),

    # Public API (scenarios, labs, progress, leaderboard)
    path("api/", include("apps.public_api.urls")),

    # Notifications API
    path("api/notifications/", include("apps.notifications.urls")),

    # Admin Panel API
    path("api/admin/", include("apps.adminpanel.urls")),

    # Billing / Stripe
    path("api/billing/", include("apps.billing.urls")),

    # Question Bank API (technologies, scenarios CRUD)
    path("api/question_bank/", include("apps.question_bank.urls")),

    # Community Threads
    path("api/community/", include("apps.community.urls")),

    # Ratings
    path("api/ratings/", include("apps.ratings.urls")),

    # Jira integration (webhooks + ticket status)
    path("api/jira/", include("apps.jira_integration.urls")),
]

if settings.DEBUG or getattr(settings, "SERVE_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

