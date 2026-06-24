#!/bin/bash
# ══════════════════════════════════════════════════════════════
# FixitLab — Production Deploy Script
# Run from: /home/fixitlab/fixitlab-main/scripts/deploy.sh
#
# Server: 150.136.13.58 (Oracle Cloud, Oracle Linux 9)
# Domain: fixitlab.in
#
# Prerequisites:
#   - Oracle Linux 8/9, RHEL 8/9, Ubuntu 22.04+, or Debian 12+
#   - DNS A record: fixitlab.in → 150.136.13.58
#   - DNS A/CNAME: www.fixitlab.in → fixitlab.in
#   - Ports 80, 443 open in OCI Security List / cloud firewall
#   - .env.production with all credentials filled in
#
# Usage:
#   chmod +x scripts/deploy.sh
#   sudo ./scripts/deploy.sh
# ══════════════════════════════════════════════════════════════
set -euo pipefail

DOMAIN="fixitlab.in"
EMAIL="fixitlab.admin@gmail.com"
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

# ── Resolve project directory (parent of scripts/) ──
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
log "Project directory: $PROJECT_DIR"

# ══════════════════════════════════════════════════════════════
step "1/7 — System Prerequisites"
# ══════════════════════════════════════════════════════════════

# Detect OS family
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="$ID"
    OS_FAMILY="${ID_LIKE:-$ID}"
else
    OS_ID="unknown"
    OS_FAMILY="unknown"
fi
log "Detected OS: $OS_ID (family: $OS_FAMILY)"

# Install system packages
if echo "$OS_FAMILY" | grep -qiE 'rhel|fedora|centos|oracle'; then
    dnf install -y curl git firewalld 2>/dev/null || yum install -y curl git firewalld 2>/dev/null || true
    # fail2ban is optional — not in default Oracle Linux repos
    if ! dnf install -y fail2ban 2>/dev/null && ! yum install -y fail2ban 2>/dev/null; then
        warn "fail2ban not available — SSH protected by firewalld"
    fi
elif echo "$OS_FAMILY" | grep -qiE 'debian|ubuntu'; then
    apt-get update -y
    apt-get install -y curl git ufw fail2ban
fi

# Install REAL Docker (not podman)
_is_real_docker() {
    command -v docker &>/dev/null && docker --version 2>/dev/null | grep -qi "docker" && ! docker --version 2>/dev/null | grep -qi "podman"
}

if ! _is_real_docker; then
    log "Installing Docker Engine..."

    # Remove podman emulation
    dnf remove -y podman-docker 2>/dev/null || yum remove -y podman-docker 2>/dev/null || true
    unset DOCKER_HOST
    rm -f /etc/profile.d/podman-docker.sh 2>/dev/null
    sed -i '/DOCKER_HOST.*podman/d' /root/.bashrc /etc/environment 2>/dev/null || true
    podman system reset --force 2>/dev/null || true

    if echo "$OS_FAMILY" | grep -qiE 'rhel|fedora|centos|oracle'; then
        dnf install -y dnf-utils 2>/dev/null || yum install -y yum-utils 2>/dev/null || true
        dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo 2>/dev/null || \
            yum-config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo 2>/dev/null || true
        dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || \
            yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin 2>/dev/null || {
                curl -fsSL https://get.docker.com | sh
            }
    else
        curl -fsSL https://get.docker.com | sh
    fi

    systemctl enable docker
    systemctl start docker
    log "Docker installed ($(docker --version))"
else
    log "Docker already installed ($(docker --version))"
fi

# Ensure DOCKER_HOST is correct
unset DOCKER_HOST
export DOCKER_HOST=unix:///var/run/docker.sock

# Verify docker compose
if ! docker compose version &>/dev/null; then
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d '"' -f4)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
log "Docker Compose: $(docker compose version)"

# ══════════════════════════════════════════════════════════════
step "2/7 — Firewall"
# ══════════════════════════════════════════════════════════════

