# FixitLab Technology Emulator Roadmap — Enterprise Digital Twin

Internal tracking for production-grade, pixel-accurate technology consoles
that share one enterprise state (Digital Twin). User-facing UI must never show:
Simulation, Simulator, Demo, Mock, Sandbox, Practice Environment.

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done

---

## A. Platform foundations (cross-cutting)

1. [x] Strip all learner-visible "simulation/simulator/demo/mock/sandbox" copy platform-wide
2. [x] Entitlement gate: lab console buttons only for subscribed tech of that scenario
3. [ ] Scenario-scoped lab servers (no global shared server across techs)
4. [ ] Cross-tech sync bus: disk/NIC/CPU/RAM changes reflect in terminal + consoles
5. [ ] Lab Terminal always binds to the scenario's Lab Server OS
6. [ ] SSH from Lab Terminal into EC2/Azure VM/GCE/vSphere guest/OpenStack instance
7. [ ] Terraform provider apply → resources appear in AWS/Azure/GCP consoles
8. [ ] Private APIs: close public exposure; auth + network allowlists
9. [x] Soften lab chrome: per-scenario console links only (not AWS+VMware+DC always)
10. [x] Subscription revenue lock: cannot open unsubscribed tech via cross-link
11. [ ] 150+ scenarios per technology (learn/build/operate/troubleshoot/production mix)
12. [ ] Notebook-style tutorials for techs that do not need full labs yet
13. [ ] Jira bots as real teammates (PO/EM/SRE/security) with progressive hints
14. [ ] Enterprise project packaging per course (epics, CRs, incidents, acceptance)
15. [ ] CI/CD console parity with real pipeline platforms
16. [x] Shared GlobalSearch omnibox on Azure/GCP/SOC/DC chrome (AWS TopNav already has unified search)
17. [ ] Lab buttons restored on every technology detail page
18. [ ] Digital Twin persistence + replay for hardware/cable/firmware changes
19. [ ] Multi-user collaboration sessions on shared lab twin
20. [ ] Performance budget: 60 FPS 3D, <2s SIEM search, lazy chunks with retry

---

## B. Interview voice / lab reliability

21. [x] Fix Join TTS cancelled by host sync (mark bootstrap message IDs)
22. [x] Disable VAD barge-in during Join bootstrap; raise barge threshold
23. [x] Stop 1Hz React re-render from interview clock (DOM-only paint)
24. [x] Harden Chrome SpeechSynthesis unlock across async startRound
25. [ ] E2E: sound-test → Join → audible first question (no silent join)
26. [x] AWS console mount tests pass for fresh/legacy/corrupt localStorage
27. [~] Production verify: academy-aws-001 Ec2 Learn loads without error boundary
28. [x] Terraform / aws-* routing: slugHints no longer map bare aws-* to Terraform IDE
29. [~] Four-droplet deploy of interview + lab console fixes

---

## C. AWS Management Console emulator

30. [~] Pixel-accurate top nav, favorites, unified search, CloudShell
31. [x] EC2 Launch Wizard default instance type aligned to grader (`t3.micro`)
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

71. [~] Campus: parking, generator yard, chillers, substation, loading dock (live plant ops)
72. [~] Rooms: NOC, SOC, MDF, IDF, MMR, staging, burn-in, spares, battery (IDF + spares live)
73. [~] Raised floor, hot/cold aisle, CRAC/CRAH, DLC, CDU, UPS, busway
74. [~] 20+ racks with cage nuts, rails, PDUs, blanking, cable managers
75. [ ] Server manufacturers: Dell/HPE/Lenovo/Cisco/Supermicro/OCP/…
76. [ ] Motherboard: VRM/DIMM/PCIe/BMC/BIOS chips interactive
77. [x] Plug/unplug cables with physics bend (Rapier) — drag connector snap-mate
78. [~] Port LEDs, fan RPM animation, thermal/power view modes
79. [~] Console: attach KVM/monitor → BIOS/UEFI/iDRAC/iLO/IPMI/Redfish
80. [~] RAID config (PERC/Smart Array/MegaRAID) + rebuild viz
81. [~] Hardware replace workflows + RMA tickets (Dell/HPE/Cisco/NVIDIA)
82. [~] Failure injection + troubleshooting training scenarios (NOC drills + clear_fault)
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
119. [x] Visual contrast pass (Azure/GCP/storage light portals)
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

