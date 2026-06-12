#!/bin/bash
swapon --show 2>/dev/null | grep -q swapfile && echo PASS && exit 0
if [ -f /var/run/fixitlab-swap-active ] && grep -q '^/swapfile ' /etc/fstab && \
   [ -f /swapfile ] && file /swapfile 2>/dev/null | grep -qi swap; then
  echo PASS && exit 0
fi
echo FAIL: swapon /swapfile and add to /etc/fstab
exit 1
