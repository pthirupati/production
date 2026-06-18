#!/bin/bash
# Check that port 80 is now accessible and the DROP rule is removed or preceded by ACCEPT
if curl -sf --max-time 5 http://127.0.0.1/ >/dev/null 2>&1; then
  echo "OK: HTTP port 80 is reachable"
  exit 0
fi
# Secondary check: see if DROP rule is still in effect
if iptables -L INPUT -n | grep -q 'DROP.*dpt:80\|DROP.*tcp.*80'; then
  echo "FAIL: iptables DROP rule for port 80 is still active — add an ACCEPT rule before it"
  exit 1
fi
echo "FAIL: port 80 is not responding — verify nginx is running and iptables rules are correct"
exit 1
