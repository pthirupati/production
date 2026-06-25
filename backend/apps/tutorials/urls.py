from django.urls import path

from .views import (
    TutorialContinueView,
    TutorialCurriculumView,
    TutorialDetailView,
    TutorialListView,
    TutorialProgressListView,
    TutorialProgressUpdateView,
)

urlpatterns = [
    path("", TutorialListView.as_view(), name="tutorial-list"),
    path("curriculum/", TutorialCurriculumView.as_view(), name="tutorial-curriculum"),
    path("progress/", TutorialProgressListView.as_view(), name="tutorial-progress-list"),
    path("progress/continue/", TutorialContinueView.as_view(), name="tutorial-progress-continue"),
    path("<slug:slug>/progress/", TutorialProgressUpdateView.as_view(), name="tutorial-progress-update"),
    path("<slug:slug>/", TutorialDetailView.as_view(), name="tutorial-detail"),
]
