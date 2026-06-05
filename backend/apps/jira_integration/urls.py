from django.urls import path
from . import views, webhooks

app_name = "jira_integration"

urlpatterns = [
    path("webhooks/", webhooks.jira_webhook, name="webhook_receiver"),
    path("tickets/", views.UserJiraTicketsView.as_view(), name="user_tickets"),
    path("tickets/scenario/<int:scenario_id>/", views.ScenarioJiraTicketView.as_view(), name="scenario_ticket"),
]
