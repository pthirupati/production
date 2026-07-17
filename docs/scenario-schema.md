# Scenario authoring schema (Phase 3.1)

Learner-facing labs are defined as `scenarios/<technology>/<slug>/scenario.yaml`.
Every lab session owns its own **Lab Servers** — there is no platform-global host.

## Required fields

| Field | Purpose |
|---|---|
| `title` | Specific ticket-style title (concrete resource names) |
| `slug` | Unique id |
| `technology` | Tech pack slug |
| `description` | Company ticket prose with CONTEXT / ENVIRONMENT / OBJECTIVE (+ IMPACT recommended) |
| `objectives` | ≥2 concrete acceptance steps |
| `hints` | ≥3 progressive hints with non-decreasing `cost` (0 → near-answer) |

## Strongly recommended (required for hero labs)

| Field | Purpose |
|---|---|
| `consoles` | List of tools to open (`terminal`, `vmware`, `aws`, `commvault`, `datacenter`, `soc`, …) |
| `lab_servers` | Scenario-scoped hosts the terminal/consoles share |
| `summary` | One-line outcome |
| `what_you_will_learn` | Skill bullets |
| `environment` | Nodes / credentials for the ticket |
| `tasks[].validation` | Machine-checkable check (usually `check.sh`) |

### `lab_servers` shape

```yaml
lab_servers:
  - id: primary
    role: primary
    hostname: db01
    persona: linux          # linux|windows|gpu|kubernetes|…
    appears_in: [terminal, vmware, commvault]
  - id: esxi-host
    role: hypervisor
    hostname: esxi-01
    persona: baremetal
    physical_location: { room: "Data Hall A", rack: "R12", u_position: 10 }
    appears_in: [vmware, datacenter]
```

Cross-tech means multiple consoles in **this** scenario share these Lab Servers.
AWS EC2 never appears in a physical rack; racked servers never appear as EC2.

## Banned learner-facing words

Do not use in `title`, `description`, `hints`, `objectives`, `summary`, etc.:

Simulation, Simulator, Simulated, Demo, Mock, Fake, Practice Environment

Internal fields (`lab_mode: simulation`, code, tests, docs) may keep those terms.

## Linter

```bash
python scripts/lint_scenarios.py --strict-heroes
python scripts/lint_scenarios.py --all --max-failures 999   # report-only catalog sweep
```
