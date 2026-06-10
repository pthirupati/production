#!/bin/bash
set -e
mkdir -p /data
umount /data 2>/dev/null || true
fsck.ext4 -y /data.img >/dev/null 2>&1 || true
mount -o loop /data.img /data 2>/dev/null || true
