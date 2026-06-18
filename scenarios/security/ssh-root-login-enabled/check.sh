#!/bin/bash
# Check that PermitRootLogin is not 'yes'
ROOT_LOGIN=$(grep -E '^\s*PermitRootLogin\s+' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' | head -1)
if [ "$ROOT_LOGIN" = "yes" ]; then
  echo "FAIL: PermitRootLogin is set to 'yes' in /etc/ssh/sshd_config — change to 'no'"
  exit 1
fi
# Check sshd is running
if ! systemctl is-active --quiet sshd ssh 2>/dev/null; then
  if ! systemctl is-active --quiet ssh 2>/dev/null; then
    echo "FAIL: SSH daemon is not running — reload with: systemctl reload sshd"
    exit 1
  fi
fi
if [ -z "$ROOT_LOGIN" ]; then
  # Default is prohibit-password on modern Ubuntu, which is acceptable
  echo "OK: PermitRootLogin not explicitly set (default prohibit-password applies)"
  exit 0
fi
echo "OK: PermitRootLogin is set to '$ROOT_LOGIN' — direct root SSH login is restricted"
exit 0
