# FixitLab Architecture & Deployment Guide

## Executive Summary

FixitLab is a **modular monolith** — Django backend + React frontend + Celery workers — deployed on **DigitalOcean droplets** using Docker Compose. Cloud lab scenarios run on **separate DO droplets** (not AWS). Jira Cloud provides realistic incident tracking. Razorpay handles INR payments with full audit trail.

**Recommended deployment:** Single platform droplet (Compose) + ephemeral lab droplets (API-provisioned). **Not Kubernetes** at current scale (<10k users).

---

## Architecture Diagram

```
                         ┌─────────────────────────────────────────┐
                         │           DigitalOcean Cloud             │
                         │                                          │
  Users ──HTTPS──► ┌─────┴──────┐                                    │
                   │  Platform   │  (Droplet: 4 vCPU / 8GB)         │
                   │  Droplet    │                                    │
                   │             │                                    │
                   │  Nginx ─────┼──► React SPA                      │
                   │     │       │                                    │
                   │     ├──► Django API (REST + WebSocket)          │
                   │     ├──► Celery workers (provision/cleanup)     │
                   │     ├──► PostgreSQL + Redis + RabbitMQ          │
                   │     └──► Docker socket (local lab containers)   │
                   └──────┬──────┘                                    │
                          │ DO API v2                                  │
                          ▼                                            │
                   ┌──────────────┐     SSH/WebSocket                 │
                   │ Lab Droplets │ ◄── per cloud scenario session    │
                   │ (ephemeral)  │     tagged fixitlab/session:{id}  │
                   └──────────────┘                                    │
                          │                                            │
                          ▼                                            │
                   ┌──────────────┐                                    │
                   │  Jira Cloud  │  tickets per user+scenario        │
                   └──────────────┘                                    │
                          │                                            │
                          ▼                                            │
                   ┌──────────────┐                                    │
                   │   Razorpay   │  technology subscriptions         │
                   └──────────────┘                                    │
                         └─────────────────────────────────────────┘
```

---

## Deployment Model Recommendation

| Option | Verdict | When to use |
|--------|---------|-------------|
| **Single droplet + Docker Compose** | ✅ **Recommended now** | <5k users, <50 concurrent labs |
| **2 droplets (app + DB)** | ✅ Stage2 / early prod | Separate Postgres for durability |
| **Microservices** | ❌ Not yet | Premature — adds ops cost without benefit |
| **Kubernetes (DOKS)** | ⚠️ Future | >10k users, multi-region, auto-scaling labs |
| **AWS EKS** | ❌ Deprecate | Replaced by DigitalOcean per your requirement |

### Why monolith on droplets (not K8s)?

1. **Team size & complexity** — One codebase, one deploy unit, easier debugging
2. **Lab provisioning** — Celery + DO API already handles async droplet lifecycle
3. **Cost** — A $48/mo droplet runs the full stack; K8s control plane alone costs more
4. **WebSocket terminals** — Nginx + Daphne on one host is battle-tested in prod-tested variant

### When to move to Kubernetes

- >100 concurrent cloud labs needing autoscaling workers
- Multi-region deployment
- Dedicated SRE team for cluster ops

---

## Environment Topology

| Environment | Branch | Host | Lab provider |
|-------------|--------|------|--------------|
| **Local dev** | any | `docker compose up` | Docker containers |
| **merge gate** | `main` (push) | GitHub runner, ephemeral | none — `E2E_SKIP_LAB=1` |
| **production** | `main` (deploy) | DO droplet (prod) | Docker + DO droplets |

There is no staging environment. The `merge-gate` job in
`.github/workflows/e2e-smoke.yml` boots a throwaway stack inside the CI runner
to smoke-test each merge before `production.yml` deploys it — see
[PRODUCTION_SETUP.md](PRODUCTION_SETUP.md) for what that does and does not cover.

---

## Component Breakdown

### Backend (Django 5 + DRF + Channels)

| App | Responsibility |
|-----|----------------|
| `public_api` | Scenarios, labs, bookmarks, progress |
| `labs` + provisioners | Docker / DO droplet lifecycle |
| `terminal` | WebSocket → docker exec or SSH |
| `billing` | Razorpay + Stripe + PaymentTransaction audit |
| `jira_integration` | Ticket create/reset/complete sync |
| `accounts` | JWT RS256, OAuth, OTP |

### Frontend (React + Vite + xterm.js)

- Lab runner with terminal reconnect (3600s nginx timeout)
- Jira ticket badge in lab top bar (links to Atlassian)
- Razorpay checkout for technology subscriptions

### Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local development |
| `docker-compose.prod.yml` | Production with TLS |
| `scripts/deploy.sh` | SSL + certbot + rolling deploy |
| `.github/workflows/production.yml` | Deploy to production + post-deploy E2E |
| `.github/workflows/e2e-smoke.yml` | Merge gate (ephemeral stack) + post-deploy smoke |
| `.github/ci/nginx-ephemeral.conf` | Same-origin gateway for the merge-gate stack |
| `infra/digitalocean/` | Droplet bootstrap scripts |

