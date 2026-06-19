from django.urls import path

from .views import (
    SupportBotChatView,
    SupportBotConfigView,
    SupportBotFeedbackView,
)

urlpatterns = [
    path("config/", SupportBotConfigView.as_view()),
    path("chat/", SupportBotChatView.as_view()),
    path("feedback/", SupportBotFeedbackView.as_view()),
]
