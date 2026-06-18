from django.urls import path

from .views import VMwareSimActionView, VMwareSimReleaseView, VMwareSimStateView

urlpatterns = [
    path("sessions/<uuid:session_id>/", VMwareSimStateView.as_view(), name="vmware-sim-state"),
    path("sessions/<uuid:session_id>/action/", VMwareSimActionView.as_view(), name="vmware-sim-action"),
    path("sessions/<uuid:session_id>/release/", VMwareSimReleaseView.as_view(), name="vmware-sim-release"),
]
