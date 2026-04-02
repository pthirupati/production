#!/bin/bash
# ══════════════════════════════════════════════════════════════
# FixitLab — Production Deploy Script
# Run this on your VPS to deploy FixitLab with SSL
#
# Prerequisites:
#   - Ubuntu 22.04+ or Debian 12+
#   - Domain fixitlab.in pointed to this server's IP
#   - At least 4GB RAM, 2 vCPUs, 40GB SSD
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# ══════════════════════════════════════════════════════════════
set -euo pipefail

DOMAIN="fixitlab.in"
EMAIL="admin@fixitlab.in"
PROJECT_DIR="/opt/fixitlab"
COMPOSE_FILE="docker-compose.prod.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
step() { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

# ── Check root ──
if [ "$(id -u)" -ne 0 ]; then
    err "This script must be run as root. Use: sudo ./deploy.sh"
fi

step "1/8 — System Prerequisites"

# Update system
apt-get update -y && apt-get upgrade -y
apt-get install -y curl git ufw fail2ban

# Install Docker if not present
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log "Docker installed"
else
    log "Docker already installed ($(docker --version))"
fi

# Install Docker Compose plugin if not present
if ! docker compose version &>/dev/null; then
    log "Installing Docker Compose plugin..."
    apt-get install -y docker-compose-plugin
    log "Docker Compose installed"
else
    log "Docker Compose already installed"
fi

step "2/8 — Firewall Configuration"

ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP (for ACME challenge + redirect)
ufw allow 443/tcp    # HTTPS
ufw --force enable
log "Firewall configured (22, 80, 443 open)"

step "3/8 — Fail2Ban (Brute-force Protection)"

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
systemctl enable fail2ban
systemctl restart fail2ban
log "Fail2Ban configured"

step "4/8 — Project Setup"

if [ ! -d "$PROJECT_DIR" ]; then
    log "Cloning project..."
    warn "You need to copy your project to $PROJECT_DIR"
    warn "  Option A: git clone your-repo $PROJECT_DIR"
    warn "  Option B: rsync -avz ./fixitlab-main/ root@your-server:$PROJECT_DIR/"
    warn ""
    warn "For now, using current directory..."
    PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fi

cd "$PROJECT_DIR"

# Check environment file
if [ ! -f ".env.production" ]; then
    if [ -f "env.production.example" ]; then
        cp env.production.example .env.production
        warn ".env.production created from template!"
        warn "IMPORTANT: Edit .env.production with your real values before continuing:"
        warn "  nano .env.production"
        warn ""
        warn "At minimum, change:"
        warn "  - DJANGO_SECRET_KEY (generate one)"
        warn "  - POSTGRES_PASSWORD"
        warn "  - REDIS_PASSWORD"
        warn "  - SUPERUSER_PASSWORD"
        warn "  - EMAIL_HOST_USER / EMAIL_HOST_PASSWORD"
        warn ""
        read -p "Press Enter after editing .env.production (or Ctrl+C to abort)..."
    else
        err ".env.production not found. Copy env.production.example and fill in values."
    fi
fi

log "Project directory: $PROJECT_DIR"

step "5/8 — Build Scenario Docker Images"

# Build scenario images (labs need them)
if [ -d "scenarios" ]; then
    log "Building scenario images..."
    for scenario_dir in scenarios/*/; do
        for sd in "$scenario_dir"*/; do
            if [ -f "$sd/Dockerfile" ]; then
                name=$(basename "$sd")
                log "  Building fixitlab/scenario-$name..."
                docker build -t "fixitlab/scenario-$name" "$sd" -q || warn "  Failed to build $name"
            fi
        done
    done
    log "Scenario images built"
else
    warn "No scenarios/ directory found — skipping scenario image builds"
fi

step "6/8 — Initial SSL Certificate (Let's Encrypt)"

# Create temp nginx for ACME challenge
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
    log "Getting initial SSL certificate for $DOMAIN..."

    # Create a minimal nginx to serve ACME challenge
    mkdir -p /tmp/certbot-www
    docker run -d --name certbot-nginx \
        -p 80:80 \
        -v /tmp/certbot-www:/var/www/certbot \
        nginx:alpine sh -c "cat > /etc/nginx/conf.d/default.conf << 'NEOF'
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'ok'; }
}
NEOF
nginx -g 'daemon off;'" 2>/dev/null || true

    sleep 3

    # Get certificate
    docker run --rm \
        -v certbot_certs:/etc/letsencrypt \
        -v /tmp/certbot-www:/var/www/certbot \
        certbot/certbot certonly \
        --webroot -w /var/www/certbot \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos \
        --non-interactive || {
            docker rm -f certbot-nginx 2>/dev/null
            err "Failed to get SSL certificate. Make sure $DOMAIN points to this server's IP."
        }

    docker rm -f certbot-nginx 2>/dev/null
    rm -rf /tmp/certbot-www

    # Copy certs to Docker volume
    docker volume create certbot_certs 2>/dev/null || true
    log "SSL certificate obtained for $DOMAIN"
else
    log "SSL certificate already exists for $DOMAIN"
fi

step "7/8 — Deploy Application"

log "Building and starting all services..."
docker compose -f "$COMPOSE_FILE" build
docker compose -f "$COMPOSE_FILE" up -d

# Wait for backend health
log "Waiting for backend to be healthy..."
TRIES=0
until docker compose -f "$COMPOSE_FILE" exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" 2>/dev/null; do
    TRIES=$((TRIES + 1))
    if [ "$TRIES" -gt 30 ]; then
        err "Backend failed to start. Check: docker compose -f $COMPOSE_FILE logs backend"
    fi
    sleep 5
done
log "Backend is healthy"

step "8/8 — Post-Deploy Verification"

echo ""
log "Checking HTTPS..."
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 "https://$DOMAIN/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    log "HTTPS working (200 OK)"
else
    warn "HTTPS returned $HTTP_CODE — may need DNS propagation time"
fi

API_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 "https://$DOMAIN/api/health/" 2>/dev/null || echo "000")
if [ "$API_CODE" = "200" ]; then
    log "API health check passed"
else
    warn "API health returned $API_CODE"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  FixitLab deployed successfully!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  🌐  Website:    ${CYAN}https://$DOMAIN${NC}"
echo -e "  🔧  API:        ${CYAN}https://$DOMAIN/api/health/${NC}"
echo -e "  👤  Admin:      ${CYAN}https://$DOMAIN/admin${NC}"
echo -e "  📧  Mailbox:    ${CYAN}https://$DOMAIN/mailbox/${NC}"
echo ""
echo -e "  📝  Logs:       docker compose -f $COMPOSE_FILE logs -f"
echo -e "  🔄  Restart:    docker compose -f $COMPOSE_FILE restart"
echo -e "  ⬆️   Update:     git pull && docker compose -f $COMPOSE_FILE up -d --build"
echo ""
echo -e "  ${YELLOW}Next steps:${NC}"
echo -e "    1. Set up automated backups (see deploy docs)"
echo -e "    2. Configure GitHub/Google OAuth in .env.production"
echo -e "    3. Set up monitoring (Uptime Robot, Grafana, etc.)"
echo -e "    4. Add more scenarios to scenarios/ directory"
echo ""
