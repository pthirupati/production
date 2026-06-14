from django.urls import path
from .views import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationDismissView,
    NotificationPreferenceView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("read/", NotificationMarkReadView.as_view(), name="mark-all-read"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="mark-read"),
    path("<int:pk>/", NotificationDismissView.as_view(), name="dismiss-notification"),
    path("preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
]
