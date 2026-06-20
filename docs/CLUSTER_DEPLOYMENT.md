# FixitLab — Four-Droplet Cluster Deployment

This is an operator runbook for the **four-droplet** production topology. It only
covers how to run the workflow — all logic lives in the pipeline and scripts.

## Topology

| Droplet | Visibility | Tag | Services |
|---|---|---|---|
| **D1 Edge** | public | `fixitlab-edge` | gateway (nginx + SSL), certbot, frontend-prod, redis, rabbitmq, vault |
| **D2 App** | private | `fixitlab-app` | backend + celery workers/beat (VMware/IDE/devops sims run inside backend) |
| **D3 Data** | private | `fixitlab-db` | postgres + pgbouncer |
| **D4 Labs** | private | `fixitlab-labs` | docker engine + `fixitlab_labs` network + scenario images |

Region `blr1`, size `s-2vcpu-8gb-160gb-intel` (override with repo variables
`DO_REGION` / `DO_SIZE`). One VPC (`fixitlab-vpc`) joins all four droplets; cloud
firewalls lock the private ports to the specific peer droplet.

## Running the workflow

GitHub → Actions → **FixitLab Production** → Run workflow:

- **action**: `launch` (first time) or `deploy` (subsequent).
- **topology**: `four-droplet`.
- **create_server**: ignored by the four-droplet path (cluster always creates/discovers its own droplets).
- **wire_existing**: `true` to reuse droplets already tagged `fixitlab-edge/app/db/labs` (skips creation).
- **rotate_secrets**: `true` to rotate infra secrets this run (Django/DB/Redis/Rabbit/JWT/admin/webhooks). Never rotates the DO API token or SSH key.
- **credentials_email**: recipient for the post-deploy credential bundle (default `thirupathi.samu2018@gmail.com`).
- **build_scenarios**, **run_e2e**, **git_ref**, **technologies**, **skip_email**: same meaning as single-host.

When **topology = single** (the default) the pipeline behaves exactly as before —
the four-droplet jobs are skipped.

## Job graph (four-droplet)

```
create-cluster → bootstrap-cluster → vault-cluster → deploy-cluster → email-credentials
                                                          ↓
              verify-health-cluster · test-units-cluster · prepare-e2e-cluster → e2e-api/e2e-labs
                                                          ↓
                            cleanup-cluster (+ daily pg_dump cron) · summary-cluster
```

`create-cluster` runs: generate/rotate secrets → create or discover droplets (one
VPC + 4 tagged) → cloud firewalls → wire env with private IPs/broker URLs/remote
docker socket/Vault addr → D2→D4 labs SSH key → sync GitHub secrets → commit
`infra/digitalocean/cluster.json`.

## One-time GitHub setup

Environment **production** secrets:

| Secret | Purpose |
|---|---|
| `DO_API_TOKEN` | DigitalOcean API (or carried inside `PRODUCTION_ENV_B64`) |
| `PROD_SSH_KEY` | ed25519/RSA private key for `root` on all droplets |
| `PRODUCTION_ENV_B64` | base64 of the full `.env` template (OAuth/payment/Jira/business config preserved) |
| `PROD_USER` | usually `root` |
| `SENDGRID_API_KEY` | sending the credentials email |
| `GH_ADMIN_TOKEN` | **REQUIRED for four-droplet.** PAT with Environment `secrets: write` on this repo. The default `github.token` CANNOT write Environment secrets (HTTP 403), and the cluster persists `PROD_HOST` / `PROD_APP_HOST` / `PROD_DB_HOST` / `PROD_LABS_HOST` / `VAULT_*` as Environment secrets the bootstrap/deploy jobs read. A preflight step now aborts **before** creating any droplet if this token can't write secrets. (Single-droplet does not need it.) |
| `DO_PROTECTED_DROPLET_IDS` | (optional) droplet IDs the automation must never modify |

Repo **variables** (optional): `DO_REGION`, `DO_SIZE`, `CREDENTIALS_EMAIL_REQUIRED`
(`1` to fail the run if the credentials email can't be sent).

The pipeline writes back `PROD_HOST`, `PROD_APP_HOST`, `PROD_DB_HOST`,
`PROD_LABS_HOST`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`, `VAULT_UNSEAL_KEY`,
`VAULT_ENABLED`, and an updated `PRODUCTION_ENV_B64`.

## Notes

- All provisioning scripts honor `DRY_RUN=1` (print the doctl/ssh/openssl commands
  instead of running them). Secrets are masked with `::add-mask::` and never logged.
- `DO_API_TOKEN` is never placed in any email body or attachment.
- Private droplets are reached by SSH **ProxyJump** through the edge node.
- Daily Postgres backups land in `/var/backups/fixitlab` on D3 (7-day retention).
