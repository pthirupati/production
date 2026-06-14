from django.urls import path
from .views import (
    ThreadListView,
    ThreadDetailView,
    ReplyView,
    ReplyDetailView,
    VoteView,
    ThreadAttachmentUploadView,
    ReplyReactionView,
    ThreadReportView,
)

urlpatterns = [
    path("threads/", ThreadListView.as_view(), name="thread_list"),
    path("threads/<uuid:thread_id>/", ThreadDetailView.as_view(), name="thread_detail"),
    path("threads/<uuid:thread_id>/replies/", ReplyView.as_view(), name="thread_reply"),
    path("threads/<uuid:thread_id>/attachments/", ThreadAttachmentUploadView.as_view(), name="thread_attachment"),
    path("replies/<uuid:reply_id>/", ReplyDetailView.as_view(), name="reply_detail"),
    path("replies/<uuid:reply_id>/react/", ReplyReactionView.as_view(), name="reply_react"),
    path("threads/<uuid:thread_id>/vote/", VoteView.as_view(), name="thread_vote"),
    path("threads/<uuid:thread_id>/report/", ThreadReportView.as_view(), name="thread_report"),
    path("replies/<uuid:reply_id>/vote/", VoteView.as_view(), name="reply_vote"),
]
