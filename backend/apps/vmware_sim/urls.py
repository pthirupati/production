from django.urls import path

from .views import (
    ActiveFaultsView,
    AzureSimActionView,
    AzureSimReleaseView,
    AzureSimStateView,
    GcpSimActionView,
    GcpSimReleaseView,
    GcpSimStateView,
    OpenStackSimActionView,
    OpenStackSimReleaseView,
    OpenStackSimStateView,
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
    WindowsSimActionView,
    WindowsSimReleaseView,
    WindowsSimStateView,
    PeoplesoftSimActionView,
    PeoplesoftSimReleaseView,
    PeoplesoftSimStateView,
    AwxSimActionView,
    AwxSimReleaseView,
    AwxSimStateView,
    TerraformSimActionView,
    TerraformSimReleaseView,
    TerraformSimStateView,
    BaremetalSimActionView,
    BaremetalSimReleaseView,
    BaremetalSimStateView,
    AwsSimActionView,
    AwsSimReleaseView,
    AwsSimStateView,
    CommvaultSimActionView,
    CommvaultSimReleaseView,
    CommvaultSimStateView,
    NetappSimActionView,
    NetappSimReleaseView,
    NetappSimStateView,
    DellemcSimActionView,
    DellemcSimReleaseView,
    DellemcSimStateView,
    DatacenterSimActionView,
    DatacenterSimReleaseView,
    DatacenterSimStateView,
    SocSimActionView,
    SocSimReleaseView,
    SocSimStateView,
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

    # Windows Server simulation (Server Manager / AD / Windows Update GUI)
    path("windows/sessions/<uuid:session_id>/", WindowsSimStateView.as_view(), name="windows-sim-state"),
    path("windows/sessions/<uuid:session_id>/action/", WindowsSimActionView.as_view(), name="windows-sim-action"),
    path("windows/sessions/<uuid:session_id>/release/", WindowsSimReleaseView.as_view(), name="windows-sim-release"),
    path("peoplesoft/sessions/<uuid:session_id>/", PeoplesoftSimStateView.as_view(), name="peoplesoft-sim-state"),
    path("peoplesoft/sessions/<uuid:session_id>/action/", PeoplesoftSimActionView.as_view(), name="peoplesoft-sim-action"),
    path("peoplesoft/sessions/<uuid:session_id>/release/", PeoplesoftSimReleaseView.as_view(), name="peoplesoft-sim-release"),
    path("awx/sessions/<uuid:session_id>/", AwxSimStateView.as_view(), name="awx-sim-state"),
    path("awx/sessions/<uuid:session_id>/action/", AwxSimActionView.as_view(), name="awx-sim-action"),
    path("awx/sessions/<uuid:session_id>/release/", AwxSimReleaseView.as_view(), name="awx-sim-release"),
    path("cicd/sessions/<uuid:session_id>/", CicdSimStateView.as_view(), name="cicd-sim-state"),
    path("cicd/sessions/<uuid:session_id>/action/", CicdSimActionView.as_view(), name="cicd-sim-action"),
    path("cicd/sessions/<uuid:session_id>/release/", CicdSimReleaseView.as_view(), name="cicd-sim-release"),
    path("terraform/sessions/<uuid:session_id>/", TerraformSimStateView.as_view(), name="terraform-sim-state"),
    path("terraform/sessions/<uuid:session_id>/action/", TerraformSimActionView.as_view(), name="terraform-sim-action"),
    path("terraform/sessions/<uuid:session_id>/release/", TerraformSimReleaseView.as_view(), name="terraform-sim-release"),
    path("baremetal/sessions/<uuid:session_id>/", BaremetalSimStateView.as_view(), name="baremetal-sim-state"),
    path("baremetal/sessions/<uuid:session_id>/action/", BaremetalSimActionView.as_view(), name="baremetal-sim-action"),
    path("baremetal/sessions/<uuid:session_id>/release/", BaremetalSimReleaseView.as_view(), name="baremetal-sim-release"),

    # AWS console simulation
    path("aws/sessions/<uuid:session_id>/", AwsSimStateView.as_view(), name="aws-sim-state"),
    path("aws/sessions/<uuid:session_id>/action/", AwsSimActionView.as_view(), name="aws-sim-action"),
    path("aws/sessions/<uuid:session_id>/release/", AwsSimReleaseView.as_view(), name="aws-sim-release"),

    # Commvault CommCell simulation
    path("commvault/sessions/<uuid:session_id>/", CommvaultSimStateView.as_view(), name="commvault-sim-state"),
    path("commvault/sessions/<uuid:session_id>/action/", CommvaultSimActionView.as_view(), name="commvault-sim-action"),
    path("commvault/sessions/<uuid:session_id>/release/", CommvaultSimReleaseView.as_view(), name="commvault-sim-release"),

    # NetApp ONTAP System Manager simulation
    path("netapp/sessions/<uuid:session_id>/", NetappSimStateView.as_view(), name="netapp-sim-state"),
    path("netapp/sessions/<uuid:session_id>/action/", NetappSimActionView.as_view(), name="netapp-sim-action"),
    path("netapp/sessions/<uuid:session_id>/release/", NetappSimReleaseView.as_view(), name="netapp-sim-release"),

    # Dell EMC Unisphere / PowerMax simulation
    path("dellemc/sessions/<uuid:session_id>/", DellemcSimStateView.as_view(), name="dellemc-sim-state"),
    path("dellemc/sessions/<uuid:session_id>/action/", DellemcSimActionView.as_view(), name="dellemc-sim-action"),
    path("dellemc/sessions/<uuid:session_id>/release/", DellemcSimReleaseView.as_view(), name="dellemc-sim-release"),

    # Cross-console fault ledger (Phase 3.2/3.4) — any console for a session
    # can list what's currently broken, regardless of which engine caused it.
    path("sessions/<uuid:session_id>/faults/", ActiveFaultsView.as_view(), name="active-faults"),

    # Microsoft Azure Portal simulation
    path("azure/sessions/<uuid:session_id>/", AzureSimStateView.as_view(), name="azure-sim-state"),
    path("azure/sessions/<uuid:session_id>/action/", AzureSimActionView.as_view(), name="azure-sim-action"),
    path("azure/sessions/<uuid:session_id>/release/", AzureSimReleaseView.as_view(), name="azure-sim-release"),

    # Google Cloud Console simulation
    path("gcp/sessions/<uuid:session_id>/", GcpSimStateView.as_view(), name="gcp-sim-state"),
    path("gcp/sessions/<uuid:session_id>/action/", GcpSimActionView.as_view(), name="gcp-sim-action"),
    path("gcp/sessions/<uuid:session_id>/release/", GcpSimReleaseView.as_view(), name="gcp-sim-release"),

    # OpenStack Horizon
    path("openstack/sessions/<uuid:session_id>/", OpenStackSimStateView.as_view(), name="openstack-sim-state"),
    path("openstack/sessions/<uuid:session_id>/action/", OpenStackSimActionView.as_view(), name="openstack-sim-action"),
    path("openstack/sessions/<uuid:session_id>/release/", OpenStackSimReleaseView.as_view(), name="openstack-sim-release"),

    # Physical datacenter (DCIM) simulation
    path("datacenter/sessions/<uuid:session_id>/", DatacenterSimStateView.as_view(), name="datacenter-sim-state"),
    path("datacenter/sessions/<uuid:session_id>/action/", DatacenterSimActionView.as_view(), name="datacenter-sim-action"),
    path("datacenter/sessions/<uuid:session_id>/release/", DatacenterSimReleaseView.as_view(), name="datacenter-sim-release"),

    # SOC / SIEM (cybersecurity) simulation
    path("soc/sessions/<uuid:session_id>/", SocSimStateView.as_view(), name="soc-sim-state"),
    path("soc/sessions/<uuid:session_id>/action/", SocSimActionView.as_view(), name="soc-sim-action"),
    path("soc/sessions/<uuid:session_id>/release/", SocSimReleaseView.as_view(), name="soc-sim-release"),
]
