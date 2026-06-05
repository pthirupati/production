#!/bin/bash
set -e
dd if=/dev/zero of=/var/raid1.img bs=1M count=120 status=none
dd if=/dev/zero of=/var/raid2.img bs=1M count=120 status=none
D1=$(losetup -f --show /var/raid1.img)
D2=$(losetup -f --show /var/raid2.img)
echo yes | mdadm --create /dev/md0 --level=1 --raid-devices=2 "$D1" "$D2"
sleep 2
mkfs.ext4 /dev/md0
mkdir -p /data && mount /dev/md0 /data
echo "raid data" > /data/important.txt
# Fail and remove second device — leaves degraded array
mdadm /dev/md0 --fail "$D2" 2>/dev/null || true
mdadm /dev/md0 --remove "$D2" 2>/dev/null || true
echo "$D2" > /etc/fixitlab-raid-spare
echo "RAID degraded — add $D2 back with mdadm --manage /dev/md0 --add"

