# FixitLab — Production Setup Guide

Complete checklist to run FixitLab on **your own** VPS (DigitalOcean droplet or any Ubuntu server), **your own Jira Cloud**, **your own Razorpay account**, and **your own GitHub** repo with one-click start/stop.

---

## Architecture (production only)

```
Your GitHub repo
    │  push main / workflow_dispatch
    ▼
SSH → Your VPS (/opt/fixitlab)
    │  docker compose -f docker-compose.prod.yml
    ▼
┌─────────────────────────────────────────┐
│  Nginx (TLS) → React + Django API       │
│  PostgreSQL (persistent volume)         │
│  Redis + RabbitMQ + Celery              │
│  Docker lab containers (per user)       │
└─────────────────────────────────────────┘
    │                    │
    ▼                    ▼
Your Jira Cloud    Your Razorpay account
(atlassian.net)    (dashboard.razorpay.com)
```

**No staging environment** — only `production` GitHub environment and `main` branch deploys.

---

## Step 1 — Server (DigitalOcean or any VPS)

### Minimum specs
- **4 GB RAM**, 2 vCPU, 80 GB disk (50 Linux lab images need disk space)
- Ubuntu 22.04 LTS
- Ports **80** and **443** open

### Bootstrap (first time)

```bash
# On your laptop — clone and push to YOUR GitHub repo first
git clone https://github.com/YOUR_USER/fixitlab.git

# On the server (as root or sudo user)
sudo mkdir -p /opt/fixitlab
sudo chown $USER:$USER /opt/fixitlab
git clone https://github.com/YOUR_USER/fixitlab.git /opt/fixitlab
cd /opt/fixitlab

cp env.production.example .env.production
nano .env.production   # fill all values (see Step 2–4)

chmod +x scripts/*.sh
./scripts/platform-start.sh
```

Or use the bootstrap script:

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USER/fixitlab/main/infra/digitalocean/bootstrap-platform.sh | bash
```

### DNS
Point your domain A record to the server IP:
- `fixitlab.in` → `YOUR_SERVER_IP`
- `www.fixitlab.in` → `YOUR_SERVER_IP`

---

## Step 2 — Environment file (`.env.production`)

Copy template and fill every `[REQUIRED]` value:

```bash
cp env.production.example .env.production
```

Generate Django secret:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

**Critical production flags:**

```env
DJANGO_DEBUG=false
DEMO_PAYMENT_ENABLED=false
LAB_PROVIDER=docker
JIRA_ENABLED=true
```

The backend reads `.env.production` automatically when that file exists.

---

## Step 3 — Your own Jira Cloud (NOT DigitalOcean)

Jira is **Atlassian Jira Cloud** — completely separate from your server provider.

### 3.1 Create Jira Cloud account & project

1. Go to [https://www.atlassian.com/software/jira](https://www.atlassian.com/software/jira)
2. Sign up (free tier works for small teams)
3. Create a project → note the **project key** (e.g. `FIXIT`)
4. Ensure workflow has statuses: **To Do**, **In Progress**, **Done** (or update env vars to match your names)

### 3.2 API token

1. [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. **Create API token** → copy it (shown once)
3. Use the **same email** as your Atlassian login in `JIRA_EMAIL`

### 3.3 Set in `.env.production`

```env
JIRA_ENABLED=true
JIRA_BASE_URL=https://YOURORG.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=paste-token-here
JIRA_PROJECT_KEY=FIXIT
JIRA_ISSUE_TYPE=Task
JIRA_TRANSITION_TODO=To Do
JIRA_TRANSITION_IN_PROGRESS=In Progress
JIRA_TRANSITION_DONE=Done
JIRA_WEBHOOK_SECRET=generate-32-char-random-string
SITE_URL=https://yourdomain.com
```

### 3.4 Inbound webhook (Jira → FixitLab)

In Jira: **⚙ Settings → System → Webhooks → Create webhook**

| Field | Value |
|-------|-------|
| Name | FixitLab |
| URL | `https://yourdomain.com/api/jira/webhooks/?secret=YOUR_JIRA_WEBHOOK_SECRET` |
| Events | Issue updated, Comment created |

### 3.5 Verify

1. Start a lab in FixitLab UI
2. Check your Jira project — new ticket `FIXIT-xxx` should appear
3. Complete lab validation → ticket moves to **Done**

See also: [docs/JIRA_SETUP.md](./JIRA_SETUP.md)

---

## Step 4 — Your own Razorpay account

**I cannot create a Razorpay account for you** — you must register with your business/KYC details.

### 4.1 Sign up

