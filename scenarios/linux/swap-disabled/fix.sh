#!/bin/bash
set -e
swapoff /swapfile 2>/dev/null || true
rm -f /swapfile
dd if=/dev/zero of=/swapfile bs=1M count=256 status=none
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