if echo "$OS_FAMILY" | grep -qiE 'rhel|fedora|centos|oracle'; then
    systemctl enable firewalld 2>/dev/null || true
    systemctl start firewalld 2>/dev/null || true
    firewall-cmd --permanent --add-service=ssh 2>/dev/null || true
    firewall-cmd --permanent --add-service=http 2>/dev/null || true
    firewall-cmd --permanent --add-service=https 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    log "firewalld: SSH, HTTP, HTTPS open"
else
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    log "ufw: SSH, HTTP, HTTPS open"
fi

# Brute-force protection
if command -v fail2ban-server &>/dev/null; then
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
[sshd]
enabled = true
port = 22
EOF
    systemctl enable fail2ban 2>/dev/null || true
    systemctl restart fail2ban 2>/dev/null || true
    log "fail2ban configured"
else
    # SSH rate limiting via firewalld
    if command -v firewall-cmd &>/dev/null; then
        firewall-cmd --permanent --add-rich-rule='rule family="ipv4" service name="ssh" limit value="5/m" accept' 2>/dev/null || true
        firewall-cmd --reload 2>/dev/null || true
        log "SSH rate limiting via firewalld"
    fi
fi

# ══════════════════════════════════════════════════════════════
step "3/7 — Environment Check"
# ══════════════════════════════════════════════════════════════

if [ ! -f ".env" ]; then
    err ".env.production not found! Copy it to $PROJECT_DIR/.env.production before deploying."
fi

# CRITICAL: Remove dev .env to prevent password mismatch.
# Docker compose reads .env for ${VAR} substitution (redis/rabbitmq passwords).
# If .env has dev passwords but .env.production has real ones, services can't connect.

# Clean up any macOS resource fork files
find . -name '._*' -delete 2>/dev/null || true
find . -name '.DS_Store' -delete 2>/dev/null || true

log "Environment verified"

# ══════════════════════════════════════════════════════════════
step "4/7 — Build Scenario Images"
# ══════════════════════════════════════════════════════════════

if [ -d "scenarios" ]; then
    for scenario_dir in scenarios/*/; do
        for sd in "$scenario_dir"*/; do
            if [ -f "$sd/Dockerfile" ]; then
                name=$(basename "$sd")
                log "Building fixitlab/scenario-$name..."
                docker build -t "fixitlab/scenario-$name" "$sd" -q || warn "Failed to build $name"
            fi
        done
    done
    log "Scenario images built"
fi

# ══════════════════════════════════════════════════════════════
step "5/7 — SSL Certificate (Let's Encrypt)"
# ══════════════════════════════════════════════════════════════

# Docker compose names volumes with project prefix: fixitlab-main_certbot_certs
COMPOSE_PROJECT="$(basename "$PROJECT_DIR")"
CERT_VOLUME="${COMPOSE_PROJECT}_certbot_certs"

# ── Check if valid cert already exists ──
CERT_EXISTS=false
CERT_VALID_DATE=""

if docker volume inspect "$CERT_VOLUME" &>/dev/null; then
    # Check if cert exists and is valid
    CERT_CHECK=$(docker run --rm -v "$CERT_VOLUME":/certs alpine \
        sh -c "if [ -f /certs/live/$DOMAIN/fullchain.pem ]; then \
            openssl x509 -in /certs/live/$DOMAIN/fullchain.pem -noout -dates 2>/dev/null; \
        else \
            echo 'NOT_FOUND'; \
        fi" 2>/dev/null)

    if echo "$CERT_CHECK" | grep -q "notAfter"; then
        # Cert exists, check if it expires soon
        EXPIRE_DATE=$(echo "$CERT_CHECK" | grep "notAfter" | cut -d'=' -f2)
        EXPIRE_EPOCH=$(date -d "$EXPIRE_DATE" +%s 2>/dev/null || date -j -f "%b %d %T %Z %Y" "$EXPIRE_DATE" +%s 2>/dev/null || echo 0)
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( (EXPIRE_EPOCH - NOW_EPOCH) / 86400 ))

        if [ "$DAYS_LEFT" -gt 30 ]; then
            CERT_EXISTS=true
            CERT_VALID_DATE="Expires in $DAYS_LEFT days"
        else
            warn "Certificate expires in $DAYS_LEFT days (will renew)"
        fi
    fi
