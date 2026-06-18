#!/bin/bash
# Check that HAProxy health check uses /healthz and backends are UP
if ! grep -q 'healthz' /etc/haproxy/haproxy.cfg 2>/dev/null; then
  echo "FAIL: HAProxy config still uses wrong health check path — change /health to /healthz"
  exit 1
fi
# Check HAProxy is running
if ! systemctl is-active --quiet haproxy 2>/dev/null; then
  echo "FAIL: HAProxy is not running — start it with: systemctl start haproxy"
  exit 1
fi
# Check for backends in UP state via stats socket
UP_COUNT=$(echo 'show stat' | socat /run/haproxy/admin.sock stdio 2>/dev/null | awk -F',' '$18=="UP"{count++} END{print count+0}')
if [ "$UP_COUNT" -gt 0 ]; then
  echo "OK: HAProxy health check fixed, $UP_COUNT backend(s) are UP"
  exit 0
fi
echo "FAIL: HAProxy configured with /healthz but no backends are UP — reload haproxy and check backend connectivity"
exit 1
