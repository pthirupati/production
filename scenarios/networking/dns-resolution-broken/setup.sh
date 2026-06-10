#!/bin/bash
set -e
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/google.com/10.20.0.10
address=/github.com/10.20.0.11
EOF
pkill dnsmasq 2>/dev/null || true
dnsmasq
echo 'nameserver 192.0.2.1' > /etc/resolv.conf
echo 'nameserver 198.51.100.1' >> /etc/resolv.conf
