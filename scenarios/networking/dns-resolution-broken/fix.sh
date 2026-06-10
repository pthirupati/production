#!/bin/bash
set -e
cat > /etc/resolv.conf <<'EOF'
nameserver 127.0.0.1
EOF
pkill -HUP dnsmasq 2>/dev/null || dnsmasq 2>/dev/null || true
sleep 1
