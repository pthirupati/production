#!/bin/bash
set -e
mkdir -p /opt/fixitlab/backing
dd if=/dev/zero of=/opt/fixitlab/backing/data.img bs=1M count=80 status=none
DEV=$(losetup -f --show /opt/fixitlab/backing/data.img)
mkfs.ext4 -F "$DEV"
mkdir -p /mnt/data
REAL_UUID=$(blkid -s UUID -o value "$DEV")
echo "critical" > /tmp/production.dat
mount "$DEV" /mnt/data && mv /tmp/production.dat /mnt/data/ && umount /mnt/data
echo "$DEV" > /etc/fixitlab-data-dev
echo "UUID=00000000-0000-0000-0000-000000000000 /mnt/data ext4 defaults 0 2" >> /etc/fstab
echo "Real UUID is $REAL_UUID but fstab has wrong value"

