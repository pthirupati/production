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
    AdminNodeMetricsView,
    AdminFleetMonitoringView,
    AdminAnalyticsView,
    AdminFunnelView,
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
    AdminItsmTicketsView,
    AdminItsmMetaView,
    AdminItsmTicketCreateView,
    AdminItsmTicketDetailView,
    AdminItsmTicketActionView,
    AdminConfigView,
    AdminUploadView,
    AdminCouponsView,
    AdminCouponDetailView,
    AdminOrganizationsView,
    AdminOrganizationDetailView,
    AdminSecurityMetricsView,
    AdminSecurityActionView,
    AdminTestEmailView,
    AdminPaymentGatewayTestView,
    AdminSyncScenariosView,
    AdminLabProvisioningView,
    AdminBlogPostsView,
    AdminBlogPostDetailView,
    AdminCampaignsView,
    AdminCampaignDetailView,
    AdminCampaignSocialView,
    AdminCertificatesView,
    AdminTechnologyMaintenanceView,
    AdminTechnologySubscribersView,
    AdminTechnologyEmailView,
    AdminTechnologyStatsView,
    AdminInterviewMaintenanceView,
    AdminEnvSecretsView,
)
from apps.billing.sales_views import (
    AdminSalesInquiriesView,
    AdminSalesInquiryDetailView,
)
from apps.interviews.admin_views import (
    AdminInterviewOverviewView,
    AdminInterviewCampaignsView,
    AdminInterviewQuestionsView,
    AdminInterviewQuestionDetailView,
    AdminInterviewAnswerCorpusView,
    AdminInterviewAnswerCorpusDetailView,
    AdminInterviewTiersView,
    AdminInterviewTierDetailView,
    AdminInterviewEntitlementsView,
    AdminInterviewSettingsView,
    AdminInterviewVoicesView,
    AdminInterviewVoiceDetailView,
    AdminInterviewTemplatesView,
    AdminInterviewTemplateDetailView,
    AdminInterviewInvitationsView,
    AdminInterviewComparisonView,
)
from apps.interviews.join_views import (
    AdminRequestJoinInterviewView,
    AdminJoinRequestsListView,
    AdminLiveInterviewSessionsView,
    AdminObserverSessionView,
)

