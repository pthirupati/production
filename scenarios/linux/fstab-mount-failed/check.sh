#!/bin/bash
grep -q '/mnt/data' /etc/fstab || { echo "FAIL: no fstab entry"; exit 1; }
if grep '/mnt/data' /etc/fstab | grep -q 'dead-beef'; then
  echo "FAIL: fstab still has invalid UUID — fix or comment the bad line"
  exit 1
fi
echo "OK: fstab entry fixed"
mount /mnt/data 2>/dev/null || mkdir -p /mnt/data
echo "PASS: fstab corrected"
exit 0
