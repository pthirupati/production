#!/bin/bash
set -e
rm -f /etc/resolv.conf
cat > /etc/resolv.conf <<'EOF'
nameserver 127.0.0.1
EOF
pkill dnsmasq 2>/dev/null || true
sleep 1
dnsmasq 2>/dev/null || true
sleep 1
