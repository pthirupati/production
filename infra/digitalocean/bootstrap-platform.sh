#!/bin/bash
# Bootstrap a DigitalOcean droplet for FixitLab platform hosting
# Run as root on a fresh Ubuntu 22.04 droplet:
#   curl -sSL https://raw.githubusercontent.com/yourorg/fixitlab/main/infra/digitalocean/bootstrap-platform.sh | bash

set -euo pipefail

echo "=== FixitLab Platform Droplet Bootstrap ==="

apt-get update
apt-get install -y ca-certificates curl gnupg git ufw

# Docker
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Firewall
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# App directory
mkdir -p /opt/fixitlab
chown -R "${SUDO_USER:-root}:${SUDO_USER:-root}" /opt/fixitlab

# Lab network (external to docker compose — used by platform-start.sh)
docker network inspect fixitlab_labs >/dev/null 2>&1 || docker network create fixitlab_labs

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. Clone repo to /opt/fixitlab"
echo "  2. cp env.production.example .env.production && edit secrets"
echo "  3. Add DO SSH key: doctl compute ssh-key import fixitlab-labs --public-key-file ~/.ssh/id_rsa.pub"
echo "  4. ./scripts/deploy.sh production"
echo "  5. python manage.py seed_scenarios"
