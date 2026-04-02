# FixitLab — Production Deployment Guide

Complete step-by-step instructions to deploy FixitLab on **DigitalOcean** (simple) or **AWS** (enterprise-scale).

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Option A — DigitalOcean Droplet (Single Server)](#option-a--digitalocean-droplet-single-server)
4. [Option B — DigitalOcean Kubernetes (DOKS)](#option-b--digitalocean-kubernetes-doks)
5. [Option C — AWS with EKS (Enterprise)](#option-c--aws-with-eks-enterprise)
6. [Domain & SSL Setup](#domain--ssl-setup)
7. [Email Configuration (SMTP)](#email-configuration-smtp)
8. [Scenario Images](#scenario-images)
9. [Backups & Monitoring](#backups--monitoring)
10. [CI/CD Pipeline](#cicd-pipeline)
11. [Troubleshooting](#troubleshooting)
12. [Cost Estimates](#cost-estimates)

---

## Architecture Overview

```
                    ┌─────────────┐
                    │   Nginx /   │
User ──► DNS ──►   │  Gateway    │
                    │  (SSL/TLS)  │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌────▼─────┐
        │ Frontend │ │ Backend  │ │   /ws/   │
        │ (React)  │ │ (Daphne) │ │ WebSocket│
        └──────────┘ └────┬─────┘ └────┬─────┘
                          │            │
              ┌───────────┼────────────┼───────────┐
              │           │            │           │
        ┌─────▼──┐  ┌────▼────┐ ┌────▼────┐ ┌───▼──────┐
        │Postgres│  │  Redis  │ │RabbitMQ │ │  Celery  │
        │  (DB)  │  │ (Cache) │ │ (Queue) │ │ Workers  │
        └────────┘  └─────────┘ └─────────┘ └───┬──────┘
                                                 │
                                          ┌──────▼──────┐
                                          │ Lab Docker  │
                                          │ Containers  │
                                          │ (Scenarios) │
                                          └─────────────┘
```

**Services (8 total):**
| Service | Purpose | Port |
|---------|---------|------|
| Gateway (Nginx) | Reverse proxy, SSL, rate limiting | 80/443 |
| Frontend | React SPA (Vite build → Nginx) | Internal |
| Backend | Django/Daphne ASGI (REST + WebSocket) | 8000 |
| Celery Worker | Background tasks (cleanup, notifications) | — |
| Celery Beat | Periodic task scheduler | — |
| PostgreSQL 15 | Primary database | 5432 |
| Redis 7 | Cache + Django Channels layer | 6379 |
| RabbitMQ 3 | Celery message broker | 5672 |

**Critical requirement:** The backend and Celery workers need access to the Docker socket (`/var/run/docker.sock`) to provision lab containers.

---

## Prerequisites

On your **local machine** before you start:

```bash
# Install these tools
brew install doctl          # DigitalOcean CLI (Option A/B)
brew install awscli         # AWS CLI (Option C)
brew install terraform      # Infrastructure as Code (Option B/C)
brew install kubectl        # Kubernetes CLI (Option B/C)
brew install docker         # Docker (all options)
```

**Accounts needed:**
- DigitalOcean account → https://cloud.digitalocean.com
- OR AWS account → https://aws.amazon.com
- A domain name (e.g., `fixitlab.com`) from any registrar
- SMTP service: [Mailgun](https://www.mailgun.com), [SendGrid](https://sendgrid.com), or [AWS SES](https://aws.amazon.com/ses/)

---

## Option A — DigitalOcean Droplet (Single Server)

**Best for:** Getting started, <500 concurrent users, budget-friendly ($24-48/month).

### Step 1: Create a Droplet

```bash
# Authenticate with DigitalOcean
doctl auth init
# → Paste your API token from https://cloud.digitalocean.com/account/api/tokens

# Create a droplet (Ubuntu 22.04, 4GB RAM minimum)
doctl compute droplet create fixitlab-prod \
  --image ubuntu-22-04-x64 \
  --size s-2vcpu-4gb \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header | head -1) \
  --tag-names production \
  --wait

# Get the IP address
doctl compute droplet list --format Name,PublicIPv4
# Example output: fixitlab-prod    164.90.xxx.xxx
```

> **Recommended sizes:**
> | Users | Droplet Size | Monthly Cost |
> |-------|-------------|-------------|
> | < 100 | s-2vcpu-4gb | $24/mo |
> | 100-300 | s-4vcpu-8gb | $48/mo |
> | 300-500 | s-8vcpu-16gb | $96/mo |

### Step 2: SSH Into the Server and Install Dependencies

```bash
# SSH into the droplet
ssh root@164.90.xxx.xxx

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# Install Docker Compose
apt install -y docker-compose-plugin

# Verify installations
docker --version        # Docker 24.x+
docker compose version  # Docker Compose v2.x+

# Install Git
apt install -y git

# Create app user (never run production as root)
useradd -m -s /bin/bash fixitlab
usermod -aG docker fixitlab

# Setup firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### Step 3: Clone the Repository

```bash
# Switch to app user
su - fixitlab

# Clone your repo
git clone https://github.com/YOUR_USERNAME/fixitlab.git ~/fixitlab
cd ~/fixitlab
```

### Step 4: Create Production Environment File

```bash
cat > .env << 'EOF'
# ─── Django ───
DJANGO_SECRET_KEY=CHANGE-ME-generate-with-python-c-"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=fixitlab.com,www.fixitlab.com,164.90.xxx.xxx

# ─── Database ───
POSTGRES_DB=fixitlab
POSTGRES_USER=fixitlab
POSTGRES_PASSWORD=CHANGE-ME-use-a-strong-password-here
POSTGRES_HOST=database
POSTGRES_PORT=5432

# ─── Redis ───
REDIS_HOST=redis
REDIS_PORT=6379

# ─── RabbitMQ ───
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//

# ─── Docker Labs ───
LAB_PROVIDER=docker
DOCKER_HOST=unix:///var/run/docker.sock
DOCKER_NETWORK=fixitlab_labs
DOCKER_CONTAINER_MEMORY_LIMIT=512m
DOCKER_CONTAINER_CPU_LIMIT=1.0
DOCKER_SCENARIO_IMAGE_PREFIX=fixitlab/scenario-

# ─── Email (SMTP) ───
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=postmaster@mg.fixitlab.com
EMAIL_HOST_PASSWORD=CHANGE-ME-mailgun-password
DEFAULT_FROM_EMAIL=FixitLab <noreply@fixitlab.com>

# ─── Superuser ───
SUPERUSER_USERNAME=admin
SUPERUSER_EMAIL=admin@fixitlab.com
SUPERUSER_PASSWORD=CHANGE-ME-strong-admin-password

# ─── Frontend ───
FRONTEND_URL=https://fixitlab.com

# ─── Stripe (optional, for billing) ───
STRIPE_SECRET_KEY=
STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
EOF
```

**Generate a real secret key:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# → Paste the output as DJANGO_SECRET_KEY value
```

### Step 5: Create Production Docker Compose Override

```bash
cat > docker-compose.prod.yml << 'YAML'
version: "3.9"

services:
  gateway:
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./gateway/nginx-prod.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - static_volume:/static

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    # No volume mounts in production (built static files inside image)
    volumes: []

  backend:
    environment:
      - DJANGO_DEBUG=false
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"

  celery_worker:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '2'
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"

  database:
    volumes:
      - fixitlab_db_data:/var/lib/postgresql/data
      - ./backups:/backups

volumes:
  fixitlab_db_data:
  static_volume:
YAML
```

### Step 6: Create Production Nginx Config (with SSL)

```bash
cat > gateway/nginx-prod.conf << 'NGINX'
# Rate limiting
limit_req_zone $binary_remote_addr zone=api_rate:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=auth_rate:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=ws_rate:10m rate=10r/s;

# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name fixitlab.com www.fixitlab.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    server_name fixitlab.com www.fixitlab.com;

    # SSL certificates (Let's Encrypt)
    ssl_certificate     /etc/letsencrypt/live/fixitlab.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fixitlab.com/privkey.pem;

    # SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_stapling on;
    ssl_stapling_verify on;

    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;

    client_max_body_size 10m;
    server_tokens off;

    # Static files
    location /static/ {
        alias /static/;
        access_log off;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Frontend (React)
    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Auth endpoints (strict rate limit)
    location /api/auth/ {
        limit_req zone=auth_rate burst=3 nodelay;
        limit_req_status 429;
        proxy_pass http://backend:8000/api/auth/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django admin
    location /admin/ {
        limit_req zone=auth_rate burst=5 nodelay;
        proxy_pass http://backend:8000/admin/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        limit_req zone=api_rate burst=40 nodelay;
        limit_req_status 429;
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 30s;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # WebSocket
    location /ws/ {
        limit_req zone=ws_rate burst=5 nodelay;
        proxy_pass http://backend:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    # Health check
    location /health {
        access_log off;
        return 200 'ok';
        add_header Content-Type text/plain;
    }

    # Block exploits
    location ~* /(\.env|\.git|wp-admin|phpMyAdmin|phpmyadmin) {
        return 404;
    }
}
NGINX
```

### Step 7: Get SSL Certificate (Let's Encrypt)

```bash
# Install certbot
apt install -y certbot

# Get certificate (stop nginx first if running)
certbot certonly --standalone -d fixitlab.com -d www.fixitlab.com \
  --email admin@fixitlab.com --agree-tos --no-eff-email

# Auto-renew (add to crontab)
echo "0 0 1 * * certbot renew --quiet && docker compose restart gateway" | crontab -
```

### Step 8: Build Scenario Images

```bash
cd ~/fixitlab

# Build all scenario images
make scenarios

# Verify they exist
docker images | grep scenario
# fixitlab/scenario-broken-nginx       latest   ...
# fixitlab/scenario-disk-full          latest   ...
# fixitlab/scenario-ssh-lockout        latest   ...
# fixitlab/scenario-zombie-process     latest   ...
# fixitlab/scenario-dns-resolution-broken  latest   ...
# fixitlab/scenario-broken-cron        latest   ...
```

### Step 9: Launch Everything

```bash
cd ~/fixitlab

# Build and start all services using production compose
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Watch the logs to ensure everything starts
docker compose logs -f

# Check all services are healthy
docker compose ps
```

**Expected output (all running/healthy):**
```
NAME                            STATUS                    STATE
fixitlab_backend                Up 2 minutes (healthy)    running
fixitlab_db                     Up 3 minutes (healthy)    running
fixitlab_frontend               Up 2 minutes              running
fixitlab_rabbitmq               Up 3 minutes (healthy)    running
fixitlab_redis                  Up 3 minutes (healthy)    running
fixitlab-celery_beat-1          Up 2 minutes              running
fixitlab-celery_worker-1        Up 2 minutes              running
fixitlab-gateway-1              Up 2 minutes              running
```

### Step 10: Set Up DNS

Go to your domain registrar and add:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | @ | 164.90.xxx.xxx | 300 |
| A | www | 164.90.xxx.xxx | 300 |

Wait 5-10 minutes for DNS propagation, then visit `https://fixitlab.com`.

### Step 11: Automated Database Backups

```bash
# Create backup directory
mkdir -p ~/fixitlab/backups

# Create backup script
cat > ~/fixitlab/backup.sh << 'BASH'
#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=~/fixitlab/backups

# Dump the database
docker compose exec -T database pg_dump -U fixitlab fixitlab | gzip > "$BACKUP_DIR/fixitlab_$TIMESTAMP.sql.gz"

# Keep only last 30 backups
ls -t "$BACKUP_DIR"/fixitlab_*.sql.gz | tail -n +31 | xargs -r rm

echo "✅ Backup completed: fixitlab_$TIMESTAMP.sql.gz"
BASH

chmod +x ~/fixitlab/backup.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * /home/fixitlab/fixitlab/backup.sh >> /home/fixitlab/fixitlab/backups/backup.log 2>&1") | crontab -
```

### Step 12: Set Up Log Rotation

```bash
cat > /etc/logrotate.d/fixitlab << 'CONF'
/var/lib/docker/containers/*/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
    maxsize 50M
}
CONF
```

You're done with DigitalOcean Droplet deployment! 🎉

---

## Option B — DigitalOcean Kubernetes (DOKS)

**Best for:** 500-5000 users, auto-scaling, high availability ($100-300/month).

### Step 1: Create a Kubernetes Cluster

```bash
# Create a DOKS cluster
doctl kubernetes cluster create fixitlab-prod \
  --region nyc1 \
  --version latest \
  --node-pool "name=app-pool;size=s-4vcpu-8gb;count=3;auto-scale=true;min-nodes=2;max-nodes=10" \
  --wait

# Save kubeconfig
doctl kubernetes cluster kubeconfig save fixitlab-prod

# Verify
kubectl get nodes
```

### Step 2: Create a Container Registry

```bash
# Create DigitalOcean Container Registry
doctl registry create fixitlab-registry --region nyc1

# Login to registry
doctl registry login

# Get registry endpoint
REGISTRY=$(doctl registry get --format Endpoint --no-header)
echo "Registry: $REGISTRY"
# Example: registry.digitalocean.com/fixitlab-registry
```

### Step 3: Build and Push Images

```bash
cd ~/fixitlab
REGISTRY="registry.digitalocean.com/fixitlab-registry"

# Build backend
docker build -t $REGISTRY/backend:latest ./backend
docker push $REGISTRY/backend:latest

# Build frontend (production)
docker build -f frontend/Dockerfile.prod -t $REGISTRY/frontend:latest ./frontend
docker push $REGISTRY/frontend:latest

# Build and push all scenario images
for dir in scenarios/*/*; do
  if [ -f "$dir/Dockerfile" ]; then
    SLUG=$(basename $dir)
    echo "Building scenario: $SLUG"
    docker build -t $REGISTRY/scenario-$SLUG:latest $dir
    docker push $REGISTRY/scenario-$SLUG:latest
  fi
done
```

### Step 4: Create a Managed Database

```bash
# Create managed PostgreSQL
doctl databases create fixitlab-db \
  --engine pg \
  --version 15 \
  --size db-s-2vcpu-4gb \
  --region nyc1 \
  --num-nodes 1 \
  --wait

# Get connection details
doctl databases connection fixitlab-db --format Host,Port,User,Password,Database
```

### Step 5: Create Managed Redis

```bash
doctl databases create fixitlab-redis \
  --engine redis \
  --version 7 \
  --size db-s-1vcpu-2gb \
  --region nyc1 \
  --num-nodes 1 \
  --wait

# Get connection details
doctl databases connection fixitlab-redis --format Host,Port,Password
```

### Step 6: Update Kubernetes Manifests

Edit `infra/kubernetes/deployment.yaml` to update:
- Container image references → `registry.digitalocean.com/fixitlab-registry/backend:latest`
- PostgreSQL host → managed database host from Step 4
- Redis host → managed Redis host from Step 5
- Remove PostgreSQL/Redis StatefulSets (using managed services instead)

```bash
# Create namespace
kubectl create namespace fixitlab

# Create secrets
kubectl -n fixitlab create secret generic fixitlab-secrets \
  --from-literal=DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  --from-literal=POSTGRES_DB=fixitlab \
  --from-literal=POSTGRES_USER=fixitlab \
  --from-literal=POSTGRES_PASSWORD='YOUR_MANAGED_DB_PASSWORD' \
  --from-literal=POSTGRES_HOST='YOUR_MANAGED_DB_HOST' \
  --from-literal=EMAIL_HOST_PASSWORD='YOUR_SMTP_PASSWORD' \
  --from-literal=SUPERUSER_PASSWORD='YOUR_ADMIN_PASSWORD'

# Create configmap
kubectl -n fixitlab create configmap fixitlab-config \
  --from-literal=DJANGO_DEBUG=false \
  --from-literal=DJANGO_ALLOWED_HOSTS='fixitlab.com,www.fixitlab.com' \
  --from-literal=POSTGRES_PORT=25060 \
  --from-literal=REDIS_HOST='YOUR_MANAGED_REDIS_HOST' \
  --from-literal=REDIS_PORT=25061 \
  --from-literal=CELERY_BROKER_URL='amqp://guest:guest@rabbitmq-service:5672//' \
  --from-literal=LAB_PROVIDER=docker \
  --from-literal=DOCKER_NETWORK=fixitlab_labs \
  --from-literal=DOCKER_SCENARIO_IMAGE_PREFIX="$REGISTRY/scenario-" \
  --from-literal=FRONTEND_URL='https://fixitlab.com' \
  --from-literal=EMAIL_HOST='smtp.mailgun.org' \
  --from-literal=EMAIL_PORT=587 \
  --from-literal=EMAIL_HOST_USER='postmaster@mg.fixitlab.com' \
  --from-literal=DEFAULT_FROM_EMAIL='FixitLab <noreply@fixitlab.com>'

# Allow cluster to pull from your registry
doctl registry kubernetes-manifest | kubectl apply -f -
```

### Step 7: Install Nginx Ingress + Cert-Manager

```bash
# Install Nginx Ingress Controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.0/deploy/static/provider/do/deploy.yaml

# Wait for LoadBalancer IP
kubectl -n ingress-nginx get svc ingress-nginx-controller -w
# → Note the EXTERNAL-IP (this is your Load Balancer IP)

# Install cert-manager for automatic TLS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml

# Create Let's Encrypt issuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@fixitlab.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Step 8: Deploy

```bash
# Apply all Kubernetes manifests
kubectl apply -f infra/kubernetes/deployment.yaml

# Watch rollout
kubectl -n fixitlab rollout status deployment/backend --timeout=300s
kubectl -n fixitlab rollout status deployment/frontend --timeout=300s

# Run migrations
kubectl -n fixitlab exec deployment/backend -- python manage.py migrate --noinput

# Verify all pods
kubectl -n fixitlab get pods
```

### Step 9: Point DNS

Point your domain A record to the LoadBalancer EXTERNAL-IP from Step 7.

---

## Option C — AWS with EKS (Enterprise)

**Best for:** 5000+ users, multi-region, compliance requirements ($300-1000+/month).

### Step 1: Configure AWS CLI

```bash
# Configure AWS credentials
aws configure
# → Enter Access Key ID
# → Enter Secret Access Key
# → Region: us-east-1
# → Output format: json

# Verify
aws sts get-caller-identity
```

### Step 2: Create Terraform State Bucket

```bash
aws s3 mb s3://fixitlab-terraform-state --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket fixitlab-terraform-state \
  --versioning-configuration Status=Enabled
```

### Step 3: Deploy Infrastructure with Terraform

```bash
cd infra/terraform

# Review and customize variables in main.tf:
#   - aws_region (default: us-east-1)
#   - db_instance_class (default: db.r6g.large)
#   - domain_name (default: fixitlab.com)

# Initialize Terraform
terraform init

# Preview what will be created
terraform plan -out=tfplan

# Apply (this takes 15-25 minutes)
terraform apply tfplan

# Save the outputs
terraform output > ../outputs.txt
cat ../outputs.txt
```

**Resources created by Terraform:**
- VPC with 3 AZs (public + private subnets)
- EKS cluster with 2 node groups (app + lab-runners)
- Aurora PostgreSQL (2 instances, multi-AZ)
- ElastiCache Redis (2 nodes, multi-AZ)
- ECR repositories (backend, frontend)
- S3 bucket for static assets
- CloudFront CDN distribution

### Step 4: Configure kubectl for EKS

```bash
aws eks update-kubeconfig --name fixitlab-eks --region us-east-1

# Verify
kubectl get nodes
# Should show 6 nodes (3 app + 3 lab-runner)
```

### Step 5: Build and Push to ECR

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(terraform output -raw ecr_backend_url | cut -d/ -f1)

ECR_BASE=$(terraform output -raw ecr_backend_url | cut -d/ -f1)

# Build and push backend
docker build -t $ECR_BASE/fixitlab/backend:latest ./backend
docker push $ECR_BASE/fixitlab/backend:latest

# Build and push frontend
docker build -f frontend/Dockerfile.prod -t $ECR_BASE/fixitlab/frontend:latest ./frontend
docker push $ECR_BASE/fixitlab/frontend:latest

# Build and push all scenario images
# First create ECR repos for each scenario
for dir in scenarios/*/*; do
  if [ -f "$dir/Dockerfile" ]; then
    SLUG=$(basename $dir)
    aws ecr create-repository --repository-name fixitlab/scenario-$SLUG --region us-east-1 2>/dev/null || true
    docker build -t $ECR_BASE/fixitlab/scenario-$SLUG:latest $dir
    docker push $ECR_BASE/fixitlab/scenario-$SLUG:latest
  fi
done
```

### Step 6: Store Secrets in AWS Secrets Manager

```bash
# Create production secrets
aws secretsmanager create-secret \
  --name fixitlab/production \
  --secret-string '{
    "DJANGO_SECRET_KEY": "'$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")'",
    "POSTGRES_PASSWORD": "'$(openssl rand -base64 32)'",
    "SUPERUSER_PASSWORD": "YourStrongAdminPassword123!",
    "EMAIL_HOST_PASSWORD": "your-smtp-password",
    "STRIPE_SECRET_KEY": "",
    "STRIPE_WEBHOOK_SECRET": ""
  }'
```

### Step 7: Install EKS Add-ons

```bash
# Install AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=fixitlab-eks

# Install Nginx Ingress
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n ingress-nginx --create-namespace \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/aws-load-balancer-type"=nlb

# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.0/cert-manager.yaml
```

### Step 8: Create Kubernetes Secrets and Config

```bash
# Get Terraform outputs
RDS_ENDPOINT=$(terraform output -raw rds_endpoint)
REDIS_ENDPOINT=$(terraform output -raw redis_endpoint)
ECR_BACKEND=$(terraform output -raw ecr_backend_url)

# Create namespace
kubectl create namespace fixitlab

# Create secrets
kubectl -n fixitlab create secret generic fixitlab-secrets \
  --from-literal=DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  --from-literal=POSTGRES_DB=fixitlab \
  --from-literal=POSTGRES_USER=fixitlab \
  --from-literal=POSTGRES_PASSWORD="$(aws secretsmanager get-secret-value --secret-id fixitlab/production --query SecretString --output text | python3 -c 'import sys,json; print(json.load(sys.stdin)["POSTGRES_PASSWORD"])')" \
  --from-literal=SUPERUSER_PASSWORD="YourStrongAdminPassword123!"

# Create config
kubectl -n fixitlab create configmap fixitlab-config \
  --from-literal=DJANGO_DEBUG=false \
  --from-literal=DJANGO_ALLOWED_HOSTS='fixitlab.com' \
  --from-literal=POSTGRES_HOST="$RDS_ENDPOINT" \
  --from-literal=POSTGRES_PORT=5432 \
  --from-literal=REDIS_HOST="$REDIS_ENDPOINT" \
  --from-literal=REDIS_PORT=6379 \
  --from-literal=CELERY_BROKER_URL='amqp://guest:guest@rabbitmq-service:5672//' \
  --from-literal=LAB_PROVIDER=docker \
  --from-literal=DOCKER_NETWORK=fixitlab_labs \
  --from-literal=DOCKER_SCENARIO_IMAGE_PREFIX="$ECR_BASE/fixitlab/scenario-" \
  --from-literal=FRONTEND_URL='https://fixitlab.com'
```

### Step 9: Update Image References in deployment.yaml

```bash
# Update deployment.yaml with your ECR image URLs
sed -i "s|fixitlab/backend:latest|$ECR_BACKEND:latest|g" infra/kubernetes/deployment.yaml
sed -i "s|fixitlab/frontend:latest|$ECR_BASE/fixitlab/frontend:latest|g" infra/kubernetes/deployment.yaml
```

### Step 10: Deploy to EKS

```bash
# Apply manifests
kubectl apply -f infra/kubernetes/deployment.yaml

# Watch rollout
kubectl -n fixitlab rollout status deployment/backend --timeout=300s
kubectl -n fixitlab rollout status deployment/frontend --timeout=300s
kubectl -n fixitlab rollout status deployment/celery-worker --timeout=300s

# Run migrations
kubectl -n fixitlab exec deployment/backend -- python manage.py migrate --noinput

# Verify
kubectl -n fixitlab get pods
kubectl -n fixitlab get svc
kubectl -n fixitlab get ingress
```

### Step 11: Configure Route 53 DNS

```bash
# Get Load Balancer hostname
LB_HOST=$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

# Create Route 53 hosted zone (if not already)
aws route53 create-hosted-zone --name fixitlab.com --caller-reference $(date +%s)

# Get hosted zone ID
ZONE_ID=$(aws route53 list-hosted-zones-by-name --dns-name fixitlab.com --query 'HostedZones[0].Id' --output text | cut -d/ -f3)

# Create A record (alias to NLB)
aws route53 change-resource-record-sets --hosted-zone-id $ZONE_ID --change-batch '{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "fixitlab.com",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "Z26RNL4JYFTOTI",
        "DNSName": "'$LB_HOST'",
        "EvaluateTargetHealth": true
      }
    }
  }]
}'
```

---

## Domain & SSL Setup

### For DigitalOcean Droplet (Option A)

Already covered in Step 7 above using Let's Encrypt/certbot.

### For Kubernetes (Option B/C)

SSL is handled automatically by cert-manager + Let's Encrypt via the Ingress annotation:

```yaml
annotations:
  cert-manager.io/cluster-issuer: "letsencrypt-prod"
```

The Ingress manifest in `infra/kubernetes/deployment.yaml` already includes this.

---

## Email Configuration (SMTP)

### Option 1: Mailgun (Recommended for Starting)

1. Sign up at https://www.mailgun.com (free: 5,000 emails/month)
2. Add your domain: `mg.fixitlab.com`
3. Add DNS records (TXT, CNAME) as Mailgun instructs
4. Update `.env`:

```env
EMAIL_HOST=smtp.mailgun.org
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=postmaster@mg.fixitlab.com
EMAIL_HOST_PASSWORD=your-mailgun-smtp-password
DEFAULT_FROM_EMAIL=FixitLab <noreply@fixitlab.com>
```

### Option 2: AWS SES

```bash
# Verify domain
aws ses verify-domain-identity --domain fixitlab.com

# Get DKIM tokens (add as CNAME records in DNS)
aws ses get-identity-dkim-attributes --identities fixitlab.com

# Request production access (to send to unverified emails)
# → Go to AWS Console → SES → Account dashboard → Request production access
```

```env
EMAIL_HOST=email-smtp.us-east-1.amazonaws.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=YOUR_SES_SMTP_USER
EMAIL_HOST_PASSWORD=YOUR_SES_SMTP_PASSWORD
DEFAULT_FROM_EMAIL=FixitLab <noreply@fixitlab.com>
```

### Option 3: SendGrid

```env
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=SG.your-sendgrid-api-key
DEFAULT_FROM_EMAIL=FixitLab <noreply@fixitlab.com>
```

---

## Scenario Images

Scenario images must be available on every node that runs labs.

### Single Server (Option A)

Images are built locally and already available:

```bash
make scenarios
docker images | grep scenario
```

### Kubernetes (Option B/C)

Images must be pushed to the container registry and pre-pulled on lab-runner nodes:

```bash
# Build + push (already done in deployment steps above)
# Verify on a node:
kubectl -n fixitlab exec deployment/backend -- docker images | grep scenario
```

### Adding New Scenarios

```bash
# 1. Create scenario directory
mkdir -p scenarios/linux/my-new-scenario

# 2. Create files:
#    - Dockerfile    (base image + intentional breakage)
#    - check.sh      (validation script — exit 0 = pass, exit 1 = fail)
#    - scenario.yaml (metadata: title, description, difficulty, technology)

# 3. Build the image
docker build -t fixitlab/scenario-my-new-scenario:latest scenarios/linux/my-new-scenario/

# 4. Push to registry (if using Kubernetes)
docker push $REGISTRY/fixitlab/scenario-my-new-scenario:latest

# 5. Add to database via Django admin or seed script
```

---

## Backups & Monitoring

### Database Backups

**DigitalOcean Droplet:**
```bash
# Manual backup
docker compose exec -T database pg_dump -U fixitlab fixitlab | gzip > backup_$(date +%Y%m%d).sql.gz

# Restore from backup
gunzip -c backup_20260330.sql.gz | docker compose exec -T database psql -U fixitlab fixitlab
```

**DigitalOcean Managed DB:** Automatic daily backups (7-day retention included).

**AWS Aurora:** Automatic continuous backups (35-day retention, point-in-time recovery).

### Monitoring

#### Basic Health Checks

```bash
# API health
curl -s https://fixitlab.com/api/health/

# All pods (Kubernetes)
kubectl -n fixitlab get pods

# Celery workers
kubectl -n fixitlab logs deployment/celery-worker --tail=20
```

#### DigitalOcean Monitoring

```bash
# Enable built-in monitoring agent
doctl compute droplet-action install-monitoring 164.90.xxx.xxx
```

Set up alerts in DigitalOcean Console → Monitoring → Create Alert:
- CPU > 80% for 5 minutes
- Memory > 90% for 5 minutes
- Disk > 85%

#### AWS CloudWatch

```bash
# Install CloudWatch agent on EKS
helm repo add aws-cloudwatch https://aws.github.io/eks-charts
helm install cloudwatch-agent aws-cloudwatch/aws-cloudwatch-observability \
  -n amazon-cloudwatch --create-namespace \
  --set clusterName=fixitlab-eks
```

#### Uptime Monitoring (Free)

Set up [UptimeRobot](https://uptimerobot.com) or [Better Uptime](https://betteruptime.com):
- Monitor: `https://fixitlab.com/api/health/`
- Check interval: 5 minutes
- Alert via email/Slack/SMS

---

## CI/CD Pipeline

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy FixitLab

on:
  push:
    branches: [main]

env:
  REGISTRY: ${{ secrets.REGISTRY_URL }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: |
          pip install -r backend/requirements.txt
          cd backend && python manage.py test --verbosity=2

  build-and-push:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Login to container registry
      - name: Login to Registry
        run: echo "${{ secrets.REGISTRY_PASSWORD }}" | docker login $REGISTRY -u ${{ secrets.REGISTRY_USERNAME }} --password-stdin

      # Build images
      - name: Build Backend
        run: docker build -t $REGISTRY/backend:${{ github.sha }} -t $REGISTRY/backend:latest ./backend

      - name: Build Frontend
        run: docker build -f frontend/Dockerfile.prod -t $REGISTRY/frontend:${{ github.sha }} -t $REGISTRY/frontend:latest ./frontend

      # Build all scenario images
      - name: Build Scenarios
        run: |
          for dir in scenarios/*/*; do
            if [ -f "$dir/Dockerfile" ]; then
              SLUG=$(basename $dir)
              docker build -t $REGISTRY/scenario-$SLUG:latest $dir
            fi
          done

      # Push images
      - name: Push Images
        run: |
          docker push $REGISTRY/backend:latest
          docker push $REGISTRY/frontend:latest
          for dir in scenarios/*/*; do
            if [ -f "$dir/Dockerfile" ]; then
              SLUG=$(basename $dir)
              docker push $REGISTRY/scenario-$SLUG:latest
            fi
          done

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # For DigitalOcean Kubernetes
      - name: Install doctl
        uses: digitalocean/action-doctl@v2
        with:
          token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}

      - name: Configure kubectl
        run: doctl kubernetes cluster kubeconfig save fixitlab-prod

      - name: Deploy
        run: |
          kubectl -n fixitlab set image deployment/backend backend=$REGISTRY/backend:${{ github.sha }}
          kubectl -n fixitlab set image deployment/frontend frontend=$REGISTRY/frontend:${{ github.sha }}
          kubectl -n fixitlab set image deployment/celery-worker worker=$REGISTRY/backend:${{ github.sha }}
          kubectl -n fixitlab set image deployment/celery-beat beat=$REGISTRY/backend:${{ github.sha }}
          kubectl -n fixitlab rollout status deployment/backend --timeout=300s
          kubectl -n fixitlab rollout status deployment/frontend --timeout=300s

      - name: Run Migrations
        run: kubectl -n fixitlab exec deployment/backend -- python manage.py migrate --noinput
```

**Required GitHub Secrets:**
| Secret | Value |
|--------|-------|
| `REGISTRY_URL` | `registry.digitalocean.com/fixitlab-registry` or ECR URL |
| `REGISTRY_USERNAME` | Registry username |
| `REGISTRY_PASSWORD` | Registry password/token |
| `DIGITALOCEAN_ACCESS_TOKEN` | DO API token (Option B) |
| `AWS_ACCESS_KEY_ID` | AWS key (Option C) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret (Option C) |

---

## Troubleshooting

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| 502 Bad Gateway | Backend not ready | `docker compose logs backend` — wait for healthy |
| WebSocket disconnects | Nginx timeout | Check `proxy_read_timeout 3600s` in nginx config |
| Terminal not typing | Docker socket permission | Ensure `/var/run/docker.sock` is mounted and accessible |
| Labs not starting | Scenario images missing | Run `make scenarios` or push to registry |
| Emails not sending | SMTP not configured | Check `EMAIL_HOST_USER` in `.env` |
| Database connection refused | DB not ready | Check `docker compose ps` for database health |
| Out of disk space | Lab containers filling disk | Run `docker system prune -f` and check cleanup task |
| "Failed to initiate payment" | Razorpay SDK loaded without keys | Leave `RAZORPAY_KEY_ID` empty for demo mode |
| Certificate download fails | Scenarios incomplete | User must complete 100% of scenarios for that technology |
| Admin panel access denied | `is_staff=False` | Run: `backend python manage.py shell -c "from django.contrib.auth.models import User; u=User.objects.get(email='YOUR_EMAIL'); u.is_staff=True; u.save()"` |
| Currency rate returns error | API rate limit | exchangerate-api.com has a free tier limit; add fallback rate in settings |

### Payment & Subscription Troubleshooting

```bash
# Check Razorpay configuration
docker compose exec backend python manage.py shell -c "
from django.conf import settings
print('RAZORPAY_KEY_ID:', settings.RAZORPAY_KEY_ID or '(empty — demo mode)')
print('RAZORPAY_KEY_SECRET:', '*****' if settings.RAZORPAY_KEY_SECRET else '(empty)')
"

# Check user's subscriptions
docker compose exec backend python manage.py shell -c "
from apps.billing.models import Subscription
subs = Subscription.objects.filter(user__email='USER_EMAIL')
for s in subs: print(f'{s.technology.name}: {s.subscription_id} ({s.status})')
"

# Manually activate a subscription (for testing)
docker compose exec backend python manage.py shell -c "
from apps.billing.models import Subscription, Technology
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
user = User.objects.get(email='USER_EMAIL')
tech = Technology.objects.get(slug='linux')
sub, created = Subscription.objects.get_or_create(user=user, technology=tech)
sub.is_active = True
sub.start_date = timezone.now()
sub.end_date = timezone.now() + timedelta(days=365)
sub.save()
print(f'Subscription activated: {sub.subscription_id}')
"

# Check certificate eligibility
curl -s http://localhost:8080/api/achievements/certificate/ \
  -H "Authorization: Bearer YOUR_TOKEN" | python3 -m json.tool
```

### Useful Commands

```bash
# ─── Docker Compose (Single Server) ───

# View logs for a specific service
docker compose logs -f backend --tail=100

# Restart a single service
docker compose restart backend

# Run Django management command
docker compose exec backend python manage.py shell

# Check running lab containers
docker ps --filter "name=fixitlab-lab-"

# Clean up old lab containers
docker ps -aq --filter "name=fixitlab-lab-" | xargs -r docker rm -f

# ─── Kubernetes ───

# View pod logs
kubectl -n fixitlab logs deployment/backend --tail=100 -f

# Restart a deployment
kubectl -n fixitlab rollout restart deployment/backend

# Django shell
kubectl -n fixitlab exec -it deployment/backend -- python manage.py shell

# Scale up workers
kubectl -n fixitlab scale deployment/celery-worker --replicas=5

# Check resource usage
kubectl -n fixitlab top pods
```

### Health Check URLs

```bash
curl https://fixitlab.com/api/health/            # Backend API
curl https://fixitlab.com/health                  # Nginx gateway
curl https://fixitlab.com/api/technologies/       # Authenticated endpoint test
```

---

## Cost Estimates

### DigitalOcean

| Component | Option A (Droplet) | Option B (DOKS) |
|-----------|-------------------|-----------------|
| Compute | $24-96/mo | $72-240/mo (3-10 nodes) |
| Managed DB | — (included) | $15-60/mo |
| Managed Redis | — (included) | $15/mo |
| Load Balancer | — (included) | $12/mo |
| Container Registry | — | $5/mo |
| Spaces (backups) | $5/mo | $5/mo |
| **Total** | **$29-101/mo** | **$124-332/mo** |

### AWS

| Component | Monthly Cost |
|-----------|-------------|
| EKS cluster | $73/mo |
| EC2 nodes (3× t3.large + 3× m5.xlarge spot) | $150-300/mo |
| Aurora PostgreSQL (2 instances) | $150/mo |
| ElastiCache Redis (2 nodes) | $100/mo |
| NAT Gateway | $32/mo |
| ALB/NLB | $22/mo |
| ECR | $5/mo |
| S3 + CloudFront | $10/mo |
| **Total** | **$542-842/mo** |

---

## Quick Reference — Deployment Commands

```bash
# ─── DigitalOcean Droplet (simplest) ───
ssh root@YOUR_IP
cd ~/fixitlab
git pull origin main
make scenarios
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# ─── DigitalOcean Kubernetes ───
make build ECR_REGISTRY=registry.digitalocean.com/fixitlab-registry
make push ECR_REGISTRY=registry.digitalocean.com/fixitlab-registry
make deploy

# ─── AWS EKS ───
make build ECR_REGISTRY=$ECR_BASE/fixitlab
make push ECR_REGISTRY=$ECR_BASE/fixitlab
make deploy
make deploy-migrate
```

---

**Need help?** Open an issue or contact the team at admin@fixitlab.com.
