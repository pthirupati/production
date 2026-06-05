#!/bin/bash
PERM=$(stat -c '%a' /opt/app/config.env 2>/dev/null)
OWNER=$(stat -c '%U' /opt/app/config.env 2>/dev/null)
if [ "$PERM" = "600" ] && [ "$OWNER" = "appuser" ]; then
  echo "OK: config owned by appuser mode 600"
  exit 0
fi
echo "FAIL: chown appuser /opt/app/config.env && chmod 600"
exit 1
