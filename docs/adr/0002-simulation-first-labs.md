# 0002 — Simulation-first lab provisioning

**Status:** Accepted
**Written:** 2026-08 (retrospectively)

## Context

A hands-on lab platform's unit economics are decided by what a single lab costs to
run. Real containers cost RAM, disk, provisioning latency and a hard concurrency
ceiling — measured at roughly 13 concurrent labs on D4.

But the catalog spans ~7,280 scenarios across 40+ technologies, and most of them do
not need a real machine. "Diagnose why nginx returns 502" needs a filesystem, a
process table and a config file that can be wrong. It does not need a kernel.

## Decision

Two provisioning paths, chosen per scenario:

- **Simulation** (`UnifiedSimulationEngine`) — an in-process model of a filesystem,
  services and command behaviour. Starts instantly, costs almost nothing.
- **Real containers** — Docker on D4, for scenarios where the fidelity genuinely
  matters.

`simulation_type` on the scenario decides. Grading runs through the same validator
either way, which is what keeps the two paths honest.

## Consequences

- Most labs start instantly and cost nothing, so the free tier is viable and the
  concurrency cap is reached far less often.
- **The simulator must be believable or the product is a lie.** A learner who
  discovers a command is faked loses trust in every lab they have completed. This
  is the reason for the depth work throughout the audit, and for
  `scan_grader_integrity.py` gating fail-open graders in CI.
- Simulation state lived in process memory, which was invisible until it wasn't:
  four uvicorn workers meant four copies and lost state across requests (Z5-1).
  State belonging outside process memory is a direct consequence of this decision.
- Two provisioning paths means two failure modes, two sets of tests, and a real
  risk of them drifting.

## Alternatives rejected

- **Real containers for everything.** Honest and unaffordable: 7,280 scenarios
  against a 13-lab ceiling.
- **Simulation for everything.** Loses the scenarios where fidelity is the point —
  kernel behaviour, real networking, actual package managers.
- **Buy a sandbox provider.** Removes the cost problem and the differentiation with
  it; the simulator depth *is* the product.
