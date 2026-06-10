#!/bin/bash
DEV=$(cat /etc/fixitlab-data-dev 2>/dev/null)
[ -z "$DEV" ] && DEV=$(losetup -j /var/data.img 2>/dev/null | cut -d: -f1 | head -1)
mount /mnt/data 2>/dev/null || true
mountpoint -q /mnt/data && [ -f /mnt/data/production.dat ] && echo PASS && exit 0
REAL=$(blkid -s UUID -o value "$DEV" 2>/dev/null)
[ -n "$REAL" ] && grep -q "$REAL" /etc/fstab 2>/dev/null && mount -a 2>/dev/null && mountpoint -q /mnt/data && echo PASS && exit 0
echo "FAIL: fix UUID in /etc/fstab for /mnt/data (use blkid) then mount -a"
exit 1
