from django.urls import path

from .views import TutorialCurriculumView, TutorialDetailView, TutorialListView

urlpatterns = [
    path("", TutorialListView.as_view(), name="tutorial-list"),
    path("curriculum/", TutorialCurriculumView.as_view(), name="tutorial-curriculum"),
    path("<slug:slug>/", TutorialDetailView.as_view(), name="tutorial-detail"),
]
