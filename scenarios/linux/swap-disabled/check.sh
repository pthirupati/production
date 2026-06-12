#!/bin/bash
swapon --show 2>/dev/null | grep -q swapfile && echo PASS && exit 0
if [ -f /var/run/fixitlab-swap-active ] && grep -q '^/swapfile ' /etc/fstab && [ -f /swapfile ]; then
  SIZE=$(stat -c%s /swapfile 2>/dev/null || echo 0)
  if [ "$SIZE" -ge 250000000 ]; then
    echo PASS && exit 0
  fi
fi
echo FAIL: swapon /swapfile and add to /etc/fstab
exit 1
