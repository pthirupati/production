#!/bin/bash
# Check that www-data no longer has ALL=(ALL) NOPASSWD: ALL
SUDO_ENTRY=$(grep -r 'www-data.*ALL.*NOPASSWD.*ALL\|www-data.*\bALL\b.*\bALL\b' /etc/sudoers /etc/sudoers.d/ 2>/dev/null)
if [ -n "$SUDO_ENTRY" ]; then
  echo "FAIL: dangerous sudoers entry still present for www-data: $SUDO_ENTRY"
  echo "      Remove with: rm /etc/sudoers.d/webserver (or edit the relevant file)"
  exit 1
fi
# Verify sudoers syntax is valid
if visudo -c 2>/dev/null; then
  echo "OK: www-data no longer has unrestricted sudo access and sudoers syntax is valid"
  exit 0
fi
echo "FAIL: sudoers file has syntax errors — fix with: visudo -c"
exit 1
