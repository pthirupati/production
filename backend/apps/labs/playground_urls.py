from django.urls import path

from .playground_views import (
    PlaygroundDetailView,
    PlaygroundListView,
    PlaygroundResetView,
    PlaygroundRunView,
)

urlpatterns = [
    path("", PlaygroundListView.as_view(), name="playground-list"),
    path("<slug:slug>/", PlaygroundDetailView.as_view(), name="playground-detail"),
    path("<slug:slug>/run/", PlaygroundRunView.as_view(), name="playground-run"),
    path("<slug:slug>/reset/", PlaygroundResetView.as_view(), name="playground-reset"),
]
