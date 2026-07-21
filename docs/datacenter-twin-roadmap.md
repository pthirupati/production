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

**Absorbs** the V2 exhaustive Omniverse-class prompt (requirements 1–22, motherboard/firmware
depth, campus plant list, every OEM/GPU/cable catalog). Delivery is **phased Lab Environment
facades inside FixitLab**, not a separate `:3080` Three.js monorepo. See
`docs/datacenter-twin-spec-index.md`.

---

## Requirement → phase map

| # | Requirement | Phase | Status |
|---|-------------|-------|--------|
| 1 | Real physics (Rapier/Cannon) | P4 lite → P7 Rapier | [x] |
| 2 | Entire campus building | P1 | [x] campus rooms + plant assets |
| 3 | Complete rack FRU | P4 → P9 | [x] dense labels/QR/cage nuts (not every screw mesh) |
| 4 | Every server OEM | P2 | [x] multi-OEM live fleet + vendor BOM |
| 5 | Every CPU generation | P2 | [~] catalog + live die from motherboard map |
| 6 | GPU systems (DGX/HGX/…) | P2 catalog → P6 AI | [~] catalog + gpu_node / H100 BOM |
| 7 | Complete motherboard + bus anim | P1–P8 | [x] interactive FRU + bus pulse |
| 8 | Every cable type + ops | P1 plug → P3 catalog | [~] |
| 9 | Real switches + CLI | P3 | [x] multi-vendor CLI + MPLS/EVPN |
| 10 | Console / BIOS / BMC / PXE | P1–P9 | [x] BMC gens + MAAS/PXE |
| 11 | Real storage stack | P3 | [x] facade stack (NVMe/Ceph/ZFS/SAN/NAS) |
| 12 | Networking simulation | P3 | [x] counters + tools + protocol writers |
| 13 | Hypervisors | P6 | [x] ESXi/KVM create/migrate/snapshot |
| 14 | Kubernetes | P6 | [x] GPU operator / Helm / MIG facades |
| 15 | AI infrastructure | P6 | [x] Slurm / Ray / CUDA / inference scale |
| 16 | Monitoring dashboards | P5 | [x] Prom-style + NOC panels |
| 17 | Ticketing / RMA | P1–P5 | [x] multi-OEM + ops tickets |
| 18 | Inventory / CMDB | P2 | [x] asset/warranty/EOS records |
| 19 | Troubleshooting / failure inject | P2 | [x] presets + cooling→BMC thermal |
| 20 | Hardware replacement / service mode | P2 | [x] |
| 21 | Interactive training roles | P5 | [x] guided scenarios + feedback |
| 22 | Digital twin persistence / replay | P5 | [x] journal + DB snapshot mirror |

Still intentionally shallow vs Omniverse: screw-level photoreal meshes, real VirtualBMC agents, full CFD liquid loops.

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
  Plant-linked: CRAC + PDU strips, thermal stress → airflow color, InstancedMesh U-slots + BVH picking.

## Phase 8 — Motherboard / RAID / BMC depth (Lab Environment)

- [x] Spec index absorbs V2 mega-prompt without greenfield monorepo
- [x] Motherboard: CPU remove/install, DIMM reseat, PCIe FRU, richer bus anim
- [x] RAID: hot-spare assign, expand VD, initialize, full level picker
- [x] BMC: generation switch (iDRAC/iLO/XCC/IPMI), KVM/virtual media/flash paths

## Phase 9 — Plant liquid cooling · dense FRU · MAAS/PXE

- [x] CDU / DLC manifolds / QD couplings + leak inject (Mechanical room)
- [x] Dense rack FRU: U labels, QR scan, cage nuts, baffle, ground torque
- [x] Server chassis label plates on CMDB
- [x] MAAS region + enlist/commission/deploy/PXE (Staging/Burn-in + server drawer)

## Phase 10 — Fire / env / optical / capacity / PdM

- [x] Fire suppression (VESDA/Novec) room ops + smoke inject
- [x] Environmental sensors (temp/humidity/leak/door) in NOC
- [x] Optical FEF/MMR/MPO trunks (fiber cut/repair, carriers, XC)
- [x] Capacity planning + predictive maintenance on NOC

## Phase 11 — DR / access / automation / reports

- [x] Utility→ATS→generator failover + site failover/failback + DR runbook
- [x] Security gate badge/biometrics/cameras/tailgate (gate + SOC)
- [x] Automation runbook catalog (incl. DR tabletop) + ops report generator

## Phase 12 — Gap closure (CAB, sustainability, plant depth)

- [x] Change CAB workflow + freeze gate on FRU/power/firmware actions
- [x] Sustainability: PUE + WUE + carbon (header + NOC panel)
- [x] Containment doors/curtains coupled to rack blanking → inlet/ΔP
- [x] Cable tray plant (fill %, ladder/basket/underfloor) in Cable/MMR rooms
- [x] Burn-in load bank + guest OS stages + release gate
- [x] SNMP walk / Redfish GET exporter depth + SOP/evidence pack
- [x] Live sensor tick (`live_tick`) + NOC auto-scrape (no Channels WS)
- [x] E2E lifecycle test: `backend/tests/test_datacenter_e2e_lifecycle.py`

Intentionally still deferred: photoreal meshes, real VirtualBMC, Django Channels WS push, full CFD.

---

## Spec document index (expand later)

1. Executive Vision · 2. PRD · 3. Functional · 4. NFR · 5. Architecture · …
60. Appendices (catalogs, protocols, standards)

Each numbered section from the commercial Omniverse-class prompt maps into Phases 1–7 above.
Do **not** attempt a single mega-prompt implementation; execute by phase commits.
