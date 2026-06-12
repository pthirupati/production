#!/bin/bash
# Local dnsmasq helpers for FixitLab DNS labs.

fixitlab_resolv_write() {
  chattr -i /etc/resolv.conf 2>/dev/null || true
  if [ -L /etc/resolv.conf ]; then
    rm -f /etc/resolv.conf
  fi
  {
    printf '%s\n' "$@"
  } > /etc/resolv.conf
  chmod 644 /etc/resolv.conf 2>/dev/null || true
}

fixitlab_resolv_local() {
  fixitlab_resolv_write "nameserver 127.0.0.1"
}

fixitlab_resolv_broken() {
  fixitlab_resolv_write "nameserver 192.0.2.1" "nameserver 198.51.100.1"
}

fixitlab_dnsmasq_reload() {
  mkdir -p /etc/dnsmasq.d /run/dnsmasq 2>/dev/null || true
  # Ubuntu's /etc/dnsmasq.conf has conf-dir commented out — bare `dnsmasq` ignores
  # /etc/dnsmasq.d/fixitlab.conf. Always start with an explicit config file.
  pkill -x dnsmasq 2>/dev/null || true
  sleep 0.2
  dnsmasq -k -p 53 -a 127.0.0.1 --no-resolv --no-poll \
    -C /etc/dnsmasq.d/fixitlab.conf 2>/dev/null &
  sleep 0.5
}

fixitlab_dns_resolve() {
  local name="$1"
  local tries="${2:-30}"
  local i
  for i in $(seq 1 "$tries"); do
    getent hosts "$name" >/dev/null 2>&1 && return 0
    sleep 0.3
  done
  return 1
}