1. [https://dashboard.razorpay.com/signup](https://dashboard.razorpay.com/signup)
2. Complete business verification (for **live** payments)
3. For testing first, use **Test Mode** (toggle in dashboard)

### 4.2 API keys

1. Dashboard → **Settings → API Keys**
2. Generate **Test** keys first: `rzp_test_...`
3. After KYC, generate **Live** keys: `rzp_live_...`

```env
RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
DEMO_PAYMENT_ENABLED=false
```

### 4.3 Webhook (Razorpay → FixitLab)

Dashboard → **Settings → Webhooks → Add New Webhook**

| Field | Value |
|-------|-------|
| URL | `https://yourdomain.com/api/billing/webhook/razorpay/` |
| Events | `payment.captured`, `payment.failed` |
| Secret | Copy the webhook secret Razorpay shows |

```env
RAZORPAY_WEBHOOK_SECRET=paste-webhook-secret-from-dashboard
```

### 4.4 Payment flow

1. User visits **Pricing** → selects technology
2. Razorpay Checkout opens (test card: `4111 1111 1111 1111`)
3. On success → `TechnologySubscription` activated → labs unlocked

---

## Step 5 — GitHub (your repo)

### 5.1 Push code to your GitHub

```bash
git remote add origin https://github.com/YOUR_USER/fixitlab.git
git push -u origin main
```

### 5.2 GitHub Secrets (Settings → Secrets and variables → Actions)

| Secret | Example | Description |
|--------|---------|-------------|
| `PROD_HOST` | `150.136.13.58` | Server IP or hostname |
| `PROD_USER` | `ubuntu` | SSH user |
| `PROD_SSH_KEY` | `-----BEGIN OPENSSH...` | Private key (full PEM) |

**No staging secrets needed** — `STAGE2_*` secrets removed.

### 5.3 GitHub Environment

1. Repo → **Settings → Environments → New environment**
2. Name: `production`
3. Optional: add required reviewers for deploy approval

### 5.4 Workflows (Actions tab)

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| **CI/CD Production** | Push to `main` | Tests → deploy via SSH |
| **Platform Start** | Manual (workflow_dispatch) | Start full stack + migrate + seed + build lab images |
| **Platform Stop** | Manual | Stop containers, **keep database volume** |

#### Start platform manually

1. GitHub → **Actions** → **Platform Start** → **Run workflow**
2. Options:
   - `build_scenarios`: `true` (rebuild all lab Docker images)
   - `git_ref`: `main` (branch to deploy)

#### Stop platform manually

1. **Actions** → **Platform Stop** → **Run workflow**

> **Never run** `docker compose down -v` — that deletes user data in `fixitlab_db_data`.

---

## Step 6 — Email (OTP + notifications)

Gmail app password example:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=16-char-app-password
PRIMARY_EMAIL=your@gmail.com
SUPPORT_EMAIL=support@yourdomain.com
PAYMENT_EMAIL=payments@yourdomain.com
```

Create app password: [Google App Passwords](https://myaccount.google.com/apppasswords)

---

## Step 7 — JWT keys (recommended for production)

```bash
cd backend
python common/security.py generate_keys
# Or openssl:
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
```

Mount into container or set PEM content:

```env
JWT_ALGORITHM=RS256
JWT_RSA_PRIVATE_KEY_PATH=/etc/ssl/private/fixitlab_jwt.key
JWT_RSA_PUBLIC_KEY_PATH=/etc/ssl/certs/fixitlab_jwt_pub.pem
```

---

## Health checks after deploy

```bash
# On server
cd /opt/fixitlab
docker compose -f docker-compose.prod.yml ps
curl -s https://yourdomain.com/api/health/

# Seed scenarios (if not done by platform-start)
docker compose -f docker-compose.prod.yml exec backend python manage.py seed_scenarios --dir /scenarios

# Build lab images (first deploy — takes 30–60 min)
./scripts/build-scenario-images.sh
```

---

## What was fixed in this codebase

| Issue | Fix |
|-------|-----|
| Missing `scripts/startup.sh` | Created — migrate, collectstatic, daphne |
| Settings read `.env` not `.env.production` | Fixed in `settings.py` |
| Demo payments on in prod | Forced off when `DJANGO_DEBUG=false` |
| Razorpay webhook didn't activate subscription | Fixed in `payment_controller.py` |
| `RAZORPAY_WEBHOOK_SECRET` unused | Wired for webhook HMAC |
| `broken-useradd` missing Dockerfile | Added |
| Staging in workflows | Removed — production only |
| JWT RSA file paths | Loaded from `JWT_RSA_*` env |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Backend won't start | Check `docker compose logs backend` — ensure `startup.sh` exists |
| Jira tickets not created | Verify `JIRA_ENABLED=true`, API token, project key |
| Jira transitions fail | Match `JIRA_TRANSITION_*` to your workflow status names |
| Payments bypassed | Set `DEMO_PAYMENT_ENABLED=false` |
| Lab won't start | Run `./scripts/build-scenario-images.sh` |
| Data lost after restart | Never use `docker compose down -v` |
| Webhook 401 | Match `JIRA_WEBHOOK_SECRET` / `RAZORPAY_WEBHOOK_SECRET` |

---

## Security reminders

- Rotate any secrets that were ever committed to git or docs
- Keep `.env.production` out of git (in `.gitignore`)
- Use live Razorpay keys only after KYC approval
- Restrict SSH to your IP in cloud firewall