---

## N. Platform surfaces — root-cause backlog (2026-07-31 audit)

### Diagnosed (shipping / shipped in fix/lab-surfaces-hosting-streaming)

121. [~] Paced terminal output: `ping` / `traceroute` emit line-by-line (1s / ~0.45s), not dump-all
122. [~] Hosting persona: `vmware_link` / NIC-disk VMware labs force `hosted_as=vmware` (not baremetal hash)
123. [~] Hosting persona: PeopleSoft / JS / React / Java / HTML / shell / Ansible do **not** rotate to fake AWS/Azure DMI
124. [~] LabRunner: Open AWS for academy-aws + aws-hosted guests (subscription-gated)
125. [~] LabRunner: Open Azure / Open GCP when host_platform matches (was hardcoded `false`)
126. [~] LabRunner: Open AWX for Ansible tech labs (not only `awx|tower` slug)
127. [~] LabRunner: single Open VMware chip (dedupe "same server" + "VMware Server")
128. [~] LabRunner: coding IDE when `coding_mode` **or** coding tech + `coding_spec.files`
129. [~] Datacenter: local 3D twin ErrorBoundary falls back to 2D (stops whole-lab "Lab environment error")

### Still broken / next PRs

130. [~] Promote YAML `consoles` + `lab_servers` to first-class API fields; LabRunner prefers them, slug heuristics remain fallback
131. [x] Seed/`normalize_sim_type`: keep `peoplesoft`, `nmap`, `wireshark`, `windows-server`, coding types (stop collapse → `generic`)
132. [x] Academy generator: JS/React/HTML → `coding_mode: true` + real `coding_spec` (Java/shell deferred)
133. [x] HTML/Web labs: live iframe preview pane in CodingIDE + academy HTML → coding_mode
134. [ ] Terraform apply → mutate AWS/Azure/GCP console inventory + Open Cloud links in dropdown
135. [ ] AWS/Datacenter "Lab environment error": prod Cache-Control on `index.html`; Terraform AWS overlay same Zustand reset as primary
136. [ ] Surface `useSimSession.error` in Datacenter/AWS shells (403/API fail ≠ silent empty)
137. [ ] Jira @team mentions: verify `JIRA_SIMULATION_MODE` in prod; coach reply when mention parse fails; E2E mention → bot → disk appears
138. [ ] Theme/contrast pass: Windows + light portals — no white-on-white; brand-accurate colors per tech
139. [~] Lint: `vmware_link` ⇒ `hosted_as=vmware`; coding techs must set `coding_mode`; forbid unknown sim types after normalize

---

## O. AI Infra Engineering (new technology) — 150 scenarios + reuse existing surfaces

New tech slug: `ai-infra` (MAAS · VyOS · LXD · AWX · GPU DC · DCGM · Packer images).
**Does not invent parallel UIs** — scenarios set `simulation_type` + `consoles` to open Bare Metal, Datacenter, AWX, or GPU terminal.

