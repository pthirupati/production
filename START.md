# FixitLab — Complete Deployment Guide (A to Z)

Everything you need to deploy FixitLab from scratch on a fresh server and make it fully functional with payments, email, SSL, and cloud labs.

---

## Table of Contents

1. [Prerequisites & Tools](#1-prerequisites--tools)
2. [Local Development Setup](#2-local-development-setup)
3. [Server Setup (VPS)](#3-server-setup-vps)
4. [Clone & Configure the Project](#4-clone--configure-the-project)
5. [Create Third-Party Accounts](#5-create-third-party-accounts)
   - [5A. Razorpay (Payments)](#5a-razorpay-payments)
   - [5B. Gmail App Password (Email)](#5b-gmail-app-password-email)
   - [5C. Domain & DNS](#5c-domain--dns)
   - [5D. AWS EC2 (Cloud Labs — Optional)](#5d-aws-ec2-cloud-labs--optional)
   - [5E. GitHub OAuth (Optional)](#5e-github-oauth-optional)
   - [5F. Google OAuth (Optional)](#5f-google-oauth-optional)
6. [Fill In the Environment File](#6-fill-in-the-environment-file)
7. [Build Scenario Docker Images](#7-build-scenario-docker-images)
8. [Deploy the Application](#8-deploy-the-application)
9. [Post-Deploy Setup](#9-post-deploy-setup)
10. [Verify Everything Works](#10-verify-everything-works)
11. [Backups & Maintenance](#11-backups--maintenance)
12. [Updating the Application](#12-updating-the-application)
13. [Troubleshooting](#13-troubleshooting)
14. [Cost Summary](#14-cost-summary)

---

## 1. Prerequisites & Tools

### On Your Local Machine (Development)

| Tool | Purpose | Install |
|------|---------|---------|
| **Docker Desktop** | Runs all 9 services locally | [docker.com/get-docker](https://docs.docker.com/get-docker/) |
| **Docker Compose v2** | Multi-container orchestration | Included with Docker Desktop |
| **Git** | Version control | `brew install git` (Mac) / `apt install git` (Linux) |
| **Node.js 20+** | Frontend build (optional, for local dev outside Docker) | `brew install node` |
| **Python 3.12+** | Backend dev (optional, for local dev outside Docker) | `brew install python` |
| **AWS CLI** | Cloud lab management (optional) | `brew install awscli` |

### On Your Production Server

| Tool | Purpose | Auto-installed by deploy script |
|------|---------|------|
| **Docker** | Container runtime | Yes |
| **Docker Compose v2** | Orchestration | Yes |
| **UFW** | Firewall | Yes |
| **Fail2Ban** | Brute-force protection | Yes |
| **curl** | Health checks | Yes |

### Server Requirements (Minimum)

| Spec | Minimum | Recommended |
|------|---------|-------------|
| **OS** | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |
| **CPU** | 2 vCPUs | 4 vCPUs |
| **RAM** | 4 GB | 8 GB |
| **Storage** | 40 GB SSD | 80 GB SSD |
| **Network** | Public IPv4 | Static IP |

### Recommended VPS Providers

| Provider | Plan | Cost/month |
|----------|------|------------|
| **DigitalOcean** | Droplet 4GB | $24/mo |
| **AWS EC2** | t3.medium | ~$30/mo |
| **Hetzner** | CX31 | €8.50/mo (best value) |
| **Contabo** | VPS S SSD | €5.99/mo |

---

## 2. Local Development Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/your-org/fixitlab.git
cd fixitlab/fixitlab-main
```

### Step 2 — Create Local Environment File

```bash
cp env.production.example .env
```

Edit `.env` with these **minimum** values for local development:

```env
# Django Core
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_SECRET_KEY=any-random-string-at-least-50-characters-long-for-dev
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=*

# PostgreSQL (works with bundled container)
POSTGRES_DB=fixitlab
POSTGRES_USER=fixitlab
POSTGRES_PASSWORD=fixitlab_dev_password
POSTGRES_HOST=database
POSTGRES_PORT=5432

# Redis (no password in dev)
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=

# Celery (no password for dev RabbitMQ)
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

# URLs
CORS_ALLOWED_ORIGINS=http://localhost,http://localhost:80,http://localhost:5173,http://localhost:8080
CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://localhost,http://localhost:5173
FRONTEND_URL=http://localhost:8080
SITE_URL=http://localhost:8080

# Email — leave EMAIL_HOST_USER empty to use MailHog (dev email catcher)
EMAIL_HOST=mailhog
EMAIL_PORT=1025
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=

# Superuser (auto-created on first boot)
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@fixitlab.com
SUPERUSER_PASSWORD=YourPassword123

# Razorpay — leave empty for demo/token mode (no real payments)
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=

# Lab Provisioning
LAB_PROVIDER=docker
LAB_MAX_DURATION_MINUTES=30
DOCKER_SOCKET=unix:///var/run/docker.sock
DOCKER_NETWORK=fixitlab_labs
DOCKER_SCENARIO_IMAGE_PREFIX=fixitlab/scenario-
DOCKER_CONTAINER_MEMORY_LIMIT=512m
DOCKER_CONTAINER_CPU_LIMIT=1.0

# Currency
DEFAULT_CURRENCY=INR

# Maintenance
MAINTENANCE_MODE=false
```

### Step 3 — Start All Services

```bash
# Build and start all 9 services (first run takes 3-5 minutes)
docker compose up -d --build
```

This starts:

| Service | Purpose | Port |
|---|---|---|
| **Gateway** (Nginx) | Reverse proxy, rate limiting | **:8080** (main entry) |
| **Frontend** (React + Vite) | SPA with Hot Module Reload | 5173 (internal) |
| **Backend** (Django + Daphne) | REST API + WebSocket | 8000 (internal) |
| **Celery Worker** | Background tasks | — |
| **Celery Beat** | Scheduled tasks | — |
| **PostgreSQL 15** | Primary database | 5432 (internal) |
| **Redis 7** | Cache + WebSocket layer | 6379 (internal) |
| **RabbitMQ 3** | Celery task broker | 5672 (internal) |
| **MailHog** | Email capture (dev only) | 8025 (internal) |

### Step 4 — Build Scenario Images

```bash
make scenarios
```

### Step 5 — Verify Everything Is Running

```bash
docker compose ps                                    # All should show "healthy"
curl http://localhost:8080/api/health/               # Should return {"status":"ok",...}
```

### Step 6 — Access the Application

| What | URL |
|---|---|
| **FixitLab App** | [http://localhost:8080](http://localhost:8080) |
| **Admin Panel** | Login → click "Admin" in navbar |
| **Django Admin** | [http://localhost:8080/django-admin/](http://localhost:8080/django-admin/) |
| **MailHog (emails)** | [http://localhost:8080/mailbox/](http://localhost:8080/mailbox/) |
| **API Health** | [http://localhost:8080/api/health/](http://localhost:8080/api/health/) |

Login with: `admin@fixitlab.com` / `YourPassword123` (or whatever you set in `.env`).

### Development Workflow

```bash
# Frontend: changes in frontend/src/ auto-reload via Vite HMR (no rebuild!)
# Backend: code is baked into Docker image — rebuild after changes:
docker compose up -d --build backend
docker compose restart celery_worker celery_beat

# Run 64 unit tests
docker compose exec backend python manage.py test --settings=config.test_settings

# Django shell
docker compose exec backend python manage.py shell

# Database shell
docker compose exec database psql -U fixitlab -d fixitlab

# View logs
docker compose logs -f backend

# Stop everything
docker compose down
```

### Payment Flow in Demo Mode (No Razorpay Keys)

When `RAZORPAY_KEY_ID` is empty, the platform runs in **demo mode**:
1. User clicks **"Buy Now"** on Pricing → creates order → gets `payment_token`
2. Selects payment method (UPI, Card, Net Banking, Wallet)
3. Clicks **"Complete Payment"** → subscription activates immediately
4. No real money charged — perfect for development

---

## 3. Server Setup (VPS)

### 3.1 Create a VPS

Pick any provider from Section 1. Choose **Ubuntu 22.04 LTS**. Note the server's **public IP address**.

### 3.2 SSH Into the Server

```bash
ssh root@YOUR_SERVER_IP
```

### 3.3 Update System & Install Docker

```bash
# Update packages
apt-get update -y && apt-get upgrade -y

# Install essential tools
apt-get install -y curl git ufw fail2ban

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# Verify
docker --version          # Should show 24.x+
docker compose version    # Should show v2.x+
```

### 3.4 Configure Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP (ACME challenge + redirect to HTTPS)
ufw allow 443/tcp    # HTTPS
ufw --force enable
```

### 3.5 Configure Fail2Ban (Brute-Force Protection)

```bash
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = 22

[nginx-http-auth]
enabled = true
port = 80,443
EOF

systemctl enable fail2ban && systemctl restart fail2ban
```

---

## 4. Clone & Configure the Project

### 4.1 Get the Code on the Server

**Option A — Git Clone:**
```bash
cd /opt
git clone https://YOUR_REPO_URL fixitlab
cd /opt/fixitlab
```

**Option B — Upload from Your Laptop:**
```bash
# Run this from YOUR LOCAL MACHINE (not the server)
rsync -avz --exclude='node_modules' --exclude='.git' --exclude='__pycache__' \
  ./fixitlab-main/ root@YOUR_SERVER_IP:/opt/fixitlab/
```

### 4.2 Create the Production Environment File

```bash
cd /opt/fixitlab
cp env.production.example .env.production
```

Now fill in `.env.production` — continue to Section 5 to set up third-party accounts first.

---

## 5. Create Third-Party Accounts

### 5A. Razorpay (Payments)

Razorpay handles technology subscription payments (INR). **Required for real payments.**

#### Step 1: Create Razorpay Account
1. Go to [https://dashboard.razorpay.com/signup](https://dashboard.razorpay.com/signup)
2. Sign up with your email and phone number
3. Complete KYC verification:
   - **Business Type**: Individual / Sole Proprietor
   - **Business Category**: Education → E-learning
   - **Website/App URL**: `https://fixitlab.in`
   - Documents: PAN card, bank account details, address proof
4. KYC approval takes 1-3 business days

#### Step 2: Get API Keys
1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com)
2. Go to **Settings → API Keys → Generate Key**
3. Copy both values immediately:
   - **Key ID** → e.g., `rzp_live_xxxxxxxxxxxx` (starts with `rzp_live_` for production)
   - **Key Secret** → shown **only once** — save it securely!

#### Step 3: Test Mode Keys (For Testing First)
1. Toggle **Test Mode** in Razorpay Dashboard (top-left toggle)
2. Generate keys in test mode → they start with `rzp_test_`
3. Test card number: `4111 1111 1111 1111`, any future expiry, any CVV, OTP: `1234`

#### Step 4: Configure Webhook (Recommended)
1. Go to **Settings → Webhooks → Add New Webhook**
2. **Webhook URL**: `https://fixitlab.in/api/billing/webhook/`
3. **Active Events**: Select:
   - `payment.captured`
   - `payment.failed`
   - `refund.created`
4. Copy the **Webhook Secret**

#### Razorpay Flow in FixitLab:
```
User clicks "Subscribe" on Pricing page
  → Frontend calls POST /api/billing/razorpay/create-order/
  → Backend creates Razorpay order (amount in paise, e.g., ₹299 = 29900)
  → Razorpay checkout popup opens in browser
  → User pays via UPI / Card / Net Banking / Wallet
  → Razorpay sends payment_id back to frontend
  → Frontend calls POST /api/billing/confirm-payment/
  → Backend verifies payment signature with Razorpay API
  → Technology subscription activated for 30 days
```

#### What Goes in `.env.production`:
```env
RAZORPAY_KEY_ID=rzp_live_YOUR_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_KEY_SECRET
```

> **Pricing Configuration**: Technology subscription prices are set in the Django admin panel under **Technologies**. Each technology has a `price_inr` field (e.g., ₹299, ₹499). Free technologies have `is_free=True`.

---

### 5B. Gmail App Password (Email)

FixitLab sends emails for: **OTP verification, welcome emails, password reset, payment receipts, certificates**.

#### Step 1: Enable 2-Factor Authentication on Gmail
1. Go to [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Under **Signing in to Google**, enable **2-Step Verification**
3. Follow the setup wizard

#### Step 2: Generate App Password
1. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Under **App name**, type `FixitLab`
3. Click **Create**
4. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
5. **Remove the spaces** → `abcdefghijklmnop`

#### Step 3: Set Up Contact Email Addresses
Create these email addresses (can be aliases of same Gmail):
- `fixitlab.admin@gmail.com` — Primary admin notifications
- `fixitlab.payment@gmail.com` — Payment notifications
- `fixitlab.techsupport@gmail.com` — Support tickets

#### What Goes in `.env.production`:
```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=fixitlab.admin@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
PRIMARY_EMAIL=fixitlab.admin@gmail.com
PAYMENT_EMAIL=fixitlab.payment@gmail.com
SUPPORT_EMAIL=fixitlab.techsupport@gmail.com
```

> **Alternative SMTP Providers** (higher volume):
> - **SendGrid**: 100 emails/day free → [sendgrid.com](https://sendgrid.com)
> - **Amazon SES**: $0.10 per 1000 emails → [aws.amazon.com/ses](https://aws.amazon.com/ses)
> - **Mailgun**: 5000 emails/month free → [mailgun.com](https://mailgun.com)

---

### 5C. Domain & DNS

#### Step 1: Buy a Domain
Recommended registrars:
- [Namecheap](https://namecheap.com) — ~₹800/year for `.in`
- [GoDaddy](https://godaddy.com) — ~₹600/year for `.in`
- [Cloudflare Registrar](https://dash.cloudflare.com) — cheapest, at-cost pricing

#### Step 2: Point DNS to Your Server
Add these DNS records at your domain registrar:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| **A** | `@` | `YOUR_SERVER_IP` | 300 |
| **A** | `www` | `YOUR_SERVER_IP` | 300 |

Example for `fixitlab.in`:
```
A    fixitlab.in       → 65.2.123.45
A    www.fixitlab.in   → 65.2.123.45
```

#### Step 3: Verify DNS Propagation
```bash
# Wait 5-30 minutes, then verify:
dig +short fixitlab.in
# Should return your server IP

nslookup fixitlab.in
# Should show your server IP
```

> DNS can take up to 48 hours globally, but usually works within 15 minutes.

#### What Goes in `.env.production`:
```env
DJANGO_ALLOWED_HOSTS=fixitlab.in,www.fixitlab.in
CORS_ALLOWED_ORIGINS=https://fixitlab.in,https://www.fixitlab.in
CSRF_TRUSTED_ORIGINS=https://fixitlab.in,https://www.fixitlab.in
FRONTEND_URL=https://fixitlab.in
SITE_URL=https://fixitlab.in
```

---

### 5D. AWS EC2 (Cloud Labs — Optional)

**Only needed** if you want to run labs on real AWS EC2 instances (not just Docker containers). Skip this for a basic deployment — Docker-based labs work without AWS.

#### Step 1: Create an AWS Account
1. Go to [https://aws.amazon.com](https://aws.amazon.com) → **Create an AWS Account**
2. Add a payment method (credit card/debit card)
3. Choose **Basic (Free)** support plan

#### Step 2: Create an IAM User
1. Go to **IAM → Users → Create User**
2. User name: `fixitlab-provisioner`
3. Attach policy: `AmazonEC2FullAccess`
4. Go to **Security Credentials → Create Access Key**
5. Choose **Application running outside AWS**
6. Copy `Access Key ID` and `Secret Access Key`

#### Step 3: Create a Security Group
1. Go to **EC2 → Security Groups → Create Security Group**
2. Name: `fixitlab-labs`
3. VPC: default VPC
4. **Inbound rules**:
   - SSH (port 22) → Source: your server IP `/32` (or `0.0.0.0/0` for testing)
   - HTTP (port 80) → Source: `0.0.0.0/0` (for web server scenarios)
5. Copy the **Security Group ID** (e.g., `sg-038e2edfb6d8aac56`)

#### Step 4: Get a Public Subnet ID
```bash
aws ec2 describe-subnets --region ap-south-1 \
  --query "Subnets[?MapPublicIpOnLaunch==\`true\`].SubnetId" --output text
# Copy the first subnet ID, e.g., subnet-0c4fe29dad449fbd2
```

#### Step 5: Create an SSH Key Pair
```bash
# Generate an Ed25519 key pair (on your local machine or server)
ssh-keygen -t ed25519 -f fixitlab-labs -C "fixitlab-labs" -N ""

# Install AWS CLI if needed
# Mac: brew install awscli
# Ubuntu: apt install awscli

# Import the public key into AWS
aws ec2 import-key-pair \
  --key-name fixitlab-labs \
  --public-key-material fileb://fixitlab-labs.pub \
  --region ap-south-1

# Copy the private key to the scripts/ directory
cp fixitlab-labs /opt/fixitlab/scripts/fixitlab.pem
chmod 600 /opt/fixitlab/scripts/fixitlab.pem
```

#### Step 6: Find the Ubuntu AMI for Your Region
```bash
aws ec2 describe-images --region ap-south-1 \
  --owners 099720109477 \
  --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
  --query "Images | sort_by(@, &CreationDate) | [-1].ImageId" --output text
# e.g., ami-03793655b06c6e29a
```

#### What Goes in `.env.production`:
```env
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=ap-south-1
AWS_LAB_BASE_AMI=ami-03793655b06c6e29a
AWS_LAB_INSTANCE_TYPE=t3.micro
AWS_LAB_SUBNET_ID=subnet-xxxxxxxx
AWS_LAB_SECURITY_GROUP_ID=sg-xxxxxxxx
AWS_LAB_KEY_PAIR=fixitlab-labs
AWS_LAB_KEY_PEM=
AWS_LAB_KEY_PATH=/scripts/fixitlab.pem
```

#### AWS Cost for Cloud Labs:
- **t3.micro**: $0.0104/hour (~₹0.87/hour) — pay only while labs are running
- Auto-terminated after lab session ends
- Cleanup task terminates orphaned instances every 5 minutes
- Monthly cost depends on usage: ~₹400-1500/month for moderate use

---

### 5E. GitHub OAuth (Optional)

Allows users to sign in with their GitHub account.

#### Step 1: Create OAuth App
1. Go to [https://github.com/settings/developers](https://github.com/settings/developers)
2. Click **New OAuth App**
3. Fill in:
   - **Application name**: `FixitLab`
   - **Homepage URL**: `https://fixitlab.in`
   - **Authorization callback URL**: `https://fixitlab.in/api/auth/github/callback/`
4. Click **Register application**
5. Copy **Client ID**
6. Click **Generate a new client secret** → Copy it

#### What Goes in `.env.production`:
```env
GITHUB_CLIENT_ID=Ov23liXXXXXXXXXXXXXX
GITHUB_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### 5F. Google OAuth (Optional)

Allows users to sign in with their Google account.

#### Step 1: Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click **New Project** → name it `FixitLab`
3. Select the project

#### Step 2: Configure OAuth Consent Screen
1. Go to **APIs & Services → OAuth Consent Screen**
2. **User type**: External → Create
3. **App name**: FixitLab
4. **Support email**: your email
5. **Authorized domain**: `fixitlab.in`
6. **Developer contact email**: your email
7. Save and continue
8. **Scopes**: Add `openid`, `email`, `profile`
9. Save and continue → **Publish App** (move from Testing → Production)

#### Step 3: Create OAuth Credentials
1. Go to **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
2. **Application type**: Web application
3. **Name**: FixitLab
4. **Authorized JavaScript origins**: `https://fixitlab.in`
5. **Authorized redirect URIs**: `https://fixitlab.in/api/auth/google/callback/`
6. Click **Create**
7. Copy **Client ID** and **Client Secret**

#### What Goes in `.env.production`:
```env
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxx
```

---

## 6. Fill In the Environment File

Now that you have all accounts, edit `.env.production` on your **server**:

```bash
nano /opt/fixitlab/.env.production
```

### Generate Strong Passwords

Run these on your server:

```bash
# Django secret key (50+ chars)
python3 -c "import secrets; print('DJANGO_SECRET_KEY=' + secrets.token_urlsafe(50))"

# PostgreSQL password
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"

# Redis password
python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))"

# RabbitMQ password
python3 -c "import secrets; print('RABBITMQ_PASS=' + secrets.token_urlsafe(24))"

# Superuser password
python3 -c "import secrets; print('SUPERUSER_PASSWORD=' + secrets.token_urlsafe(16))"
```

### Complete `.env.production` Template

```env
# ═══════════════════════════════════════════════════
#  FixitLab — Production Environment Variables
#  SECURITY: Never commit this file to version control!
# ═══════════════════════════════════════════════════

# ── Django Core ──
DJANGO_SETTINGS_MODULE=config.settings
DJANGO_SECRET_KEY=PASTE_GENERATED_KEY_HERE
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=fixitlab.in,www.fixitlab.in

# ── PostgreSQL ──
POSTGRES_DB=fixitlab
POSTGRES_USER=fixitlab
POSTGRES_PASSWORD=PASTE_GENERATED_PASSWORD_HERE
POSTGRES_HOST=database
POSTGRES_PORT=5432

# ── Redis ──
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=PASTE_GENERATED_PASSWORD_HERE

# ── Celery (RabbitMQ) ──
# ⚠️  The password in the URL MUST match RABBITMQ_PASS
CELERY_BROKER_URL=amqp://fixitlab:PASTE_RABBIT_PASSWORD@rabbitmq:5672//
RABBITMQ_USER=fixitlab
RABBITMQ_PASS=PASTE_RABBIT_PASSWORD

# ── CORS & CSRF ──
CORS_ALLOWED_ORIGINS=https://fixitlab.in,https://www.fixitlab.in
CSRF_TRUSTED_ORIGINS=https://fixitlab.in,https://www.fixitlab.in

# ── Frontend ──
FRONTEND_URL=https://fixitlab.in
SITE_URL=https://fixitlab.in

# ── SSL ──
SECURE_SSL_REDIRECT=true

# ── Email (Gmail App Password) ──
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=fixitlab.admin@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password

# ── Contact Emails ──
PRIMARY_EMAIL=fixitlab.admin@gmail.com
PAYMENT_EMAIL=fixitlab.payment@gmail.com
SUPPORT_EMAIL=fixitlab.techsupport@gmail.com

# ── Razorpay (REQUIRED for real payments) ──
RAZORPAY_KEY_ID=rzp_live_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxx

# ── Currency ──
DEFAULT_CURRENCY=INR
ENABLE_CURRENCY_CONVERSION=true

# ── Lab Provisioning ──
LAB_PROVIDER=docker
LAB_MAX_DURATION_MINUTES=60
LAB_CLEANUP_INTERVAL_MINUTES=5
DOCKER_SOCKET=unix:///var/run/docker.sock
DOCKER_NETWORK=fixitlab_labs
DOCKER_SCENARIO_IMAGE_PREFIX=fixitlab/scenario-
DOCKER_CONTAINER_MEMORY_LIMIT=512m
DOCKER_CONTAINER_CPU_LIMIT=1.0

# ── AWS (leave empty if not using cloud labs) ──
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
AWS_LAB_BASE_AMI=ami-03793655b06c6e29a
AWS_LAB_INSTANCE_TYPE=t3.micro
AWS_LAB_SUBNET_ID=
AWS_LAB_SECURITY_GROUP_ID=
AWS_LAB_KEY_PAIR=fixitlab-labs
AWS_LAB_KEY_PEM=
AWS_LAB_KEY_PATH=/scripts/fixitlab.pem

# ── DigitalOcean (leave empty if not using) ──
DO_API_TOKEN=
DO_SSH_KEY_ID=
DO_SSH_KEY_PEM=
DO_SSH_KEY_PATH=
DO_REGION=nyc1
DO_SIZE=s-1vcpu-1gb

# ── Superuser (created automatically on first boot) ──
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=your-admin@email.com
SUPERUSER_PASSWORD=PASTE_GENERATED_PASSWORD_HERE

# ── Social OAuth (leave empty to disable) ──
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# ── Stripe (optional — legacy) ──
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRO_PRICE_ID=
STRIPE_TEAM_PRICE_ID=

# ── Business Details (shown on invoices/receipts) ──
BUSINESS_NAME=FixitLab
BUSINESS_ADDRESS=
BUSINESS_GSTIN=
BUSINESS_PAN=

# ── Maintenance ──
MAINTENANCE_MODE=false
MAINTENANCE_MESSAGE=We are performing scheduled maintenance. Please check back soon.
```

> **Important**: The RabbitMQ password in `CELERY_BROKER_URL` must exactly match `RABBITMQ_PASS`.

---

## 7. Build Scenario Docker Images

Scenarios are Docker images that create broken Linux environments for users to fix.

```bash
cd /opt/fixitlab

# Build all scenario images
for dir in scenarios/*/; do
  for sd in "$dir"*/; do
    if [ -f "$sd/Dockerfile" ]; then
      name=$(basename "$sd")
      echo "Building fixitlab/scenario-$name..."
      docker build -t "fixitlab/scenario-$name" "$sd"
    fi
  done
done

# Or use the Makefile shortcut:
make scenarios
```

This builds images like:
- `fixitlab/scenario-broken-nginx`
- `fixitlab/scenario-broken-cron`
- `fixitlab/scenario-disk-full`
- `fixitlab/scenario-ssh-lockout`
- `fixitlab/scenario-zombie-process`
- `fixitlab/scenario-password-change-broken`
- `fixitlab/scenario-dns-resolution-broken`

Verify they are built:
```bash
docker images | grep fixitlab/scenario
```

---

## 8. Deploy the Application

### Option A: Automated Deploy (Recommended)

```bash
cd /opt/fixitlab
chmod +x scripts/deploy.sh
sudo ./scripts/deploy.sh
```

The script automatically:
1. Installs Docker, UFW, Fail2Ban
2. Configures firewall (ports 22, 80, 443)
3. Builds scenario Docker images
4. Gets SSL certificate from Let's Encrypt
5. Starts all 9 services using `docker-compose.prod.yml`
6. Waits for health checks to pass
7. Verifies HTTPS

### Option B: Manual Step-by-Step

```bash
cd /opt/fixitlab

# 1. Build and start all services
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 2. Wait for backend health (takes 30-60 seconds on first start)
echo "Waiting for backend..."
until docker compose -f docker-compose.prod.yml exec -T backend python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" 2>/dev/null; do
  sleep 5
done
echo "Backend is healthy!"

# 3. Check all services
docker compose -f docker-compose.prod.yml ps

# Expected output — 9 services (8 + certbot):
#   gateway         running (healthy)
#   frontend-prod   running
#   backend         running (healthy)
#   celery_worker   running
#   celery_beat     running
#   database        running (healthy)
#   redis           running (healthy)
#   rabbitmq        running (healthy)
#   certbot         running
```

### Get SSL Certificate (If Automated Deploy Didn't Run)

```bash
# 1. Make sure ports 80 + 443 are free and DNS points to this server
# 2. Start a temp nginx for the ACME challenge
mkdir -p /tmp/certbot-www
docker run -d --name certbot-nginx -p 80:80 \
  -v /tmp/certbot-www:/var/www/certbot \
  nginx:alpine

# 3. Request certificate from Let's Encrypt
docker run --rm \
  -v certbot_certs:/etc/letsencrypt \
  -v /tmp/certbot-www:/var/www/certbot \
  certbot/certbot certonly \
  --webroot -w /var/www/certbot \
  -d fixitlab.in -d www.fixitlab.in \
  --email admin@fixitlab.in \
  --agree-tos --non-interactive

# 4. Cleanup temp container
docker rm -f certbot-nginx
rm -rf /tmp/certbot-www

# 5. Start the full stack with SSL
docker compose -f docker-compose.prod.yml up -d
```

> **SSL auto-renewal**: The `certbot` sidecar container renews certificates every 12 hours automatically. No cron needed.

---

## 9. Post-Deploy Setup

### 9.1 Verify Superuser Was Created

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.filter(is_superuser=True).first()
print(f'Superuser: {u.username} ({u.email})')
"
```

### 9.2 Access Admin Panel

1. Go to `https://fixitlab.in/admin` (React admin panel — full-featured)
2. Log in with your superuser credentials
3. Verify: **Scenarios** tab shows all seeded scenarios
4. Verify: **Users** tab is accessible

Django admin (raw database admin): `https://fixitlab.in/django-admin/`

### 9.3 Verify Scenarios Are Seeded

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "
from apps.question_bank.models import Scenario, Technology
for t in Technology.objects.all():
    count = Scenario.objects.filter(technology=t).count()
    print(f'  {t.name}: {count} scenarios')
print(f'Total: {Scenario.objects.count()} scenarios')
"
```

### 9.4 Test Email Delivery

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "
from django.core.mail import send_mail
send_mail('FixitLab Test', 'If you see this, email is working!', None, ['your-email@gmail.com'])
print('Test email sent — check your inbox (and spam folder)')
"
```

### 9.5 Test Razorpay Integration

1. Log in to the website
2. Go to **Pricing** page
3. Click **Subscribe** on any technology
4. Razorpay checkout popup should open
5. If using **test keys** (`rzp_test_`), use:
   - Card: `4111 1111 1111 1111`
   - Expiry: any future date (e.g., `12/30`)
   - CVV: any 3 digits (e.g., `123`)
   - OTP: `1234`

### 9.6 Test a Lab

1. Subscribe to a technology (or use a free scenario like "Fix the Broken Nginx")
2. Click **Start Challenge**
3. Terminal should open with the xterm.js interface showing the welcome banner
4. Run commands to fix the broken scenario
5. Click **Check Solution** to validate
6. Click **Stop Lab** when done

---

## 10. Verify Everything Works

### Health Check URLs

| URL | Expected |
|-----|----------|
| `https://fixitlab.in` | React SPA loads |
| `https://fixitlab.in/api/health/` | `{"status": "ok", ...}` |
| `https://fixitlab.in/django-admin/` | Django admin login page |

### Feature Checklist

| Feature | How to Test | Works? |
|---------|-------------|--------|
| **User Registration** | Register → OTP → Verify | ☐ |
| **Email Delivery** | Check inbox for OTP/welcome email | ☐ |
| **Login** | Login with email/password | ☐ |
| **GitHub/Google OAuth** | Login with social accounts | ☐ |
| **View Scenarios** | Browse /scenarios page | ☐ |
| **Pricing Page** | View /pricing, see plans | ☐ |
| **Razorpay Payment** | Subscribe to a technology | ☐ |
| **Start Docker Lab** | Start a free scenario | ☐ |
| **Terminal (xterm.js)** | Type commands in the web terminal | ☐ |
| **Lab Validation** | Click "Check Solution" | ☐ |
| **Hints** | Reveal hints during a lab | ☐ |
| **Leaderboard** | View /leaderboard | ☐ |
| **Admin Panel** | Access /admin (staff users) | ☐ |
| **Certificates** | Complete all scenarios → download cert | ☐ |
| **Stop Lab** | Stop a running lab | ☐ |
| **Cloud Lab (AWS)** | Start a cloud scenario (if AWS configured) | ☐ |

### Run Backend Tests

```bash
docker compose -f docker-compose.prod.yml exec backend \
  python manage.py test --settings=config.test_settings -v 0
# Expected: Ran 64 tests ... OK
```

---

## 11. Backups & Maintenance

### 11.1 Automated Daily Backups

```bash
# Set up daily backups at 3 AM
chmod +x /opt/fixitlab/scripts/backup.sh
mkdir -p /opt/fixitlab/backups

# Add to crontab
crontab -e
# Add this line:
0 3 * * * /opt/fixitlab/scripts/backup.sh >> /var/log/fixitlab-backup.log 2>&1
```

The backup script saves:
- **PostgreSQL dump**: `backups/db_YYYYMMDD_HHMMSS.sql.gz`
- **Redis snapshot**: `backups/redis_YYYYMMDD_HHMMSS.rdb`
- Auto-deletes backups older than 30 days

### 11.2 Manual Database Backup & Restore

```bash
# Backup
docker compose -f docker-compose.prod.yml exec -T database \
  pg_dump -U fixitlab fixitlab | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore
gunzip -c backup_20260401.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T database \
  psql -U fixitlab fixitlab
```

### 11.3 SSL Certificate Renewal

Auto-handled by the `certbot` container. To manually renew:
```bash
docker compose -f docker-compose.prod.yml exec certbot certbot renew --quiet
docker compose -f docker-compose.prod.yml restart gateway
```

### 11.4 Log Rotation

```bash
cat > /etc/logrotate.d/fixitlab << 'EOF'
/var/log/fixitlab-*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

### 11.5 Docker Cleanup

```bash
# Remove unused images and containers
docker system prune -f

# Kill all running lab containers
docker ps -q --filter "name=fixitlab-lab-" | xargs -r docker rm -f

# Check Docker disk usage
docker system df
```

### 11.6 Monitor Disk Space

```bash
df -h                    # Overall disk
docker system df -v      # Docker-specific usage
```

### 11.7 Uptime Monitoring (Free)

Set up at [UptimeRobot](https://uptimerobot.com):
1. Sign up (free plan: 50 monitors)
2. Add monitor: `https://fixitlab.in/api/health/`
3. Check interval: 5 minutes
4. Alert contacts: your email

---

## 12. Updating the Application

### Pull Latest Code & Redeploy

```bash
cd /opt/fixitlab

# 1. Pull latest changes
git pull origin main

# 2. Rebuild and restart (near-zero downtime)
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 3. Run migrations if database schema changed
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate --noinput

# 4. Verify health
docker compose -f docker-compose.prod.yml ps
curl -s https://fixitlab.in/api/health/
```

### Frontend-Only Update

```bash
docker compose -f docker-compose.prod.yml build frontend-prod
docker compose -f docker-compose.prod.yml up -d frontend-prod
docker compose -f docker-compose.prod.yml restart gateway
```

### Backend-Only Update

```bash
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend celery_worker celery_beat
```

### Add New Scenarios

```bash
# 1. Create scenario in scenarios/linux/new-scenario/
# 2. Build the Docker image
docker build -t fixitlab/scenario-new-scenario scenarios/linux/new-scenario/

# 3. Add to seed_data.py and re-seed
docker compose -f docker-compose.prod.yml exec backend python /scripts/seed_data.py
```

---

## 13. Troubleshooting

### Quick Diagnostic Commands

```bash
# Check all service health
docker compose -f docker-compose.prod.yml ps

# Check backend logs
docker compose -f docker-compose.prod.yml logs -f backend --tail 50

# Check celery worker logs
docker compose -f docker-compose.prod.yml logs -f celery_worker --tail 50

# Check gateway/nginx logs
docker compose -f docker-compose.prod.yml logs -f gateway --tail 50

# Backend Django shell
docker compose -f docker-compose.prod.yml exec backend python manage.py shell

# Database shell
docker compose -f docker-compose.prod.yml exec database psql -U fixitlab -d fixitlab

# Redis shell
docker compose -f docker-compose.prod.yml exec redis redis-cli -a YOUR_REDIS_PASSWORD
```

### Common Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| **502 Bad Gateway** | Backend not healthy yet | Wait 30-60s. Check: `docker logs fixitlab_backend` |
| **WebSocket disconnects** | Nginx/proxy timeout | Check: `docker logs fixitlab-main-gateway-1` |
| **Labs not starting** | Scenario images not built | Run: `make scenarios` |
| **"Auth failed" in terminal** | SSH key not available | Verify `/scripts/fixitlab.pem` in container |
| **Emails not sending** | Wrong Gmail app password | Re-generate at myaccount.google.com/apppasswords |
| **Razorpay popup won't load** | `RAZORPAY_KEY_ID` empty/wrong | Set correct key, restart backend |
| **HTTPS not working** | DNS not propagated | Check: `dig fixitlab.in`. Wait & retry certbot. |
| **"CSRF verification failed"** | Domain mismatch | Ensure `CSRF_TRUSTED_ORIGINS` has `https://` prefix |
| **Static files 404** | collectstatic missing | Run inside container: `python manage.py collectstatic --noinput` |
| **Database connection refused** | Container unhealthy | `docker compose logs database` |
| **Port 80/443 in use** | Another web server running | `lsof -i :80` then `systemctl stop apache2` or `nginx` |

### Reset Admin Password

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(email='admin@fixitlab.in')
u.set_password('NewSecurePassword123')
u.save()
print('Password reset successfully')
"
```

### Full Database Reset (Nuclear Option)

```bash
docker compose -f docker-compose.prod.yml down -v   # ⚠️ DELETES ALL DATA
docker compose -f docker-compose.prod.yml up -d --build
# Wait 60s for migrations, seeding, and health checks
```

---

## 14. Cost Summary

### Minimum Viable Deployment (Docker-Only Labs)

| Item | Cost |
|------|------|
| VPS (4GB RAM — Hetzner/Contabo) | ₹500-2500/mo |
| Domain (.in) | ₹800/year |
| Gmail SMTP | Free |
| Razorpay | 2% per transaction (no monthly fee) |
| Let's Encrypt SSL | Free |
| UptimeRobot monitoring | Free |
| **Total** | **~₹500-2500/mo** |

### Full Deployment (Docker + AWS Cloud Labs)

| Item | Cost |
|------|------|
| VPS (8GB RAM) | ₹2000-4000/mo |
| Domain (.in) | ₹800/year |
| AWS EC2 lab instances | ₹400-1500/mo (usage-based) |
| Gmail SMTP | Free |
| Razorpay | 2% per transaction |
| **Total** | **₹3000-6000/mo** |

### Optional Add-ons

| Item | Cost |
|------|------|
| Sentry error tracking | Free (5K events/mo) |
| Cloudflare CDN + DDoS protection | Free |
| S3 for backup storage | ~₹80/mo |
| SendGrid email (higher volume) | Free (100/day) |
| Google Analytics | Free |

---

## Architecture Diagram

```
                    Internet
                       │
                   ┌───▼───┐
                   │ Nginx │ :80 / :443 (SSL + rate limiting)
                   │Gateway│
                   └───┬───┘
              ┌────────┼────────┐
              ▼        ▼        ▼
         ┌────────┐ ┌──────┐ ┌──────────┐
         │Frontend│ │  API │ │WebSocket │
         │ React  │ │Django│ │ Terminal │
         │ Vite   │ │ DRF  │ │ xterm.js │
         └────────┘ └──┬───┘ └────┬─────┘
                       │          │
          ┌────────────┼──────────┼────────────┐
          ▼            ▼          ▼             ▼
     ┌────────┐  ┌─────────┐ ┌───────┐  ┌──────────┐
     │Postgres│  │RabbitMQ │ │ Redis │  │  Celery  │
     │  15    │  │  3.x    │ │  7.x  │  │ Workers  │
     └────────┘  └─────────┘ └───────┘  └────┬─────┘
                                              │
                                    ┌─────────┼─────────┐
                                    ▼         ▼         ▼
                               ┌────────┐ ┌────────┐ ┌──────┐
                               │ Docker │ │  AWS   │ │  DO  │
                               │  Labs  │ │  EC2   │ │Drops │
                               └────────┘ └────────┘ └──────┘
```

**9 Services:** Gateway · Frontend · Backend · Celery Worker · Celery Beat · PostgreSQL · Redis · RabbitMQ · Certbot (prod)

---

## Quick Reference Commands

```bash
# ── Development ──
docker compose up -d --build               # Start all (dev)
docker compose down                         # Stop all (dev)
docker compose logs -f backend              # Follow backend logs
make scenarios                              # Build scenario images
make test                                   # Run 64 unit tests
make shell                                  # Django shell
make dbshell                                # PostgreSQL shell

# ── Production ──
docker compose -f docker-compose.prod.yml up -d --build     # Start all (prod)
docker compose -f docker-compose.prod.yml down               # Stop all (prod)
docker compose -f docker-compose.prod.yml logs -f            # Follow all logs
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate --noinput

# ── Lab Management ──
docker ps --filter "name=fixitlab-lab-"                      # View running labs
docker ps -q --filter "name=fixitlab-lab-" | xargs -r docker rm -f  # Kill all labs
docker images | grep fixitlab/scenario                       # List scenario images

# ── Backups ──
./scripts/backup.sh                                          # Run manual backup
ls -la backups/                                              # List backups
```

---

**Questions?** Check `docs/DEPLOYMENT.md` for DigitalOcean/AWS Kubernetes deploy options, or `docs/api.md` for API documentation.

