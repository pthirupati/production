"""ITSM API routes (mounted at /api/itsm/)."""

from django.urls import path

from .views import (
    ItsmFulfilView,
    ItsmMetaView,
    ItsmSubTicketView,
    ItsmTicketDetailView,
    ItsmTransferView,
    ItsmTransitionView,
    ScenarioItsmTicketView,
)

urlpatterns = [
    path("meta/", ItsmMetaView.as_view(), name="itsm-meta"),
    path("scenario/<int:scenario_id>/", ScenarioItsmTicketView.as_view(), name="itsm-scenario-ticket"),
    path("tickets/<uuid:ticket_id>/", ItsmTicketDetailView.as_view(), name="itsm-ticket-detail"),
    path("tickets/<uuid:ticket_id>/transition/", ItsmTransitionView.as_view(), name="itsm-ticket-transition"),
    path("tickets/<uuid:ticket_id>/transfer/", ItsmTransferView.as_view(), name="itsm-ticket-transfer"),
    path("tickets/<uuid:ticket_id>/sub-tickets/", ItsmSubTicketView.as_view(), name="itsm-sub-ticket"),
    path("tickets/<uuid:ticket_id>/fulfil/", ItsmFulfilView.as_view(), name="itsm-ticket-fulfil"),
]
