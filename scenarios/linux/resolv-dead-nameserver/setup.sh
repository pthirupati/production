#!/bin/bash
set -e
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/app.fixitlab.local/10.20.0.5
EOF
if pidof dnsmasq >/dev/null 2>&1; then
  kill -HUP "$(pidof dnsmasq | awk '{print $1}')"
else
  dnsmasq
fi
echo 'nameserver 192.0.2.1' > /etc/resolv.conf
echo "dnsmasq on 127.0.0.1 — fix resolv.conf to use it"
