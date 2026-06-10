#!/bin/bash
set -e
[ -f /swapfile ] || fallocate -l 256M /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=256
chmod 600 /swapfile
mkswap /swapfile >/dev/null 2>&1 || true
swapon /swapfile
grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
