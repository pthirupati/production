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
if ! pidof dnsmasq >/dev/null 2>&1; then
  dnsmasq
fi
sleep 1
