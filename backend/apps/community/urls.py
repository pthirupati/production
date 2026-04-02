from django.urls import path
from .views import (
    ThreadListView,
    ThreadDetailView,
    ReplyView,
    ReplyDetailView,
    VoteView,
)

urlpatterns = [
    path("threads/", ThreadListView.as_view(), name="thread_list"),
    path("threads/<uuid:thread_id>/", ThreadDetailView.as_view(), name="thread_detail"),
    path("threads/<uuid:thread_id>/replies/", ReplyView.as_view(), name="thread_reply"),
    path("replies/<uuid:reply_id>/", ReplyDetailView.as_view(), name="reply_detail"),
    path("threads/<uuid:thread_id>/vote/", VoteView.as_view(), name="thread_vote"),
    path("replies/<uuid:reply_id>/vote/", VoteView.as_view(), name="reply_vote"),
]
