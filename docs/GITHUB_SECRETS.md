# GitHub Secrets & Production Environment

FixitLab **does not store secrets in git**. Workflows inject the full production `.env` from GitHub.

## How it works

```
GitHub (production environment secrets)
  PRODUCTION_ENV_B64  →  decoded on server  →  /opt/fixitlab/.env.production
  PROD_HOST / PROD_USER / PROD_SSH_KEY     →  SSH deploy
```

On every **Platform Start** or **CI/CD deploy**, `scripts/sync-production-env.sh` writes `.env.production` before Docker starts.

## Updating production host (new droplet / IP change)

After creating or replacing the DO droplet:

```bash
./scripts/create-production-droplet.sh              # creates droplet + auto-updates files + commit
./scripts/create-production-droplet.sh --sync-only  # droplet already exists — sync only
./scripts/update-production-host.sh --from-doctl fixitlab-prod --commit --push-secrets
```

**Auto-updated (local, gitignored):** `deploy/production.env`, `.env.production` — includes `PROD_HOST`, `DO_PROTECTED_DROPLET_IDS`, `DJANGO_ALLOWED_HOSTS`.

**Auto-updated + committed (no secrets):** `infra/digitalocean/production.json`, docs, `env.production.example`.

**GitHub secrets:** use `--push-secrets` or run `./scripts/upload-secrets-to-github.sh` after `gh auth login`.

## One-time setup (5 minutes)

### 1. Create local env file

```bash
cp env.production.example deploy/production.env
# Edit deploy/production.env — fill EVERY section, especially Jira:
```

Required for Jira (`JIRA_ENABLED=true`):

| Variable | Example |
|----------|---------|
| `JIRA_BASE_URL` | `https://fixitlab.atlassian.net` |
| `JIRA_EMAIL` | your Atlassian account email |
| `JIRA_API_TOKEN` | from [Atlassian API tokens](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `JIRA_PROJECT_KEY` | `KAN` |
| `JIRA_WEBHOOK_SECRET` | long random string (same as Jira webhook URL `?secret=`) |

See [JIRA_SETUP.md](JIRA_SETUP.md).

### 2. Upload to GitHub

```bash
gh auth login
./scripts/upload-secrets-to-github.sh
```

This sets **Environment secrets** on the `production` environment:

| Secret | Purpose |
|--------|---------|
| `PRODUCTION_ENV_B64` | Base64 of entire `deploy/production.env` |
| `PROD_HOST` | Server IP (`64.227.175.89`) |
| `PROD_USER` | SSH user (`root`) |
| `PROD_SSH_KEY` | SSH private key (full PEM) |

### 3. Create GitHub Environment

**Settings → Environments → New environment → `production`**

(The upload script creates it if missing.)

### 4. Deploy

```bash
git push origin main
# or Actions → Platform Start → Run workflow
```

## Updating secrets later

Edit `deploy/production.env` locally, then:

```bash
./scripts/upload-secrets-to-github.sh
```

Re-run **Platform Start** to apply on the server.

## Manual alternative (no GitHub secrets)

On the server only:

```bash
scp deploy/production.env root@64.227.175.89:/opt/fixitlab/.env.production
ssh root@64.227.175.89 'chmod 600 /opt/fixitlab/.env.production && cd /opt/fixitlab && ./scripts/platform-start.sh'
```

## Verify Jira on server

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
from django.conf import settings
print('JIRA_ENABLED', settings.JIRA_ENABLED)
print('JIRA_BASE_URL', settings.JIRA_BASE_URL)
print('JIRA_PROJECT_KEY', settings.JIRA_PROJECT_KEY)
print('API token set', bool(settings.JIRA_API_TOKEN))
"
```

## Security notes

- `deploy/production.env` and `.env.production` are **gitignored** — never commit them.
- Use `env.production.example` as the template (no real secrets).
- CI runs `scripts/check-no-secrets-in-git.sh` on every push to block accidental token commits.
- Store production env only in GitHub **Environment secret** `PRODUCTION_ENV_B64` (see `./scripts/upload-secrets-to-github.sh`).
- **If a token was ever committed** (e.g. DigitalOcean `dop_v1_*`): GitHub may revoke it automatically. Create a new token, rotate all exposed secrets (`DJANGO_SECRET_KEY`, DB passwords, `JIRA_API_TOKEN`, etc.), update `PRODUCTION_ENV_B64`, and redeploy. Old commits may still contain secrets in git history — consider `git filter-repo` or BFG if the repo is public.
