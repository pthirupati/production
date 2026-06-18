#!/bin/bash
# Check that fail2ban SSH jail is enabled and running
if ! systemctl is-active --quiet fail2ban 2>/dev/null; then
  echo "FAIL: fail2ban is not running — start with: systemctl start fail2ban"
  exit 1
fi
# Check jail status
JAIL_STATUS=$(fail2ban-client status sshd 2>/dev/null)
if echo "$JAIL_STATUS" | grep -q 'Status for the jail: sshd'; then
  # Jail exists and is running
  CURRENTLY_FAILED=$(echo "$JAIL_STATUS" | grep 'Currently failed' | awk '{print $NF}')
  echo "OK: fail2ban sshd jail is active (currently failed: ${CURRENTLY_FAILED:-0})"
  exit 0
fi
# Check configuration
if grep -q 'enabled = true' /etc/fail2ban/jail.local 2>/dev/null; then
  echo "FAIL: fail2ban jail.local has sshd enabled but jail is not active — restart fail2ban"
  exit 1
fi
echo "FAIL: fail2ban sshd jail is not enabled — create /etc/fail2ban/jail.local with [sshd] enabled = true"
exit 1
