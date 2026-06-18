#!/bin/bash
# Check that fail2ban is running successfully
if ! systemctl is-active --quiet fail2ban 2>/dev/null; then
  # Try to get the error
  ERROR=$(journalctl -u fail2ban -n 5 --no-pager 2>/dev/null | grep -i 'error\|failed' | head -2)
  echo "FAIL: fail2ban is not running — ${ERROR:-check config with: fail2ban-client --test}"
  exit 1
fi
# Check that at least one jail is active
JAIL_COUNT=$(fail2ban-client status 2>/dev/null | grep 'Number of jail' | grep -oE '[0-9]+')
if [ -z "$JAIL_COUNT" ] || [ "$JAIL_COUNT" -eq 0 ]; then
  echo "FAIL: fail2ban is running but no jails are active — check /etc/fail2ban/jail.local"
  exit 1
fi
echo "OK: fail2ban is running with $JAIL_COUNT active jail(s)"
exit 0
