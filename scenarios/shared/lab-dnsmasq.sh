#!/bin/bash
# Reload local dnsmasq after config/resolv changes (FixitLab DNS labs).

fixitlab_dnsmasq_reload() {
  if pidof dnsmasq >/dev/null 2>&1; then
    pkill -HUP dnsmasq 2>/dev/null || kill -HUP "$(pidof dnsmasq | awk '{print $1}')" 2>/dev/null || true
    sleep 0.5
    return 0
  fi
  dnsmasq 2>/dev/null || true
  sleep 0.5
}
