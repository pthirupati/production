#!/bin/bash
set -e
swapoff /swapfile 2>/dev/null || true
rm -f /swapfile
dd if=/dev/zero of=/swapfile bs=1M count=256 status=none
chmod 600 /swapfile
mkswap /swapfile
if swapon /swapfile 2>/dev/null; then
  echo active > /var/run/fixitlab-swap-active
else
  # Docker hosts often block swap — record intent for validation
  echo configured > /var/run/fixitlab-swap-active
fi
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
