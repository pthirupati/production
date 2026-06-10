#!/bin/bash
set -e
mkdir -p /mnt/data
sed -i '/\/mnt\/data/ {/dead-beef/d;}' /etc/fstab
if ! grep -q '/mnt/data' /etc/fstab; then
  echo 'tmpfs /mnt/data tmpfs defaults 0 0' >> /etc/fstab
fi
mount /mnt/data 2>/dev/null || true