140. [x] Technology seed + catalog page + subscription product (`ai-infra`) — PR #127
141. [x] Lab surfaces: reuse MAAS/baremetal + DC twin + AWX + GPU terminal
142. [x] Scenario pack (150): academy 145 + heroes (DCOPS thermal, MAAS commission, ESC dcgm-exporter, AWX driver, SXM tray)
143. [x] NVIDIA: `nvidia-smi dmon` / `pmon` / `-l` paced streaming + expanded query/topo/nvlink/MIG/CC matrix
144. [x] AMD: `rocm-smi --show*` + streamed `amd-smi monitor` + event/topology/firmware depth
145. [ ] Ops runbooks: scp diag scripts MAAS↔node, PSBCheck, fieldiag, dcgmprofrunner, gpu-admin-tools PPCIe/CC
146. [x] DCOps tickets: thermal / tray / commission heroes from wiki+Jira patterns
147. [~] Image factory: Packer + Terraform + Python + shell + upstream base + vuln fix (no manual) — *Packer CVE gate + MAAS publish in lab terminal*
148. [ ] Pixel parity: NVIDIA green / AMD red telemetry consoles; MAAS commission timeline
149. [ ] Cross-link: Datacenter twin GPU trays ↔ ai-infra scenarios
150. [x] Baremetal/imgdev wiki import → outlines (PSINFRA, ESC, DCOPS, GM1 escalation)
151. [ ] NCCL/RCCL stress + DCGM exporter scrape in monitoring companion
152. [ ] Dell/HPE engineer badge + access control for rack entry (DC twin)
153. [ ] Soundscape + LED blink realism (Steam-like immersion target for DC)
154. [x] 150 learn/build/operate/troubleshoot/production scenarios authored + ticket-format lint
155. [ ] CI lint: ai-infra scenarios never host as wrong cloud without `hosted_as`
156. [x] Docs: learner path AI Infra Engineer career track (catalog entry)
157. [ ] GPU MIG / vGPU partitions in twin + terminal
158. [ ] Multi-node NVLink fabric view in DC + `nvidia-smi nvlink`
159. [ ] End-to-end commission → burn-in → production handoff project
186. [~] Full NVIDIA 75-command matrix (query/dmon/pmon/topo/lock clocks/ECC/accounting) — *core matrix + `/proc/driver/nvidia` sysfs; keep extending*
187. [~] Full AMD 75-command matrix (rocm-smi + amd-smi + sysfs/debugfs) — *core matrix + drm/pp_dpm_* / amdgpu_pm_info seeded*
188. [x] GPU SKU matrix: H100 / H200 / B300 / A100 / L40S / MI300X with correct PCIe/SXM topology
189. [~] VyOS CLI: interfaces/DHCP/PXE helper (UI + BGP depth still open)
190. [~] MAAS E2E: machines read → commission → deploy → release (PXE menu depth open)
191. [~] LXD list/start/stop + gpu-passthrough profile (nested burn-in depth open)
192. [x] AWX job templates for driver install, DCGM exporter, image repave (inventory from MAAS)
193. [ ] DCOps RMA deep flow: FRU → parts availability → dock → install → burn-in → close
194. [x] Packer build stream + CVE gate artifact (full GH Actions factory still open)
195. [ ] `dcgm-exporter` + Prometheus/Grafana companion scrape in ai-infra observability labs
196. [ ] Integrated stack demo: MAAS node + VyOS underlay + LXD + AWX + DC twin + GPU CLI as one project

---

## P. Per-technology depth — 20 items each (pixel + E2E realism)

Track as waves; mark `[~]`/`[x]` when a 20-pack lands. Each tech needs: brand colors, all primary pages/buttons, CLI↔GUI sync, companion links, 20 graded scenarios.

