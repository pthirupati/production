# Datacenter Digital Twin — Engineering Roadmap (FixitLab)

This is the **authoritative phased backlog** for the enterprise DCIM / digital-twin vision.
Implementation stays inside FixitLab’s LabRunner datacenter sim (`datacenter_engine` + React UI).
A separate Three.js + Rapier monorepo is **Phase 7 optional** only after product decision.

Learner language: Lab Environment / Lab Server / Hosted as — never “Simulation/Sandbox/Mock”.

Legend: `[x]` done · `[~]` partial · `[ ]` open

---

## Vision mandate

Professional production-grade Digital Twin / DCIM — interactive, configurable, removable,
replaceable, monitorable. Full lifecycle: plan → install → deploy → monitor → troubleshoot →
maintain → RMA → incident. Performance target for any future 3D surface: 60+ FPS via LOD /
instancing / streaming.

---

## Requirement → phase map

| # | Requirement | Phase | Status |
|---|-------------|-------|--------|
| 1 | Real physics (Rapier/Cannon) | P4 lite → P7 Rapier | [x] |
| 2 | Entire campus building | P1 | [x] campus rooms + plant assets |
| 3 | Complete rack FRU | P4 | [~] racks/PDUs; not every screw |
| 4 | Every server OEM | P2 | [~] Dell/HPE live; catalog expanded |
| 5 | Every CPU generation | P2 | [~] catalog |
| 6 | GPU systems (DGX/HGX/…) | P2 catalog → P6 AI | [~] |
| 7 | Complete motherboard + bus anim | P1 panels → P4 anim | [~] |
| 8 | Every cable type + ops | P1 plug → P3 catalog | [~] |
| 9 | Real switches + CLI | P3 | [ ] |
| 10 | Console / BIOS / BMC / PXE | P1–P2 | [~] |
| 11 | Real storage stack | P3 | [ ] |
| 12 | Networking simulation | P3 | [ ] |
| 13 | Hypervisors | P6 | [~] ESXi role bridge |
| 14 | Kubernetes | P6 | [ ] |
| 15 | AI infrastructure | P6 | [ ] |
| 16 | Monitoring dashboards | P5 | [~] DCIM PUE |
| 17 | Ticketing / RMA | P1 Dell/HPE → P5 full | [~] |
| 18 | Inventory / CMDB | P2 | [~] |
| 19 | Troubleshooting / failure inject | P2 | [~] |
| 20 | Hardware replacement / service mode | P2 | [~] |
| 21 | Interactive training roles | P5 | [ ] |
| 22 | Digital twin persistence / replay | P5 | [~] session cache |

---

## Phase 1 — Foundation (shipped)

- [x] Multi-room facility + power chain + CRAC + network ports
- [x] FRU replace, cables plug/unplug, Dell/HPE tickets, serial console
- [x] Motherboard / RAID / BIOS / iDRAC·iLO panels
- [x] Campus zones (gate, NOC, SOC, generators, chillers, MMR, FEF, …)

## Phase 2 — Hardware depth (current)

- [x] Hardware catalog: OEMs, CPU gens, GPUs, cables, switch vendors
- [x] CMDB inventory records (serial, asset tag, warranty, EOS/EOL, history)
- [x] Expanded failure injection presets
- [x] Service mode: rails, CPU, paste, CMOS/TPM, hot-swap PSU
- [x] RAID depth: delete VD, patrol, CC, foreign import
- [x] BMC depth: generations, NMI, firmware targets, users, HTML5 KVM
- [x] BIOS: POST, password, flash, boot settings
- [x] Wire every catalog OEM into live fleet population (still Dell/HPE primary)
  Live fleet: Dell, HPE, Lenovo, Supermicro, Cisco, Gigabyte (+ Dell/Extreme switches)

## Phase 3 — Network & storage

- [x] Switch CLI (Cisco / Arista / Juniper / Spectrum facades)
- [x] Packets counters, latency, BGP/OSPF/VLAN/LACP, ping/traceroute/iperf
- [x] Full cable catalog + damage/label/route/bend/replace
- [x] NVMe/SATA/SAS/U.2/E3.S + Ceph/ZFS/SAN/NAS facades
- [x] Deeper MPLS/EVPN config writers (show-level done)

## Phase 4 — Physics-lite & rack FRU

- [x] Mass, tipping risk, heat propagation, fan pressure (formulas)
- [x] Cage nuts, rails, blanking, PDU outlets, QR/warranty labels
- [x] Bus packet animation (PCIe/DDR/UPI/IF/NVLink)

## Phase 5 — Ops platform

- [x] Full ticketing: change/incident/problem/RCA + Cisco/NVIDIA
- [x] Grafana-style metrics panels (Prom/SNMP/Redfish/DCGM facades)
- [x] Guided training by role with feedback
- [x] Replayable event journal (session twin journal + LabSession.simulation_snapshot DB mirror + replay_twin_journal)

## Phase 6 — Compute platforms

- [x] Hypervisor ops (ESXi/KVM/Proxmox) create/migrate/snapshot
- [x] K8s + GPU operator + Slurm/Ray/CUDA/MIG facades
- UI: Burn-in / Staging rooms → ComputeAiPanel

## Phase 7 — Optional 3D (product gate)

- [x] Three.js + R3F scene only if explicitly approved
- [x] Rapier constraints for cables/racks
- [x] LOD / InstancedMesh / BVH for 60 FPS
  Data hall **2D | 3D** toggle; 3D lazy-loads `DatacenterTwin3D` (R3F + Rapier).
  CSS pseudo-isometric floor remains the default fallback.
  Motions: camera intro, staggered rack rise, door open, LED/fan pulse, cable packets, airflow particles.

---

## Spec document index (expand later)

1. Executive Vision · 2. PRD · 3. Functional · 4. NFR · 5. Architecture · …
60. Appendices (catalogs, protocols, standards)

Each numbered section from the commercial Omniverse-class prompt maps into Phases 1–7 above.
Do **not** attempt a single mega-prompt implementation; execute by phase commits.
