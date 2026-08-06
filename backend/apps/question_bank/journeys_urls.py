"""URL routes for the read-only Learning Journeys API (mounted at /api/journeys/)."""

from django.urls import path

from .journeys_views import JourneyListView, JourneyDetailView, JourneyNextStepView

urlpatterns = [
    path("", JourneyListView.as_view(), name="journey-list"),
    # Must precede <slug:slug> — that pattern would otherwise swallow "next" and
    # 404 it as a journey lookup. The cost is that a journey literally slugged
    # "next" becomes unreachable; the seeded set has no such slug.
    path("next/", JourneyNextStepView.as_view(), name="journey-next-step"),
    path("<slug:slug>/", JourneyDetailView.as_view(), name="journey-detail"),
]
