#!/bin/bash
if sudo -u devops -n true 2>/dev/null; then
  echo "OK: devops can sudo"
  exit 0
fi
if grep 'ALLL' /etc/sudoers 2>/dev/null; then
  echo "FAIL: typo ALLL in sudoers — should be ALL"
  exit 1
fi
echo "FAIL: devops still cannot sudo"
exit 1
