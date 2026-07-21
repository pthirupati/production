# Datacenter Digital Twin — Spec Index (FixitLab)

This index **absorbs** the commercial Omniverse-class / V2 exhaustive wishlist
(requirements 1–22, motherboard/firmware depth, and the `:3080` Three.js monorepo
prompt) into FixitLab’s **Lab Environment** architecture.

## Non-negotiable product constraints

1. Implementation stays inside FixitLab (`datacenter_engine` + React LabRunner overlays).
2. Learner language: Lab Environment / Lab Server / Hosted as — never “Simulation/Sandbox/Mock”.
3. A separate Three.js + Rapier monorepo on `:3080` is **out of scope** unless product
   explicitly pivots; Phase 7 already provides an in-lab R3F twin with 2D fallback.
4. Facades model operational workflows and state — not photoreal screw meshes or real OS installs.
5. Target: interactive, configurable, removable, replaceable, monitorable lifecycle tasks at
   usable FPS (LOD / InstancedMesh / BVH where 3D is used).

## Requirement map (1–22)

| # | Theme | FixitLab surface | Depth status |
|---|--------|------------------|--------------|
| 1 | Real physics | P4 formulas + P7 Rapier (tipping, cable bits, gravity) | Facade + lite Rapier |
| 2 | Entire campus | Campus rooms + plant assets + 3D CRAC/PDU | Rooms live; photoreal campus deferred |
| 3 | Complete rack FRU | Cage nuts, rails, blanking, PDU outlets, QR/labels | Not every screw |
| 4 | Server OEMs | Fleet profiles + vendor BOM/BMC/RAID | Live multi-OEM |
| 5 | CPU generations | Catalog + motherboard die maps | Catalog + facade |
| 6 | GPU systems | Catalog + gpu_node / AI panels | Catalog + facade |
| 7 | Motherboard + buses | MotherboardPanel + BusAnimPanel + service ops | Interactive facade |
| 8 | Cables | Catalog + cable/label/route/bend | Facade |
| 9 | Switches | Multi-vendor CLI + blink/counters | Facade |
| 10 | Console / BIOS / BMC | Serial + BIOS + iDRAC/iLO/IPMI panels | Facade |
| 11 | Storage | NVMe/SAS + Ceph/ZFS/SAN/NAS | Facade |
| 12 | Networking | BGP/OSPF/VXLAN/EVPN/MPLS + tools | Facade |
| 13 | Hypervisors | Burn-in/Staging ComputeAiPanel | Facade |
| 14 | Kubernetes | K8s GPU operator / Helm / MIG | Facade |
| 15 | AI infra | Slurm/Ray/CUDA/NCCL/DCGM/MIG | Facade |
| 16 | Monitoring | NOC Prom-style + PUE | Facade |
| 17 | Ticketing / RMA | Multi-OEM + ops tickets | Facade |
| 18 | Inventory / CMDB | Asset/warranty/EOS records | Facade |
| 19 | Failure inject | Presets + cooling→BMC thermal | Facade |
| 20 | Hardware replacement | Service mode + FRU drawers | Facade |
| 21 | Training mode | Guided roles + feedback | Facade |
| 22 | Digital twin persistence | Journal + LabSession snapshot + replay | Facade |

## Motherboard / RAID / BMC depth (this tranche)

Interactive Lab Environment surfaces (not static 3D PCB):

- **Motherboard:** selectable CPU/DIMM/PCIe/chips; cover; paste; remove/install CPU; reseat DIMM; PCIe remove/populate; bus packet animation (PCIe/DDR/UPI/IF/NVLink/SMBus/SATA).
- **RAID:** PERC/Smart Array/LSI-style create/delete/rebuild/patrol/CC/foreign import; hot-spare assign; expand VD; initialize; levels 0/1/5/6/10/50/60.
- **BMC:** iDRAC/iLO/XCC/IPMI/IMC generations; power/NMI/KVM/virtual media; sensors/SEL; firmware targets; diagnostics suites; network/RBAC.

## V2 monorepo prompt (indexed, not greenfield)

The exhaustive `datacenter-3d/` Vite+Express+SQLite structure, raised-floor tile grid,
exploded server view, and photoreal PCB component list remain **reference architecture**
for future optional Phase 7+ depth. They are **not** to be scaffolded as a parallel app
unless product approves a pivot.

## Spec document outline (expand as needed)

1 Executive Vision · 2 PRD · 3 Functional · 4 NFR · 5 Architecture · …
17 Motherboards · 22 RAID · 23 BIOS · 24 BMC · 42 Digital Twin · 58 Roadmap · 60 Appendices

Authoritative phased backlog: `docs/datacenter-twin-roadmap.md`.
