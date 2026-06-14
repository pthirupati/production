from django.urls import path
from .views import (
    AdminOverviewView,
    AdminTechnologiesView,
    AdminTechnologyDetailView,
    AdminTagsView,
    AdminTagDetailView,
    AdminScenariosView,
    AdminScenarioDetailView,
    AdminHintsView,
    AdminHintDetailView,
    AdminUsersView,
    AdminUserDetailView,
    AdminBulkUsersView,
    AdminBulkLabsView,
    AdminActiveLabsView,
    AdminTerminateLabView,
    AdminTerminateAllIdleLabsView,
    AdminMonitoringContainersView,
    AdminMonitoringContainerDetailView,
    AdminMonitoringContainerLogsView,
    AdminAnalyticsView,
    AdminSystemHealthView,
    AdminAuditLogView,
    AdminActivityFeedView,
    AdminExportUsersView,
    AdminExportLabsView,
    AdminExportProgressView,
    AdminMaintenanceModeView,
    AdminInactiveUsersView,
    AdminSubscriptionLogsView,
    AdminInvoicesView,
    AdminThreadModerationView,
    AdminJiraTicketsView,
    AdminJiraCreateView,
    AdminConfigView,
    AdminUploadView,
)

urlpatterns = [
    # Overview
    path("overview/", AdminOverviewView.as_view()),
    path("health/", AdminSystemHealthView.as_view()),
    path("analytics/", AdminAnalyticsView.as_view()),
    path("activity/", AdminActivityFeedView.as_view()),
    path("audit-logs/", AdminAuditLogView.as_view()),
    path("config/", AdminConfigView.as_view()),
    path("upload/", AdminUploadView.as_view()),

    # Maintenance Mode
    path("maintenance/", AdminMaintenanceModeView.as_view()),

    # Technologies CRUD
    path("technologies/", AdminTechnologiesView.as_view()),
    path("technologies/<int:pk>/", AdminTechnologyDetailView.as_view()),

    # Tags CRUD
    path("tags/", AdminTagsView.as_view()),
    path("tags/<int:pk>/", AdminTagDetailView.as_view()),

    # Scenarios CRUD
    path("scenarios/", AdminScenariosView.as_view()),
    path("scenarios/<int:pk>/", AdminScenarioDetailView.as_view()),

    # Hints CRUD
    path("scenarios/<int:scenario_id>/hints/", AdminHintsView.as_view()),
    path("hints/<int:pk>/", AdminHintDetailView.as_view()),

    # Users Management
    path("users/", AdminUsersView.as_view()),
    path("users/bulk/", AdminBulkUsersView.as_view()),
    path("users/<int:pk>/", AdminUserDetailView.as_view()),
    path("users/inactive/", AdminInactiveUsersView.as_view()),

    # Lab Management
    path("labs/active/", AdminActiveLabsView.as_view()),
    path("labs/bulk/", AdminBulkLabsView.as_view()),
    path("labs/<uuid:session_id>/terminate/", AdminTerminateLabView.as_view()),
    path("labs/terminate-idle/", AdminTerminateAllIdleLabsView.as_view()),

    # Monitoring
    path("monitoring/containers/", AdminMonitoringContainersView.as_view()),
    path("monitoring/containers/<str:container_id>/", AdminMonitoringContainerDetailView.as_view()),
    path("monitoring/containers/<str:container_id>/logs/", AdminMonitoringContainerLogsView.as_view()),

    # Subscription Logs
    path("subscriptions/", AdminSubscriptionLogsView.as_view()),
    path("invoices/", AdminInvoicesView.as_view()),

    # Thread Moderation
    path("threads/", AdminThreadModerationView.as_view()),
    path("threads/<uuid:thread_id>/", AdminThreadModerationView.as_view()),

    # Jira tickets
    path("jira/tickets/", AdminJiraTicketsView.as_view()),
    path("jira/tickets/create/", AdminJiraCreateView.as_view()),

    # Data Exports (CSV)
    path("export/users/", AdminExportUsersView.as_view()),
    path("export/labs/", AdminExportLabsView.as_view()),
    path("export/progress/", AdminExportProgressView.as_view()),
]
