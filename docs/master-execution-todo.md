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
- [~] AWS ↔ terminal bridge (exists; FE Zustand still often SoT)
- [x] `seed_scenario_lab_servers` + YAML `lab_servers` for heroes
- [x] Bidirectional sync: AWX
- [x] Bidirectional sync: Grafana / Prometheus
- [x] Bidirectional sync: Kubernetes
- [x] Bidirectional sync: GPU (seed + set_gpu on modprobe); grading verified fail-closed across all academy-gpu-* slugs (G-04)
- [x] Bidirectional sync: Windows
- [x] Bidirectional sync: Commvault (clients) / NetApp (storage) / Dell EMC (storage) / SOC (assets, quarantine=power)
- [~] Datacenter (already had deeper sync from earlier pass; see G-13)
- [ ] `physical_location` / `bmc` / `network_port` on every physical LabServer path
- [ ] Event bus correlation/trace ID on every mutation

## Phase 1.5 — Prefer real free engines (feature-flagged)
- [ ] VMware → `vcsim` (flag)
- [ ] AWS → LocalStack CE / OSS successor (license check + flag)
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
- [x] 3.2 Chaos engine foundation
- [x] 3.2 Wire chaos into VMware / Windows / NetApp (drop_nic/stop_service/fill_disk); AWS/SOC/DellEMC still open
- [x] 3.4 Cross-console fault ledger API (`GET /api/vmware/sessions/<id>/faults/`) — any console can see what's broken
- [ ] 3.3 Learner SSO identity + RBAC across consoles
- [ ] 3.4 Cross-engine trace IDs
- [ ] 3.5 Session lifecycle manager

## Phase 4 — Cybersecurity course + range
- [~] SOC console + hero labs (ransomware, brute-force)
- [ ] SIEM / EDR / firewall / pcap / vuln scanner / attacker terminal (full)
- [ ] Scenario types: SOC L1/L2, IR, hunting, vuln assess, red vs blue
- [ ] MITRE ATT&CK + NIST-NICE on all cyber scenarios
- [ ] @security as incident coordinator with acceptance hints
- [ ] LabServers for every cyber host

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
- [ ] Azure Portal pack + heroes + LabServer (Azure VM ≠ physical rack)
- [ ] GCP Console pack + heroes
- [ ] OpenStack Horizon pack + heroes
- [ ] OpenShift Console pack + heroes
- [ ] Expand networking / identity / backup (Veeam) / Hyper-V as needed

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
