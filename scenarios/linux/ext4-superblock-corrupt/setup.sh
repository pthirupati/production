#!/bin/bash
# Create loop-mounted ext4 filesystem at container start (requires privileged lab container).
set -e
mkdir -p /data
if [ ! -f /data.img ]; then
  dd if=/dev/zero of=/data.img bs=1M count=100 status=none
  mkfs.ext4 -F /data.img >/dev/null 2>&1
fi
umount /data 2>/dev/null || true
mount -o loop /data.img /data 2>/dev/null || true
echo corrupt > /data/.marker 2>/dev/null || true
# Simulate dirty filesystem for fsck practice
tune2fs -c 1 /data.img 2>/dev/null || true
