# HashiCorp Vault for FixitLab secrets

FixitLab can store **all production secrets** in [HashiCorp Vault](https://www.vaultproject.io/) instead of a plaintext `.env.production` on disk or a large `PRODUCTION_ENV_B64` GitHub secret.

## Architecture

```
deploy/production.env     (your Mac only — gitignored, master copy for edits)
        │
        ├── ./scripts/vault/bootstrap.sh     → Vault KV (encrypted at rest)
        ├── ./scripts/vault/seed-from-env.sh → update Vault after env edits
        │
        └── ./scripts/upload-vault-secrets-to-github.sh
                  → GitHub: VAULT_UNSEAL_KEY, VAULT_ROLE_ID, VAULT_SECRET_ID

Production server:
  docker-compose.vault.yml  →  Vault on 127.0.0.1:8200 (not public)
  deploy / platform-start   →  render .env.production from Vault (AppRole)
  docker compose            →  containers still use env_file (ephemeral render)
```

**What stays on GitHub after migration:** small Vault credentials only — not the full env file.

**What stays on server:** Vault data volume (`fixitlab_vault_data`) + briefly rendered `.env.production` at container start (required by Docker Compose today).

---

## Step 1 — Bootstrap Vault on the production server

SSH to the server (or run from your Mac against the server repo after copying `deploy/production.env`):

```bash
cd /opt/fixitlab   # or local fixitlab clone

# Start Vault container
docker compose -f docker-compose.vault.yml up -d

# One-time init + seed from your env file
chmod +x scripts/vault/*.sh scripts/vault/env-kv-helper.py
./scripts/vault/bootstrap.sh deploy/production.env
```

This creates (gitignored, **back up offline**):

| File | Contents |
|------|----------|
| `deploy/vault-init.json` | Unseal key + root token |
| `deploy/vault-approle.env` | AppRole ID/secret for the app |

Add to `deploy/production.env` before seeding (or re-seed after):

```env
VAULT_ENABLED=true
```

Re-seed if you add it later:

```bash
./scripts/vault/seed-from-env.sh deploy/production.env
```

---

## Step 2 — Upload Vault creds to GitHub

From your Mac:

```bash
./scripts/upload-vault-secrets-to-github.sh
```

Uploads to **Settings → Environments → production**:

- `VAULT_ENABLED=true`
- `VAULT_UNSEAL_KEY`
- `VAULT_ROLE_ID`
- `VAULT_SECRET_ID`

---

## Step 3 — Verify render + restart

On the server:

```bash
export VAULT_ENABLED=true
# load approle from file or env
source deploy/vault-approle.env

./scripts/vault/render-env.sh
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend celery_worker
```

Send admin test email / check health.

---

## Step 4 — Optional: remove full env from GitHub

After Vault works in production:

1. Confirm deploy workflow succeeds with Vault secrets only.
2. Delete GitHub secret `PRODUCTION_ENV_B64` (keep offline backup of `deploy/production.env` on your Mac).
3. Optionally remove `/opt/fixitlab/.env.production` after each deploy — it is re-rendered on every `platform-start.sh`.

---

## Day-to-day: change a secret

**Mac (recommended one-liner):**

```bash
./scripts/vault/push-env-and-render.sh deploy/production.env
```

Or manually:

1. Edit **`deploy/production.env`** on your Mac (never commit).
2. Push to Vault:

```bash
./scripts/vault/seed-from-env.sh deploy/production.env
```

3. On server (or via deploy workflow):

```bash
./scripts/vault/render-env.sh
docker compose -f docker-compose.prod.yml --env-file .env.production up -d backend celery_worker
```

---

## Commands reference

| Command | Purpose |
|---------|---------|
| `./scripts/vault/start.sh` | Start Vault container |
| `./scripts/vault/status.sh` | Check Vault sealed/unsealed |
| `./scripts/vault/unseal.sh` | Unseal after reboot |
| `./scripts/vault/bootstrap.sh` | First-time setup |
| `./scripts/vault/render-env.sh` | Vault → `.env.production` |
| `./scripts/vault/seed-from-env.sh` | `.env` → Vault |
| `./scripts/vault/push-env-and-render.sh` | Local edit → Vault → render |
| `./scripts/vault/check-metrics.sh` | Verify Prometheus metrics on :8201 |

**Metrics:** Vault exposes Prometheus metrics on `127.0.0.1:8201` inside the container (`/v1/sys/metrics?format=prometheus`). Post-deploy verification runs `check-metrics.sh` when Vault is running.

**CI auto-sync:** When `PRODUCTION_ENV_B64` is set and Vault is initialized on the server, `sync-production-env.sh` seeds Vault KV before rendering so deploy always uses the latest secrets.

---

## After server reboot

Vault starts sealed. Deploy workflow (or `platform-start.sh`) calls `unseal.sh` automatically when `VAULT_UNSEAL_KEY` is set.

Manual unseal:

```bash
export VAULT_UNSEAL_KEY='...'   # from deploy/vault-init.json or GitHub secret
./scripts/vault/unseal.sh
./scripts/vault/render-env.sh
```

---

## Security notes

- Vault listens on **127.0.0.1:8200 only** — not exposed to the internet.
- Use **AppRole** for the app; store root token offline only.
- Back up `deploy/vault-init.json` encrypted — losing unseal key + data volume means secrets are gone.
- Rendered `.env.production` is still plaintext for Docker; Vault removes the need to **store** secrets in git/GitHub/long-lived server copies.

---

## CI failure fix (run 27508396403)

Deploy succeeded; **E2E failed** because the backend stopped after the long all-scenario lab test (~40+ Docker labs). `ci-post-deploy-verify.sh` now calls `ensure-backend-healthy.sh` to restart the backend before the API E2E suite.

Re-run **FixitLab Production → deploy** with `run_e2e=true`.
