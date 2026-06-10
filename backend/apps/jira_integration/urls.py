from django.urls import path
from . import views, webhooks

app_name = "jira_integration"

urlpatterns = [
    path("webhooks/", webhooks.jira_webhook, name="webhook_receiver"),
    path("tickets/", views.UserJiraTicketsView.as_view(), name="user_tickets"),
    path("tickets/scenario/<int:scenario_id>/", views.ScenarioJiraTicketView.as_view(), name="scenario_ticket"),
    path("issues/<str:issue_key>/", views.JiraIssueDetailView.as_view(), name="issue_detail"),
    path("issues/<str:issue_key>/transition/", views.JiraIssueTransitionView.as_view(), name="issue_transition"),
    path("issues/<str:issue_key>/comments/", views.JiraIssueCommentView.as_view(), name="issue_comment"),
]
