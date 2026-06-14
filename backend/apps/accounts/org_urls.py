from django.urls import path

from .org_views import MyOrganizationsView, OrganizationDetailView

urlpatterns = [
    path("", MyOrganizationsView.as_view(), name="my_organizations"),
    path("<slug:slug>/", OrganizationDetailView.as_view(), name="organization_detail"),
]