---

## Jira Integration Flow

```
User clicks "Start Lab"
    │
    ├─ First time for scenario → Create Jira ticket (FIXIT-xxx)
    │   Body includes: issue description, objectives, lab URL, scenario URL
    │
    ├─ Restart same scenario → Reset ticket (To Do → In Progress), increment run_count
    │
    ├─ Lab running → Jira status: "In Progress"
    │
    ├─ Validation passes → Jira status: "Done" + comment with score/time
    │
    └─ User stops lab → Jira status: "To Do" + comment
```

**Setup:** Create Jira Cloud project (e.g. `FIXIT`), generate API token, set env vars:

```env
JIRA_ENABLED=true
JIRA_BASE_URL=https://yourorg.atlassian.net
JIRA_EMAIL=bot@yourorg.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=FIXIT
```

Transition names must match your Jira workflow: `In Progress`, `To Do`, `Done`.

---

## Payment Flow (Razorpay)

```
Frontend → POST /api/billing/create-order/ (server-side price lookup)
         → Razorpay modal
         → POST /api/billing/verify-payment/ (HMAC signature check)
         → PaymentTransaction marked success
         → TechnologySubscription activated (payment_verified=true)
         → Webhook /api/billing/webhook/razorpay/ (idempotent backup)
```

**Production rule:** Set `RAZORPAY_KEY_ID` + `RAZORPAY_KEY_SECRET`. Do not rely on demo payment mode.

---

## Security Checklist

| Control | Status |
|---------|--------|
| JWT RS256 (no HS256 in prod) | ✅ |
| Rate limiting (DRF + Nginx) | ✅ |
| WebSocket JWT auth | ✅ |
| Server-side payment verification | ✅ |
| Per-lab Docker network isolation | ✅ |
| Blocked command patterns | ✅ |
| Audit logging | ✅ |
| CSP + HSTS (prod nginx) | ✅ |
| Secrets in env only (not git) | ⚠️ Rotate any exposed in SETUP_COMPLETE.md |
| Sentry error monitoring | 🔲 Add `SENTRY_DSN` |
| Demo payment disabled in prod | 🔲 Set in settings_production |

---

## Deployment: Step by Step (DigitalOcean)

### 1. Create platform droplet

- **Size:** 4 vCPU / 8GB RAM ($48/mo) for production
- **Region:** Same as lab droplets (e.g. `nyc1`)
- **Image:** Ubuntu 22.04
- Install Docker + Docker Compose

### 2. Bootstrap

```bash
git clone https://github.com/yourorg/fixitlab.git /opt/fixitlab
cd /opt/fixitlab
cp env.production.example .env.production
# Edit: DO_API_TOKEN, JIRA_*, RAZORPAY_*, JWT keys, DOMAIN
./scripts/deploy.sh production
```

### 3. Configure DO for lab droplets

- Add SSH key to DO account → set `DO_SSH_KEY_ID`
- Set `DO_API_TOKEN` with read/write scope
- Platform droplet needs outbound API access to DO v2

### 4. CI/CD (GitHub Actions)

Add secrets: `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`

- Push to `main` → runs the `merge-gate` smoke job (ephemeral CI stack, no
  deploy). Deploying is a separate, manually dispatched `production.yml` run.
- No staging secrets are needed; there is no staging environment.

### Manual vs automated

| Method | Use when |
|--------|----------|
| **GitHub Actions** | Default — every merge deploys |
| **Manual `./scripts/deploy.sh`** | Hotfixes, initial setup, rollback |

---

## Scenarios (8 total)

| Scenario | Infrastructure | Difficulty |
|----------|---------------|------------|
| broken-nginx | docker | easy (free) |
| broken-cron | docker | easy |
| disk-full | docker | medium |
| zombie-process | docker | easy |
| password-change-broken | docker | medium |
| broken-useradd | digitalocean | medium |
| ssh-lockout | digitalocean | hard |
| dns-resolution-broken | digitalocean | medium |

Seed: `python manage.py seed_scenarios`

---

## What Changed in This Audit

1. ✅ **Jira sync implemented** — was broken (missing `sync.py`)
2. ✅ **Payment audit trail** — PaymentTransaction + webhooks ported
3. ✅ **6 new scenario YAMLs** — all 8 scenarios seedable
4. ✅ **DO-first cloud labs** — aws_ec2 scenarios moved to digitalocean
5. ✅ **Prod deploy files** — Dockerfile.prod, nginx.prod.conf, dual compose
6. ✅ **CI/CD for DigitalOcean** — replaces AWS EKS pipeline
7. ✅ **Jira + billing tests** added

---

## Future Enhancements

- Real-time Jira webhook → FixitLab (bidirectional sync)
- Slack/Teams notifications on lab completion
- Team/org billing with seat licenses
- Scenario marketplace (community submissions)
- DOKS migration path when scale demands it
- Playwright E2E in CI (port from prod-tested `test/smoketest_e2e.py`)
