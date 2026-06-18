#!/bin/bash
# Check that /etc/cron.daily is not world-writable
CRON_PERM=$(stat -c '%a' /etc/cron.daily 2>/dev/null)
if [ -z "$CRON_PERM" ]; then
  echo "FAIL: /etc/cron.daily not found or stat failed"
  exit 1
fi
# World-writable means the last digit is 2, 3, 6, or 7 (write bit set for others)
OTHER_WRITE=$((CRON_PERM % 10))
if [ "$OTHER_WRITE" -ge 2 ] && [ "$OTHER_WRITE" -ne 4 ] && [ "$OTHER_WRITE" -ne 5 ]; then
  echo "FAIL: /etc/cron.daily has permissions $CRON_PERM — world-writable! Fix with: chmod 755 /etc/cron.daily"
  exit 1
fi
# Also check owner is root
CRON_OWNER=$(stat -c '%U' /etc/cron.daily 2>/dev/null)
if [ "$CRON_OWNER" != "root" ]; then
  echo "FAIL: /etc/cron.daily is owned by '$CRON_OWNER' not root — fix with: chown root:root /etc/cron.daily"
  exit 1
fi
echo "OK: /etc/cron.daily has permissions $CRON_PERM and is owned by root"
exit 0
