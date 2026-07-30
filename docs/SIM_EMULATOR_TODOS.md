# FixitLab Technology Emulator Roadmap — 120+ Todos

Internal tracking for production-grade, pixel-accurate technology consoles.
User-facing UI must never show: Simulation, Simulator, Demo, Mock, Sandbox, Practice Environment.

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done

---

## A. Platform foundations (cross-cutting)

1. [ ] Strip all learner-visible "simulation/simulator/demo/mock/sandbox" copy platform-wide
2. [ ] Entitlement gate: lab console buttons only for subscribed tech of that scenario
3. [ ] Scenario-scoped lab servers (no global shared server across techs)
4. [ ] Cross-tech sync bus: disk/NIC/CPU/RAM changes reflect in terminal + consoles
5. [ ] Lab Terminal always binds to the scenario's Lab Server OS
6. [ ] SSH from Lab Terminal into EC2/Azure VM/GCE/vSphere guest/OpenStack instance
7. [ ] Terraform provider apply → resources appear in AWS/Azure/GCP consoles
8. [ ] Private APIs: close public exposure; auth + network allowlists
9. [ ] Soften lab chrome: per-scenario console links only (not AWS+VMware+DC always)
10. [ ] Subscription revenue lock: cannot open unsubscribed tech via cross-link
11. [ ] 150+ scenarios per technology (learn/build/operate/troubleshoot/production mix)
12. [ ] Notebook-style tutorials for techs that do not need full labs yet
13. [ ] Jira bots as real teammates (PO/EM/SRE/security) with progressive hints
14. [ ] Enterprise project packaging per course (epics, CRs, incidents, acceptance)
15. [ ] CI/CD console parity with real pipeline platforms
16. [ ] Search bars on every console table/list (missing searches restored)
17. [ ] Lab buttons restored on every technology detail page
18. [ ] Digital Twin persistence + replay for hardware/cable/firmware changes
19. [ ] Multi-user collaboration sessions on shared lab twin
20. [ ] Performance budget: 60 FPS 3D, <2s SIEM search, lazy chunks with retry

---

## B. Interview voice / lab reliability

21. [x] Fix Join TTS cancelled by host sync (mark bootstrap message IDs)
22. [x] Disable VAD barge-in during Join bootstrap; raise barge threshold
23. [x] Stop 1Hz React re-render from interview clock (DOM-only paint)
24. [ ] Harden Chrome SpeechSynthesis unlock across async startRound
25. [ ] E2E: sound-test → Join → audible first question (no silent join)
26. [x] AWS console mount tests pass for fresh/legacy/corrupt localStorage
27. [ ] Production verify: academy-aws-001 Ec2 Learn loads without error boundary
28. [ ] Terraform labs load after chunk-retry + store reset paths
29. [ ] Four-droplet deploy of interview + lab console fixes

---

## C. AWS Management Console emulator

30. [ ] Pixel-accurate top nav, favorites, unified search, CloudShell
31. [ ] EC2: full launch wizard, all families, connect (SSH/RDP/serial)
32. [ ] EC2: start/stop/reboot/terminate sync to Lab Terminal reachability
33. [ ] VPC: subnets, route tables, IGW, NAT, NACLs, peering, TGW
34. [ ] S3: buckets, objects, versioning, lifecycle, encryption, static site
35. [ ] IAM: users/groups/roles/policies, STS assume-role
36. [ ] RDS / DynamoDB / ElastiCache / Redshift creates + detail
37. [ ] Lambda / API Gateway / EventBridge / Step Functions / SQS / SNS
38. [ ] EKS / ECS / ECR / CloudWatch / CloudTrail / Config / GuardDuty / WAF
39. [ ] Route53 / ACM / CloudFront / ALB/NLB / ASG / Launch Templates
40. [ ] Billing / Cost Explorer / Budgets / Organizations
41. [ ] LocalStack bridge OR keep pure client store — pick one and wire CLI+GUI
42. [ ] `aws` CLI in Lab Terminal mutates same store as console
43. [ ] Terraform AWS provider resources mirror into console inventory

---

## D. Microsoft Azure Portal emulator

44. [ ] Fluent UI v9 tokens, top bar, sidebar, subscription picker
45. [ ] VM create wizard (8 tabs) + all detail blades
46. [ ] VMSS, AKS, Container Apps, App Service, Functions
47. [ ] VNet, LB, App Gateway, Firewall, VPN, ExpressRoute, Front Door, vWAN
48. [ ] Storage Accounts, Backup, Site Recovery
49. [ ] SQL / Cosmos / Redis / PostgreSQL Flexible
50. [ ] Service Bus, Event Hubs, Event Grid, Logic Apps, APIM
51. [ ] Entra ID (users/apps/CA/PIM), Key Vault, Defender, Sentinel
52. [ ] Monitor, Policy, Cost Management, Automation, Arc
53. [ ] Cloud Shell (`az`) against local mock API
54. [ ] Lab Terminal SSH to Azure VM; disk/NIC sync

---

## E. Google Cloud Console emulator

55. [ ] Material 3 tokens, project picker, product search
56. [ ] Compute Engine all machine families + MIG/templates
57. [ ] GKE Standard + Autopilot full cluster detail
58. [ ] Cloud Storage, Cloud SQL, Spanner, Bigtable, Firestore, Memorystore
59. [ ] BigQuery editor + IAM + VPC + all LB types + Armor + CDN + DNS
60. [ ] Cloud Run / Functions / App Engine / Pub/Sub
61. [ ] Monitoring / Logging / Trace / Profiler
62. [ ] Cloud Build / Artifact Registry / Cloud Deploy
63. [ ] Security Command Center, KMS, Vertex AI, Dataflow, Composer, Dataproc
64. [ ] Cloud Shell (`gcloud`/`bq`/`gsutil`) mock
65. [ ] Lab Terminal SSH to GCE; Terraform GCP provider sync

