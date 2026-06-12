#!/bin/bash
# Local dnsmasq helpers for FixitLab DNS labs.

# Write resolv.conf via bind mount (Docker often bind-mounts the file — rm/truncate fails).
fixitlab_resolv_apply() {
  chattr -i /etc/resolv.conf 2>/dev/null || true
  cat > /tmp/fixitlab-resolv.conf <<EOF
$(printf '%s\n' "$@")
EOF
  chmod 644 /tmp/fixitlab-resolv.conf
  if mountpoint -q /etc/resolv.conf 2>/dev/null; then
    umount /etc/resolv.conf 2>/dev/null || true
  fi
  if mount --bind /tmp/fixitlab-resolv.conf /etc/resolv.conf 2>/dev/null; then
    return 0
  fi
  rm -f /etc/resolv.conf 2>/dev/null || true
  cp /tmp/fixitlab-resolv.conf /etc/resolv.conf 2>/dev/null || \
    cat /tmp/fixitlab-resolv.conf > /etc/resolv.conf
  chmod 644 /etc/resolv.conf 2>/dev/null || true
}

fixitlab_resolv_local() {
  fixitlab_resolv_apply "nameserver 127.0.0.1" "options edns0 trust-ad"
}

fixitlab_resolv_broken() {
  fixitlab_resolv_apply "nameserver 192.0.2.1" "nameserver 198.51.100.1"
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
