# Scenario-scoped Lab Servers

## Decision (locked)

**Do not** maintain one global server shared across the whole platform.

Every **lab session** (one learner attempt of one scenario) owns its own infrastructure graph:

```
LabSession (scenario slug + learner)
  └── LabServer[]   ← ServerIdentity records keyed by session_id
        ├── primary OS (terminal always attaches here)
        ├── optional peers (web2, db, ESXi host, …) for multi-host / cross-tech
        └── optional physical_location / bmc when the scenario is on-prem
```

| Scenario kind | What the terminal is | Where it also appears |
|---|---|---|
| Linux / GPU / Ansible | That Linux host | Only that lab session |
| VMware / cross-tech VM | Guest OS of the seeded VM | vCenter inventory for **this** session |
| AWS | Primary EC2 guest | AWS console for **this** session — never a physical rack |
| Azure / GCP / OpenStack *(future)* | Cloud VM of that scenario | That cloud console only |
| Datacenter / MAAS / bare metal | OS on the racked server | Rack elevation + BMC for **this** session |
| Windows | Windows Server OS | Windows Server Manager / SCCM for **this** session |
| Cross-tech (e.g. VMware + Commvault) | Same LabServer(s) | Both consoles in the same session |

Cross-tech means **within one scenario**: the same LabServer(s) are visible from every console that scenario opens. It does **not** mean one EC2 that also lives in every VMware lab on the platform.

## Cost rule

All LabServers are in-memory / facade / future free emulators. No real cloud spend, no real GPUs, no vendor entitlements by default.

## Implementation

- Registry: `apps.labs.provisioner.simulation.server_identity` (cache key includes `session_id`)
- Hardware bridges: `vmware_bridge`, `aws_bridge` (session-scoped)
- Provision seed: `seed_scenario_lab_servers()` on lab start
