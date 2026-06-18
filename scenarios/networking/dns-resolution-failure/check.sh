#!/bin/bash
# Check that DNS resolution is working
if host google.com >/dev/null 2>&1; then
  echo "OK: DNS resolution is working"
  exit 0
fi
# Check resolv.conf for a valid nameserver
if grep -q 'nameserver' /etc/resolv.conf; then
  BAD=$(grep 'nameserver' /etc/resolv.conf | grep -v '8.8.8.8\|1.1.1.1\|8.8.4.4\|1.0.0.1\|9.9.9.9' | head -1)
  if [ -n "$BAD" ]; then
    echo "FAIL: resolv.conf still contains unreachable nameserver — $BAD"
    exit 1
  fi
fi
echo "FAIL: DNS resolution is not working — check /etc/resolv.conf and network connectivity"
exit 1
