from django.urls import path

from .views import (
    AimlSimActionView,
    AimlSimReleaseView,
    AimlSimStateView,
    DatascienceSimActionView,
    DatascienceSimReleaseView,
    DatascienceSimStateView,
    DockerSimActionView,
    DockerSimReleaseView,
    DockerSimStateView,
    K8sSimActionView,
    K8sSimReleaseView,
    K8sSimStateView,
    MonitoringSimActionView,
    MonitoringSimDemoActionView,
    MonitoringSimDemoStateView,
    MonitoringSimReleaseView,
    MonitoringSimStateView,
    NmapSimActionView,
    NmapSimReleaseView,
    NmapSimStateView,
    WiresharkSimActionView,
    WiresharkSimReleaseView,
    WiresharkSimStateView,
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

    # Monitoring simulation (Grafana + Prometheus)
    path("monitoring/demo/", MonitoringSimDemoStateView.as_view(), name="monitoring-sim-demo-state"),
    path("monitoring/demo/action/", MonitoringSimDemoActionView.as_view(), name="monitoring-sim-demo-action"),
    path("monitoring/sessions/<uuid:session_id>/", MonitoringSimStateView.as_view(), name="monitoring-sim-state"),
    path("monitoring/sessions/<uuid:session_id>/action/", MonitoringSimActionView.as_view(), name="monitoring-sim-action"),
    path("monitoring/sessions/<uuid:session_id>/release/", MonitoringSimReleaseView.as_view(), name="monitoring-sim-release"),

    # Nmap simulation (network scanning)
    path("nmap/sessions/<uuid:session_id>/", NmapSimStateView.as_view(), name="nmap-sim-state"),
    path("nmap/sessions/<uuid:session_id>/action/", NmapSimActionView.as_view(), name="nmap-sim-action"),
    path("nmap/sessions/<uuid:session_id>/release/", NmapSimReleaseView.as_view(), name="nmap-sim-release"),

    # Wireshark simulation (packet capture / analysis)
    path("wireshark/sessions/<uuid:session_id>/", WiresharkSimStateView.as_view(), name="wireshark-sim-state"),
    path("wireshark/sessions/<uuid:session_id>/action/", WiresharkSimActionView.as_view(), name="wireshark-sim-action"),
    path("wireshark/sessions/<uuid:session_id>/release/", WiresharkSimReleaseView.as_view(), name="wireshark-sim-release"),

    # Data Science simulation (BI dashboard builder)
    path("datascience/sessions/<uuid:session_id>/", DatascienceSimStateView.as_view(), name="datascience-sim-state"),
    path("datascience/sessions/<uuid:session_id>/action/", DatascienceSimActionView.as_view(), name="datascience-sim-action"),
    path("datascience/sessions/<uuid:session_id>/release/", DatascienceSimReleaseView.as_view(), name="datascience-sim-release"),

    # AI / ML simulation (n8n-style agent / workflow builder)
    path("aiml/sessions/<uuid:session_id>/", AimlSimStateView.as_view(), name="aiml-sim-state"),
    path("aiml/sessions/<uuid:session_id>/action/", AimlSimActionView.as_view(), name="aiml-sim-action"),
    path("aiml/sessions/<uuid:session_id>/release/", AimlSimReleaseView.as_view(), name="aiml-sim-release"),
]
