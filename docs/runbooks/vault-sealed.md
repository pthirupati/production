# Vault sealed or unreachable

## What you will see

Auth and interview endpoints returning 500 while the rest of the site looks fine.
This has happened before and presented exactly this way.

## Confirm it

```bash
curl -s https://fixitlab.in/api/health/ready/ | jq '.checks.vault'
```

`status` will be `unavailable` or `degraded`. The node itself stays `ok`/`degraded`
and keeps serving — that is deliberate (ADR 0004).

## What still works

Everything already running. Secrets were loaded into memory at boot, so a sealed
Vault does not remove them from a process that is already up. What breaks is any
process that **restarts** while Vault is sealed and cannot find its secrets in the
baked environment either.

## Fix

Unseal Vault on D1, then restart the backend on D2 so it re-reads cleanly:

```bash
# On D1
vault operator unseal   # x3, with the unseal keys

# On D2
docker compose -f docker-compose.app.yml restart backend celery_worker celery_beat
```

## Why it behaves this way

Vault is a **rotation source, not a runtime dependency** (ADR 0004). Readiness
reports it as informational precisely so a sealed Vault is a rotation outage rather
than a platform outage — and so that this is diagnosable at all, which is what made
the original incident tractable.

**Do not** "fix" this by making readiness fail on Vault. That would take healthy
nodes out of rotation for a condition they are designed to survive.
