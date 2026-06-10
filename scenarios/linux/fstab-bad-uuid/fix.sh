#!/bin/bash
set -e
DEV=$(cat /etc/fixitlab-data-dev 2>/dev/null || true)
[ -z "$DEV" ] && DEV=$(losetup -j /var/data.img 2>/dev/null | cut -d: -f1 | head -1)
[ -n "$DEV" ] || exit 1
UUID=$(blkid -s UUID -o value "$DEV" 2>/dev/null || true)
[ -n "$UUID" ] || exit 1
mkdir -p /mnt/data
sed -i "s#^UUID=.*[[:space:]]\+/mnt/data[[:space:]].*#UUID=$UUID /mnt/data ext4 defaults 0 2#" /etc/fstab
grep -q '/mnt/data' /etc/fstab || echo "UUID=$UUID /mnt/data ext4 defaults 0 2" >> /etc/fstab
mount -a 2>/dev/null || mount "$DEV" /mnt/data 2>/dev/null || true