---

## F. VMware vSphere Client emulator

66. [ ] Hosts/clusters/VMs/datastores/networks pixel UI
67. [ ] VM hardware edit → Lab Terminal `lscpu`/`lsblk`/`ip link` update
68. [ ] Snapshots, vMotion, templates, content library
69. [ ] vSAN health, NSX-lite views
70. [ ] Cross-link to Commvault discovery

---

## G. 3D Datacenter Digital Twin

71. [ ] Campus: parking, generator yard, chillers, substation, loading dock
72. [ ] Rooms: NOC, SOC, MDF, IDF, MMR, staging, burn-in, spares, battery
73. [ ] Raised floor, hot/cold aisle, CRAC/CRAH, DLC, CDU, UPS, busway
74. [ ] 20+ racks with cage nuts, rails, PDUs, blanking, cable managers
75. [ ] Server manufacturers: Dell/HPE/Lenovo/Cisco/Supermicro/OCP/…
76. [ ] Motherboard: VRM/DIMM/PCIe/BMC/BIOS chips interactive
77. [ ] Plug/unplug cables with physics bend (Rapier)
78. [ ] Port LEDs, fan RPM animation, thermal/power view modes
79. [ ] Console: attach KVM/monitor → BIOS/UEFI/iDRAC/iLO/IPMI/Redfish
80. [ ] RAID config (PERC/Smart Array/MegaRAID) + rebuild viz
81. [ ] Hardware replace workflows + RMA tickets (Dell/HPE/Cisco/NVIDIA)
82. [ ] Failure injection + troubleshooting training scenarios
83. [ ] DCIM: PUE, capacity, inventory, warranty, predictive maintenance
84. [ ] LOD/instancing/BVH for 60 FPS

---

## H. Storage & data protection

85. [ ] Commvault Command Center: all workloads + plans + ransomware
86. [ ] Commvault discovers VMware/cloud VMs automatically
87. [ ] NetApp ONTAP SM: FlexGroup, SnapLock, SVM-DR, NVMe-oF, ARP, MAV, S3
88. [ ] Dell PowerStore / PowerProtect DD / VxRail / iDRAC 9 complete
89. [ ] Storage attach to VMware/K8s/physical Lab Servers

---

## I. CyberOps / SOC platform

90. [ ] Dark SOC home: threat map, MITRE heatmap, live alert feed
91. [ ] SIEM SPL search over seeded events + 50 correlation rules
92. [ ] EDR endpoint detail tabs + threat hunting library
93. [ ] Panorama-style firewall policies + profiles + CLI
94. [ ] PAM sessions/recordings/UEBA/access requests
95. [ ] Vuln mgmt CVE detail + scans + exceptions
96. [ ] NDR, DNS security, PCAP, NetFlow
97. [ ] CSPM/CIEM multi-cloud + compliance frameworks
98. [ ] Playbooks SOAR step execution

---

## J. Kubernetes / OpenShift / Docker / GPU / MAAS

99. [ ] K8s console: workloads, services, ingress, storage, RBAC
100. [ ] OpenShift console parity + operators
101. [ ] Docker Desktop/engine console + compose
102. [ ] GPU K8s: DCGM, MIG, NCCL, operators, Slurm/Ray views
103. [ ] MAAS: machines, commissioning, LXD, KVM pods
104. [ ] Bare-metal PXE/IPMI/Redfish in lab + DC twin

---

## K. Automation / GitOps / Monitoring / Windows / PeopleSoft

105. [ ] Ansible AWX: inventories, templates, jobs, credentials
106. [ ] Terraform Cloud + workspace IDE + multi-cloud apply bridge
107. [ ] GitOps: Argo CD / Flux consoles
108. [ ] Grafana + Prometheus + Alertmanager + Loki pixel UI
109. [ ] Windows Server: ADUC, GPO, services, registry, Event Viewer
110. [ ] Oracle PeopleSoft PIA flows

---

## L. Scenario content quality

111. [ ] Rewrite scenarios with business context + RCA (no templates)
112. [ ] Add create/build/configure scenarios (not only break/fix)
113. [ ] LXD/KVM/GPU-K8s/MAAS commissioning scenario packs
114. [ ] Cybersecurity learning path scenarios end-to-end
115. [ ] Cross-tech graded labs with single source of truth host

---

## M. Security & ops polish

116. [ ] Audit private endpoints; JWT on all lab/sim APIs
117. [ ] Rate-limit Cloud Shell / CLI mock endpoints
118. [ ] No placeholder pages; dead-link crawl CI
119. [ ] Visual contrast pass (Azure/GCP/storage light portals)
120. [ ] Competitor parity review notes → backlog grooming

---

## Execution order (recommended)

1. Interview voice + AWS/Terraform lab load (prod verify) — **now**
2. User-facing wording purge + entitlement/console-link gating
3. Lab Server single source of truth + SSH + Terraform bridges
4. Datacenter twin depth (physics, BMC, RAID, RMA)
5. Azure/GCP/Cyber/Storage pixel depth waves
6. Scenario volume to 150+/tech + tutorials

Update this file as items complete. Keep internal code names (`*Simulator`, `simulation_type`) if needed — never expose them in UI.
