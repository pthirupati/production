"""URL routes for the read-only Learning Journeys API (mounted at /api/journeys/)."""

from django.urls import path

from .journeys_views import JourneyListView, JourneyDetailView

urlpatterns = [
    path("", JourneyListView.as_view(), name="journey-list"),
    path("<slug:slug>/", JourneyDetailView.as_view(), name="journey-detail"),
]
