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
25. [~] E2E: sound-test → Join → audible first question (no silent join) — *Test speakers gate + no cancel-before-speak*
481. [ ] Interview: optional Piper/sherpa-onnx local TTS blob playback (free, replaces flaky OS voices)
482. [ ] Interview: Vosk STT engine finish (INTERVIEW_STT_ENGINE=vosk currently NotImplemented)
483. [ ] Interview lab narration reacting to streamed practical commands (P2.R3)
484. [ ] Interview: reduce backchannel collisions with STT (mute cues first 2s of listen)
485. [x] AI Infra: seed H200/B300/MI300X commission heroes
486. [x] AI Infra: libguestfs guestfish/virt-customize handlers + inspect scenario
487. [~] AI Infra: more VyOS BGP/firewall/commit-rollback scenarios (4 more) — BGP + DHCP + firewall + commit-rollback seeded
488. [~] Datacenter Steam: forklift pallet + badge door before Walk — corridor forklift + mantrap door meshes
489. [x] Datacenter: auto-close ticket after burn-in pass (FRU loop finish)
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
134. [x] Terraform apply → mutate AWS/Azure/GCP console inventory + Open Cloud links in dropdown
135. [x] AWS/Datacenter "Lab environment error": prod Cache-Control on `index.html`; Terraform AWS overlay same Zustand reset as primary
136. [x] Surface `useSimSession.error` in Datacenter/AWS shells (403/API fail ≠ silent empty) — *DC done; Terraform/Azure/GCP Retry UI + companion AWS auto-reset*
137. [ ] Jira @team mentions: verify `JIRA_SIMULATION_MODE` in prod; coach reply when mention parse fails; E2E mention → bot → disk appears
138. [ ] Theme/contrast pass: Windows + light portals — no white-on-white; brand-accurate colors per tech
139. [x] Lint: `vmware_link` ⇒ `hosted_as=vmware`; coding techs must set `coding_mode`; forbid unknown sim types after normalize

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
212. [~] Terraform apply → create/update/delete mirrors into AWS/Azure/GCP/VMware/MAAS/LXD consoles — *AWS/Azure/GCP/VMware + MAAS enlist + LXD create/destroy; deeper maas_* types open*
213. [ ] Hardware failure events fan out to Grafana alerts, SOC tickets, DCIM LEDs, and lab terminal `dmesg`
214. [ ] Cross-console sync: disk/NIC/CPU/RAM edits in VMware/DC update guest `lsblk`/`ip`/`nvidia-smi`
215. [ ] Persistent twin replay (undo/timeline) for cable/firmware/part swaps

### S2 — Org login & living enterprise chrome
216. [ ] Enterprise login → org home (not isolated “pick a lab” only)
217. [ ] Shared nav: tickets, CMDB, monitoring, clouds, DC floor, Git, AWX
218. [ ] RBAC personas (DC tech Dell/HPE badge, cloud eng, SRE, SOC analyst, interviewer)

### S3 — Datacenter Steam-class immersion
219. [~] Reception → security → staging → repair bay → warehouse → dock → halls (walkable) — *room exits + reception/repair/warehouse stubs; full 3D corridor open*
220. [ ] Per-rack realism: servers, GPUs, ToR, storage, PDUs, UPS, CRAC, fiber/copper, LEDs, fan audio
221. [ ] Full FRU RMA: locate → diagnose → order part → dock receive → swap → burn-in → close
222. [ ] Ambient audio + blink patterns + thermal aisle effects (extend Q 180–185)

### S4 — MAAS / PXE / VyOS / LXD / AWX integration spine
223. [~] MAAS machines read/commission/deploy/release with **paced PXE stream** (DHCP→TFTP→scripts)
224. [ ] MAAS UI pixel surface (or deepen BaremetalSimulator MAAS panes): region/rack, images, scripts
225. [ ] Full PXE animation in DC twin (boot menu + Curtin + cloud-init)
226. [~] VyOS CLI interfaces/DHCP/PXE helper; add commit/rollback + BGP/firewall UI — *configure/set/commit/rollback + BGP summary done; pixel UI + firewall still open*
227. [~] LXD list/start/stop + GPU passthrough; add clustering/projects/migration
228. [x] AWX job templates (driver/DCGM/repave) streamed; inventory sync from MAAS
229. [~] Packer+GH Actions image factory publishes to MAAS boot-resources *(CLI CVE gate + publish done; GH Actions factory open)*

