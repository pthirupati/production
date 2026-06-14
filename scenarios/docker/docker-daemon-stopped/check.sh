#!/bin/bash
FAILED=0
if docker info >/dev/null 2>&1; then
  echo "OK: Docker daemon is running"
else
  echo "FAIL: Docker daemon is not running — start with: systemctl start docker"
  FAILED=1
fi
if docker ps >/dev/null 2>&1; then
  echo "OK: docker ps works"
else
  echo "FAIL: docker ps failed"
  FAILED=1
fi
[ $FAILED -eq 0 ] && exit 0
exit 1