urlpatterns = [
    # Overview
    path("overview/", AdminOverviewView.as_view()),
    path("health/", AdminSystemHealthView.as_view()),
    path("analytics/", AdminAnalyticsView.as_view()),
    path("funnel/", AdminFunnelView.as_view()),
    path("activity/", AdminActivityFeedView.as_view()),
    path("audit-logs/", AdminAuditLogView.as_view()),
    path("config/", AdminConfigView.as_view()),
    path("upload/", AdminUploadView.as_view()),
    path("coupons/", AdminCouponsView.as_view()),
    path("coupons/<int:pk>/", AdminCouponDetailView.as_view()),
    path("organizations/", AdminOrganizationsView.as_view()),
    path("organizations/<uuid:org_id>/", AdminOrganizationDetailView.as_view()),
    path("security/", AdminSecurityMetricsView.as_view()),
    path("security/actions/", AdminSecurityActionView.as_view()),
    path("email/test/", AdminTestEmailView.as_view()),
    path("payments/test-gateway/", AdminPaymentGatewayTestView.as_view()),

    # Maintenance Mode
    path("maintenance/", AdminMaintenanceModeView.as_view()),

    # Technologies CRUD + maintenance + subscriber management
    path("technologies/stats/", AdminTechnologyStatsView.as_view()),
    path("technologies/", AdminTechnologiesView.as_view()),
    path("technologies/<int:pk>/", AdminTechnologyDetailView.as_view()),
    path("technologies/<int:pk>/maintenance/", AdminTechnologyMaintenanceView.as_view()),
    path("technologies/<int:pk>/subscribers/", AdminTechnologySubscribersView.as_view()),
    path("technologies/<int:pk>/email/", AdminTechnologyEmailView.as_view()),

    # Tags CRUD
    path("tags/", AdminTagsView.as_view()),
    path("tags/<int:pk>/", AdminTagDetailView.as_view()),

    # Scenarios CRUD
    path("scenarios/", AdminScenariosView.as_view()),
    path("scenarios/sync/", AdminSyncScenariosView.as_view()),

    # Lab Provisioning — per-technology re-seed (checkbox UI + copy command)
    path("lab-provisioning/", AdminLabProvisioningView.as_view()),
    path("scenarios/<int:pk>/", AdminScenarioDetailView.as_view()),

    # Blog CMS
    path("blog/", AdminBlogPostsView.as_view()),
    path("blog/<uuid:post_id>/", AdminBlogPostDetailView.as_view()),

    # Campaigns / Ads / Announcements
    path("campaigns/", AdminCampaignsView.as_view()),
    path("campaigns/social/", AdminCampaignSocialView.as_view()),
    path("campaigns/<uuid:pk>/", AdminCampaignDetailView.as_view()),

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
    path("monitoring/metrics/", AdminNodeMetricsView.as_view()),
    path("monitoring/fleet/", AdminFleetMonitoringView.as_view()),
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

    # ITSM / ServiceNow tickets
    path("itsm/meta/", AdminItsmMetaView.as_view()),
    path("itsm/tickets/", AdminItsmTicketsView.as_view()),
    path("itsm/tickets/create/", AdminItsmTicketCreateView.as_view()),
    path("itsm/tickets/<uuid:ticket_id>/", AdminItsmTicketDetailView.as_view()),
    path("itsm/tickets/<uuid:ticket_id>/action/", AdminItsmTicketActionView.as_view()),

    # Data Exports (CSV)
    path("export/users/", AdminExportUsersView.as_view()),
    path("export/labs/", AdminExportLabsView.as_view()),
    path("export/progress/", AdminExportProgressView.as_view()),

    # AI Interview Studio
    path("interviews/overview/", AdminInterviewOverviewView.as_view()),
    path("interviews/settings/", AdminInterviewSettingsView.as_view()),
    path("interviews/campaigns/", AdminInterviewCampaignsView.as_view()),
    path("interviews/live/", AdminLiveInterviewSessionsView.as_view()),
    path("interviews/join-request/", AdminRequestJoinInterviewView.as_view()),
    path("interviews/join-requests/", AdminJoinRequestsListView.as_view()),
    path("interviews/observer/<uuid:token>/", AdminObserverSessionView.as_view()),
    path("interviews/questions/", AdminInterviewQuestionsView.as_view()),
    path("interviews/questions/<int:pk>/", AdminInterviewQuestionDetailView.as_view()),
    path("interviews/answer-corpora/", AdminInterviewAnswerCorpusView.as_view()),
    path("interviews/answer-corpora/<int:pk>/", AdminInterviewAnswerCorpusDetailView.as_view()),
    path("interviews/tiers/", AdminInterviewTiersView.as_view()),
    path("interviews/tiers/<int:pk>/", AdminInterviewTierDetailView.as_view()),
    path("interviews/voices/", AdminInterviewVoicesView.as_view()),
    path("interviews/voices/<int:pk>/", AdminInterviewVoiceDetailView.as_view()),
    path("interviews/entitlements/", AdminInterviewEntitlementsView.as_view()),
    path("interviews/templates/", AdminInterviewTemplatesView.as_view()),
    path("interviews/templates/<uuid:pk>/", AdminInterviewTemplateDetailView.as_view()),
    path("interviews/invitations/", AdminInterviewInvitationsView.as_view()),
    path("interviews/comparison/", AdminInterviewComparisonView.as_view()),
    path("interviews/maintenance/", AdminInterviewMaintenanceView.as_view()),
    path("certificates/", AdminCertificatesView.as_view()),

    # Teams/Org sales inquiries + custom quotes
    path("sales/", AdminSalesInquiriesView.as_view()),
    path("sales/<uuid:pk>/", AdminSalesInquiryDetailView.as_view()),

    path("env-secrets/", AdminEnvSecretsView.as_view()),
    path("env-secrets/sync/", AdminEnvSecretsView.as_view()),
]