### S5 — Cloud / Terraform / GitOps / Dev / Security depth
230. [ ] AWS/Azure/GCP full page matrices (extend C/D/E + P 160–162)
231. [x] Terraform multi-provider bridge + console dropdown links after apply
232. [ ] GitOps: Git IDE + PR + Flux/Argo sync health end-to-end
233. [ ] Coding IDEs for all language techs + HTML preview (finish 176)
234. [ ] PeopleSoft app-server host persona (not generic EC2) (finish 175)
235. [ ] SOC/SIEM events tied to twin assets (finish 172)
236. [~] Environment resolver CI: every scenario opens correct primary console + companions

### S6 — Interview realism (see §R)
237. [~] Ship P2.R1–R7 before paid STT; keep 100% free constraint — *R1–R5/R7 + R4 done; R6 UI two-way + P2.1–P2.4 still open*

---

## T. Deep gap backlog (code-inspected Aug 2026 — ship without missing lines)

### T0 — Deploy / visibility (blocker for AI Infra in app)
238. [x] **Prod four-droplet deploy** so `seed_scenarios` creates `Technology(slug=ai-infra)` + 150 scenarios (last green prod was pre-#127)
239. [x] Frontend `techCatalog` entry + TechIcon alias for `ai-infra`
240. [x] Tutorial topic map `ai-infrastructure` → `ai-infra` (was incorrectly `gpu`)
241. [ ] Learning journey / career track row for AI Infra on `/technologies/ai-infra`
242. [x] Scenarios page chip shows AI Infra after seed (API-driven — verify post-deploy)

### T1 — Environment resolver & hosting (wrong console / wrong host)
243. [x] Backfill `hosted_as: vmware` on every `vmware_link` scenario YAML (not only nic-add-vmware-rescan)
244. [x] PeopleSoft: `hosted_as` + PeopleSoft persona (never AWS DMI rotate) on all PS scenarios
245. [x] Harden `scripts/lint_scenarios.py` to **fail CI** on wrong host / missing coding_mode / unknown sim_type — *academy coding packs + vmware_link/peoplesoft hosted_as*
246. [x] Ansible labs: always surface Open AWX companion when `simulation_type`/consoles include awx — *LabRunner + YAML backfill + lint*
247. [x] AWS labs: always surface Open AWS Console companion (not only terraform/hosted heuristics) — *terraform + aws_link + consoles:aws*
248. [x] Coding techs: academy java/shell/nodejs/python + HTML heroes → `coding_mode` + `coding_spec` *(java/shell heroes remain simulation marker labs; typescript still pending)*
249. [x] HTML heroes: CodingIDE + live preview iframe (academy done; heroes still terminal)
250. [ ] Cross-tech scenarios: assert each companion console link opens and shares session_id

### T2 — Terminal realism (paced I/O)
251. [~] Audit all instant multi-line commands (`ping`, `tail -f`, `journalctl -f`, `kubectl logs -f`, `dmesg -w`, `nvidia-smi -l`, `top`) — *ping/journalctl/tail/top/watch paced; kubectl logs -f still open*
252. [x] `subscription-manager` RHEL commands: status/register/list/repos + broken entitlement preset + Jira credential hint
253. [x] RHEL repos/subscription credentials surfaced in Jira ticket comments for labs that need them

### T3 — Terraform / cloud bridge remaining
254. [x] Terraform `vsphere_virtual_machine` → VMware `create_vm` + Open VMware link
255. [x] Terraform destroy → terminate/delete mirrored AWS/Azure/GCP/VMware resources
256. [x] Terraform → MAAS enlist / LXD create fan-out
257. [ ] Terraform import + state list/show parity with mirrored consoles
258. [ ] Provider resource coverage beyond instance/VM (S3, VPC, SG, Azure RG, GCP disk, vsphere network)

### T4 — VyOS / MAAS / LXD / AWX spine
259. [x] VyOS `configure` / `set` / `commit` / `rollback` + BGP summary
260. [ ] VyOS firewall / NAT / VPN / VRRP / QoS CLI depth
261. [ ] VyOS pixel UI (router appliance shell) linked from ai-infra + networking labs
262. [ ] MAAS UI region/rack/images/scripts panes (pixel)
263. [ ] Full PXE animation in DC twin (DHCP→TFTP→kernel→Curtin→cloud-init)
264. [ ] LXD clustering / projects / migration depth
265. [ ] Packer + GitHub Actions image factory → MAAS boot-resources (end-to-end, not CLI-only)
266. [ ] Integrated stack project: MAAS + VyOS underlay + LXD + AWX + DC + GPU CLI as one graded flow

### T5 — Datacenter Steam-class immersion
267. [x] Reception / security checkpoint / staging / repair bay / warehouse / dock walkable stubs
268. [ ] Per-rack LEDs, fan audio, fiber/copper trays, PDU/UPS/CRAC interactivity
269. [ ] Dell/HPE engineer badge + access control for rack entry
270. [ ] Full FRU RMA: locate → diagnose → order → dock → swap → burn-in → close
271. [ ] DC ↔ ai-infra GPU tray cross-link (same asset id)
272. [ ] 3D twin ErrorBoundary + progressive enhancement (keep 2D fallback)

### T6 — Per-technology depth packs (20 items each — track progress)
273. [ ] AWS 20-pack: IAM/Org/Control Tower/EC2/EBS/VPC/R53/ELB/CFN/Lambda/ECS/EKS/S3/RDS/CW/CT/SSM/Secrets/GuardDuty/Billing pages live
274. [ ] Azure 20-pack: Entra/VM/VNet/NSG/AKS/Storage/KeyVault/Monitor/LogAnalytics/Automation/ResourceGraph/Defender/Policy/Cost/AppGW/…
275. [ ] GCP 20-pack: Projects/IAM/GCE/GKE/GCS/VPC/SQL/Artifact/Build/Logging/Monitoring/…
276. [ ] Grafana/Prometheus 20-pack: datasources, folders, alerts, Explore, Loki, Tempo, DCGM scrape
277. [ ] DellEMC / NetApp / Commvault storage 20-pack each
278. [ ] Security/SOC/SIEM 20-pack: tickets tied to twin assets
279. [ ] GitOps 20-pack: Git IDE + PR + Flux/Argo sync health
280. [ ] DevOps/CI 20-pack: pipeline IDE + preview after deploy
281. [ ] AI/ML agents 20-pack: build agents that call twin tools
282. [ ] Windows contrast/theme pass (no white-on-white)
283. [ ] VMware page matrix remaining (HA/DRS/vSAN/NSX polish)

### T7 — Interview realism leftovers
284. [ ] P2.1 browser voice loop + in-room switcher
285. [ ] P2.R6 framing UI two-way open/close beats
286. [ ] P2.2 barge-in + skip-on-silence
287. [ ] P2.4 inline practical validation + P2.R3 lab narration
288. [ ] P2.5 resume score tips

### T8 — Jira / collaboration
289. [x] Coach reply when `@…team` parse fails (TODO 137) — *near-miss mention coach*
290. [x] E2E: mention → bot → disk appears in session `lsblk`
291. [ ] Teams channel bot parity

### T9 — Unified state bus remaining
292. [ ] Hardware failure fan-out → Grafana + SOC + DCIM LED + dmesg
293. [ ] Cross-console disk/NIC/CPU/RAM edits update guest tools
294. [ ] Twin replay timeline (undo cable/firmware/part swaps)
295. [ ] Org login → living enterprise chrome (tickets/CMDB/monitoring/clouds/DC/Git/AWX)

### T10 — AI Infra field ops depth
296. [ ] Ops runbooks: scp diag scripts MAAS↔node, PSBCheck, fieldiag, dcgmprofrunner, gpu-admin-tools PPCIe/CC
297. [ ] Pixel NVIDIA green / AMD red telemetry consoles
298. [ ] `dcgm-exporter` + Prometheus/Grafana companion scrape
299. [ ] MIG / vGPU partitions in twin + terminal
300. [ ] Multi-node NVLink fabric view
301. [ ] End-to-end commission → burn-in → production handoff project
302. [ ] CI lint: ai-infra scenarios never host as wrong cloud without `hosted_as`

### T11 — Verified live / remaining learner blockers (Aug 2026 deep check)
303. [x] **AI Infra technology live on prod API** (`/api/technologies/` → `ai-infra`, 150 scenarios) — if UI still hides it, hard-refresh / clear CDN; catalog + TechIcon already wired
304. [x] `subscription-manager` status/register/list/repos/attach/refresh/clean + broken entitlement preset + Jira RHSM credentials
305. [x] Paced streams: `ping` (already) + `journalctl -f` / `tail -f` / `top` / `watch` via StreamedCommandResult
306. [x] Open AWX companion for `ai-infra` + `consoles` include awx (ansible tech already)
307. [x] Jira coach when @mention near-miss fails parse (`@team storage`, typos)
308. [~] AWS console ErrorBoundary: capture production stack from returning-user localStorage — *null-safe scoped/merge + TopNav/CW filters*
309. [~] Datacenter twin ErrorBoundary: same chunk-recovery + store-reset path as AWS — *default floorView 2d to avoid R3F on open*
310. [x] Ansible YAML backfill: `consoles: [terminal, awx]` or `awx_link: true` on all ansible heroes (not only academy `simulation_type: ansible`)
311. [x] AWS companion link on every AWS-tech scenario (not only terraform/hosted heuristics)
312. [ ] TypeScript coding tech tree (missing entirely) + academy coding_mode pack
313. [x] Packer CodingIDE / workspace for image-factory scenarios (ai-infra)
314. [x] Terraform destroy → delete mirrored cloud/VMware resources
315. [ ] MAAS UI region/rack/images panes pixel surface
316. [ ] VyOS firewall/NAT/VPN/VRRP CLI + pixel appliance UI
317. [x] Steam DC: reception → security → staging → repair bay walkable stubs
318. [ ] IDE polish: file tree, tabs, run terminal panel, theme parity for Java/JS/React/HTML/Python/Shell/Node
319. [ ] GitOps: GitHub PR approve + Flux/Argo sync health end-to-end
320. [ ] Windows Simulator contrast pass (no white-on-white)
321. [ ] PeopleSoft app-server persona verification E2E (not AWS DMI)
322. [ ] Interview P2.1 voice loop + P2.R6 two-way framing UI
323. [x] E2E: `@storage team` → disk in `lsblk` (disk E2E)
324. [ ] Learning journey / career track row for AI Infra on `/technologies/ai-infra`
325. [ ] ai-infra scenario count growth: VyOS + Packer + MAAS + DCOps RMA heroes beyond current 150
326. [ ] Cross-tech companion session_id share assert in CI
327. [ ] Dead-link crawl CI for every console route
328. [ ] Per-tech 20-pack tracker dashboard (mark progress on 273–283)

---

## U. Mega wave — Steam DC + AI Infra depth + AWS/IDE realism (2026-08-05 audit)

Source: learner report (Steam Data Center Simulator parity, AI Infra as first-class tech, AWS Lab environment error, AWX chrome missing, Terraform popup consoles, Packer IDE, company-grade projects). Deep code audit before shipping — do not re-open fixed items blindly.

### U0 — Critical learner blockers (ship first)
329. [~] AWS "Lab environment error": distinguish ChunkLoadError vs Zustand — hide Reset for chunk fails; hard-reload copy — *wave1 UX*
330. [~] AWS: gate LabRunner on persist rehydrate so overlay reset is not undone by async merge — *AuthBoot wraps AppRouter*
331. [~] AWS: `mergePersistedAws` keep string chrome arrays (`favorites` / `recentServices` / `homeWidgets`) — *this PR*
332. [~] AWS: null-safe ConsoleHome / S3Pages / InstanceList post-nav reads — *ConsoleHome done; S3/EC2 follow*
333. [ ] AWS: verify CDN/edge never caches `index.html` over nginx no-cache
334. [ ] AWS: production verify academy-aws + aws-ec2 heroes load after deploy without boundary
335. [~] Primary GUI labs (AWX/Bare Metal/DC/Terraform): always-visible Hints/Check/+30m/Stop on companion strip — *wave1*
336. [~] AI Infra subscription unlocks Open AWX companion (not only ansible/ansible-awx) — *wave1*
337. [~] Terraform Open Cloud → full overlay popup (not cramped bottom panel) via companion event — *wave1*
338. [~] Deduplicate Terraform "Open AWS" vs "AWS Console" chips — *wave1*
339. [~] Packer IDE: allow `cross_technology` academy packer labs (`isPackerLab` gate) — *wave1*
340. [ ] Packer labs YAML: `consoles: [terminal, packer]` + drop or keep cross_tech intentionally
341. [ ] AWX primary labs: CI assert LabChromeBar + companion strip both receive four handlers
342. [x] Close / merge storage lsblk E2E + Packer IDE PRs into main + 4D deploy — *via #146*

### U1 — Steam-class Datacenter immersion (target: Data Center Simulator Game feel)
343. [~] Default entry: optional "Enter facility" cinematic (camera truck through security → reception → hall) — *#147 cinematic*
344. [~] First-person / badge-walk mode (even low-poly) for campus rooms — not orbit-only — *WASD walk in #147*
345. [~] 3D corridor meshes linking reception → staging → data-hall → MDF (progressive; ErrorBoundary) — *CorridorShell #147*
346. [~] Keep 2D floor default; "Enter hall (3D)" CTA with chrome intact + dedicated R3F ErrorBoundary — *#147*
347. [~] Ambient CRAC/PDU/fan audio bed + thermal alarm stinger tied to DC tickets — *#147*
348. [~] LED blink / fan spin / thermal aisle haze volume FX (extend Q 180–185) — *ThermalHaze #147*349. [ ] Cable bend + port LED realism on ToR / MDF trunks
350. [ ] Full FRU RMA loop: locate → order → dock receive → repair bay swap → burn-in → close ticket
351. [ ] Parts warehouse ↔ dock ↔ repair bay inventory sync with Jira FRU tickets
352. [ ] Per-rack GPU tray cross-link to `ai-infra` scenario IDs (TODO 271)
353. [ ] Soundscape mute / volume control in DC chrome
354. [ ] Progressive LOD / mobile 2D-only path so Steam FX never brick phones
355. [ ] DC twin performance budget: 60fps desktop target on mid GPU; degrade gracefully
356. [ ] Pixel checklist: Steam store reference for rack install / cable / walk pacing (docs + QA rubric)

### U2 — AI Infrastructure Engineering as first-class technology
357. [x] Tech slug `ai-infra` live on prod with 150 scenarios (catalog verify)
358. [ ] Career track / learning journey row on `/technologies/ai-infra` (324)
359. [ ] Grow beyond 150: dedicated VyOS heroes (BGP, DHCP helper, firewall, commit/rollback UI)
360. [ ] Grow: Packer image-factory heroes with IDE + MAAS publish assert
361. [ ] Grow: MAAS commission/deploy/release paced PXE + region/rack/images pixel panes
362. [ ] Grow: LXD GPU passthrough + projects/migration labs
363. [ ] Grow: AWX JT packs for driver/DCGM/repave with inventory from MAAS
364. [ ] Grow: DCOps RMA / thermal / SXM tray / fieldiag / DCGM heroes from Bare Metal team tickets
365. [ ] Ingest Bare Metal + ImageDev + DCOps wiki/Jira/GitHub readmes → scenario matrix spreadsheet
366. [ ] NVIDIA H100 / H200 / B300 + AMD MI300 command matrices in graded labs (not only GPU tech)
367. [ ] libguestfs / virt-customize image inspect labs under ai-infra
368. [~] Packer-built artifact selectable as MAAS boot-resource in same session (end-to-end) — *#149*
369. [ ] Open MAAS / Open AWX / Open Datacenter / Open Packer always visible on ai-infra labs when entitled
370. [ ] Ai-infra must NOT dump all work into `gpu` tech — keep GPU app-platform separate
371. [ ] Integrated stack graded project: MAAS + VyOS + LXD + AWX + DC + GPU CLI as one flow
372. [ ] Pixel MAAS UI: region/rack/images/scripts panes
373. [ ] Pixel VyOS UI: interfaces + firewall + BGP summary (beyond CLI)
374. [ ] AWX job stdout stream + inventory sync from MAAS for ai-infra JT labs
375. [ ] Seed more company-style projects (multi-ticket, multi-team, deps) for ai-infra

### U3 — Company-grade projects (all technologies)
376. [ ] Project template: epic + multi-team Jira + wiki + Git + AWX + validation gates
377. [ ] Every project lists real team handoffs (@storage / @network / @security / @backup / ImageDev / DCOps)
378. [ ] Projects require cross-console proof (terminal + GUI + ticket comments)
379. [ ] Refresh weak projects: acceptance criteria must name exact commands/consoles
380. [ ] Add dependency graph UI on project board (blocked-by tickets)
381. [ ] Project rubrics: timebox + severity + change window like real change management

### U4 — Scenario quality / command coverage (all techs)
382. [ ] Crawl every scenario YAML: consoles[], simulation_type, check.sh, graders — no fail-open
383. [ ] Every linked button in lab chrome opens a working surface for that session_id
384. [ ] Cross-tech scenarios: shared session_id assert in CI (326)
385. [ ] Dead-link crawl CI for console routes (327)
386. [ ] Per-tech 20-pack depth (273–283) with tracker dashboard (328)
387. [ ] Improve weak solutions/hints that skip required tools
388. [ ] Align academy markers FIXED-OK with real remediation paths

### U5 — IDE excellence (Terraform / Packer / Coding)
389. [~] Terraform: cloud consoles open as overlays not bottom tabs — *wave1*
390. [~] Terraform IDE: full folder tree, multi-root modules, `.terraform.lock.hcl`, fmt on save — *folder tree #152*
391. [ ] Terraform IDE: integrated terminal that creates/edits files under `/root/terraform`
392. [~] Terraform IDE: color themes, breadcrumbs, problems panel, command palette — *themes+breadcrumbs #152*
393. [ ] Packer IDE: sync edited `.pkr.hcl` into sim shell filesystem before build
394. [~] Packer IDE: variables UI + build log panel + artifact → MAAS publish button — *publish+sync in #149*
395. [ ] Coding IDE: file/folder structure, run/debug, multi-file tests (318)
396. [ ] Unified IDE shell shared by TF/Packer/Coding (VsCodeWorkbench extensions)

### U6 — AWS console depth & stability
397. [ ] Expand service coverage only after mount stability green
398. [ ] Persist schema version bump + migration for aws-sim blobs
399. [~] Soft-gate AppRouter/LabRunner until AWS rehydrate finishes — *AuthBootValidator children gate*
400. [ ] E2E Playwright: open aws-ec2 lab, navigate EC2/S3, no boundary

### U7 — Continue twin connectivity / leftover spine
401. [ ] Terraform destroy/MAAS fan-out already partially shipped — extend other `maas_*` types
402. [~] VyOS commit/rollback + BGP UI depth (226/261) — *compare + history CLI #151*
403. [ ] Subscription-manager realism remaining edge cases
404. [ ] Interview P2 voice + framing (322)
405. [ ] Unified asset registry finish (§S1) across AWS/DC/MAAS/AWX

### U8 — Extra audit lines from mega brief (do not skip)
406. [ ] AI Infra AWX lab: regression test that companion LabChromeControls never unmount on JT navigate
407. [ ] AI Infra catalog: seed VyOS commit/rollback CLI scenarios (at least 5 graded)
408. [ ] AI Infra catalog: seed Packer→libguestfs inspect→MAAS boot-resource publish chain
409. [ ] AI Infra catalog: seed MAAS enlist/commission/deploy/release with PXE timeline asserts
410. [ ] AI Infra catalog: seed LXD projects + GPU passthrough + live migration heroes
411. [ ] AI Infra: Bare Metal Jira ticket templates mirrored as scenario briefs (dcops/thermal/SXM)
412. [ ] AI Infra: ImageDev Packer base GPU image from upstream (RHEL/Ubuntu) hero project
413. [ ] AI Infra: AWX JT inventory sourced from MAAS machines tagged gpu
414. [ ] Datacenter Steam: rack install animation (slide tray + click rails + power LED cascade)
415. [ ] Datacenter Steam: cable pull physics (drag length + bend radius warn)
416. [ ] Datacenter Steam: thermal heatmap aisle overlay synced to ticket severity
417. [ ] Datacenter Steam: badge/door access mini-game before hall entry
418. [ ] Datacenter Steam: warehouse forklift / pallet receive for FRU RMA
419. [ ] IDE: file explorer create/rename/delete + drag-drop into workspace
420. [ ] IDE: split editor + terminal panel resize + command palette (Ctrl/Cmd+P)
421. [ ] IDE: syntax themes (light/dark/high-contrast) persisted per user
422. [~] Terraform popup: remove leftover bottom-panel cloud tabs entirely after overlay path — *#152*
423. [~] AWS: InstanceList / S3Pages null-safe maps (332 companion)
424. [~] AWS: bump persist version 3→4 after chrome string-array merge ships — *#148*
425. [ ] Scenario crawl: every ai-infra scenario has working consoles[] entries
426. [ ] Projects: multi-team AI cluster bring-up (MAAS+VyOS+LXD+AWX+DC) company template
427. [ ] Cross-tech: terraform→aws create/destroy already shipped — assert no dual AWS chips
428. [ ] Production smoke: academy-aws-001 + ai-infra AWX primary after each 4D deploy
429. [~] Datacenter: default entry is Steam 3D hall (not 2D) with mobile/reduced-motion 2D fallback — *this PR*
430. [~] Datacenter: rack tray slide-in install animation with rail click + LED cascade — *slide+stagger #154*
431. [~] Datacenter: FRU RMA full loop UI (locate → dock → repair → burn-in) — *partial #154*
456. [~] Scenario hero: ai-infra-packer-gpu-image-factory (align project_data_extra AII4) — *seeded*
458. [~] Scenario heroes: ai-infra-vyos-* (BGP/DHCP/firewall/commit-rollback) ×5 — *1/5 DHCP seeded*
467. [~] DCOps RMA deep scenario graded against FRU state machine (431/441) — *scenario seeded; grader still marker*
432. [ ] AI Infra: grow scenario count with VyOS/Packer/libguestfs heroes beyond academy packer markers
433. [ ] Verify AWS labs on prod after #148 AuthBoot harden (hard refresh + reset path)
434. [~] AWX companion LabChromeControls visible on every ai-infra primary GUI lab (regression) — *isAwxLab no longer steals ai-infra; companion uses onExit Close + fixed shell*
435. [~] Companion chrome one-pattern: every overlay `fixed inset-0 z-[60]` + never `embedded` for companions; Back = onExit||onToggleTerminal — *#154 follow-up*
436. [~] Primary companion strip parity: Open Packer / Bare Metal / Terraform / AWX / Datacenter chips — *#154 follow-up*
437. [~] Deduplicate Terraform+hosted AWS overlay double-mount; force `embedded={false}` popup shell — *#154 follow-up*
438. [~] ai-infra unlocks Datacenter companion without separate datacenter sub (AWX parity) — *#154 follow-up*
439. [~] showAwxLink: allow ai-infra + consoles:awx even when cross_technology — *#154 follow-up*
440. [~] FRU Issue spare always sends asset_id (selected server); disable without selection — *#154 follow-up*
441. [~] FRU RMA orchestrator: ship_rma → dock ASN(ticket+asset) → receive → kits_staged → repair_bay_swap → burn-in → close — *ASN+kit+swap in #154; burn-in/close auto still open*
442. [~] Repair bay UI: swap/consume staged kit actions (not copy-only) — *Install kit button*
443. [ ] Datacenter: expose RackPhysicsFruPanel on 3D path (today 2D-only)
444. [ ] Datacenter: ToR backbone cables interactive + bend-radius warn in InteractiveCable
445. [ ] Datacenter: aisle thermal heatmap keyed by ticket severity + BMC inlet (beyond single ThermalHaze plane)
446. [ ] Datacenter: badge/door gate WalkController before hall (CorridorShell door mesh)
447. [ ] Datacenter: forklift + pallet mesh animate on receive_dock
448. [ ] Datacenter: walkable campus room portals in 3D (not tab-only)
449. [ ] Datacenter: FPS LOD — cut particles / Rapier when fps < 40
450. [ ] Datacenter: ambient volume slider in chrome (TODO 353)
451. [ ] Datacenter: server drawer z-index must not bury Walk/FPS twin toolbar
452. [ ] LabRunner sidebar z-[75] must not paint over DC companion z-[60]
453. [~] MAAS deploy picker: select custom/{sku}-jammy boot resource in GUI + CLI maas_deploy — *engine+Images select in #154*
454. [ ] Packer scenarios: set consoles: [packer, baremetal, terminal] (not heuristic-only)
455. [ ] libguestfs handlers: guestfish / virt-customize / virt-inspect in simulation_modules
456. [ ] Scenario hero: ai-infra-packer-gpu-image-factory (align project_data_extra AII4)
457. [ ] Scenario hero: ai-infra-libguestfs-image-inspect
458. [ ] Scenario heroes: ai-infra-vyos-* (BGP/DHCP/firewall/commit-rollback) ×5
459. [ ] Scenario heroes: H200 / B300 / MI300X commission + thermal (SKU matrix)
460. [ ] VyOS pixel UI shell under frontend/src/components/vyos + LabRunner map
461. [ ] Replace FIXED-OK-only check.sh for ai-infra heroes with state asserts
462. [ ] lint_scenarios: forbid marker-only graders for ai-infra non-academy heroes
463. [ ] Company project template: MAAS+VyOS+LXD+AWX+DC multi-team board with blocked-by
464. [ ] ImageDev Packer base GPU image from upstream RHEL/Ubuntu hero + GH Actions factory
465. [ ] AWX JT inventory sourced from MAAS machines tagged gpu (live mirror)
466. [ ] PSINFRA / GM1 escalation multi-team handoff scenario
467. [ ] DCOps RMA deep scenario graded against FRU state machine (431/441)
468. [ ] Terraform IDE: integrated terminal creates files under /root/terraform
469. [ ] Packer IDE: variables UI + build log panel polish beyond publish button
470. [ ] Coding IDE: file/folder create/rename/delete + drag-drop
471. [ ] Unified IDE shell shared by TF/Packer/Coding
472. [ ] AWS Playwright E2E: open academy-aws lab, EC2 navigate, no boundary crash
473. [ ] Production smoke checklist after every 4D deploy (AWS + ai-infra AWX Open + Packer publish)
474. [ ] Jira @team coach + disk E2E wave
475. [ ] Terraform destroy / MAAS fan-out remaining maas_* types
476. [ ] subscription-manager realism remaining edge cases
477. [ ] Terraform→VMware create mirror (212 slice)
478. [ ] Jira mentions wave (137)
479. [ ] Reconcile stale TODO 309/346 (2D default) vs 429 (3D default)
480. [ ] CI assert: companion overlays never pass embedded=true; LabChromeControls present after JT navigate


---

## Execution order (updated)

1. **Wave1 (merged #146):** AWS chunk-error UX, primary-lab chrome, AWX ai-infra entitlement, TF overlay popup + AWS chip dedupe, Packer cross-tech gate, storage lsblk
2. **Steam DC enter+audio (#147):** TODOs 346–347
3. **AWS rehydrate harden (#148):** AuthBoot gates AppRouter; mergePersisted string chrome; lab clearStorage; ConsoleHome null-safe
4. **Packer→MAAS (#149), VyOS CLI (#151), TF IDE (#152), DC 3D default (#153)**
5. **Companion chrome one-pattern (#154):** 434–440 — AWX Close/chrome, strip parity, AWS popup dedupe, FRU asset_id
6. Steam DC immersion remaining (414–418, 430–431, 441–452)
7. AI Infra growth (453–467, 406–413, 425–426)
8. Company projects U3 + scenario crawl U4
9. IDE excellence (468–471, 389–396, 419–421)
10. Twin leftovers / Jira / TF→VMware / registry (474–478, U7)
