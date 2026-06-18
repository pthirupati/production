#!/bin/bash
# Check that Docker is no longer listening on TCP 2375
if ss -tlnp 2>/dev/null | grep -q ':2375 '; then
  echo "FAIL: Docker is still listening on TCP port 2375 — remove tcp:// from /etc/docker/daemon.json and restart"
  exit 1
fi
# Double-check via curl
if curl -sf --max-time 3 http://localhost:2375/version >/dev/null 2>&1; then
  echo "FAIL: Docker API is still accessible on TCP port 2375 without authentication"
  exit 1
fi
# Check daemon.json no longer has TCP binding
if [ -f /etc/docker/daemon.json ] && grep -q 'tcp://' /etc/docker/daemon.json 2>/dev/null; then
  echo "FAIL: /etc/docker/daemon.json still contains tcp:// listener — remove it"
  exit 1
fi
# Check Docker is running
if systemctl is-active --quiet docker 2>/dev/null; then
  echo "OK: Docker TCP exposure removed — daemon listening only on Unix socket"
  exit 0
fi
echo "FAIL: Docker is not running — restart with: systemctl start docker"
exit 1
