#!/bin/bash
# Local dnsmasq helpers for FixitLab DNS labs.

fixitlab_resolv_local() {
  chattr -i /etc/resolv.conf 2>/dev/null || true
  rm -f /etc/resolv.conf
  cat > /etc/resolv.conf <<'EOF'
nameserver 127.0.0.1
options edns0 trust-ad
EOF
  chmod 644 /etc/resolv.conf
}

fixitlab_dnsmasq_reload() {
  pkill dnsmasq 2>/dev/null || true
  sleep 0.3
  mkdir -p /etc/dnsmasq.d /run/dnsmasq 2>/dev/null || true
  if [ ! -f /etc/dnsmasq.d/fixitlab.conf ]; then
    echo "listen-address=127.0.0.1" > /etc/dnsmasq.d/fixitlab.conf
    echo "bind-interfaces" >> /etc/dnsmasq.d/fixitlab.conf
    echo "no-resolv" >> /etc/dnsmasq.d/fixitlab.conf
    echo "no-poll" >> /etc/dnsmasq.d/fixitlab.conf
  fi
  dnsmasq
  sleep 0.5
}

fixitlab_dns_resolve() {
  local name="$1"
  local tries="${2:-10}"
  local i
  for i in $(seq 1 "$tries"); do
    getent hosts "$name" >/dev/null 2>&1 && return 0
    sleep 0.3
  done
  return 1
}
