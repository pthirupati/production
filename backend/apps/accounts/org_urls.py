from django.urls import path

from .org_views import (
    CreateOrganizationView,
    MyOrganizationsView,
    OrganizationAnalyticsView,
    OrganizationDetailView,
    OrganizationInviteCancelView,
    OrganizationMemberDetailView,
    OrganizationMemberRemoveView,
    OrganizationRazorpayVerifyView,
    OrganizationSettingsView,
)

urlpatterns = [
    path("", MyOrganizationsView.as_view(), name="my_organizations"),
    # NOTE: keep "create/" above the "<slug:slug>/" catch-all so it is not
    # swallowed as an org slug.
    path("create/", CreateOrganizationView.as_view(), name="organization_create"),
    path("<slug:slug>/", OrganizationDetailView.as_view(), name="organization_detail"),
    path("<slug:slug>/analytics/", OrganizationAnalyticsView.as_view(), name="organization_analytics"),
    path("<slug:slug>/members/<int:user_id>/", OrganizationMemberDetailView.as_view(), name="organization_member_detail"),
    path("<slug:slug>/members/<int:user_id>/remove/", OrganizationMemberRemoveView.as_view(), name="organization_member_remove"),
    path("<slug:slug>/invites/<uuid:invite_id>/", OrganizationInviteCancelView.as_view(), name="organization_invite_cancel"),
    path("<slug:slug>/verify-payment/", OrganizationRazorpayVerifyView.as_view(), name="organization_verify_payment"),
    path("<slug:slug>/settings/", OrganizationSettingsView.as_view(), name="organization_settings"),
]
