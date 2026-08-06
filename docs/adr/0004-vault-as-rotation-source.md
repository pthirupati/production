# 0004 — Vault is a rotation source, not a runtime dependency

**Status:** Accepted
**Written:** 2026-08 (retrospectively, after an outage that made the distinction
concrete)

## Context

HashiCorp Vault runs on D1 (edge) and injects secrets at Django startup via AppRole.
The backend runs on D2 (app).

An incident made the coupling visible: Vault sealed, and interview and auth endpoints
returned 500s. The platform was treating a secret *source* as a runtime dependency,
so a sealed Vault took down request paths that already had every secret they needed
in memory.

## Decision

Vault is authoritative at **load time only**. Once the process has booted, its
secrets are in memory and Vault being unreachable is not an error.

Concretely:

- secrets are loaded at startup, with a fallback to the rendered/baked environment;
- `/api/health/ready/` reports Vault as an **informational sub-status**. A sealed or
  unreachable Vault yields `degraded`, not `error`, and the node keeps serving;
- a genuinely missing secret prevents boot, so it cannot be missed silently.

## Consequences

- A sealed Vault is now a rotation outage, not a platform outage.
- Readiness stays honest: it names Vault as degraded rather than hiding it, which is
  why the earlier incident was diagnosable at all. This is the pattern later applied
  to Redis, the broker and Docker (Z5-10).
- Secrets live in process memory for the process lifetime. Rotation therefore
  requires a restart — accepted, because the alternative is re-reading Vault on the
  request path.
- Someone reading only the Vault integration could assume it is required. This ADR
  exists largely to prevent that assumption being re-introduced.

## Alternatives rejected

- **Vault as a hard dependency.** Correct-looking and operationally worse: it makes
  the secret store a tier-1 availability dependency of the whole platform.
- **No Vault, env vars only.** Simpler, and gives up managed rotation and audit.
- **Vault Agent sidecar.** Better long-term answer for rotation-without-restart;
  rejected for now as a fourth moving part on a two-vCPU box.
