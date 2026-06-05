#!/bin/bash
if curl -sf http://127.0.0.1/ >/dev/null; then
  echo "OK: port 80 reachable locally"
  exit 0
fi
if iptables -L INPUT -n | grep -q 'dpt:80'; then
  echo "FAIL: iptables still blocking port 80 — remove DROP rule"
  exit 1
fi
echo "FAIL: nginx not responding on port 80"
exit 1
