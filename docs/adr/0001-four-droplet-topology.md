# 0001 — Four-droplet topology (edge / app / data / labs)

**Status:** Accepted
**Written:** 2026-08 (retrospectively — the topology predates this record)

## Context

FixitLab runs untrusted code. A lab is a container the learner has root inside, by
design, and the whole product is "here is a broken system, fix it". That single
fact drives the architecture more than scale does.

At the same time this is a small business: ~$192/mo of fixed infrastructure, one
maintainer, no on-call rotation.

## Decision

Four DigitalOcean droplets on a private VPC, each `s-2vcpu-8gb`:

- **D1 edge** — nginx, TLS termination, Vault. The only public surface.
- **D2 app** — Django/uvicorn, Celery workers.
- **D3 data** — PostgreSQL and pgBouncer. No public inbound.
- **D4 labs** — the Docker daemon that runs learner containers.

Provisioned by `doctl` from `production.yml`. Terraform exists in the repo and is
**dead code** — it is not the deploy path.

## Consequences

- The blast radius of a lab escape stops at D4. It has no database credentials and
  no public inbound; reaching customer data requires a second pivot across the VPC.
- Lab load cannot starve the app. A learner running `stress --cpu 8` costs D4, not
  the checkout page.
- D3 is a single point of failure with no read replica. Accepted deliberately: a
  replica doubles the data-tier cost for a business this size, and the actual
  exposure is restore time, which is tracked separately (Z5-8).
- Four boxes billed 24/7 regardless of load. D4 in particular is idle most of the
  time — this is the largest single line of fixed cost and is revisited in Z5-19.
- Deploys are multi-host and therefore slower and more failure-prone than a single
  box. `production.yml` carries the complexity so a human does not have to.

## Alternatives rejected

- **Single droplet.** Cheapest and simplest, and unacceptable: learner containers
  would share a kernel and a network with the database.
- **Kubernetes.** Solves scheduling problems this platform does not have yet, and
  adds a control plane that one maintainer would be on the hook for.
- **Managed Postgres.** Genuinely tempting and still open. Rejected on cost at this
  stage, not on principle; it would remove the D3 SPOF outright.
