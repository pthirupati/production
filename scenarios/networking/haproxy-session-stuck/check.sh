#!/bin/bash
# Check that HAProxy maxconn is set to a sufficient value
MAXCONN=$(echo 'show info' | socat /run/haproxy/admin.sock stdio 2>/dev/null | grep '^Maxconn:' | awk '{print $2}')
if [ -z "$MAXCONN" ]; then
  # Fallback: check config file
  MAXCONN=$(grep -E '^\s*maxconn\s+[0-9]+' /etc/haproxy/haproxy.cfg 2>/dev/null | head -1 | awk '{print $2}')
fi
if [ -z "$MAXCONN" ]; then
  echo "FAIL: cannot determine HAProxy maxconn — check haproxy is running and config is valid"
  exit 1
fi
if [ "$MAXCONN" -lt 1000 ]; then
  echo "FAIL: HAProxy maxconn is $MAXCONN — too low for production traffic. Increase to at least 10000."
  exit 1
fi
if systemctl is-active --quiet haproxy 2>/dev/null; then
  echo "OK: HAProxy maxconn is $MAXCONN and service is running"
  exit 0
fi
echo "FAIL: maxconn configured correctly ($MAXCONN) but HAProxy is not running — reload it"
exit 1
