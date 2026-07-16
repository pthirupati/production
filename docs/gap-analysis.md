# FixItLab Gap Analysis — Production-Grade Company Infra

Living document for the platform hardening pass on `chore/vault-diagnose`.
Last updated: 2026-07-16.

## North-star rules

1. **Scenario-scoped Lab Servers (not one global server).** Each lab session owns its own LabServer graph (`ServerIdentity` keyed by `session_id`). Cross-tech consoles in the *same* scenario share those servers; AWS EC2 never appears in a physical rack, and VMware guests never leak into unrelated AWS labs. See `docs/architecture-lab-servers.md`.
2. **Prefer a real free/self-hosted engine over a hand-rolled mock** when one exists and runs at zero external cloud spend (Phase 1.5 / 1.6). Otherwise build an API-faithful facade and label it.
3. **Never show learners:** Simulation, Simulator, Simulated, Demo, Mock, Fake, Practice Environment. Internal code/docs may keep those terms; UI must read as Fortune-100 company infra (console, environment, lab, vCenter, Command Center, AI Interview Studio, sample labs, practice exam).
4. **Zero real cloud / vendor spend / physical GPU.** In-memory facades and future self-hosted emulators only; quotas + default-deny egress + idle teardown are mandatory.

### Recommended build order (consolidated)

1. Finish scenario LabServer seeding + bridges for every existing tech (this pass).
2. Scenario YAML schema + linter + richer Jira coach content.
3. Deepen Commvault / NetApp / Dell / Datacenter / SOC beyond hero labs.
4. Azure / GCP / OpenStack / OpenShift as **new scenario-scoped console packs** (facades first) — not one shared cloud VM.
5. Optional free emulators behind feature flags (vcsim, LocalStack CE if license OK, kind, VirtualBMC/sushy) — still zero real-cloud cost.

---

## Technology inventory (Phase 0)

| Tech | Backend | Frontend | Shared identity today | Real-engine vs facade | Status |
|---|---|---|---|---|---|
| VMware | `vmware_sim/engine.py` | `VMwareSimulator.jsx` | Partial (`vmware_bridge`) | **Target:** `vcsim` (govmomi). Today: facade | Bridge to terminal works for NIC/disk/power |
| AWS | `aws_engine.py` + Zustand store | `AwsLabOverlay` | Partial (`aws_bridge`) | **Target:** LocalStack CE / OSS successor (verify license). Today: facade; FE store still often SoT | Bridge attach/power → terminal |
| Linux terminal | `unified_sim` / `rhel_shell` | LabTerminal WS | Hub for bridges | **Target:** real per-session container/microVM. Today: Python shell facade | High fidelity facade |
| AWX | `awx_engine.py` | `AwxSimulator.jsx` | Partial (ansible bridge) | Facade (no Tower API) | OK as facade |
| Grafana/Prom | `monitoring_engine.py` | `MonitoringSimulator.jsx` | Cosmetic only | **Target:** real Prometheus+Grafana containers. Today: facade | Health not graded |
| CI/CD | `cicd_engine.py` (grading) + FE mock | `CicdPipelineSim.jsx` | Isolated | **Target:** real job runner in sandbox. Today: toy | P0 rebuild |
| Kubernetes | `k8s_engine.py` + `k8s_cluster.py` | No GUI wired to engine | Partial VMware↔kubectl | **Target:** kind/k3s. Today: dual unsynced facades | Orphan GUI engine |
| GPU | none | terminal only | N/A | **Target:** mocked PCI/`nvidia-smi` via ServerIdentity. Today: broken grading | 87% check.sh auto-pass |
| Windows | `windows_engine.py` | `WindowsServerSimulator` | Isolated | Facade + **SCCM patching (done)** | SCCM Software Center + scenario added |
| Terraform | `terraform_engine.py` | TerraformSimulator | Partial file sync | Facade (no real terraform binary) | |
| PeopleSoft | `peoplesoft_engine.py` | PeopleSoftSimulator | Isolated | Facade-only (no OSS) | |
| Commvault | `commvault_engine.py` | CommvaultSimulator | Partial VM discovery | **Facade-only** (no public simulator) | Hero labs exist |
| NetApp | `netapp_engine.py` | NetAppSimulator | Isolated | Facade vs ONTAP REST (vsim entitlement-gated opt-in later) | Hero lab |
| Dell EMC | `dellemc_engine.py` | DellEmcSimulator | Isolated | **High-fidelity facade** (no redistributable sim) | Hero lab |
| Datacenter | `datacenter_engine.py` | DatacenterSimulator | Partial (ServerIdentity sync + BMC) | Facade (physical always in-memory). **Target:** VirtualBMC + sushy + MAAS later | Multi-room facility + PUE/ASHRAE + BMC + chaos |
| SOC | `soc_engine.py` | SocSimulator | Isolated | **Target:** Suricata/Zeek + OpenSearch + Juice Shop. Today: facade | Hero labs |
| Baremetal | `baremetal_engine.py` | BaremetalSimulator | Isolated | **Target:** MAAS + VirtualBMC. Today: facade | |
| Nmap / Wireshark | engines | inline sims | Isolated | Target: real nmap/tshark in sandbox | Facades |
| Jira | `jira_integration` | JiraUi | Yes (ops_state) | Real Jira Cloud optional; sim default | Coach bots OK |
| Coding IDE | — | CodingIDE | N/A | Pyodide real for Python/JS | |

---

## Gap ledger

### P0 — must finish for “real company infra” feel

