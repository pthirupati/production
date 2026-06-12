#!/bin/bash
set -e
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/app.fixitlab.local/10.20.0.5
EOF
cat > /etc/resolv.conf <<'EOF'
nameserver 127.0.0.1
EOF
pkill dnsmasq 2>/dev/null || true
dnsmasq
sleep 1
getent hosts app.fixitlab.local >/dev/null
