#!/bin/bash
if lsattr /etc/myapp/config.env 2>/dev/null | grep -qE '^[^ ]*i'; then
  echo "FAIL: remove immutable flag first (chattr -i)"
  exit 1
fi
grep -q 'PORT=9090' /etc/myapp/config.env && echo PASS && exit 0
echo "FAIL: chattr -i /etc/myapp/config.env then set PORT=9090"
exit 1