160. [ ] AWS ×20 (VPC/IAM/RDS/Lambda/EKS/… full console + CLI sync)
161. [ ] Azure ×20 (Fluent blades + `az` Cloud Shell)
162. [ ] GCP ×20 (Material console + `gcloud`)
163. [ ] VMware ×20 (hardware edit → guest `ip`/`lsblk`)
164. [ ] Datacenter ×20 (Steam-grade twin: entry, parts, cables, sound, 3D/8D)
165. [ ] Kubernetes/OpenShift ×20
166. [ ] Docker ×20
167. [ ] Ansible/AWX ×20
168. [ ] Terraform ×20 (+ multi-cloud apply bridge)
169. [ ] GitOps (Argo/Flux/GitHub) ×20 + real IDE/terminal/PR approvals
170. [ ] DevOps/CI ×20 + deploy preview
171. [ ] Monitoring (Grafana/Prom) ×20
172. [ ] SOC/Cyber ×20
173. [ ] Commvault / NetApp / DellEMC ×20 each
174. [ ] Windows Server ×20 (contrast fix first)
175. [ ] PeopleSoft ×20 (app server host, not fake EC2)
176. [ ] Coding (JS/Java/HTML/React/Shell) ×20 IDE+preview
177. [ ] AI/ML/LLM Agents ×20 (custom LLM + agents that actually run)
178. [ ] OpenStack / Baremetal / Networking ×20 each
179. [ ] Collaboration: Jira bots + Teams mentions reliable E2E

---

## Q. Immersion / DC Steam-class target

180. [ ] First-person / avatar entry with badge (Dell/HPE engineer roles)
181. [ ] Ambient DC audio (CRAC, PDU hum) + alert tones
182. [ ] Part warehouse inventory ↔ RMA ↔ dock receive (already started) → full chain
183. [ ] Cable bend physics + port LED + blink patterns (partial) → all media types
184. [ ] Thermal volume rendering / aisle smoke for incidents
185. [ ] Competitor study notes from PC building / DC games → backlog grooming

---

## R. Interview Bot — "Feels Like a Real Call" (P2 realism, 100% free)

Rule-based only (`interview_ai.py` + `services/conversation/` + new `services/realism/`). No paid LLM/STT/TTS.

197. [x] **P2.R1** Response-timing model (`realism/timing.py`) — think-time + jitter + "persona is typing"
198. [x] **P2.R2** Backchannel layer (`realism/backchannel.py`) — live mm-hmm/okay off interim STT
199. [ ] **P2.R3** Lab narration — real-time reactions to streamed commands (needs P2.4)
200. [x] **P2.R4** Wrong-answer probing state machine (narrow → hint → graceful move-on)
201. [x] **P2.R5** Callback memory → phrasing (in-round + cross-round from prior report)
202. [~] **P2.R6** Small-talk framing beats (beats stored on round start; two-way UI still open)
203. [x] **P2.R7** Phrasing variety / disfluency guard
204. [ ] **P2.1** Fix browser voice loop + in-room voice switcher
205. [ ] **P2.2** Barge-in + skip-on-silence
206. [ ] **P2.3** Human follow-ups (quote-the-candidate, de-dupe)
207. [ ] **P2.4** Inline practical validation + checker stream
208. [ ] **P2.5** Resume score + tips
209. [ ] **P2.6–P2.R8** Vosk STT + WS streaming + server-side backchannel (later)

Suggested order: P2.1 → P2.3 → P2.R1 → P2.R6 → P2.R2 → P2.2 → P2.R4 → P2.R7 → P2.R5 → P2.4 → P2.R3 → …

---

## S. Enterprise Infrastructure Digital Twin (north-star architecture)

Vision: one living organization — identity, DC, cloud, network, virt, automation,
monitoring, security, storage, AI infra, and software share **one backend state**.
Learner-facing UI never says simulation/demo/mock.

### S1 — Unified enterprise state bus
210. [~] Single asset/resource registry (hostname, serial, asset tag, rack/U, CPU/RAM/disk/RAID, firmware, BIOS, BMC, NICs, VLANs, GPUs, power/thermal, OS, deploy status, owner) — *schema + list_assets on server_identity*
211. [~] Write-once identity: MAAS commission → appears in CMDB, DC twin, monitoring, Terraform import targets, AWX inventory — *MAAS terminal/baremetal → identity → AWX maas-gpu-nodes; Terraform/monitoring still open*
212. [ ] Terraform apply → create/update/delete mirrors into AWS/Azure/GCP/VMware/MAAS/LXD consoles
213. [ ] Hardware failure events fan out to Grafana alerts, SOC tickets, DCIM LEDs, and lab terminal `dmesg`
214. [ ] Cross-console sync: disk/NIC/CPU/RAM edits in VMware/DC update guest `lsblk`/`ip`/`nvidia-smi`
215. [ ] Persistent twin replay (undo/timeline) for cable/firmware/part swaps

