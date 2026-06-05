#!/bin/bash
set -e
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/app.fixitlab.local/10.20.0.5
EOF
dnsmasq
echo 'nameserver 192.0.2.1' > /etc/resolv.conf
echo "dnsmasq on 127.0.0.1 — fix resolv.conf to use it"

