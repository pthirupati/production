from django.urls import path
from .views import RateView, RatingsListView

urlpatterns = [
    path("rate/", RateView.as_view(), name="rate"),
    path("", RatingsListView.as_view(), name="ratings_list"),
]
