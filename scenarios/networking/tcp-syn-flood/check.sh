#!/bin/bash
# Check that tcp_syncookies is enabled
SYNCOOKIES=$(sysctl -n net.ipv4.tcp_syncookies 2>/dev/null)
if [ "$SYNCOOKIES" = "1" ]; then
  # Also verify backlog is reasonably sized
  BACKLOG=$(sysctl -n net.ipv4.tcp_max_syn_backlog 2>/dev/null)
  if [ -n "$BACKLOG" ] && [ "$BACKLOG" -lt 1024 ]; then
    echo "FAIL: tcp_syncookies enabled but tcp_max_syn_backlog ($BACKLOG) is too small — set to at least 2048"
    exit 1
  fi
  echo "OK: tcp_syncookies is enabled (backlog: ${BACKLOG:-default})"
  exit 0
fi
echo "FAIL: tcp_syncookies is disabled — enable with: sysctl -w net.ipv4.tcp_syncookies=1"
exit 1
