#!/bin/bash
if [ -f /var/lib/dpkg/lock ] || [ -f /var/lib/dpkg/lock-frontend ]; then
  echo "FAIL: rm /var/lib/dpkg/lock /var/lib/dpkg/lock-frontend"
  exit 1
fi
if dpkg --audit 2>/dev/null | grep -q .; then
  echo "FAIL: dpkg --configure -a"
  exit 1
fi
echo PASS && exit 0
