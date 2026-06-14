from django.urls import path

from .org_views import (
    MyOrganizationsView,
    OrganizationDetailView,
    OrganizationAnalyticsView,
    OrganizationRazorpayVerifyView,
)

urlpatterns = [
    path("", MyOrganizationsView.as_view(), name="my_organizations"),
    path("<slug:slug>/", OrganizationDetailView.as_view(), name="organization_detail"),
    path("<slug:slug>/analytics/", OrganizationAnalyticsView.as_view(), name="organization_analytics"),
    path("<slug:slug>/verify-payment/", OrganizationRazorpayVerifyView.as_view(), name="organization_verify_payment"),
]
