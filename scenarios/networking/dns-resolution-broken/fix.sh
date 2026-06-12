#!/bin/bash
set -e
. /opt/fixitlab/lab-dnsmasq.sh
mkdir -p /etc/dnsmasq.d
cat > /etc/dnsmasq.d/fixitlab.conf <<'EOF'
listen-address=127.0.0.1
bind-interfaces
address=/google.com/10.20.0.10
address=/github.com/10.20.0.11
EOF
cat > /etc/resolv.conf <<'EOF'
nameserver 127.0.0.1
EOF
fixitlab_dnsmasq_reload
getent hosts google.com >/dev/null
