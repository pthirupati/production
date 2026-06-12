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
fixitlab_resolv_local
fixitlab_dnsmasq_reload
fixitlab_dns_resolve app.fixitlab.local
