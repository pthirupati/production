from django.urls import path
from .views import NotificationListView, NotificationMarkReadView, NotificationPreferenceView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("read/", NotificationMarkReadView.as_view(), name="mark-all-read"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="mark-read"),
    path("preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
]