| ID | Gap | Root cause | Affected | Proposed fix | Done? |
|---|---|---|---|---|---|
| G-01 | No scenario LabServer registry | Each engine owns private JSON | all engines | Session-scoped ServerIdentity + bridges | **Partial** — VMware/AWS/GPU + `seed_scenario_lab_servers` for other personas |
| G-02 | AWS FE store ≠ backend | Zustand localStorage is SoT | awsStore, aws_engine | Make backend authoritative; FE thin cache | Partial (`aws_bridge`) |
| G-03 | Learner sees “simulation” | Copy in LabRunner, AWS, VMware, errors | frontend | Purge user-facing strings | **Done** (marketing + consoles; internal code/comments OK) |
| G-04 | GPU labs auto-pass | No engine; check.sh `exit 0` | scenarios/gpu | Mock GPU in ServerIdentity + real validate | **Partial** — ServerIdentity GPU facet + seed; grader still uses `gpu_healthy` |
| G-05 | Ansible terminal labs auto-pass | No validate_ansible_lab; engine=None fail-open | scenarios/ansible | Wire grading to shell state / AWX | **Partial** — engine=None fail-open fixed; ssh-key still primary objective |
| G-06 | CI/CD is a toy | FE mock; cicd_engine not session-wired | CicdPipelineSim | Real sandbox job runner | Open |
| G-07 | K8s dual engines | GUI engine orphaned | k8s_engine, k8s_cluster | Unify under kind + ServerIdentity | Open |

### P1

| ID | Gap | Proposed fix | Done? |
|---|---|---|---|
| G-10 | Thin scenario YAML | Schema + linter (Phase 3.1) | **Partial** — `docs/scenario-schema.md` + `scripts/lint_scenarios.py` (CI `--strict-heroes`); hero labs declare `consoles`/`lab_servers`; catalog-wide enrich still open |
| G-11 | Jira coach shallow | Acceptance-criteria coach (started) | Partial |
| G-12 | Windows no SCCM/patching | Add SCCM console + scenarios | **Done** |
| G-13 | Datacenter not cross-tech | Show Open Datacenter + shared ServerIdentity | **Done** (UI link; facility rooms/BMC/PUE; deeper merge still open) |
| G-14 | Monitoring cosmetic | Real Prom/Grafana or feed validation | Open |
| G-15 | No shared chaos/fault layer | Per-engine one-off flags | `chaos_engine.py` + DC trip_pdu | **Done** (foundation; wire more engines next) |

### P2 / multi-sprint (real engines)

| ID | Gap | Notes |
|---|---|---|
| G-20 | vcsim under VMware | Pool per session; ServerIdentity listens |
| G-21 | Local AWS emulator | CI lint blocks real amazonaws.com |
| G-22 | kind/k3s per session | Quotas + tear-down |
| G-23 | Cyber range real tools | Juice Shop + Suricata + OpenSearch |
| G-24 | Physical: VirtualBMC + sushy + MAAS | Phase 7 sequence |
| G-25 | Three.js facility + 2D fallback | After 7.1–7.7 data model |
| G-26 | Session pool / golden images | Cost control Phase 1.6 |

---

## Real vs facade decisions (locked for this pass)

| Tech | Decision |
|---|---|
| VMware | Facade now → **vcsim** next sprint |
| AWS | Facade + bridge now → **LocalStack/OSS** next (license check) |
| Commvault | **Faithful facade** permanently (no public sim) |
| Dell EMC | **High-fidelity facade** (published API shapes) |
| NetApp | Facade default; real vsim **opt-in entitlement flag** only |
| Terminal | Facade shell now → real container later |
| GPU | Always **virtualized/mocked** device — never real GPU |
| Datacenter / BMC | Facade now → VirtualBMC / sushy-tools / qemu-bmc + MAAS later (zero real hardware) |
| SOC | Facade now → real IDS/SIEM stack later |

Research note (Phase 7 path): OpenStack **sushy-emulator** (Redfish over libvirt) and **VirtualBMC** (IPMI) remain the standard free backends; **qemu-bmc** is a newer single-binary Redfish+IPMI option suited to containerized MAAS labs. Default build stays in-memory facade until a feature-flagged emulator pool ships.

---

## Baseline already verified (do not regress)

- Interview round DELETE; interview TTS unlock
- Lab companion strip; SimErrorBoundary
- CloudShell SSH + SG; VMware NIC/disk bridge; AWS seed + Instance Connect sync
- Jira @security / coach help; enterprise hero sims (Commvault/NetApp/Dell/DC/SOC)

---

## Resource footprint (Phase 1.6 — measured later)

Not yet measured. Target after containerization: document CPU/RAM/disk per session type and concurrent capacity per host.

---

## Shipped this pass (verify before marking done)

- Learner copy purge: Demo/Mock/Simulator → lab console / AI Interview / sample labs / practice exam
- Datacenter facility: Data Hall / MDF / Mechanical / Electrical rooms, power chain + PUE, CRAC/ASHRAE, switches, BMC power menu, ServerIdentity sync, PDU breaker → chaos
- Shared `chaos_engine` (`drop_nic`, `fill_disk`, `stop_service`, `trip_pdu`, `raise_temp`) + tests
- Phase 3.1: scenario schema doc + hero YAML linter in CI; heroes declare `lab_servers`/`consoles`; seed materializes YAML LabServers per session
- Scenario-scoped LabServer architecture doc (`docs/architecture-lab-servers.md`)

## Recommended next priorities after this commit

1. Finish ServerIdentity read/write in AWX / Grafana / K8s / Windows beyond YAML seed.
2. Fix GPU + Ansible grading (correctness) — highest P0 correctness debt.
3. Wire CI/CD to a real sandbox runner.
4. Introduce vcsim behind a feature flag for VMware.
5. Catalog-wide scenario enrich + `lint_scenarios.py --all` warn mode; grow Commvault/NetApp/Dell/SOC packs beyond heroes.
