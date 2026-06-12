#!/bin/bash
set -e
. /opt/fixitlab/lab-dnsmasq.sh
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
no-resolv
no-poll
address=/app.fixitlab.local/10.20.0.5
EOF
fixitlab_dnsmasq_reload
chattr -i /etc/resolv.conf 2>/dev/null || true
echo 'nameserver 192.0.2.1' > /etc/resolv.conf
echo "dnsmasq on 127.0.0.1 — fix resolv.conf to use it"
