from django.urls import path
from .views import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationDismissView,
    NotificationDismissAllView,
    NotificationPreferenceView,
    MarketingUnsubscribeView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("read/", NotificationMarkReadView.as_view(), name="mark-all-read"),
    path("clear/", NotificationDismissAllView.as_view(), name="clear-all"),
    path("<int:pk>/read/", NotificationMarkReadView.as_view(), name="mark-read"),
    path("<int:pk>/", NotificationDismissView.as_view(), name="dismiss-notification"),
    path("preferences/", NotificationPreferenceView.as_view(), name="notification-preferences"),
    path("unsubscribe/", MarketingUnsubscribeView.as_view(), name="marketing-unsubscribe"),
]
