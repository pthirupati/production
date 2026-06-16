from django.urls import path

from .views import SupportBotChatView, SupportBotConfigView

urlpatterns = [
    path("config/", SupportBotConfigView.as_view()),
    path("chat/", SupportBotChatView.as_view()),
]