fi

if [ "$CERT_EXISTS" = true ]; then
    log "SSL certificate already exists for $DOMAIN ($CERT_VALID_DATE)"
else
    log "Getting SSL certificate for $DOMAIN (using Certbot)..."

    # Stop anything on port 80
    docker stop certbot-nginx 2>/dev/null || true
    docker rm certbot-nginx 2>/dev/null || true

    # Ensure the compose volume exists
    docker volume create "$CERT_VOLUME" 2>/dev/null || true

    # Temp nginx for ACME challenge
    mkdir -p /tmp/certbot-www

    # Start temporary nginx
    docker run -d --name certbot-nginx \
        -p 80:80 \
        -v /tmp/certbot-www:/var/www/certbot \
        -v "$CERT_VOLUME":/etc/letsencrypt \
        nginx:alpine sh -c "
cat > /etc/nginx/conf.d/default.conf << 'NEOF'
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN *.fixitlab.in;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'ACME challenge server'; }
}
NEOF
nginx -g 'daemon off;'" &

    NGINX_PID=$!
    sleep 3

    # ── Attempt certificate generation with retry logic ──
    CERT_ATTEMPT=0
    MAX_ATTEMPTS=3
    RETRY_DELAY=30

    while [ "$CERT_ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
        CERT_ATTEMPT=$((CERT_ATTEMPT + 1))
        log "Certbot attempt $CERT_ATTEMPT/$MAX_ATTEMPTS..."

        if docker run --rm \
            -v "$CERT_VOLUME":/etc/letsencrypt \
            -v /tmp/certbot-www:/var/www/certbot \
            certbot/certbot certonly \
            --webroot -w /var/www/certbot \
            -d "$DOMAIN" \
            -d "www.$DOMAIN" \
            --email "$EMAIL" \
            --agree-tos \
            --non-interactive \
            --preferred-challenges http \
            --register-unsafely-without-email 2>&1 | tee /tmp/certbot-output.log; then
            
            log "SSL certificate obtained successfully for $DOMAIN"
            CERT_ATTEMPT=$MAX_ATTEMPTS  # Exit loop
            break
        else
            if [ "$CERT_ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
                # Check for rate limit error
                if grep -q "rate limit" /tmp/certbot-output.log 2>/dev/null; then
                    WAIT_TIME=$((RETRY_DELAY * CERT_ATTEMPT))
                    warn "Rate limited by Let's Encrypt. Waiting $WAIT_TIME seconds before retry..."
                    sleep $WAIT_TIME
                else
                    warn "Certificate generation attempt $CERT_ATTEMPT failed. Retrying in ${RETRY_DELAY}s..."
                    sleep $RETRY_DELAY
                fi
            else
                err "Failed to get SSL certificate after $MAX_ATTEMPTS attempts. Verify: 1) DNS A record points to this IP, 2) Port 80 is open, 3) Domain is accessible from internet"
            fi
        fi
    done

    docker rm -f certbot-nginx 2>/dev/null
    rm -rf /tmp/certbot-www
fi

# ══════════════════════════════════════════════════════════════
step "6/7 — Deploy Application"
# ══════════════════════════════════════════════════════════════

# Stop any existing deployment cleanly
docker compose --env-file .env -f "$COMPOSE_FILE" down 2>/dev/null || true

# Build and start
log "Building images..."
docker compose --env-file .env -f "$COMPOSE_FILE" build

log "Starting services..."
docker compose --env-file .env -f "$COMPOSE_FILE" up -d

# Wait for backend health
log "Waiting for backend to become healthy (up to 3 minutes)..."
TRIES=0
MAX_TRIES=36
while [ "$TRIES" -lt "$MAX_TRIES" ]; do
    TRIES=$((TRIES + 1))

    # Check if container is running
    if ! docker compose --env-file .env -f "$COMPOSE_FILE" ps backend 2>/dev/null | grep -q "Up\|running"; then
        if [ "$TRIES" -ge 10 ]; then
            warn "Backend container not running after $((TRIES * 5))s. Logs:"
            docker compose --env-file .env -f "$COMPOSE_FILE" logs --tail=30 backend 2>&1 || true
            err "Backend failed to start."
        fi
        sleep 5
        continue
    fi

    # Check health endpoint
    if docker compose --env-file .env -f "$COMPOSE_FILE" exec -T backend \
        python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" 2>/dev/null; then
        break
    fi

    if [ "$TRIES" -ge "$MAX_TRIES" ]; then
        warn "Backend health check failed after 3 minutes. Logs:"
        docker compose --env-file .env -f "$COMPOSE_FILE" logs --tail=40 backend 2>&1 || true
        err "Backend is unhealthy. Fix the issue above and re-run deploy.sh"
    fi
    sleep 5
done
log "Backend is healthy"

log "Running database migrations..."
docker compose --env-file .env -f "$COMPOSE_FILE" exec -T backend python manage.py migrate --noinput

log "Seeding tutorials and content (idempotent)..."
docker compose --env-file .env -f "$COMPOSE_FILE" exec -T backend python manage.py seed_tutorials || warn "seed_tutorials failed — check logs"

# ══════════════════════════════════════════════════════════════
step "7/7 — Verification"
# ══════════════════════════════════════════════════════════════

echo ""

# Check all containers
RUNNING=$(docker compose --env-file .env -f "$COMPOSE_FILE" ps --status running -q 2>/dev/null | wc -l)
TOTAL=$(docker compose --env-file .env -f "$COMPOSE_FILE" ps -q 2>/dev/null | wc -l)
log "Containers: $RUNNING/$TOTAL running"

# Check HTTPS
HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 10 "https://$DOMAIN/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    log "HTTPS working (200 OK)"
elif [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    log "HTTPS responding ($HTTP_CODE redirect)"
else
    warn "HTTPS returned $HTTP_CODE — check DNS propagation and SSL cert"
fi

# Internal health check
API_RESULT=$(docker compose --env-file .env -f "$COMPOSE_FILE" exec -T backend \
    python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health/').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$API_RESULT" | grep -q '"ok"'; then
    log "API health check: OK"
else
    warn "API health check: $API_RESULT"
fi

READY_RESULT=$(docker compose --env-file .env -f "$COMPOSE_FILE" exec -T backend \
    python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health/ready/').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$READY_RESULT" | grep -q '"status"'; then
    log "Readiness check: $(echo "$READY_RESULT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status","?"))' 2>/dev/null || echo OK)"
else
    warn "Readiness check: $READY_RESULT"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  FixitLab deployed successfully!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Website:  ${CYAN}https://$DOMAIN${NC}"
echo -e "  API:      ${CYAN}https://$DOMAIN/api/health/${NC}"
echo -e "  Admin:    ${CYAN}https://$DOMAIN/admin${NC}"
echo ""
echo -e "  ${YELLOW}Useful commands:${NC}"
echo -e "    Logs:     docker compose --env-file .env -f $COMPOSE_FILE logs -f"
echo -e "    Restart:  docker compose --env-file .env -f $COMPOSE_FILE restart"
echo -e "    Status:   docker compose --env-file .env -f $COMPOSE_FILE ps"
echo -e "    Update:   docker compose --env-file .env -f $COMPOSE_FILE up -d --build"
echo ""
