#!/bin/bash
set -e
. /opt/fixitlab/lab-dnsmasq.sh
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
no-resolv
no-poll
address=/google.com/10.20.0.10
address=/github.com/10.20.0.11
EOF
fixitlab_dnsmasq_reload
chattr -i /etc/resolv.conf 2>/dev/null || true
echo 'nameserver 192.0.2.1' > /etc/resolv.conf
echo 'nameserver 198.51.100.1' >> /etc/resolv.conf
