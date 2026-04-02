#!/bin/bash
set -e

echo "🔧 Bootstrapping FixitLab node..."

# Update system
apt update -y && apt upgrade -y

# Install Docker
apt install -y docker.io
systemctl enable docker
systemctl start docker

# Install docker-compose
curl -L "https://github.com/docker/compose/releases/download/v2.25.0/docker-compose-linux-x86_64" \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
mv kubectl /usr/local/bin/

echo "✅ FixitLab bootstrap complete"

