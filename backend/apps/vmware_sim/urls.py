from django.urls import path

from .views import (
    DockerSimActionView,
    DockerSimReleaseView,
    DockerSimStateView,
    K8sSimActionView,
    K8sSimReleaseView,
    K8sSimStateView,
    VMwareSimActionView,
    VMwareSimDemoActionView,
    VMwareSimDemoStateView,
    VMwareSimReleaseView,
    VMwareSimStateView,
)

urlpatterns = [
    # VMware simulation
    path("demo/", VMwareSimDemoStateView.as_view(), name="vmware-sim-demo-state"),
    path("demo/action/", VMwareSimDemoActionView.as_view(), name="vmware-sim-demo-action"),
    path("sessions/<uuid:session_id>/", VMwareSimStateView.as_view(), name="vmware-sim-state"),
    path("sessions/<uuid:session_id>/action/", VMwareSimActionView.as_view(), name="vmware-sim-action"),
    path("sessions/<uuid:session_id>/release/", VMwareSimReleaseView.as_view(), name="vmware-sim-release"),

    # Kubernetes simulation
    path("k8s/sessions/<uuid:session_id>/", K8sSimStateView.as_view(), name="k8s-sim-state"),
    path("k8s/sessions/<uuid:session_id>/action/", K8sSimActionView.as_view(), name="k8s-sim-action"),
    path("k8s/sessions/<uuid:session_id>/release/", K8sSimReleaseView.as_view(), name="k8s-sim-release"),

    # Docker simulation
    path("docker/sessions/<uuid:session_id>/", DockerSimStateView.as_view(), name="docker-sim-state"),
    path("docker/sessions/<uuid:session_id>/action/", DockerSimActionView.as_view(), name="docker-sim-action"),
    path("docker/sessions/<uuid:session_id>/release/", DockerSimReleaseView.as_view(), name="docker-sim-release"),
]
