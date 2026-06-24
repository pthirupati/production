from django.urls import path

from .billing_views import CertRazorpayOrderView, CertRazorpayVerifyView
from .views import (
    AdminTrackDetailView,
    AdminTrackListView,
    AdminTrackScenariosView,
    CertVerifyView,
    ExamDetailView,
    ExamStartView,
    ExamSubmitView,
    MyCertificatesView,
    MyCertDashboardView,
    TrackDetailView,
    TrackListView,
)

urlpatterns = [
    path("", TrackListView.as_view(), name="cert-track-list"),
    path("dashboard/", MyCertDashboardView.as_view(), name="cert-dashboard"),
    path("certificates/", MyCertificatesView.as_view(), name="cert-my-certificates"),
    path("certificate/verify/", CertVerifyView.as_view(), name="cert-verify"),
    path("billing/razorpay/order/", CertRazorpayOrderView.as_view(), name="cert-razorpay-order"),
    path("billing/razorpay/verify/", CertRazorpayVerifyView.as_view(), name="cert-razorpay-verify"),
    # Admin (IsPlatformAdmin) — track management. Listed before the <slug>
    # catch-all so "admin" is never mistaken for a track slug.
    path("admin/tracks/", AdminTrackListView.as_view(), name="cert-admin-track-list"),
    path("admin/tracks/<int:pk>/", AdminTrackDetailView.as_view(), name="cert-admin-track-detail"),
    path(
        "admin/tracks/<int:pk>/scenarios/",
        AdminTrackScenariosView.as_view(),
        name="cert-admin-track-scenarios",
    ),
    path("exam/<uuid:attempt_id>/", ExamDetailView.as_view(), name="cert-exam-detail"),
    path("exam/<uuid:attempt_id>/submit/", ExamSubmitView.as_view(), name="cert-exam-submit"),
    path("<slug:slug>/", TrackDetailView.as_view(), name="cert-track-detail"),
    path("<slug:slug>/exam/start/", ExamStartView.as_view(), name="cert-exam-start"),
]
