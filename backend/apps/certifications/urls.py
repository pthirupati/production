from django.urls import path

from .views import (
    CertVerifyView,
    ExamDetailView,
    ExamStartView,
    ExamSubmitView,
    MyCertificatesView,
    TrackDetailView,
    TrackListView,
)

urlpatterns = [
    path("", TrackListView.as_view(), name="cert-track-list"),
    path("certificates/", MyCertificatesView.as_view(), name="cert-my-certificates"),
    path("certificate/verify/", CertVerifyView.as_view(), name="cert-verify"),
    path("exam/<uuid:attempt_id>/", ExamDetailView.as_view(), name="cert-exam-detail"),
    path("exam/<uuid:attempt_id>/submit/", ExamSubmitView.as_view(), name="cert-exam-submit"),
    path("<slug:slug>/", TrackDetailView.as_view(), name="cert-track-detail"),
    path("<slug:slug>/exam/start/", ExamStartView.as_view(), name="cert-exam-start"),
]
