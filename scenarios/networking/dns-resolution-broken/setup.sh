#!/bin/bash
set -e
. /opt/fixitlab/lab-dnsmasq.sh
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
address=/google.com/10.20.0.10
address=/github.com/10.20.0.11
EOF
fixitlab_dnsmasq_reload
fixitlab_resolv_broken
