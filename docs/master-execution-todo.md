# Master execution todo — Enterprise Infrastructure Platform

Source of truth for the master architecture prompt. Track status in `docs/gap-analysis.md`.
**Rule:** scenario-scoped Lab Servers (no platform-global host). Zero real cloud/GPU spend. Never show Simulation/Simulator/Demo/Mock/Fake to learners.

Legend: `[x]` done · `[~]` partial · `[ ]` open

---

## Phase 0 — Audit & research
- [x] Technology inventory in gap-analysis
- [x] Real vs facade decisions documented
- [x] Living gap ledger (`docs/gap-analysis.md`)
- [x] Scenario LabServer architecture doc
- [ ] Keep inventory updated as packs land (Azure/GCP/OpenStack/OpenShift)

## Phase 1 — Scenario-scoped LabServer identity + event bus
- [x] ServerIdentity keyed by `session_id`
- [x] VMware ↔ terminal NIC/disk/power bridge
- [x] AWS ↔ terminal bridge — audited every awsStore.js action against aws_engine.py's 8 graded
      `broken` marker types; every action that can satisfy one already syncs to the backend
      (`GuiSyncContractTests` + this session's detachVolume/deleteSecurityGroup fixes). 30/30 green.
      Non-core AWS services (RDS/Lambda/DynamoDB/CloudFormation/CloudWatch/ELB/ASG) intentionally
      remain frontend-only — aws_engine doesn't model or grade them today, so backend-authority there
      is moot until/unless per-service grading is authored (see new backlog item below).
- [x] `seed_scenario_lab_servers` + YAML `lab_servers` for heroes
- [x] Bidirectional sync: AWX
- [x] Bidirectional sync: Grafana / Prometheus
- [x] Bidirectional sync: Kubernetes
- [x] Bidirectional sync: GPU (seed + set_gpu on modprobe); grading verified fail-closed across all academy-gpu-* slugs (G-04)
- [x] Bidirectional sync: Windows
- [x] Bidirectional sync: Commvault (clients) / NetApp (storage) / Dell EMC (storage) / SOC (assets, quarantine=power)
- [~] Datacenter (already had deeper sync from earlier pass; see G-13)
- [ ] `physical_location` / `bmc` / `network_port` on every physical LabServer path
- [x] Event bus correlation/trace ID — `server_identity.new_trace_id()` / `events_for_trace()` added;
      threaded through `upsert_server`/`set_power`/`attach_disk`/`detach_disk`/`attach_nic` (optional
      kwarg, fully backward compatible). Wired end-to-end for Azure/GCP (console click -> engine's own
      event log -> bridge queue -> terminal apply, all sharing one trace_id, closed via a new
      `RHELShell._publish_resize_applied` hook) and AWS bridge (volume attach/detach, instance power).
      9 new tests prove the full chain reconstructs via `events_for_trace()`. VMware/Windows/other
      bridges still emit untraced events — same additive kwarg pattern, just not wired yet.

## Phase 1.5 — Prefer real free engines (feature-flagged)
- [ ] VMware → `vcsim` (flag)
- [x] AWS → LocalStack evaluated Jul 2026: **reject for commercial FixItLab** (CE ended; free Hobby is non-commercial-only; paid breaks zero-vendor-spend). Stay on `aws_engine` + Zustand facade; deepen grading instead.
- [ ] K8s → kind/k3s per session (flag)
- [ ] CI/CD → sandbox job runner executing real steps
- [ ] GPU → virtualized PCI/`nvidia-smi` only (never real GPU) — partial seed done
- [ ] Cyber → Juice Shop / Suricata / OpenSearch / Kali sandboxes (flag)
- [ ] NetApp → facade default; vsim entitlement opt-in
- [ ] Dell / Commvault → documented high-fidelity facades
- [ ] Terminal → real container/microVM later
- [ ] BMC → VirtualBMC + sushy-emulator (flag)
- [ ] Bare metal → MAAS over BMC-fronted VMs (flag)

## Phase 1.6 — Cost containment
- [ ] CI lint: no real `amazonaws.com` / vendor management endpoints
- [ ] Per-session CPU/RAM/disk/network quotas
- [ ] Idle teardown + GC
- [ ] Default-deny egress from sandboxes
- [ ] Golden-image / CoW session pool
- [ ] Admin live session / resource dashboard
- [ ] Measure & document footprint in gap-analysis

## Phase 2 — Backlog verification
- [x] Interview round DELETE
- [x] Lab companion strip + SimErrorBoundary
- [x] CloudShell SSH + SG; Instance Connect SG gate
- [x] VMware hot-add bridge + console ip a / PCI rescan
- [x] AWS lab terminal seed + Instance Connect re-sync
- [x] AWS EBS detach round-trips through engine/bridge/ServerIdentity (was attach-only)
- [x] Jira @security / @network keywords + engine lookup
- [x] Windows SCCM patching
- [x] **CI/CD grading regression**: dispatcher no longer shadows the terminal-only devops/cicd/pipeline catalog with the orphaned `cicd_engine` (found + fixed this pass; see G-06)
- [~] AWX/Grafana/Prom/K8s LabServer sync done; GPU/Windows partial — deeper bidirectional writes still open
- [~] Scenario YAML quality (heroes linted; catalog open)
- [~] Jira bot coaching depth
- [ ] GUI polish per every scenario type
- [x] CI/CD grading regression fixed (dispatcher no longer shadows terminal catalog)
- [ ] CI/CD rebuilt on real runner (FE CicdPipelineSim ↔ backend cicd_engine still disconnected; engine itself unused by any scenario today — deliberately, until FE wiring + explicit opt-in exist)
- [x] AWS EBS detach round-trips through engine/bridge/ServerIdentity (was attach-only)

## Phase 3 — Cross-cutting systems
- [x] 3.1 Scenario schema + hero linter in CI
- [ ] 3.1 Catalog migration + enricher at scale
- [~] CI/CD real sandbox runner — investigated in depth. `cicd_engine.py` is a complete, well-tested,
      fail-closed backend (derives outcome from job image/needs/manual-gate state, never a free
      green/red toggle) but is genuinely orphaned: no scenario opts into it, and the frontend
      `CicdPipelineSim.jsx` (647 lines + PipelineGraph/JobConsole/pipelineEngine/pipelineParser, ~2000
      more) is a rich, already-working, YAML-driven multi-provider (GitLab/GitHub/Jenkins) pipeline UI
      with its OWN parsed-model execution — not a fake toggle either, just not backend-authoritative.
      Wiring them together risks a bad mapping between "arbitrary parsed YAML" and cicd_engine's fixed
      3-job shape, which could make a *valid* learner fix grade as failing — worse than today's status
      quo. Decision: leave both exactly as they are (zero regression risk) until a dedicated pass can
      afford to either (a) constrain new hero labs to cicd_engine's exact job shape with a purpose-built
      thin UI, or (b) extend cicd_engine to accept an arbitrary parsed-YAML job graph as input.
- [x] 3.2 Chaos engine foundation
- [x] 3.2 Wire chaos into VMware / Windows / NetApp / AWX / SOC (drop_nic/stop_service/fill_disk).
      AWS and Dell EMC intentionally left unwired — audited both engines' actual `broken` marker
      shapes (EBS/SG for AWS; unmapped-volume/masking-view for Dell EMC) and neither has a clean
      semantic fit with the current 5 fault types (drop_nic/fill_disk/stop_service/trip_pdu/raise_temp);
      forcing a mismatched label would hurt the ledger's signal quality more than help it.
- [x] 3.4 Cross-console fault ledger API (`GET /api/vmware/sessions/<id>/faults/`) — any console can see what's broken
- [x] New pack: Microsoft Azure — Portal console (Resource groups/VMs/VNets/NSGs/Managed disks), server-authoritative
      backend (`azure_engine.py`), cross-tech bridge to the Linux terminal (`azure_bridge.py` — VM resize really
      changes `nproc`/`free -h` in the SAME session's guest, matching the master-prompt canonical example),
      ServerIdentity sync (`sync_azure_vm`), 3 hero labs (resize-undersized-VM, NSG-blocks-SSH with real
      priority-ordered rule evaluation, attach-pending-managed-disk), fail-closed grading, full dispatch wiring,
      and a real frontend console (`AzureConsole.jsx`) with zero local state duplication (every action round-trips
      to the backend — avoids the AWS Zustand-drift gap by construction).
- [x] New pack: Google Cloud Platform — Console (VPC/Firewall rules with real priority-ordered allow/deny
      evaluation/VM instances/Persistent Disks), server-authoritative backend (`gcp_engine.py`) + cross-tech
      bridge (`gcp_bridge.py` — machine-type change really changes `nproc`/`free -h` in the SAME session's
      guest) + `sync_gcp_instance` + full dispatch/seed wiring + `GcpConsole.jsx` (zero local state
      duplication, same pattern as Azure). 3 hero labs, 22 new backend tests, full catalog lint clean.
      OpenStack/OpenShift packs still open.
- [ ] 3.3 Learner SSO identity + RBAC across consoles
- [ ] 3.4 Cross-engine trace IDs
- [ ] 3.5 Session lifecycle manager

## Phase 4 — Cybersecurity course + range
- [x] SOC console + 6 hero labs, covering 4 of the 5 scenario types with real (not relabeled) fits:
      SOC Analyst triage (`soc-brute-force-block-ip`), Incident Response (`soc-escalate-critical-alert`,
      `soc-execute-containment-playbook`), Threat Hunting (`soc-threat-hunt-attacker-ip`), Red vs Blue
      (`soc-red-vs-blue-dual-containment` — a genuinely new dual-vector preset requiring BOTH block_ip
      AND quarantine_host, added as a new `_apply_preset` branch with zero changes to existing branches).
      Every existing/new preset now has dedicated engine tests (`apps/vmware_sim/tests/test_soc_engine.py`,
      14 tests) plus dispatch-integration tests (4 tests) — closing the "no test_soc*.py" gap found during
      the audit. All 6 labs carry real MITRE ATT&CK technique IDs + NIST-NICE work role codes.
- [ ] Vulnerability Assessment scenario type — deliberately NOT built this pass: soc_engine has no
      vuln-scanning concept, and relabeling an existing action (block/quarantine) as "vulnerability
      assessment" would be dishonest content. Needs a real (even if small) vuln-scan engine+action first.
- [ ] SIEM / EDR / firewall / pcap / vuln scanner / attacker terminal (full standalone consoles) — pcap
      exists today only as the separate Wireshark track, not integrated into the cyber range narrative.
- [x] MITRE ATT&CK + NIST-NICE — present on all 6 SOC hero labs (was 2/2 before this pass, now 6/6)
- [ ] @security as incident coordinator with acceptance hints
- [ ] LabServers for every cyber host (web01/ws-finance-07 already wired; db01 not yet)

## Phase 5 — Commvault + VMware
- [~] Hero: cv-vm-backup-missing-client + VMware discovery
- [ ] Add hypervisor wizard (full)
- [ ] VM group discovery rules (dynamic)
- [ ] Backup plans Full + Incremental
- [ ] Jobs monitor with chaos failure reasons
- [ ] Restore wizard (full VM + guest file)
- [ ] Academy scenario pack

## Phase 6 — Dell EMC + NetApp
- [~] Hero labs (masking / volume resize)
- [ ] PowerStore/Unisphere: pools, LUN/NAS, snapshots, replication, wizards
- [ ] ONTAP: volumes, snapshot policies, SnapMirror, FlexClone
- [ ] Attach storage to LabServers / VMware datastores
- [ ] Academy packs

## Phase 7 — Physical datacenter
- [~] Multi-room facility + power/PUE/ASHRAE/BMC (facade)
- [ ] 7.1 Full org/region/campus hierarchy
- [ ] 7.2 Complete power chain faults → LabServer power
- [ ] 7.3 Cooling model + liquid cooling for GPU racks + DCIM
- [ ] 7.4 Network fabric + structured cabling + topology
- [ ] 7.4 SAN FC zoning + multipathing
- [ ] 7.5 BMC console (KVM/power/boot/SEL) → VirtualBMC/sushy later
- [ ] 7.6 MAAS lifecycle (New→…→Released) + ESXi/GPU deploy path
- [ ] 7.7 Component-level replace (CPU/DIMM/PCIe/disk) with OS consequences
- [ ] 7.8 Three.js 3D + 2D fallback
- [ ] 7.9 Cross-tech: same LabServer as ESXi / MAAS / GPU / storage / switch
- [ ] 7.10 Badge access + @facilities + CCTV viewpoints

## Phase 8 — Content & quality
- [x] Banned-word purge (major surfaces)
- [x] Zero banned learner words remaining — full `lint_scenarios.py --all` sweep across all 5393 scenarios: 0 findings (was 9098 across 5535 files); also found + deleted a bogus "IT Simulation Labs" pseudo-technology (150 nonsense scenarios) and registered TECH_META for the 5 new hero techs
- [~] Every scenario: objective, AC, progressive hints — required-field schema already enforced catalog-wide by the existing enricher; `consoles`/`lab_servers` metadata still hero-only
- [ ] Jira tickets as playbooks everywhere
- [ ] No dead buttons / blank panels / console errors

## Phase 9 — Delivery
- [x] Clean scoped commits on `chore/vault-diagnose`
- [ ] Lint 0 + backend/frontend tests green for each slice
- [ ] Integration tests against real engines when flagged on
- [ ] Gap-analysis always current
- [ ] Health Check workflow permissions fixed (issues:write)

## New technology packs (scenario-scoped facades first)
- [x] Azure Portal pack + heroes + LabServer — Resource Groups/VNets/NSGs (real priority-ordered rule
      eval)/VMs/Managed Disks, `azure_engine.py` + `azure_bridge.py` (VM resize really changes
      nproc/free in the same-session Linux terminal — the master-prompt canonical example) +
      `sync_azure_vm` + full provisioner dispatch/seed wiring + `AzureConsole.jsx`. 3 hero labs, 23 new
      backend tests, full catalog lint clean.
- [ ] GCP Console pack + heroes
- [ ] OpenStack Horizon pack + heroes
- [ ] OpenShift Console pack + heroes
- [ ] Expand networking / identity / backup (Veeam) / Hyper-V as needed

## Grading depth (new backlog item — found during the AWS SoT audit)
- [ ] ~350 `academy-aws-*` scenarios (EKS/SSM/Kinesis/ELB/Route53/Cognito/RDS/Lambda/DynamoDB/
      CloudFormation/CloudWatch/ASG/...) ship a generic `check.sh` stub with no topic-specific
      `broken` marker in `aws_engine._apply_preset`, so they grade via the fail-closed-until-any-
      activity fallback (`validate_aws_lab`'s final `if not events: fail` branch) rather than checking
      the actual topic. Not a regression — it is at minimum fail-closed on a fresh session — but it is
      not rigorous. Fixing this means authoring a `broken` preset + a specific check per AWS service
      (a large content project, comparable in size to a new tech pack per service) plus, for the
      services aws_engine does not model at all yet (RDS/Lambda/DynamoDB/CloudFormation/CloudWatch/
      ELB/ASG), extending the engine's state model first.

## Ops / CI
- [x] Fix Health Check resolve job 403 (`issues: write`)
- [ ] Interview TTS verified in prod after deploy
- [ ] `migrate` + `seed_scenarios` for new techs in prod
- [ ] Push `chore/vault-diagnose` (or merge) so health-check fix reaches production repo

---

## Execution order (do not skip)
1. CI health perms + master todo (this doc)
2. P0 LabServer sync packs (AWX→Grafana→Windows→K8s→GPU) + AWS SoT
3. ~~GPU/Ansible grading~~ (verified fail-closed, done) + CI/CD sandbox runner
4. Chaos wiring + scenario catalog enrich + Jira coach
5. Commvault/NetApp/Dell depth + cyber range expansion
6. Datacenter 7.x deepening (data model before Three.js)
7. Azure/GCP/OpenStack/OpenShift facades
8. Feature-flagged real engines + cost controls
