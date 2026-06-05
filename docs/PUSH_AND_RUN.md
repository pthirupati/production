# Push and Run — FixitLab Production

## One-time GitHub setup (3 secrets)

**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `PROD_HOST` | `139.59.58.8` |
| `PROD_USER` | `root` (or your SSH user) |
| `PROD_SSH_KEY` | Full private SSH key to the droplet |

**Settings → Environments →** create environment named `production`.

## DNS (required)

Point `fixitlab.in` and `www.fixitlab.in` → **`139.59.58.8`**

No manual server setup needed — the workflow clones to `/opt/fixitlab` on first run.

## Every deploy

```bash
git push origin main
```

This runs **CI/CD Production** (tests + deploy).

Or manually: **Actions → Platform Start → Run workflow**

## What happens on deploy

1. `deploy/production.env` → copied to `.env.production` on server
2. `docker compose -f docker-compose.prod.yml up -d --build`
3. Migrations + scenario seed
4. Scenario Docker images built (first run takes 30–60 min)

## Stop platform

**Actions → Platform Stop → Run workflow** (keeps database volume)

## Verify

- https://fixitlab.in/api/health/
- Login → start free lab `broken-nginx`
- Paid tech: demo payment flow works until Razorpay keys are added
- Jira: ticket `KAN-xxx` on lab start
