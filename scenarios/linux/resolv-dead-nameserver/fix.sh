#!/bin/bash
set -e
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/app.fixitlab.local/10.20.0.5
EOF
# resolv.conf is often a Docker mount — overwrite in place instead of rm
cat > /etc/resolv.conf <<'EOF'
nameserver 127.0.0.1
EOF
pkill dnsmasq 2>/dev/null || true
sleep 1
dnsmasq
sleep 1