### S2 — Org login & living enterprise chrome
216. [ ] Enterprise login → org home (not isolated “pick a lab” only)
217. [ ] Shared nav: tickets, CMDB, monitoring, clouds, DC floor, Git, AWX
218. [ ] RBAC personas (DC tech Dell/HPE badge, cloud eng, SRE, SOC analyst, interviewer)

### S3 — Datacenter Steam-class immersion
219. [ ] Reception → security → staging → repair bay → warehouse → dock → halls (walkable)
220. [ ] Per-rack realism: servers, GPUs, ToR, storage, PDUs, UPS, CRAC, fiber/copper, LEDs, fan audio
221. [ ] Full FRU RMA: locate → diagnose → order part → dock receive → swap → burn-in → close
222. [ ] Ambient audio + blink patterns + thermal aisle effects (extend Q 180–185)

### S4 — MAAS / PXE / VyOS / LXD / AWX integration spine
223. [~] MAAS machines read/commission/deploy/release with **paced PXE stream** (DHCP→TFTP→scripts)
224. [ ] MAAS UI pixel surface (or deepen BaremetalSimulator MAAS panes): region/rack, images, scripts
225. [ ] Full PXE animation in DC twin (boot menu + Curtin + cloud-init)
226. [~] VyOS CLI interfaces/DHCP/PXE helper; add commit/rollback + BGP/firewall UI
227. [~] LXD list/start/stop + GPU passthrough; add clustering/projects/migration
228. [x] AWX job templates (driver/DCGM/repave) streamed; inventory sync from MAAS
229. [~] Packer+GH Actions image factory publishes to MAAS boot-resources *(CLI CVE gate + publish done; GH Actions factory open)*

### S5 — Cloud / Terraform / GitOps / Dev / Security depth
230. [ ] AWS/Azure/GCP full page matrices (extend C/D/E + P 160–162)
231. [ ] Terraform multi-provider bridge + console dropdown links after apply
232. [ ] GitOps: Git IDE + PR + Flux/Argo sync health end-to-end
233. [ ] Coding IDEs for all language techs + HTML preview (finish 176)
234. [ ] PeopleSoft app-server host persona (not generic EC2) (finish 175)
235. [ ] SOC/SIEM events tied to twin assets (finish 172)
236. [~] Environment resolver CI: every scenario opens correct primary console + companions

### S6 — Interview realism (see §R)
237. [~] Ship P2.R1–R7 before paid STT; keep 100% free constraint — *R1–R5/R7 + R4 done; R6 UI two-way + P2.1–P2.4 still open*

---

## Execution order (updated)

1. **Ship** lab-surfaces PR (121–129) — hosting, links, ping stream, DC 3D fallback
2. Consoles schema + academy coding_mode reseed (130–133)
3. Terraform↔cloud bridge + AWS/DC load hardening (134–136)
4. Jira mentions + contrast (137–138)
5. **Merged PR #127–#129** AI Infra Engineering + AWX/Packer + GPU command matrix
6. AI Infra depth (remaining): VyOS UI, MAAS UI, Packer GH Actions, DCOps RMA (186–196, 223–229)
7. Interview realism P2 leftovers (P2.1–P2.4, P2.R3, P2.R6 UI) in parallel with coding IDE leftovers
8. **Unified state bus foundation (210–215)** — *MAAS→identity→AWX slice shipping; Terraform/Grafana fan-out next*
9. Per-tech 20-packs in priority waves (AWS/DC/GitOps/AI-ML first)
10. Steam-class DC immersion (180–185, 219–222)
