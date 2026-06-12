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
if pidof dnsmasq >/dev/null 2>&1; then
  kill -HUP "$(pidof dnsmasq | awk '{print $1}')"
else
  dnsmasq
fi
sleep 1
