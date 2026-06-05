# Push and Run — FixitLab Production

## One-time GitHub setup

**Full guide:** [docs/GITHUB_SECRETS.md](GITHUB_SECRETS.md)

```bash
# 1. Fill local env (includes Jira keys)
cp env.production.example deploy/production.env
# edit deploy/production.env

# 2. Upload to GitHub Environment "production"
gh auth login
./scripts/upload-secrets-to-github.sh
```

This creates these **Environment secrets** (Settings → Environments → production):

| Secret | Purpose |
|--------|---------|
| `PRODUCTION_ENV_B64` | Full `.env` (Jira, OAuth, DB, email, everything) |
| `PROD_HOST` | `64.227.175.89` |
| `PROD_USER` | `root` |
| `PROD_SSH_KEY` | SSH private key to droplet |

**Do not commit `deploy/production.env`** — it is gitignored.

## DNS (required)

Point `fixitlab.in` and `www.fixitlab.in` → **`64.227.175.89`** only (remove parking IPs).

## Every deploy

```bash
git push origin main
```

Or **Actions → Platform Start → Run workflow**

## What happens on deploy

1. `PRODUCTION_ENV_B64` decoded → `.env.production` on server
2. SSL certificates (Let's Encrypt) if missing
3. `docker compose -f docker-compose.prod.yml up -d --build`
4. Migrations + scenario seed + Docker image build

## Verify

- https://fixitlab.in/
- https://fixitlab.in/api/health/ (internal only via gateway)
- Start lab → Jira ticket `KAN-xxx` when `JIRA_ENABLED=true`

## Update env (e.g. add Razorpay keys)

Edit `deploy/production.env` → run `./scripts/upload-secrets-to-github.sh` → Platform Start
