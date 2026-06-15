from django.urls import path

from .org_views import (
    MyOrganizationsView,
    OrganizationAnalyticsView,
    OrganizationDetailView,
    OrganizationInviteCancelView,
    OrganizationMemberDetailView,
    OrganizationMemberRemoveView,
    OrganizationRazorpayVerifyView,
)

urlpatterns = [
    path("", MyOrganizationsView.as_view(), name="my_organizations"),
    path("<slug:slug>/", OrganizationDetailView.as_view(), name="organization_detail"),
    path("<slug:slug>/analytics/", OrganizationAnalyticsView.as_view(), name="organization_analytics"),
    path("<slug:slug>/members/<int:user_id>/", OrganizationMemberDetailView.as_view(), name="organization_member_detail"),
    path("<slug:slug>/members/<int:user_id>/remove/", OrganizationMemberRemoveView.as_view(), name="organization_member_remove"),
    path("<slug:slug>/invites/<uuid:invite_id>/", OrganizationInviteCancelView.as_view(), name="organization_invite_cancel"),
    path("<slug:slug>/verify-payment/", OrganizationRazorpayVerifyView.as_view(), name="organization_verify_payment"),
]
