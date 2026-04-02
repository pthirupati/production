# FixitLab — Hands-On Linux & DevOps Troubleshooting Platform

FixitLab is a production-grade, interactive platform where users practice real-world Linux and DevOps troubleshooting scenarios in live terminal environments. Users connect to broken servers (Docker containers, AWS EC2 instances, or DigitalOcean droplets), diagnose issues, and fix them — all validated automatically.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Features](#features)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Environment Variables (.env)](#environment-variables-env)
- [Running the Application](#running-the-application)
- [Database & Migrations](#database--migrations)
- [Seeding Data](#seeding-data)
- [Building Scenario Images](#building-scenario-images)
- [Running Tests](#running-tests)
- [Cloud Provisioning (AWS EC2 / DigitalOcean)](#cloud-provisioning-aws-ec2--digitalocean)
- [Production Deployment — AWS](#production-deployment--aws)
- [Production Deployment — DigitalOcean](#production-deployment--digitalocean)
- [Kubernetes Deployment](#kubernetes-deployment)
- [API Reference](#api-reference)
- [Admin Panel](#admin-panel)
- [Troubleshooting](#troubleshooting)
- [Makefile Commands](#makefile-commands)
- [Contributing](#contributing)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                        │
│                           (users browser)                                    │
└─────────────────────────────────┬────────────────────────────────────────────┘
                                  │ :8080 (dev) / :443 (prod)
                                  ▼
                    ┌─────────────────────────────┐
                    │       Nginx Gateway         │
                    │  • Rate limiting             │
                    │  • TLS termination (prod)    │
                    │  • WebSocket upgrade (/ws/)  │
                    │  • Static file serving       │
                    │  • Security headers          │
                    │  • MailHog proxy (admin-only) │
                    └────┬──────────────┬─────────┘
                         │              │
              ┌──────────▼──┐    ┌──────▼──────────────┐
              │  Frontend   │    │  Backend (Daphne)    │
              │  React 18   │    │  Django 5 + DRF      │
              │  Vite 5     │    │  Channels (WebSocket)│
              │  Tailwind   │    │  SimpleJWT Auth      │
              │  xterm.js   │    │  OTP Registration    │
              │  Zustand    │    │  Audit Logging       │
              └─────────────┘    └────┬───┬───┬────────┘
                                      │   │   │
            ┌─────────────────────────┘   │   └──────────────────────┐
            ▼                             ▼                          ▼
   ┌─────────────────┐       ┌─────────────────────┐    ┌──────────────────────┐
   │  PostgreSQL 15  │       │    Redis 7           │    │   RabbitMQ 3         │
   │  • User data    │       │  • Channel layers    │    │  • Celery broker     │
   │  • Scenarios    │       │  • Caching           │    │  • Task queuing      │
   │  • Lab sessions │       │  • Session store     │    │                      │
   │  • Audit logs   │       └─────────────────────┘    └───────┬──────────────┘
   │  • Progress     │                                          │
   │  • Billing      │                                          ▼
   └─────────────────┘                               ┌────────────────────────┐
                                                     │   Celery Workers       │
                                                     │  • Lab cleanup         │
                                                     │  • Orphan termination  │
                                                     │  • Cloud resource mgmt │
                                                     └────────────────────────┘
                                                     ┌────────────────────────┐
                                                     │   Celery Beat          │
                                                     │  • Scheduled cleanup   │
                                                     │  • Periodic tasks      │
                                                     └────────────────────────┘

                    ┌───────────────── Lab Providers ──────────────────┐
                    │                                                   │
          ┌─────────▼──────────┐  ┌──────────▼──────┐  ┌──────────▼──────────┐
          │  Docker Containers │  │  AWS EC2         │  │  DigitalOcean       │
          │  • broken-nginx    │  │  • broken-fstab  │  │  • firewall-lockout │
          │  • broken-cron     │  │  • lvm-recovery  │  │  (real iptables)    │
          │  • disk-full       │  │  (real systemd,  │  │                     │
          │  • ssh-lockout     │  │   LVM, fstab)    │  │                     │
          │  • zombie-process  │  │                  │  │                     │
          │  • dns-broken      │  └──────────────────┘  └─────────────────────┘
          └────────────────────┘
                    │
          xterm.js ◄──► WebSocket (/ws/terminal/) ◄──► Docker exec / SSH (paramiko)
```

### How It Works

1. **User registers** with email OTP verification → logs in → browses scenarios
2. **User starts a lab** → backend provisions a Docker container (or EC2/DO instance)
3. **Terminal connects** via WebSocket → xterm.js in browser talks to a shell inside the container/instance
4. **User fixes the issue** → clicks "Validate" → backend runs validation script inside the environment
5. **Lab auto-terminates** after timeout → Celery workers clean up expired resources
6. **Admin dashboard** shows real-time health, active labs, user activity, and cloud provider status

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18.3, Vite 5.4, TailwindCSS 3.4, xterm.js 5.5, Zustand 4.5, Lucide Icons |
| **Backend** | Django 5.0, Django REST Framework 3.15, Daphne (ASGI), Channels 4.0 |
| **Auth** | SimpleJWT (access 2h / refresh 7d, rotating + blacklist), Email OTP |
| **Database** | PostgreSQL 15 (uuid-ossp, pg_trgm extensions) |
| **Cache** | Redis 7 (channel layers, caching, session store) |
| **Message Broker** | RabbitMQ 3 (Celery tasks) |
| **Task Queue** | Celery 5.3 + Celery Beat (scheduled cleanup) |
| **Lab Provisioning** | Docker SDK 7.0, boto3 (AWS EC2), paramiko (SSH), requests (DO API) |
| **Reverse Proxy** | Nginx 1.25 (rate limiting, WebSocket upgrade, security headers) |
| **Email (dev)** | MailHog (SMTP capture) |
| **Email (prod)** | Gmail SMTP / any SMTP provider |
| **Payments** | Razorpay (UPI, Cards, Net Banking, Wallets) + demo mode fallback |
| **Currency** | Live INR ↔ USD conversion via exchangerate-api.com |
| **Monitoring** | Sentry SDK, structured logging (structlog) |
| **Infrastructure** | Terraform (AWS VPC, EKS, RDS Aurora, ElastiCache, CloudFront), Kubernetes |

---

## Project Structure

```
fixitlab-main/
├── backend/                    # Django backend (API + WebSocket + Celery)
│   ├── Dockerfile
│   ├── manage.py
│   ├── requirements.txt
│   ├── apps/
│   │   ├── accounts/           # User auth, registration, OTP, profiles
│   │   ├── adminpanel/         # Admin API (health, users, labs, scenarios, maintenance, config)
│   │   ├── audit/              # Audit logging middleware + models
│   │   ├── billing/            # Stripe subscriptions + per-technology subscriptions
│   │   ├── community/          # Community discussion threads, replies, voting
│   │   ├── hints/              # Scenario hints system
│   │   ├── labs/               # Lab sessions + provisioners
│   │   │   └── provisioner/    # Docker, EC2, DigitalOcean provisioners
│   │   ├── leaderboard/        # User rankings + XP
│   │   ├── notifications/      # User notifications + email templates
│   │   ├── progress/           # User scenario progress tracking
│   │   ├── public_api/         # Public API views (start/stop/validate labs, platform config)
│   │   ├── question_bank/      # Scenarios, technologies, tags
│   │   ├── ratings/            # Scenario ratings and reviews
│   │   ├── scenario_versions/  # Scenario versioning
│   │   └── terminal/           # WebSocket terminal consumer
│   ├── celery_app/             # Celery config + tasks
│   ├── common/                 # Shared utilities, constants, permissions
│   └── config/                 # Django settings, URLs, ASGI/WSGI
├── frontend/                   # React SPA
│   ├── Dockerfile              # Dev (Vite hot-reload)
│   ├── Dockerfile.prod         # Prod (multi-stage, nginx)
│   ├── package.json
│   └── src/
│       ├── api/                # Axios API clients (labs, admin, community, ratings, subscriptions)
│       ├── components/         # Reusable React components (layout, skeleton, modals)
│       ├── pages/              # Page components (Dashboard, Labs, Admin, Community, FAQ, etc.)
│       ├── router/             # React Router config
│       ├── store/              # Zustand state management (auth, theme, notifications)
│       ├── styles/             # Global CSS + Tailwind (light/dark theme)
│       └── utils/              # Shared constants (ACHIEVEMENT_META), time utilities
├── gateway/                    # Nginx reverse proxy
│   ├── Dockerfile
│   └── nginx.conf
├── database/                   # PostgreSQL init
│   ├── Dockerfile
│   └── init/init.sql           # UUID + pg_trgm extensions
├── scenarios/                  # Lab scenario Docker images
│   ├── linux/
│   │   ├── broken-nginx/       # Misconfigured Nginx
│   │   ├── broken-cron/        # Broken crontab entries
│   │   ├── disk-full/          # Full disk simulation
│   │   ├── ssh-lockout/        # SSH access issues
│   │   └── zombie-process/     # Zombie process cleanup
│   ├── networking/
│   │   └── dns-resolution-broken/  # DNS resolver issues
│   └── shared/                 # Shared scenario utilities (systemctl shim)
├── infra/
│   ├── kubernetes/             # K8s deployment manifests
│   │   └── deployment.yaml     # Full cluster config (HPA, Ingress, etc.)
│   ├── terraform/              # AWS infrastructure-as-code
│   │   └── main.tf             # VPC, EKS, RDS, ElastiCache, CloudFront
│   └── scripts/
│       └── bootstrap.sh        # Server bootstrap (Docker, kubectl)
├── scripts/
│   ├── startup.sh              # Backend entrypoint (migrate + seed + serve)
│   ├── create_superuser.py     # Idempotent superuser creation
│   ├── seed_data.py            # Seed plans, technologies, scenarios, hints
│   └── wait_for_db.sh          # Database readiness check
├── test/
│   ├── Dockerfile
│   ├── smoketest_e2e.py
│   └── e2e_full.sh             # 64-test E2E suite
├── docs/
│   ├── api.md
│   ├── architecture.md
│   └── ui-guidelines.md
├── docker-compose.yml          # Full dev environment (9 services)
├── Makefile                    # Build, test, deploy commands
└── .env                        # Environment variables (not in git)
```

---

## Features

### Core Platform
- **Live Terminal Labs**: Connect to broken servers via xterm.js — Docker containers, AWS EC2, or DigitalOcean droplets
- **Auto-Validation**: Solutions checked automatically inside the environment
- **Hint System**: Progressive hints available per scenario (with point deductions)
- **Leaderboard**: XP-based rankings with achievement badges
- **Achievements**: 13 unlockable badges (streaks, mastery, speed runs)
- **Multi-Provider**: Labs run on Docker (local), AWS EC2, or DigitalOcean

### Community & Social
- **Discussion Threads**: Create, reply, vote on threads filtered by technology
- **Ratings & Reviews**: Rate scenarios (1-5 stars) with written reviews
- **Nested Replies**: Full reply threading with edit/delete support

### Subscription & Billing
- **Per-Technology Subscriptions**: Subscribe to individual technology tracks (e.g., Linux ₹499, Docker ₹599, AWS ₹799)
- **Razorpay Integration**: UPI, credit/debit cards, net banking, wallets — with demo mode for development
- **Live Currency Conversion**: Auto-detect user country → show prices in INR or USD with live exchange rates
- **Multi-Tech Cart**: Add multiple technologies to cart and subscribe in one batch
- **Unique Subscription IDs**: Format `<TECH>-<USERNAME>-<YEAR>-FIXITLAB`
- **Email Notifications**: Confirmation emails to users + admin notifications on new subscriptions
- **Per-Technology Certificates**: Downloadable only after completing ALL scenarios for a technology + active subscription
- **Certificate Emails**: Certificate details automatically emailed to user on generation

### Admin Panel
- **Dashboard**: Revenue, paid subscribers, active labs, completion rates, community stats
- **User Management**: View, ban, promote users; track inactive accounts (90+ days)
- **Maintenance Mode**: Toggle platform-wide maintenance from admin
- **Thread Moderation**: Pin, lock, or delete community threads
- **Subscription Logs**: Full subscription history with revenue totals
- **Platform Config**: View all configurable emails and system settings

### Static & Public Pages
- Privacy Policy, Terms of Service, Contact, FAQ — all with consistent layout
- Light/dark theme support throughout (default: light)

---

## Quick Start

> **Want to get running fast?** See the full [START.md](START.md) guide.

```bash
git clone https://github.com/your-org/fixitlab.git
cd fixitlab/fixitlab-main
cp env.production.example .env     # Edit with your values
docker compose up -d --build       # Start all 9 services
make scenarios                     # Build lab scenario images
# Open http://localhost:8080
```

---

## Prerequisites

- **Docker Desktop** ≥ 24.0 (with Docker Compose v2)
- **Git**
- **macOS / Linux** (Windows users: use WSL2)
- **Node.js 20+** (only if running frontend outside Docker)
- **Python 3.12+** (only if running backend outside Docker)

For production deployments:
- **AWS CLI v2** + IAM credentials (for AWS deployment)
- **doctl** (for DigitalOcean deployment)
- **kubectl** (for Kubernetes)
- **Terraform** ≥ 1.7 (for AWS infrastructure provisioning)

---

## Local Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/fixitlab.git
cd fixitlab/fixitlab-main
```

### 2. Create the `.env` File

```bash
cp .env.example .env   # or create manually
```

Add the following to your `.env` file:

```env
# ─── Django ──────────────────────────────────────────────
DJANGO_SECRET_KEY=your-secret-key-change-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend

# ─── PostgreSQL ──────────────────────────────────────────
POSTGRES_DB=fixitlab
POSTGRES_USER=fixitlab
POSTGRES_PASSWORD=fixitlab_secure_password
POSTGRES_HOST=database
POSTGRES_PORT=5432

# ─── Redis ───────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379

# ─── RabbitMQ / Celery ──────────────────────────────────
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

# ─── CORS ────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080

# ─── Superuser ───────────────────────────────────────────
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@fixitlab.com
SUPERUSER_PASSWORD=YourStrongPassword123!

# ─── Email (Development — uses MailHog) ──────────────────
# Leave EMAIL_HOST_USER empty to use MailHog
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# ─── Email (Production — Gmail SMTP example) ─────────────
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_HOST_USER=your-email@gmail.com
# EMAIL_HOST_PASSWORD=your-app-password
# EMAIL_USE_TLS=True

# ─── Frontend ───────────────────────────────────────────
FRONTEND_URL=http://localhost:8080

# ─── Lab Settings ───────────────────────────────────────
LAB_PROVIDER=docker
LAB_MAX_DURATION_MINUTES=60
LAB_CLEANUP_INTERVAL_MINUTES=5
DOCKER_NETWORK=fixitlab_labs
DOCKER_SCENARIO_IMAGE_PREFIX=fixitlab/scenario-
DOCKER_CONTAINER_MEMORY_LIMIT=512m
DOCKER_CONTAINER_CPU_LIMIT=1.0

# ─── Stripe (optional) ──────────────────────────────────
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# ─── AWS EC2 (optional — for cloud lab scenarios) ───────
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
AWS_LAB_BASE_AMI=ami-0c7217cdde317cfec
AWS_LAB_INSTANCE_TYPE=t3.micro
AWS_LAB_SUBNET_ID=
AWS_LAB_SECURITY_GROUP_ID=
AWS_LAB_KEY_PAIR=fixitlab-labs
AWS_LAB_KEY_PEM=
AWS_LAB_KEY_PATH=

# ─── DigitalOcean (optional — for cloud lab scenarios) ──
DO_API_TOKEN=
DO_SSH_KEY_ID=
DO_SSH_KEY_PEM=
DO_SSH_KEY_PATH=
DO_REGION=nyc1
DO_SIZE=s-1vcpu-1gb
```

### 3. Start Everything

```bash
# Build and start all 9 services
docker compose up -d --build

# Or use the Makefile
make up
```

This starts:
| Service | Container | Port |
|---|---|---|
| Nginx Gateway | `fixitlab-main-gateway-1` | `8080` → 80 |
| React Frontend | `fixitlab_frontend` | internal 5173 |
| Django Backend | `fixitlab_backend` | internal 8000 |
| Celery Worker | `fixitlab-main-celery_worker-1` | — |
| Celery Beat | `fixitlab-main-celery_beat-1` | — |
| PostgreSQL | `fixitlab_db` | internal 5432 |
| Redis | `fixitlab_redis` | internal 6379 |
| RabbitMQ | `fixitlab_rabbitmq` | internal 5672 |
| MailHog | `fixitlab_mailhog` | internal 8025 |

### 4. Build Scenario Images

```bash
# Build all 6 Docker-based scenario images
make scenarios

# Or manually build one
docker build -t fixitlab/scenario-broken-nginx:latest scenarios/linux/broken-nginx/
```

### 5. Access the Application

| URL | Description |
|---|---|
| http://localhost:8080 | Main application |
| http://localhost:8080/api/health/ | Health check |
| http://localhost:8080/api/admin/health/ | Admin health dashboard (requires auth) |
| http://localhost:8080/django-admin/ | Django admin interface |
| http://localhost:8080/mailbox/ | MailHog email viewer (Basic Auth: `admin` / your superuser password) |

### 6. First Login

1. Open http://localhost:8080
2. Click **Register** → enter email → receive OTP in MailHog (http://localhost:8080/mailbox/)
3. Enter OTP → set password → you're in!
4. Or login with the superuser: email = `admin@fixitlab.com`, password = your `SUPERUSER_PASSWORD`

---

## Environment Variables (.env)

### Required Variables

| Variable | Description | Example |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key (generate a unique one for production) | `django-insecure-abc123...` |
| `POSTGRES_DB` | Database name | `fixitlab` |
| `POSTGRES_USER` | Database user | `fixitlab` |
| `POSTGRES_PASSWORD` | Database password | `strong_password_here` |
| `SUPERUSER_USERNAME` | Admin username | `admin` |
| `SUPERUSER_EMAIL` | Admin email | `admin@fixitlab.com` |
| `SUPERUSER_PASSWORD` | Admin password (min 8 chars) | `YourStrongPass!` |

### Optional Variables

| Variable | Description | Default |
|---|---|---|
| `DJANGO_DEBUG` | Debug mode | `True` |
| `DJANGO_ALLOWED_HOSTS` | Allowed hosts | `localhost,127.0.0.1,backend` |
| `EMAIL_HOST_USER` | SMTP username (empty = MailHog) | `""` |
| `EMAIL_HOST_PASSWORD` | SMTP password | `""` |
| `LAB_MAX_DURATION_MINUTES` | Lab timeout | `60` |
| `DOCKER_CONTAINER_MEMORY_LIMIT` | Container RAM limit | `512m` |
| `DOCKER_CONTAINER_CPU_LIMIT` | Container CPU limit | `1.0` |
| `RAZORPAY_KEY_ID` | Razorpay API key (empty = demo mode) | `""` |
| `RAZORPAY_KEY_SECRET` | Razorpay API secret | `""` |
| `DEFAULT_CURRENCY` | Default pricing currency | `INR` |
| `ENABLE_CURRENCY_CONVERSION` | Enable live INR ↔ USD conversion | `true` |

### Cloud Provider Variables (for AWS EC2 / DigitalOcean labs)

| Variable | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `AWS_LAB_BASE_AMI` | Base AMI for lab instances |
| `AWS_LAB_INSTANCE_TYPE` | EC2 instance type (default: `t3.micro`) |
| `AWS_LAB_SUBNET_ID` | VPC subnet ID |
| `AWS_LAB_SECURITY_GROUP_ID` | Security group ID (SSH port 22 must be open) |
| `AWS_LAB_KEY_PAIR` | EC2 key pair name |
| `AWS_LAB_KEY_PEM` | Raw PEM content (alternative to KEY_PATH) |
| `AWS_LAB_KEY_PATH` | Path to `.pem` file (mount into container) |
| `DO_API_TOKEN` | DigitalOcean API token |
| `DO_SSH_KEY_ID` | DO SSH key fingerprint/ID |
| `DO_SSH_KEY_PEM` | Raw PEM content (alternative to KEY_PATH) |
| `DO_SSH_KEY_PATH` | Path to private key file |
| `DO_REGION` | DO region (default: `nyc1`) |
| `DO_SIZE` | Droplet size (default: `s-1vcpu-1gb`) |

---

## Running the Application

### Development Mode (with hot-reload)

```bash
# Start all services with live code mounting
docker compose up --build

# Or detached
docker compose up -d --build

# View logs
docker compose logs -f
docker compose logs -f backend     # backend only
docker compose logs -f gateway     # nginx only
```

### Restart Individual Services

```bash
docker compose restart backend
docker compose restart frontend
docker compose restart celery_worker celery_beat
docker compose restart gateway
```

### Rebuild After Code Changes

```bash
# Backend changes
docker compose up -d --build backend
docker compose restart celery_worker celery_beat gateway

# Frontend changes
docker compose up -d --build frontend
docker compose restart gateway

# Full rebuild
docker compose up -d --build
```

### Stop Everything

```bash
docker compose down          # stop containers
docker compose down -v       # stop + delete volumes (wipes database!)
```

---

## Database & Migrations

### How Migrations Work

The `startup.sh` entrypoint automatically runs migrations on every backend start:
1. `makemigrations` for all apps
2. `migrate --noinput`
3. `migrate --run-syncdb` (catches missing columns)

### Manual Migration Commands

```bash
# Check current migration status
docker compose exec backend python manage.py showmigrations

# Create new migrations after model changes
docker compose exec backend python manage.py makemigrations

# Apply pending migrations
docker compose exec backend python manage.py migrate

# Apply specific app migrations
docker compose exec backend python manage.py migrate accounts
docker compose exec backend python manage.py migrate question_bank
docker compose exec backend python manage.py migrate labs

# Rollback a migration
docker compose exec backend python manage.py migrate accounts 0001

# Show SQL for a migration (dry run)
docker compose exec backend python manage.py sqlmigrate accounts 0002

# Or use the Makefile
make migrate
make makemigrations
```

### Database Shell

```bash
# Django ORM shell
docker compose exec backend python manage.py shell

# PostgreSQL shell
docker compose exec database psql -U fixitlab -d fixitlab

# Or use the Makefile
make shell
make dbshell
```

### If Migrations Are Missing or Broken

```bash
# 1. Check what's out of sync
docker compose exec backend python manage.py showmigrations

# 2. Force-create migrations for a specific app
docker compose exec backend python manage.py makemigrations accounts --name fix_missing_fields

# 3. If migration files exist but aren't applied
docker compose exec backend python manage.py migrate --fake accounts 0001
docker compose exec backend python manage.py migrate accounts

# 4. Nuclear option — reset all migrations (DEVELOPMENT ONLY)
docker compose down -v                                    # wipe database
docker compose exec backend find . -path "*/migrations/0*.py" -delete  # delete migration files
docker compose exec backend python manage.py makemigrations           # regenerate
docker compose exec backend python manage.py migrate                  # apply fresh

# 5. Fix "table already exists" errors
docker compose exec backend python manage.py migrate --fake-initial
```

---

## Seeding Data

The `startup.sh` script automatically seeds data on first boot. To manually re-seed:

```bash
# Copy seed script into container and run
docker cp scripts/seed_data.py fixitlab_backend:/app/seed_data.py
docker compose exec backend python seed_data.py

# Or use the Makefile
make seed
```

This seeds:
- **3 Billing Plans**: Free ($0), Pro ($9.99/mo), Enterprise ($49.99/mo)
- **5 Technologies**: Linux, Docker, Networking, Web Servers, Databases
- **9 Scenarios**: 6 Docker-based + 2 AWS EC2 + 1 DigitalOcean
- **Tags**: config, nginx, cron, disk, ssh, process, dns, filesystem, lvm, firewall
- **Hints**: Multiple hints per scenario with point costs

---

## Building Scenario Images

Each scenario is a Docker image containing a pre-broken Linux environment.

```bash
# Build ALL scenario images
make scenarios

# Build a specific scenario
docker build -t fixitlab/scenario-broken-nginx:latest scenarios/linux/broken-nginx/
docker build -t fixitlab/scenario-broken-cron:latest scenarios/linux/broken-cron/
docker build -t fixitlab/scenario-disk-full:latest scenarios/linux/disk-full/
docker build -t fixitlab/scenario-ssh-lockout:latest scenarios/linux/ssh-lockout/
docker build -t fixitlab/scenario-zombie-process:latest scenarios/linux/zombie-process/
docker build -t fixitlab/scenario-dns-resolution-broken:latest scenarios/networking/dns-resolution-broken/

# Verify images are built
docker images | grep fixitlab/scenario
```

### Available Scenarios

| Scenario | Category | Provider | Description |
|---|---|---|---|
| `broken-nginx` | Linux | Docker | Misconfigured Nginx (syntax errors, wrong ports) |
| `broken-cron` | Linux | Docker | Broken crontab entries |
| `disk-full` | Linux | Docker | Full disk simulation |
| `ssh-lockout` | Linux | Docker | SSH access/config issues |
| `zombie-process` | Linux | Docker | Zombie processes to clean up |
| `dns-resolution-broken` | Networking | Docker | DNS resolver misconfiguration |
| `broken-fstab` | Linux | AWS EC2 | Broken /etc/fstab (needs real mount) |
| `lvm-recovery` | Linux | AWS EC2 | LVM volume group recovery |
| `firewall-lockout` | Networking | DigitalOcean | iptables firewall rules |

---

## Running Tests

### E2E Test Suite (64 tests)

The full end-to-end test suite validates every API endpoint, auth flow, lab lifecycle, admin panel, and security control.

```bash
# Run the full 64-test E2E suite
bash test/e2e_full.sh

# Expected output:
# ═══════════════════════════════════════════════
#   RESULTS: 64 passed, 0 failed, 64 total
# ═══════════════════════════════════════════════
```

**What the E2E tests cover:**

| Section | Tests |
|---|---|
| Infrastructure | Health endpoint, gateway status |
| Registration | OTP flow, email verification, duplicate rejection |
| Authentication | Login, bad login rejection, unauthorized access |
| Profile | Read profile, update display name |
| Scenarios | List, filter by technology, search, detail view |
| Lab Lifecycle | Start lab, validate, stop, XP awarded |
| Progress | User progress tracking, per-scenario stats |
| Leaderboard | Rankings with XP data |
| Hints | List hints, unlock hints |
| Notifications | List notifications |
| Billing | Plans listing |
| Dashboard | User stats dashboard |
| Password Management | Change password, login with new password |
| Security | MailHog port blocked, gateway auth, blocked paths |
| Rate Limiting | Auth endpoint throttling |
| Admin Endpoints | Overview, users, scenarios, health, activity, audit |
| Email Delivery | Gmail SMTP send verification |

### Django Unit Tests

```bash
# Run backend unit tests
docker compose exec backend python manage.py test --verbosity=2

# Run tests for a specific app
docker compose exec backend python manage.py test apps.accounts --verbosity=2
docker compose exec backend python manage.py test apps.labs --verbosity=2

# Or use the Makefile
make test
```

### Linting

```bash
# Lint backend code
docker compose exec backend flake8 --max-line-length=120 --exclude=migrations .

# Or use the Makefile
make lint
```

---

## Payment Flow & Subscriptions

FixitLab uses **Razorpay** for processing payments with a built-in **demo mode** for development.

### Pricing Model

| Technology | Price (INR) | Price (USD, live rate) |
|---|---|---|
| Linux | ₹499 | ~$5.32 |
| Docker | ₹599 | ~$6.38 |
| Networking | ₹399 | ~$4.25 |
| Web Servers | ₹449 | ~$4.78 |
| Databases | ₹499 | ~$5.32 |
| AWS | ₹799 | ~$8.51 |

USD prices are calculated via live exchange rates from exchangerate-api.com.

### Demo Mode (Development)

When `RAZORPAY_KEY_ID` is empty or not set, the platform operates in **demo mode**:

1. User selects technologies → clicks **"Buy Now"** → backend creates order with `payment_token`
2. User is redirected to Payment page → selects payment method (UPI, Card, Net Banking, Wallet)
3. For UPI: enters UPI ID (e.g., `user@upi`) → clicks **"Complete Payment"**
4. Backend confirms the `payment_token` → subscription activates immediately
5. No real money is charged — ideal for development and testing

### Live Mode (Production)

1. Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env.production`
2. Razorpay SDK loads in the browser → opens Razorpay checkout
3. User completes payment through Razorpay's secure form
4. Backend verifies the payment signature → activates subscription

### Multi-Technology Cart

Users can add multiple technologies to their cart from the Pricing page and subscribe to all of them in a single batch checkout.

---

## Certificates

Certificates are issued **per technology** and require:

1. **Active subscription** for that technology
2. **100% scenario completion** — all scenarios in the technology must be completed with a passing score

### How It Works

1. User completes all scenarios for a technology (e.g., 8/8 Linux scenarios)
2. A **"Download Certificate"** button appears on the Achievements page and Dashboard
3. Clicking it generates a printable HTML certificate with:
   - User's name and username
   - Technology name and scenario count
   - Total score and completion date
   - Unique certificate ID (format: `CERT-<TECH>-<USER>-<TIMESTAMP>`)
   - QR-style verification URL
4. Certificate details are **automatically emailed** to the user
5. Certificates can be verified publicly via `/api/achievements/certificate/verify/?certificate_id=<id>`

### Prerequisites for Tests

Ensure all services are running and healthy:

```bash
# Check all containers are up
docker compose ps

# Check backend health
curl http://localhost:8080/api/health/

# Check all scenario images are built
docker images | grep fixitlab/scenario
```

---

## Cloud Provisioning (AWS EC2 / DigitalOcean)

FixitLab supports three infrastructure providers for lab scenarios:

| Provider | Use Case | Cost |
|---|---|---|
| **Docker** (default) | Most scenarios — fast, free, local | Free |
| **AWS EC2** | Scenarios needing real systemd, LVM, fstab, kernel modules | ~$0.01/hr per t3.micro |
| **DigitalOcean** | Scenarios needing real iptables, full networking stack | ~$0.007/hr per s-1vcpu-1gb |

### Setting Up AWS EC2 Labs

1. **Create an IAM user** with `AmazonEC2FullAccess` policy
2. **Create a key pair** in the EC2 console → download the `.pem` file
3. **Create a security group** with inbound SSH (port 22) from your backend server's IP
4. **Create a VPC subnet** (or use the default VPC)

```bash
# Add to .env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG...
AWS_REGION=us-east-1
AWS_LAB_BASE_AMI=ami-0c7217cdde317cfec
AWS_LAB_INSTANCE_TYPE=t3.micro
AWS_LAB_SUBNET_ID=subnet-0abc123def456
AWS_LAB_SECURITY_GROUP_ID=sg-0abc123def456
AWS_LAB_KEY_PAIR=fixitlab-labs
AWS_LAB_KEY_PATH=/keys/fixitlab-labs.pem
```

5. **Mount the key into the Docker container** — add a volume mount in `docker-compose.yml`:

```yaml
backend:
  volumes:
    - ./keys/fixitlab-labs.pem:/keys/fixitlab-labs.pem:ro
```

6. Restart the backend:

```bash
docker compose up -d --build backend
docker compose restart celery_worker celery_beat
```

### Setting Up DigitalOcean Labs

1. **Generate a Personal Access Token** at https://cloud.digitalocean.com/account/api/tokens
2. **Add an SSH key** at https://cloud.digitalocean.com/account/security → note the key ID

```bash
# Add to .env
DO_API_TOKEN=dop_v1_abc123...
DO_SSH_KEY_ID=12345678
DO_SSH_KEY_PATH=/keys/do-key.pem
DO_REGION=nyc1
DO_SIZE=s-1vcpu-1gb
```

3. Mount the key and restart (same as AWS above).

### Auto-Termination

All cloud instances are automatically terminated:
- When the lab session times out (`LAB_MAX_DURATION_MINUTES`)
- When a user clicks "Stop Lab"
- When an admin terminates from the admin panel
- By the `cleanup_orphaned_containers` Celery task (runs every 15 minutes)

Cloud instances are tagged with `fixitlab` metadata for safe cleanup.

---

## Production Deployment — AWS

### Option A: Full AWS with Terraform + EKS (Recommended)

This deploys the complete production infrastructure:
- **EKS** (Kubernetes) with auto-scaling node groups
- **RDS Aurora PostgreSQL** (multi-AZ, 7-day backups)
- **ElastiCache Redis** (2-node cluster, automatic failover)
- **CloudFront CDN** for static assets
- **ECR** for Docker image registry
- **VPC** with private/public subnets across 3 AZs

#### Step 1: Prerequisites

```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# Configure AWS credentials
aws configure
# Enter: Access Key ID, Secret Key, Region (us-east-1), Output (json)

# Install Terraform
brew install terraform    # macOS
# or: https://developer.hashicorp.com/terraform/install

# Install kubectl
brew install kubectl      # macOS
```

#### Step 2: Create S3 Backend for Terraform State

```bash
aws s3 mb s3://fixitlab-terraform-state --region us-east-1
aws s3api put-bucket-versioning \
  --bucket fixitlab-terraform-state \
  --versioning-configuration Status=Enabled
```

#### Step 3: Deploy Infrastructure

```bash
cd infra/terraform

# Initialize Terraform
terraform init

# Preview the infrastructure
terraform plan

# Deploy (takes ~20-30 minutes)
terraform apply

# Note the outputs:
# - eks_cluster_endpoint
# - rds_endpoint
# - redis_endpoint
# - ecr_backend_url
# - ecr_frontend_url
# - cloudfront_domain
```

#### Step 4: Configure kubectl

```bash
aws eks update-kubeconfig --region us-east-1 --name fixitlab-prod
kubectl get nodes   # should show nodes
```

#### Step 5: Build and Push Docker Images

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build production images
docker build -t <ECR_URL>/fixitlab/backend:latest ./backend
docker build -f frontend/Dockerfile.prod -t <ECR_URL>/fixitlab/frontend:latest ./frontend

# Push images
docker push <ECR_URL>/fixitlab/backend:latest
docker push <ECR_URL>/fixitlab/frontend:latest

# Build and push scenario images
make scenarios ECR_REGISTRY=<ECR_URL>/fixitlab
make push ECR_REGISTRY=<ECR_URL>/fixitlab
```

#### Step 6: Update Kubernetes Secrets

Edit `infra/kubernetes/deployment.yaml` and update the Secrets section with your production values:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: fixitlab-secrets
  namespace: fixitlab
type: Opaque
stringData:
  DJANGO_SECRET_KEY: "your-production-secret-key-here"
  POSTGRES_PASSWORD: "your-rds-password"
  STRIPE_SECRET_KEY: "sk_live_..."
  STRIPE_WEBHOOK_SECRET: "whsec_..."
  AWS_ACCESS_KEY_ID: "AKIA..."
  AWS_SECRET_ACCESS_KEY: "wJalr..."
  DO_API_TOKEN: "dop_v1_..."
```

Update the ConfigMap with Terraform outputs:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fixitlab-config
  namespace: fixitlab
data:
  POSTGRES_HOST: "<RDS_ENDPOINT>"           # from terraform output
  REDIS_HOST: "<ELASTICACHE_ENDPOINT>"      # from terraform output
  DJANGO_ALLOWED_HOSTS: "fixitlab.com,www.fixitlab.com"
  CORS_ALLOWED_ORIGINS: "https://fixitlab.com"
  FRONTEND_URL: "https://fixitlab.com"
```

#### Step 7: Deploy to Kubernetes

```bash
# Create namespace and deploy everything
kubectl apply -f infra/kubernetes/deployment.yaml

# Check rollout status
kubectl -n fixitlab rollout status deployment/backend --timeout=300s
kubectl -n fixitlab rollout status deployment/frontend --timeout=300s

# Run migrations
kubectl -n fixitlab exec deployment/backend -- python manage.py migrate --noinput

# Verify all pods are running
kubectl -n fixitlab get pods

# Check services
kubectl -n fixitlab get svc

# Check ingress
kubectl -n fixitlab get ingress
```

#### Step 8: DNS Configuration

Point your domain to the AWS Load Balancer:

```bash
# Get the ingress external address
kubectl -n fixitlab get ingress fixitlab-ingress

# Create a CNAME record:
# fixitlab.com → <LOAD_BALANCER_DNS>
# or an A record if using Route53 alias
```

#### Step 9: SSL Certificate

The Kubernetes Ingress is configured to use cert-manager with Let's Encrypt:

```bash
# Install cert-manager (if not already installed)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# The Ingress annotation handles certificate issuance automatically:
# cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

### Option B: Single EC2 Instance (Budget)

For smaller deployments, run everything on a single EC2 instance:

#### Step 1: Launch an EC2 Instance

```bash
# Recommended: t3.large (2 vCPU, 8 GB RAM) or bigger
# AMI: Ubuntu 22.04 LTS
# Storage: 50 GB SSD minimum
# Security Group: Open ports 80, 443, 22
```

#### Step 2: Bootstrap the Server

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Run the bootstrap script
curl -sSL https://raw.githubusercontent.com/your-org/fixitlab/main/infra/scripts/bootstrap.sh | bash

# Or manually:
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER
newgrp docker
```

#### Step 3: Deploy

```bash
git clone https://github.com/your-org/fixitlab.git
cd fixitlab/fixitlab-main

# Create production .env
cp .env.example .env
nano .env
# Set:
#   DJANGO_DEBUG=False
#   DJANGO_SECRET_KEY=<generate-new-key>
#   DJANGO_ALLOWED_HOSTS=your-domain.com,<EC2_PUBLIC_IP>
#   CORS_ALLOWED_ORIGINS=https://your-domain.com
#   FRONTEND_URL=https://your-domain.com
#   POSTGRES_PASSWORD=<strong-password>
#   EMAIL_HOST_USER=your-email@gmail.com
#   EMAIL_HOST_PASSWORD=your-app-password

# Build and start
docker compose up -d --build

# Build scenario images
make scenarios

# Verify
curl http://localhost:8080/api/health/
```

#### Step 4: Set Up Nginx + SSL (on the host)

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

# Create Nginx config
sudo tee /etc/nginx/sites-available/fixitlab <<'EOF'
server {
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/fixitlab /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

---

## Production Deployment — DigitalOcean

### Option A: DigitalOcean Kubernetes (DOKS)

#### Step 1: Create a Kubernetes Cluster

```bash
# Install doctl
brew install doctl     # macOS

# Authenticate
doctl auth init

# Create cluster (3 nodes)
doctl kubernetes cluster create fixitlab-prod \
  --region nyc1 \
  --size s-4vcpu-8gb \
  --count 3 \
  --auto-upgrade

# Save kubeconfig
doctl kubernetes cluster kubeconfig save fixitlab-prod
```

#### Step 2: Create Managed Database + Redis

```bash
# PostgreSQL 15
doctl databases create fixitlab-db \
  --engine pg --version 15 \
  --size db-s-2vcpu-4gb \
  --region nyc1 \
  --num-nodes 2

# Redis
doctl databases create fixitlab-redis \
  --engine redis --version 7 \
  --size db-s-1vcpu-2gb \
  --region nyc1

# Note the connection strings from:
doctl databases connection fixitlab-db
doctl databases connection fixitlab-redis
```

#### Step 3: Create Container Registry

```bash
doctl registry create fixitlab --region nyc1

# Login to registry
doctl registry login

# Build and push images
docker build -t registry.digitalocean.com/fixitlab/backend:latest ./backend
docker build -f frontend/Dockerfile.prod -t registry.digitalocean.com/fixitlab/frontend:latest ./frontend
docker push registry.digitalocean.com/fixitlab/backend:latest
docker push registry.digitalocean.com/fixitlab/frontend:latest

# Connect registry to cluster
doctl kubernetes cluster registry add fixitlab-prod
```

#### Step 4: Deploy to Kubernetes

Update `infra/kubernetes/deployment.yaml` with DO database endpoints and image URLs, then:

```bash
kubectl apply -f infra/kubernetes/deployment.yaml
kubectl -n fixitlab rollout status deployment/backend
kubectl -n fixitlab exec deployment/backend -- python manage.py migrate
```

#### Step 5: DNS + SSL

```bash
# Get load balancer IP
kubectl -n fixitlab get svc

# Point domain A record to the load balancer IP
# SSL is handled by cert-manager (already configured in deployment.yaml)
```

### Option B: Single Droplet (Budget)

```bash
# Create a droplet
doctl compute droplet create fixitlab-prod \
  --image ubuntu-22-04-x64 \
  --size s-4vcpu-8gb \
  --region nyc1 \
  --ssh-keys <YOUR_SSH_KEY_ID>

# SSH in
ssh root@<DROPLET_IP>

# Bootstrap
curl -sSL https://raw.githubusercontent.com/your-org/fixitlab/main/infra/scripts/bootstrap.sh | bash

# Clone, configure .env, and deploy (same as AWS single-instance steps above)
git clone https://github.com/your-org/fixitlab.git
cd fixitlab/fixitlab-main
cp .env.example .env
nano .env   # configure for production
docker compose up -d --build
make scenarios

# Set up Nginx + Let's Encrypt SSL
apt install -y nginx certbot python3-certbot-nginx
# (same nginx config as AWS single-instance above)
certbot --nginx -d your-domain.com
```

---

## Kubernetes Deployment

The `infra/kubernetes/deployment.yaml` provides a complete production-grade K8s setup:

### Resources Created

| Resource | Replicas | Scaling |
|---|---|---|
| Backend (Daphne) | 3 | HPA: 3–50 pods @ 70% CPU |
| Celery Worker | 2 | HPA: 2–20 pods @ 70% CPU |
| Celery Beat | 1 | No scaling (singleton) |
| Frontend (Nginx) | 2 | HPA: 2–10 pods @ 70% CPU |
| PostgreSQL | 1 | StatefulSet with 20Gi PVC |
| Redis | 1 | Deployment |
| RabbitMQ | 1 | Deployment |

### Key Commands

```bash
# Apply/update deployment
kubectl apply -f infra/kubernetes/deployment.yaml

# Check all resources
kubectl -n fixitlab get all

# View logs
kubectl -n fixitlab logs -f deployment/backend
kubectl -n fixitlab logs -f deployment/celery-worker

# Run migrations
kubectl -n fixitlab exec deployment/backend -- python manage.py migrate

# Scale manually
kubectl -n fixitlab scale deployment/backend --replicas=5

# Restart a deployment
kubectl -n fixitlab rollout restart deployment/backend

# Access Django shell
kubectl -n fixitlab exec -it deployment/backend -- python manage.py shell
```

---

## API Reference

### Authentication

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/auth/send-otp/` | Send OTP to email | No |
| `POST` | `/api/auth/verify-otp/` | Verify OTP code | No |
| `POST` | `/api/auth/register/` | Register with verified OTP | No |
| `POST` | `/api/auth/login/` | Login (returns JWT tokens) | No |
| `POST` | `/api/auth/logout/` | Logout (blacklist token) | Yes |
| `POST` | `/api/auth/refresh/` | Refresh access token | No |
| `GET` | `/api/auth/profile/` | Get user profile | Yes |
| `PATCH` | `/api/auth/profile/` | Update profile | Yes |
| `POST` | `/api/auth/change-password/` | Change password | Yes |
| `POST` | `/api/auth/forgot-password/` | Send reset email | No |
| `POST` | `/api/auth/reset-password/` | Reset with token | No |

### Labs & Scenarios

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/api/scenarios/` | List all scenarios | Yes |
| `GET` | `/api/scenarios/<id>/` | Scenario detail | Yes |
| `GET` | `/api/technologies/` | List technologies | Yes |
| `POST` | `/api/labs/start/` | Start a lab session | Yes |
| `POST` | `/api/labs/stop/` | Stop active lab | Yes |
| `POST` | `/api/labs/validate/` | Validate lab solution | Yes |
| `GET` | `/api/progress/` | User progress | Yes |
| `GET` | `/api/leaderboard/` | Leaderboard | Yes |
| `GET` | `/api/hints/<scenario_id>/` | List hints | Yes |
| `POST` | `/api/hints/<hint_id>/unlock/` | Unlock a hint | Yes |

### Billing & Subscriptions

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/billing/subscribe/technology/` | Subscribe to a technology | Yes |
| `POST` | `/api/billing/cancel/` | Cancel a subscription | Yes |
| `GET` | `/api/billing/subscriptions/` | List user's subscriptions | Yes |
| `GET` | `/api/billing/subscription-logs/` | Subscription history log | Yes |
| `POST` | `/api/billing/razorpay/order/` | Create Razorpay payment order | Yes |
| `POST` | `/api/billing/razorpay/verify/` | Verify Razorpay payment signature | Yes |
| `POST` | `/api/billing/confirm-payment/` | Confirm payment (demo mode) | Yes |
| `GET` | `/api/billing/currency-rate/` | Get live currency conversion rate | Yes |
| `GET` | `/api/billing/status/` | Billing account status | Yes |

### Community

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/api/community/threads/` | List threads (filterable by technology) | Yes |
| `POST` | `/api/community/threads/` | Create a new thread | Yes |
| `GET` | `/api/community/threads/<id>/` | Thread detail with replies | Yes |
| `PATCH` | `/api/community/threads/<id>/` | Edit own thread | Yes |
| `DELETE` | `/api/community/threads/<id>/` | Delete own thread | Yes |
| `POST` | `/api/community/threads/<id>/replies/` | Reply to a thread | Yes |
| `PATCH` | `/api/community/replies/<id>/` | Edit own reply | Yes |
| `DELETE` | `/api/community/replies/<id>/` | Delete own reply | Yes |
| `POST` | `/api/community/threads/<id>/vote/` | Vote on a thread (upvote/downvote) | Yes |

### Ratings

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/api/ratings/rate/` | Rate a scenario (1-5 stars + review) | Yes |
| `GET` | `/api/ratings/` | List ratings (filterable by scenario) | Yes |

### Platform & Achievements

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/api/config/` | Platform config (emails, maintenance status) | No |
| `GET` | `/api/health/` | System health check | No |
| `GET` | `/api/achievements/` | List achievement badges | Yes |
| `GET` | `/api/achievements/certificate/` | List eligible technologies for certificates | Yes |
| `GET` | `/api/achievements/certificate/?technology=<slug>` | Generate & download certificate for a technology | Yes |
| `GET` | `/api/achievements/certificate/verify/?certificate_id=<id>` | Verify a certificate (public) | No |
| `GET` | `/api/notifications/` | User notifications | Yes |
| `POST` | `/api/contact/` | Contact form submission | No |
| `GET` | `/api/search/?q=<query>` | Search scenarios, technologies | Yes |

### Admin

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `GET` | `/api/admin/overview/` | Platform stats (revenue, subscribers, community) | Admin |
| `GET` | `/api/admin/health/` | System health (DB, Redis, RabbitMQ, Celery, Email, Cloud) | Admin |
| `GET` | `/api/admin/users/` | User management | Admin |
| `GET` | `/api/admin/scenarios/` | Scenario management | Admin |
| `POST` | `/api/admin/scenarios/` | Create scenario | Admin |
| `GET` | `/api/admin/labs/active/` | Active lab sessions | Admin |
| `POST` | `/api/admin/labs/<id>/terminate/` | Terminate a lab | Admin |
| `GET` | `/api/admin/activity/` | Activity feed | Admin |
| `GET` | `/api/admin/audit/` | Audit logs | Admin |
| `GET/POST` | `/api/admin/maintenance/` | Get/toggle maintenance mode | Admin |
| `GET` | `/api/admin/config/` | View platform configuration | Admin |
| `GET` | `/api/admin/inactive-users/` | List users inactive for 90+ days | Admin |
| `GET` | `/api/admin/subscriptions/` | View all subscription logs | Admin |
| `GET` | `/api/admin/threads/` | List all community threads | Admin |
| `PATCH` | `/api/admin/threads/<id>/` | Pin/lock a thread | Admin |
| `DELETE` | `/api/admin/threads/<id>/` | Delete a thread | Admin |

### WebSocket

| Endpoint | Description |
|---|---|
| `ws://host/ws/terminal/<session_id>/` | Terminal WebSocket (xterm.js ↔ container/SSH shell) |

---

## Admin Panel

Access the admin panel at `http://localhost:8080` → login as admin → Admin link in navigation.

### Admin Pages

| Page | Features |
|---|---|
| **Dashboard** | Revenue, paid subscribers, active labs, completion rates, community stats, maintenance status |
| **Users** | User list, roles, activity, ban/promote |
| **Scenarios** | CRUD scenarios, set infrastructure type (Docker/EC2/DO), validation scripts |
| **Active Labs** | Live labs with resource IDs, terminate individual or idle labs |
| **Activity Feed** | Real-time user actions |
| **Audit Logs** | Full API audit trail with export |
| **Subscriptions** | All subscription logs, revenue totals, search by user |
| **Threads** | Community thread moderation — pin, lock, or delete threads |
| **Settings** | Maintenance mode toggle, email configuration view, inactive users list |

### Creating Cloud Scenarios (Admin)

1. Go to Admin → Scenarios → Create New
2. Set **Infrastructure Type** to `AWS EC2` or `DigitalOcean`
3. Fill in the **Cloud Setup Script** (bash script that runs on instance boot to break things)
4. Optionally override the **AMI** (AWS) or **Image** (DO)
5. Set the **Validation Script** (bash script that checks if the user fixed the issue)
6. Save — users will now get a cloud instance when they start this scenario

---

## Troubleshooting

### Common Issues

#### 1. Containers won't start / health check failing

```bash
# Check container status
docker compose ps

# Check startup logs
docker compose logs backend
docker compose logs database

# Common cause: database not ready yet
# Fix: wait and restart
docker compose restart backend
```

#### 2. "relation does not exist" / migration errors

```bash
# Check migration status
docker compose exec backend python manage.py showmigrations

# Apply all migrations
docker compose exec backend python manage.py migrate

# If tables exist but migrations aren't tracked:
docker compose exec backend python manage.py migrate --fake-initial

# Force re-create migrations
docker compose exec backend python manage.py makemigrations accounts labs question_bank
docker compose exec backend python manage.py migrate
```

#### 3. "No such table: accounts_profile" or missing columns

```bash
# The startup.sh script handles this, but manually:
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate --run-syncdb

# Check if column exists
docker compose exec database psql -U fixitlab -d fixitlab -c "\d accounts_profile"
```

#### 4. Lab container fails to start

```bash
# Check if scenario images are built
docker images | grep fixitlab/scenario

# If missing, build them
make scenarios

# Check Docker socket is mounted
docker compose exec backend ls -la /var/run/docker.sock

# Check Docker network exists
docker network ls | grep fixitlab_labs
docker network create fixitlab_labs  # if missing
```

#### 5. WebSocket terminal not connecting

```bash
# Check Daphne is running (not gunicorn)
docker compose logs backend | grep -i daphne

# Check Redis (channel layer backend)
docker compose exec redis redis-cli ping   # should return PONG

# Check nginx WebSocket config
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://localhost:8080/ws/terminal/test/

# Common fix: restart gateway
docker compose restart gateway
```

#### 6. Emails not being received

```bash
# Development: check MailHog
curl -s http://localhost:8080/mailbox/   # access via gateway (needs basic auth)
# Or check MailHog API directly from backend container
docker compose exec backend curl -s http://mailhog:8025/api/v2/messages | python3 -m json.tool

# Production: verify SMTP settings
docker compose exec backend python -c "
from django.conf import settings
print('HOST:', settings.EMAIL_HOST)
print('PORT:', settings.EMAIL_PORT)
print('USER:', settings.EMAIL_HOST_USER)
print('TLS:', settings.EMAIL_USE_TLS)
"

# Send test email
docker compose exec backend python manage.py shell -c "
from django.core.mail import send_mail
send_mail('Test', 'Test email body', None, ['test@example.com'])
print('Sent!')
"
```

#### 7. Health endpoint returns 500 error

```bash
# Check the actual error
TOKEN=$(curl -s http://localhost:8080/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@fixitlab.com","password":"YOUR_PASSWORD"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/admin/health/ | head -50

# Common cause: missing import in views.py
# Fix: rebuild backend
docker compose up -d --build backend
docker compose restart celery_worker celery_beat gateway
```

#### 8. E2E tests failing

```bash
# Make sure all services are healthy
docker compose ps   # all should show "Up" + "healthy"

# Make sure scenario images exist
docker images | grep fixitlab/scenario

# Rebuild and restart everything
docker compose up -d --build
make scenarios
sleep 10   # wait for services to stabilize
bash test/e2e_full.sh
```

#### 9. Cloud labs (EC2/DO) not launching

```bash
# Check credentials are configured
docker compose exec backend python manage.py shell -c "
from django.conf import settings
print('AWS Key:', bool(settings.AWS_ACCESS_KEY_ID))
print('AWS Region:', settings.AWS_REGION)
print('DO Token:', bool(settings.DO_API_TOKEN))
"

# Check admin health endpoint for cloud provider status
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/admin/health/ \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('cloud_providers',{}), indent=2))"

# Common issues:
# - Security group doesn't allow SSH (port 22) from backend
# - SSH key pair name doesn't match
# - PEM file not mounted into container
# - Subnet doesn't have internet access (needs NAT gateway or public IP)
```

#### 10. "Permission denied" Docker socket errors

```bash
# Check socket permissions
ls -la /var/run/docker.sock

# Fix on Linux:
sudo chmod 666 /var/run/docker.sock
# Or add the container user to docker group

# On macOS Docker Desktop: this usually works out of the box
```

#### 11. RabbitMQ connection refused

```bash
# Check RabbitMQ is healthy
docker compose exec rabbitmq rabbitmq-diagnostics -q ping

# Check Celery broker URL
docker compose exec celery_worker env | grep CELERY_BROKER_URL

# Restart RabbitMQ + dependents
docker compose restart rabbitmq
sleep 10
docker compose restart celery_worker celery_beat backend
```

#### 12. Frontend build fails

```bash
# Check node_modules
docker compose exec frontend ls node_modules/ | head

# Clean rebuild
docker compose build --no-cache frontend
docker compose up -d frontend
docker compose restart gateway
```

### Useful Debug Commands

```bash
# Django shell
docker compose exec backend python manage.py shell

# Check database tables
docker compose exec database psql -U fixitlab -d fixitlab -c "\dt"

# Check database size
docker compose exec database psql -U fixitlab -d fixitlab -c "
  SELECT pg_size_pretty(pg_database_size('fixitlab'));"

# View all running lab containers
docker ps --filter "name=fixitlab-lab-"

# Kill all lab containers
docker ps -q --filter "name=fixitlab-lab-" | xargs -r docker rm -f

# Check Celery workers
docker compose exec celery_worker celery -A config inspect active

# Check Celery scheduled tasks
docker compose exec celery_worker celery -A config inspect scheduled

# View Redis keys
docker compose exec redis redis-cli keys '*'

# Full system cleanup (CAUTION: wipes everything)
docker compose down -v --rmi local
docker system prune -af
```

---

## Makefile Commands

```bash
make help              # Show all available commands

# Development
make dev               # Start all services (attached, with logs)
make up                # Start all services (detached)
make down              # Stop all services
make logs              # Tail logs for all services
make restart           # Restart all services
make shell             # Open Django shell
make dbshell           # Open PostgreSQL shell

# Database
make migrate           # Run Django migrations
make makemigrations    # Create new migration files
make seed              # Seed database
make superuser         # Create superuser interactively

# Scenarios
make scenarios         # Build all scenario Docker images

# Testing
make test              # Run Django unit tests
make test-e2e          # Run E2E test container
make lint              # Lint backend code with flake8

# Build & Push (production)
make build             # Build all Docker images
make push              # Push all images to registry
make deploy            # Deploy to Kubernetes
make deploy-migrate    # Run migrations on K8s cluster

# Cleanup
make clean             # Remove all containers, volumes, images
make clean-labs        # Kill all running lab containers
```

---

## Security Notes (Production)

- [ ] Generate a unique `DJANGO_SECRET_KEY` (use `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] Set `DJANGO_DEBUG=False`
- [ ] Set `DJANGO_ALLOWED_HOSTS` to your domain only
- [ ] Set `CORS_ALLOWED_ORIGINS` to your domain only
- [ ] Use strong `POSTGRES_PASSWORD`
- [ ] Use dedicated IAM user for AWS with minimal permissions
- [ ] Enable HTTPS/TLS via cert-manager or Cloudflare
- [ ] Set up database backups (RDS automated or pg_dump cron)
- [ ] Configure Sentry for error tracking: add `SENTRY_DSN` to `.env`
- [ ] Review rate limits in `gateway/nginx.conf`
- [ ] Restrict MailHog access (production should use real SMTP, not MailHog)
- [ ] Store SSH keys securely (use AWS Secrets Manager or Vault in production)

---

## Documentation

| Document | Description |
|---|---|
| [START.md](START.md) | Quick start guide — get running in under 5 minutes |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Production deployment (DigitalOcean, AWS, Kubernetes) |
| [docs/architecture.md](docs/architecture.md) | System architecture details |
| [docs/api.md](docs/api.md) | API documentation |
| [docs/ui-guidelines.md](docs/ui-guidelines.md) | UI/UX design guidelines |
| [env.production.example](env.production.example) | Production environment template |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run the full test suite: `bash test/e2e_full.sh`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Open a Pull Request

---

## License

Copyright © 2026 FixitLab. All rights reserved.
