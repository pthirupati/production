#!/bin/bash
# Check that 'deploy' user no longer has NOPASSWD: ALL
BROAD_GRANT=$(grep -r 'deploy.*NOPASSWD.*\bALL\b$\|deploy.*ALL.*NOPASSWD.*ALL\b$' /etc/sudoers /etc/sudoers.d/ 2>/dev/null | grep -v '#')
if [ -n "$BROAD_GRANT" ]; then
  echo "FAIL: 'deploy' user still has unrestricted NOPASSWD: ALL grant: $BROAD_GRANT"
  echo "      Restrict to specific commands using visudo"
  exit 1
fi
# Check that the restricted grant exists (allows specific service restarts)
RESTRICTED=$(grep -r 'deploy.*NOPASSWD.*systemctl.*restart' /etc/sudoers /etc/sudoers.d/ 2>/dev/null | grep -v '#')
if [ -z "$RESTRICTED" ]; then
  echo "FAIL: 'deploy' user has no sudo grants configured — add restricted grants for systemctl restart nginx/app"
  exit 1
fi
# Verify sudoers syntax
if visudo -c 2>/dev/null; then
  echo "OK: 'deploy' user sudo restricted to specific commands and sudoers syntax is valid"
  exit 0
fi
echo "FAIL: sudoers file has syntax errors — fix with: visudo"
exit 1
