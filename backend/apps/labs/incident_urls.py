"""URLs for the Live Incident Director + public postmortem artifact.

Mounted at /api/labs/ in config/urls.py. The postmortem endpoint is public
(AllowAny) and NOT under an admin-IP-gated prefix.
"""

from django.urls import path

from .incident_views import IncidentDirectorView, PublicPostmortemView

urlpatterns = [
    # Public, no-auth, read-only portfolio artifact (token-gated).
    path(
        "postmortem/<uuid:public_token>/",
        PublicPostmortemView.as_view(),
        name="public-postmortem",
    ),
    # Authenticated + flag-guarded Director entrypoint.
    path(
        "incidents/director/",
        IncidentDirectorView.as_view(),
        name="incident-director",
    ),
]
