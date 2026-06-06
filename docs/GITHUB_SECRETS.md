# GitHub Secrets & Production Environment

FixitLab **does not store secrets in git**. Workflows inject the full production `.env` from GitHub.

## One workflow — everything automated

**GitHub → Actions → FixitLab Production → Run workflow**

**Manual only** — push to `main` does **not** run this workflow. Use **Run workflow** in GitHub Actions.

| Action | When to use | What runs automatically |
|--------|-------------|-------------------------|
| **launch** | First time or full rebuild | Optional create server → GitHub secrets → GoDaddy DNS → tests → **deploy & start app** → health |
| **deploy** | Day-to-day updates | Tests → **deploy & start app** → health + E2E verify |
| **stop** | Pause platform | **Stop** containers (database volume kept) |

Pipeline options when running workflow:
- **build_scenarios** — rebuild all lab Docker images (required for labs to start)
- **run_e2e** — post-deploy health, scenario image check, sample lab provisioning, full API E2E

After E2E tests finish, `scripts/cleanup-test-data.py` automatically removes test users (`@fixitlab-test.local`), lab sessions, Jira tickets, community threads, and containers. Set `E2E_SKIP_CLEANUP=1` on the server to disable.

E2E coverage (`scripts/e2e_tab_coverage.py`) tests every main app tab, admin tab, lab runner options, billing, community actions, and per-technology Jira/scenario flows.

Pull requests run **CI Tests** only (no deploy).

### Launch (brand-new server)

1. Action: **launch**
2. ☑ **Create server**
3. ☑ **Run tests** (recommended)
4. Run workflow

No manual steps: droplet, bootstrap, `PROD_HOST`, `PRODUCTION_ENV_B64`, GoDaddy A record, clone, Docker, migrations, scenarios, SSL.

### Deploy (server already running)

1. Action: **deploy**
2. Run workflow

### Stop

1. Action: **stop**
2. Run workflow

## Required GitHub secrets (production environment)

| Secret | Purpose |
|--------|---------|
| `PRODUCTION_ENV_B64` | Full env file (base64) — Jira, OAuth, DO token, GoDaddy keys, etc. |
| `PROD_SSH_KEY` | SSH private key for `root@` server |
| `PROD_USER` | `root` |
| `PROD_HOST` | Auto-set when **launch + create server**; required for deploy/stop otherwise |

Optional: `DO_API_TOKEN` if not already inside `PRODUCTION_ENV_B64`.

**GoDaddy DNS** (inside `PRODUCTION_ENV_B64`):

```env
GODADDY_API_KEY=...
GODADDY_API_SECRET=...
GODADDY_DOMAIN=fixitlab.in
```

## One-time local setup

```bash
cp env.production.example deploy/production.env
# Edit deploy/production.env — fill ALL sections
./scripts/upload-secrets-to-github.sh   # once, after gh auth login
```

Re-run upload **only** when you change `deploy/production.env` locally (new API keys, passwords, etc.).  
**Not** needed for normal deploy/launch/stop — the workflow uses GitHub secrets already stored.

**You never push env files to git** — only `./scripts/upload-secrets-to-github.sh` once after editing `deploy/production.env`.

## How secrets reach the server

```
GitHub production secrets
  PRODUCTION_ENV_B64  →  decoded on server  →  /opt/fixitlab/.env.production
  PROD_HOST / PROD_SSH_KEY  →  SSH deploy
```

On deploy, `scripts/sync-production-env.sh` writes `.env.production` before Docker starts.

## Security notes

- `deploy/production.env` is **gitignored** — never commit it.
- CI runs `scripts/check-no-secrets-in-git.sh` on every test run.
- Rotate any token that was ever committed to git history.

See also: [JIRA_SETUP.md](JIRA_SETUP.md), [DNS_AND_SSL.md](DNS_AND_SSL.md)
