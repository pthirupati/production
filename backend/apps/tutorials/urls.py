from django.urls import path

from .views import TutorialDetailView, TutorialListView

urlpatterns = [
    path("", TutorialListView.as_view(), name="tutorial-list"),
    path("<slug:slug>/", TutorialDetailView.as_view(), name="tutorial-detail"),
]
