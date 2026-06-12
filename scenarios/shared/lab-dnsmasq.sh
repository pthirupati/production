#!/bin/bash
# Local dnsmasq helpers for FixitLab DNS labs.

fixitlab_resolv_write() {
  chattr -i /etc/resolv.conf 2>/dev/null || true
  {
    printf '%s\n' "$@"
  } > /etc/resolv.conf
  chmod 644 /etc/resolv.conf 2>/dev/null || true
}

fixitlab_resolv_local() {
  fixitlab_resolv_write "nameserver 127.0.0.1" "options edns0 trust-ad"
}

fixitlab_resolv_broken() {
  fixitlab_resolv_write "nameserver 192.0.2.1" "nameserver 198.51.100.1"
}

fixitlab_dnsmasq_reload() {
  mkdir -p /etc/dnsmasq.d /run/dnsmasq 2>/dev/null || true
  # Setup already starts dnsmasq — reload config with HUP instead of restart (port 53 stays bound).
  if pgrep -x dnsmasq >/dev/null 2>&1; then
    killall -HUP dnsmasq 2>/dev/null || pkill -HUP -x dnsmasq 2>/dev/null || true
    sleep 0.5
    return 0
  fi
  pkill -x dnsmasq 2>/dev/null || true
  sleep 0.5
  dnsmasq
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
